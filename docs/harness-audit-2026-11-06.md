# Harness attack review — November 6, 2026

The owner requested twenty independent attacks on RL-harness practices and Harbor compatibility. Twenty fresh Codex reviewers have completed bounded reviews. The container review found a missing Buildx prerequisite. A task-scoped Buildx continuation then passed the four prepared runtime cases; a plain-file forgery follow-up remains pending because Docker rejected the combined fixture's symlink before collecting its forged files. The first fourteen reviewed shared revision `c22e5351f27911cb1fa8e85c4194f14ff96fb31b` and individual revision `8b26dabb58883ef50e9b6ac41827d93fa71b175a`. Later reviewers inspected the new integration and fixes. This is same-provider review, not twenty independent empirical experiments or a SOTA result.

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
| 15 | Harbor isolation | Replay-tampering probes passed; generated sidecar evidence avoids default agent artifact collisions. Clean-verifier and canonical station-artifact transfer passed actual container trials; plain forged-file ingestion is being checked separately. |
| 16 | Packaging | Minimal valid Config crashed midway through export. Fixed default handling and atomic staging; official schema and verifier resolution passed. |
| 17 | Trajectories | ATIF is an agent capability distinct from task scoring. Keep game replay separate and never fabricate training tokens. |
| 18 | Regression quality | Corrupt usage and erased calls could bypass resume accounting. Added complete usage/probe schema and call-to-decision reconciliation before execution. |
| 19 | Claims | Keep evaluation, learning, task-format validation and runtime compatibility claims separate. Applied throughout this release. |
| 20 | Container acceptance | Both reward-mode oracles and combined forgery plus genuine play completed 12 decisions with accepted reward 1.0. Forged-only incomplete play produced no reward. Docker rejected the escaping symlink; plain forged-file ingestion remains a separate follow-up. |

A preliminary Dockerfile-newline concern was retracted after inspecting the actual export. The arithmetic review found sound per-round bounds; no reward formula was changed. Historical model outcomes remain tied to their original revisions.

## Verification scope

Local regression suites and upstream schema validation cover the implementation. Hosted CI is not counted as verification evidence. No model inference, model ranking or RL training was run for this upgrade. Both packages passed 85 local tests. Runtime trials used Docker 29.1.3, Compose 2.40.3, checksum-verified temporary Buildx 0.38.2 and pinned Harbor 0.25.0. Four separate verifiers ran and collected matching canonical station records. Three genuine-play cases earned the expected 1.0; zero-decision evidence failed with `invalid transcript length` and no accepted reward. Harbor still exited zero for that verifier failure: inspect verifier results rather than CLI status. The first four cases used a run-level station resource limit; the exporter now declares the same 1 CPU / 1 GiB limit itself. Final-export and plain-file forgery validation remain pending. This is bounded integration evidence, not general security certification.

The research baseline includes Harbor's [pinned task model](https://github.com/harbor-framework/harbor/blob/ff2a1ef48070a8df374669138e4d4db79b77f013/src/harbor/models/task/task.py), [artifact handling](https://github.com/harbor-framework/harbor/blob/ff2a1ef48070a8df374669138e4d4db79b77f013/src/harbor/trial/artifact_handler.py), [ATIF metrics](https://github.com/harbor-framework/harbor/blob/ff2a1ef48070a8df374669138e4d4db79b77f013/src/harbor/models/trajectories/metrics.py), and the earlier [cooperation literature review](release-council-2026-11-06.md). No external certification or exhaustive literature coverage is claimed.
