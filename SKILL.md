---
name: agent-dispatch
description: Optimize Codex work with adaptive subagent orchestration, fail-closed dispatch receipts, and usage accounting. Use for nontrivial coding or repository tasks that benefit from delegation, independent model/reasoning exploration, episodic frontier consultation, safe parallel work, context isolation, verification, telemetry, usage accounting, or learned repository defaults. Do not use for trivial single-step work where orchestration overhead dominates.
---

# Agent Dispatch

Optimize for accepted results per scarce resource without learning away correctness.

## First-use and start-of-turn invariant

The public installation contract is only: `Install github.com/jimnoble/agent-dispatch`.

Do not require the user to run a bootstrap or initialization command after installation. On first activation, and opportunistically on later activations, silently perform routine initialization before dispatching work:

1. ensure Agent Dispatch local state exists;
2. ensure the managed Agent Dispatch trigger exists in global Codex `AGENTS.md`;
3. initialize usage/rate-card state when needed;
4. run `scripts/resources.py reconcile` before creating any Agent Dispatch-managed temporary resource;
5. preserve unrelated user configuration; and
6. continue the user's original task without treating setup/reconciliation as a separate user-visible step unless intervention is actually required.

Reconciliation is deliberately scoped to the Agent Dispatch managed-resource registry. Never scan arbitrary user directories looking for garbage. If a malformed managed marker, quarantined resource with potentially valuable work, or another genuine conflict makes automatic repair unsafe, report it rather than deleting or overwriting it.

## Start-of-task protocol

1. Identify deliverables, strongest acceptance evidence, constraints, dependencies, and write-conflict classes.
2. Decide whether orchestration can materially reduce scarce-model usage, parent context, or critical-path time.
3. Classify subtasks by task class, domain, reasoning need, write class, and delegation depth.
4. Consult `scripts/dispatch.py recommend` for learned routing/execution policy and inspect `.agent-dispatch/defaults.json` when present in the repository.
5. Before the first substantive dispatch, create the run receipt with `scripts/dispatch.py begin-run`; retain its `run_id` for the entire user-facing run or milestone.
6. Treat **model choice and reasoning effort as independent variables**. Capability tiers are priors/safety envelopes, not a one-dimensional ladder.
7. Delegate bounded work to the least-expensive capable route; use frontier reasoning episodically for planning, architecture, ambiguity, stubborn failures, conflicting evidence, or adjudication.
8. Parallelize the dependency graph, not merely the task list. Read-only/non-repository work may run concurrently; repository mutations serialize by default unless the repository explicitly declares a tested isolation mechanism or the user explicitly opts into one.
9. Follow the fail-closed lifecycle below for every substantive spawn or reactivation.
10. Before reporting completion, require a passing `audit-run`, append `record-run`, and surface the compact usage footer.

Read `references/routing.md`, `references/parallel-safety.md`, `references/contracts.md`, and `references/learning.md` when their detail is needed.

## Fail-closed delegated-task lifecycle

Treat each spawn or reactivation as a distinct task attempt, even when the same agent ID is reused.

1. Run `begin-task` immediately before the host spawn/reactivation call. It emits an append-only pre-spawn receipt and returns the task ID. If registration fails, **do not dispatch**.
2. After a successful spawn, run `bind-task` with the returned agent ID. For reactivation, pass the already-known agent ID to `begin-task` and do not create a duplicate binding.
3. After verification, run `finish-task` once. It appends the terminal event with the effective model/revision/reasoning, outcome, verification, retries/escalations, rework, and acceptance. Never mutate or replace the start receipt.
4. After the worker completes, first use `usage.py record-turn --capture-task-usage <task-id>` to recover exact per-request counters from the bound child rollout. It attributes by lifecycle receipt, agent path, parent thread, and activation boundaries, and fails closed if the match is ambiguous or incomplete. Fall back to `--task-usage` when the host directly exposes counters, or `--unknown-task-usage` only when neither source is available. Unknown means null, never zero. Record front-door usage with `--usage` or `--unknown-usage` in the same run.
5. Reconcile tool-visible agents with `audit-run --expected-agent-id ... --expected-task-count ...`. Then run `record-run`, which automatically repeats the lifecycle audit and refuses to summarize an incomplete managed run.

