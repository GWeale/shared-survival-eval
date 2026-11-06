import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared_survival_eval.agents import AgentFailure, CallBudget, CommandAgent, ChatAgent, Reply, decode_decision, request_for, validate_config
from shared_survival_eval.engine import StationEnv
from shared_survival_eval.replay import render_replay, seat_record
from shared_survival_eval.runner import parse_probe, run_batch, run_episode, summarize


PLAN = {"agents": {"a": {"type": "baseline", "name": "cooperative"}, "b": {"type": "baseline", "name": "selfish"}},
        "crews": {"mixed": ["b", "a", "a", "a"]}}


class RunnerTests(unittest.TestCase):
    def test_rotated_assignments_and_paired_worlds(self):
        records = [run_episode(PLAN, "mixed", mode, 9, rotation=rotation) for mode in ("shared", "individual") for rotation in range(4)]
        self.assertEqual({r["scenario_hash"] for r in records}, {records[0]["scenario_hash"]})
        self.assertEqual([r["assignment"].index("b") for r in records[:4]], [0, 1, 2, 3])
        summary = summarize(records)
        self.assertEqual(summary["paired_comparisons"][0]["complete_pairs"], 4)
        self.assertIsNone(summary["paired_comparisons"][0]["ci95"])

    def test_probes_do_not_change_observations_actions_or_results(self):
        plain = run_episode(PLAN, "mixed", "individual", 5)
        probed = run_episode(PLAN, "mixed", "individual", 5, probes=True)
        for field in ("frames", "result", "events"):
            self.assertEqual(plain[field], probed[field])
        self.assertEqual(len(probed["probes"]), probed["result"]["rounds"] * 4)
        self.assertTrue(all(0 <= p["survival_brier"] <= 1 for p in probed["probes"]))

    def test_bad_probes_are_counted(self):
        self.assertIsNone(parse_probe({"survival": float("nan"), "repairs": {str(s): 0.5 for s in range(4)}}))
        self.assertIsNone(parse_probe({"survival": 1, "repairs": {}}))
        self.assertIsNone(decode_decision('{"action":"wait","bad":NaN}'))
        for value in ([], 4, None):
            with self.assertRaises(ValueError):
                validate_config({"type": "chat", "model": "test", "base_url": value})

    def test_budget_failure_is_not_a_game_loss(self):
        record = run_episode(PLAN, "mixed", "shared", 0, budget=CallBudget(2))
        self.assertEqual(record["status"], "error")
        self.assertNotIn("result", record)
        self.assertEqual(record["attempted_calls"], 2)
        self.assertEqual(set(record["frames"][0]["decisions"]), {0, 1})
        row = summarize([record])["rows"][0]
        self.assertEqual(row["errors"], 1)
        self.assertIsNone(row["metrics"]["survival_rate"]["mean"])

    def test_resume_is_no_op_and_rejects_changed_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "batch"
            first = run_batch(PLAN, out, [0, 1], rotations=1, max_calls=500)
            paths = list((out / "episodes").glob("*.json"))
            timestamps = {p.name: p.stat().st_mtime_ns for p in paths}
            with patch("shared_survival_eval.runner.run_episode", side_effect=AssertionError("must not run")):
                second = run_batch(PLAN, out, [0, 1], rotations=1, max_calls=500, resume=True)
            self.assertEqual(first, second)
            self.assertEqual(timestamps, {p.name: p.stat().st_mtime_ns for p in paths})
            with self.assertRaisesRegex(ValueError, "manifest differs"):
                run_batch(PLAN, out, [0, 1], rotations=1, max_calls=500, communication="none", resume=True)
            self.assertTrue((out / ".run.lock").exists())

    def test_concurrent_writer_and_nonempty_directory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            from shared_survival_eval.session_lock import locked
            with locked(out / ".run.lock"):
                with self.assertRaisesRegex(ValueError, "locked"):
                    run_batch(PLAN, out, [0])
            (out / "unrelated").write_text("keep")
            with self.assertRaisesRegex(ValueError, "empty"):
                run_batch(PLAN, out, [0])
            self.assertEqual((out / "unrelated").read_text(), "keep")

    def test_budget_is_total_across_resumption(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            run_batch(PLAN, out, [0], rotations=1, max_calls=3)
            self.assertEqual(json.loads((out / "budget.json").read_text())["attempted_calls"], 3)
            summary = run_batch(PLAN, out, [0], rotations=1, max_calls=3, resume=True)
            self.assertEqual(sum(r["usage"]["attempted_calls"] for r in summary["rows"]), 3)
            self.assertEqual(sum(r["errors"] for r in summary["rows"]), 2)

    def test_external_requires_opt_in(self):
        plan = {"agents": {"external": {"type": "command", "argv": [sys.executable, "-c", "print('{}')"]}},
                "crews": {"external": ["external"] * 4}}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "enable-external"):
                run_batch(plan, Path(tmp), [0])

    def test_command_agent_real_process_contract(self):
        command = [sys.executable, "-c", "import json,sys; r=json.load(sys.stdin); print(json.dumps({'action':'repair' if r['observation']['seat']==2 else 'wait'}))"]
        obs = StationEnv().reset()[2]
        self.assertEqual(CommandAgent(command).respond(obs, "act").decision, {"action": "repair"})
        with self.assertRaises(AgentFailure):
            CommandAgent([sys.executable, "-c", "import time;time.sleep(1)"], timeout=0.01).respond(obs, "act")
        self.assertIsNone(CommandAgent([sys.executable, "-c", "print('not-json')"]).respond(obs, "act").decision)
        with self.assertRaises(ValueError):
            CommandAgent("python3")

    def test_command_agent_episode_through_public_cli(self):
        plan = {"agents": {"cmd": {"type": "command", "argv": [sys.executable, "-m", "examples.command_agent"]}}, "crews": {"cmd": ["cmd"] * 4}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "plan.json").write_text(json.dumps(plan))
            result = subprocess.run([sys.executable, "-m", "shared_survival_eval", "run", "--plan", str(path / "plan.json"),
                                     "--out", str(path / "run"), "--seeds", "1", "--rotations", "1", "--eval", "both", "--enable-external", "--max-calls", "100"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((path / "run/summary.json").read_text())
            self.assertEqual(len(summary["rows"]), 2)
            self.assertTrue(all(r["metrics"]["survival_rate"]["mean"] == 1 for r in summary["rows"]))
            self.assertEqual(json.loads((path / "run/budget.json").read_text())["attempted_calls"], 96)

    def test_http_payload_is_only_seat_observation_and_env_key_not_logged(self):
        observed = {}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit):
                return json.dumps({"choices": [{"message": {"content": '{"action":"repair"}'}}], "usage": {"prompt_tokens": 30, "completion_tokens": 7}}).encode()
        class Opener:
            def open(self, request, timeout):
                observed["body"] = json.loads(request.data)
                observed["auth"] = request.get_header("Authorization")
                return Response()
        env = StationEnv()
        obs = env.reset()[1]
        with patch("urllib.request.build_opener", return_value=Opener()), patch.dict(os.environ, {"TEST_MODEL_KEY": "test-only-placeholder"}):
            reply = ChatAgent({"model": "fixture", "api_key_env": "TEST_MODEL_KEY"}).respond(obs, "act")
        self.assertEqual(reply.decision, {"action": "repair"})
        self.assertEqual(reply.input_tokens, 30)
        self.assertEqual(reply.output_tokens, 7)
        self.assertEqual(json.loads(observed["body"]["messages"][1]["content"]), json.loads(json.dumps(request_for(obs, "act"))))
        self.assertNotIn("test-only-placeholder", json.dumps(observed["body"]))

    def test_seat_export_removes_hidden_data_not_just_ui_elements(self):
        record = run_episode(PLAN, "mixed", "shared", 5, probes=True)
        record["scenario"]["private_marker"] = "hidden-scenario"
        for frame in record["frames"]:
            frame["observations"][2]["private"]["marker"] = "hidden-seat-two"
        record["events"].append({"kind": "message", "visible_to": [1, 2], "text": "hidden-message"})
        record["events"].append({"kind": "message", "visible_to": None, "text": "visible-message"})
        redacted = seat_record(record, 0)
        serialized = json.dumps(redacted)
        for secret in ("hidden-scenario", "hidden-seat-two", "hidden-message", '"scenario_hash"', '"seed"'):
            self.assertNotIn(secret, serialized)
        self.assertIn("visible-message", serialized)
        self.assertEqual({p["seat"] for p in redacted["probes"]}, {0})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "replay.html"
            render_replay(record, path, seat=0)
            self.assertNotIn("hidden-seat-two", path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_same_phase_requests_do_not_receive_others_submissions(self):
        seen = []
        class SpyAgent:
            def respond(self, obs, phase):
                seen.append(copy.deepcopy(obs))
                if phase == "discuss":
                    return Reply({"say": f"r{obs['round']}-s{obs['seat']}", "private": {"to": (obs["seat"] + 1) % 4, "text": "private"}})
                return Reply({"action": "repair"})
        with patch("shared_survival_eval.runner.make_agent", return_value=SpyAgent()):
            run_episode(PLAN, "mixed", "shared", 0)
        for obs in seen:
            current = [e for e in obs["history"] if e["round"] == obs["round"]]
            if obs["phase"] == "discuss":
                self.assertEqual(current, [])
            else:
                self.assertEqual(len([e for e in current if e["kind"] == "message" and e["channel"] == "public"]), 4)
                self.assertEqual(len([e for e in current if e["kind"] == "message" and e["channel"] == "private"]), 2)
                self.assertFalse(any(e["kind"] == "resolution" for e in current))

    def test_replay_escapes_script_injection(self):
        record = run_episode(PLAN, "mixed", "shared", 0)
        record["events"].append({"kind": "message", "visible_to": None, "text": "</script><script>alert('bad')</script>"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "replay.html"
            render_replay(record, path)
            self.assertNotIn("</script><script>alert", path.read_text())
            self.assertIn("\\u003c/script>", path.read_text())


if __name__ == "__main__":
    unittest.main()
