"""Canonical read-only repository fingerprint, shared by the E2 lifecycle and /pm-check.

`pm_enhance.py` captures a fingerprint when an enhancement starts; `consistency.py`
recomputes it to detect drift. These MUST agree byte-for-byte, so both import this
one implementation instead of keeping divergent copies. In particular, a supported
local codebase that is *not* a Git checkout gets an `os.walk` fallback fingerprint
here too — otherwise the checker would see `None` where capture stored a real hash
and report false `ENHANCEMENT_REPOSITORY_DRIFT`.

Never follows symlinks and never reads `.git`; hashes only Git-visible worktree
bytes (or, without Git, every non-`.git` file).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Optional


def git_value(path: Optional[Path], *args: str) -> Optional[str]:
    """Run `git -C <path> <args>` read-only; return stripped stdout or None on failure."""
    if path is None:
        return None
    result = subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _git_visible_paths(path: Path) -> Optional[list[str]]:
    result = subprocess.run(
        [
            "git", "-C", str(path), "ls-files", "-z", "--cached", "--others",
            "--exclude-standard",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    decoded = result.stdout.decode("utf-8", errors="surrogateescape")
    return sorted(item for item in decoded.split("\0") if item)


def repository_fingerprint(path: Path) -> str:
    """Hash Git-visible worktree bytes without following links or reading .git.

    Falls back to an `os.walk` of every non-`.git` file when the path is not a Git
    checkout, so a non-Git codebase gets a stable, reproducible fingerprint rather
    than being treated as unhashable (which downstream reads as drift).
    """
    path = Path(path)
    relative_paths = _git_visible_paths(path)
    if relative_paths is None:
        relative_paths = []
        for current, directories, files in os.walk(path, followlinks=False):
            directories[:] = sorted(name for name in directories if name != ".git")
            current_path = Path(current)
            for name in sorted(files):
                relative_paths.append((current_path / name).relative_to(path).as_posix())
        relative_paths.sort()

    digest = hashlib.sha256()
    for relative in relative_paths:
        candidate = path / relative
        digest.update(relative.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        if candidate.is_symlink():
            digest.update(b"L\0")
            digest.update(os.readlink(str(candidate)).encode("utf-8", errors="surrogateescape"))
        elif candidate.is_file():
            digest.update(b"F\0")
            with candidate.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        else:
            digest.update(b"M\0")
        digest.update(b"\0")
    return digest.hexdigest()
