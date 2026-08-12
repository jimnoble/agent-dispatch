# agent-dispatch

Adaptive subagent orchestration for Codex: delegate work to the least-expensive capable model, parallelize independent work safely, escalate instead of thrashing, verify delegated output, and learn routing preferences from local telemetry.

## Install with Codex

Tell Codex:

> Install the `agent-dispatch` skill from `https://github.com/jimnoble/agent-dispatch/tree/main/skills/agent-dispatch` and run its bootstrap step.

Or use Codex's bundled skill installer with that GitHub directory URL.

After installation, restart Codex if the skill does not appear immediately.

## What it does

`agent-dispatch` keeps the front-door model user-selected. Underneath it, the skill:

- decomposes nontrivial work into bounded tasks;
- routes each task to the cheapest model/reasoning tier likely to succeed;
- uses stronger models for planning, architecture, ambiguity, hard debugging, adjudication, and final acceptance when needed;
- preferentially uses alternate usage pools (for example Codex Spark) when suitable;
- runs dependency-independent work in parallel while isolating writes;
- passes narrow context packets to subagents instead of cloning giant parent contexts;
- requires concise evidence-bearing result packets;
- escalates early on uncertainty or repeated failure;
- records local telemetry and autonomously tunes routing preferences within hard safety/correctness bounds;
- reports how different user-selected front-door models perform over time.

## Local data

By default, telemetry and learned routing state live outside repositories at:

`~/.codex/agent-dispatch/`

No telemetry is uploaded by this skill.

## Versioning

Releases use semantic Git tags (`vMAJOR.MINOR.PATCH`). Install a pinned version by changing `main` in the GitHub directory URL to a tag such as `v1.0.0`.

## License

MIT. See `LICENSE`.
