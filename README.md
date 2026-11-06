# Shared Survival

Evaluate multi-agent cooperation under a common survival and crew-objective reward.

Four agents share a damaged space station, limited batteries, and six rounds until rescue. Each sees private cargo values and sensor readings, negotiates through public and private messages, and commits actions simultaneously. Every agent receives the same reward for keeping the station alive and completing crew objectives.

## Run

Python 3.11+ is sufficient. Local baselines require no dependencies or API credentials.

```sh
python3 -m shared_survival_eval run \
  --plan examples/baselines.json \
  --out ../eval-runs/shared-survival-eval \
  --seeds 10 --rotations 4 --probes

python3 -m shared_survival_eval replay \
  ../eval-runs/shared-survival-eval/episodes/shared--one-selfish--s0--r0--n0.json \
  --out ../eval-runs/shared-survival-eval/replay.html

python3 -m unittest discover -s tests -v
```

The default eval is `shared`. The alternative reward scheme remains available through `--eval both` for controlled comparisons. This repository has its own Python package (`shared_survival_eval`) and runs independently.

## Included

- A seeded simulation with isolated observations and simultaneous actions.
- Baseline policies, command adapters, and a JSON chat-completions adapter.
- Rotated seat assignments, matched scenarios, isolated prediction probes, and resumable batches.
- Survival and objective metrics, resource accounting, and scenario-bootstrap intervals.
- Offline HTML replays and physically redacted seat exports.

External model adapters require explicit opt-in and can incur charges. Keep runtime logs outside Git. The included results use scripted policies; no live LLM evaluation or RL training has been performed.

[Protocol](docs/protocol.md) · [Model adapters, evaluation plans, and RL API](docs/usage.md) · [Verification](docs/verification.md)
