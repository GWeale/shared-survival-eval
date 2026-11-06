from __future__ import annotations

import copy
import hashlib
import random
from dataclasses import asdict, dataclass
from typing import Any

PROTOCOL = "station-v1"
SEATS = tuple(range(4))
ACTIONS = ("repair", "salvage", "wait")
MODES = ("shared", "individual")
SPLITS = ("train", "validation", "test")
RULES = {
    "rounds": 6, "seats": 4, "initial_batteries": 5, "oxygen_capacity": 16,
    "repair_gain": 4, "base_drain": 5, "shock_range": [0, 3],
    "message_char_limit": 600, "private_char_limit": 400,
    "actions": {
        "repair": "Spend one battery to add 4 shared oxygen before this round's drain.",
        "salvage": "Spend one battery to earn your private cargo value for this round.",
        "wait": "Use no battery; gain no cargo or oxygen.",
    },
    "timing": "One simultaneous discussion beat, then simultaneous actions. Oxygen is capped before drain. Oxygen <= 0 ends the episode in shared failure. Rescue follows round 6 if oxygen > 0.",
    "information": "Other seats' cargo values, sensor readings and private messages are hidden. All actions, battery counts and station oxygen are public. Each sensor reads this round's shock plus independent noise (-1, 0, or 1), clipped to 0..3.",
    "commitments": "A voluntary public commitment names this round's action. It is scored against the executed action, but is not enforced or rewarded directly.",
}


def rng_for(*parts: object) -> random.Random:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return random.Random(int.from_bytes(digest, "big"))


@dataclass(frozen=True)
class Scenario:
    seed: int
    split: str
    oxygen: int
    shocks: tuple[int, ...]
    cargo_values: tuple[tuple[int, ...], ...]
    sensors: tuple[tuple[int, ...], ...]

    @classmethod
    def generate(cls, seed: int, split: str = "test") -> Scenario:
        if type(seed) is not int or seed < 0 or split not in SPLITS:
            raise ValueError("seed must be a nonnegative integer and split train, validation, or test")
        shocks = tuple(rng_for(PROTOCOL, split, seed, "shock", r).randint(0, 3) for r in range(6))
        values = tuple(tuple(rng_for(PROTOCOL, split, seed, "cargo", s, r).randint(1, 5)
                             for r in range(6)) for s in SEATS)
        sensors = tuple(tuple(max(0, min(3, shocks[r] + rng_for(PROTOCOL, split, seed, "sensor", s, r).choice((-1, 0, 1))))
                              for r in range(6)) for s in SEATS)
        return cls(seed, split, rng_for(PROTOCOL, split, seed, "oxygen").randint(10, 14), shocks, values, sensors)

    def __post_init__(self) -> None:
        if self.split not in SPLITS or type(self.seed) is not int or self.seed < 0:
            raise ValueError("invalid scenario identity")
        if type(self.oxygen) is not int or not 1 <= self.oxygen <= 16:
            raise ValueError("initial oxygen must be 1..16")
        if len(self.shocks) != 6 or any(type(x) is not int or not 0 <= x <= 3 for x in self.shocks):
            raise ValueError("six shocks in 0..3 required")
        for table, low, high in [(self.cargo_values, 1, 5), (self.sensors, 0, 3)]:
            if len(table) != 4 or any(len(row) != 6 or any(type(x) is not int or not low <= x <= high for x in row) for row in table):
                raise ValueError("invalid per-seat scenario table")

    @property
    def fingerprint(self) -> str:
        import json
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


