"""The readiness record: what the build team is owed (backlog #74).

`readiness.yaml` at the project root lists three kinds of owed items:

- eval sets, one per AI step, citing the requirement it evaluates, with a
  named reviewer, the starter count needed at kick-off, a target count, the
  milestone it is due by and a status;
- test inputs: what each real input file is for, who supplies it, the
  milestone that needs it, and its status;
- open decisions (`OD-###`), linked to the epics and stories they block, with
  an owner, a decide-by milestone and a status.

It is **ungated**, following the `delivery.yaml` design in
`docs/plans/pm-os-modes-delivery-and-handoff-plan.md` Part B: status changes
weekly, so it is not a stage artifact, is never hashed or approved, and never
makes anything stale. The agent edits it on the PM's behalf (PM decision
2026-10-21); this module only scaffolds and validates it, and answers which
items are overdue, for `/pm-check`, `scripts/pm_readiness.py` and the release
check.

"Overdue" is measured in milestones, not dates: `milestones` lists them in
order and `current_milestone` says where the project is. An item due at or
before the current milestone and not done is overdue.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

READINESS_FILE = "readiness.yaml"
SCHEMA_VERSION = 1

EVAL_STATUSES = ("needed", "in_review", "starter_ready", "complete")
EVAL_READY = ("starter_ready", "complete")
INPUT_STATUSES = ("requested", "received", "not_needed")
INPUT_DONE = ("received", "not_needed")
DECISION_STATUSES = ("open", "decided", "dropped")

_ID_FORMATS = {"eval_sets": r"EVAL-\d{3,}", "test_inputs": r"TI-\d{3,}", "open_decisions": r"OD-\d{2,}"}
_STATUSES = {"eval_sets": EVAL_STATUSES, "test_inputs": INPUT_STATUSES, "open_decisions": DECISION_STATUSES}
_DUE_KEY = {"eval_sets": "due", "test_inputs": "needed_by", "open_decisions": "decide_by"}
_REQUIRED = {
    "eval_sets": ("id", "ai_step", "requirement", "reviewer", "starter_count", "target_count", "status"),
    "test_inputs": ("id", "purpose", "supplier", "status"),
    "open_decisions": ("id", "question", "owner", "status"),
}

TEMPLATE = """\
# PM-OS readiness record (backlog #74): what the build team is owed.
# Ungated: editing this file never needs approval and never makes a stage stale.
# Ask the agent to update it ("the interpretation golden set is starter-ready");
# it edits this file and re-checks it with /pm-check.
schema_version: 1

# Milestones in order, and where the project is now. An item due at or before
# current_milestone that is not done is overdue, and blocks a handoff release.
milestones: []            # e.g. [M0, M1, M2, M3, M4]
current_milestone: null   # e.g. M0

# One per AI step. The reviewer is a named person, not a role.
# status: needed | in_review | starter_ready | complete
eval_sets: []
#  - id: EVAL-001
#    ai_step: Interpret recommendations
#    requirement: FR-012
#    reviewer: Anika Kaur
#    starter_count: 30      # needed at kick-off
#    target_count: 120
#    have_count: 0
#    due: M1
#    status: needed

# Real input files the build needs. `file` (optional) is a path in the project.
# status: requested | received | not_needed
test_inputs: []
#  - id: TI-001
#    purpose: A bot-protected brand page
#    supplier: Karan
#    needed_by: M0
#    file: inputs/jardiance.html
#    status: requested

# Decisions still open. blocking: true means the build cannot finish without it.
# status: open | decided | dropped (record the outcome in `decision`)
open_decisions: []
#  - id: OD-001
#    question: Do emoji-only sentences belong in the snapshot?
#    epics: [EPIC-002]
#    stories: [US-004]
#    owner: Karan
#    decide_by: M1
#    blocking: true
#    status: open
#    decision: ''
"""


@dataclass(frozen=True)
class ReadinessIssue:
    severity: str      # error | warning
    code: str
    item: str | None   # EVAL-001 / TI-002 / OD-003, or None for the file
    message: str
    fix: str


def path_for(project_root: Path | str) -> Path:
    return Path(project_root) / READINESS_FILE


def scaffold(project_root: Path | str) -> tuple[Path, bool]:
    """Write the commented template if the file is absent. Never overwrites."""
    path = path_for(project_root)
    if path.exists():
        return path, False
    path.write_text(TEMPLATE, encoding="utf-8")
    return path, True


def load(path: Path | str) -> tuple[dict | None, ReadinessIssue | None]:
    """Parse a readiness file. Returns (data, None), (None, issue) when it
    can't be read, or (None, None) when there is no file."""
    path = Path(path)
    if not path.is_file():
        return None, None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        return None, ReadinessIssue("error", "READINESS_INVALID_YAML", None,
                                    f"{path.name} is not valid YAML: {exc}".splitlines()[0],
                                    f"Fix the YAML syntax in {path.name}.")
    if not isinstance(data, dict):
        return None, ReadinessIssue("error", "READINESS_INVALID_YAML", None,
                                    f"{path.name} must be a mapping of keys, not a list or value.",
                                    f"Start {path.name} from the template (`pm_readiness.py init` on a fresh file).")
    return data, None


