"""Unit coverage for the T10 consistency checker (lib/consistency.py).

Covers invariants with no natural home in the correlated existing suites
(schema/stage shape, missing artifact, context/sources YAML parseability)
plus cross-cutting sanity on check_project/format_report/summary_line. The
telemetry-chain, body-hash-drift, meta<->frontmatter-sync, and
upstream-approval-shape invariants are additionally asserted in place inside
test_telemetry.py, test_hashing.py, test_project.py,
test_approval_and_staleness.py, and test_stage_gates.py (see their `# T10:`
comments), reusing those tests' own fixtures rather than duplicating them here.
"""
from pathlib import Path

import pytest
import yaml

import consistency
import frontmatter
from hashing import hash_artifact_body

pytestmark = pytest.mark.unit


def _write_meta(tmp_path: Path, stages: list, schema_version=4) -> Path:
    meta = {
        "schema_version": schema_version,
        "project_slug": "consistency-test",
        "stages": stages,
    }
    (tmp_path / ".meta.yaml").write_text(yaml.dump(meta, sort_keys=False), encoding="utf-8")
    return tmp_path


def _stage(stage_id, status="pending", origin="generated", content_hash=None):
    return {"id": stage_id, "status": status, "origin": origin, "content_hash": content_hash}


def _approved_stage00(tmp_path: Path) -> dict:
    """Write a real, approved 00-business-statement.md and return its meta stage entry."""
    path = tmp_path / "00-business-statement.md"
    body = "# Statement\n\nSomething.\n"
    frontmatter.write(str(path), {"status": "approved", "content_hash": None}, body)
    h = hash_artifact_body(str(path))
    frontmatter.write(str(path), {"status": "approved", "content_hash": h}, body)
    return _stage("00", status="approved", origin="generated", content_hash=h)


# --- Schema / stage shape (invariant 5) ----------------------------------------
# Tested against the private helper directly: check_project()'s call to
# project.load_meta() auto-migrates schema_version/origin in memory (and
# persists the fix to disk) before this invariant ever runs, so a project-level
# fixture can't reliably exercise a missing/invalid schema_version end-to-end.

def test_missing_schema_version_is_an_error():
    issues = consistency._check_schema_and_stage_shape({"stages": []})
    assert any(i.code == consistency.CODE_SCHEMA_VERSION_MISSING for i in issues)


def test_stage_missing_required_field_is_an_error():
    meta = {"schema_version": 4, "stages": [{"id": "01", "status": "draft"}]}  # no origin
    issues = consistency._check_schema_and_stage_shape(meta)
    assert any(i.code == consistency.CODE_STAGE_SHAPE_INVALID and i.stage == "01" for i in issues)


def test_unknown_stage_id_is_an_error():
    meta = {"schema_version": 4, "stages": [_stage("99")]}
    issues = consistency._check_schema_and_stage_shape(meta)
    assert any(i.code == consistency.CODE_STAGE_SHAPE_INVALID for i in issues)


def test_invalid_status_value_is_an_error():
    meta = {"schema_version": 4, "stages": [_stage("01", status="bogus")]}
    issues = consistency._check_schema_and_stage_shape(meta)
    assert any(i.code == consistency.CODE_STAGE_SHAPE_INVALID for i in issues)


def test_invalid_origin_value_is_an_error():
    meta = {"schema_version": 4, "stages": [_stage("01", origin="bogus")]}
    issues = consistency._check_schema_and_stage_shape(meta)
    assert any(i.code == consistency.CODE_STAGE_SHAPE_INVALID for i in issues)


def test_healthy_meta_has_no_shape_issues():
    meta = {"schema_version": 4, "stages": [_stage("00", status="approved")]}
    assert consistency._check_schema_and_stage_shape(meta) == []


# --- Missing artifact file (invariant 6) ----------------------------------------

def test_non_pending_stage_missing_artifact_is_an_error(tmp_path):
    _write_meta(tmp_path, [_stage("00", status="approved")])  # no file written
    issues = consistency.check_project(tmp_path)
    assert any(i.code == consistency.CODE_ARTIFACT_MISSING and i.stage == "00" for i in issues)


