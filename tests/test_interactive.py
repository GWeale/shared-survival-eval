import json
import tempfile
import unittest
from pathlib import Path

from shared_survival_eval.agents import Baseline
from shared_survival_eval.interactive import create, export_record, submit
from shared_survival_eval.runner import run_episode


class InteractiveTests(unittest.TestCase):
    def test_interactive_matches_batch_and_hides_other_seats(self):
        for mode in ("shared", "individual"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "state.json"
                request = create(path, mode=mode, seed=41, seat=2, model="scripted-check")
                while not request["done"]:
                    obs = request["observation"]
                    self.assertEqual(obs["seat"], 2)
                    self.assertNotIn("seed", obs)
                    self.assertNotIn("scenario", request)
                    decision = Baseline("cooperative", 0).respond(obs, obs["phase"]).decision
                    request = submit(path, {"decision_id": request["decision_id"], "decision": decision})
                record = export_record(path)
                plan = {"agents": {"c": {"type": "baseline", "name": "cooperative"}},
                        "crews": {"c": ["c"] * 4}}
                batch = run_episode(plan, "c", mode, 41)
                self.assertEqual(record["result"], batch["result"])
                self.assertEqual(record["events"], batch["events"])
                self.assertEqual(len(record["frames"]), 13)

    def test_retry_is_idempotent_and_cannot_revise_or_skip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            request = create(path, mode="individual", seed=1, seat=0, model="test")
            envelope = {"decision_id": request["decision_id"], "decision": {"say": "Ready"}}
            after = submit(path, envelope)
            self.assertEqual(submit(path, envelope), after)
            self.assertEqual(len(json.loads(path.read_text())["submissions"]), 1)
            with self.assertRaisesRegex(ValueError, "cannot change"):
                submit(path, {**envelope, "decision": {"say": "Changed"}})
            with self.assertRaisesRegex(ValueError, "incorrect"):
                submit(path, {**envelope, "decision_id": "missing"})

    def test_illegal_model_action_is_scored_not_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            request = create(path, mode="shared", seed=1, seat=0, model="test")
            request = submit(path, {"decision_id": request["decision_id"], "decision": {}})
            request = submit(path, {"decision_id": request["decision_id"], "decision": {"action": "cheat"}})
            record = export_record(path)
            self.assertEqual(record["events"][-1]["actions"][0], "wait")
            self.assertEqual(sum(e["kind"] == "invalid" for e in record["events"]), 1)


if __name__ == "__main__":
    unittest.main()
