from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import MODES
from .replay import render_replay
from .runner import run_batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate multi-agent cooperation under a common survival and crew-objective reward.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run a versioned plan and write paired episode results")
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--eval", choices=["both", *MODES], default="shared")
    run.add_argument("--seeds", type=int, default=10, help="number of consecutive scenarios")
    run.add_argument("--seed-start", type=int, default=0)
    run.add_argument("--split", choices=["train", "validation", "test"], default="test")
    run.add_argument("--rotations", type=int, choices=range(1, 5), default=4)
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--communication", choices=["full", "public", "none"], default="full")
    run.add_argument("--probes", action="store_true")
    run.add_argument("--max-calls", type=int, default=100_000, help="total request-attempt limit, including probes and resumed work; not a dollar cap")
    run.add_argument("--enable-external", action="store_true", help="allow command/chat adapters; model servers may charge for requests")
    run.add_argument("--resume", action="store_true", help="skip saved episodes; refuse changed code/settings; errors remain visible")
    replay = sub.add_parser("replay", help="export a standalone offline HTML replay")
    replay.add_argument("episode", type=Path)
    replay.add_argument("--out", type=Path, required=True)
    replay.add_argument("--seat", type=int, choices=range(4), help="physically redact all other seats' private data")
    try:
        args = parser.parse_args(argv)
        if args.command == "replay":
            render_replay(json.loads(args.episode.read_text()), args.out, args.seat)
            print(f"Replay: {args.out.resolve()}")
            return 0
        if args.seeds < 1 or args.seed_start < 0 or args.repeats < 1:
            raise ValueError("seeds and repeats must be positive; seed-start must be nonnegative")
        plan = json.loads(args.plan.read_text())
        modes = MODES if args.eval == "both" else (args.eval,)
        summary = run_batch(plan, args.out, list(range(args.seed_start, args.seed_start + args.seeds)),
                            split=args.split, rotations=args.rotations, repeats=args.repeats, modes=modes,
                            communication=args.communication, probes=args.probes, max_calls=args.max_calls,
                            enable_external=args.enable_external, resume=args.resume)
        for row in summary["rows"]:
            survival = row["metrics"]["survival_rate"]["mean"]
            rate = f"{survival:.1%}" if survival is not None else "unavailable"
            print(f"{row['eval']:10} {row['crew']:16} completed={row['completed']}/{row['planned']} errors={row['errors']} survival={rate}")
        print(f"Results: {(args.out / 'summary.json').resolve()}")
        return 2 if any(row["errors"] for row in summary["rows"]) else 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
