"""Handoff release record, change note and package manifest (backlog #73, #75, #68).

A *release* is a package build the PM marks with a one-line reason
(`/pm-handoff --package --release-note "…"`, PM decision 2026-10-21). Plain
rebuilds are drafts: they get a change note against the last release but are
not recorded, so iterating locally never pollutes the history of what was sent.

Three things are written from one snapshot of the package:

- `.releases/REL-###.yaml` at the project root (releases only): the ledger
  entry, holding the note, each source artifact's approved version and hash,
  a hash per stable-id block of every approved source, the outside inputs
  (Figma file version from the design return, readiness test-input files),
  and every file shipped. It is ungated and never under `handoff/`, which is
  regenerated.
- `CHANGES.md` in each audience folder: stable ids added, removed or changed
  since the last release, the stories that touches, the outside inputs whose
  version or hash changed, and the PM's note.
- `manifest.json` in each audience folder (#75, v1): every file with its role,
  hash, source, version, status and reading order. It is also #68's delete
  list: a rebuild removes only the files the previous manifest lists, never a
  file someone else put in the folder.

The id comparison reuses the stable-id block splitter (`split_stable_id_blocks`,
via `enhancement.stable_id_blocks`) and the same new/removed/modified
classification as the enhancement delta (`enhancement.classify_change`).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

RELEASES_DIR = ".releases"
MANIFEST_FILE = "manifest.json"
CHANGES_FILE = "CHANGES.md"
MANIFEST_SCHEMA_VERSION = 1
# Approved artifacts whose stable ids a release records. Stage 03 (PRD), 04
# (design spec), 06 (QA plan) and 08 (TRD) are where the ids a build team
# cites are declared.
ID_SOURCE_STAGES = ("03", "04", "06", "08")

_REL_ID_RE = re.compile(r"^REL-(\d{3,})\.yaml$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

def releases_dir(project_root: Path | str) -> Path:
    return Path(project_root) / RELEASES_DIR


def latest(project_root: Path | str) -> dict | None:
    """The most recent recorded release, or None."""
    folder = releases_dir(project_root)
    if not folder.is_dir():
        return None
    numbered = sorted(
        (int(m.group(1)), path) for path in folder.iterdir()
        if (m := _REL_ID_RE.match(path.name))
    )
    if not numbered:
        return None
    try:
        return yaml.safe_load(numbered[-1][1].read_text(encoding="utf-8")) or None
    except (OSError, yaml.YAMLError):
        return None


def next_id(project_root: Path | str) -> str:
    folder = releases_dir(project_root)
    numbers = [int(m.group(1)) for path in folder.iterdir() if (m := _REL_ID_RE.match(path.name))] \
        if folder.is_dir() else []
    return f"REL-{(max(numbers) if numbers else 0) + 1:03d}"


def write_record(project_root: Path | str, record: dict) -> Path:
    folder = releases_dir(project_root)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record['id']}.yaml"
    if path.exists():
        raise FileExistsError(f"{path} already exists; releases are never overwritten")
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Snapshot of what a build ships
# ---------------------------------------------------------------------------

def stable_id_hashes(project_root: Path | str, provenance: dict[str, dict]) -> dict[str, dict[str, str]]:
    """{artifact: {stable id: block hash}} for every approved id-bearing source."""
    from enhancement import stable_id_blocks
    from frontmatter import read as fm_read
    from project import artifact_path

    out: dict[str, dict[str, str]] = {}
    for stage_id in ID_SOURCE_STAGES:
        record = provenance.get(stage_id)
        if not record or record.get("status") != "approved":
            continue
        path = artifact_path(Path(project_root), stage_id)
        try:
            _fm, body = fm_read(str(path))
        except Exception:
            continue
        out[path.name] = {
            ident: sha256_bytes(block.encode("utf-8"))[:16]
            for ident, block in stable_id_blocks(body).items()
        }
    return out


def outside_inputs(project_root: Path | str) -> dict[str, str]:
    """Versions/hashes of inputs PM-OS does not itself hash: the Figma file
    behind the design return, and the readiness record's test-input files."""
    root = Path(project_root)
    found: dict[str, str] = {}
    ia = root / "design-in" / "ia.yaml"
    if ia.is_file():
        try:
            figma = (yaml.safe_load(ia.read_text(encoding="utf-8")) or {}).get("figma") or {}
        except (OSError, yaml.YAMLError):
            figma = {}
        if figma.get("file_key"):
            stamp = str(figma.get("version") or "")
            if figma.get("last_modified"):
                stamp += f" ({figma['last_modified']})"
            found[f"Figma file {figma['file_key']}"] = stamp.strip() or "unversioned"
    try:
        import readiness
        data, _problem = readiness.load(readiness.path_for(root))
    except Exception:
        data = None
    for row in (data or {}).get("test_inputs") or []:
        if not isinstance(row, dict) or not row.get("file"):
            continue
        path = root / str(row["file"])
        label = f"{row.get('id')} {row['file']}"
        found[label] = sha256_file(path)[:16] if path.is_file() else "missing"
    return found


