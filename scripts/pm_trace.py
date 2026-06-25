#!/usr/bin/env python3
"""Resolve and (re)build the local traceability spine (Phase 3.5).

Subcommands:
  rebuild                      Rebuild .traceability.yaml from the PRD + QA plan.
  requirement REQ-001          Show the TC-### scenarios covering a requirement.
  scenario TC-001              Show the requirement ids a test case covers.
  coverage                     List requirements with no covering scenario.
  show                         Print the whole index as JSON.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".pm-os" / "lib"))

from project import resolve_project
import traceability as trace


def main():
    parser = argparse.ArgumentParser(description="PM-OS traceability resolver.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("rebuild", help="Rebuild .traceability.yaml from PRD + QA plan.")
    p_req = sub.add_parser("requirement", help="Scenarios covering a requirement id.")
    p_req.add_argument("req_id")
    p_tc = sub.add_parser("scenario", help="Requirements a test case covers.")
    p_tc.add_argument("tc_id")
    sub.add_parser("coverage", help="Requirements with no covering scenario.")
    sub.add_parser("show", help="Print the whole traceability index as JSON.")

    args = parser.parse_args()

    try:
        root = resolve_project()
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if args.command == "rebuild":
        index = trace.rebuild(root)
        reqs = index.get("requirements") or {}
        tcs = index.get("test_cases") or {}
        print(f"Rebuilt {trace.TRACEABILITY_FILENAME}: "
              f"{len(reqs)} requirement(s), {len(tcs)} test case(s).")
        uncovered = trace.uncovered_requirements(root)
        if uncovered:
            print(f"Requirements with no covering scenario: {', '.join(uncovered)}")
        return

    if args.command == "requirement":
        scenarios = trace.scenarios_for_requirement(root, args.req_id)
        if scenarios:
            print(f"{args.req_id.upper()} is covered by: {', '.join(scenarios)}")
        else:
            print(f"{args.req_id.upper()} has no covering scenarios.")
        return

    if args.command == "scenario":
        reqs = trace.requirements_for_scenario(root, args.tc_id)
        if reqs:
            print(f"{args.tc_id.upper()} covers: {', '.join(reqs)}")
        else:
            print(f"{args.tc_id.upper()} covers no requirements (or is unknown).")
        return

    if args.command == "coverage":
        uncovered = trace.uncovered_requirements(root)
        if uncovered:
            print("Requirements with no covering scenario:")
            for req_id in uncovered:
                print(f"  {req_id}")
        else:
            print("All requirements are covered by at least one scenario.")
        return

    if args.command == "show":
        index = trace.load_index(root) or trace.build_index(root)
        print(json.dumps(index, indent=2, sort_keys=True))
        return


if __name__ == "__main__":
    main()
