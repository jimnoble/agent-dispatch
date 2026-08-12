# Delegation contracts

## Minimal task packet

Construct bounded packets using only relevant context:

```text
TASK
<single bounded objective>

READ
<files, commands, artifacts, or sources the worker should inspect>

DELIVER
<code/commit/report/test/evidence expected>

CONSTRAINTS
<scope, compatibility, write limits, acceptance criteria>

ESCALATE IF
<specific conditions that require stronger reasoning or parent judgment>
```

Prefer repository pointers over pasted parent context. Let workers inspect source directly when that is cheaper and more reliable than summarizing large material.

## Result packet

Require concise returns:

```text
OUTCOME: pass | partial | blocked | fail
SUMMARY: <what was established or changed>
ARTIFACTS: <files/commits/patches>
EVIDENCE: <tests, screenshots, benchmarks, reviewer findings>
UNCERTAINTIES: <remaining uncertainty, or none>
ESCALATION: <why stronger judgment is required, if any>
```

Do not return long exploratory transcripts unless the parent explicitly needs them.

## Worker/reviewer separation

For consequential work, prefer an independent reviewer that receives the artifact/change plus acceptance criteria, not the worker's full chain of rationale. This reduces correlated error.

A reviewer should be read-only unless explicitly asked to fix findings. A review pass does not supersede deterministic tests when deterministic evidence is available.
