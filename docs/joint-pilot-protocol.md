# Frozen joint-work subscription pilot

Status: completed with recorded execution interruptions and one command-attempt deviation. See the [32-game results and audit](joint-pilot-results.md). The protocol below preserves the decisions made before inference and the authorized resumption amendment.

This diagnostic uses GPT-6 Astra at high reasoning effort through the existing Codex subscription connection. It schedules 32 fresh-context games: eight concealed scenarios crossed with quartermaster/scout roles and shared/individual rewards. Each focal player has three scripted coordinator partners. The station-v2 joint workload uses the extreme 36-round configuration. Physical worlds and partner policies are matched across reward modes; cell order is randomized within each scenario.

The private manifest was frozen at 2026-11-06T06:16:27.476400+00:00. Its SHA-256 commitment is `bff582b8cb3130409f0bda2bdd848fa4cecbbe194c3f8735546b23c5b60a34dd`. Scenario seeds, raw sessions, transcripts, and account/runtime identifiers remain outside Git. The game source fingerprint is `4b134a94f5fa3223a96506b201f3abfd0353af9edbaaba84ef3a6534a07e4300`; engine revisions are shared `27efa3dc48982ff3d5128f8f608321a6e509a468` and individual `c1260e724abba11b1a634cbad3e43383d3fad7cd`.

The first four cells form a balanced interface diagnostic. Pause expansion if at least three crews die or more than 10% of focal decisions are game-invalid. Stop immediately for an information-boundary breach or repeated orchestration failure. Otherwise complete the fixed sample without tuning. Record all scheduled games, including incompletes; do not convert infrastructure failures to game losses.

Primary outcome: paired shared-minus-individual team delivered value, reported separately by role, including zero on death. Report survival, actual focal reward, delivery conditional on survival, work mismatches, invalid decisions, parseable teammate reports, explicit silence, infrastructure failures, and available usage alongside it. Eight scenarios cannot establish a leaderboard.

Matched scripted anchors include the coordinator, local worker, maintenance-only, value-blind allocation, reactive rotating public pairs, silent focal seat, and focal local worker. The public-pair control preserves maintenance communication while ignoring production reports. References are feasible policies, not certified bounds. Check that scripted behavior is identical across reward modes.

## Execution limits and amendments

- Maximum 2,304 submitted game-decision attempts, at most 72 per game. Failed submit attempts count; no implicit retries or replacement games. An envelope is limited to 4,096 bytes in addition to the game's message limits.
- T3 exposes fixed reasoning effort but no enforceable per-request or total token cap for these subscription delegates. The earlier proposed token caps therefore cannot be claimed. Game decisions also differ from provider-internal inference requests. Record exposed usage without inventing missing token counts or dollar estimates. No paid API fallback, account switching, or refresh changes.
- The transport returns newly visible history events once, plus the complete current observation and rules. A history command recovers the full visible history. This preserves information while reducing repeated context. Scripted partners retain their original full observations.
- Players use only their assigned view/submit/history interface. This is a trusted-player instruction boundary with a tool-activity audit, not an operating-system sandbox. They may not inspect source, seeds, evaluator state, or other sessions, and must choose each decision themselves.

Transport checks passed four complete 72-decision validation games, covering both roles and reward modes. Reassembled incremental observations exactly matched the engine's seat-filtered observations at every step; terminal history recovery and the decision cap passed. These were scripted fixtures, not model results. Game source is unchanged from the reviewed 60-test revisions.

Transport SHA-256: `c230feb7441b7ad1c536922a0b1cfd9c68905d6cf8c696ae6a8e6d5393d743c5`. Control runner SHA-256: `4afe3fa0a368af12c1496000a711a49bd100ddd221ee0e7a054336d22a26b686`. The private manifest is the authoritative pre-run assignment record.

## Authorized resumption after the transport interruption

The initial execution stopped after two completed episodes recorded provider network errors. A third affected episode was interrupted by the supervisor at round 22, after 42 accepted decisions. Nine games had completed. Their scores and all runtime failures remain in the record.

The user subsequently requested another attempt. Resume the interrupted episode in its original participant context and saved world, with the same Astra/high/default settings. Do not replay accepted decisions, reset the 72-decision cap, change scenarios or rules, or rerun completed games. This resumed episode must be identified in the final analysis.

Use that continuation as a bounded recovery check. Only after it completes without new infrastructure or information-boundary failures should the remaining 22 frozen assignments proceed, with at most three active participants. A new blocking recovery failure pauses expansion for diagnosis; the original stop criteria apply to new faults after resumption. Historical errors remain included in reliability reporting. This amendment was recorded before resuming inference; it does not erase the original stopping event or turn interrupted runs into clean executions.