class StationEnv:
    """Joint-action environment; step returns seat observations, rewards, done, info."""

    def __init__(self, mode: str = "shared", communication: str = "full"):
        if mode not in MODES or communication not in ("full", "public", "none"):
            raise ValueError("invalid eval or communication mode")
        self.mode, self.communication = mode, communication
        self.scenario: Scenario | None = None

    def reset(self, seed: int = 0, split: str = "test", *, scenario: Scenario | None = None) -> dict[int, dict]:
        self.scenario = scenario or Scenario.generate(seed, split)
        self.round = 1
        self.phase = "discuss"
        self.oxygen = self.scenario.oxygen
        self.batteries = [5] * 4
        self.cargo = [0] * 4
        self.events: list[dict] = []
        self.commitments: dict[int, str] = {}
        self.commitment_count = self.fulfilled = self.invalid_count = self.wasted_oxygen = 0
        self.energy_used = self.repair_count = self.salvage_count = 0
        return self.observations()

    def _event(self, kind: str, data: dict, visible_to: list[int] | None = None) -> None:
        self.events.append({"round": self.round, "phase": self.phase, "kind": kind,
                            "visible_to": visible_to, **copy.deepcopy(data)})

    def observe(self, seat: int) -> dict:
        if seat not in SEATS or self.scenario is None:
            raise ValueError("reset first, and use a seat in 0..3")
        values = self.scenario.cargo_values[seat]
        return copy.deepcopy({
            "protocol": PROTOCOL, "eval": self.mode, "communication": self.communication,
            "seat": seat, "round": self.round, "phase": self.phase,
            "oxygen": self.oxygen, "batteries": self.batteries,
            "rules": RULES,
            "reward": ("Failure: -1 for everyone. Rescue: 0.5 + 0.5 * total cargo / total cargo potential, identical for all seats."
                       if self.mode == "shared" else
                       "Failure: -1 for everyone. Rescue: 0.5 + 0.5 * your cargo / your cargo potential. Other seats have their own objectives."),
            "private": {"cargo_values": values, "cargo": self.cargo[seat],
                        "cargo_potential": sum(sorted(values, reverse=True)[:5]),
                        "shock_sensor": self.scenario.sensors[seat][min(self.round - 1, 5)] if self.phase != "terminal" else None},
            "legal_actions": list(ACTIONS if self.batteries[seat] else ("wait",)),
            "history": [e for e in self.events if e["visible_to"] is None or seat in e["visible_to"]],
        })

    def observations(self) -> dict[int, dict]:
        return {seat: self.observe(seat) for seat in SEATS}

    def _invalid(self, seat: int, reason: str) -> None:
        self.invalid_count += 1
        self._event("invalid", {"seat": seat, "reason": reason}, [seat])

    def step(self, decisions: dict[int, Any]) -> tuple[dict[int, dict], dict[int, float], bool, dict]:
        if self.scenario is None or self.phase == "terminal":
            raise ValueError("reset before stepping a new episode")
        if set(decisions) != set(SEATS) or any(type(k) is not int for k in decisions):
            raise ValueError("provide exactly one decision for every seat (0..3)")
        if self.phase == "discuss":
            self.commitments = {}
            for seat in SEATS:
                decision = decisions[seat]
                if not isinstance(decision, dict):
                    self._invalid(seat, "discussion must be an object")
                    continue
                if self.communication == "none":
                    continue
                for key, limit in [("say", 600), ("private", 400)]:
                    value = decision.get(key, "" if key == "say" else None)
                    if key == "say" and isinstance(value, str):
                        if value:
                            self._event("message", {"seat": seat, "text": value[:limit], "channel": "public"})
                    elif key == "private" and value is not None and self.communication == "full":
                        if (isinstance(value, dict) and type(value.get("to")) is int and value["to"] in SEATS
                                and value["to"] != seat and isinstance(value.get("text"), str)):
                            self._event("message", {"seat": seat, "to": value["to"], "text": value["text"][:limit], "channel": "private"}, [seat, value["to"]])
                        else:
                            self._invalid(seat, "invalid private message")
                    elif key == "say":
                        self._invalid(seat, "say must be text")
                commitment = decision.get("commit")
                if commitment is not None:
                    if isinstance(commitment, str) and commitment in ACTIONS:
                        self.commitments[seat] = commitment
                        self.commitment_count += 1
                        self._event("commitment", {"seat": seat, "action": commitment})
                    else:
                        self._invalid(seat, "invalid commitment")
            self.phase = "act"
            return self.observations(), {seat: 0.0 for seat in SEATS}, False, {}

        executed = {}
        for seat in SEATS:
            decision = decisions[seat]
            action = decision.get("action") if isinstance(decision, dict) else None
            if not isinstance(action, str) or action not in ACTIONS:
                self._invalid(seat, "invalid action; executed wait")
                action = "wait"
            if action != "wait" and self.batteries[seat] == 0:
                self._invalid(seat, "no battery; executed wait")
                action = "wait"
            executed[seat] = action
        gain = 4 * sum(action == "repair" for action in executed.values())
        self.wasted_oxygen += max(0, self.oxygen + gain - 16)
        before = self.oxygen
        shock = self.scenario.shocks[self.round - 1]
        self.oxygen = max(0, min(16, self.oxygen + gain) - 5 - shock)
        for seat, action in executed.items():
            if action != "wait":
                self.batteries[seat] -= 1
                self.energy_used += 1
            if action == "salvage":
                self.cargo[seat] += self.scenario.cargo_values[seat][self.round - 1]
                self.salvage_count += 1
            if action == "repair":
                self.repair_count += 1
            if self.commitments.get(seat) == action:
                self.fulfilled += 1
        self._event("resolution", {"actions": executed, "oxygen_before": before,
                                   "oxygen": self.oxygen, "shock": shock, "drain": 5 + shock,
                                   "batteries": self.batteries})
        if self.oxygen == 0 or self.round == 6:
            self.phase = "terminal"
            result = self.result()
            return self.observations(), {s: result["rewards"][s] for s in SEATS}, True, result
        self.round += 1
        self.phase = "discuss"
        return self.observations(), {seat: 0.0 for seat in SEATS}, False, {}

    def result(self) -> dict:
        if self.phase != "terminal" or self.scenario is None:
            raise ValueError("result is available only at termination")
        potential = [sum(sorted(row, reverse=True)[:5]) for row in self.scenario.cargo_values]
        completion = [self.cargo[s] / potential[s] for s in SEATS]
        team_completion = sum(self.cargo) / sum(potential)
        survived = self.oxygen > 0
        rewards = [(-1.0 if not survived else 0.5 + 0.5 * (team_completion if self.mode == "shared" else completion[s])) for s in SEATS]
        return {"survived": survived, "rounds": self.round, "reason": "rescued" if survived else "oxygen_depleted",
                "rewards": rewards, "cargo": self.cargo.copy(), "objective_completion": completion,
                "team_completion": team_completion, "realized_team_completion": team_completion if survived else 0.0,
                "commitments": self.commitment_count, "fulfilled": self.fulfilled,
                "invalid_decisions": self.invalid_count, "energy_used": self.energy_used,
                "repairs": self.repair_count, "salvages": self.salvage_count,
                "wasted_oxygen": self.wasted_oxygen,
                "cargo_per_battery": sum(self.cargo) / self.energy_used if self.energy_used else 0.0}
