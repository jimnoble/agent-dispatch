# Telemetry and autonomous learning

Telemetry is local-first, append-only at the raw-event layer, outcome-oriented, and must not contain hidden reasoning transcripts. The learner may tune routing/orchestration without user intervention, but cannot rewrite the skill, weaken correctness gates, grant permissions, or change the user-selected front door.

## State and evidence

Global state lives under `~/.codex/agent-dispatch/`: `telemetry.jsonl` (raw events), `routing-state.json` (derived policy), `config.json` (bounded learner parameters), and `cells.json` (runtime-supported model×effort cells).

`run_started` identifies a managed user-facing run. `delegated_task_started` is the immutable pre-spawn receipt, `delegated_task_bound` attaches the host-returned agent ID, and `delegated_task` records the terminal child/subtree outcome. Only terminal `delegated_task` events feed the learner. `turn_usage` links task-aware usage by `run_id` and `task_id`; `run_summary` records whole front-door runs so highly delegated jobs do not count as many independent front-door experiments.

Every substantive spawn or reactivation gets a distinct task receipt before the host call. Terminal outcomes and usage append new events rather than mutating that receipt. A lifecycle audit requires exactly one terminal outcome and one task-aware measured, estimated, or explicitly unknown usage component for each spawned receipt. A receipt closed as not spawned requires no worker usage. Runtime agent IDs and the expected task count should be supplied to the audit whenever the host exposes them, because the ledger alone cannot detect a spawn that bypassed registration entirely.

Every delegated observation contributes to project-specific and pooled global aggregates. Project-local evidence overrides broader priors once strong enough. Model identity, optional model/runtime revision, reasoning effort, and skill version distinguish learned routes. Recent evidence is weighted more heavily than stale evidence.

Evidence precedence is deterministic tests/acceptance, independent review, parent acceptance, then worker self-report. Contradictory stronger evidence wins. Clean success also requires no attributable rework or parallel collision.

## Model × reasoning surface

Model capability and reasoning effort are independent experimental dimensions. Do not collapse them into one tier ladder. A cheap model at high/xhigh effort or a frontier model at low effort may be Pareto-superior for a particular task class.

Only explore cells the current runtime actually supports. Register supported cells with `scripts/surface.py register-cell`; do not infer availability from names. When observable, telemetry should distinguish requested model/effort from effective model/effort so silently substituted runtime routes do not contaminate learning.

Controlled exploration should favor under-sampled neighboring effort levels on the same model, then under-sampled cross-model cells. Frontier/consequential tasks should generally use shadow evaluation. Repeated improvement when effort increases on the same model is evidence of effort insufficiency; repeated failure across effort levels followed by success on a stronger model is evidence of capability insufficiency.

## Objective and learned policy

Optimize accepted result per scarce resource. Reward clean verified acceptance; penalize rework, failure, avoidable escalation, frontier scarcity, excess reasoning effort, and latency. Missing token metrics remain unknown unless explicitly marked derived.

The learner may tune worker/model+effort preference, retry budget, escalation threshold, reviewer policy, safe concurrency, and exploration/shadow guidance. Frontier use may be labeled `necessary`, `rescue`, `avoidable`, or `unknown` for reporting.

## Burn-in promotion to repository defaults

Transient learning should become a sensible project default when evidence is mature. `scripts/surface.py promote` considers only project-local routes and requires minimum samples, high clean-success, low rework, and a meaningful utility lead over alternatives. It writes `.agent-dispatch/defaults.json` inside the target repository.

The generated defaults file is deliberately separate from `AGENTS.md` and project source: it is inspectable, reviewable, easy to commit, and safe to replace. A promoted default is a strong prior, not a lock. New local evidence can supersede it, and changed model/runtime revisions should earn confidence again.

This creates the learning chain: shipped priors → global learned evidence → project-local evidence → promoted repository defaults → continued project-local adaptation.

## Exploration and reporting

Default exploration budget is 5% on low-risk bounded work. Do not double-run routine work merely to collect data. The information value should plausibly exceed the exploration cost.

Prefer run-level front-door reports when run summaries exist. Report clean success, rework, frontier calls/rescues, elapsed time, and measured usage where available, explicitly distinguishing measured, derived, and unknown values.
