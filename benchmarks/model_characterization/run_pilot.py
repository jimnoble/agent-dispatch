#!/usr/bin/env python3
"""Run one model route through the synthetic characterization suite."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from score import score_response


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_TASKS_PATH = HERE / "tasks.json"
SCHEMA_PATH = HERE / "response-schema.json"
DISPATCH = REPO / "scripts" / "dispatch.py"
USAGE = REPO / "scripts" / "usage.py"
LOCAL_REASONING = Path.home() / ".codex" / "skills" / "local-reasoning" / "scripts" / "local-reasoning.mjs"
PROJECT = "agent-dispatch-model-pilot"

ROUTES = {
    "local-20b": {"kind": "local", "model": "gpt-oss:20b", "effort": "unknown", "tier": "alternate_pool"},
    "local-120b": {"kind": "local", "model": "gpt-oss:120b", "effort": "unknown", "tier": "alternate_pool"},
    "luna-low": {"kind": "remote", "model": "gpt-5.6-luna", "effort": "low", "tier": "cheap"},
    "terra-medium": {"kind": "remote", "model": "gpt-5.6-terra", "effort": "medium", "tier": "general"},
    "sol-high": {"kind": "remote", "model": "gpt-5.6-sol", "effort": "high", "tier": "frontier"},
}


def _run(command: list[str], *, stdin: str | None = None, timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=timeout,
    )
    if check and completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command[:4])}\n{completed.stderr[-1200:]}")
    return completed


def _json_command(command: list[str], *, stdin: str | None = None, timeout: int = 300) -> dict[str, Any]:
    completed = _run(command, stdin=stdin, timeout=timeout)
    return json.loads(completed.stdout)


def _prompt(task: dict[str, Any], contract: str) -> str:
    return "\n\n".join(
        [
            "You are a bounded advisory worker. Do not claim to run tools or edit files. Return only the requested JSON. Give conclusions and concise evidence, not hidden chain-of-thought. Set should_escalate when evidence or scope is inadequate.",
            contract,
            f"Task category: {task['category']}",
            f"Subproblem: {task['prompt']}",
            f"Bounded context:\n{task['context']}",
            f"Acceptance criteria:\n{task['acceptance']}",
        ]
    )


def _begin_task(run_id: str, route_name: str, route: dict[str, str], task: dict[str, Any], skill_version: str) -> str:
    task_id = f"pilot-{route_name}-{task['id']}"
    _json_command(
        [
            sys.executable,
            str(DISPATCH),
            "begin-task",
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--project",
            PROJECT,
            "--task-class",
            task["category"].replace(" ", "-"),
            "--domain",
            "synthetic-model-characterization",
            "--worker-model",
            route["model"],
            "--worker-reasoning",
            route["effort"],
            "--skill-version",
            skill_version,
            "--tier",
            route["tier"],
            "--delegation-depth",
            "1",
            "--parallel",
            "false",
            "--shadow",
            "true",
            "--parallel-group-size",
            "1",
            "--write-class",
            "read_only",
            "--consultation-mode",
            "consult",
            "--notes",
            f"Identical synthetic pilot task {task['id']} for route {route_name}.",
        ]
    )
    return task_id


def _bind_task(run_id: str, task_id: str, agent_id: str) -> None:
    _json_command(
        [sys.executable, str(DISPATCH), "bind-task", "--run-id", run_id, "--task-id", task_id, "--agent-id", agent_id]
    )


def _finish_task(
    run_id: str,
    task_id: str,
    agent_id: str | None,
    route: dict[str, str],
    evaluation: dict[str, Any],
    duration_ms: int,
    usage: dict[str, int | None],
    *,
    spawned: bool = True,
) -> None:
    passed = bool(evaluation["passed"])
    outcome = "pass" if passed else ("partial" if evaluation["score"] > 0 else "fail")
    command = [
        sys.executable,
        str(DISPATCH),
        "finish-task",
        "--run-id",
        run_id,
        "--task-id",
        task_id,
        "--actual-worker-model",
        route["model"],
        "--actual-worker-reasoning",
        route["effort"],
        "--spawned",
        str(spawned).lower(),
        "--review-pass",
        str(passed).lower(),
        "--tests-pass",
        str(passed).lower(),
        "--rework",
        "false",
        "--accepted",
        str(passed).lower(),
        "--frontier-use",
        "necessary" if route["model"] == "gpt-5.6-sol" else "unknown",
        "--frontier-calls",
        "1" if route["model"] == "gpt-5.6-sol" else "0",
        "--duration-s",
        f"{duration_ms / 1000:.3f}",
        "--usage-source",
        "measured" if usage.get("input_tokens") is not None else "unknown",
        "--outcome",
        outcome,
        "--notes",
        f"Deterministic benchmark score {evaluation['score']:.3f}: {evaluation['detail']}",
    ]
    if agent_id:
        command.extend(["--agent-id", agent_id])
    if usage.get("input_tokens") is not None:
        command.extend(["--input-tokens", str(usage["input_tokens"]), "--output-tokens", str(usage["output_tokens"] or 0)])
    _json_command(command)


def _record_usage(run_id: str, task_id: str, agent_id: str, route: dict[str, str], usage: dict[str, int | None]) -> None:
    command = [
        sys.executable,
        str(USAGE),
        "record-turn",
        "--turn-id",
        f"{task_id}-usage",
        "--run-id",
        run_id,
        "--project",
        PROJECT,
        "--front-door-model",
        "gpt-5.6-sol",
        "--front-door-effort",
        "high",
    ]
    if usage.get("input_tokens") is None:
        command.extend(
            [
                "--unknown-task-usage",
                f"{task_id},{agent_id},worker,{route['model']},{route['effort']},counters_unavailable",
            ]
        )
    else:
        command.extend(
            [
                "--task-usage",
                ",".join(
                    [
                        task_id,
                        agent_id,
                        "worker",
                        route["model"],
                        route["effort"],
                        str(usage["input_tokens"]),
                        str(usage.get("cached_input_tokens") or 0),
                        str(usage.get("output_tokens") or 0),
                        "measured",
                    ]
                ),
            ]
        )
    _json_command(command)


def _local_call(args: argparse.Namespace, route: dict[str, str], task: dict[str, Any]) -> dict[str, Any]:
    request = {
        "session_id": args.local_session_id,
        "session_started_at_utc": args.local_session_started_at,
        "category": f"pilot-{task['category'].replace(' ', '-')}",
        "prompt": task["prompt"],
        "context": task["context"],
        "acceptance": task["acceptance"],
        "model": route["model"],
        "online_model": "gpt-5.6-sol",
    }
    started = time.perf_counter()
    completed = _run(
        ["node", str(LOCAL_REASONING), "invoke", "--repo", str(REPO)],
        stdin=json.dumps(request, separators=(",", ":")),
        timeout=660,
        check=False,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"local reasoning returned invalid JSON: {exc}") from exc
    if not payload.get("invocation_id"):
        raise RuntimeError(payload.get("error") or f"local reasoning failed with {completed.returncode}")
    return {
        "agent_id": payload["invocation_id"],
        "response": payload.get("result", {}),
        "duration_ms": payload.get("duration_ms", elapsed_ms),
        "provider_duration_ms": payload.get("duration_ms"),
        "usage": {
            "input_tokens": payload.get("local_input_tokens"),
            "cached_input_tokens": 0,
            "output_tokens": payload.get("local_output_tokens"),
        },
        "metadata": {
            "schema_valid": payload.get("schema_valid"),
            "model_digest": payload.get("model_digest"),
            "ollama_version": payload.get("ollama_version"),
            "execution_profile": payload.get("execution_profile"),
            "context_window": payload.get("context_window"),
            "timeout_ms": payload.get("timeout_ms"),
            "scheduler_wait_ms": payload.get("scheduler_wait_ms"),
            "execution_error": payload.get("error"),
        },
    }


def _remote_call(route: dict[str, str], task: dict[str, Any], contract: str) -> dict[str, Any]:
    codex = shutil.which("codex.cmd") or shutil.which("codex")
    if not codex:
        raise RuntimeError("codex CLI not found")
    command = [
        codex,
        "--ask-for-approval",
        "never",
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--model",
        route["model"],
        "--config",
        f'model_reasoning_effort="{route["effort"]}"',
        "--sandbox",
        "read-only",
        "--output-schema",
        str(SCHEMA_PATH),
        "--cd",
        str(REPO),
        "-",
    ]
    started = time.perf_counter()
    completed = _run(command, stdin=_prompt(task, contract), timeout=360, check=False)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    events = []
    for line in completed.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    thread = next((event.get("thread_id") for event in events if event.get("type") == "thread.started"), None)
    message = None
    for event in events:
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            message = item.get("text")
    usage_event = next((event.get("usage", {}) for event in reversed(events) if event.get("type") == "turn.completed"), {})
    if completed.returncode or not thread or not message:
        error = (completed.stderr or completed.stdout).strip().splitlines()
        raise RuntimeError(error[-1] if error else f"codex exec failed with {completed.returncode}")
    response = json.loads(message)
    input_total = usage_event.get("input_tokens")
    cached = usage_event.get("cached_input_tokens") or 0
    input_non_cached = None if input_total is None else max(int(input_total) - int(cached), 0)
    return {
        "agent_id": f"codex-exec:{thread}",
        "response": response,
        "duration_ms": elapsed_ms,
        "provider_duration_ms": None,
        "usage": {
            "input_tokens": input_non_cached,
            "cached_input_tokens": int(cached),
            "output_tokens": usage_event.get("output_tokens"),
        },
        "metadata": {"thread_id": thread, "event_count": len(events), "exit_code": completed.returncode},
    }


def _record_local_outcome(args: argparse.Namespace, invocation_id: str, accepted: bool) -> None:
    request = {
        "session_id": args.local_session_id,
        "session_started_at_utc": args.local_session_started_at,
        "invocation_id": invocation_id,
        "outcome": "accepted" if accepted else "rejected",
        "validation": "Deterministic synthetic benchmark scorer.",
    }
    _json_command(
        ["node", str(LOCAL_REASONING), "outcome", "--repo", str(REPO)],
        stdin=json.dumps(request, separators=(",", ":")),
    )


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route", choices=sorted(ROUTES), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tasks-path", type=Path, default=DEFAULT_TASKS_PATH)
    parser.add_argument("--task", action="append")
    parser.add_argument("--local-session-id")
    parser.add_argument("--local-session-started-at")
    parser.add_argument("--skill-version", default="unknown")
    args = parser.parse_args()
    route = ROUTES[args.route]
    if route["kind"] == "local" and (not args.local_session_id or not args.local_session_started_at):
        parser.error("local routes require --local-session-id and --local-session-started-at")

    suite = json.loads(args.tasks_path.read_text(encoding="utf-8"))
    tasks = [task for task in suite["tasks"] if not args.task or task["id"] in set(args.task)]
    if args.output.exists():
        payload = json.loads(args.output.read_text(encoding="utf-8"))
        if payload.get("suite") != suite["suite"] or payload.get("route") != args.route:
            raise SystemExit("existing output belongs to a different suite or route")
    else:
        payload = {
            "schema": 1,
            "suite": suite["suite"],
            "route": args.route,
            "model": route["model"],
            "reasoning_effort": route["effort"],
            "results": [],
        }
        _write_atomic(args.output, payload)
    completed_ids = {item["task_id"] for item in payload["results"]}
    tasks = [task for task in tasks if task["id"] not in completed_ids]

    for task in tasks:
        task_id = _begin_task(args.run_id, args.route, route, task, args.skill_version)
        call: dict[str, Any] | None = None
        agent_id: str | None = None
        try:
            call = _local_call(args, route, task) if route["kind"] == "local" else _remote_call(route, task, suite["response_contract"])
            agent_id = call["agent_id"]
            _bind_task(args.run_id, task_id, agent_id)
            evaluation = score_response(task, call["response"])
            if route["kind"] == "local":
                _record_local_outcome(args, agent_id, evaluation["passed"])
            _finish_task(args.run_id, task_id, agent_id, route, evaluation, call["duration_ms"], call["usage"])
            _record_usage(args.run_id, task_id, agent_id, route, call["usage"])
            payload["results"].append(
                {
                    "task_id": task["id"],
                    "agent_id": agent_id,
                    "response": call["response"],
                    "evaluation": evaluation,
                    "duration_ms": call["duration_ms"],
                    "provider_duration_ms": call["provider_duration_ms"],
                    "usage": call["usage"],
                    "metadata": call["metadata"],
                }
            )
        except Exception as exc:
            evaluation = {"score": 0.0, "passed": False, "detail": f"execution failure: {exc}"}
            usage = call["usage"] if call else {"input_tokens": None, "cached_input_tokens": None, "output_tokens": None}
            if agent_id:
                _finish_task(args.run_id, task_id, agent_id, route, evaluation, call["duration_ms"] if call else 0, usage)
                _record_usage(args.run_id, task_id, agent_id, route, usage)
            else:
                _finish_task(args.run_id, task_id, None, route, evaluation, 0, usage, spawned=False)
            payload["results"].append(
                {
                    "task_id": task["id"],
                    "agent_id": agent_id,
                    "response": {},
                    "evaluation": evaluation,
                    "duration_ms": call["duration_ms"] if call else 0,
                    "provider_duration_ms": None,
                    "usage": usage,
                    "metadata": {},
                }
            )
        _write_atomic(args.output, payload)

    payload["summary"] = {
        "tasks": len(payload["results"]),
        "passed": sum(item["evaluation"]["passed"] for item in payload["results"]),
        "mean_score": round(sum(item["evaluation"]["score"] for item in payload["results"]) / max(len(payload["results"]), 1), 3),
        "wall_time_ms": sum(item["duration_ms"] for item in payload["results"]),
        "input_tokens": sum(item["usage"].get("input_tokens") or 0 for item in payload["results"]),
        "cached_input_tokens": sum(item["usage"].get("cached_input_tokens") or 0 for item in payload["results"]),
        "output_tokens": sum(item["usage"].get("output_tokens") or 0 for item in payload["results"]),
    }
    _write_atomic(args.output, payload)
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
