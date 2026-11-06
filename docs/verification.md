# Verification

Verified on George’s MacBook Pro with Python 3.13.18. Runtime dependencies: Python standard library. These checks concern the implementation and scripted controls, not learned model capability.

## V2 verification

Both independent packages pass **47 tests**, including 19 V2 checks. The V2 checks cover hidden information, delayed jobs, permanent deadline damage, component arrival timing, escrow, credit conservation, simultaneous decisions, critical-role free-riding, source-locked sessions, resumable budgets, and checkpoint evaluation.

The frozen scripted calibration completed **1,200 episodes**, with 100 independent scenarios per tier/policy and no invalid decisions. The observation-only planner survived all tested scenarios; this establishes a feasible policy on those scenarios, not full-game optimality. See [calibration provenance and aggregates](v2-calibration.json). No V2 LLM comparison or RL training has run.

V2 public-CLI checks completed both reward modes, mixed partner populations, prediction probes, and checkpoint evaluation. The replay was inspected with the isolated renderer at 728 and 390 pixels, including action and terminal frames. No installed local browser was launched for V2. The lead performed focused review; no independent hidden reviewer was available.

## V1 repository packaging verification (historical)

This repository has its own `shared_survival_eval` package and defaults to `shared`. All **25 tests passed** after the split, including the original behavior checks and a public-CLI regression check confirming that the default runs only this repository’s eval. The paired control path remains covered by the command-agent CLI test with `--eval both`.

Repository changes affect package names, the CLI default, and documentation; the engine and replay template are unchanged. The original combined-harness measurements below remain historical evidence, not a claim that their source fingerprint matches the renamed package. Runtime logs and transcripts are excluded from the repository.

## Original combined-harness verification

- The public CLI completed **800 episodes** across 20 seeds, four cyclic seat rotations, five baseline crew configurations and both evals. All completed; no infrastructure errors or invalid baseline decisions were recorded.
- **24 Python behavior checks passed.** They cover hand-calculated rewards, success and failure, energy conservation, invalid moves, message privacy, same-phase isolation, action-order independence, fixed hazard schedules, probes, seat rotation, paired worlds, budget exhaustion, resumption, configuration mismatch, process adapters, HTTP request/response contracts, replay redaction and script injection.
- The supplied command adapter completed both evals through the public CLI in real subprocesses. Both episodes survived; the persisted budget recorded 96 request attempts.
- The HTTP adapter’s payload, credential placement, parsing and token accounting were tested with a fixture response. No live LLM endpoint or provider-specific model was exercised.
- Re-running the completed batch with `--resume` returned the same summary without running new episodes. The recorded fingerprint identifies the original combined harness at commit `dfb1e99`, before repository-specific packaging. The game rules are unchanged by the split.
- The offline viewer passed headless browser checks for initialization, previous/next navigation, seat switching, private-message filtering, chronological events, terminal rewards, selector focus, and overflow at actual 1200- and 500-pixel viewport widths.
- A separate 390-pixel render passed the same interaction assertions and had a measured document width of 390 pixels. Desktop and narrow screenshots were visually inspected. Native headless Chrome’s requested 390-pixel window initially produced a wider layout and a cropped screenshot; that result was not accepted as mobile verification.
- The lead performed direct code review and secret screening. An independent review was not performed; no hidden reviewer route was established. No publication or deployment occurred.

## Mechanics results

The same scripted policies produce the same survival rates under both incentives because they do not adapt to reward prompts. There are 80 episodes per crew per eval, but only **20 independent scenario blocks**; rotations are not counted as independent scenarios.

| Scripted crew | Survival | Scenario-bootstrap 95% interval |
|---|---:|---:|
| Fixed coordinated repair schedule | 100% | 100–100% |
| Three coordinated agents, one selfish | 97.5% | 92.5–100% |
| Cargo-reporting greedy negotiators | 70% | 50–90% |
| Random actions | 30% | 15–50% |
| All selfish salvage agents | 0% | 0–0% |

These are control-policy outcomes, not a leaderboard of language models. Degenerate bootstrap intervals at 0% or 100% do not prove a population success rate. The coordinated policy deliberately overprovisions repairs; a selfish player sometimes reduces wasted effort, so its presence need not reduce every metric. The greedy negotiator is a heuristic with no optimality claim. Its fixed probability forecasts test the scoring path, not a theory of model reasoning.

[Sanitized aggregate results](baseline-results.json) include the source fingerprint and scenario-level intervals. Full episode logs and HTML replays are in the sibling `../eval-runs/` directory, outside Git.

## Reproduce

```sh
python3 -m unittest discover -s tests -v
python3 -m shared_survival_eval run --plan examples/baselines.json --eval both \
  --out ../eval-runs/reproduce --seeds 20 --rotations 4 --probes
python3 -m shared_survival_eval run --plan examples/baselines.json --eval both \
  --out ../eval-runs/reproduce --seeds 20 --rotations 4 --probes --resume
```

The legacy browser check below is for an explicitly approved browser host. Agents must not launch installed Chrome/Chromium on George’s MacBook; use the isolated renderer there:

```sh
python3 -m tests.browser_check --chrome /path/to/chrome --out ../eval-runs/ui
```

The budget is a request-attempt ceiling, not a dollar cap. Live provider behavior, training gains, human play, broader scenario validity, adaptive-model incentive effects and generalization beyond this environment remain untested.
