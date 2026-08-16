# Model characterization pilot

This benchmark compares bounded advisory routes with identical synthetic task
content and a common structured response contract. It is designed to measure
the operational route as used by Agent Dispatch, including prompt overhead,
wall-clock latency, exposed token counters, deterministic acceptance, and
rate-card-derived remote credits.

The v1 suite contains ten tasks covering structured extraction, dependency
planning, debugging, code synthesis, data aggregation, contract review,
ambiguity calibration, adversarial instructions, quantitative reasoning, and
constraint solving. The scorer is deterministic and executes generated Python
only in an isolated interpreter with a fixed behavior harness.

Routes:

- `local-20b`: Ollama `gpt-oss:20b`
- `local-120b`: Ollama `gpt-oss:120b`
- `luna-low`: Codex `gpt-5.6-luna` at low reasoning
- `terra-medium`: Codex `gpt-5.6-terra` at medium reasoning
- `sol-high`: Codex `gpt-5.6-sol` at high reasoning

Local routes use the local-reasoning client and its compact bounded-worker
prompt. Remote routes use an ephemeral read-only Codex execution with the same
task content and response schema. Consequently, token counts describe each
real operational route; they are not tokenizer-normalized measures of abstract
model efficiency.

Run one route with:

```powershell
python benchmarks/model_characterization/run_pilot.py `
  --route luna-low `
  --run-id <agent-dispatch-run-id> `
  --output benchmarks/model_characterization/results/<pilot>/luna-low.json `
  --skill-version <revision>
```

Local routes also require the active local-reasoning session ID and start time.
The runner writes results atomically after every task and resumes by skipping
task IDs already present in the output file.

The initial August 13, 2026 pilot report is in
`results/2026-08-13-pilot-v2/report.md`.

The harder v2 suite is in `tasks-hard.json`. Pass it with
`--tasks-path benchmarks/model_characterization/tasks-hard.json`. It raises
the context and compositional-reasoning burden while retaining deterministic
scoring and the identical response contract across all five routes.
