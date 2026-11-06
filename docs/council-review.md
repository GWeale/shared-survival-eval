# Five-agent council: benchmark decision

## Decision

All five independent reviewers recommend a bounded model pilot before more difficulty, a leaderboard, or RL training. The lead accepts that direction with two preconditions: make scripted partners' communication convention explicit and add stronger production controls to the pilot. This is agreement among correlated model reviewers across two providers, not proof of benchmark validity.

The panel reviewed shared-survival `233420c02e6dd312df2abc863c678e6102692e77` and individual-incentives `92e2011c3c0e743982ff856d559d293f006af262`. Their repository source was frozen during review. Reviewers worked independently, read-only, and did not see each other's findings. Only Codex and Claude were enabled; the council skill's default third provider was unavailable. Five requested seats were filled across the two available providers.

| Reviewer | Focus | Main recommendation |
|---|---|---|
| GPT-6 Astra | Construct validity | Test reward responsiveness and an information-pooling diagnostic. |
| GPT-6.1 Sol | Incentives | Pair shared/individual rewards with fixed partners and report role-specific effects. |
| Claude Opus 5.5 | Methodology | Disclose the scripted teammate format, add value-blind controls, and start with a small focal pilot. |
| GPT-6.1 Terra | Mechanics | Establish interface reliability and compare simple reactive conventions before scaling. |
| Claude Sonnet 5.5 | Research direction | Establish attainable production and stronger baselines before making capability claims. |

## Material findings checked by the lead

**Private-value reasoning has not been demonstrated.** Opus ran a controller that retained truthful availability, inventory and maintenance reports but assigned every feasible order equal weight when selecting work. On the 100 published development scenarios, mean delivery was 45.55 versus 46.12 for the value-sensitive coordinator. The paired difference was 0.57 with a descriptive 95% bootstrap interval of −0.56 to 1.86. The lead inspected and reran the script, reproducing these results. Both survived all cases. The values were still present in messages; this is a decision-policy ablation, not a test of hiding the information channel. It suggests that this reference policy's gain mainly comes from feasible assignment and synchronization, not valuation optimization. It does not establish that values never matter to other policies.

**The focal-model interface had a real confound.** `work_orders.work_reports` ignores prose, requiring typed inventory, availability, and a complete current-order map. `v2_policies.reports` also requires structured maintenance reports. The player-facing schema only advertised public text. The lead reproduced that the same seat was accepted with a JSON report and ignored with a prose report. Reports permit extra top-level fields; the exact-id requirement applies to the work-order map. A focal model should not have to guess this protocol. The lead added a descriptive `scripted_partner_protocol` to joint discussion requests and removed the obsolete solo-contract instruction from joint-mode commerce rules. No private values or suggested decisions are supplied by that metadata. These fixes do not alter physics or payoffs.

**Survival failures do not isolate production reasoning.** Silent, misleading-partner, and fixed-schedule controls lose the station. Their zero delivery establishes those policies' failure, not the necessity of complex negotiation. The local-worker comparison is more informative about production because both policies survive. Report survival, unconditional delivered value, and delivery conditional on survival together; conditional results alone can introduce survivor selection bias.

**Role contributions and attainable performance are unequal and unresolved.** The engineer production-policy substitution changes nothing in the reported reference runs. That does not mean the engineer contributes nothing: its maintenance role is essential. The reference coordinator is a feasible policy, not an optimal ceiling. The optimistic per-round matching bound ignores maintenance and stock. Surpassing the coordinator is evidence that the reference was suboptimal, not automatic evidence that the environment is too easy.

**Reward and delivered-value metrics can favor different risk choices.** Death receives −1 reward, while certain survival without production receives zero. At successful reward near 0.0525, a hypothetical risky production policy needs approximately 95% survival to outperform certain zero-production maintenance in expected reward. This calculation assumes the successful reward is approximately constant; it is not a measured model threshold. Small reward magnitudes can still discriminate policies. The concern is the risk tradeoff and optimistic denominator, not decimal scale by itself. Report actual reward as well as delivery and survival; specify the acceptable survival tradeoff before any training claim.

