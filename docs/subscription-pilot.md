# Interactive subscription pilot

The interactive interface lets a trusted coding-agent session play one seat through its existing subscription. It does not call a model API or manage authentication. A supervisor creates a session, starts a fresh model context for that episode, and collects the recorded outcome.

## Protocol

The supervisor imports `shared_survival_eval.interactive.create` and supplies an outside-repository state path, mode, seed, seat, and model ID. Players receive only the output of:

```sh
python3 -m shared_survival_eval.interactive view /private/path/session.json
```

For each request, the player submits an envelope on standard input:

```sh
python3 -m shared_survival_eval.interactive submit /private/path/session.json <<'JSON'
{"decision_id":"ID_FROM_REQUEST","decision":{"action":"repair"}}
JSON
```

Discussion uses the discussion schema in the request. Keep submitting decisions until `done` is true. A repeated identical envelope is idempotent; changing an accepted decision or skipping a phase is rejected. Invalid game actions count as violations and execute as wait. Three cooperative scripted peers act from their own observations simultaneously with the focal player.

The state file and `export_record` output are evaluator-only data. Players must not read source, raw state, other sessions, seeds, or evaluator records. The CLI filters observations; it does not create an operating-system sandbox. Use this with trusted participants, audit their tool activity, and do not claim adversarial isolation. One writer owns each session file. Source changes invalidate existing sessions.

## First pilot design

- Models: `gpt-6-luna`, `gpt-6.1-terra`, `gpt-6-astra`, `gpt-6.1-sol`.
- Codex provider, ChatGPT sign-in, high reasoning effort, default service tier.
- Both reward modes, full communication, two matched scenarios per model per mode.
- Scenario A: test seed 20261105, focal seat 0. Scenario B: test seed 20261106, focal seat 2.
- Fresh model context for every episode; no prediction probes, model training, or retry after a game loss.
- Six rounds maximum, two decisions per round: at most 192 focal decisions across 16 games.
- Report every scheduled game, including execution failures. Outcomes use completed games only; show completion counts separately.
- Primary metrics: survival and focal reward. Also report realized team cargo, realized focal cargo, and focal repairs. Failed survival makes realized cargo zero.

This is an initial test of one model player with fixed peers. Two scenarios cannot support a capability ranking or a stable uncertainty interval. Seat and scenario vary together; comparisons are matched across models, but do not estimate seat effects independently. Coding-agent system instructions, tool use, and conversation memory are part of the evaluated setup. Subscription usage is not zero cost; token billing and limits must not be inferred from missing usage data. No paid API fallback is allowed for this pilot.

Raw prompts, transcripts, state, and orchestration identifiers stay outside Git. Publish only sanitized outcomes, source fingerprints, methodology, and aggregate charts after the run is audited.
