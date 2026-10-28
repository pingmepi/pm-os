"""Unit tests for lib/release_check.py — the release check that runs on any
handoff folder, PM-OS-built or hand-built, before it reaches a build team
(backlog #72). See docs/guides/testing.md §5 (T1)."""
import zipfile
from pathlib import Path

import pytest

import release_check as rc

pytestmark = pytest.mark.unit


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _story(story_id: str, *, epic: str | None = "EP-01", priority: str | None = "Must",
           source: str | None = None, body: str = "As a user, I want things.\n") -> str:
    fm = [f"story_id: {story_id}"]
    if epic is not None:
        fm.append(f"epic: {epic}")
    if priority is not None:
        fm.append(f"priority: {priority!r}")
    if source is not None:
        fm.append(f"source: {source}")
    return "---\n" + "\n".join(fm) + f"\n---\n\n# {story_id} · A story\n\n{body}"


def _codes(report) -> dict[str, int]:
    out: dict[str, int] = {}
    for finding in report.findings:
        out[finding.code] = out.get(finding.code, 0) + 1
    return out


def _clean_package(root: Path) -> Path:
    _write(root, "README.md", "# Package\n\nSee [the story](stories/US-01-sign-in.md).\n")
    _write(root, "epics.md", "## EP-01 — Accounts\n\nOutcome: users sign in.\n")
    _write(root, "stories/US-01-sign-in.md", _story("US-01"))
    return root


def test_clean_hand_built_package_has_no_findings(tmp_path):
    """A package whose stories carry an epic and a priority, whose links resolve
    and whose ids are all defined produces no findings and is classed hand-built."""
    report = rc.check_release(_clean_package(tmp_path))
    assert report.kind == "hand-built"
    assert report.findings == []
    assert report.stats["stories"] == 1


def test_story_without_epic_or_priority_is_an_error(tmp_path):
    """Missing epic and missing priority are errors, located at the story file,
    with a fix that names the frontmatter key to add."""
    _write(tmp_path, "stories/US-01-sign-in.md", _story("US-01", epic=None, priority=None))
    report = rc.check_release(tmp_path)
    codes = _codes(report)
    assert codes["STORY_EPIC_MISSING"] == 1 and codes["STORY_PRIORITY_MISSING"] == 1
    finding = next(f for f in report.errors if f.code == "STORY_PRIORITY_MISSING")
    assert finding.path == "stories/US-01-sign-in.md" and "priority:" in finding.fix


def test_priority_with_markdown_markup_is_malformed(tmp_path):
    """A priority value that still carries `**` (the backlog #70 symptom in
    every PRISM dev story) is an error naming the clean value to use."""
    _write(tmp_path, "epics.md", "## EP-01 — Accounts\n")
    _write(tmp_path, "stories/US-01-sign-in.md", _story("US-01", priority="** Must / S2"))
    report = rc.check_release(tmp_path)
    finding = next(f for f in report.errors if f.code == "STORY_PRIORITY_MALFORMED")
    assert "'Must / S2'" in finding.fix and finding.line == 4


def test_epic_and_priority_can_come_from_labeled_body_lines(tmp_path):
    """A story without frontmatter keys still passes when its body carries
    labeled `Epic:` and `Priority:` lines (the PM-OS story shape)."""
    _write(tmp_path, "epics.md", "## EP-01 — Accounts\n")
    _write(tmp_path, "stories/US-01-sign-in.md",
           "---\nstory_id: US-01\n---\n# US-01\n**Epic:** EP-01\n**Priority:** Must\n")
    assert not [f for f in rc.check_release(tmp_path).errors if f.code.startswith("STORY_")]


