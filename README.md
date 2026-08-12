> Install `github.com/jimnoble/agent-dispatch` and run its bootstrap step.

# Agent Dispatch

**Adaptive subagent orchestration for Codex. Spend expensive reasoning where it matters, push routine work down, parallelize what is safe, and learn which routing choices actually work.**

Codex subagents are powerful, but deciding **what to delegate, to which model, at what reasoning level, when to run work in parallel, and when to escalate** is itself an orchestration problem. Agent Dispatch gives the front-door coding agent a reusable operating policy for doing that deliberately instead of treating every task as one monolithic model invocation.

The goal is simple: **approach frontier-model quality while reducing scarce-model usage and wall-clock time.**

## What it does

Agent Dispatch keeps your normal Codex model picker as the front door. Underneath it, the skill can:

- decompose nontrivial work into bounded subtasks;
- route each subtask to the least-expensive model/reasoning tier likely to succeed;
- reserve frontier reasoning for planning, architecture, ambiguity, hard debugging, adjudication, and other high-leverage decisions;
- preferentially exploit alternate usage pools such as Codex Spark when they fit the work;
- run dependency-independent work concurrently while isolating conflicting writes;
- give workers narrow task packets instead of cloning giant parent contexts;
- escalate early when a cheaper worker is out of its depth instead of paying for repeated failed attempts;
- independently review consequential delegated work and require evidence rather than accepting a worker's `done`;
- record local telemetry about routing, retries, escalation, rework, acceptance, duration, and measured usage when available;
- autonomously tune future routing preferences from that telemetry without weakening correctness requirements;
- compare how different user-selected front-door models perform over time.

## Why

A frontier model can often solve the entire job itself, but that is not always the best use of frontier tokens. Many coding tasks contain a mixture of expensive reasoning and cheap execution: architecture beside repository inventory, difficult debugging beside mechanical edits, planning beside test execution.

Agent Dispatch separates those concerns. A stronger model can be consulted episodically for the decisions that justify it while cheaper workers handle bounded implementation, investigation, review, search, tests, or mechanical work. Independent branches/worktrees and dependency-aware scheduling allow safe work to happen in parallel.

The parent agent still owns integration and final correctness. Delegation transfers execution, **not responsibility**.

## It learns from actual outcomes

Static routing rules are only priors. Agent Dispatch maintains append-only local telemetry and derives a learned routing profile from observed results.

It can learn, for example, that a cheap model reliably handles repository inventory, that a general model is the sweet spot for a particular project's Rust implementation, or that a class of Blender failures nearly always escalates and should skip the cheap attempt next time.

Learning is bounded. It may tune model/reasoning preferences, retry and escalation behavior, reviewer selection, exploration, and parallelism preferences. It may **not** learn away tests, acceptance criteria, safety constraints, permissions, or required verification.

Your front-door model remains your choice in the normal Codex UI. That makes front-door selection an experiment too: accumulated telemetry can later tell you whether, say, a cheaper front door plus selective frontier delegation actually matched the quality of starting every task on the frontier model.

## Context is a resource too

Delegation is also context compression. Instead of making the parent consume an entire investigation, a worker receives a bounded packet and returns a concise result with artifacts, evidence, uncertainties, and escalation conditions. The parent pays for the conclusion rather than every exploratory step.

## Local-first and inspectable

Runtime state lives by default at:

`~/.codex/agent-dispatch/`

Raw events are append-only JSONL; learned routing state is derived and inspectable. No telemetry is uploaded by this skill. Missing token/usage data stays unknown rather than being invented.

Useful operations include routing recommendations, tuning, front-door performance reports, routing explanations, and resetting learned state while preserving raw telemetry.

## Bootstrap

After installation, the bootstrap initializes local state and idempotently adds a small Agent Dispatch trigger block to your global Codex `AGENTS.md`, preserving existing content. That gives Codex a persistent reminder to consider orchestration for substantial work while keeping the detailed policy in the skill itself.

Restart Codex if the newly installed skill is not discovered immediately.

## Versioning

Releases use semantic Git tags (`vMAJOR.MINOR.PATCH`). For reproducible installs, ask your coding agent to install a specific tag instead of the current default branch.

## Status

Agent Dispatch is intentionally starting pre-1.0. The core policy is conservative; the adaptive routing behavior is expected to improve with real-world telemetry and iteration.

## License

MIT. See `LICENSE`.
