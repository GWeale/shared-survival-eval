# November 6, 2026 release council

The council recommends a research-informed experimental release with a certified incentive conflict, reproducible cross-play and stronger execution checks. It does not endorse a state-of-the-art performance claim. The original Astra pilot tested one model in eight worlds and missed its 90% clean-execution target.

Three independent, read-only Codex reviewers examined shared revision `d6f80eb3a184d786a06567c5735e111ae8479c0f` and individual revision `587f9cce4eeaad776de6a921f3757e362419a536`. GPT-6 Astra reviewed incentives, GPT-6.1 Sol reviewed methodology, and GPT-6.1 Terra reviewed reliability and publication readiness. They received the same user request and original artifacts, with separate scopes and no other reviewer's conclusions. This was a single-provider panel, not cross-provider validation. Both 60-test baseline suites passed before implementation.

## Decisions implemented in 0.4

- Add opt-in `allocation-v1`: equal production opportunity across roles, simultaneous private/common choices, separate accounting and an exhaustive unilateral-incentive certificate. Keep the old station workloads and historical pilot separate.
- Add objective-aware, cooperative, selfish, reciprocal, forgiving and switching production controls. Supply development and cross-play plans, rotate the focal agent across all roles, and freeze every episode assignment in the manifest before execution.
- Add paired unconditional cargo, realized completion and allocation-payoff contrasts. Disclose missing/error pairs; reject duplicate episode identities, incompatible summary inputs and mismatched paired scenarios or assignments. Keep role strata and communication-character counts visible.
- Preserve paired comparisons and plan fingerprints in checkpoint reports. Evaluating supplied plans does not verify that they are genuine training checkpoints or that increasing training-count labels caused improvement.
- Serialize session creation and updates with kernel-released locks, preserve idempotent envelopes, flush atomic state replacements, and bound subprocess stdout/stderr while reading. Separate invalid decisions from invalid-field events.
- Add release documentation and CI checks for tests, package installation and the executable incentive certificate. Keep all raw model transcripts, credentials and private evaluator state outside Git.

The lead rejected a preliminary claim that `v2 run --workload joint` ignored its flag: the generic configuration loop already handled it, and the reviewer retracted the finding. Longer horizons alone were also rejected as evidence of strategic difficulty.

## Research available by the cutoff

These primary sources informed the design; no algorithms or source code were copied from them.

| Source and version date | Relevant evidence | Application here |
|---|---|---|
| [CoopEval v2, July 5, 2026](https://arxiv.org/abs/2604.15267v2) | Compares repetition, reputation, mediation and contracts in mixed-motive games; varying co-players can change outcomes. | Evaluate distinct partners and certify incentive conflicts rather than assuming communication causes cooperation. |
| [Learning Robust Social Strategies with LLMs v3, October 30, 2026](https://arxiv.org/abs/2511.19405v3) | Studies cooperative payoff alongside resistance to exploitation and opponent-aware training. | Include production-only selfish and changing partners; separate frozen-model play from learned strategies. No training algorithm is implemented here. |
| [MASBench v2, November 4, 2026](https://arxiv.org/abs/2610.04672v2) | Evaluates partial observability, collaboration mechanisms and communication cost with repeated runs. | Preserve seat boundaries and distinct communication/call/token accounting; use repeated, paired model rollouts in future studies. |
| [Melting Pot, ICML 2021](https://proceedings.mlr.press/v139/leibo21a.html) | Evaluates generalization to social situations and partners beyond training performance. | Separate development/evaluation partner sets and avoid claiming generalization from known scripted partners. |
| [Evaluating Collective Behaviour of Hundreds of LLM Agents v2, July 2, 2026](https://arxiv.org/abs/2602.16662v2) | Uses strategy generation, behavioral fingerprints and population mixtures to study collective outcomes at scale. | Keep action-level strategic controls and payoff matrices explicit; no population-scale or evolutionary claim follows from this four-seat release. |

The literature scan is bounded, not exhaustive. It supports these design choices without proving novelty or superiority to other benchmarks.

## Release verification

Both final packages pass 73 local tests. Each builds and installs in a clean temporary Python 3.13 environment, and its installed CLI reproduces the 16-profile certificate from outside the checkout. A fresh Sol code review found one conflicting nested reward instruction in allocation observations; it was corrected in both packages and covered by a regression test across every player-visible reward description. The reviewer found no other release blocker. These reviews share one provider and are not external validation.

The [scripted checks](allocation-checks.json) cover 320 completed episodes: four public development worlds, five partner types, four focal roles, two reward modes and two deterministic repeats. All survived with zero invalid decisions; every role received 36 allocation opportunities. All 160 paired reward-mode cases preserved ordinary station cargo and scenario identity. After the reward-instruction correction, all 320 policy runs were recomputed against the final source and matched the recorded terminal results and full event histories. The artifact retains the original batch source hash and the final-source recheck hash.

These are engineering checks over four distinct worlds, not 320 independent statistical samples or new model evidence. No model inference or training was run for this release. The historical pilot's failed infrastructure target and unresolved shared-reward effect remain unchanged.

## Deferred work and public scope

Information pooling, production-value removal, bankable resources with a certified planning oracle, all-model experiments and training studies remain future work. Implementing them without their information-boundary and optimality checks would broaden the benchmark's claims faster than its evidence. No new paid model inference is part of this release.

Publication was explicitly requested by the owner. Public visibility is distinct from granting a reuse license. No open-source license has been selected; the release makes no open-source licensing claim. The owner can separately choose licensing terms. This does not prevent publishing the repositories for inspection.

The lead screened the full reachable Git history for credential patterns, local private paths, runtime-session identifiers and sensitive filenames before publication. This is a bounded screen, not a guarantee against every possible secret. Historical data and limitations are retained. No new model leaderboard, learned-cooperation result or SOTA claim is published.
