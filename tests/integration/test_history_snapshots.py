"""Generated history snapshot helper and lineage consistency checks."""

import pytest

import consistency
import frontmatter
from hashing import hash_artifact_body
from helpers import make_draft, run_script

pytestmark = pytest.mark.integration


def test_pm_snapshot_stamps_hash_and_copies_exact_artifact(pmos, new_project):
    proj = new_project("snapshot-helper", "A problem")
    apath = make_draft(proj, "01", body="Generated body.\n")
    fm, body = frontmatter.read(str(apath))
    fm["generated_hash"] = "wrong"
    frontmatter.write(str(apath), fm, body)

    res = run_script(pmos, "pm_snapshot.py", "01", cwd=proj)
    assert res.returncode == 0, res.stderr

    stamped_hash = hash_artifact_body(str(apath))
    fm_after, _ = frontmatter.read(str(apath))
    assert fm_after["generated_hash"] == stamped_hash
    snapshots = list((proj / ".history").glob("01-brief.*.generated.md"))
    assert len(snapshots) == 1
    assert hash_artifact_body(str(snapshots[0])) == stamped_hash


def test_pm_check_warns_when_generated_snapshot_missing_or_mismatched(pmos, new_project):
    proj = new_project("snapshot-check", "A problem")
    apath = make_draft(proj, "01", body="Generated body.\n")
    fm, body = frontmatter.read(str(apath))
    fm["generated_hash"] = hash_artifact_body(str(apath))
    frontmatter.write(str(apath), fm, body)

    issues = consistency.check_project(proj)
    assert any(i.code == consistency.CODE_HISTORY_SNAPSHOT_MISSING and i.stage == "01" for i in issues)

    hist = proj / ".history"
    hist.mkdir(exist_ok=True)
    bad = hist / "01-brief.20260101T000000Z.generated.md"
    bad.write_text(apath.read_text(encoding="utf-8").replace("Generated body.", "Different body."), encoding="utf-8")
    issues = consistency.check_project(proj)
    assert any(i.code == consistency.CODE_HISTORY_SNAPSHOT_HASH_MISMATCH and i.stage == "01" for i in issues)
