# Parallel safety

Parallelize the dependency graph, not merely the task list. Parallelism is an optimization, not a correctness requirement.

## Defaults

- Run independent read-only investigation concurrently up to runtime/resource limits.
- Prefer a small useful fan-out (roughly 3–5 workers) over an indiscriminate swarm unless evidence and runtime capacity justify more.
- **Do not create Git worktrees by default.**
- Serialize repository mutations unless the repository explicitly declares a tested isolation mechanism or the user explicitly opts into one.
- Never let two workers knowingly modify the same file or logical subsystem concurrently without explicit coordination.
- Parent integrates sequentially in dependency order and resolves semantic conflicts; a clean Git merge is not proof of semantic compatibility.
- Do not create additional repository copies for read-only workers unless isolation materially helps and lifecycle cost is bounded.

## Conflict classification

Label each subtask:

- `read_only`
- `write_isolated`
- `write_shared`

`read_only` is generally safe to parallelize. `write_shared` is serialized by default. `write_isolated` may run concurrently only when the repository already provides a proven isolation mechanism, or the user/repository policy explicitly enables one for Agent Dispatch.

If no safe isolation mechanism is declared, choose less parallelism rather than inventing one.

## Worktree policy

Git worktrees are **opt-in only**. Agent Dispatch must never infer "parallel implementation would be faster" as sufficient permission to create them.

Worktrees may be used only when at least one of the following is true:

1. repository policy explicitly enables Agent Dispatch worktrees and defines the managed location/lifecycle; or
2. the user explicitly authorizes worktree use for the current project/work.

When worktrees are enabled:

- place every Agent Dispatch-created worktree under one predictable managed directory declared by repository policy; never scatter them through the repository parent directory or other user-visible sibling namespaces;
- do not choose paths outside the repository tree unless repository policy explicitly defines that managed location;
- record lifecycle metadata sufficient to identify owning task/run, branch, creation time, intended cleanup, and current state;
- avoid copying/rebuilding large generated, cache, dependency, build, artifact, or model directories when they can safely remain shared/excluded;
- cap or otherwise account for expected disk amplification before creating additional worktrees when repositories can generate large local state;
- creation must have a deterministic Git-aware cleanup/recovery procedure;
- on later Agent Dispatch activation, inspect managed worktree metadata and `git worktree list` for stale/orphaned managed worktrees before creating new ones;
- interrupted/abandoned work must be reconciled before deletion: inspect uncommitted/unmerged changes, preserve anything potentially valuable, then remove/prune using Git-aware commands;
- never instruct the user to blindly `rm -rf` registered worktrees as the normal cleanup path;
- if cleanup/recovery cannot be completed safely and automatically, stop creating additional worktrees and report the managed leftovers clearly.

The scheduler should treat worktree lifecycle risk, disk amplification, and cleanup cost as real orchestration costs. If they outweigh expected wall-clock savings, serialize the writes.

## Repository-provided isolation

Prefer a repository's existing, tested concurrency mechanism over inventing a generic one. Examples can include repository-native task sandboxes, disposable clones managed by project tooling, isolated build roots, generated-file partitioning, or another explicit mechanism documented by the project.

Agent Dispatch should follow that mechanism's lifecycle rules and telemetry should identify which isolation mechanism was used. Absence of a declared mechanism means repository writes serialize by default.

## Learned parallelism

Telemetry records whether work ran in parallel, group size, write class, isolation mechanism, and whether a semantic/merge/lifecycle collision caused failure or rework. The learner may recommend a preferred concurrency for a task/project/domain based on successful group sizes and collision/lifecycle cost.

Learned concurrency is advisory and cannot override explicit write-safety or worktree opt-in rules. When collision, cleanup, orphaning, or disk-amplification cost rises, become more conservative; when read-only or explicitly isolated work repeatedly succeeds, modestly increase concurrency up to the configured cap.
