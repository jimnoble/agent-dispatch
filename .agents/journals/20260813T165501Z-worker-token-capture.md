# Worker Token Capture

UTC task journal for replacing unknown collaboration-worker usage with exact local rollout counters.

## Chat Log

### User

> yea about token usage.. an agent reported this.. how do we fix it?
>
> One limitation: worker token counters aren’t exposed by the collaboration runtime. Those entries are honestly labeled token_source: unknown and use rough message-count estimates. Earlier tasks were backfilled when V56 made Agent Dispatch mandatory; future tasks are recorded directly.

### Assistant

> COMPLYING WITH GLOBAL AGENTS.MD V58
>
> I’m tracing the collaboration-runtime fields, Agent Dispatch accounting path, and current tests to separate what can be fixed locally from what requires host support. I’ll use local reasoning for a bounded design review, and because this is a substantive repository investigation I’ll start measured telemetry first.

### Assistant

> The central question is whether exact child counters exist anywhere after a collaboration call returns. I’m checking the host-visible result shape and every current fallback path; if the runtime truly omits counters, the durable fix is to change how Agent Dispatch collects usage—not to relabel rough estimates as measured.

### Assistant

> There is a local path to exact counters: each child has its own rollout log, identified by `session_meta.agent_path`, and that log contains per-request `last_token_usage` records. For the recent Terra worker that was marked unknown, the child rollout yields 14 requests and exact token classes. I’m doing one bounded failure-mode review before I recommend the implementation shape.

### Assistant

> The bounded review agreed with the design and highlighted the same hard edges: parent-thread disambiguation, inherited fork history, reactivation boundaries, and incomplete logs. I’m implementing the collector fail-closed, adding supersession so unknown/backfilled records can be corrected without double counting, and covering those cases with tests. Repository journaling applies because this changes source and documentation.

### Assistant

> The implementation is passing all 26 tests. It now reconstructs exact worker usage from the child’s own rollout, excludes inherited fork history, converts cached input correctly, fails to `unknown` on ambiguous attribution, and lets a later measured record supersede an earlier unknown one without double-counting. I’m documenting the new default workflow and then I’ll run an end-to-end validation.

### Assistant

> The implementation is verified with 27 passing tests, standalone package validation, a clean diff check, and a live read-only capture from the previously unknown Terra worker.

### Assistant

> Repository-journaling sidecar created: `.agents/journals/20260813T165501Z-worker-token-capture-1.patch`. It contains the complete non-journal implementation, tests, and documentation diff.

### Assistant

> The rollout lookup was optimized to prefilter session metadata by the bound agent path before parsing JSON. The same live capture dropped from roughly 11 seconds to 0.57 seconds without changing attribution or counters.

### User

> commit to main and roll out the skill to the local machine globally

### Assistant

> COMPLYING WITH GLOBAL AGENTS.MD V58
>
> I’ll commit the verified worker-token capture changes directly to `main`, then install that exact commit into the machine’s global Agent Dispatch skill with staging validation and rollback protection. I’m using the Agent Dispatch, skill-installer, repository-journaling, and local-reasoning procedures because this spans publication, installation, and telemetry verification.

### Assistant

> The first installer-skill lookup used the non-system path and missed the file; the cataloged system skill is present under `.system`. I’m loading that authoritative installer workflow before touching the global installation.

### Assistant

> The repository is on `main`, the change set is scoped to the implementation, tests, documentation, and required journal artifacts, and all 27 tests pass. I’m running one bounded local release-check review before creating the commit; final acceptance remains based on the deterministic test and install validation.

### Assistant

> The local release-check response didn’t provide the checklist it claimed to, so I rejected it and am relying on the passing deterministic checks. I’m staging only the five implementation/docs/test files and the two required journal artifacts, then committing them on `main`.

### Assistant

> Commit `429d232` is on `main`. Because this commit exists only locally, the GitHub installer cannot install it without pushing; I’m instead exporting that exact Git object into an isolated staging directory, validating the staged package, and only then swapping the global installation while retaining the current copy as rollback.

### Assistant

> The staged package from commit `429d232` passed all 27 tests and replaced the global skill successfully; the previous installation is retained at `agent-dispatch.backup-429d232-20260813T171225Z`. The managed global `AGENTS.md` block was already current and was not changed. I’m recording those results in the journal, amending the still-local commit, then refreshing the installation once more from the final commit so `main` and the global package are exact.

### Assistant

> The final installed package now matches amended commit `823495d` for the implementation, passed standalone validation and all eight token-accounting tests, and left global `AGENTS.md` unchanged. I’m making one journal-only amendment, copying that identical journal into the installed package, and verifying hashes so the final `main` commit and global skill remain synchronized without reinstalling unchanged code.

## Patch Files

- `.agents/journals/20260813T165501Z-worker-token-capture-1.patch` — complete non-journal source, test, skill, and README change batch.

## Changes Made

- Added `record-turn --capture-task-usage <task-id>` to recover exact worker counters from local child rollout records.
- Bound attribution to the lifecycle task, canonical agent path, parent thread, and completed activation window.
- Excluded inherited fork history and selected the correct activation when an agent is reactivated.
- Converted rollout input totals into separate uncached and cached input fields before credit calculation.
- Added measured provenance and request-count metadata without persisting prompts, responses, or absolute rollout paths.
- Prefiltered rollout metadata by agent path so live capture remains fast as the session archive grows.
- Added append-only `--supersedes-turn-id` corrections and effective-turn materialization in usage reports and lifecycle audits.
- Updated Agent Dispatch instructions and README so rollout capture is attempted before explicitly unknown usage.
- Added tests for exact capture, cross-thread mismatch, reactivation attribution, supersession, report behavior, and audit behavior.
- Committed the complete implementation and journal artifacts directly to `main`.
- Exported the commit into an isolated staging directory, passed package validation and all 27 tests, and atomically replaced the global Agent Dispatch skill while retaining the previous installation as rollback.
- Confirmed the managed global `AGENTS.md` trigger was already current, so no global instruction version change was required.
- Re-exported the amended commit, validated the installed package again, passed all eight targeted token-accounting tests, and verified the installed `usage.py` hash exactly matches `main`.

## Problems Encountered

- Collaboration tool results do not expose token counters directly, but the child rollout files do contain exact per-request counters.
- Forked child rollouts include inherited parent history with rewritten timestamps, so naïvely summing the file overcounts heavily. Task boundary selection is required.
- The repository uses CRLF in the working tree; patch edits temporarily produced mixed line endings and were normalized before final verification.
- The first live lookup parsed metadata from every archived rollout and took roughly 11 seconds. A raw agent-path prefilter reduced the same lookup to 0.57 seconds.
- The first installer-skill lookup used the non-system path; the authoritative `.system` skill location from the available-skills catalog was then loaded successfully.
- The bounded local release-check response repeated the supplied facts but omitted its requested checklist. It was rejected and deterministic validation remained authoritative.
- The GitHub installer cannot install an unpushed local commit, so the exact Git object was exported locally and installed through validated staging with rollback protection.

## Lessons

- Missing counters in a tool result do not imply the data is unavailable locally; attribution should inspect the authoritative child execution record before falling back to unknown.
- Agent path alone is insufficient because names can recur across parent threads. Parent-thread and lifecycle timing are required fail-closed keys.
- Append-only telemetry requires explicit supersession semantics; otherwise a later correction causes duplicate task usage and polluted aggregate routes.
- Cached input is a subset of rollout input totals and must be subtracted before storing the uncached input component.
- Global skill updates should validate an immutable staged Git export before replacing the live directory, retain the prior directory as rollback, and rerun installed-package tests afterward.
