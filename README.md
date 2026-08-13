> Install `github.com/jimnoble/agent-dispatch`.

# Agent Dispatch

**Adaptive subagent orchestration for Codex. Spend expensive reasoning where it matters, push routine work down, parallelize what is safe, and learn which routing choices actually work.**

Codex subagents are powerful, but deciding **what to delegate, to which model, at what reasoning level, when to run work in parallel, and when to escalate** is itself an orchestration problem. Agent Dispatch gives the front-door coding agent a reusable operating policy for doing that deliberately instead of treating every task as one monolithic model invocation.

The goal is simple: **approach frontier-model quality while reducing scarce-model usage and wall-clock time.**

There is no post-install command. On first use, Agent Dispatch initializes its local state and repairs/installs its small global `AGENTS.md` trigger automatically. The bundled bootstrap helper exists only as an internal/self-repair primitive; users do not need to invoke it.

## What it does

Agent Dispatch keeps your normal Codex model picker as the front door. Underneath it, the skill can:

- decompose nontrivial work into bounded subtasks;
- route each subtask to the least-expensive model/reasoning tier likely to succeed;
- reserve frontier reasoning for planning, architecture, ambiguity, hard debugging, adjudication, and other high-leverage decisions;
- preferentially exploit alternate usage pools such as Codex Spark when they fit the work;
- run dependency-independent read-only or non-repository work concurrently;
- serialize repository mutations by default unless the repository explicitly provides a tested isolation mechanism or the user opts into one;
- **never create Git worktrees by default**; worktrees are explicit opt-in and must follow managed lifecycle/recovery rules;
- give workers narrow task packets instead of cloning giant parent contexts;
- emit an append-only pre-spawn receipt before every substantive worker launch or reactivation, and stop dispatch if registration fails;
- escalate early when a cheaper worker is out of its depth instead of paying for repeated failed attempts;
- independently review consequential delegated work and require evidence rather than accepting a worker's `done`;
- explore model choice and reasoning effort independently, including counterintuitive combinations when supported;
- bind receipts to returned agent IDs, append terminal outcomes, and record measured, estimated, or explicitly unknown usage without inventing zeroes;
- fail closed before completion when lifecycle, runtime-agent, usage, or run-summary coverage is incomplete;
- report per-agent/model/effort usage and estimate savings against an all-frontier baseline;
- autonomously tune future routing preferences from telemetry without weakening correctness requirements;
- promote high-confidence burn-in discoveries into inspectable repository defaults;
- compare how different user-selected front-door models perform over time.

## Why

A frontier model can often solve the entire job itself, but that is not always the best use of frontier tokens. Many coding tasks contain a mixture of expensive reasoning and cheap execution: architecture beside repository inventory, difficult debugging beside mechanical edits, planning beside test execution.

Agent Dispatch separates those concerns. A stronger model can be consulted episodically for the decisions that justify it while cheaper workers handle bounded implementation, investigation, review, search, tests, or mechanical work. Dependency-aware scheduling still gives us substantial safe parallelism without requiring extra repository copies.

The parent agent still owns integration and final correctness. Delegation transfers execution, **not responsibility**.

## It learns from actual outcomes

Static routing rules are only priors. Agent Dispatch maintains append-only local telemetry and derives a learned routing profile from observed results.

It can learn, for example, that a cheap model reliably handles repository inventory, that a general model is the sweet spot for a particular project's Rust implementation, or that a class of Blender failures nearly always escalates and should skip the cheap attempt next time.

Learning is bounded. It may tune model/reasoning preferences, retry and escalation behavior, reviewer selection, exploration, and parallelism preferences. It may **not** learn away tests, acceptance criteria, safety constraints, permissions, required verification, or worktree opt-in requirements.

Your front-door model remains your choice in the normal Codex UI. That makes front-door selection an experiment too: accumulated telemetry can later tell you whether a cheaper front door plus selective frontier delegation actually matched the quality of starting every task on the frontier model.

## Context is a resource too

Delegation is also context compression. Instead of making the parent consume an entire investigation, a worker receives a bounded packet and returns a concise result with artifacts, evidence, uncertainties, and escalation conditions. The parent pays for the conclusion rather than every exploratory step.

## Local-first and inspectable

Runtime state lives by default at:

`~/.codex/agent-dispatch/`

Raw events are append-only JSONL; learned routing state is derived and inspectable. No telemetry is uploaded by this skill. Missing token/usage data stays unknown rather than being invented.

Managed delegation follows a receipt lifecycle: `begin-run` → `begin-task` before spawning → `bind-task` after the host returns an agent ID → `finish-task` after verification → task-aware usage → `audit-run` → `record-run`. Each reactivation gets a new task ID. The final summary automatically repeats the audit and refuses incomplete managed runs.

The local scripts cannot atomically invoke Codex's host-level spawn tool. Enforcement therefore combines mandatory receipt-before-spawn instructions, an append-only lifecycle, runtime-agent reconciliation when IDs are available, and a fail-closed run summary. Backfilled telemetry is audit recovery, not compliant registration.

Useful operations include routing recommendations, tuning, front-door performance reports, routing explanations, usage/savings reports, and resetting learned state while preserving raw telemetry.

## Zero-step initialization

Installation is the only user action. On first activation the skill must, without prompting for routine setup:

1. ensure local Agent Dispatch state exists;
2. ensure the delimited Agent Dispatch trigger in global Codex `AGENTS.md` exists and is current;
3. preserve all unrelated existing `AGENTS.md` content;
4. initialize usage/rate-card state as needed;
5. continue with the user's original task.

If initialization encounters a genuine conflict that cannot be repaired safely (for example, a malformed half-present managed marker), the agent should report that conflict rather than overwrite unrelated user configuration.

Restart Codex only if the host itself requires a restart to discover a newly installed skill.

## Status

Agent Dispatch is intentionally pre-1.0 while real-workload burn-in establishes which routing policies actually dominate.

## License

MIT. See `LICENSE`.