**Shared-versus-individual incentive effects remain untested.** Existing scripted policies do not condition their choices on the reward mode. Sol expects meaningful specialization/bargaining conflicts; Sonnet expects incentives to remain substantially aligned because joint work benefits both participants. Neither hypothesis has model evidence. A paired reward-mode experiment can resolve part of this disagreement.

## Chosen next experiment

Run a **32-episode focal-player diagnostic**, not a model ranking:

- One frozen GPT-6 Astra configuration at fixed high effort through the subscription route, with three scripted coordinator partners. No paid API fallback.
- Eight new concealed scenarios, frozen and hashed before execution. Published seeds are development data.
- Two focal roles: quartermaster and scout. Cross both roles with shared versus individual reward on each scenario: 8 × 2 × 2 = 32 games. Hold physical worlds and partner policy fixed. The result will not generalize to engineer/operator roles or all-model crews without follow-up tests.
- Use the reviewed 36-round joint configuration for this diagnostic. Disclose the scripted convention, preserve private observations, isolate episode contexts, and randomize paired execution order.
- Maximum **2,304 model decision requests** (32 × 36 × 2), excluding no-cost scripted decisions. Failed requests count toward the cap; no implicit retries or probes. Also freeze a per-request reasoning/output limit and total token limit. Request count is not a token or money estimate. No pilot has been launched by this council review.
- Run matched scripted anchors: coordinator, local worker, maintenance-only, value-blind allocation, a reactive public-pairing convention, and a silent focal seat. Keep maintenance communication available when ablating production information. These are references, not certified floors or ceilings.

Primary outcome: paired team delivered value, with death scored zero, reported separately by role and reward mode. Also report actual reward, survival, conditional delivery, mismatched work, game-invalid actions, teammate-report parse rate, explicit silence, incomplete episodes, and token/context growth. Distinguish ignored but legal prose from an invalid game action.

Use the first four balanced cells as an infrastructure diagnostic. Stop immediately for leakage or repeated orchestration failure; if three of those games die or invalid game decisions exceed 10%, pause for transcript diagnosis and label the stopped batch exploratory. Do not relabel stopped games as completed zeros or silently discard them. Otherwise finish the frozen sample without tuning. Expand only after reliable execution (at least 90% completed episodes without infrastructure failure), no privacy breach, and outcomes that distinguish interface failure, maintenance failure and production choices. Report paired uncertainty; eight scenarios cannot support a general leaderboard. Do not require a preferred score band or model ordering.

If reward-mode differences remain unresolved, retain that uncertainty and estimate the sample size needed for a larger study. If native communication appears to be the bottleneck, follow with Astra's pooled-current-information condition. If the interface is reliable, the next broader study should include all-model teams and unfamiliar partners. Do not expand all those factors in the first diagnostic.

## Suggestions not adopted

- We did not adopt the proposed normalized `(model - local)/(coordinator - local)` primary score: neither reference is a certified bound and individual scenarios can have zero or reversed denominators.
- We did not adopt requirements that a model fall between 20% and 80% of the reference or below its confidence bound. That would make evaluation acceptance depend on the desired performance band.
- We did not treat a centralized heuristic as a full-game upper bound without a proof of optimality or a valid relaxation.
- We corrected request accounting: with 36 rounds and two phases, a focal episode has at most 72 model decisions and a four-model episode 288, before explicitly budgeted retries/probes. Larger counts suggested by one reviewer were not supported by this interface.
- We did not infer that private values are universally irrelevant, that the engineer has no causal contribution, or that one false diagnosis inevitably kills any possible policy.

## Verification and scope

The lead reran the existing 59-test suite before review. Following the interface corrections, both repositories pass 60 tests, including a regression checking that the convention is disclosed without private data and that solo-mode requests remain unchanged. The lead independently reproduced the value-blind control and the ignored-prose defect. No LLM gameplay evaluation or RL training ran during this council. Source, results and original claims remain available at their audited commits.
