"""Example external policy. Replace this policy with your model call."""
import json
import sys

from shared_survival_eval.agents import Baseline

request = json.load(sys.stdin)
reply = Baseline("cooperative", 0).respond(request["observation"], request["phase"])
print(json.dumps(reply.decision))
