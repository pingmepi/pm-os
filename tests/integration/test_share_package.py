"""pm-share package mode (Phase 4a) — the readable projection built by
`scripts/pm_share.py --package`, invoked via `/pm-handoff --package` (the
`pm-share` skill was folded into `pm-handoff`; this script is unchanged).

Approving 01/02/03/06 gives pm_share.py an approved pipeline + a
.traceability.yaml spine. --package assembles per-story files in the boss
house-format by walking US-### -> FR-### -> UJ-### -> covering TC-###, split
into `handoff/{dev,design,qa,business}/` audience folders (2026-07-28
audience-folder rework). It is a read-only projection: it must never touch the
gate/hash/status state machine, every file is stamped with source provenance,
and sections with no source content are flagged (not fabricated). Screen
mentions link into the copied prototype when it carries a matching anchor
(backlog #29).
See docs/guides/testing.md §"Share package mode"."""
import json

import pytest

from helpers import run_script, make_draft

pytestmark = pytest.mark.integration


_BRIEF = """## Target User
Collections users at mid-size banks.
## Overview
Overdue cases pile up because agencies aren't managed in-system.
"""

_SCOPE = """## MVP Boundary
Add and list external agencies. No allocation engine in v1.
"""

_PRD = """## Product Epics
### EPIC-001 — Agency onboarding
**Outcome:** Collections users can add external agencies.
**Scope:** Agency creation and approval state.
**Success signal:** An agency is saved for approval.
### EPIC-002 — Agency discovery
**Outcome:** Collections users can find agencies.
**Scope:** Agency listing.
**Success signal:** Agency list loads within target performance.
## User Journeys
### UJ-001 — Manage agencies
Primary user: Collections user. Traceability: US-001.
## Prioritization Method
MoSCoW. Must items cover the MVP approval path; Should items improve discovery
without blocking first release.
## User Stories with Acceptance Criteria
### US-001 — Add external agency
Priority: Must
Epic: EPIC-001
As a Collections user, I want to add agencies, so that cases can be allocated.
Traceability: UJ-001, FR-001.
Data fields: Agency Code, Status.
Acceptance: agency saved with status Sent for approval.
### US-002 — List agencies
Priority: Should
Epic: EPIC-002
As a user, I want to list agencies.
## Functional Requirements
FR-001 — The system stores agencies.
Priority: Must
Epic: EPIC-001
## Non-Functional Requirements
Performance: list loads under 2s for 10k agencies.
## Impact Analysis
Impacted components: PS, Pitboss.
"""

_QA = """## Functional Test Cases
### TC-001 — Add happy path (covers US-001, FR-001)
Given valid fields, the agency is saved.
### TC-002 — Duplicate code (covers US-001)
Given a duplicate code, an error is returned.
"""


def _approve_pipeline(pmos, proj):
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", _PRD), ("06", _QA)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0


