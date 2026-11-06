# Changelog

## 0.4.0 — November 6, 2026

- Add the opt-in allocation-v1 incentive diagnostic, exact payoff certificate and partner cross-play plans.
- Add paired production contrasts, frozen episode schedules, completion coverage and summary identity checks.
- Release killed session locks automatically; serialize concurrent creates/submissions and retain idempotency.
- Bound both command output streams and clean up child processes on timeout or overflow.
- Count distinct invalid decisions separately from invalid field events in V2.
- Preserve checkpoint paired comparisons and plan fingerprints; add public release checks and documentation.

Existing sessions and batch manifests are source-fingerprinted and require their original revision to resume. Use new output directories with 0.4.0. Historical model results remain at their original engine revisions and do not validate new mechanics.
