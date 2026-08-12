# Telemetry and autonomous learning

## Principles

Telemetry is local-first, compact, append-only at the raw-event layer, and outcome-oriented. Do not log hidden reasoning transcripts. Record what was attempted, how it was routed, what evidence accepted or rejected it, and what resources were measurably consumed.

The learner adjusts routing and orchestration preferences without user intervention, but cannot rewrite the skill, weaken correctness gates, grant permissions, or change the user-selected front door.

## State

Default state directory: `~/.codex/agent-dispatch/`

- `telemetry.jsonl`: append-only raw events.
- `routing-state.json`: disposable derived route and orchestration policy.
- `config.json`: bounded learner parameters.

Two event types matter:

- `delegated_task`: one bounded child/subtree outcome;
- `run_summary`: one substantial front-door run/milestone outcome.

Run summaries prevent a highly-delegated job from counting as many independent front-door experiments.

## Global and project-local learning

Every delegated-task observation contributes to both project-specific and pooled global aggregates, with exact-domain and wildcard-domain views. Sufficient project-local evidence overrides broader priors; otherwise the learner backs off to project-wide, global-domain, then global evidence.

Model identity, optional model/runtime revision, reasoning level, and skill version are part of learned-route identity when supplied. Do not assume a materially changed model alias or skill version inherits confidence from an older implementation.

Recent evidence is exponentially weighted more strongly than stale evidence.

## Evidence-weighted success

Evidence strength is ordered:

1. deterministic tests/acceptance;
2. independent review;
3. parent acceptance;
4. worker self-report.

Contradictory stronger evidence dominates weaker positive evidence. A parent acceptance with failing deterministic tests is a failure for learning purposes. Clean success also requires no attributable rework or parallel-collision failure.

## Objective

Optimize accepted result per scarce resource. Reward clean verified acceptance. Penalize rework, failure, avoidable escalation, frontier scarcity, and latency. Missing token metrics remain unknown unless explicitly marked derived.

Frontier events can be labeled `necessary`, `rescue`, `avoidable`, or `unknown`. Reports surface this distribution so expensive reasoning is not treated as uniformly valuable.

## Learned policy dimensions

With enough evidence, the derived policy may tune:

- worker/model and reasoning preference;
- retry budget;
- escalation-after-failure threshold;
- reviewer policy (`optional`, `recommended`, `required`);
- preferred safe concurrency;
- exploration/shadow guidance.

Hard write-safety rules and correctness gates remain outside learner authority.

## Exploration and shadow evaluation

Default exploration budget is 5% and applies only to low-risk bounded work. Expensive/frontier classifications should prefer shadow evaluation: a cheaper route may attempt the problem without controlling the real outcome, then be compared against accepted evidence.

Exploration is a recommendation, not permission to violate task safety or wastefully double-run routine work. The orchestrator should choose under-tested cheaper alternatives only when the information value plausibly exceeds the extra cost.

## Autonomous refresh

Recording delegated tasks periodically rebuilds learned state. Every `recommend` refreshes derived state before returning a decision, so the agent does not need a user-driven tuning step.

## Reporting

Prefer run-level front-door comparisons when run summaries exist. Report clean-success rate, rework, frontier calls/rescues, elapsed time, and measured usage where available. Fall back to delegated-task grouping only when no run summaries exist.

Explicitly distinguish measured, derived, and unknown resource fields.