_ROLE_RULES = (
    (re.compile(r"^(README\.md|CHANGES\.md|index\.html|manifest\.json)$"), "index"),
    (re.compile(r"^readiness\.yaml$"), "status"),
    (re.compile(r"^reference/(prd|trd|design-spec)\.md$"), "source-of-truth"),
    (re.compile(r"^(stories|requirements|epics)/|^00-overview\.md$"), "derived"),
    (re.compile(r"^DESIGNER-WORKFLOW\.md$"), "guide"),
)
_ORDER_RULES = (
    ("README.md", 1), ("CHANGES.md", 2), ("readiness.yaml", 3), ("00-overview.md", 5),
    ("epics/", 10), ("stories/", 20), ("requirements/", 30), ("reference/prd.md", 40),
    ("reference/trd.md", 41), ("reference/design-spec.md", 42), ("reference/", 50),
    ("DESIGNER-WORKFLOW.md", 60), ("wireframes/", 80),
)


def _role(rel: str) -> str:
    return next((role for rx, role in _ROLE_RULES if rx.search(rel)), "reference")


def _read_order(rel: str) -> int:
    return next((order for prefix, order in _ORDER_RULES
                 if rel == prefix or (prefix.endswith("/") and rel.startswith(prefix))), 70)


def _file_frontmatter(path: Path) -> dict:
    if path.suffix.lower() != ".md":
        return {}
    text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    try:
        fm = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}
    return fm if isinstance(fm, dict) else {}


def file_entries(audience_dir: Path) -> list[dict]:
    """One manifest entry per file in an audience folder (manifest excluded)."""
    entries = []
    for path in sorted(p for p in audience_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(audience_dir).as_posix()
        if rel in (MANIFEST_FILE, ".pm-os-handoff"):
            continue
        fm = _file_frontmatter(path)
        sources = fm.get("sources") or []
        entries.append({
            "path": rel,
            "role": _role(rel),
            "sha256": sha256_file(path),
            "source": (sources[0].get("artifact") if sources and isinstance(sources[0], dict) else None),
            "version": fm.get("version"),
            "status": fm.get("status"),
            "read_order": _read_order(rel),
        })
    return sorted(entries, key=lambda e: (e["read_order"], e["path"]))


def build_manifest(project_name: str, audience: str, audience_dir: Path,
                   release_id: str | None, generated_at: str) -> dict:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "project": project_name,
        "audience": audience,
        "release": release_id,
        "draft": release_id is None,
        "generated_at": generated_at,
        "roles": {
            "source-of-truth": "Full projection of an approved stage artifact; wins on any conflict.",
            "derived": "Decomposed from the source of truth for reading (stories, requirements, epics).",
            "reference": "Supporting material; never cite it as a source.",
            "status": "What is still owed (readiness record); changes without re-approval.",
            "index": "Navigation and change notes.",
            "guide": "How to work with this package.",
        },
        "files": file_entries(audience_dir),
    }