def test_cited_series_id_without_definition_is_an_error(tmp_path):
    """APEX AL-21: rule ids R-01…R-03 cited in a story but defined nowhere in
    the package are undefined-id errors; adding a table that defines them in
    its first column resolves them."""
    _clean_package(tmp_path)
    _write(tmp_path, "stories/US-01-sign-in.md",
           _story("US-01", body="Follows R-01, R-02 and R-03.\n"))
    report = rc.check_release(tmp_path)
    undefined = sorted(f.message.split("`")[1] for f in report.errors if f.code == "ID_UNDEFINED")
    assert undefined == ["R-01", "R-02", "R-03"]
    _write(tmp_path, "rules.md", "| Rule | Means |\n|---|---|\n| **R-01 One page** | x |\n"
                                 "| **R-02 Verbatim** | y |\n| R-03 | z |\n")
    assert not [f for f in rc.check_release(tmp_path).errors if f.code == "ID_UNDEFINED"]


@pytest.mark.parametrize("text", [
    "Dates use ISO-8601 and hashes use SHA-256 over UTF-8 text.",
    "Built during COVID-19.",
    "Sample run RUN-0001, RUN-0002 and RUN-0003 are records, not spec ids.",
    "One-off reference ASM-01 in passing.",
])
def test_standards_one_offs_and_sample_records_are_not_ids(tmp_path, text):
    """Standard tokens, a one-off WORD-n mention and 4-digit sample records in a
    family the folder never defines are not treated as ids."""
    _clean_package(tmp_path)
    _write(tmp_path, "notes.md", f"# Notes\n\n{text}\n")
    assert not [f for f in rc.check_release(tmp_path).findings if f.code.startswith("ID_")]


def test_ids_inside_code_and_link_targets_are_not_citations(tmp_path):
    """Code is where packages keep sample data and schemas, so ids in fenced or
    inline code, and in link targets or URLs, are not citations."""
    _clean_package(tmp_path)
    _write(tmp_path, "schema.md",
           "# Schema\n\n```json\n{\"ids\": [\"S-001\", \"S-002\", \"S-003\"]}\n```\n"
           "Example `S-004` here. See [doc](https://example.com/S-005-x/S-006).\n")
    assert not [f for f in rc.check_release(tmp_path).findings if f.code.startswith("ID_")]


def test_short_form_warns_and_ambiguous_short_form_errors(tmp_path):
    """`US-01` for the only defined `S1-US-01` is a warning naming the full id;
    when both `S1-US-01` and `S2-US-01` exist it is ambiguous, an error."""
    _write(tmp_path, "epics.md", "## EP-01 — Accounts\n")
    _write(tmp_path, "stories/S1-US-01-a.md", _story("S1-US-01"))
    _write(tmp_path, "stories/S1-US-02-b.md", _story("S1-US-02"))
    _write(tmp_path, "README.md", "# Stories\n\nStart with US-01, then US-02 and US-03.\n")
    report = rc.check_release(tmp_path)
    short = next(f for f in report.findings if f.code == "ID_SHORT_FORM" and "`US-01`" in f.message)
    assert short.severity == "warning" and "S1-US-01" in short.fix
    _write(tmp_path, "stories/S2-US-01-c.md", _story("S2-US-01"))
    report = rc.check_release(tmp_path)
    assert any(f.code == "ID_AMBIGUOUS" and "`US-01`" in f.message for f in report.errors)


def test_example_only_citation_is_a_warning(tmp_path):
    """An id cited only as an example — alone in parentheses or after "e.g." —
    is a warning suggesting code formatting, not an error."""
    _clean_package(tmp_path)
    _write(tmp_path, "rules.md", "| E-01 | x |\n| E-02 | y |\n")
    _write(tmp_path, "notes.md", "# Notes\n\nAn element id (E-12) is stable, e.g. E-13 v2.\n")
    report = rc.check_release(tmp_path)
    assert {f.code for f in report.findings if "E-1" in f.message} == {"ID_EXAMPLE_UNDEFINED"}


def test_ignore_ids_skips_prefixes_and_exact_ids(tmp_path):
    """`ignore_ids` (the CLI's --ignore-ids) skips a whole prefix or one id."""
    _clean_package(tmp_path)
    _write(tmp_path, "notes.md", "# Notes\n\nSee R-01, R-02, R-03 and T-1, T-2, T-3.\n")
    report = rc.check_release(tmp_path, ignore_ids=["R", "T-1"])
    undefined = sorted(f.message.split("`")[1] for f in report.errors if f.code == "ID_UNDEFINED")
    assert undefined == ["T-2", "T-3"]


