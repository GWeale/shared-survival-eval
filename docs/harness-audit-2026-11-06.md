# Harness attack review — November 6, 2026

Twenty fresh Codex reviewers completed bounded attacks on RL-harness practices and Harbor compatibility. The supported fixes are implemented, and final exported tasks passed actual Harbor execution and plain-file forgery checks. This is same-provider review and bounded integration evidence; it does not establish state-of-the-art model performance or RL learning.

The first fourteen reviewers inspected shared revision `c22e5351f27911cb1fa8e85c4194f14ff96fb31b` and individual revision `8b26dabb58883ef50e9b6ac41827d93fa71b175a`. Later reviewers inspected the integration and fixes. The final runtime checks used shared revision `8368b4473d1a03260a8afc3bf812b535abe8c94d` and individual revision `57a8e08cba7338459e36b08fd4a2246a1a0f76b1`. Subsequent publication changes only documentation; source fingerprints still match those executed revisions.

## Findings and disposition

| Review | Scope | Finding and disposition |
|---|---|---|
| 01 | Harbor contract | Base release had no integration. Added an exporter targeting pinned Harbor schema 1.4; format validation alone is not runtime evidence. |
| 02 | Verifier security | Filesystem-accessible state and saved scores are not safe against hostile shell agents. Added isolated station evidence and clean-verifier replay; native logs remain trusted evaluator files. |
| 03 | RL environment API | Allocation could not be enabled for checkpoint curves; malformed custom scenarios reached terminal crashes. Added complete config support and constructor validation. |
| 04 | Reward math | No arithmetic defect found; expanded regression coverage to all 81 common/private/burn profiles. |
| 05 | Observation privacy | Predictable decision IDs exposed low-range seeds. Replaced them with per-session secrets and seed-free HMAC tokens; constrained focal observations. |
| 06 | Statistics | Record-only coverage missed entire absent pairs. Added schedule-aware summaries. The historical pilot analyzer remains a strict validator for its fixed completed dataset, not a reusable incomplete-pilot analyzer. |
| 07 | Resume integrity | Mutable command files, corrupted records and rewound budgets passed resume. Added executable/declared-artifact hashes, complete preflight replay and budget reconciliation before any new calls. |
| 08 | Concurrency | Curve manifest writes raced; foreign-session tokens collided; interrupted initialization blocked resume. Added whole-curve locking, unique tokens, and preservation of orphan writes in a sibling recovery directory. |
| 09 | Transport | Socket inactivity timeout was not an overall deadline; truncated HTTP and huge usage could abort persistence. HTTP now runs in a deadline-bound child; protocol failures become error episodes and unusable usage remains unknown. |
| 10 | Input fuzzing | Huge probe integers, exponent-overflow JSON and invalid scenarios escaped validation. Added bounded numeric validation and finite JSON parsing. |
| 11 | Generalization | Split namespaces do not prove training exclusion. Reports label that provenance unverified; no automatic training seed schedule or training loop is claimed. |
| 12 | Partner validity | The objective-conditioned policy is myopic against retaliating partners. Clarified this; it is not an optimal repeated-game policy. |
| 13 | Communication | Solo/V1 scripted conventions were undisclosed and failed-run messages were omitted. Disclosed the conventions and count delivered messages in all records. No-message mode still also suppresses offers, so it is not a language-only causal control. |
| 14 | RL practice | Checkpoint weights and training tokens were not captured. Added declared file-digest verification; remote weights, training exclusion, sampled tokens and loss masks remain unverified or unsupported. |
| 15 | Harbor isolation | Replay-tampering probes passed; generated sidecar evidence avoids default agent artifact collisions. Clean-verifier and canonical station-artifact transfer passed actual container trials, including successful ingestion of ordinary forged agent files. |
| 16 | Packaging | Minimal valid Config crashed midway through export. Fixed default handling and atomic staging; official schema and verifier resolution passed. |
| 17 | Trajectories | ATIF is an agent capability distinct from task scoring. Keep game replay separate and never fabricate training tokens. |
| 18 | Regression quality | Corrupt usage and erased calls could bypass resume accounting. Added complete usage/probe schema and call-to-decision reconciliation before execution. |
| 19 | Claims | Keep evaluation, learning, task-format validation and runtime compatibility claims separate. Applied throughout this release. |
| 20 | Container acceptance | Both reward modes completed 12 decisions with accepted reward 1.0 despite successful ingestion of forged agent files. Forged-only incomplete play produced no reward. Final exported resource limits were observed without overrides. |

A preliminary Dockerfile-newline concern was retracted after inspecting the actual export. The arithmetic review found sound per-round bounds; no reward formula was changed. Historical model outcomes remain tied to their original revisions.

## Verification scope

Both packages passed 85 local tests, and both exports passed official schema 1.4 validation. Runtime checks used pinned Harbor 0.25.0, Docker 29.1.3, Compose 2.40.3 and checksum-verified temporary Buildx 0.38.2. Hosted CI is not counted as verification evidence. No model inference, model ranking or RL training was run for this upgrade.

The final acceptance cases used development seed 83 and ordinary forged files containing score 999. Harbor successfully collected those untrusted files in all three cases. It separately collected the canonical station record with a matching source fingerprint and started a fresh verifier.

| Final exported task | Focal decisions | Accepted reward | Observed result |
|---|---:|---:|---|
| Shared oracle plus forged files | 12 | 1.0 | Survived; verifier and host replay agree |
| Individual oracle plus forged files | 12 | 1.0 | Survived; verifier and host replay agree |
| Forged files without play | 0 | None | Incomplete transcript rejected; no reward file |

The main, station and verifier workloads each ran with 1 CPU / 1 GiB limits from the exports, without resource overrides. Harbor's auxiliary egress-control services retain uncapped upstream defaults. Trial containers, networks and temporary Buildx configuration were removed; existing services and shared caches were preserved. Exact revisions and results are in the [acceptance record](harbor-acceptance-2026-11-06.json).

An earlier combined forgery/symlink fixture was insufficient by itself because Docker rejected the escaping symlink before artifact collection completed. The final plain-file cases closed that specific gap. The first runtime attempt also exposed a missing Buildx prerequisite, now documented. Harbor exited zero even when verification rejected incomplete evidence; callers must inspect verifier results and accepted rewards.

This closes the specified integration gates for the pinned version and these fixtures. It is not exhaustive security testing, external certification, a model leaderboard, or proof of training effectiveness.

The research baseline includes Harbor's [pinned task model](https://github.com/harbor-framework/harbor/blob/ff2a1ef48070a8df374669138e4d4db79b77f013/src/harbor/models/task/task.py), [artifact handling](https://github.com/harbor-framework/harbor/blob/ff2a1ef48070a8df374669138e4d4db79b77f013/src/harbor/trial/artifact_handler.py), [ATIF metrics](https://github.com/harbor-framework/harbor/blob/ff2a1ef48070a8df374669138e4d4db79b77f013/src/harbor/models/trajectories/metrics.py), and the earlier [cooperation literature review](release-council-2026-11-06.md). No external certification or exhaustive literature coverage is claimed.