# ---------------------------------------------------------------------------
# Comparison and the change note
# ---------------------------------------------------------------------------

def diff(previous: dict | None, stable_ids: dict, inputs: dict) -> dict:
    """Ids added/removed/changed per artifact, and outside inputs that moved."""
    from enhancement import classify_change

    changes: list[dict] = []
    prev_ids = (previous or {}).get("stable_ids") or {}
    for artifact in sorted(set(prev_ids) | set(stable_ids)):
        before, after = prev_ids.get(artifact) or {}, stable_ids.get(artifact) or {}
        for ident in sorted(set(before) | set(after)):
            kind = classify_change(before.get(ident), after.get(ident))
            if kind:
                changes.append({"artifact": artifact, "id": ident, "change": kind})
    prev_inputs = (previous or {}).get("outside_inputs") or {}
    moved = [
        {"input": key, "before": prev_inputs.get(key), "after": inputs.get(key)}
        for key in sorted(set(prev_inputs) | set(inputs))
        if prev_inputs.get(key) != inputs.get(key)
    ]
    return {"previous": (previous or {}).get("id"), "ids": changes, "inputs": moved}


def affected_stories(project_root: Path | str, changed_ids: list[str]) -> dict[str, list[str]]:
    """{story: [changed ids that touch it]}, resolved through the spine: a
    story is touched by its own block, its requirements (either direction),
    its journeys, its epic, and the test cases, screens and tasks that trace to
    any of those."""
    import traceability
    from delivery_map import build_prd_delivery_map
    from frontmatter import read as fm_read
    from project import artifact_path

    root = Path(project_root)
    try:
        _fm, prd_body = fm_read(str(artifact_path(root, "03")))
        delivery = build_prd_delivery_map(prd_body)
        index = traceability.build_index(root)
    except Exception:
        return {}
    touches: dict[str, set[str]] = {}
    for story in delivery.story_blocks:
        refs = {story} | set(delivery.story_requirements.get(story, [])) \
            | set(delivery.story_journeys.get(story, []))
        if delivery.story_to_epic.get(story):
            refs.add(delivery.story_to_epic[story])
        for tc, rec in (index.get("test_cases") or {}).items():
            if set(rec.get("requirements") or []) & refs:
                refs.add(tc)
        for scr, rec in (index.get("screens") or {}).items():
            if set(rec.get("serves") or []) & refs:
                refs.add(scr)
        for tsk, rec in (index.get("tasks") or {}).items():
            if set(rec.get("implements") or []) & refs:
                refs.add(tsk)
        touches[story] = refs
    out: dict[str, list[str]] = {}
    for story, refs in touches.items():
        hits = [ident for ident in changed_ids if ident in refs]
        if hits:
            out[story] = hits
    return out


