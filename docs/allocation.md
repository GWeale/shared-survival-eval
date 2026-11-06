# Certified incentive diagnostic

Version 0.4 adds opt-in `allocation-v1` alongside the existing joint-work station. Every seat receives one independent production token each action round, including an engineer occupied by a repair. Choose `"allocation":"common"` or `"allocation":"private"` in addition to the usual station action. Tokens cannot be transferred, stored or spent twice. An omitted or invalid allocation burns that round's token and counts as an invalid decision.

Private allocation gives its owner 4 allocation points. Common allocation gives each of the four seats 2 points. Settlement is simultaneous; pending choices are hidden. Allocation never consumes power, maintenance components or ordinary cargo. Resolved profiles and payoffs are public, so partners can reciprocate or change behavior over time.

| Profile for one round | Focal payoff | Crew payoff |
|---|---:|---:|
| Everyone contributes | 8 | 32 |
| Focal keeps its token; three others contribute | 10 | 28 |
| Everyone keeps their token | 4 | 16 |

Against any fixed choices by the other three players, switching from common to private increases the focal payoff by exactly 2 and decreases crew payoff by exactly 4. The certificate exhausts all 16 binary profiles and all seats. This establishes a genuine individual/team incentive conflict. It is a simple diagnostic, not a claim of frontier difficulty or a full-station optimum.

Death still gives −1. On rescue, shared reward is crew allocation points divided by `32 × scheduled rounds`; individual reward is own allocation points divided by `10 × scheduled rounds`. Rewards arrive only at termination. Ordinary station cargo remains separately reported and does not enter this opt-in diagnostic reward. Use `allocation_delivered_value` and `shared_minus_individual_allocation_delivery` for this task; ordinary `delivered_value` still means station cargo. All denominators are fixed in advance, shared across roles, and have certified bounds for this production game.

## Run and inspect

```sh
python3 -m shared_survival_eval v2 allocation-certificate
python3 -m shared_survival_eval v2 run \
  --plan examples/allocation-crossplay.json --out ../runs/allocation \
  --workload joint --allocation --difficulty extreme \
  --seeds 4 --seed-start 1000 --rotations 4 --repeats 2 --eval both
```

For a private interactive session, add `--allocation --workload joint` to `v2 session-create` and choose an allocation-compatible scripted background, such as `--background allocation_common`. All-model crews can use the existing simultaneous multi-seat session API. Player decisions must come through seat-filtered observations; the evaluator's state file is not player input.

`allocation_objective` contributes under shared reward and keeps under individual reward. Other controls contribute, keep, reciprocate the preceding partners' behavior, periodically forgive, or switch from common to private halfway through the episode. Their life-support controller is the same joint coordinator. These are observation-only scripts with no seed, future-state or partner-policy access. Their prescribed responses verify incentive sensitivity; they are not model evidence.

The cross-play plan places the objective-aware focal agent in each of four roles against each of five partner types. The manifest enumerates every reward mode, crew, world, rotation, replicate and seat assignment before execution. The development plan uses only common/private partners. A future learned policy can reserve reciprocal/forgiving/switch partners for evaluation, provided it did not encounter those policies during training. Published example seeds and partners are development material; the examples do not establish unseen-partner generalization on their own. Repeating a deterministic baseline verifies scheduling and does not create independent samples.

## Interpretation and recovery

Reports retain completion coverage, unfinished/error cases, conditional and unconditional cargo delivery, paired reward-mode contrasts, role rotations, communication characters and reported model usage. An error is not a simulated death. Token totals stay null when incomplete or unavailable; character counts are not provider token counts. Duplicate episode identities and incompatible split/configuration/communication mixes are rejected.

Session and batch locks use POSIX advisory locking. A killed writer releases its kernel lock; the persistent `.lock` file is normal and should not be deleted while another process may use it. Session creation and writes are serialized. Resubmitting the exact accepted envelope is idempotent; changing accepted input is rejected. Atomic writes flush the file and parent directory. These checks cover local process interruption, not a proof of durability on every storage system.

Batch `--resume` preserves saved episodes, error records and the total call budget. An interrupted episode without a saved result can be rerun from its beginning; previously charged external calls remain charged and appear as attempts without an episode record. This is conservative budget recovery, not exactly-once remote inference. Failed shell commands that never invoke the harness cannot be charged by its internal cap. No fresh subscription reliability pilot has run after these changes; the historical 81.25% clean-execution result remains unchanged.

Command adapters cap each output stream at 100,000 bytes while reading and terminate their own process group on completion, timeout or overflow. This bounds captured output, not the child process's total memory or access privileges. CLI execution currently requires Linux or macOS (POSIX); Windows support and adversarial sandboxing are not claimed.

## Recorded engineering checks

The [release check artifact](allocation-checks.json) records 320 completed scripted episodes across four development worlds, all four focal roles, five partner types, two reward modes and two deterministic repeats. All survived with zero invalid decisions and equal production opportunities; every paired objective comparison preserved ordinary station cargo. Final-source recomputation matched all recorded terminal results and event histories. These checks validate scheduling and mechanics, not model cooperation or independent statistical sample size.

## What remains unvalidated

This release does not establish model ranking, RL learning, robust negotiation, or temporal planning difficulty. Bankable tokens, time-varying returns and deadlines need an exact small-horizon oracle and a case where foresight outperforms a myopic policy before inclusion. Information-pooling and production-value removal need separate visibility tests; public messaging is not a pooled-private-information condition. See the [research and council decisions](release-council-2026-11-06.md) and the unchanged [Astra pilot](joint-pilot-results.md).
