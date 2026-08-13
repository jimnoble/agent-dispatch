#!/usr/bin/env python3
"""Idempotently install the small Agent Dispatch trigger in global AGENTS.md."""
from __future__ import annotations
import os
import re
from pathlib import Path

START = "<!-- agent-dispatch:start -->"
END = "<!-- agent-dispatch:end -->"
BLOCK = f"""{START}
## Agent Dispatch

For nontrivial work, consider whether subagent delegation, cheaper model/reasoning tiers, alternate usage pools, or safe parallelism can reduce scarce-model usage or wall-clock time without reducing correctness. When materially useful, load and follow the `agent-dispatch` skill. Keep the parent responsible for integration and acceptance; escalate ambiguity or repeated failure instead of thrashing.

For substantive delegated work, never launch or reactivate a raw subagent until Agent Dispatch has emitted a pre-spawn receipt containing run and task IDs; if registration fails, stop dispatch. Bind the returned agent ID, append the terminal outcome and measured/estimated/unknown usage, then require a passing telemetry audit and run summary before reporting completion. The only emergency exception is urgent safety or containment work when telemetry itself is unavailable: disclose it, backfill at the first safe opportunity, and classify the backfill as audit recovery rather than compliant registration.
{END}"""


def target() -> Path:
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return home / "AGENTS.md"


def bump_global_version(text: str) -> str:
    match = re.search(r"(?m)^(# Global AGENTS\.md V)(\d+)[ \t]*$", text)
    if not match:
        return text
    old_version = int(match.group(2))
    new_version = old_version + 1
    text = text[:match.start()] + f"{match.group(1)}{new_version}" + text[match.end():]
    commentary = re.compile(r"(Begin every request's commentary with exactly `COMPLYING WITH GLOBAL AGENTS\.MD\nV)" + str(old_version) + r"(`)")
    return commentary.sub(rf"\g<1>{new_version}\g<2>", text)


def main() -> int:
    path = target()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if START in existing and END in existing:
        before = existing.split(START, 1)[0].rstrip()
        after = existing.split(END, 1)[1].lstrip()
        pieces = [p for p in (before, BLOCK, after) if p]
        new = "\n\n".join(pieces).rstrip() + "\n"
    elif START in existing or END in existing:
        print(f"Refusing to modify {path}: found an incomplete Agent Dispatch marker block.")
        print("Canonical block:\n")
        print(BLOCK)
        return 2
    else:
        new = (existing.rstrip() + "\n\n" if existing.strip() else "") + BLOCK + "\n"
    if new != existing:
        new = bump_global_version(new)
        path.write_text(new, encoding="utf-8")
        print(f"Installed Agent Dispatch trigger in {path}")
    else:
        print(f"Agent Dispatch trigger already current in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