def test_pending_stage_missing_artifact_is_not_an_error(tmp_path):
    stage00 = _approved_stage00(tmp_path)
    _write_meta(tmp_path, [stage00, _stage("02", status="pending")])
    issues = consistency.check_project(tmp_path)
    assert not any(i.code == consistency.CODE_ARTIFACT_MISSING for i in issues)


# --- Context / sources YAML parse (invariant 7) --------------------------------

def test_absent_context_and_sources_yaml_is_healthy(tmp_path):
    stage00 = _approved_stage00(tmp_path)
    _write_meta(tmp_path, [stage00])
    issues = consistency.check_project(tmp_path)
    assert not any(
        i.code in (consistency.CODE_CONTEXT_YAML_UNPARSEABLE, consistency.CODE_SOURCES_YAML_UNPARSEABLE)
        for i in issues
    )


def test_malformed_context_yaml_is_an_error(tmp_path):
    stage00 = _approved_stage00(tmp_path)
    _write_meta(tmp_path, [stage00])
    ctx_dir = tmp_path / "context"
    ctx_dir.mkdir()
    (ctx_dir / "context.yaml").write_text("key: [unclosed", encoding="utf-8")
    issues = consistency.check_project(tmp_path)
    assert any(i.code == consistency.CODE_CONTEXT_YAML_UNPARSEABLE for i in issues)


def test_malformed_sources_yaml_is_an_error(tmp_path):
    stage00 = _approved_stage00(tmp_path)
    _write_meta(tmp_path, [stage00])
    (tmp_path / ".sources.yaml").write_text("key: [unclosed", encoding="utf-8")
    issues = consistency.check_project(tmp_path)
    assert any(i.code == consistency.CODE_SOURCES_YAML_UNPARSEABLE for i in issues)


def test_valid_context_and_sources_yaml_is_healthy(tmp_path):
    stage00 = _approved_stage00(tmp_path)
    _write_meta(tmp_path, [stage00])
    ctx_dir = tmp_path / "context"
    ctx_dir.mkdir()
    (ctx_dir / "context.yaml").write_text("global: []\n", encoding="utf-8")
    (tmp_path / ".sources.yaml").write_text("sources: []\n", encoding="utf-8")
    issues = consistency.check_project(tmp_path)
    assert not any(
        i.code in (consistency.CODE_CONTEXT_YAML_UNPARSEABLE, consistency.CODE_SOURCES_YAML_UNPARSEABLE)
        for i in issues
    )


# --- Cross-cutting / whole-function sanity --------------------------------------

def test_healthy_project_returns_empty_list(tmp_path):
    stage00 = _approved_stage00(tmp_path)
    _write_meta(tmp_path, [stage00])
    assert consistency.check_project(tmp_path) == []


def test_format_report_empty_is_healthy_message():
    assert "consistent" in consistency.format_report([]).lower()


def test_format_report_groups_errors_and_warnings():
    issues = [
        consistency.Issue("SOME_ERROR", "error", "01", "bad thing", "fix it"),
        consistency.Issue("SOME_WARNING", "warning", "02", "meh thing", "maybe fix it"),
    ]
    report = consistency.format_report(issues)
    assert "Errors (1)" in report
    assert "Warnings (1)" in report
    assert "SOME_ERROR" in report and "SOME_WARNING" in report


def test_summary_line_variants():
    assert consistency.summary_line([]) == "Consistency: healthy"

    warn_only = [consistency.Issue("W", "warning", None, "m", "r")]
    warn_line = consistency.summary_line(warn_only)
    assert "warning" in warn_line and "error" not in warn_line

    with_error = [consistency.Issue("E", "error", None, "m", "r")]
    error_line = consistency.summary_line(with_error)
    assert "error" in error_line and "/pm-check" in error_line


def test_issue_as_dict_shape():
    issue = consistency.Issue("CODE", "error", "01", "message", "remediation")
    assert set(issue.as_dict().keys()) == {"code", "severity", "stage", "message", "remediation"}
