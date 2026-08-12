# Telemetry and autonomous learning

## Principles

Telemetry is local-first, compact, and outcome-oriented. Do not log hidden reasoning transcripts. Record model/tier, task classification, timing, measured usage when exposed, retries, escalation, parallelism, verification, rework, and final acceptance.

The learner adjusts routing preferences without user intervention, but cannot rewrite the skill, weaken correctness gates, grant permissions, or change the user-selected front door.

## State

Default state directory: `~/.codex/agent-dispatch/`

- `telemetry.jsonl`: append-only raw events.
- `routing-state.json`: derived scores/preferences; disposable and rebuildable.
- `config.json`: tunable bounded learner parameters.

Project identity and domain/task class allow both global and project-specific learning. Project-specific evidence may override global priors once it is sufficiently strong.

## Objective

Optimize accepted result per scarce resource. Reward clean verified acceptance; penalize rework, failed attempts, unnecessary escalation, scarce/frontier usage, and wall-clock latency. Missing token metrics remain unknown rather than estimated unless explicitly marked derived.

## Cold start

Use shipped priors. Do not switch a route from defaults until enough evidence exists. Weight recent evidence more heavily than stale evidence. Model identity/reasoning are part of the route key; do not assume a new model version inherits old performance unchanged.

## Exploration and shadow evaluation

Permit small exploration only on low-risk bounded work. Default exploration budget is 5%. Prefer shadow evaluation for expensive/frontier classifications when feasible: let a cheaper agent attempt the task without controlling the real outcome, then compare against accepted evidence.

Do not double-run routine work merely to collect data. Exploration itself has a cost and is logged.

## Reporting

Reports should compare front-door strategies and child routes using clean-success rate, review/test pass rate, rework, escalation/rescue, elapsed time, and measured usage where available. Explicitly distinguish measured, derived, and unknown fields.
