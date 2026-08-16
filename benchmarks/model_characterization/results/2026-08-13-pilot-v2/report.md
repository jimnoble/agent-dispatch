# Local 120B model characterization pilot

Date: 2026-08-13 UTC  
Suite: `agent-dispatch-model-characterization-v1`  
Agent Dispatch run: `model-pilot-20260813-v2`

## Outcome

The current 120B route is not ready for regular automatic dispatch. It was
correct on all three scored completions, but two consecutive calls reached the
local-reasoning client's fixed 180-second timeout. The circuit breaker then
stopped the batch. One already-started sixth invocation completed in the
background after termination, but its response was unavailable to the scorer;
the remaining four tasks were withheld. This is an operational reliability
finding, not evidence that 120B lacks reasoning capability.

The other four routes all passed all ten tasks with a deterministic mean score
of 1.000. The suite therefore has a quality ceiling for those routes and does
not establish that 120B is equivalent to Luna, Terra, or Sol. It establishes
only a lower bound: on structured extraction, dependency planning, and a
bounded debugging diagnosis, all five routes were correct.

## Full-suite results

| Route | Completed / attempted | Passed | Score | Observed wall time | Exposed tokens | Derived remote credits |
|---|---:|---:|---:|---:|---:|---:|
| Local 20B | 10 / 10 | 10 | 1.000 | 21.325 s | 5,739 | 0 |
| Local 120B | 3 scored / 6 invocations | 3 | 0.600 over five scored attempts | 666.995 s including two timeouts and one unscored completion | 2,424 on response-producing calls; timeout tokens unavailable | 0 |
| Luna Low | 10 / 10 | 10 | 1.000 | 57.031 s | 146,045 | 3.788125 |
| Terra Medium | 10 / 10 | 10 | 1.000 | 56.811 s | 158,783, including 70,400 cached input | 6.245188 |
| Sol High | 10 / 10 | 10 | 1.000 | 67.123 s | 160,213, including 25,088 cached input | 18.126725 |

Credits are rate-card calculations from exposed token classes, not billed
debits. Local routes consume zero remote-model credits; electricity and local
hardware costs were not measured.

## Common three-task comparison

All routes scored 3/3 on the three tasks completed by 120B.

| Route | Wall time | Input | Cached input | Output | Derived remote credits |
|---|---:|---:|---:|---:|---:|
| Local 20B | 5.761 s | 1,310 | 0 | 181 | 0 |
| Local 120B | 205.672 s | 1,246 | 0 | 289 | 0 |
| Luna Low | 18.474 s | 44,144 | 0 | 269 | 1.143950 |
| Terra Medium | 12.880 s | 47,143 | 0 | 224 | 3.030438 |
| Sol High | 17.468 s | 47,778 | 0 | 301 | 6.198000 |

The first 120B call took 175.722 seconds and appears to include cold loading.
Its next two successful calls took 14.168 and 15.782 seconds. Those warm calls
were still about 7–14 times slower than the corresponding 20B calls. The next
two 120B calls each reached 180 seconds without a usable result. A sixth call
completed in 101.258 seconds after the runner was terminated, but could not be
scored because the response was no longer available.

## Operational context

At observation time the host exposed about 64 GiB of physical RAM and an RTX
5090 with 32,607 MiB of VRAM. Ollama reported the 66 GB 120B model split 55%
CPU / 45% GPU with a 32,768-token context, while only about 8 GiB of physical
RAM remained free. This makes CPU offload and memory pressure a plausible
latency contributor, but the pilot did not isolate a single root cause for the
timeouts.

The remote routes include Codex's operational prompt overhead, while local
routes use the compact local-reasoning prompt. Their token counts therefore
measure real route consumption rather than equalized tokenizer efficiency.

## Routing guidance

1. Keep local 20B as the default local route for bounded easy-to-moderate work;
   it matched every remote baseline here and was the fastest complete route.
2. Do not promote 120B to automatic regular use under the present 32k-context,
   180-second-timeout profile.
3. Bring 120B into controlled regular shadow use only after adding a dedicated
   execution profile with a smaller context window, longer timeout, and
   exclusive local scheduling with verified cancellation/drain behavior.
4. After that operational repair, route a modest share of difficult,
   local-eligible debugging, synthesis, and constrained-planning tasks to 120B
   and compare them with 20B and the three remote tiers.
5. Use a harder second-stage suite with partial-credit discriminators and at
   least 30 successful 120B observations before assigning it a Luna, Terra, or
   Sol equivalence. The present suite cannot make that mapping because all
   complete routes hit the ceiling.

## Reproducibility and caveats

- Temperature was 0.2 for local-reasoning calls.
- Local context was fixed at 32,768 tokens by the installed client.
- Each remote task ran in a fresh ephemeral read-only Codex execution.
- Tasks were serialized to avoid local resource and telemetry collisions.
- A preflight run (`model-pilot-20260813-v1`) identified and repaired a Codex
  CLI option-order bug; it is excluded from the formal v2 results.
- The formal 120B batch stopped after two consecutive failures, as required by
  local-reasoning's escalation policy.
