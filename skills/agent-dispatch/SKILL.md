---
name: agent-dispatch
description: Optimize Codex work with adaptive subagent orchestration. Use for nontrivial coding or repository tasks that can benefit from delegation, model/reasoning down-routing, Sol escalation for planning or hard reasoning, safe parallel work, context isolation, independent verification, telemetry, or learning which front-door/subagent strategies perform best. Do not use for trivial single-step work where orchestration overhead would dominate.
---

# Agent Dispatch

Optimize for accepted results per scarce resource: preserve frontier-model usage, exploit cheaper/alternate pools when reliable, reduce wall-clock time with safe parallelism, and never learn away correctness.

## Start-of-task protocol

For a nontrivial task:

1. Identify deliverables, acceptance evidence, constraints, and dependency edges.
2. Decide whether orchestration will materially reduce scarce-model usage or critical-path time. If not, work directly.
3. Classify candidate subtasks by reasoning need and write-conflict risk.
4. Consult learned routing with `scripts/dispatch.py recommend` when practical. Treat it as a preference, not permission to violate this skill.
5. Delegate bounded work to the least-expensive capable tier. Prefer alternate usage pools such as Codex Spark where suitable.
6. Parallelize dependency-independent tasks. Serialize overlapping logical writes unless isolation makes them safe.
7. Integrate results in dependency order, verify against the strongest available evidence, record outcomes, and update learned state.

Read `references/routing.md` when choosing tiers, escalation behavior, or Sol consultation mode. Read `references/parallel-safety.md` before concurrent implementation. Read `references/contracts.md` when constructing subagent prompts/results. Read `references/learning.md` for telemetry, tuning, exploration, and reporting.

## Hard rules

- The front-door model remains user-selected. Never silently change the user's UI-selected front door.
- The parent/front-door agent owns the overall goal, decomposition, integration, and final acceptance.
- Delegate responsibility for execution, never responsibility for correctness.
- Use frontier reasoning episodically: planning, architecture, ambiguity, stubborn failures, conflicting evidence, or consequential adjudication. Do not summon a frontier agent merely to repeat routine implementation.
- Escalate instead of repeatedly retrying an underpowered model.
- Give subagents the minimum context needed. Prefer pointers to repo files plus a compact task packet over copying parent history.
- Require evidence-bearing result packets. A subagent saying "done" is not acceptance evidence.
- Never weaken tests, acceptance criteria, safety rules, permissions, or verification frequency solely because a cheaper route looks faster.
- Learned state may tune preferences only inside the policy envelope defined by this skill.
- Never modify this installed skill's canonical source as part of autonomous learning.

## Success evidence order

Prefer the strongest evidence available:

1. deterministic automated acceptance/tests/benchmarks;
2. independent reviewer verdict tied to explicit criteria;
3. parent integration acceptance;
4. worker self-report only when nothing stronger is possible.

A clean success means accepted with no later corrective rework attributable to the delegated result.

## Bootstrap

Run:

```bash
python3 scripts/dispatch.py init
python3 scripts/bootstrap_agents.py
```

The bootstrap script idempotently adds a small, delimited Agent Dispatch trigger block to the user's global Codex `AGENTS.md` while preserving existing content. If it cannot safely determine or write the file, print the block and ask the user/parent agent to place it manually.

## Finish-of-task protocol

For every materially delegated task, record telemetry using `scripts/dispatch.py record`. Record measured values when available; otherwise use `null`/omit them rather than inventing usage. Then run `scripts/dispatch.py tune`.

For periodic summaries or user questions, use `scripts/dispatch.py report` and `scripts/dispatch.py explain` rather than reasoning over raw JSONL unless deeper diagnosis is needed.
