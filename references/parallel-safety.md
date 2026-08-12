# Parallel safety

Parallelize the dependency graph, not merely the task list.

## Defaults

- Run independent read-only investigation concurrently up to runtime/resource limits.
- Prefer a small useful fan-out (roughly 3–5 workers) over an indiscriminate swarm unless evidence and runtime capacity justify more.
- Give concurrent implementation workers isolated branches/worktrees when available.
- Never let two workers knowingly modify the same file or logical subsystem concurrently without explicit coordination.
- Parent integrates sequentially in dependency order and resolves semantic conflicts; a clean Git merge is not proof of semantic compatibility.
- Do not create a worktree for a read-only worker unless isolation materially helps.

## Conflict classification

Label each subtask:

- `read_only`
- `write_isolated`
- `write_shared`

`read_only` is generally safe to parallelize. `write_isolated` may run concurrently when paths/subsystems are disjoint or worktrees isolate changes. Serialize `write_shared` unless a stronger coordination mechanism is explicitly designed.

## Learned parallelism

Telemetry records whether work ran in parallel, group size, write class, and whether a semantic/merge collision caused failure or rework. The learner may recommend a preferred concurrency for a task/project/domain based on successful group sizes and collision rate.

Learned concurrency is advisory and cannot override explicit write-safety rules. When collision rate rises, become more conservative; when isolated/read-only work repeatedly succeeds, modestly increase concurrency up to the configured cap.
