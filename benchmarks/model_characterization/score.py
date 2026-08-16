#!/usr/bin/env python3
"""Deterministically score model-characterization responses."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _recommendation_json(response: dict[str, Any]) -> Any:
    return json.loads(response.get("recommendation", ""))


def _score_chunked(source: str) -> tuple[float, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return 0.0, f"invalid Python: {exc.msg}"
    if any(isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)) for node in ast.walk(tree)):
        return 0.0, "disallowed syntax"
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1 or functions[0].name != "chunked":
        return 0.0, "expected one chunked function"
    harness = source + "\n" + """
assert chunked([], 3) == []
assert chunked([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
assert chunked('abcde', 3) == ['abc', 'de']
for invalid in (0, -1):
    try:
        chunked([1], invalid)
    except ValueError:
        pass
    else:
        raise AssertionError('missing ValueError')
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", harness],
        capture_output=True,
        text=True,
        timeout=3,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        return 0.0, detail[-1] if detail else "behavior tests failed"
    return 1.0, "behavior tests passed"


def _score_coalesce(source: str) -> tuple[float, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return 0.0, f"invalid Python: {exc.msg}"
    if any(isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)) for node in ast.walk(tree)):
        return 0.0, "disallowed syntax"
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1 or functions[0].name != "coalesce":
        return 0.0, "expected one coalesce function"
    harness = source + "\n" + """
assert coalesce([]) == []
assert coalesce([(5, 8), (1, 3), (3, 5), (10, 12), (11, 15)]) == [(1, 8), (10, 15)]
assert coalesce(((4, 7), (1, 2), (2, 4))) == [(1, 7)]
source = [(3, 4), (1, 2)]
assert coalesce(source) == [(1, 2), (3, 4)]
assert source == [(3, 4), (1, 2)]
for invalid in ([(1, 1)], [(2, 1)], [(1, '2')], [(True, 2)], [(1, 2, 3)]):
    try:
        coalesce(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError('missing ValueError')
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", harness],
        capture_output=True,
        text=True,
        timeout=3,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        return 0.0, detail[-1] if detail else "behavior tests failed"
    return 1.0, "behavior tests passed"


def score_response(task: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    validator = task["validator"]
    kind = validator["type"]
    schema_fields = {"analysis_summary", "recommendation", "evidence", "uncertainties", "should_escalate"}
    if not isinstance(response, dict) or not schema_fields.issubset(response):
        return {"score": 0.0, "passed": False, "detail": "response schema invalid"}

    try:
        if kind == "json_equal":
            ok = _recommendation_json(response) == validator["expected"] and response["should_escalate"] is False
            detail = "exact structured answer" if ok else "structured answer mismatch"
            score = 1.0 if ok else 0.0
        elif kind == "normalized_text":
            actual = re.sub(r"[;\s]+", "", response["recommendation"]).lower()
            expected = re.sub(r"[;\s]+", "", validator["expected"]).lower()
            ok = actual == expected and response["should_escalate"] is False
            detail = "exact normalized answer" if ok else "normalized answer mismatch"
            score = 1.0 if ok else 0.0
        elif kind == "python_chunked":
            score, detail = _score_chunked(response["recommendation"])
            if response["should_escalate"] is not False:
                score *= 0.5
                detail += "; unnecessary escalation"
            ok = score >= 0.8
        elif kind == "python_coalesce":
            score, detail = _score_coalesce(response["recommendation"])
            if response["should_escalate"] is not False:
                score *= 0.5
                detail += "; unnecessary escalation"
            ok = score >= 0.8
        elif kind == "calibrated_escalation":
            joined = " ".join(response.get("uncertainties", [])).lower()
            hits = sum(any(term in joined for term in alternatives) for alternatives in validator["required_concepts"])
            no_period = not re.search(r"\b\d+\s*(day|month|year)s?\b", response.get("recommendation", "").lower())
            score = (0.4 if response["should_escalate"] is True else 0.0) + 0.15 * hits + (0.15 if no_period else 0.0)
            score = min(score, 1.0)
            ok = score >= 0.8
            detail = f"escalation={response['should_escalate']}; concept_hits={hits}; invented_period={not no_period}"
        else:
            raise ValueError(f"unknown validator: {kind}")
    except (json.JSONDecodeError, TypeError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        score, ok, detail = 0.0, False, f"scoring error: {exc}"
    return {"score": round(score, 3), "passed": ok, "detail": detail}


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: score.py TASKS_JSON RESPONSES_JSON")
    tasks = {task["id"]: task for task in json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["tasks"]}
    payload = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    scored = []
    for item in payload["results"]:
        result = score_response(tasks[item["task_id"]], item["response"])
        scored.append({**item, "evaluation": result})
    summary = {
        "tasks": len(scored),
        "passed": sum(item["evaluation"]["passed"] for item in scored),
        "mean_score": round(sum(item["evaluation"]["score"] for item in scored) / max(len(scored), 1), 3),
    }
    print(json.dumps({**payload, "results": scored, "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
