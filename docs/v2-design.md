# V2 design decisions

The V1 pilot admitted a policy that never repaired or negotiated and still maximized individual cargo in both sampled scenarios. Future benchmark changes must check simple exploit policies before spending model inference. Survival saturation can reflect partner support rather than model capability.

V2 keeps the two reward modes on the same physical simulation. Physical interdependence, private diagnosis/manuals, and deadlines make coordination consequential. Shared resources resolve in announced rotating priority; transferable items settle afterward. Only the environment computes rewards. No LLM judge grades persuasive writing.

Implementation ownership is serial: one engine/policy/runner implementation is mirrored into two independent packages, with explicit tests and repo-specific CLI defaults. Existing V1 records are retained for reproducibility. The shared simulation files must remain byte-identical across repos; only package imports and default eval differ.

Difficulty was developed with validation seeds, then frozen for the 100-scenario scripted check. Test results are evidence, not a request to tune toward a preferred model ordering. No generic intelligence ordering is assumed. The exact repair oracle is deliberately labeled as a restricted subproblem, and a feasible reference policy is not advertised as an optimal solver.

All remote/model calls remain explicit. Runtime state and transcripts stay outside Git. Subscription sessions are coordinated through observation/decision envelopes; they never require API-key conversion. Private state filtering does not provide operating-system isolation.