def _milestone_index(data: dict) -> dict[str, int]:
    return {str(m): i for i, m in enumerate(data.get("milestones") or [])}


def validate(data: dict, declared_ids: set[str] | None = None) -> list[ReadinessIssue]:
    """Structural checks. ``declared_ids`` (from the approved PRD) turns a
    requirement/epic/story reference to an id nobody declares into a warning."""
    issues: list[ReadinessIssue] = []

    def add(severity, code, item, message, fix):
        issues.append(ReadinessIssue(severity, code, item, message, fix))

    if data.get("schema_version") not in (None, SCHEMA_VERSION):
        add("error", "READINESS_SCHEMA_VERSION", None,
            f"schema_version is {data.get('schema_version')!r}; this PM-OS reads version {SCHEMA_VERSION}.",
            "Update PM-OS, or set schema_version: 1.")
    milestones = data.get("milestones") or []
    if not isinstance(milestones, list):
        add("error", "READINESS_MILESTONES_INVALID", None, "`milestones` must be a list.",
            "Write it as a list, e.g. `milestones: [M0, M1, M2]`.")
        milestones = []
    order = _milestone_index({"milestones": milestones})
    current = data.get("current_milestone")
    if current is not None and str(current) not in order:
        add("error", "READINESS_MILESTONE_UNKNOWN", None,
            f"current_milestone {current!r} is not in `milestones`.",
            "Add it to `milestones`, or correct the name.")

    seen: set[str] = set()
    for section, required in _REQUIRED.items():
        rows = data.get(section) or []
        if not isinstance(rows, list):
            add("error", "READINESS_SECTION_INVALID", None, f"`{section}` must be a list.",
                f"Write `{section}:` as a list of items, one `- id: …` per item.")
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                add("error", "READINESS_ITEM_INVALID", None, f"{section}[{index}] is not a mapping.",
                    "Give each item keys such as `id:` and `status:`.")
                continue
            item = str(row.get("id") or f"{section}[{index}]")
            missing = [key for key in required if row.get(key) in (None, "")]
            if missing:
                add("error", "READINESS_FIELDS_MISSING", item,
                    f"{item} is missing: {', '.join(missing)}.", f"Fill in {', '.join(missing)} for {item}.")
            if row.get("id") and not re.fullmatch(_ID_FORMATS[section], str(row["id"])):
                add("error", "READINESS_ID_FORMAT", item,
                    f"{item} does not look like {_ID_FORMATS[section].split(chr(92))[0]}###.",
                    f"Number {section} items {_ID_FORMATS[section].split(chr(92))[0]}001, …002, …")
            if row.get("id"):
                if item in seen:
                    add("error", "READINESS_ID_DUPLICATE", item, f"{item} appears more than once.",
                        "Give each item its own id.")
                seen.add(item)
            status = row.get("status")
            if status not in (None, "") and status not in _STATUSES[section]:
                add("error", "READINESS_STATUS_INVALID", item,
                    f"{item} has status {status!r}.", f"Use one of: {', '.join(_STATUSES[section])}.")
            due = row.get(_DUE_KEY[section])
            # The due milestone is required once the project has milestones; before
            # that, a fresh record seeded by stage 03/06 stays valid.
            if due in (None, "") and order:
                add("error", "READINESS_FIELDS_MISSING", item,
                    f"{item} has no {_DUE_KEY[section]} milestone.",
                    f"Set {_DUE_KEY[section]} to one of: {', '.join(order)}.")
            if due not in (None, "") and order and str(due) not in order:
                add("error", "READINESS_MILESTONE_UNKNOWN", item,
                    f"{item} is due at {due!r}, which is not in `milestones`.",
                    "Use a milestone listed in `milestones`.")
            if section == "eval_sets":
                starter, target = row.get("starter_count"), row.get("target_count")
                counts = [c for c in (starter, target, row.get("have_count")) if c is not None]
                if any(not isinstance(c, int) or c < 0 for c in counts):
                    add("error", "READINESS_COUNT_INVALID", item, f"{item} has a count that is not a whole number.",
                        "Use whole numbers for starter_count, target_count and have_count.")
                elif isinstance(starter, int) and isinstance(target, int) and starter > target:
                    add("warning", "READINESS_STARTER_ABOVE_TARGET", item,
                        f"{item}: starter_count {starter} is above target_count {target}.",
                        "Check the two counts.")
                reviewer = str(row.get("reviewer") or "")
                if reviewer and re.fullmatch(r"(?i)(the\s+)?(strategist|reviewer|qa|product|pm|team|tbd|tbc)s?", reviewer.strip()):
                    add("warning", "READINESS_REVIEWER_IS_A_ROLE", item,
                        f"{item}: reviewer {reviewer!r} is a role, not a person.",
                        "Name the person who will review the expected outputs.")
            if declared_ids:
                refs = []
                if section == "eval_sets" and row.get("requirement"):
                    refs.append(str(row["requirement"]))
                if section == "open_decisions":
                    refs += [str(r) for r in (row.get("epics") or []) + (row.get("stories") or [])]
                for ref in refs:
                    if ref.upper() not in declared_ids:
                        add("warning", "READINESS_UNKNOWN_REFERENCE", item,
                            f"{item} cites {ref}, which the PRD does not declare.",
                            f"Correct the id, or declare {ref} in 03-prd.md.")
    return issues


