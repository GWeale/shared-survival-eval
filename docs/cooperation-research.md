# Cooperation research and joint workload

## What the benchmark should measure

The primary outcome is **team value delivered while everyone survives**, measured by `delivered_value` (zero if the station is lost). Survival is a constraint and a separate diagnostic. Shared-mode reward is identical for every seat. Individual-mode reward creates conflicting incentives, but evaluate that condition with the same team-delivery metric as well as personal payoff. Do not confuse winning the private incentive game with cooperating well.

A good benchmark should distinguish successful maintenance, useful production, allocation quality, adaptation to unfamiliar teammates, and resilience to mistakes. Message count, persuasive language, and model-name ordering are not objectives. A large gap between named models is not a validity criterion.

## Evidence that changed the design

A 20-scenario validation audit of the original hard V2 workload found:

- The planner survived every scenario and delivered mean cargo 72.6.
- Removing all contract actions still preserved survival in every scenario, with zero delivery and shared reward 0.5.
- Replacing only the scout with a greedy contractor also preserved survival in every scenario; mean delivery fell to 64.55.
- The planner made no accepted trades. Trading was available, but the tested solution did not require it.

These are scripted-policy findings, not GPT results. The earlier survival-only calibration did not demonstrate sophisticated joint production. [Original audit aggregates](cooperation-initial-audit.json) preserve that evidence.

## Research basis

