#!/usr/bin/env python3
"""Ingest external design-authority output into stage 04 as a draft spec."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from design_ingest import ingest_design  # noqa: E402
from design_input import design_error_count, format_design_findings  # noqa: E402
from project import resolve_project  # noqa: E402


def main() -> None:
    try:
        root = resolve_project()
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    result = ingest_design(root)
    if result.findings:
        print(format_design_findings(result.findings))
    if not result.written:
        print("Design ingest did not write stage 04.")
        sys.exit(1 if design_error_count(result.findings) else 0)
    print(f"Ingested external design into {result.path.name} as a draft.")
    if result.screen_ids:
        print("Screen IDs:")
        for node_id, scr_id in result.screen_ids.items():
            print(f"- {scr_id}: {node_id}")
    print("Review and approve stage 04 explicitly before downstream handoff.")


if __name__ == "__main__":
    main()
