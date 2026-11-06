from __future__ import annotations

import copy
import json
from pathlib import Path


def seat_record(record: dict, seat: int) -> dict:
    if seat not in range(4):
        raise ValueError("seat must be in 0..3")
    public = {key: copy.deepcopy(record[key]) for key in ("protocol", "eval", "crew", "assignment", "communication", "status")}
    public["restricted_seat"] = seat
    public["frames"] = []
    for frame in record["frames"]:
        observations = frame["observations"]
        own = observations.get(seat, observations.get(str(seat)))
        decisions = frame["decisions"]
        decision = decisions.get(seat, decisions.get(str(seat)))
        public["frames"].append({"round": frame["round"], "phase": frame["phase"],
                                  "observations": {str(seat): copy.deepcopy(own)},
                                  "decisions": {str(seat): copy.deepcopy(decision)} if decision is not None else {}})
    public["events"] = [copy.deepcopy(e) for e in record["events"] if e["visible_to"] is None or seat in e["visible_to"]]
    public["probes"] = [copy.deepcopy(p) for p in record["probes"] if p["seat"] == seat]
    public["calls"] = [copy.deepcopy(c) for c in record["calls"] if c["seat"] == seat]
    if record.get("result"):
        result = record["result"]
        public["result"] = {key: copy.deepcopy(result[key]) for key in ("survived", "rounds", "reason")}
        public["result"].update(own_reward=result["rewards"][seat], own_cargo=result["cargo"][seat])
    if "error" in record:
        public["error"] = record["error"]
    return public


def render_replay(record: dict, out: Path, seat: int | None = None) -> None:
    data = seat_record(record, seat) if seat is not None else record
    payload = json.dumps(data, allow_nan=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template = Path(__file__).with_name("viewer.html").read_text()
    html = template.replace("__EPISODE_DATA__", payload)
    out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with out.open("w", encoding="utf-8") as stream:
        stream.write(html)
    out.chmod(0o600)
