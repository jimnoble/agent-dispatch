---
name: agent-dispatch
description: Optimize Codex work with adaptive subagent orchestration. Use for nontrivial coding or repository tasks that can benefit from delegation, model/reasoning down-routing, episodic frontier consultation, safe parallel work, context isolation, independent verification, telemetry, or learning which front-door/subagent strategies perform best. Do not use for trivial single-step work where orchestration overhead would dominate.
---

# Agent Dispatch

Optimize for accepted results per scarce resource: preserve frontier-model usage, exploit cheaper/alternate pools when reliable, reduce wall-clock time with safe parallelism, and never learn away correctness.

## Start-of-task protocol

For a nontrivial task:

1. Identify deliverables, strongest available acceptance evidence, constraints, dependency edges, and write-conflict classes.
2. Decide whether orchestration will materially reduce scarce-model usage, parent-context consumption, or critical-path time. If not, work directly.
3. Classify candidate subtasks by task class, domain, reasoning need, write class, and delegation depth.
4. Consult `scripts/dispatch.py recommend` before materially delegated work. Its policy packet can include learned worker/reasoning preference, retry budget, escalation threshold, reviewer policy, preferred concurrency, exploration/shadow guidance, and remaining recursive-delegation depth.
5. Delegate bounded work to the least-expensive capable tier. Prefer alternate usage pools such as Codex Spark when suitable.
6. Use frontier reasoning episodically for planning, architecture, ambiguity, stubborn failures, conflicting evidence, or adjudication. Do not hide a permanent frontier executive behind a cheap front door.
7. Parallelize dependency-independent work, not merely the task list. Serialize shared logical writes unless isolation makes them safe.
8. Integrate results in dependency order, verify against the strongest available evidence, record delegated-task telemetry, and record a run summary at the end of a substantial run.

Read `references/routing.md` for capability tiers, frontier consultation, escalation, recursive delegation, and front-door behavior. Read `references/parallel-safety.md` before concurrent implementation. Read `references/contracts.md` for subagent packets/results. Read `references/learning.md` for telemetry, autonomous tuning, exploration, and reporting.

## Hard rules

- The front-door model remains user-selected. Never silently change the user's UI-selected front door.
- The parent/front-door agent owns the overall goal, decomposition, integration, and final acceptance.
- Delegate execution, never responsibility for correctness.
- A cheap front door must not become a weak gatekeeper. Escalate classification/planning early when uncertainty itself is consequential.
- Escalate instead of repeatedly retrying an underpowered model.
- Give subagents minimum sufficient context. Prefer repository pointers plus a compact packet over copied parent history.
- Require evidence-bearing result packets. A worker saying `done` is not acceptance evidence.
- Independent reviewers should see artifacts plus criteria, not the worker's entire rationale, when correlated error matters.
- Never weaken tests, acceptance criteria, safety rules, permissions, or verification requirements because a cheaper route looks faster.
- Learned state may tune preferences only inside this policy envelope.
- Never autonomously rewrite the installed skill's canonical source.
- Respect recursive-delegation depth/fan-out limits. Children may delegate bounded cheaper work, but must remain accountable for child output.

## Evidence hierarchy

Use the strongest available evidence:

1. deterministic automated tests/acceptance/benchmarks;
2. independent reviewer verdict against explicit criteria;
3. parent integration acceptance;
4. worker self-report only when nothing stronger exists.

A clean success requires acceptance with no contradictory stronger evidence and no later corrective rework attributable to the delegated result.

## Telemetry

For every materially delegated task, use `scripts/dispatch.py record`. Record measured usage only when exposed; otherwise mark it unknown rather than inventing values. Include run ID, front door, task class/domain, worker/model revision/reasoning, delegation depth, parallel/write metadata, consultation/frontier-use metadata, verification, retries/escalations, rework, acceptance, and skill version when known.

For each substantial user-facing run or milestone, also use `scripts/dispatch.py record-run` so front-door strategies are compared by whole-job outcomes rather than by raw child-task counts.

The learner periodically rebuilds derived state automatically and `recommend` always refreshes it before routing. `scripts/dispatch.py tune` remains available for explicit rebuilds.

## Bootstrap

Run:

```bash
python3 scripts/dispatch.py init
python3 scripts/bootstrap_agents.py
```

The bootstrap idempotently installs a small delimited Agent Dispatch trigger in global Codex `AGENTS.md`, preserving existing content.

## Reporting and diagnosis

Use:

- `scripts/dispatch.py recommend` — effective routing/policy packet;
- `scripts/dispatch.py explain` — same evidence-bearing policy view for diagnosis;
- `scripts/dispatch.py report` — front-door run comparison plus frontier-use accounting;
- `scripts/dispatch.py reset --learned-only` — discard derived learning while retaining raw telemetry.

Do not reason over raw JSONL unless deeper diagnosis requires it.