The scripts cannot transactionally wrap a host-level spawn tool. The receipt-before-spawn ordering and fail-closed summary are therefore the enforceable boundary. A telemetry audit can detect unclosed receipts and runtime agents supplied to it; it cannot discover a raw spawn omitted from both telemetry and runtime expectations.

Do not use raw spawning for substantive Agent Dispatch work without a receipt. The only emergency exception is urgent safety or containment work when telemetry itself is unavailable. Disclose the exception, backfill at the first safe opportunity, and label the backfill audit recovery rather than compliant registration. Do not report ordinary work complete under this exception.

## Managed temporary resources and crash recovery

Agent turns may terminate unexpectedly. Therefore end-of-turn cleanup is only best effort; **start-of-subsequent-turn reconciliation is the reliability mechanism**.

For any temporary resource Agent Dispatch itself creates (scratch directory, cache workspace, temporary workspace, explicitly opted-in Git worktree):

- register it with `scripts/resources.py register` **before creation**;
- keep it inside the managed namespace under `~/.codex/agent-dispatch/workspaces/<repo-id>/<run-id>/`; never create arbitrary sibling directories next to the user's repository;
- mark it active/heartbeat leases while genuinely in use when long-lived;
- mark cleanup pending when work is complete and clean immediately when safe;
- on every later activation, reconcile expired resources before creating new ones;
- never blindly delete a stale Git worktree; inspect for uncommitted work and use Git-aware `worktree remove`/`prune` when safe;
- quarantine rather than delete anything with uncommitted/potentially valuable work, an unmanaged path, missing lifecycle metadata, or failed Git-aware cleanup.

A concurrent live resource must not be reclaimed merely because another turn ended. Lease expiry plus registry state gates reclamation. Cleanup/recovery must never depend on the creating turn reaching its final phase.

## Model × reasoning exploration

Do not assume only diagonal combinations such as cheap/light and frontier/high are useful. Routes such as a cheap model with high reasoning or a frontier model with light reasoning may dominate for particular task classes.

- Record requested model/effort separately from effective model/effort whenever the runtime exposes the distinction.
- Register only model×effort cells actually supported by the current runtime with `scripts/surface.py register-cell`; never invent availability.
- Use `scripts/surface.py suggest` for controlled exploration. Prefer under-sampled same-model effort neighbors, then under-sampled cross-model cells.
- For consequential/frontier work, prefer shadow evaluation rather than allowing an uncertain cheap route to control the outcome.
- Distinguish effort insufficiency from model-capability insufficiency when evidence supports it: success after increasing effort favors horizontal escalation; repeated failure across effort levels favors a stronger model.

## Hard rules

- The front-door model remains user-selected; never silently change the UI-selected front door.
- The parent owns decomposition, integration, and final acceptance. Delegation transfers execution, not correctness responsibility.
- A cheap front door must not become a weak gatekeeper; escalate classification/planning early when uncertainty is consequential.
- Escalate rather than repeatedly retrying an underpowered route.
- Give children minimum sufficient context and require evidence-bearing result packets.
- Never weaken tests, acceptance criteria, safety rules, permissions, or verification requirements to improve apparent efficiency.
- Learned state may tune preferences only inside this policy envelope and may not rewrite this skill.
- Respect recursive delegation depth/fan-out limits; every parent remains accountable for child output.
- Never present estimated token/credit usage as measured. Unknown rates or counters remain unknown.
- **Never create Git worktrees by default.** Worktrees require explicit repository policy or user opt-in and must follow the managed lifecycle/recovery rules in `references/parallel-safety.md`.
- If no tested write-isolation mechanism is explicitly available, serialize repository mutations rather than inventing isolation.
- Never create an Agent Dispatch temporary resource outside its managed namespace; register before create, and reconcile stale managed resources at the top of subsequent activations.

## Evidence hierarchy

Strongest evidence wins: deterministic tests/acceptance/benchmarks; independent review; parent integration acceptance; worker self-report. A clean success has no contradictory stronger evidence and no attributable corrective rework.

## Telemetry and autonomous learning

Use `begin-run`, `begin-task`, `bind-task`, and `finish-task` for materially delegated tasks, and `record-run` for every substantial user-facing run or milestone. Raw telemetry is append-only: terminal events link to receipts by `run_id` and `task_id`; they never update prior records. Keep `record` only for legacy/unmanaged observations. Record measured usage when exposed and explicitly unknown otherwise.

