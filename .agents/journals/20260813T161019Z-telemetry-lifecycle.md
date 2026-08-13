# Telemetry Lifecycle Enforcement

UTC task journal for the Agent Dispatch telemetry lifecycle implementation and publication goal.

## Chat Log

### User

> activate a goal to implement all of this, when complete, commit to main and push remote, update the global installation of the skill on this machine

### Assistant

> COMPLYING WITH GLOBAL AGENTS.MD
> V56
>
> I’ll activate a goal and implement the telemetry lifecycle, enforcement audit, unknown-usage support, documentation, and tests; then I’ll journal the repository changes, commit directly to `main`, push `origin/main`, and refresh the machine’s global skill installation. I’m using `agent-dispatch`, `skill-creator`, `repository-journaling`, `github:yeet`, `skill-installer`, and `local-reasoning` in that order because this spans skill design, code changes, publication, and installation.

### Assistant

> The goal is active. I’m honoring the user’s explicit direct-to-`main` instruction, which overrides the publish skill’s usual feature-branch/PR default. I’ll keep the working tree scoped, verify GitHub authentication before publishing, and use the local model only for bounded review—not implementation authority or final acceptance.

### User

> more feedback from the agent, take from this what you will:
>
> ---
>
> Yes, I would amend it in two places:
> Agent Dispatch: make pre-spawn registration mandatory—initialize/reconcile, select the route, create the run ID, and write a provisional task record before any worker is launched. If that fails, dispatch must stop.
> Global/repository instructions: prohibit raw subagent spawning for substantive work unless that pre-spawn receipt exists, with a narrowly documented emergency exception.
> Then completion should finalize the same record with the actual model/effort, outcome, verification, rework, and token counts—or explicitly unknown. A turn-level run summary should be mandatory before replying.
> That closes the loophole I fell through. The present skill treats telemetry as an end-to-end responsibility, but its hardest wording is at “record materially delegated tasks,” which allowed me to postpone it incorrectly. The repository rules already demanded more; I failed to apply that stricter layer. The telemetry has since been backfilled, but backfill is audit recovery, not compliance.

### Assistant

> That feedback strengthens the fail-closed boundary, and I’m adopting it with one important adjustment: “finalize the same record” will be implemented as a terminal append-only event linked to the pre-spawn receipt, preserving the existing immutable raw ledger.
>
> I’ll also tighten the managed global Agent Dispatch trigger so substantive raw spawning is prohibited without a receipt. The emergency exception will be limited to urgent safety/containment work when telemetry itself is unavailable, must be disclosed and backfilled, and cannot be treated as normal compliance. Because this changes global `AGENTS.md`, I’ll increment its version and reload it as required.

### Assistant

> The first local test-planning response did not actually return the checklist it claimed to generate, so I’m rejecting that invocation and making one tighter bounded retry. If the retry is similarly incomplete, I’ll proceed from repository evidence without further local-model churn.

### Assistant

> The implementation contract is now settled:
>
> - `begin-run` creates the run identity.
> - `begin-task` emits the mandatory pre-spawn receipt.
> - `bind-task` attaches the host-returned agent ID.
> - `finish-task` appends the terminal outcome and effective route.
> - Task-aware usage records accept measured, estimated, or explicitly unknown counters.
> - `audit-run` reconciles lifecycle, usage, expected runtime agents, and dispatch count.
> - `record-run` automatically invokes the audit and refuses to summarize an incomplete managed run.
>
> Start events remain separate from learner outcome events, so provisional work cannot be mislearned as failure.

### Assistant

> The first full test run exposed one versioning bug: the regex that increments `Global AGENTS.md` consumed the blank line after the header, making an otherwise idempotent second bootstrap look changed and bump again. I’m narrowing that regex to horizontal whitespace; the lifecycle and usage tests themselves passed.

### Assistant

> The implementation and validation suite now pass: 21 unit tests, Python compilation, standalone package validation, and the system skill validator. The second local test-planning attempt contained useful prompts but contradicted the intended event ordering in several cases, so I’m rejecting it as authoritative and continuing with direct diff review and deterministic tests.

### Assistant

> The implementation now durably flushes each receipt and usage event before returning, so “registration succeeded” means the JSONL entry has been written and synchronized—not merely queued in memory. I’m normalizing the modified files back to the checkout’s CRLF working-tree policy before the final verification pass.

### Assistant

> Repository-journaling sidecar created: `.agents/journals/20260813T161019Z-telemetry-lifecycle-1.patch`. It captures the complete non-journal change batch before publication.

## Patch Files

- `.agents/journals/20260813T161019Z-telemetry-lifecycle-1.patch` — complete non-journal implementation, documentation, metadata, and test diff.

## Changes Made

- Added schema-v3 append-only run and delegated-task lifecycle events with pre-spawn receipts, agent binding, terminal outcomes, actual route metadata, durable flushes, and duplicate/conflict checks.
- Added fail-closed `audit-run` reconciliation for task outcomes, task-aware usage, explicit unknown counters, front-door usage, expected runtime agent IDs, and expected task counts.
- Made managed `record-run` automatically audit and refuse incomplete summaries.
- Added task-aware measured/estimated usage and explicit unknown front-door/task usage while preserving null counters and visible unknown routes in reports and footers.
- Tightened the managed global Agent Dispatch trigger and added idempotent global instruction version increments when that block changes.
- Updated the skill instructions, learning reference, README, UI metadata, and standalone validation contract.
- Expanded deterministic coverage from 12 to 22 tests, including reactivation, failed spawn, duplicate lifecycle events, missing telemetry, runtime reconciliation, unknown usage, rough-message rejection, and bootstrap version idempotence.

## Problems Encountered

- The first local reasoning result omitted its requested checklist; the retry returned concrete cases but contradicted the intended lifecycle ordering. Both invocations were rejected and not used as acceptance evidence.
- The first bootstrap version test caught a multiline-regex bug that incremented the global instruction version repeatedly. Restricting the header suffix to horizontal whitespace restored idempotence.
- Patch edits produced mixed working-tree line endings. All modified text files were normalized back to the repository’s CRLF checkout policy before final verification.
- Tracking a conventional unified diff caused its blank context prefixes to trip `git diff --check`; the sidecar was regenerated with zero context and validated using `git apply --unidiff-zero --reverse --check`.

## Lessons

- A prose obligation is insufficient for telemetry that must precede an external host call; a durable receipt plus a fail-closed terminal summary creates a much stronger invariant.
- Append-only telemetry needs separate start, bind, and terminal events. Reusing the learner’s terminal event type for provisional records would contaminate routing evidence.
- Unknown usage is a first-class state, not zero usage, and must remain visible in aggregate reporting.
- Ledger-only audits cannot discover calls that bypassed registration entirely; runtime agent IDs and expected dispatch counts are necessary reconciliation inputs until the host provides a transactional dispatch hook.