def test_package_generates_per_story_files_with_traceability(pmos, new_project):
    proj = new_project("handoff-e2e", "A problem")
    _approve_pipeline(pmos, proj)

    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode == 0, res.stderr

    pkg = proj / "handoff"
    assert (pkg / "README.md").exists()  # the top-level audience-folder hub
    assert (pkg / "business" / "00-overview.md").exists()
    assert (pkg / "dev" / "epics" / "EPIC-001-agency-onboarding.md").exists()
    assert (pkg / "dev" / "epics" / "EPIC-002-agency-discovery.md").exists()
    assert not (pkg / "dev" / "epics" / "US-001-add-external-agency.md").exists()
    # Epics also duplicate into business (dev + business per the mapping table).
    assert (pkg / "business" / "epics" / "EPIC-001-agency-onboarding.md").exists()

    story = (pkg / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "epic: EPIC-001" in story
    assert "priority: Must" in story
    assert "- **Priority:** Must" in story
    # Assembled from the spine: both covering test cases resolved and listed together.
    assert "TC-001" in story and "TC-002" in story
    assert "TC-001, TC-002" in story  # the joined "Covering test cases" line
    # Authored story content is carried through.
    assert "cases can be allocated" in story
    # Provenance stamp + non-canonical banner.
    assert "03-prd.md@" in story
    assert "DO NOT EDIT HERE" in story
    # Stories are duplicated byte-identical into qa/ (dev+qa per the mapping table).
    assert (pkg / "qa" / "stories" / "US-001-add-external-agency.md").read_text() == story

    # B0: pm-share and pm-handoff must decompose the same approved pipeline with
    # Jira-native refs: Product Epics as Jira Epics, with US-### items as stories.
    # jira-plan.json lands at the handoff/ root, never inside an audience folder.
    assert run_script(pmos, "pm_handoff.py", "plan", cwd=proj).returncode == 0
    plan = json.loads((pkg / "jira-plan.json").read_text())
    jira_epics = {item["ref"] for item in plan["items"] if item["type"] == "Epic"}
    jira_stories = {item["ref"] for item in plan["items"] if item["type"] == "Story"}
    package_epics = {path.name.split("-", 2)[0] + "-" + path.name.split("-", 2)[1] for path in (pkg / "dev" / "epics").glob("EPIC-*.md")}
    assert package_epics == jira_epics == {"EPIC-001", "EPIC-002"}
    assert jira_stories == {"US-001", "US-002"}


def test_package_flags_unsourced_sections_instead_of_fabricating(pmos, new_project):
    proj = new_project("handoff-gaps", "A problem")
    _approve_pipeline(pmos, proj)
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    # US-002 has no covering test case and no FR — those must be flagged, not invented.
    story = (proj / "handoff" / "dev" / "stories" / "US-002-list-agencies.md").read_text()
    assert "— not captured in source —" in story


def test_package_resolves_reverse_declared_fr_and_uj_links(pmos, new_project):
    """A story that never self-cites its FR/UJ ids (only the FR/journey block
    names the story, the other direction) must still resolve them and pull in
    the test cases that trace only to that FR — the fix for backlog #12 (IMP-008,
    Bug B): forward-only regex scanning of the story's own block used to miss this."""
    prd = """## User Journeys
### UJ-001 — Manage agencies
Primary user: Collections user. Traceability: US-001.
## User Stories with Acceptance Criteria
### US-001 — Add external agency
As a Collections user, I want to add agencies, so that cases can be allocated.
## Functional Requirements
- FR-001 (Agency storage) — The system stores agencies. *(US-001)*
"""
    qa = """## Functional Test Cases
### TC-001 — Add happy path (covers FR-001)
Given valid fields, the agency is saved.
"""
    proj = new_project("handoff-reverse", "A problem")
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", prd), ("06", qa)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0

    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0
    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "FR-001" in story
    assert "UJ-001" in story
    assert "TC-001" in story
    # Requirements/journeys/test cases all resolve. (Screens legitimately do not —
    # this project has no approved design spec declaring SCR-### ids.)
    traceability_section = story.split("## Traceability")[-1]
    for line in ("**Requirements:**", "**Journeys:**", "**Covering test cases:**"):
        resolved = next(l for l in traceability_section.splitlines() if line in l)
        assert "— not captured in source —" not in resolved, resolved


def test_package_keeps_full_body_for_single_line_test_cases(pmos, new_project):
    """A single-line-bullet QA scenario (the whole TC on one line, no separate
    body lines) must still render its description in the handoff file — the fix
    for backlog #12 (IMP-008, Bug A): the old strip-first-line logic emptied
    single-line blocks entirely."""
    qa = """## Functional Test Cases
- TC-001: Verify the agency saves with a valid code. Covers US-001, FR-001.
- TC-002: Verify a duplicate code is rejected. Covers US-001.
"""
    proj = new_project("handoff-singleline", "A problem")
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", _PRD), ("06", qa)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0

    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0
    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "Verify the agency saves with a valid code" in story
    assert "Verify a duplicate code is rejected" in story


def test_package_overview_and_reference_docs(pmos, new_project):
    proj = new_project("handoff-ref", "A problem")
    _approve_pipeline(pmos, proj)
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0
    pkg = proj / "handoff"

    assert "Collections users at mid-size banks" in (pkg / "business" / "00-overview.md").read_text()
    assert "MoSCoW" in (pkg / "dev" / "reference" / "prioritization.md").read_text()
    assert "[Prioritization method](reference/prioritization.md)" in (pkg / "dev" / "README.md").read_text()
    assert "Pitboss" in (pkg / "dev" / "reference" / "impact-analysis.md").read_text()
    assert "under 2s" in (pkg / "dev" / "reference" / "nfrs.md").read_text()
    # impact-analysis and nfrs also duplicate into qa (so a dev-only link never dangles
    # in the qa story files, which cite impact-analysis too).
    assert "Pitboss" in (pkg / "qa" / "reference" / "impact-analysis.md").read_text()
    assert "under 2s" in (pkg / "qa" / "reference" / "nfrs.md").read_text()


def test_package_is_read_only_and_does_not_touch_state_machine(pmos, new_project):
    """Generating the package must not change .meta.yaml, artifact hashes, or statuses."""
    proj = new_project("handoff-readonly", "A problem")
    _approve_pipeline(pmos, proj)
    meta_before = (proj / ".meta.yaml").read_text()
    prd_before = (proj / "03-prd.md").read_text()

    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    assert (proj / ".meta.yaml").read_text() == meta_before
    assert (proj / "03-prd.md").read_text() == prd_before


def test_package_requires_a_prd(pmos, new_project):
    """With no approved PRD, the generator refuses rather than emitting an empty package."""
    proj = new_project("handoff-noprd", "A problem")
    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode != 0
    assert "PRD" in (res.stdout + res.stderr)


def test_package_refuses_a_draft_prd(pmos, new_project):
    """A PRD that exists but is only 'draft' (not approved) must be refused — the
    package projects approved decisions only, so an unreviewed PRD must not be
    published as canonical handoff."""
    proj = new_project("handoff-draftprd", "A problem")
    for stage, body in (("01", _BRIEF), ("02", _SCOPE)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    make_draft(proj, "03", body=_PRD)  # draft, never approved

    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode != 0
    assert "approved" in (res.stdout + res.stderr).lower()
    assert not (proj / "handoff").exists()


def test_package_refuses_an_edited_prd(pmos, new_project):
    """`edited` (PRD body drifted after approval) must also be refused, not just
    draft: the changes are unreviewed and the traceability index — rebuilt only at
    approval — is stale relative to the edited body, so covering-test-case
    resolution would mix a current body with a pre-edit index. Re-approval is
    required (Codex PR #32 finding)."""
    import project
    import frontmatter as fm_mod

    proj = new_project("handoff-editedprd", "A problem")
    _approve_pipeline(pmos, proj)

    # Simulate post-approval drift: flip stage 03 to `edited` in both sources of truth.
    meta = project.load_meta(proj)
    project.get_stage(meta, "03")["status"] = "edited"
    project.save_meta(meta, proj)
    fm_mod.update_status(str(project.artifact_path(proj, "03")), "edited")

    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode != 0
    assert "approved" in (res.stdout + res.stderr).lower()
    assert not (proj / "handoff").exists()


def test_package_refuses_destructive_output_dir(pmos, new_project):
    """--output pointing at the project root (or cwd) must be refused before any
    mkdir/audience work, so a stray --output . can never erase .meta.yaml/approved
    artifacts."""
    proj = new_project("handoff-destructive", "A problem")
    _approve_pipeline(pmos, proj)

    res = run_script(pmos, "pm_share.py", "--package", "--output", ".", cwd=proj)
    assert res.returncode != 0
    assert "refusing" in (res.stdout + res.stderr).lower()
    # The project itself is untouched.
    assert (proj / ".meta.yaml").exists()
    assert (proj / "03-prd.md").exists()


def test_package_does_not_touch_unrelated_files_in_output_root(pmos, new_project):
    """--output pointing at an existing directory with unrelated content no longer
    refuses outright: the handoff ROOT is never destructively wiped since the
    audience-folder rework (only handoff/<audience>/ is) — it's just mkdir'd
    non-destructively, so pre-existing unrelated files are left alone and audience
    subfolders are created alongside them."""
    proj = new_project("handoff-unrelated-root", "A problem")
    _approve_pipeline(pmos, proj)
    target = proj / "existing-docs"
    target.mkdir()
    (target / "keepme.md").write_text("important\n", encoding="utf-8")

    res = run_script(pmos, "pm_share.py", "--package", "--output", str(target), cwd=proj)
    assert res.returncode == 0, res.stderr
    assert (target / "keepme.md").exists()
    assert (target / "dev" / ".pm-os-handoff").exists()


def test_package_refuses_existing_unmarked_audience_dir(pmos, new_project):
    """An existing non-empty AUDIENCE subfolder that this tool did not generate (no
    .pm-os-handoff marker) must not be deleted — only a prior package's audience
    folder is cleared. The marker guard now lives one level deeper than the
    handoff root (see _prepare_audience_dir)."""
    proj = new_project("handoff-unmarked", "A problem")
    _approve_pipeline(pmos, proj)
    target = proj / "handoff" / "dev"
    target.mkdir(parents=True)
    (target / "keepme.md").write_text("important\n", encoding="utf-8")

    res = run_script(pmos, "pm_share.py", "--package", "--audience", "dev", cwd=proj)
    assert res.returncode != 0
    assert (target / "keepme.md").exists()

    (target / "keepme.md").unlink()
    target.rmdir()

    # A prior package (carrying the marker) IS safely regenerated in place.
    assert run_script(pmos, "pm_share.py", "--package", "--audience", "dev", cwd=proj).returncode == 0
    assert (proj / "handoff" / "dev" / ".pm-os-handoff").exists()
    assert run_script(pmos, "pm_share.py", "--package", "--audience", "dev", cwd=proj).returncode == 0


def test_package_audience_scoped_rebuild_leaves_others_untouched(pmos, new_project):
    """--audience dev rebuilds only handoff/dev/ — handoff/design/, /qa/, /business/
    (built by an earlier full run) must be byte-for-byte untouched, even after the
    PRD changes and dev/ picks up the change."""
    proj = new_project("handoff-audience-scope", "A problem")
    _approve_pipeline(pmos, proj)
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    other_before = {
        p: p.read_text() for p in (proj / "handoff").rglob("*")
        if p.is_file() and "dev" not in p.relative_to(proj / "handoff").parts
    }
    assert other_before  # sanity: design/qa/business actually produced files

    # Change the PRD and re-approve so dev/ has something new to pick up.
    changed_prd = _PRD.replace("Add external agency", "Add external agency FAST")
    make_draft(proj, "03", body=changed_prd)
    assert run_script(pmos, "pm_approve.py", "03", cwd=proj).returncode == 0

    assert run_script(pmos, "pm_share.py", "--package", "--audience", "dev", cwd=proj).returncode == 0

    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency-fast.md").read_text()
    assert "Add external agency FAST" in story

    for path, content_before in other_before.items():
        assert path.read_text() == content_before, f"{path} changed during a dev-only rebuild"


def test_package_audience_conflict_stops_before_any_content_write(pmos, new_project):
    """If one of several requested audiences has an unmarked-conflict directory,
    the prepare pass raises before the content-write pass begins for ANY audience
    — so no audience folder ends up with stale content silently served. Audiences
    already validated+wiped before the conflicting one (dev, design — "qa" is
    third in the fixed dev/design/qa/business order) are left as empty,
    marker-less directories rather than falsely marked as rebuilt; audiences after
    the conflict (business) are never even created."""
    proj = new_project("handoff-audience-conflict", "A problem")
    _approve_pipeline(pmos, proj)
    conflict = proj / "handoff" / "qa"
    conflict.mkdir(parents=True)
    (conflict / "keepme.md").write_text("important\n", encoding="utf-8")

    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode != 0
    assert (conflict / "keepme.md").exists()
    assert not (proj / "handoff" / "dev" / ".pm-os-handoff").exists()
    assert not (proj / "handoff" / "dev" / "stories").exists()
    assert not (proj / "handoff" / "business").exists()


def test_package_audience_flag_requires_package(pmos, new_project):
    """--audience without --package is a hard error, not a silently ignored flag —
    a load-bearing flag that looks like it should do something must fail loudly."""
    proj = new_project("handoff-audience-noflag", "A problem")
    _approve_pipeline(pmos, proj)
    res = run_script(pmos, "pm_share.py", "--audience", "dev", cwd=proj)
    assert res.returncode != 0
    assert "--package" in (res.stdout + res.stderr)


def test_raw_mode_unchanged_by_the_merge(pmos, new_project):
    """The pre-existing raw-export behavior (single stage or all-approved,
    verbatim text) must be untouched by folding --package in alongside it."""
    proj = new_project("share-raw", "A problem")
    _approve_pipeline(pmos, proj)

    res = run_script(pmos, "pm_share.py", "03", cwd=proj)
    assert res.returncode == 0
    assert "Stage 03" in res.stdout
    assert "As a Collections user" in res.stdout
    # Raw mode must not create a handoff/ package as a side effect.
    assert not (proj / "handoff").exists()


_DESIGN = """## Information Architecture
- **SCR-001 — Agency list**
  - Purpose: the landing surface listing every agency.
  - Serves: US-001, US-002, UJ-001
- **SCR-002 — Add agency form**
  - Purpose: capture a new agency.
  - Serves: US-001
## Journey-to-Flow Traceability
UJ-001 enters at SCR-001 and completes at SCR-002.
## Key User Flows
Add flow.
## Product UX Guardrails
Interaction model: non-AI
## Design Principles
Clarity.
## Component Inventory
Table, form.
## Typography
Scale.
## Color Tokens
Tokens.
## Spacing Tokens
Scale.
## Iconography
Set.
## Accessibility Notes
Keyboard order and labels.
"""


def _project_with_screens(pmos, new_project, slug="handoff-screen-gate"):
    """Scaffold and approve the pipeline used by the screen tests (01/02/03/04/06),
    returning the project root with a fully approved, screen-bearing design spec."""
    proj = new_project(slug, "A problem")
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", _PRD), ("04", _DESIGN), ("06", _QA)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    return proj


def test_package_maps_screens_to_each_story(pmos, new_project):
    """With an approved design spec declaring SCR-### screens, each story file lists the
    screens it touches (resolved through the spine, via its requirements *and* journeys)
    and the design spec joins the story's provenance stamps."""
    proj = new_project("handoff-screens", "A problem")
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", _PRD), ("04", _DESIGN), ("06", _QA)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "## Screens this story touches" in story
    assert "SCR-001 · Agency list" in story and "SCR-002 · Add agency form" in story
    assert "the landing surface listing every agency" in story  # the screen's own body
    assert "**Screens:** SCR-001, SCR-002" in story
    assert "04-design-spec.md@" in story  # provenance includes the design spec

    # US-002 is served by SCR-001 only.
    other = (proj / "handoff" / "dev" / "stories" / "US-002-list-agencies.md").read_text()
    assert "**Screens:** SCR-001" in other and "SCR-002" not in other


def test_package_screen_map_reference_lists_coverage_both_ways(pmos, new_project):
    """reference/screen-map.md is the reverse view — each screen with what it serves —
    and names any story no screen covers, so a design gap is visible at handoff."""
    proj = new_project("handoff-screenmap", "A problem")
    design = _DESIGN.replace("  - Serves: US-001, US-002, UJ-001\n", "  - Serves: US-001, UJ-001\n")
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", _PRD), ("04", design), ("06", _QA)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    screen_map = (proj / "handoff" / "design" / "reference" / "screen-map.md").read_text()
    assert "| SCR-001 | Agency list | US-001, UJ-001 |" in screen_map
    assert "## Stories with no screen" in screen_map
    assert "US-002 · List agencies" in screen_map
    assert "04-design-spec.md@" in screen_map  # stamped with its source
    assert "[Screen map](reference/screen-map.md)" in (proj / "handoff" / "design" / "README.md").read_text()
    # screen-map is duplicated into qa/ too (design + qa per the mapping table).
    assert (proj / "handoff" / "qa" / "reference" / "screen-map.md").read_text() == screen_map


def test_screen_map_counts_journey_only_coverage_as_covered(pmos, new_project):
    """A screen that serves only a journey (SCR-001 → UJ-001, and UJ-001 → US-001) must
    NOT list US-001 under "Stories with no screen": its own story file already shows the
    screen via journey resolution, so the reverse map has to agree. Guards against the
    map deriving coverage from each screen's literal `serves` ids. See docs/guides/testing.md §6."""
    proj = new_project("handoff-journey-coverage", "A problem")
    # No screen names US-001 directly: SCR-001 serves only UJ-001 (and UJ-001 → US-001),
    # SCR-002 serves US-002. So US-001 is covered *purely* through its journey link.
    design = (
        _DESIGN
        .replace("  - Serves: US-001, US-002, UJ-001\n", "  - Serves: UJ-001\n")
        .replace("  - Serves: US-001\n", "  - Serves: US-002\n")
    )
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", _PRD), ("04", design), ("06", _QA)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    # The story file resolves SCR-001 through the journey.
    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "SCR-001" in story
    # ...and the reverse map must not contradict it: both stories are covered, so no
    # story may appear under "Stories with no screen". Deriving coverage from each
    # screen's literal `serves` ids (the bug) would report US-001 uncovered here.
    screen_map = (proj / "handoff" / "design" / "reference" / "screen-map.md").read_text()
    tail = screen_map.split("## Stories with no screen")[-1] if "## Stories with no screen" in screen_map else ""
    assert "US-001 · Add external agency" not in tail, "US-001 is covered via its journey but reported uncovered"
    assert "US-002 · List agencies" not in tail


def test_package_without_screen_ids_degrades_gracefully(pmos, new_project):
    """A project with no approved design spec (or one predating SCR-### ids) still
    packages: stories show the not-captured marker for screens and the screen map
    explains what to add — no crash, no fabrication."""
    proj = new_project("handoff-noscreens", "A problem")
    _approve_pipeline(pmos, proj)
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "**Screens:** — not captured in source —" in story
    screen_map = (proj / "handoff" / "design" / "reference" / "screen-map.md").read_text()
    assert "— not captured in source —" in screen_map
    assert "SCR-###" in screen_map  # tells the PM how to fix it


def test_package_excludes_screens_from_an_unapproved_design_spec(pmos, new_project):
    """A design spec that is drafted (or edited/stale after approval) contributes no
    screens: neither the per-story sections nor reference/screen-map.md may present
    unapproved design decisions as handoff material. Mirrors the rule build_index
    already applies to stage 04. See docs/guides/testing.md §6 (T_share)."""
    import frontmatter
    import project

    proj = _project_with_screens(pmos, new_project, "handoff-screen-unapproved")
    # Re-open the approved design spec as a draft carrying a brand-new screen.
    path = project.artifact_path(proj, "04")
    fm, body = frontmatter.read(str(path))
    # The new screen must land *inside* Information Architecture — that is the only
    # section screens are parsed from, so appending at the end would prove nothing.
    unapproved = body.replace(
        "## Journey-to-Flow Traceability",
        "- **SCR-099 — Unreleased admin console**\n"
        "  - Purpose: an unreleased surface.\n"
        "  - Serves: US-001\n"
        "## Journey-to-Flow Traceability",
    )
    assert "SCR-099" in unapproved
    frontmatter.write(str(path), {**fm, "status": "draft"}, unapproved)
    meta = project.load_meta(proj)
    project.get_stage(meta, "04")["status"] = "draft"
    project.save_meta(meta, proj)

    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode == 0, res.stderr
    pkg = proj / "handoff"
    screen_map = (pkg / "design" / "reference" / "screen-map.md").read_text()
    assert "SCR-099" not in screen_map, "unapproved screen leaked into the package"
    assert "Unreleased admin console" not in screen_map
    story = next((pkg / "dev" / "stories").glob("US-001-*.md")).read_text()
    assert "SCR-099" not in story


def test_package_resolves_screens_from_a_stale_on_disk_index(pmos, new_project):
    """Screens resolve even when .traceability.yaml predates them (schema v2, no
    screens map) — the package builds the spine fresh rather than trusting the file,
    so a project that last rebuilt before this release is not silently screenless."""
    proj = _project_with_screens(pmos, new_project, "handoff-screen-stale-index")
    # Simulate a pre-screens index: strip the screens map and reverse links.
    import yaml
    tpath = proj / ".traceability.yaml"
    index = yaml.safe_load(tpath.read_text())
    index["schema_version"] = 2
    index.pop("screens", None)
    for entry in (index.get("requirements") or {}).values():
        entry.pop("screens", None)
    tpath.write_text(yaml.safe_dump(index, sort_keys=True))

    res = run_script(pmos, "pm_share.py", "--package", cwd=proj)
    assert res.returncode == 0, res.stderr
    story = next((proj / "handoff" / "dev" / "stories").glob("US-001-*.md")).read_text()
    assert "SCR-001" in story, "stale on-disk index silently hid the screens"


# --- screen links into the prototype (backlog #29) ---------------------------

def test_screen_link_emitted_when_anchor_present(pmos, new_project):
    """When the copied prototype carries a matching id="SCR-###" anchor, both the
    story file and the screen map link straight to it."""
    proj = _project_with_screens(pmos, new_project, "handoff-screen-link-anchored")
    (proj / "05-prototype-mockup.html").write_text(
        '<!doctype html><html><body>'
        '<section id="SCR-001">Agency list</section>'
        '<section id="SCR-002">Add agency form</section>'
        "</body></html>",
        encoding="utf-8",
    )
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "../wireframes/prototype.html#SCR-001" in story
    assert "../wireframes/prototype.html#SCR-002" in story

    screen_map = (proj / "handoff" / "design" / "reference" / "screen-map.md").read_text()
    assert "../wireframes/prototype.html#SCR-001" in screen_map

    # The prototype itself is duplicated into dev (not just design/qa), since dev
    # stories now link into it.
    assert (proj / "handoff" / "dev" / "wireframes" / "prototype.html").exists()


def test_screen_link_falls_back_when_anchor_absent(pmos, new_project):
    """A prototype that predates the anchor requirement (backlog #29) still gets
    copied in and linked to — just without a working hash, never a dead link, and
    the design spec's screen bodies are always shown either way."""
    proj = _project_with_screens(pmos, new_project, "handoff-screen-link-noanchor")
    (proj / "05-prototype-mockup.html").write_text(
        "<!doctype html><html><body><div>No anchors here.</div></body></html>",
        encoding="utf-8",
    )
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "#SCR-001" not in story
    assert "../wireframes/prototype.html" in story  # plain link, not a dead hash


def test_screen_link_omitted_without_a_prototype(pmos, new_project):
    """No 05-prototype-mockup.html at all: screens still resolve and render, they
    just carry no prototype link and no wireframes/ folder is created."""
    proj = _project_with_screens(pmos, new_project, "handoff-screen-link-noproto")
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "SCR-001" in story
    assert "prototype.html" not in story
    assert not (proj / "handoff" / "dev" / "wireframes").exists()


# --- backend work: TRD tasks per story (option 1) ----------------------------

_TRD = """## Architecture
Layered services over the existing agency store.
## Work Breakdown
### TSK-001 — Build the agency store write path
- **Implements:** FR-001
### TSK-002 — Add the agency-list query
- **Implements:** FR-001
"""


def test_package_maps_backend_tasks_to_each_story(pmos, new_project):
    """With an approved TRD, each story file lists the TSK-### backend tasks that
    implement its requirements (resolved through the spine over the story's FRs),
    carries each task's body, adds a "Backend tasks:" traceability line, and the
    TRD joins the story's provenance stamps."""
    proj = new_project("handoff-backend", "A problem")
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", _PRD), ("06", _QA), ("08", _TRD)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "## Backend work (TRD tasks)" in story
    assert "TSK-001" in story and "TSK-002" in story
    assert "Build the agency store write path" in story  # the task's own body
    assert "**Backend tasks:** TSK-001, TSK-002" in story
    assert "08-trd.md@" in story  # provenance includes the TRD

    # US-002 cites no FR, so no task implements it — backend work is flagged, not invented.
    other = (proj / "handoff" / "dev" / "stories" / "US-002-list-agencies.md").read_text()
    assert "## Backend work (TRD tasks)" in other
    assert "**Backend tasks:** — not captured in source —" in other


def test_package_without_trd_degrades_backend_to_not_captured(pmos, new_project):
    """A project with no approved TRD still packages: the Backend work section and
    the traceability line show the not-captured marker rather than being omitted or
    fabricated — the same graceful degradation as screens without a design spec."""
    proj = new_project("handoff-no-trd", "A problem")
    _approve_pipeline(pmos, proj)
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "## Backend work (TRD tasks)" in story
    assert "**Backend tasks:** — not captured in source —" in story
    assert "08-trd.md@" not in story  # no TRD in provenance when there are no tasks


def test_story_frontmatter_is_valid_yaml_when_title_has_colon(pmos, new_project):
    """Regression for backlog #33: a story title containing a colon-space (e.g.
    'Search: filters and sort') produced invalid YAML frontmatter, because the
    template interpolated the title unquoted (`title: Search: filters and sort`).
    The rendered story's frontmatter must parse and round-trip the title."""
    import frontmatter

    proj = new_project("story-yaml", "A problem")
    prd = _PRD.replace("### US-001 — Add external agency",
                       "### US-001 — Search: filters and sort")
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", prd), ("06", _QA)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    stories_dir = proj / "handoff" / "dev" / "stories"
    matches = list(stories_dir.glob("US-001-*.md"))
    assert len(matches) == 1, [p.name for p in stories_dir.glob("*.md")]
    fm, _body = frontmatter.read(str(matches[0]))  # raises yaml.YAMLError if invalid
    assert fm["title"] == "Search: filters and sort"
    assert fm["story_id"] == "US-001"


def test_business_epic_has_no_dangling_story_links(pmos, new_project):
    """Regression for backlog #34: business epic files linked into ../stories/, but
    the business audience gets no stories/ folder, so every link dangled. Business
    epics must reference stories as plain text; dev epics (which have stories) keep
    working links that resolve."""
    proj = new_project("epic-links", "A problem")
    _approve_pipeline(pmos, proj)
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0
    pkg = proj / "handoff"

    biz_epic = (pkg / "business" / "epics" / "EPIC-001-agency-onboarding.md").read_text()
    assert "US-001" in biz_epic                    # story still referenced
    assert "../stories/" not in biz_epic           # but not as a dangling link
    assert not (pkg / "business" / "stories").exists()

    dev_epic = (pkg / "dev" / "epics" / "EPIC-001-agency-onboarding.md").read_text()
    assert "](../stories/US-001-add-external-agency.md)" in dev_epic  # dev link present...
    assert (pkg / "dev" / "stories" / "US-001-add-external-agency.md").exists()  # ...and resolves


def test_journey_shared_screen_not_attributed_to_every_story(pmos, new_project):
    """Regression for backlog #36: a screen serving one story directly plus a shared
    journey was attributed to *every* story in that journey. A screen that names
    specific stories/requirements must go only to those; the journey fallback applies
    only to screens that name no story/requirement directly (preserving the
    journey-only coverage case)."""
    proj = new_project("screen-journey-scope", "A problem")
    # Put both US-001 and US-002 in journey UJ-001.
    prd = _PRD.replace(
        "Primary user: Collections user. Traceability: US-001.",
        "Primary user: Collections user. Traceability: US-001, US-002.",
    )
    # SCR-001 is a shared list screen (serves both stories directly); SCR-002 is
    # US-001's detail screen, tagged with the shared journey. US-002 shares only the
    # journey, so it must NOT pick up SCR-002.
    design = (
        _DESIGN
        .replace("  - Serves: US-001, US-002, UJ-001\n", "  - Serves: US-001, US-002\n")
        .replace("  - Serves: US-001\n", "  - Serves: US-001, UJ-001\n")
    )
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", prd), ("04", design), ("06", _QA)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    us1 = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "**Screens:** SCR-001, SCR-002" in us1  # US-001 keeps both — direct
    us2 = (proj / "handoff" / "dev" / "stories" / "US-002-list-agencies.md").read_text()
    assert "**Screens:** SCR-001" in us2  # direct shared screen
    assert "SCR-002" not in us2           # not pulled in via the shared journey


def test_global_ia_prose_does_not_leak_into_story_screen_body(pmos, new_project):
    """Regression for backlog #35: trailing Information-Architecture prose not under
    its own heading was absorbed into the preceding screen's block and copied verbatim
    into every story touching that screen. A story's screen body must contain only the
    screen's own content, not the global narrative."""
    proj = new_project("screen-prose-leak", "A problem")
    # Stray global prose after SCR-002's sub-bullets, before the next heading — the
    # shape that leaks (the fixture's own trailing prose sits under a ## heading and is
    # bounded correctly).
    design = _DESIGN.replace(
        "  - Serves: US-001\n## Journey-to-Flow Traceability",
        "  - Serves: US-001\nAll screens share the global header and left nav.\n"
        "## Journey-to-Flow Traceability",
    )
    for stage, body in (("01", _BRIEF), ("02", _SCOPE), ("03", _PRD), ("04", design), ("06", _QA)):
        make_draft(proj, stage, body=body)
        assert run_script(pmos, "pm_approve.py", stage, cwd=proj).returncode == 0
    assert run_script(pmos, "pm_share.py", "--package", cwd=proj).returncode == 0

    story = (proj / "handoff" / "dev" / "stories" / "US-001-add-external-agency.md").read_text()
    assert "SCR-002 · Add agency form" in story        # the screen is present...
    assert "capture a new agency" in story             # ...with its own body kept...
    assert "All screens share the global header" not in story  # ...but not the global prose
