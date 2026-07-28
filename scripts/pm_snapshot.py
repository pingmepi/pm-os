#!/usr/bin/env python3
"""Create a generated-artifact history snapshot without relying on agent file writes."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.environ.get("PM_OS_LIB_PATH") or str(Path.home() / ".pm-os" / "lib"))

from frontmatter import read as fm_read, write as fm_write  # noqa: E402
from hashing import hash_artifact_body  # noqa: E402
from project import STAGE_NAMES, artifact_path, resolve_project  # noqa: E402


def _warn(message: str) -> None:
    print(f"Warning: {message}", file=sys.stderr)


def snapshot(project_root: Path, stage_id: str) -> Path | None:
    stage_id = stage_id.zfill(2)
    if stage_id not in STAGE_NAMES:
        _warn(f"unknown stage '{stage_id}'")
        return None
    apath = artifact_path(project_root, stage_id)
    if not apath.exists():
        _warn(f"artifact not found: {apath}")
        return None

    try:
        fm, body = fm_read(str(apath))
        computed = hash_artifact_body(str(apath))
    except Exception as exc:  # noqa: BLE001 - lineage must warn, not block generation.
        _warn(f"could not read/hash {apath.name}: {exc}")
        return None

    if fm.get("generated_hash") != computed:
        fm["generated_hash"] = computed
        try:
            fm_write(str(apath), fm, body)
        except Exception as exc:  # noqa: BLE001
            _warn(f"could not stamp generated_hash on {apath.name}: {exc}")
            return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    history = project_root / ".history"
    try:
        history.mkdir(exist_ok=True)
        dest = history / f"{apath.stem}.{timestamp}.generated.md"
        suffix = 1
        while dest.exists():
            dest = history / f"{apath.stem}.{timestamp}.{suffix}.generated.md"
            suffix += 1
        shutil.copy2(apath, dest)
    except Exception as exc:  # noqa: BLE001
        _warn(f"could not write generated snapshot for {apath.name}: {exc}")
        return None

    try:
        snap_hash = hash_artifact_body(str(dest))
    except Exception as exc:  # noqa: BLE001
        _warn(f"could not verify generated snapshot {dest.name}: {exc}")
        return dest
    if snap_hash != computed:
        _warn(f"generated snapshot hash mismatch for {dest.name}")
    else:
        print(f"Generated snapshot written: {dest}")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a PM-OS generated artifact snapshot.")
    parser.add_argument("stage_id", help="Two-digit stage id, e.g. 03")
    args = parser.parse_args()
    try:
        root = resolve_project()
    except FileNotFoundError as exc:
        _warn(str(exc))
        return
    snapshot(root, args.stage_id)


if __name__ == "__main__":
    main()
