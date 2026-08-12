#!/usr/bin/env python3
"""Local telemetry, adaptive routing, and reporting for Agent Dispatch.

Standard-library only. Raw events are append-only JSONL; learned state is derived.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA = 1
DEFAULT_CONFIG = {
    "schema": SCHEMA,
    "min_samples": 8,
    "exploration_rate": 0.05,
    "half_life_days": 45.0,
    "prior_success": {
        "frontier": 0.97,
        "general": 0.90,
        "cheap": 0.78,
        "alternate_pool": 0.82,
    },
    "scarcity_penalty": {
        "frontier": 0.22,
        "general": 0.08,
        "cheap": 0.02,
        "alternate_pool": 0.01,
    },
    "rework_penalty": 0.35,
    "escalation_penalty": 0.16,
    "failure_penalty": 0.55,
    "latency_penalty_per_minute": 0.002,
}

DEFAULT_CLASS_PRIORS = {
    "architecture": "frontier",
    "planning": "frontier",
    "ambiguous_debugging": "frontier",
    "adjudication": "frontier",
    "bounded_implementation": "general",
    "ordinary_debugging": "general",
    "code_review": "general",
    "investigation": "general",
    "repository_inventory": "alternate_pool",
    "mechanical_edit": "cheap",
    "formatting": "cheap",
    "simple_test": "cheap",
    "metadata_extraction": "cheap",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def state_dir() -> Path:
    override = os.environ.get("AGENT_DISPATCH_HOME")
    if override:
        return Path(override).expanduser()
    codex = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    return codex / "agent-dispatch"


def paths() -> tuple[Path, Path, Path]:
    root = state_dir()
    return root / "telemetry.jsonl", root / "routing-state.json", root / "config.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")


def init_state() -> None:
    telem, route, cfg = paths()
    telem.parent.mkdir(parents=True, exist_ok=True)
    telem.touch(exist_ok=True)
    if not cfg.exists():
        cfg.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    if not route.exists():
        route.write_text(json.dumps({"schema": SCHEMA, "generated_at": now_iso(), "routes": {}}, indent=2) + "\n", encoding="utf-8")
    print(f"Agent Dispatch state initialized at {telem.parent}")


def parse_boolish(value: str | None) -> bool | None:
    if value is None:
        return None
    v = value.lower()
    if v in {"1", "true", "yes", "pass", "passed"}:
        return True
    if v in {"0", "false", "no", "fail", "failed"}:
        return False
    raise argparse.ArgumentTypeError(f"expected boolean-ish value, got {value!r}")


def record(args: argparse.Namespace) -> None:
    init_state_silent()
    telem, _, _ = paths()
    event = {
        "schema": SCHEMA,
        "timestamp": args.timestamp or now_iso(),
        "event": "delegated_task",
        "task_id": args.task_id,
        "parent_task_id": args.parent_task_id,
        "project": args.project,
        "task_class": args.task_class,
        "domain": args.domain,
        "front_door_model": args.front_door_model,
        "front_door_reasoning": args.front_door_reasoning,
        "worker_model": args.worker_model,
        "worker_reasoning": args.worker_reasoning,
        "tier": args.tier,
        "parallel": args.parallel,
        "shadow": args.shadow,
        "duration_s": args.duration_s,
        "input_tokens": args.input_tokens,
        "output_tokens": args.output_tokens,
        "usage_source": args.usage_source,
        "retries": args.retries,
        "escalations": args.escalations,
        "review_pass": args.review_pass,
        "tests_pass": args.tests_pass,
        "rework": args.rework,
        "accepted": args.accepted,
        "outcome": args.outcome,
        "notes": args.notes,
        "skill_version": args.skill_version,
    }
    event = {k: v for k, v in event.items() if v is not None}
    with telem.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")
    print(json.dumps(event, indent=2, sort_keys=True))


def init_state_silent() -> None:
    telem, route, cfg = paths()
    telem.parent.mkdir(parents=True, exist_ok=True)
    telem.touch(exist_ok=True)
    if not cfg.exists():
        cfg.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
    if not route.exists():
        route.write_text(json.dumps({"schema": SCHEMA, "generated_at": now_iso(), "routes": {}}, indent=2) + "\n", encoding="utf-8")


def events() -> list[dict[str, Any]]:
    telem, _, _ = paths()
    init_state_silent()
    out = []
    for i, line in enumerate(telem.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
            if e.get("event") == "delegated_task":
                out.append(e)
        except json.JSONDecodeError:
            print(f"warning: skipping invalid telemetry line {i}", file=sys.stderr)
    return out


def age_weight(ts: str, half_life_days: float) -> float:
    try:
        then = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=dt.timezone.utc)
        age = max(0.0, (dt.datetime.now(dt.timezone.utc) - then).total_seconds() / 86400.0)
        return 0.5 ** (age / max(1e-6, half_life_days))
    except Exception:
        return 1.0


def route_key(e: dict[str, Any]) -> str:
    return "|".join([
        str(e.get("project") or "*"),
        str(e.get("task_class") or "unknown"),
        str(e.get("domain") or "*"),
        str(e.get("worker_model") or e.get("tier") or "unknown"),
        str(e.get("worker_reasoning") or "*"),
    ])


def score_event(e: dict[str, Any], cfg: dict[str, Any]) -> float:
    accepted = e.get("accepted")
    score = 1.0 if accepted is True else 0.0
    if accepted is False:
        score -= cfg["failure_penalty"]
    if e.get("rework") is True:
        score -= cfg["rework_penalty"]
    score -= cfg["escalation_penalty"] * float(e.get("escalations", 0) or 0)
    score -= cfg["scarcity_penalty"].get(e.get("tier"), 0.05)
    if e.get("duration_s") is not None:
        score -= cfg["latency_penalty_per_minute"] * (float(e["duration_s"]) / 60.0)
    return score


def tune(_: argparse.Namespace) -> None:
    init_state_silent()
    _, route_path, cfg_path = paths()
    cfg = load_json(cfg_path, DEFAULT_CONFIG)
    grouped: dict[str, list[tuple[dict[str, Any], float]]] = defaultdict(list)
    for e in events():
        w = age_weight(str(e.get("timestamp", "")), float(cfg["half_life_days"]))
        grouped[route_key(e)].append((e, w))
    routes = {}
    for key, rows in grouped.items():
        total_w = sum(w for _, w in rows) or 1.0
        accepted_w = sum(w for e, w in rows if e.get("accepted") is True)
        rework_w = sum(w for e, w in rows if e.get("rework") is True)
        escalation_w = sum(w * float(e.get("escalations", 0) or 0) for e, w in rows)
        utilities = [(score_event(e, cfg), w) for e, w in rows]
        utility = sum(s * w for s, w in utilities) / total_w
        durations = [float(e["duration_s"]) for e, _ in rows if e.get("duration_s") is not None]
        route = {
            "samples": len(rows),
            "effective_samples": round(total_w, 3),
            "clean_success_rate": round(accepted_w / total_w, 4),
            "rework_rate": round(rework_w / total_w, 4),
            "mean_escalations": round(escalation_w / total_w, 4),
            "utility": round(utility, 4),
            "median_duration_s": round(statistics.median(durations), 3) if durations else None,
        }
        routes[key] = route
    state = {"schema": SCHEMA, "generated_at": now_iso(), "routes": routes}
    route_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Updated {route_path} from {sum(len(v) for v in grouped.values())} telemetry events")


def candidates(task_class: str, domain: str | None, project: str | None, state: dict[str, Any], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    matches = []
    for key, metrics in state.get("routes", {}).items():
        p, tc, d, model, reasoning = key.split("|", 4)
        if tc != task_class:
            continue
        specificity = 0
        if project and p == project:
            specificity += 2
        elif p != "*":
            continue
        if domain and d == domain:
            specificity += 1
        elif d != "*":
            continue
        if metrics.get("samples", 0) < cfg["min_samples"]:
            continue
        matches.append({"project": p, "domain": d, "model": model, "reasoning": reasoning, "specificity": specificity, **metrics})
    return sorted(matches, key=lambda x: (x["specificity"], x["utility"], x["clean_success_rate"]), reverse=True)


def recommend(args: argparse.Namespace) -> None:
    init_state_silent()
    _, route_path, cfg_path = paths()
    state = load_json(route_path, {"routes": {}})
    cfg = load_json(cfg_path, DEFAULT_CONFIG)
    cs = candidates(args.task_class, args.domain, args.project, state, cfg)
    prior_tier = DEFAULT_CLASS_PRIORS.get(args.task_class, "general")
    result: dict[str, Any] = {
        "task_class": args.task_class,
        "domain": args.domain,
        "project": args.project,
        "default_tier": prior_tier,
        "learned_override": False,
        "recommendation": {"tier": prior_tier},
    }
    if cs:
        best = cs[0]
        result["learned_override"] = True
        result["recommendation"] = {
            "model_or_tier": best["model"],
            "reasoning": None if best["reasoning"] == "*" else best["reasoning"],
            "evidence": {k: best[k] for k in ("samples", "effective_samples", "clean_success_rate", "rework_rate", "mean_escalations", "utility", "specificity")},
        }
    result["exploration_rate"] = cfg["exploration_rate"]
    print(json.dumps(result, indent=2, sort_keys=True))


def report(args: argparse.Namespace) -> None:
    es = events()
    if args.project:
        es = [e for e in es if e.get("project") == args.project]
    if args.days:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)
        filtered = []
        for e in es:
            try:
                ts = dt.datetime.fromisoformat(str(e.get("timestamp", "")).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt.timezone.utc)
                if ts >= cutoff:
                    filtered.append(e)
            except Exception:
                pass
        es = filtered
    by_front: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in es:
        key = "/".join(filter(None, [str(e.get("front_door_model") or "unknown"), str(e.get("front_door_reasoning") or "")]))
        by_front[key].append(e)
    rows = []
    for front, items in by_front.items():
        n = len(items)
        accepted = sum(1 for e in items if e.get("accepted") is True)
        rework = sum(1 for e in items if e.get("rework") is True)
        escal = sum(int(e.get("escalations", 0) or 0) for e in items)
        durations = [float(e["duration_s"]) for e in items if e.get("duration_s") is not None]
        tokens = [int(e.get("input_tokens", 0) or 0) + int(e.get("output_tokens", 0) or 0) for e in items if e.get("usage_source") == "measured"]
        rows.append({
            "front_door": front,
            "delegated_tasks": n,
            "clean_success_rate": round(accepted / n, 4) if n else None,
            "rework_rate": round(rework / n, 4) if n else None,
            "escalations_per_task": round(escal / n, 4) if n else None,
            "median_duration_s": round(statistics.median(durations), 3) if durations else None,
            "measured_tokens_sum": sum(tokens) if tokens else None,
        })
    rows.sort(key=lambda r: ((r["clean_success_rate"] or -1), -(r["rework_rate"] or 0)), reverse=True)
    print(json.dumps({"events": len(es), "front_doors": rows}, indent=2, sort_keys=True))


def explain(args: argparse.Namespace) -> None:
    recommend(args)


def reset(args: argparse.Namespace) -> None:
    telem, route, cfg = paths()
    if args.learned_only:
        route.parent.mkdir(parents=True, exist_ok=True)
        route.write_text(json.dumps({"schema": SCHEMA, "generated_at": now_iso(), "routes": {}}, indent=2) + "\n", encoding="utf-8")
        print(f"Reset learned routing state; retained telemetry at {telem}")
        return
    if not args.yes:
        raise SystemExit("Refusing to delete telemetry without --yes (or use --learned-only).")
    for p in (telem, route, cfg):
        if p.exists():
            p.unlink()
    print(f"Reset Agent Dispatch state at {state_dir()}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(func=lambda _: init_state())

    r = sub.add_parser("record")
    r.add_argument("--task-id", required=True)
    r.add_argument("--parent-task-id")
    r.add_argument("--project")
    r.add_argument("--task-class", required=True)
    r.add_argument("--domain")
    r.add_argument("--front-door-model")
    r.add_argument("--front-door-reasoning")
    r.add_argument("--worker-model")
    r.add_argument("--worker-reasoning")
    r.add_argument("--tier", choices=["frontier", "general", "cheap", "alternate_pool"], required=True)
    r.add_argument("--parallel", type=parse_boolish)
    r.add_argument("--shadow", type=parse_boolish)
    r.add_argument("--duration-s", type=float)
    r.add_argument("--input-tokens", type=int)
    r.add_argument("--output-tokens", type=int)
    r.add_argument("--usage-source", choices=["measured", "derived", "unknown"], default="unknown")
    r.add_argument("--retries", type=int, default=0)
    r.add_argument("--escalations", type=int, default=0)
    r.add_argument("--review-pass", type=parse_boolish)
    r.add_argument("--tests-pass", type=parse_boolish)
    r.add_argument("--rework", type=parse_boolish)
    r.add_argument("--accepted", type=parse_boolish)
    r.add_argument("--outcome", choices=["pass", "partial", "blocked", "fail"])
    r.add_argument("--notes")
    r.add_argument("--skill-version")
    r.add_argument("--timestamp")
    r.set_defaults(func=record)

    t = sub.add_parser("tune")
    t.set_defaults(func=tune)

    for name, func in (("recommend", recommend), ("explain", explain)):
        q = sub.add_parser(name)
        q.add_argument("--task-class", required=True)
        q.add_argument("--domain")
        q.add_argument("--project")
        q.set_defaults(func=func)

    rep = sub.add_parser("report")
    rep.add_argument("--project")
    rep.add_argument("--days", type=int)
    rep.set_defaults(func=report)

    rs = sub.add_parser("reset")
    rs.add_argument("--learned-only", action="store_true")
    rs.add_argument("--yes", action="store_true")
    rs.set_defaults(func=reset)
    return p


def main() -> int:
    args = parser().parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
