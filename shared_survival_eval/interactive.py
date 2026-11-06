"""A durable focal-player session for a trusted interactive model harness.

The CLI returns only that player's observation. The state file is evaluator data,
not player input. This is an information boundary, not an OS security sandbox.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

from .agents import Baseline, request_for
from .engine import PROTOCOL, SEATS, StationEnv
from .runner import atomic_json, source_hash


def create(path: Path, *, mode: str, seed: int, seat: int, model: str) -> dict:
    if path.exists():
        raise ValueError("session already exists")
    if type(seat) is not int or seat not in SEATS:
        raise ValueError("seat must be 0..3")
    env = StationEnv(mode)
    env.reset(seed, "test")
    state = {"format": "focal-session-v1", "mode": mode, "seed": seed,
             "split": "test", "seat": seat, "model": model,
             "source_hash": source_hash(), "submissions": []}
    atomic_json(path, state)
    return view(state, env)


def restore(state: dict) -> StationEnv:
    if state["source_hash"] != source_hash():
        raise ValueError("source changed since session creation")
    env = StationEnv(state["mode"])
    env.reset(state["seed"], state["split"])
    for item in state["submissions"]:
        env.step({int(s): d for s, d in item["decisions"].items()})
    return env


def decision_id(state: dict, env: StationEnv) -> str:
    # Opaque, stable IDs allow a retry without advancing a second time.
    value = [state["model"], state["mode"], state["seed"], state["seat"],
             env.round, env.phase, state["source_hash"]]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()[:24]


def view(state: dict, env: StationEnv) -> dict:
    seat = state["seat"]
    if env.phase == "terminal":
        result = env.result()
        return {"done": True, "survived": result["survived"],
                "reward": result["rewards"][seat],
                "objective_completion": result["objective_completion"][seat],
                "team_completion": result["team_completion"]}
    return {"done": False, "decision_id": decision_id(state, env),
            **request_for(env.observe(seat), env.phase)}


def submit(path: Path, envelope: dict) -> dict:
    state = json.loads(path.read_text())
    env = restore(state)
    if not isinstance(envelope, dict) or set(envelope) != {"decision_id", "decision"}:
        raise ValueError("submit requires decision_id and decision")
    for prior in state["submissions"]:
        if prior["decision_id"] == envelope["decision_id"]:
            if prior["decision"] != envelope["decision"]:
                raise ValueError("cannot change a submitted decision")
            return view(state, env)
    if env.phase == "terminal" or envelope["decision_id"] != decision_id(state, env):
        raise ValueError("stale or incorrect decision_id")
    # All players decide from observations before this simultaneous phase.
    decisions = {s: (envelope["decision"] if s == state["seat"] else
                     Baseline("cooperative", 0).respond(env.observe(s), env.phase).decision)
                 for s in SEATS}
    item = {**envelope, "round": env.round, "phase": env.phase, "decisions": decisions}
    env.step(decisions)
    state["submissions"].append(item)
    atomic_json(path, state)
    return view(state, env)


def export_record(path: Path) -> dict:
    """Evaluator-only replay export. Never supply this record to a player."""
    state = json.loads(path.read_text())
    restore(state)  # Validate source identity before export.
    env = StationEnv(state["mode"])
    observations = env.reset(state["seed"], state["split"])
    assignment = [state["model"] if s == state["seat"] else "cooperative" for s in SEATS]
    record = {"protocol": PROTOCOL, "eval": state["mode"], "crew": state["model"],
              "assignment": assignment, "seed": state["seed"], "split": state["split"],
              "rotation": state["seat"], "replicate": 0, "communication": "full",
              "scenario_hash": env.scenario.fingerprint, "source_hash": state["source_hash"],
              "harness": "interactive-focal-v1", "frames": [], "calls": [], "probes": []}
    for item in state["submissions"]:
        decisions = {int(s): d for s, d in item["decisions"].items()}
        record["frames"].append({"round": env.round, "phase": env.phase,
                                 "observations": copy.deepcopy(observations), "decisions": decisions})
        for s in SEATS:
            record["calls"].append({"round": env.round, "phase": env.phase,
                                    "seat": s, "agent": assignment[s], "input_tokens": None,
                                    "output_tokens": None, "estimated_usd": None, "seconds": None})
        observations, _, _, _ = env.step(decisions)
    record["frames"].append({"round": env.round, "phase": env.phase,
                             "observations": observations, "decisions": {}})
    record["events"] = copy.deepcopy(env.events)
    record["attempted_calls"] = len(record["calls"])
    record["status"] = "complete" if env.phase == "terminal" else "incomplete"
    if env.phase == "terminal":
        record["result"] = env.result()
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("view", "submit"))
    parser.add_argument("state", type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "submit":
            result = submit(args.state, json.load(sys.stdin))
        else:
            state = json.loads(args.state.read_text())
            result = view(state, restore(state))
        print(json.dumps(result, allow_nan=False))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"session error: {exc}\n")


if __name__ == "__main__":
    main()
