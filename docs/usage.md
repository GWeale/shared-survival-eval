# Shared survival and individual incentives

Two runnable multi-agent evaluations ask whether agents sustain cooperation when their interests align, and when their rewards depend on private objectives. Both use the same six-round space-station simulation so the incentive scheme can be changed without changing the physical world.

**Status:** working initial protocol, local baseline policies, model adapters, paired runner, isolated belief probes, and offline replays. This is not a validated capability benchmark. No trained model or frontier-model leaderboard is included.

## Run both evals

Python 3.11+ is sufficient. There are no runtime dependencies, API keys, or install step for local baselines. Run commands from the repository root.

```sh
python3 -m shared_survival_eval run \
  --plan examples/baselines.json --eval both \
  --out ../eval-runs/first \
  --seeds 10 --rotations 4 --probes

python3 -m shared_survival_eval replay \
  ../eval-runs/first/episodes/individual--one-selfish--s0--r0--n0.json \
  --out ../eval-runs/first/replay.html

python3 -m unittest discover -s tests -v
```

Open the HTML file directly. It needs no server, network requests, or external assets. The moment selector moves through observations and decisions; the viewpoint selector shows what each seat could see. The omniscient file still contains all private data. For a genuinely redacted export:

```sh
python3 -m shared_survival_eval replay \
  ../eval-runs/first/episodes/individual--one-selfish--s0--r0--n0.json \
  --out ../eval-runs/first/seat-0.html --seat 0
```

Keep runtime artifacts outside the source repository. Output files are private by default. Logs may contain model-generated conversations and private observations. Do not commit or publish them by accident.

## What differs between the evals

| | Shared Survival (`shared`) | Individual Incentives (`individual`) |
|---|---|---|
| Physical rules | Identical | Identical |
| Information | Each player sees its own cargo values, sensor and permitted messages | Same |
| Shared failure | Everyone receives −1 | Everyone receives −1 |
| Rescue reward | Everyone receives `0.5 + 0.5 × crew completion` | Each receives `0.5 + 0.5 × own completion` |
| Primary outcomes | Survival, crew objective completion | Survival, individual objective completion |

Cargo potential is the sum of each seat’s five highest cargo opportunities, the most it could collect with five batteries. Crew completion divides total cargo by total potential. Completion is bounded in `[0,1]`; rewards on rescue lie in `[0.5,1]`. Collected cargo is lost on shared failure when reporting realized completion. The survival rate and personal outcome are always reported separately.

Each round has one simultaneous communication beat and one simultaneous action step. A player can repair shared life support, salvage its own cargo, or wait. A stochastic hazard consumes oxygen after repairs. The engine, not a language-model judge, resolves all consequences. See [the protocol](protocol.md).

## Evaluation plans

A plan registers agents and four-seat crews. The supplied baseline plan contains coordinated, selfish, random, information-sharing, and mixed crews. Baselines are scripted controls; they do not learn or adapt to the reward prompt. Equal cross-eval outcomes for these controls are expected. Their separation checks the mechanics, not model capability.

This repository defaults to `shared`. Pass `--eval both` to run each scenario under both incentive schemes as a matched control. `--rotations 4` moves each crew member through every seat and private objective. `--repeats N` repeats model sampling; a scenario seed cannot force a remote model to be deterministic. Scenario namespaces are separated with `--split train`, `validation`, or `test`. Keep test seeds, task variants and partners out of tuning and training; a seed namespace alone does not guarantee generalization.

Useful switches:

- `--eval shared` or `--eval individual` runs one eval.
- `--communication public` removes private messages; `none` suppresses all communication and commitments. Both retain the discussion request to keep the number of request opportunities comparable.
- `--probes` asks each agent for survival and partner-action probabilities in an isolated request before actions. Probe output never enters observations or changes policy state. Brier scores measure reported forecast accuracy.
- `--max-calls N` limits total attempted agent requests, including probes. It is a request limit, **not a dollar budget**. External attempts are persisted before invocation, including attempts interrupted by a crash.
- `--resume` skips saved episodes and refuses changed code, plans or settings. An interrupted, unsaved episode restarts from its beginning. Saved error episodes remain errors; retry in a new output directory to preserve the original result.

No concurrent writer may use the same output directory. A `.run.lock` holds the process ID. Remove a stale lock only after verifying that its process has ended.

## Connect a model