The learner maintains global and project-local evidence, recency weighting, run-level front-door comparisons, reviewer/concurrency/retry/escalation policy, and frontier-use accounting. `recommend` refreshes learned state before routing. Parallelism learning cannot override the worktree opt-in rule or other explicit write-safety constraints.

## Token, credit, and savings accounting

Use `scripts/usage.py record-turn` to record usage for the front door and each materially used subagent separately. Lifecycle-managed worker components also identify `task_id`, so repeated activations of one agent remain auditable. Each component identifies agent ID, role, model, reasoning effort, and measured/estimated token counts or an explicit unknown state.

The collaboration result packet may omit worker counters even though the local Codex child rollout contains them. `--capture-task-usage` reads only local rollout metadata, task boundaries, model settings, and `last_token_usage` counters; it does not persist prompts or responses. The current parent thread ID is used to prevent cross-thread agent-path collisions. If an unknown or malformed usage event was already appended, record the corrected complete turn with `--supersedes-turn-id <old-turn-id>` so audits and reports use only the effective replacement.

The ledger derives credits from the local Codex rate card when a public numeric rate exists. A model with no numeric published rate remains unknown rather than being assigned a guessed price.

At the end of each user-facing turn, use `scripts/usage.py footer` to surface a compact total plus per-subagent/model/effort breakdown. Use `scripts/usage.py report` for aggregate project reporting.

Reports also calculate a **Sol/max same-token counterfactual**: the observed input/cached/output token mix is repriced at the Sol rate to estimate what the same token volume would have cost if routed entirely to Sol. Reasoning effort itself is not a separate rate-card multiplier; max reasoning may change token volume in reality. Therefore this baseline is explicitly an estimate, and a baseline token multiplier may be used for sensitivity analysis or an empirically learned multiplier. Never describe the counterfactual as actual usage.

## Promoting burn-in into repository defaults

Burn-in discoveries should survive beyond transient global telemetry when project-local evidence is strong.

Use `scripts/surface.py promote --repo-root <repo> --project <project> --task-class <class> ...` after tuning. Promotion requires a minimum project-local sample count, high clean-success rate, low rework, and a meaningful utility lead over competing cells. It writes only the generated, inspectable file `.agent-dispatch/defaults.json`; it does **not** rewrite project source or `AGENTS.md`.

Repository defaults are strong priors, not immutable truth. New project-local evidence may supersede them, and a changed model/runtime revision should earn confidence again. Commit promoted defaults when they are useful to future clones/agents.

## Internal repair primitives

These commands exist for the skill/agent to initialize, reconcile, or repair itself. They are not required user-facing installation steps:

- `scripts/dispatch.py init` — ensure local orchestration state
- `scripts/bootstrap_agents.py` — ensure the managed global `AGENTS.md` trigger
- `scripts/resources.py reconcile` — recover/clean expired Agent Dispatch-managed resources
- `scripts/resources.py list` — inspect the managed resource registry
- `scripts/usage.py show-rates` — inspect/initialize the local rate card

## Useful commands

- `scripts/dispatch.py recommend` / `explain` — routing and execution policy
- `scripts/dispatch.py begin-run` — create a run receipt before the first dispatch
- `scripts/dispatch.py begin-task|bind-task|finish-task` — append the delegated-task lifecycle
- `scripts/dispatch.py audit-run` — fail-closed lifecycle, runtime-agent, and usage reconciliation
- `scripts/dispatch.py report` — front-door and frontier-use reporting
- `scripts/usage.py record-turn` — per-task/per-agent rollout-captured, directly measured, estimated, or unknown usage; supports append-only correction with `--supersedes-turn-id`
- `scripts/usage.py footer` — compact end-of-turn usage + savings line
- `scripts/usage.py report` — aggregate actual usage, route breakdown, and all-Sol/max counterfactual
- `scripts/surface.py register-cell` — record a runtime-supported model×effort cell
- `scripts/surface.py suggest` — choose an under-explored cell
- `scripts/surface.py promote` — promote high-confidence burn-in to repo defaults
- `scripts/resources.py register|activate|heartbeat|complete|reconcile|list` — managed-resource lifecycle and recovery
- `scripts/dispatch.py reset --learned-only` — rebuild learning from retained raw telemetry