def test_broken_links_links_outside_the_package_and_missing_anchors(tmp_path):
    """APEX AL-23: a relative link to a missing file is an error, a link that
    leaves the package is an error even when the target exists on disk, a
    missing heading anchor is a warning, and URLs are never checked."""
    pkg = tmp_path / "pkg"
    _clean_package(pkg)
    _write(tmp_path, "outside.md", "# Outside\n")
    _write(pkg, "links.md",
           "# Links\n\n## Real heading\n\n[gone](missing.md) [out](../outside.md) "
           "[anchor](#real-heading) [bad anchor](epics.md#nope) [web](https://example.com/x.md)\n")
    report = rc.check_release(pkg)
    codes = _codes(report)
    assert codes == {"LINK_BROKEN": 1, "LINK_OUTSIDE_PACKAGE": 1, "LINK_ANCHOR_MISSING": 1}
    broken = next(f for f in report.errors if f.code == "LINK_BROKEN")
    assert (broken.path, broken.line) == ("links.md", 5)


def test_missing_file_is_flagged_only_under_a_shipped_folder(tmp_path):
    """A path in code whose folder ships with the package but whose file does
    not is an error; a path into a folder the package never ships (a file the
    developer creates) is not checked."""
    _clean_package(tmp_path)
    _write(tmp_path, "config/brands/aimovig.yaml", "brand: aimovig\n")
    _write(tmp_path, "notes.md", "# Notes\n\nLoad `config/brands/inlyta.yaml` and "
                                 "`config/brands/aimovig.yaml`; write `src/app.py`.\n")
    report = rc.check_release(tmp_path)
    missing = [f for f in report.findings if f.code == "FILE_REFERENCE_MISSING"]
    assert [f.message.split("`")[1] for f in missing] == ["config/brands/inlyta.yaml"]


def test_placeholder_markers(tmp_path):
    """Unfilled template markers (TODO, TBD, lorem ipsum, {{slot}}) are errors;
    disclosed gaps ("to be confirmed", "pending") are warnings grouped per file;
    ordinary prose ("a to-do list") is left alone."""
    _clean_package(tmp_path)
    _write(tmp_path, "notes.md",
           "# Notes\n\nCopy: TBD.\nKeep a to-do list.\nFrame A: copy to be confirmed.\n"
           "Frame B: copy to be confirmed.\nHello {{name}}.\n")
    report = rc.check_release(tmp_path)
    assert _codes(report) == {"PLACEHOLDER": 2, "PENDING_MARKER": 1}
    pending = next(f for f in report.findings if f.code == "PENDING_MARKER")
    assert pending.line == 5 and "1 more line" in pending.message


def test_hand_built_story_built_from_an_older_prd_is_stale(tmp_path):
    """sprint-2 shape: a story whose `source:` names PRD-sprint-2 v0.3 while the
    package's PRD-sprint-2.md is v0.5 (version on its first line) is a stale-
    source error; two copies of the PRD at different versions conflict."""
    _write(tmp_path, "epics.md", "## EP-01 — Accounts\n")
    _write(tmp_path, "PRD-sprint-2.md", "PRISM / Sprint 2 / PRD · v0.5, 21 October 2026\n\n# PRD\n")
    _write(tmp_path, "stories/S2-US-01-a.md",
           _story("S2-US-01", source="PRD-sprint-2 v0.3, 14 Oct 2026"))
    _write(tmp_path, "stories/S2-US-02-b.md",
           _story("S2-US-02", source="PRD-sprint-2 v0.5, 21 Oct 2026"))
    report = rc.check_release(tmp_path)
    stale = [f for f in report.errors if f.code == "SOURCE_STALE"]
    assert [f.path for f in stale] == ["stories/S2-US-01-a.md"]
    assert "v0.5" in stale[0].message
    _write(tmp_path, "reference/PRD-sprint-2.md", "PRD · v0.4\n")
    assert any(f.code == "SOURCE_VERSION_CONFLICT" for f in rc.check_release(tmp_path).errors)