- **SMACv2** tested an open-loop agent that used the timestep without reacting to observations, exposing weaknesses in the original benchmark. It introduced procedural variation and stronger partial observability. We apply its diagnostic lesson with a fixed action schedule trained on a separate scenario, rather than assuming a long episode demands reasoning. [Ellis et al., NeurIPS 2023](https://papers.neurips.cc/paper_files/paper/2023/hash/764c18ad230f9e7bf6a77ffc2312c55e-Abstract-Datasets_and_Benchmarks.html).
- **Melting Pot** evaluates social generalization to unfamiliar situations and partners. We use paired partner interventions and report each focal role separately. [Leibo et al., ICML 2021](https://proceedings.mlr.press/v139/leibo21a.html).
- **Overcooked** showed that strong self-play can fail with different partners. We keep homogeneous-team and mixed-partner results separate. These scripted partners are not substitutes for human testing. [Carroll et al., NeurIPS 2019](https://proceedings.neurips.cc/paper/2019/hash/f5b1b89d98b7286673128a5fb112cb9a-Abstract.html).
- **Hanabi** makes cooperative decisions depend on imperfect information and teammates' beliefs and intentions. The new workload distributes costs and valuations across players; a single player cannot see all order values. Subsequent council ablations found little benefit from using those values in the reference allocation policy, so this design does not yet demonstrate Hanabi-like inference. [Bard et al., Artificial Intelligence 2020](https://arxiv.org/abs/1902.00506).
- The **Overcooked Generalisation Challenge** jointly tests unknown partners and unfamiliar environments. Our bounded research runner separates validation-based configuration selection from a frozen holdout. This is an application of the evaluation principle, not a reproduction of its training method. [Ruhdorfer et al., TMLR](https://arxiv.org/abs/2406.17949v3).

## Joint production workload

Opt in with `--workload joint`. The default `solo` workload retains the previous rules and reward formula. Both are identified explicitly in manifests and observations; never pool their scores.

Each round offers six work orders, one for each pair of seats. Every order needs both assigned players to select its id during the same action phase. Each participant privately sees its own required component and cargo value. Each spends one part and one power. A matching pair earns the two participants' values; a mismatch consumes inputs and produces nothing. Orders expire each round. Two disjoint pairs may work concurrently.

Work competes with maintenance, inspection, fabrication, cooling, repair jobs, and transfers for scarce actions and resources. Role assignments, stock, private values, and partner choices determine which allocation is worthwhile. All original life-support failures remain possible. Solo contracts are disabled in this workload, so individual salvage cannot substitute for joint production.

On rescue, shared reward is `team cargo / optimistic opportunity upper bound`. There is **no survival-only bonus**: a maintenance-only crew gets zero. Death still gives −1. Individual reward is `.75 * own cargo / own opportunity bound + .25 * own credits / 40`. This changes the incentives, not the physical transition rules. Credit transfers alone do not improve shared delivery.

The team bound sums exact maximum-weight matchings for each round while ignoring component scarcity and maintenance. It is an optimistic upper bound, **not a feasible full-game optimum**. A low fraction does not mean the remaining fraction is attainable. Use raw delivered value as the primary comparison within matched workload/configuration/seed sets. Do not compare raw totals across different horizons as a skill ranking.

The observation-only `coordinator` communicates availability, inventory, diagnoses, and current private order values, then solves a small matching problem. It has no evaluator-state access. Its maintenance controller is conservative and is not globally optimal. `local_worker` performs the same maintenance but selects its most valuable personally affordable order without agreeing on a partner. `maintenance` does no production. `greedy` neglects maintenance. `opportunist` switches work selection, and `deceptive` publishes false diagnoses. Existing `reactive` and `reciprocal` controls remain solo-only; they are rejected for joint work.

## Reproduce and use

```sh
python3 -m shared_survival_eval v2 run --plan examples/joint-work.json \
  --workload joint --difficulty hard --eval both \
  --seeds 100 --seed-start 50000 --rotations 4 --out ../eval-runs/joint-run

python3 -m shared_survival_eval v2 session-create ../eval-runs/joint-session.json \
  --workload joint --difficulty hard

python3 -m shared_survival_eval v2 curve --checkpoints checkpoints.json \
  --workload joint --out ../eval-runs/joint-curve
```

Use `coordinator` as a scripted background for a focal-player session; omit `--focal` for four independent external players. The session's per-seat observation is the information boundary. Inference requires the separately authorized subscription orchestrator or an explicitly enabled external adapter. None of the research commands calls a model, spends API credit, or trains weights.

## Bounded automatic research

```sh
python3 -m shared_survival_eval v2 research --out ../eval-runs/joint-research \
  --validation-seeds 20 --test-seeds 100 --test-start 40000
```

The command performs one finite research pass, with no recurring job:

1. Test the standard, hard, and extreme joint configurations on validation seeds. Compare coordinated production against local work selection on matched worlds.
2. Admit configurations only when the reference has at least 95% survival and positive-delivery rates, zero invalid actions, and a positive lower paired-bootstrap bound for delivery improvement over the local control.
3. Choose the longest viable horizon using that predeclared rule. Save the selection before inspecting any test outcomes. Longer horizon is a selection rule, not proof of greater cognitive difficulty.
4. Evaluate the frozen choice on fresh test seeds: coordinated production, local choice, maintenance only, no messages, a fixed action schedule derived from train seed 0, a local worker in each of the four roles, and a misleading partner.
5. Report raw delivery, shared reward, survival, mismatched work, invalid actions, and paired delivery differences with scenario-bootstrap intervals. Save failed gates as failures; return a nonzero exit code. If no candidate passes validation, do not evaluate the holdout.

A failed holdout is evidence to retain, not permission to retune on those seeds. Subsequent revisions need new test seeds and a new output directory. The bootstrap is descriptive and can be degenerate at boundaries. Policy ablations show dependence of those policies on information or coordination; they do not prove that every possible strategy needs messages.

## Frozen scripted results

[Complete aggregates and provenance](cooperation-results.json) · [chart](cooperation-results.html) record 120 validation episodes, one train-split schedule reference, and 1,000 held-out episodes (100 independent scenarios per control). Selection chose the 36-round extreme configuration before the test pass. Both repositories use byte-identical simulation, policy, and research modules; this pass executed in the shared-survival package. The scripts do not adapt their policy to reward mode, so no incentive-response conclusion follows.

| Control | Survival | Mean delivered value | 95% scenario-bootstrap interval |
|---|---:|---:|---:|
| Coordinated allocation | 100% | 46.12 | 44.08–48.30 |
| Independent local work choice | 100% | 9.04 | 6.84–11.07 |
| Maintenance only | 100% | 0 | 0–0 |
| No messages | 0% | 0 | 0–0 |
| Fixed train-scenario schedule | 0% | 0 | 0–0 |
| Misleading scout | 0% | 0 | 0–0 |

All predeclared holdout gates passed. The coordinated policy delivered positive value on all 100 cases with zero invalid actions. The fixed schedule averaged 1.45 invalid actions per episode; these are failed game actions, not infrastructure failures. The misleading-partner failure is retained: the reference is brittle to false diagnoses and is not evidence that this condition is unsolvable.

Replacing one coordinator with a local chooser gave mean team delivery 46.12 in the engineer seat, 30.77 in the operator seat, 23.09 in the quartermaster seat, and 33.14 in the scout seat. The engineer's production-policy intervention had no effect here because maintenance occupied that role. Report roles separately; do not treat these seats as interchangeable or hide the zero-effect result in a single average.

Both repositories pass 59 tests. Public CLI checks exercised both reward modes, joint checkpoint evaluation, and default individual-mode routing. Seat exports were checked for hidden work-order leakage. Four representative replay frames were inspected at 390 and 728 pixels with the isolated renderer. The first display assertion mistakenly searched embedded script source for its own `NaN` literal; limiting it to rendered text passed. No installed local browser was launched.

## Current limits and next acceptance criteria

The joint workload is an experimental benchmark improvement, not a validated intelligence leaderboard. The scripted suite tests mechanics and exposes shortcuts. It has not established how Luna, Terra, Astra, or Sol perform on these new tasks, and no RL training has run. Trading remains optional; robust bargaining and long-horizon learning are still unproven.

Before claiming useful model discrimination, run budget-matched independent model players on concealed seeds with balanced roles, compare homogeneous and unfamiliar-partner crews, retain incomplete runs separately, and report scenario-level uncertainty. Freeze the cases before observing model identities/results. Success means higher shared delivery at acceptable survival, robust to partner changes—not a preselected model order. Training claims additionally require learning curves from actual training checkpoints and held-out partners/worlds.

The initial implementation was reviewed by the task lead. A subsequent [five-agent council](council-review.md) independently reviewed the frozen revisions, challenged the controls, and specified the next diagnostic pilot.

The frozen research source is preserved at [shared-survival commit dedb7fd](https://github.com/GWeale/shared-survival-eval/commit/dedb7fdfb4e1e54229d8f82af4c6c07856d57e3f). A subsequent regression fix copies the joint-rule metadata before exposing it to a player, preventing one in-process agent from changing another player’s rule text. The defect was reproduced and the regression now passes. This guard does not change rule content, physical transitions, or reward formulas; the 1,000-episode holdout was not retuned or relabeled as a fresh experiment after this fix.

For the current communication convention, verified limitations, and proposed next experiment, see the [council decision](council-review.md). The original holdout above is historical evidence, not a new run after interface changes.