def render_changes(*, project_name: str, delta: dict, stories: dict[str, list[str]],
                   note: str | None, release_id: str | None, generated_at: str) -> str:
    """CHANGES.md. Ids are written in `code` so a removed id never reads as a
    citation the release check would expect the package to define."""
    title = f"{release_id}" if release_id else "draft build (not a recorded release)"
    previous = delta.get("previous")
    lines = [f"# What changed: {project_name}, {title}", ""]
    lines.append(f"> Generated {generated_at}. " + (
        f"Compared with the last recorded release, `{previous}`." if previous
        else "No earlier release is recorded, so everything below is new."))
    if not release_id:
        lines.append("> This build is a draft. It becomes a release when built with a release note.")
    lines += ["", "## Why", "", note.strip() if note else "_No release note given._", ""]

    groups = {"new": "Added", "modified": "Changed", "removed": "Removed"}
    lines += ["## Stable ids", ""]
    if not previous:
        # A first release would list every id as added; count them instead.
        per_artifact: dict[str, int] = {}
        for change in delta["ids"]:
            per_artifact[change["artifact"]] = per_artifact.get(change["artifact"], 0) + 1
        lines += [f"- {artifact}: {count} ids" for artifact, count in sorted(per_artifact.items())] \
            or ["No stable ids found in the approved sources."]
        lines += ["", "Later releases list each id added, removed or changed, and the stories it affects.", ""]
        lines += ["## Outside inputs", ""]
        lines += [f"- {row['input']}: {row['after']}" for row in delta["inputs"]] \
            or ["None recorded (Figma file version, test-input files)."]
        lines.append("")
        return "\n".join(lines)
    if not delta["ids"]:
        lines.append("No stable id was added, removed or changed.")
    for kind, label in groups.items():
        rows = [c for c in delta["ids"] if c["change"] == kind]
        if rows:
            lines.append(f"**{label} ({len(rows)}):** " + ", ".join(f"`{c['id']}`" for c in rows))
    lines += ["", "## Stories affected", ""]
    if stories:
        for story, hits in sorted(stories.items()):
            others = [i for i in hits if i != story]
            parts = (["its own text changed"] if story in hits else []) + \
                (["via " + ", ".join(f"`{i}`" for i in others)] if others else [])
            lines.append(f"- `{story}`: " + "; ".join(parts))
        lines.append("")
        lines.append("Re-plan only these stories; the rest are unchanged since the last release.")
    else:
        lines.append("No story is affected.")
    lines += ["", "## Outside inputs", ""]
    if delta["inputs"]:
        lines += [f"- {row['input']}: {row['before'] or 'not recorded'} → {row['after'] or 'removed'}"
                  for row in delta["inputs"]]
    else:
        lines.append("No outside input changed (Figma file version, test-input files).")
    lines.append("")
    return "\n".join(lines)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Clearing an audience folder before a rebuild (#68)
# ---------------------------------------------------------------------------

# A folder built before manifests existed has only the marker. Its generated
# files are recognised by the package layout: these top-level names, plus
# Markdown/HTML files inside these folders. Anything else is someone's own file.
_LEGACY_TOP_LEVEL = {"README.md", "index.html", "00-overview.md", "DESIGNER-WORKFLOW.md",
                     "readiness.yaml", CHANGES_FILE, MANIFEST_FILE, ".pm-os-handoff"}
_LEGACY_DIRS = {"stories", "requirements", "epics", "reference", "wireframes"}


def _legacy_generated(rel: str) -> bool:
    parts = rel.split("/")
    if len(parts) == 1:
        return rel in _LEGACY_TOP_LEVEL
    return parts[0] in _LEGACY_DIRS and Path(rel).suffix.lower() in {".md", ".html"}


def generated_files(audience_dir: Path) -> set[str]:
    """Paths PM-OS wrote into this folder last time: the previous manifest's
    list, or the layout rule for a folder built before manifests."""
    manifest = audience_dir / MANIFEST_FILE
    listed: set[str] | None = None
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            listed = {str(entry["path"]) for entry in data.get("files") or [] if entry.get("path")}
        except (OSError, ValueError, TypeError, KeyError):
            listed = None
    present = {p.relative_to(audience_dir).as_posix() for p in audience_dir.rglob("*") if p.is_file()}
    if listed is None:
        return {rel for rel in present if _legacy_generated(rel)}
    return (listed | {MANIFEST_FILE, ".pm-os-handoff"}) & present


def clear_generated(audience_dir: Path) -> list[str]:
    """Delete what PM-OS generated last time and return the files kept.

    Only files the previous build wrote are removed (#68), so a designer kit or
    notes saved into handoff/<audience>/ survive a rebuild. Folders left empty
    are removed.
    """
    if not audience_dir.is_dir():
        return []
    for rel in sorted(generated_files(audience_dir)):
        (audience_dir / rel).unlink()
    for folder in sorted((p for p in audience_dir.rglob("*") if p.is_dir()),
                         key=lambda p: len(p.parts), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()
    return sorted(p.relative_to(audience_dir).as_posix() for p in audience_dir.rglob("*") if p.is_file())