def test_pmos_package_generated_from_an_older_artifact_is_stale(tmp_path):
    """A PM-OS package (marker present) whose `generated_from` hash no longer
    matches the project's current 03-prd.md content hash is stale; one whose
    source stage is no longer approved is flagged too."""
    project = tmp_path / "proj"
    _write(project, ".meta.yaml", "schema_version: 5\nstages:\n- id: '03'\n  status: approved\n"
                                  "- id: '06'\n  status: stale\n")
    _write(project, "03-prd.md", "---\nstatus: approved\ncontent_hash: " + "b" * 64 + "\n---\n# PRD\n")
    _write(project, "06-qa-plan.md", "---\nstatus: stale\ncontent_hash: " + "c" * 64 + "\n---\n# QA\n")
    pkg = project / "handoff" / "dev"
    _write(pkg, ".pm-os-handoff", "marker\n")
    _write(pkg, "stories/US-001-a.md",
           "---\nstory_id: US-001\nepic: EPIC-001\npriority: Must\ngenerated_from:\n"
           "- 03-prd.md@aaaaaaaaaaaa\n- 06-qa-plan.md@cccccccccccc\ncanonical_source: 03-prd.md\n---\n# US-001\n")
    report = rc.check_release(pkg)
    assert report.kind == "pm-os" and report.project_root == project.resolve()
    codes = _codes(report)
    assert codes.get("SOURCE_STALE") == 1 and codes.get("SOURCE_NOT_APPROVED") == 1


def test_coverage_is_not_enforced_before_the_qa_plan_is_approved(tmp_path):
    """A design package is built from a stage-04 brief before any QA plan
    exists, so with stage 06 unapproved the untested-requirement check (#53a)
    becomes one COVERAGE_NOT_CHECKED warning instead of errors."""
    project = tmp_path / "proj"
    _write(project, ".meta.yaml", "schema_version: 5\nstages:\n- id: '03'\n  status: approved\n")
    _write(project, "03-prd.md", "---\nstatus: approved\ncontent_hash: " + "b" * 64 + "\n---\n"
                                 "## User Stories with Acceptance Criteria\n### US-001 — A\nPriority: Must\n")
    pkg = project / "handoff" / "design"
    _write(pkg, ".pm-os-handoff", "marker\n")
    _write(pkg, "stories/US-001-a.md", "---\nstory_id: US-001\nepic: EPIC-001\npriority: Must\n---\n# US-001\n")
    report = rc.check_release(pkg)
    assert not report.errors
    assert [f.code for f in report.warnings] == ["COVERAGE_NOT_CHECKED"]


def test_release_check_never_writes_to_the_project_it_reads(tmp_path):
    """The check reads `.meta.yaml` with plain YAML, never `load_meta()`, which
    migrates and saves. Checking a package inside an old-schema project (and a
    hand-built folder sitting inside a project) must leave every project file
    byte-for-byte unchanged."""
    project = tmp_path / "proj"
    _write(project, ".meta.yaml", "schema_version: 2\nstages:\n- id: '03'\n  status: approved\n"
                                  "- id: '06'\n  status: approved\n")
    _write(project, "03-prd.md", "---\nstatus: approved\ncontent_hash: " + "b" * 64 + "\n---\n"
                                 "## User Stories with Acceptance Criteria\n### US-001 — A\nPriority: Must\n")
    _write(project, "06-qa-plan.md", "---\nstatus: approved\n---\n## Functional Test Cases\n"
                                     "### TC-001 — A (covers US-001)\n")
    pkg = project / "handoff" / "dev"
    _write(pkg, ".pm-os-handoff", "marker\n")
    _write(pkg, "stories/US-001-a.md", "---\nstory_id: US-001\nepic: EPIC-001\npriority: Must\n---\n# US-001\n")
    _write(project, "sprint-2/stories/S2-US-01-a.md", _story("S2-US-01"))
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    rc.check_release(pkg)
    rc.check_release(project / "sprint-2")
    after = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert after == before


