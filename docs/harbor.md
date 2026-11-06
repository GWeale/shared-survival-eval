# Harbor focal-seat tasks

The exporter targets Harbor 0.25.0, task schema 1.4, at [upstream revision ff2a1ef](https://github.com/harbor-framework/harbor/tree/ff2a1ef48070a8df374669138e4d4db79b77f013). It implements one focal agent playing the station game against three scripted partners. It does not turn one terminal agent into four independent models, and it does not perform RL training.

## Export and run

Run from this repository with Python 3.11+:

```sh
python -m shared_survival_eval.harbor export \
  --spec examples/harbor-focal.json --out ../harbor-shared-focal \
  --base-image python:3.13-slim@sha256:09a17cad02668ae61ece136b4fd36ac3849e14f670ebedb637ea3e15580525bc
```

The destination must be new. Export is staged and renamed only after successful generation. The bundle includes `instruction.md`, `task.toml`, agent and station container definitions, `solution/solve.sh`, a dedicated verifier image, and `tests/test.sh`. The generated provenance file records the source fingerprint, exact scenario specification, upstream Harbor revision and image digest. Keep fresh evaluation specifications and exported bundles private: published example seed 83 is development material.

Use the pinned Harbor source on a machine with Docker Engine and Compose v2. Harbor itself needs Python 3.12+; the benchmark package does not depend on Harbor. From that environment:

```sh
harbor run -p ../harbor-shared-focal -a oracle
```

The reference policy plays through the same focal RPC as a model. A real model run requires an explicitly selected Harbor agent/model and its normal usage authorization. The sample uses intro difficulty so integration errors remain distinguishable from game difficulty. Generate distinct role, world, partner and reward-mode tasks for a preregistered evaluation; this single example is not a leaderboard.

## Trust boundary

The `main` container holds only the player client. The `station` sidecar owns the engine, hidden scenario, other-seat observations, pending state and canonical transcript. Its API provides only `GET /observation`, `GET /health`, and `POST /submit` for one fixed focal seat. Random decision IDs bind accepted actions to that live game; identical retries do not advance it twice. There is no reset, cross-seat, arbitrary-file or score-submission endpoint. Requests are bounded and processed serially.

Harbor collects `/evidence/record.json` **from the station service**, then places it in a fresh verifier container. The verifier checks task/source identity, regenerates scripted decisions, replays the episode and derives the terminal reward. Incomplete, inconsistent or modified evidence produces a verification error with no reward file. Model failures and verifier failures must remain separate from simulated station deaths, whose reward is −1.

Do not override artifact declarations, expose Docker sockets, share evaluator volumes/process namespaces, or collapse the services into an agent-writable filesystem. Additional operator-supplied artifacts can change Harbor's collision behavior and invalidate this boundary. The native command/session APIs continue to require trusted evaluator-owned files; source hashes and replay consistency are not cryptographic authentication of arbitrary local logs.

## Evidence and training scope

Both exports load through the pinned upstream `Task` and `TaskConfig` models. Local tests cover focal replay, modified scores and background actions, incomplete evidence, token separation, reward math and adapter failures. Container execution and artifact transfer are a separate acceptance gate; see the [audit disposition](harness-audit-2026-11-06.md) for its current status.

The game artifact is `harbor-focal-v1` replay evidence, not ATIF. A compatible Harbor focal agent may produce its own ATIF trajectory. Do not infer original sampled tokens, tokenizer identity, log probabilities or loss masks from decoded JSON decisions or usage counts. A training backend must capture those values directly and exclude observations and scripted actions from its loss. No token-level training export or learning result is claimed here.

Primary contracts: [task format](https://docs.harborframework.com/tasks/overview), [configuration](https://docs.harborframework.com/tasks/configuration), [separate verifier](https://docs.harborframework.com/tasks/separate-verifier), [multi-container tasks](https://docs.harborframework.com/tasks/multi-container). These are versioned implementation contracts; this project has no external Harbor certification.
