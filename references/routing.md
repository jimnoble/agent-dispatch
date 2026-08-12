# Routing, escalation, and recursive delegation

## Capability tiers

Use stable capability labels in policy/telemetry and localize concrete model mappings because lineups change.

- `frontier`: architecture, consequential planning/adjudication, ambiguous cross-system reasoning, difficult debugging, high-stakes acceptance.
- `general`: bounded implementation, normal debugging, code review, moderate investigation, ordinary integration.
- `cheap`: mechanical edits, grep/search, formatting, simple tests, metadata extraction, straightforward transformations.
- `alternate_pool`: bounded work reliably handled by a separate/favorable usage pool; prefer it when acceptance remains high.

Discover available models from the current Codex runtime/UI. Do not invent availability. When present, a reasonable cold-start mapping is Sol/frontier, Terra/general, Luna/cheap, and Codex Spark as an alternate-pool candidate.

## Frontier consultation modes

Use the narrowest sufficient mode:

1. `plan`: bounded decomposition/architecture decision, then execute cheaply.
2. `consult`: focused frontier question when ambiguity/conflict appears.
3. `adjudicate`: resolve conflicting worker/reviewer evidence.
4. `subtree`: frontier agent owns a genuinely frontier-heavy subtree only when repeated consultation would cost more.

Do not default to `subtree`; that turns a cheap front door into a disguised frontier front door.

## Escalation

Escalate when confidence is materially low, ambiguity can change architecture/acceptance, repeated attempts reveal capability mismatch, scope unexpectedly crosses subsystems, reviewer and worker disagree on consequential correctness, evidence conflicts, or the task materially departs from the delegated packet.

The learned policy can lower retry budgets or escalation thresholds for classes that historically thrash before rescue. Hard upper bounds remain conservative; never use a learned retry budget as a reason to persist through an obvious capability mismatch.

## Front-door behavior

The user chooses the front-door model through normal Codex UI controls. Record it as an experimental dimension. When task classification/planning itself is uncertain or consequential, consult stronger reasoning early rather than relying on a weak gatekeeper.

At the end of a substantial run, record a run summary so front-door quality/cost is evaluated by whole-job outcome.

## Recursive delegation

Recursive delegation is allowed because context isolation can save additional tokens: a general worker may delegate bounded cheap inventory/test/mechanical work instead of doing it itself.

Defaults:

- maximum delegation depth: 2 below the front door;
- every parent remains accountable for child integration/acceptance;
- children must use the same bounded task/result contracts;
- do not recursively delegate merely to create management layers;
- stop recursion when the task is already bounded and cheap;
- fan-out still follows dependency and write-safety rules.

`recommend` reports remaining delegation depth.
