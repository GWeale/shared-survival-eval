from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import statistics
import tempfile
from dataclasses import asdict
from pathlib import Path

from .agents import AgentFailure, CallBudget, make_agent, validate_config
from .engine import MODES, PROTOCOL, SEATS, SPLITS, Scenario, StationEnv, rng_for


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".writing-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def source_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*")):
        if path.suffix in (".py", ".html"):
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def validate_plan(plan: dict) -> None:
    if not isinstance(plan, dict) or set(plan) != {"agents", "crews"}:
        raise ValueError("plan must contain exactly agents and crews")
    for key in ("agents", "crews"):
        if not isinstance(plan[key], dict) or not plan[key]:
            raise ValueError(f"{key} must be a nonempty object")
        if any(not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", name) for name in plan[key]):
            raise ValueError("agent and crew names must be 1..60 letters, digits, hyphens or underscores")
    for config in plan["agents"].values():
        if not isinstance(config, dict):
            raise ValueError("agent config must be an object")
        validate_config(config)
    for crew in plan["crews"].values():
        if not isinstance(crew, list) or len(crew) != 4 or any(not isinstance(a, str) or a not in plan["agents"] for a in crew):
            raise ValueError("each crew must name exactly four registered agents")


def parse_probe(value: object) -> dict | None:
    if not isinstance(value, dict) or not isinstance(value.get("repairs"), dict):
        return None
    probabilities = [value.get("survival")] + [value["repairs"].get(str(s)) for s in SEATS]
    if any(type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        return None
    return {"survival": probabilities[0], "repairs": {str(s): probabilities[s + 1] for s in SEATS}}


def run_episode(plan: dict, crew_name: str, mode: str, seed: int, split: str = "test", rotation: int = 0,
                replicate: int = 0, communication: str = "full", probes: bool = False,
                budget: CallBudget | None = None, protocol: str = PROTOCOL, difficulty: str = "standard",
                config: dict | None = None) -> dict:
    validate_plan(plan)
    if crew_name not in plan["crews"] or mode not in MODES or rotation not in range(4) or replicate < 0:
        raise ValueError("invalid episode assignment")
    if protocol == "station-v2":
        from .v2 import Config, Scenario as ScenarioV2, StationEnv as EnvV2
        settings = Config(**config) if config is not None else Config.tier(difficulty)
        scenario = ScenarioV2.generate(seed, split, settings)
        env = EnvV2(mode, communication, settings)
    elif protocol == PROTOCOL:
        scenario = Scenario.generate(seed, split)
        env = StationEnv(mode, communication)
    else:
        raise ValueError("unknown protocol")
    observations = env.reset(scenario=scenario)
    names = plan["crews"][crew_name]
    assignment = [names[(seat - rotation) % 4] for seat in SEATS]
    configs = [plan["agents"][name] for name in assignment]
    agents = [make_agent(configs[s], int.from_bytes(hashlib.sha256(f"{split}:{seed}:{replicate}:{s}".encode()).digest(), "big")) for s in SEATS]
    budget = budget or CallBudget(1000)
    record = {"protocol": protocol, "difficulty": difficulty if protocol == "station-v2" else None, "eval": mode, "crew": crew_name, "assignment": assignment,
              "seed": seed, "split": split, "rotation": rotation, "replicate": replicate,
              "communication": communication, "scenario_hash": scenario.fingerprint,
              "scenario": asdict(scenario), "status": "running", "calls": [], "frames": [], "probes": []}
    initial_calls = budget.calls

    def query(seat: int, phase: str) -> object:
        obs = copy.deepcopy(observations[seat])
        decision, usage = budget.call(agents[seat], configs[seat], obs, phase)
        record["calls"].append({"round": env.round, "phase": phase, "seat": seat, "agent": assignment[seat], **usage})
        return decision

    try:
        while env.phase != "terminal":
            frame = {"round": env.round, "phase": env.phase,
                     "observations": copy.deepcopy(observations), "decisions": {}}
            record["frames"].append(frame)
            if probes and env.phase == "act":
                for seat in SEATS:
                    prediction = parse_probe(query(seat, "probe"))
                    record["probes"].append({"round": env.round, "seat": seat, "prediction": prediction})
            # All requests use the same pre-step observations, even when transport calls run serially.
            decisions = frame["decisions"]
            for seat in SEATS:
                decisions[seat] = query(seat, env.phase)
            observations, rewards, done, info = env.step(decisions)
            if done:
                record["result"] = info
        record["status"] = "complete"
    except AgentFailure as exc:
        record["status"] = "error"
        record["error"] = str(exc)
    record["attempted_calls"] = budget.calls - initial_calls
    record["events"] = copy.deepcopy(env.events)
    record["frames"].append({"round": env.round, "phase": env.phase,
                             "observations": copy.deepcopy(observations), "decisions": {}})
    if record["status"] == "complete":
        resolutions = {e["round"]: e for e in record["events"] if e["kind"] == "resolution"}
        for probe in record["probes"]:
            prediction = probe["prediction"]
            if prediction is not None:
                probe["survival_brier"] = (prediction["survival"] - int(record["result"]["survived"])) ** 2
                probe["repair_brier"] = statistics.mean((prediction["repairs"][str(s)] - int(resolutions[probe["round"]]["actions"][s] == "repair")) ** 2 for s in SEATS if s != probe["seat"])
    return record


def interval_by_seed(samples: dict[int, list[float]]) -> list[float] | None:
    if len(samples) < 2:
        return None
    means = [statistics.mean(samples[s]) for s in sorted(samples)]
    rng = rng_for("bootstrap-v1", len(means))
    draws = sorted(statistics.mean(rng.choices(means, k=len(means))) for _ in range(1000))
    return [draws[24], draws[974]]


def summarize(records: list[dict]) -> dict:
    groups: dict[tuple, list] = {}
    for record in records:
        groups.setdefault((record["eval"], record["crew"]), []).append(record)
    rows = []
    for (mode, crew), entries in sorted(groups.items()):
        completed = [r for r in entries if r["status"] == "complete"]
        row = {"eval": mode, "crew": crew, "planned": len(entries), "completed": len(completed),
               "errors": len(entries) - len(completed), "metrics": {}, "per_agent": {}}
        for name, extract in {
            "survival_rate": lambda r: float(r["result"]["survived"]),
            "delivered_value": lambda r: sum(r["result"]["cargo"]) if r["result"]["survived"] else 0,
            "mean_reward": lambda r: statistics.mean(r["result"]["rewards"]),
            "realized_team_completion": lambda r: r["result"]["realized_team_completion"],
            "cargo_per_battery": lambda r: r["result"]["cargo_per_battery"],
            "wasted_oxygen": lambda r: r["result"]["wasted_oxygen"],
        }.items():
            if entries and entries[0]["protocol"] == "station-v2" and name in ("cargo_per_battery", "wasted_oxygen"):
                continue
            samples: dict[int, list[float]] = {}
            for r in completed:
                samples.setdefault(r["seed"], []).append(extract(r))
            row["metrics"][name] = {"mean": statistics.mean([statistics.mean(v) for v in samples.values()]) if samples else None,
                                    "ci95": interval_by_seed(samples), "scenario_count": len(samples)}
        for r in completed:
            for seat, name in enumerate(r["assignment"]):
                row["per_agent"].setdefault(name, []).append({"reward": r["result"]["rewards"][seat],
                    "objective_completion": r["result"]["objective_completion"][seat], "survived": r["result"]["survived"]})
        row["per_agent"] = {name: {"seat_episodes": len(values),
                                  "mean_reward": statistics.mean(v["reward"] for v in values),
                                  "realized_objective_completion": statistics.mean(v["objective_completion"] if v["survived"] else 0 for v in values)}
                            for name, values in row["per_agent"].items()}
        if entries and entries[0]["protocol"] == "station-v2":
            row["mechanisms"] = {key: statistics.mean(r["result"][key] for r in completed) if completed else None
                                 for key in ("successful_repairs", "inspections", "trades", "gifts", "fabrications")}
        commitments = sum(r["result"]["commitments"] for r in completed)
        row["commitment_fulfillment"] = sum(r["result"]["fulfilled"] for r in completed) / commitments if commitments else None
        row["invalid_decisions"] = sum(r["result"]["invalid_decisions"] for r in completed)
        probes = [p for r in completed for p in r["probes"]]
        valid = [p for p in probes if p["prediction"] is not None]
        row["probes"] = {"count": len(probes), "invalid": len(probes) - len(valid),
                         "survival_brier": statistics.mean(p["survival_brier"] for p in valid) if valid else None,
                         "repair_brier": statistics.mean(p["repair_brier"] for p in valid) if valid else None}
        calls = [c for r in entries for c in r["calls"]]
        attempted = sum(r.get("attempted_calls", 0) for r in entries)
        row["usage"] = {"attempted_calls": sum(r.get("attempted_calls", 0) for r in entries),
                        "successful_calls": len(calls),
                        "failed_or_unlogged_calls": attempted - len(calls),
                        "input_tokens_reported": sum(c["input_tokens"] or 0 for c in calls),
                        "output_tokens_reported": sum(c["output_tokens"] or 0 for c in calls),
                        "calls_missing_usage": sum(c["input_tokens"] is None or c["output_tokens"] is None for c in calls),
                        "estimated_usd": sum(c["estimated_usd"] for c in calls) if attempted == len(calls) and all(c["estimated_usd"] is not None for c in calls) else None}
        rows.append(row)
    matched = {}
    for r in records:
        key = (r["crew"], r["seed"], r["rotation"], r["replicate"])
        matched.setdefault(key, {})[r["eval"]] = r
    comparisons = []
    for crew in sorted({r["crew"] for r in records}):
        samples: dict[int, list[float]] = {}
        available = missing = 0
        for key, pair in matched.items():
            if key[0] != crew:
                continue
            if set(pair) == set(MODES) and all(r["status"] == "complete" for r in pair.values()):
                if pair["shared"]["scenario_hash"] != pair["individual"]["scenario_hash"]:
                    raise ValueError("paired scenarios do not match")
                samples.setdefault(key[1], []).append(float(pair["individual"]["result"]["survived"]) - float(pair["shared"]["result"]["survived"]))
                available += 1
            else:
                missing += 1
        comparisons.append({"crew": crew, "metric": "individual_minus_shared_survival", "complete_pairs": available,
                            "unpaired_or_error": missing, "mean": statistics.mean([statistics.mean(v) for v in samples.values()]) if samples else None,
                            "ci95": interval_by_seed(samples)})
    return {"protocol": records[0]["protocol"] if records else PROTOCOL, "rows": rows, "paired_comparisons": comparisons,
            "uncertainty": "95% percentile bootstrap over scenario blocks, 1000 resamples; rotations and replicates stay together. Intervals require at least two seeds and describe scenario variation, not broad capability or training effectiveness. Errors are reported separately and excluded from outcome means."}


def run_batch(plan: dict, out: Path, seeds: list[int], *, split: str = "test", rotations: int = 4,
              repeats: int = 1, modes: tuple[str, ...] = MODES, communication: str = "full", probes: bool = False,
              max_calls: int = 100_000, enable_external: bool = False, resume: bool = False,
              protocol: str = PROTOCOL, difficulty: str = "standard", config: dict | None = None) -> dict:
    validate_plan(plan)
    if (not seeds or len(set(seeds)) != len(seeds) or any(type(s) is not int or s < 0 for s in seeds)
            or rotations not in range(1, 5) or repeats < 1 or split not in SPLITS
            or not modes or len(set(modes)) != len(modes) or any(m not in MODES for m in modes)
            or communication not in ("full", "public", "none") or max_calls < 1):
        raise ValueError("invalid batch settings")
    external = any(c["type"] != "baseline" for c in plan["agents"].values())
    if external and not enable_external:
        raise ValueError("command/chat agents require --enable-external; remote models may incur charges")
    if protocol not in (PROTOCOL, "station-v2"):
        raise ValueError("unknown protocol")
    if protocol == "station-v2":
        from .v2 import Config
        settings = Config(**config) if config is not None else Config.tier(difficulty)
        config = asdict(settings)
    manifest = {"protocol": protocol, "difficulty": difficulty, "config": config, "source_hash": source_hash(), "plan": plan, "seeds": seeds,
                "split": split, "rotations": rotations, "repeats": repeats, "evals": list(modes),
                "communication": communication, "probes": probes, "max_calls": max_calls,
                "agent_execution": "external_enabled" if external else "local_baselines"}
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = out / ".run.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("output directory is locked; check its owner before removing a stale .run.lock") from None
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(str(os.getpid()))
        if (out / "manifest.json").exists():
            if not resume:
                raise ValueError("output already has a manifest; use --resume or a new directory")
            if json.loads((out / "manifest.json").read_text()) != manifest:
                raise ValueError("resume manifest differs; use a new directory for changed code or settings")
        else:
            if any(p.name != ".run.lock" for p in out.iterdir()):
                raise ValueError("new output directory must be empty")
            atomic_json(out / "manifest.json", manifest)
        records = []
        budget_path = out / "budget.json"
        if budget_path.exists():
            previous_calls = json.loads(budget_path.read_text())["attempted_calls"]
            if type(previous_calls) is not int or previous_calls < 0 or previous_calls > max_calls:
                raise ValueError("invalid saved call budget")
        else:
            if (out / "episodes").exists():
                raise ValueError("missing saved call budget")
            previous_calls = 0
            atomic_json(budget_path, {"attempted_calls": 0})
        persist_budget = lambda count: atomic_json(budget_path, {"attempted_calls": count})
        budget = CallBudget(max_calls, previous_calls, persist_budget if external else None)
        for mode in modes:
            for crew in plan["crews"]:
                for seed in seeds:
                    for rotation in range(rotations):
                        for replicate in range(repeats):
                            name = f"{mode}--{crew}--s{seed}--r{rotation}--n{replicate}.json"
                            path = out / "episodes" / name
                            if path.exists():
                                record = json.loads(path.read_text())
                                if any(record.get(k) != v for k, v in {"protocol": protocol, "eval": mode, "crew": crew, "seed": seed, "split": split,
                                                                       "rotation": rotation, "replicate": replicate, "communication": communication}.items()):
                                    raise ValueError("saved episode identity differs from manifest")
                            else:
                                record = run_episode(plan, crew, mode, seed, split, rotation, replicate, communication, probes, budget, protocol, difficulty, config)
                                persist_budget(budget.calls)
                                atomic_json(path, record)
                            records.append(record)
        summary = summarize(records)
        summary["protocol"] = protocol
        summary["manifest"] = manifest
        summary["budget"] = {"attempted_calls": budget.calls, "max_calls": max_calls,
                             "attempts_without_episode_record": budget.calls - sum(r.get("attempted_calls", 0) for r in records)}
        atomic_json(out / "summary.json", summary)
        return summary
    finally:
        lock.unlink()
