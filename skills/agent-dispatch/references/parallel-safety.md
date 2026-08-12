# Parallel safety

Parallelize the dependency graph, not merely the task list.

## Defaults

- Run independent read-only investigation concurrently up to runtime/resource limits.
- Prefer a small useful fan-out (roughly 3–5 workers) over an indiscriminate swarm unless the runtime and task shape clearly support more.
- Give concurrent implementation workers isolated branches/worktrees when available.
- Never let two workers knowingly modify the same file or logical subsystem concurrently without explicit coordination.
- Parent integrates sequentially in dependency order and resolves semantic conflicts; a clean Git merge is not proof of semantic compatibility.
- Do not create a separate worktree for a read-only worker unless isolation materially helps.

## Conflict classification

Before launch, label each subtask:

- `read_only`
- `write_isolated`
- `write_shared`

`read_only` tasks are generally safe to parallelize. `write_isolated` tasks may run concurrently when paths/subsystems are disjoint or worktrees isolate changes. Serialize `write_shared` unless a stronger coordination mechanism is explicitly designed.

## Learning parallelism

Telemetry may tune preferred concurrency and known collision patterns by task/domain. Learned state may become more conservative after merge/rework collisions. It must not override explicit write-safety constraints.
