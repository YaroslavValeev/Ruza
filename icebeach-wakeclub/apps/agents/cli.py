from __future__ import annotations

import argparse
import json
import sys

from .runners import (
    run_daily_brief,
    run_late_marker,
    run_intake_sync,
    run_ops_alert,
    run_preflight_guard,
    run_shift_snapshot,
)


AGENTS = {
    "preflight_guard": lambda args: run_preflight_guard(),
    "late_marker": lambda args: run_late_marker(),
    "shift_snapshot": lambda args: run_shift_snapshot(),
    "ops_alert": lambda args: run_ops_alert(),
    "daily_brief": lambda args: run_daily_brief(mode=args.mode),
    "intake_sync": lambda args: run_intake_sync(),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ice Beach operational agents")
    parser.add_argument("command", choices=["run", "list"])
    parser.add_argument("--agent", choices=sorted(AGENTS.keys()))
    parser.add_argument("--mode", choices=["morning", "evening"], default="morning")
    args = parser.parse_args(argv)

    if args.command == "list":
        print("\n".join(sorted(AGENTS.keys())))
        return 0

    if not args.agent:
        parser.error("--agent is required for run")
    result = AGENTS[args.agent](args)
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