def test_overdue_readiness_items_block_and_owed_files_only_warn(tmp_path):
    """Backlog #74: with a readiness record in the folder, an eval set not
    starter-ready by its due milestone and a blocking decision past decide-by
    are errors; a referenced file the record lists as owed is a FILE_PENDING
    warning instead of a FILE_REFERENCE_MISSING error. Ids the record declares
    (OD-01) resolve for the undefined-id check."""
    _clean_package(tmp_path)
    _write(tmp_path, "inputs/aimovig.html", "<p>page</p>\n")
    _write(tmp_path, "readiness.yaml", """schema_version: 1
milestones: [M0, M1]
current_milestone: M1
eval_sets:
  - {id: EVAL-001, ai_step: Interpret, requirement: FR-001, reviewer: Anika Kaur,
     starter_count: 30, target_count: 120, due: M1, status: needed}
test_inputs:
  - {id: TI-001, purpose: Bot-protected page, supplier: Karan, needed_by: M1,
     file: inputs/jardiance.html, status: requested}
open_decisions:
  - {id: OD-01, question: 'Emoji-only sentences?', owner: Karan, decide_by: M0,
     blocking: true, status: open}
""")
    _write(tmp_path, "notes.md", "# Notes\n\nTest on `inputs/jardiance.html`; see OD-01.\n")
    report = rc.check_release(tmp_path)
    codes = _codes(report)
    assert codes["READINESS_EVAL_SET_NOT_READY"] == 1
    assert codes["READINESS_DECISION_OVERDUE"] == 1
    assert codes["READINESS_INPUT_MISSING"] == 1
    assert codes["FILE_PENDING"] == 1 and "FILE_REFERENCE_MISSING" not in codes
    assert "ID_UNDEFINED" not in codes


def test_invalid_readiness_record_is_a_release_error(tmp_path):
    """A readiness record that does not validate blocks the release."""
    _clean_package(tmp_path)
    _write(tmp_path, "readiness.yaml", "eval_sets:\n  - {id: EVAL-1, status: maybe}\n")
    assert any(f.code == "READINESS_INVALID" for f in rc.check_release(tmp_path).errors)


def test_zip_is_checked_and_an_escaping_member_is_refused(tmp_path):
    """A `.zip` of a package is checked as its contents (paths relative to the
    archive root); an archive member that would extract outside is refused."""
    src = _clean_package(tmp_path / "src")
    archive = tmp_path / "pkg.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in src.rglob("*"):
            zf.write(path, path.relative_to(src).as_posix())
        zf.writestr("stories/README.md", "[prd](../../PRD.md)\n")
    report = rc.check_release(archive)
    assert report.folder == archive
    assert [(f.code, f.path) for f in report.errors] == [("LINK_BROKEN", "stories/README.md")]
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("../escape.md", "x")
    with pytest.raises(ValueError):
        rc.check_release(bad)


def test_format_report_shows_location_code_and_fix(tmp_path):
    """The text report gives each finding its file:line, code and fix, and ends
    with the error/warning totals the CLI and export gate print."""
    _write(tmp_path, "stories/US-01-a.md", _story("US-01", epic=None))
    text = rc.format_report(rc.check_release(tmp_path), label="pkg")
    assert "ERROR   stories/US-01-a.md:1  STORY_EPIC_MISSING" in text
    assert "Fix: Add `epic:" in text
    assert text.rstrip().endswith("1 error(s), 0 warning(s).")


def test_version_key_tolerates_non_numeric_versions():
    """A hand-built package's `version: draft` or `1.0-rc` orders instead of crashing
    the release check (it used to raise ValueError from int())."""
    assert rc._version_key("1.2") == (1, 2)
    assert rc._version_key("1.0-rc") == (1, 0)
    assert rc._version_key("draft") == (0,)
