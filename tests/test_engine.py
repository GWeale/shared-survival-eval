import copy
import unittest

from shared_survival_eval import Scenario, StationEnv
from shared_survival_eval.agents import Baseline


class EngineTests(unittest.TestCase):
    def scenario(self, shocks=(0,) * 6):
        return Scenario(0, "test", 10, shocks, ((1, 2, 3, 4, 5, 1),) * 4, (shocks,) * 4)

    def test_exact_resource_resolution_and_shared_failure(self):
        env = StationEnv()
        env.reset(scenario=self.scenario())
        env.step({s: {} for s in range(4)})
        observations, rewards, done, _ = env.step({0: {"action": "repair"}, 1: {"action": "salvage"}, 2: {"action": "wait"}, 3: {"action": "wait"}})
        self.assertEqual(observations[0]["oxygen"], 9)
        self.assertEqual(observations[0]["batteries"], [4, 4, 5, 5])
        self.assertEqual(observations[1]["private"]["cargo"], 1)
        self.assertEqual(list(rewards.values()), [0] * 4)
        self.assertFalse(done)
        for _ in range(2):
            env.step({s: {} for s in range(4)})
            _, rewards, done, result = env.step({s: {"action": "wait"} for s in range(4)})
        self.assertTrue(done)
        self.assertEqual(result["reason"], "oxygen_depleted")
        self.assertEqual(list(rewards.values()), [-1] * 4)
        with self.assertRaises(ValueError):
            env.step({s: {} for s in range(4)})

    def test_messages_objectives_and_invalid_feedback_are_private(self):
        env = StationEnv()
        initial = env.reset()
        self.assertNotIn("scenario", initial[0])
        self.assertNotIn("seed", initial[0])
        initial[0]["batteries"][0] = -100
        self.assertEqual(env.observe(0)["batteries"][0], 5)
        obs, *_ = env.step({0: {"say": "public", "private": {"to": 1, "text": "secret-value"}},
                            1: {}, 2: {"private": {"to": 2, "text": "bad"}}, 3: {}})
        self.assertIn("secret-value", str(obs[0]["history"]))
        self.assertIn("secret-value", str(obs[1]["history"]))
        self.assertNotIn("secret-value", str(obs[2]))
        self.assertNotIn("secret-value", str(obs[3]))
        self.assertNotIn("invalid", str(obs[3]["history"]))
        self.assertEqual(len(obs[2]["history"]), 2)

    def test_submission_order_cannot_change_joint_result(self):
        a, b = StationEnv(), StationEnv()
        a.reset(44)
        b.reset(44)
        talk = {s: {"say": f"seat {s}"} for s in range(4)}
        self.assertEqual(a.step(talk), b.step(dict(reversed(list(talk.items())))))
        moves = {s: {"action": "repair" if s < 2 else "salvage"} for s in range(4)}
        self.assertEqual(a.step(moves), b.step(dict(reversed(list(moves.items())))))

    def test_modes_change_only_reward_for_same_actions(self):
        a, b = StationEnv("shared"), StationEnv("individual")
        a.reset(11)
        b.reset(11)
        while a.phase != "terminal":
            if a.phase == "discuss":
                decisions = {s: {} for s in range(4)}
            else:
                decisions = {s: Baseline("cooperative", 0).respond(a.observe(s), "act").decision for s in range(4)}
            a.step(copy.deepcopy(decisions))
            b.step(copy.deepcopy(decisions))
        self.assertEqual(a.events, b.events)
        self.assertEqual(a.result()["cargo"], b.result()["cargo"])
        self.assertEqual(len(set(a.result()["rewards"])), 1)
        self.assertGreater(len(set(b.result()["rewards"])), 1)

    def test_terminal_rewards_match_hand_calculated_objectives(self):
        actions = [
            ["repair", "repair", "salvage", "salvage"],
            ["salvage", "salvage", "repair", "repair"],
            ["repair", "repair", "salvage", "salvage"],
            ["salvage", "salvage", "repair", "repair"],
            ["repair", "repair", "wait", "wait"],
            ["wait", "wait", "repair", "repair"],
        ]
        for mode in ("shared", "individual"):
            env = StationEnv(mode)
            env.reset(scenario=self.scenario())
            for moves in actions:
                env.step({s: {} for s in range(4)})
                _, rewards, done, result = env.step({s: {"action": moves[s]} for s in range(4)})
            self.assertTrue(done)
            self.assertTrue(result["survived"])
            self.assertEqual(result["cargo"], [6, 6, 4, 4])
            expected = [2 / 3] * 4 if mode == "shared" else [0.7, 0.7, 19 / 30, 19 / 30]
            for seat in range(4):
                self.assertAlmostEqual(rewards[seat], expected[seat])

    def test_actions_cannot_change_future_shocks(self):
        a, b = StationEnv(), StationEnv()
        a.reset(10)
        b.reset(10)
        for _ in range(3):
            for env in (a, b):
                env.step({s: {} for s in range(4)})
            a.step({s: {"action": "repair"} for s in range(4)})
            b.step({s: {"action": "repair" if s < 2 else "salvage"} for s in range(4)})
            self.assertEqual(a.events[-1]["shock"], b.events[-1]["shock"])

    def test_coordinated_rescue_and_selfish_failure(self):
        for seed in range(30):
            for policy, expected in [("cooperative", True), ("selfish", False)]:
                env = StationEnv()
                env.reset(seed)
                while env.phase != "terminal":
                    env.step({s: Baseline(policy, seed).respond(env.observe(s), env.phase).decision for s in range(4)})
                self.assertEqual(env.result()["survived"], expected, (seed, policy))
                if expected:
                    self.assertEqual(env.result()["rounds"], 6)
                self.assertTrue(all(0 <= b <= 5 for b in env.batteries))
                self.assertTrue(all(0 <= c <= 1 for c in env.result()["objective_completion"]))

    def test_ablation_drops_private_messages_and_commitments(self):
        for mode, count in [("full", 3), ("public", 2), ("none", 0)]:
            env = StationEnv(communication=mode)
            env.reset()
            env.step({0: {"say": "a", "commit": "repair", "private": {"to": 1, "text": "b"}}, 1: {}, 2: {}, 3: {}})
            self.assertEqual(len(env.observe(0)["history"]), count)

    def test_malformed_actions_wait_and_commitments_follow_executed_action(self):
        env = StationEnv()
        env.reset()
        env.step({s: {"commit": "repair"} for s in range(4)})
        env.step({0: {"action": ["repair"]}, 1: None, 2: {"action": "repair"}, 3: {"action": "repair"}})
        self.assertEqual(env.observe(0)["batteries"], [5, 5, 4, 4])
        self.assertEqual(env.fulfilled, 2)
        self.assertEqual(env.invalid_count, 2)

    def test_splits_and_resets(self):
        self.assertEqual(Scenario.generate(8), Scenario.generate(8))
        self.assertNotEqual(Scenario.generate(8, "train"), Scenario.generate(8, "test"))
        env = StationEnv()
        initial = env.reset(5)
        env.step({s: {"say": "hello"} for s in range(4)})
        self.assertEqual(env.reset(5), initial)
        with self.assertRaises(ValueError):
            Scenario.generate(-1)
        with self.assertRaises(ValueError):
            env.step({0: {}, 1: {}})


if __name__ == "__main__":
    unittest.main()
