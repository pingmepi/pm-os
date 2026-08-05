"""Zip codebase sources: extract into .codebase/ as a self-contained git checkout.

Covers prepare-codebase with a .zip archive — single-folder flattening, the
synthetic git commit that makes a zip behave like a clone for SHA pinning,
idempotent reuse of the same archive, refusal to silently overwrite with a
different archive, and zip-slip rejection. See docs/guides/testing.md.
"""
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest
import yaml

from helpers import run_script

pytestmark = pytest.mark.integration


def _make_zip(path: Path, members: dict, wrap: str | None = "myproj") -> Path:
    """Write a zip; when ``wrap`` is set, nest members under one top-level folder."""
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            arcname = f"{wrap}/{name}" if wrap else name
            archive.writestr(arcname, content)
    return path


def _prepare(pmos, proj, zip_path):
    return run_script(pmos, "pm_context_import.py", "prepare-codebase", str(zip_path), cwd=proj)


def test_zip_extracts_flattens_and_becomes_a_git_checkout(pmos, new_project, tmp_path):
    """A wrapped zip unwraps into .codebase/ and gets a synthetic git commit."""
    proj = new_project("zip-product")
    zip_path = _make_zip(
        tmp_path / "code.zip",
        {"app.py": "VALUE = 1\n", "README.md": "# Demo\n", "pkg/util.py": "x = 2\n"},
    )

    result = _prepare(pmos, proj, zip_path)

    assert result.returncode == 0, result.stdout + result.stderr
    codebase = proj / ".codebase"
    assert (codebase / "app.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (codebase / "pkg" / "util.py").is_file()
    assert not (codebase / "myproj").exists()  # wrapper folder flattened away
    assert (codebase / ".git").is_dir()  # git-init'd so E2 can pin a SHA

    meta = yaml.safe_load((proj / ".meta.yaml").read_text(encoding="utf-8"))
    assert meta["codebase_path"] == str(codebase)
    assert isinstance(meta.get("codebase_ref"), str) and len(meta["codebase_ref"]) == 40
    head = subprocess.run(
        ["git", "-C", str(codebase), "rev-parse", "HEAD"], capture_output=True, text=True,
    )
    assert head.returncode == 0 and head.stdout.strip() == meta["codebase_ref"]

    gitignore = (proj / ".gitignore").read_text(encoding="utf-8")
    assert ".codebase/" in gitignore and ".codebase-source" in gitignore
    assert (proj / ".codebase-source").read_text(encoding="utf-8").startswith("zip:")


def test_same_zip_reuses_and_different_zip_is_refused(pmos, new_project, tmp_path):
    """Re-preparing the same archive reuses; a different archive refuses to clobber."""
    proj = new_project("zip-reuse")
    first = _make_zip(tmp_path / "a.zip", {"app.py": "A = 1\n"})
    assert _prepare(pmos, proj, first).returncode == 0
    original_ref = yaml.safe_load((proj / ".meta.yaml").read_text(encoding="utf-8"))["codebase_ref"]

    reuse = _prepare(pmos, proj, first)
    assert reuse.returncode == 0
    assert "reusing" in reuse.stdout.lower()

    other = _make_zip(tmp_path / "b.zip", {"app.py": "B = 2\n"})
    refused = _prepare(pmos, proj, other)
    assert refused.returncode != 0
    assert "already exists" in (refused.stdout + refused.stderr).lower()
    # The refusal must not have swapped the extracted code or its recorded ref.
    assert (proj / ".codebase" / "app.py").read_text(encoding="utf-8") == "A = 1\n"
    assert yaml.safe_load((proj / ".meta.yaml").read_text(encoding="utf-8"))["codebase_ref"] == original_ref


def test_zip_slip_entry_is_rejected_without_writing_outside(pmos, new_project, tmp_path):
    """A traversal entry (../escape) is refused before anything is extracted."""
    proj = new_project("zip-slip")
    malicious = tmp_path / "evil.zip"
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("app.py", "ok = 1\n")
        archive.writestr("../escape.txt", "pwned\n")

    result = _prepare(pmos, proj, malicious)

    assert result.returncode != 0
    assert "escape" in (result.stdout + result.stderr).lower()
    assert not (proj.parent / "escape.txt").exists()
    assert not (proj / ".codebase").exists()  # nothing left half-extracted


def test_non_zip_file_is_rejected_clearly(pmos, new_project, tmp_path):
    """A plain file that is not a valid archive gets an actionable error, not a crash."""
    proj = new_project("zip-bad")
    not_a_zip = tmp_path / "notes.txt"
    not_a_zip.write_text("just text\n", encoding="utf-8")

    result = _prepare(pmos, proj, not_a_zip)

    assert result.returncode != 0
    assert "not a valid .zip" in (result.stdout + result.stderr).lower()