def overdue(data: dict) -> list[dict]:
    """Items due at or before `current_milestone` that are not done.

    Each is `{section, id, due, status, summary, blocking}`. Eval sets are
    overdue until starter_ready; test inputs until received or not_needed;
    open decisions only when `blocking: true` and still open.
    """
    order = _milestone_index(data)
    current = data.get("current_milestone")
    if current is None or str(current) not in order:
        return []
    now = order[str(current)]
    found: list[dict] = []
    for section in _REQUIRED:
        for row in data.get(section) or []:
            if not isinstance(row, dict):
                continue
            due = row.get(_DUE_KEY[section])
            if due is None or str(due) not in order or order[str(due)] > now:
                continue
            status = row.get("status")
            if section == "eval_sets" and status in EVAL_READY:
                continue
            if section == "test_inputs" and status in INPUT_DONE:
                continue
            if section == "open_decisions" and (status != "open" or not row.get("blocking")):
                continue
            summary = row.get("ai_step") or row.get("purpose") or row.get("question") or ""
            found.append({"section": section, "id": row.get("id"), "due": str(due), "status": status,
                          "summary": str(summary), "blocking": section != "open_decisions" or bool(row.get("blocking"))})
    return found


def pending_files(data: dict | None) -> set[str]:
    """POSIX paths of test-input files still owed (not yet received)."""
    if not data:
        return set()
    return {
        str(row["file"]).replace("\\", "/").removeprefix("./")
        for row in data.get("test_inputs") or []
        if isinstance(row, dict) and row.get("file") and row.get("status") not in INPUT_DONE
    }


def summary(data: dict | None) -> dict:
    """Counts for `/pm-status`: open items per list, and how many are overdue."""
    if not data:
        return {}
    return {
        "eval_sets_not_ready": sum(1 for r in data.get("eval_sets") or []
                                   if isinstance(r, dict) and r.get("status") not in EVAL_READY),
        "test_inputs_owed": sum(1 for r in data.get("test_inputs") or []
                                if isinstance(r, dict) and r.get("status") not in INPUT_DONE),
        "open_decisions": sum(1 for r in data.get("open_decisions") or []
                              if isinstance(r, dict) and r.get("status") == "open"),
        "overdue": len(overdue(data)),
    }


# ---------------------------------------------------------------------------
# Project-level check, shared by scripts/pm_readiness.py and /pm-check
# ---------------------------------------------------------------------------

def prd_declared_ids(project_root: Path | str) -> set[str]:
    """Requirement, story and epic ids the PRD mentions (empty without a PRD)."""
    from artifact_contracts import epic_ids, requirement_ids
    from frontmatter import read as fm_read
    from project import artifact_path

    path = artifact_path(Path(project_root), "03")
    if not path.exists():
        return set()
    try:
        _fm, body = fm_read(str(path))
    except Exception:
        return set()
    return set(requirement_ids(body)) | set(epic_ids(body))


def check_project(project_root: Path | str) -> tuple[list[ReadinessIssue], list[dict], bool]:
    """(issues, overdue items, whether the file exists) for a project."""
    data, problem = load(path_for(project_root))
    if problem:
        return [problem], [], True
    if data is None:
        return [], [], False
    return validate(data, prd_declared_ids(project_root)), overdue(data), True


def format_issues(issues: list[ReadinessIssue]) -> str:
    lines = []
    for issue in issues:
        where = f" {issue.item}" if issue.item else ""
        lines.append(f"{issue.severity.upper():7} {issue.code}{where}: {issue.message}")
        lines.append(f"        Fix: {issue.fix}")
    return "\n".join(lines)


_SECTION_LABELS = {"eval_sets": "eval set", "test_inputs": "test input", "open_decisions": "open decision"}


def format_overdue(items: list[dict]) -> str:
    return "\n".join(
        f"- {item['id']} ({_SECTION_LABELS[item['section']]}, due {item['due']}, {item['status']}): {item['summary']}"
        for item in items
    )
