# Automatic Activation Contract

## Chat Log

**User**

> activate a goal to update the skill thusly and reinstall locally when complete

**Assistant**

> COMPLYING WITH GLOBAL AGENTS.MD V58
>
> I’m activating a goal to harden Agent Dispatch’s automatic-activation contract, update its regression coverage and documentation, verify the change, then reinstall the updated skill locally and confirm the global trigger was refreshed. I’ll use `agent-dispatch` for the work, `skill-installer` for the local reinstall, `local-reasoning` for required telemetry, and `repository-journaling` before completion.

**Assistant**

> The repository has pre-existing untracked benchmark/journal work, so I’ll leave it untouched. The relevant tracked files use CRLF, which I’ll preserve. Agent Dispatch recommends a general-tier worker; I’m registering one read-only review task now so an independent agent can challenge the wording and test boundary while I implement.

**Assistant**

> I’m also using the local reasoning model for one narrow task: generate assertions that distinguish “automatic decision protocol” from “always spawn.” It will not edit or authorize changes; I’ll accept or reject its suggestions against the actual bootstrap behavior.

**Assistant**

> The independent review agrees with the narrow fix and surfaced one useful additional guard: make the skill’s own discovery description mandatory too, because that metadata can decide whether the skill loads at all. I’m accepting that finding and will keep receipts/telemetry conditional on actual delegation so local-only tasks do not become fail-closed orchestration runs.

**Assistant**

> The patch introduced mixed newline sequences at the edited hunks, so I’m normalizing only the four touched files back to their existing CRLF policy before testing. No unrelated files are being rewritten.

**Assistant**

> The targeted contract tests pass, including the upgrade path that replaces an old managed block and increments the global instruction version once. I’m running the full repository validation next; after that I’ll create the required journal/sidecar before touching the installed skill.

**Assistant**

> Repository journaling is in place. The non-journal change batch is captured in `.agents/journals/20260814T153123Z-automatic-activation-contract-1.patch`; the existing unrelated benchmark/journal artifacts remain untouched. Next I’m refreshing the installed skill and then running the installed bootstrap against the global instructions.

**Assistant**

> The local reinstall is complete: 20 package files were refreshed with zero hash mismatches, the installed package passed validation and all 29 packaged tests, and the managed bootstrap updated global instructions once and was idempotent on the second run. Because that changed a governing instruction, I’m reloading both the new global `AGENTS.md` and installed `SKILL.md` now before final verification.

**Assistant**

> The completion audit correctly failed closed because my front-door usage tuple omitted its required `measured` provenance field. No run summary was written. I’m correcting that telemetry entry and rerunning the audit; the repository and installed skill remain unaffected.

**Assistant**

> One final accounting check caught that the turn estimator reports cached tokens as a subset of total input, while Agent Dispatch expects uncached and cached input separately. I’m appending the required superseding telemetry event so the completed run is not double-counted; this does not change the implementation or installation.

**User**

> merge and push hoss

**Assistant**

> COMPLYING WITH GLOBAL AGENTS.MD V59
>
> I’ll publish only the completed automatic-activation change set and its journal artifacts, leaving the unrelated untracked benchmark work alone. I’m applying `agent-dispatch` automatically for the repository workflow and using the GitHub `yeet` publication checks; because you explicitly asked to merge and push, I’ll commit directly on the current branch and push it if the branch/remote state is clean.

**Assistant**

> The branch is `main`, exactly synchronized with `origin/main`, and GitHub authentication is healthy. The worktree is mixed, but the intended scope is unambiguous from the completed task: four implementation files plus its two `20260814T153123Z` journal artifacts; I’m excluding the older journal and all model-characterization files. Since publication is linear and already fully tested, the dispatch decision is to keep it local rather than spawn another worker.

**Assistant**

> I’m using the local reasoning model only to sanity-check the six-file commit scope against the stated publish intent. It cannot stage, commit, merge, or push; I’ll independently verify the staged diff before the external write.

**Assistant**

> The local scope check failed before producing advice because Ollama crashed during CUDA initialization. I’m recording it as escalated and proceeding with the evidence already in Git: the six paths correspond exactly to the completed task, while every excluded path predates or belongs to separate work.

## Patch Files

- `20260814T153123Z-automatic-activation-contract-1.patch` — source, documentation, bootstrap, and regression-test changes; journal files excluded.

## Changes Made

- Replaced advisory bootstrap language with an explicit automatic decision-protocol requirement for every nontrivial coding or repository task.
- Explicitly authorized unprompted skill loading, subagent delegation, and parallel agent work when the decision protocol finds material benefit.
- Preserved conditional spawning and local execution for trivial or non-beneficial work.
- Updated the skill discovery description and start-of-task protocol to distinguish mandatory activation from mandatory spawning.
- Updated public documentation to describe Agent Dispatch as post-install standard operating procedure.
- Added bootstrap and public-contract regression tests, including the managed-block upgrade path.

## Verification

- `python scripts/validate_skill.py` — passed.
- Three targeted automatic-activation tests — passed.
- `python -m unittest discover -s tests -v` — 34 tests passed.
- `git diff --check` — passed.
- Confirmed the four touched tracked files retain CRLF line endings.
- Refreshed 20 tracked package files into the local installation with zero SHA-256 mismatches.
- Installed `scripts/validate_skill.py` — passed.
- Installed package test suite — 29 tests passed.
- Installed bootstrap upgraded global `AGENTS.md` from V58 to V59 exactly once; a second run reported the trigger current.
- Reloaded global `AGENTS.md` V59 and the installed `SKILL.md`; both contain the automatic-activation contract.
- Agent Dispatch lifecycle audit passed with one registered, bound, completed, and usage-attributed review task; the run summary was recorded successfully.
- Appended a superseding front-door usage event separating uncached input from cached input; the follow-up lifecycle audit passed.
- Publish preflight confirmed `main` exactly matched `origin/main`, the GitHub CLI was authenticated, and only the six task-owned paths were selected for publication.

## Problems Encountered

- Applying the textual patch created mixed newline sequences at edited hunks. The four touched tracked files were normalized back to their existing CRLF policy before validation.
- The working tree already contained unrelated untracked benchmark and journal artifacts; they were preserved and excluded from the change patch.
- The first completion-audit attempt omitted the required usage-provenance field and failed closed as designed. The tuple was corrected to measured provenance, after which the audit and run summary passed.
- A subsequent accounting review found the turn estimator's input total includes cached input, while Agent Dispatch records those classes separately. An append-only superseding event corrected the double count.
- The local publish-scope review crashed during CUDA initialization before returning advice. The parent retained responsibility and verified the six-path scope directly from Git status, diff, and this journal.

## Lessons

- A managed instruction that merely says to “consider” orchestration can be treated as advisory under a host guard requiring explicit delegation authorization.
- The activation contract must appear both in the installed global trigger and the skill discovery metadata; either can gate whether the detailed protocol is loaded.
- Mandatory protocol application should not imply mandatory worker creation, run receipts, or usage telemetry for local-only work.
