# Routing and escalation

## Capability tiers

Use stable capability labels in policy and telemetry; keep concrete model mappings localized because model lineups change.

- `frontier`: architecture, ambiguous cross-system reasoning, difficult debugging, consequential planning/adjudication, final acceptance when stakes warrant it.
- `general`: bounded implementation, normal debugging, code review, moderate investigation, ordinary integration.
- `cheap`: mechanical edits, repository inventory, grep/search, formatting, simple tests, metadata extraction, straightforward transformations.
- `alternate_pool`: work reliably handled by a model with a separate/favorable usage pool; prefer it when it preserves scarce capacity without reducing expected acceptance.

Current environment mappings should be discovered from the Codex runtime/UI when available. Do not invent model availability. When GPT-5.6 family choices are available, a sensible prior is Sol/frontier, Terra/general, Luna/cheap. Treat Codex Spark as an alternate-pool candidate for bounded work.

## Frontier consultation modes

Use the narrowest sufficient mode:

1. `plan`: ask frontier agent for a bounded decomposition/architecture decision, then execute cheaply.
2. `consult`: ask a focused question when ambiguity or conflict appears mid-task.
3. `subtree`: let frontier agent own a genuinely frontier-heavy subtree only when repeated episodic consultation would be worse.
4. `adjudicate`: resolve conflicting worker/reviewer evidence.

Do not default to `subtree`; it erases most savings of a cheaper front door.

## Escalation triggers

Escalate one tier when any applies:

- confidence is materially low;
- requirements are ambiguous in a way that could change architecture or acceptance;
- two substantive attempts fail for the same underlying reason (often escalate after one when the failure clearly reflects capability mismatch);
- the proposed change broadens scope or crosses subsystem boundaries unexpectedly;
- worker and reviewer disagree on consequential correctness;
- evidence conflicts;
- the task has become materially different from the bounded delegated packet.

Avoid retry loops. Record failed attempts and escalation so the learner can route similar work directly to the stronger tier later.

## Front-door behavior

The user chooses the front-door model through normal Codex UI controls. Record it as an experimental dimension. A cheap front door must not become a weak gatekeeper: when task classification itself is uncertain or consequential, consult a stronger agent early.