No external adapter runs without `--enable-external`. This enables processes or model servers and can incur charges. This repository does not choose credentials, start a model server, or download model weights.

**Command adapter:** a trusted executable receives one JSON request on stdin and returns one JSON decision on stdout. It is invoked without a shell, once per request. Full permitted history is in the observation, so no persistent process memory is needed. A working example:

```sh
python3 -m shared_survival_eval run --plan examples/command.json --eval both \
  --out ../eval-runs/command --seeds 1 --rotations 1 \
  --enable-external --max-calls 100
```

Replace the example policy with your model call. Commands inherit your environment and working directory; use trusted adapters. Protocol-level observation isolation does not sandbox arbitrary executable code.

**Chat adapter:** edit the model name in `examples/local-model.json` to an installed local model, then use that plan with `--enable-external`. The adapter targets the JSON-mode `/v1/chat/completions` interface, including the [documented Ollama-compatible API](https://docs.ollama.com/api/openai-compatibility). It sends the complete permitted observation on each call and requests a JSON object. Provider-specific reasoning fields are not supported in this version. Run a small smoke test before a large batch.

Remote endpoints require HTTPS. Credentials are read only from a named environment variable (`api_key_env`); never put a literal key in a plan or argv. Optional `input_usd_per_million` and `output_usd_per_million` fields produce estimates from reported token usage. Missing usage/pricing yields an unknown cost, not zero. Estimates exclude provider-specific caching discounts or billing rules. Both adapters have bounded response handling and per-request timeouts; transport errors end the episode as an error rather than a game loss. Invalid decision JSON instead counts as invalid play and becomes a wait/no-op.

## Results and reproducibility

The output directory contains:

- `manifest.json`: protocol, source fingerprint, plan, seeds, rotations, split and budgets.
- `episodes/*.json`: scenario truth, visibility-tagged events, seat observations, submitted decisions, probes and token usage. These are omniscient, private artifacts.
- `summary.json`: survival, reward, realized cargo completion, resource efficiency, commitments, invalid actions, probe scores, per-agent outcomes, usage and paired incentive comparisons.
- `budget.json`: cumulative attempted requests, retained on resume.

Scenario shocks use independent keyed randomness, so actions cannot change future shocks by consuming a random generator. Results include 95% bootstrap intervals over scenario blocks, keeping all rotations and repeats for a seed together. At least two distinct seeds are required for intervals. Failed episodes and missing pairs are counted explicitly; outcome averages exclude them and may be biased when failures are selective. Pairwise comparisons are within the same crew and scenario. There is no claim that a single scalar rating captures mixed incentives.

## Use as an RL environment

```python
from shared_survival_eval import StationEnv

env = StationEnv(mode="individual", communication="full")
observations = env.reset(seed=42, split="train")
while True:
    decisions = {seat: policy(obs) for seat, obs in observations.items()}
    observations, rewards, done, info = env.step(decisions)
    if done:
        break
```

`policy` is your policy function. During `discuss`, it returns `say`, optional `private: {to, text}`, and optional `commit`. During `act`, it returns `action: repair|salvage|wait`. Intermediate rewards are zero; terminal rewards implement the eval’s incentive scheme. This is a small joint-action API, not a Gymnasium or PettingZoo wrapper. Training algorithms, model weights and training runs are not included.

## Implementation map

`engine.py` owns rules and visibility. `agents.py` owns policy boundaries and transports. `runner.py` owns matched experiments and reporting. `replay.py` and `viewer.html` own private/omniscient exports. `cli.py` exposes run and replay commands.

See [verification](verification.md) for observed checks and current limitations, and [design](design.md) for the implementation boundaries.

## Resume and training provenance in 0.5

Batch manifests fingerprint executable argv files and optional command `artifact_hashes` (file path to SHA256 hex digest). Declare checkpoint weight files explicitly; a remote model name or undeclared directory does not establish immutable weights. Resume preflights saved scenarios, assignments, replay results, usage/probes and cumulative budget before any new calls. This detects inconsistent evaluator records; it does not authenticate records against an attacker who can rewrite all trusted files.

Use `summarize(records, manifest)` for schedule-based coverage, including wholly missing pairs. Without a manifest, coverage is relative to received records. Checkpoint curves accept a complete `config` through Python and `--allocation` through the CLI. Training exclusion remains unverified unless an external training system supplies and audits its own provenance. Default `reset()` is deterministic test seed 0; training callers must explicitly choose and advance their training seeds and split.
