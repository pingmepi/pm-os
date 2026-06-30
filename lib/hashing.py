import hashlib
import json
import re
from pathlib import Path

import yaml


def hash_artifact_body(file_path: str) -> str:
    """SHA-256 of artifact body (everything after the closing frontmatter ---)."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    body = _extract_body(content)
    return _sha256(body)


def hash_event(event_dict: dict, prev_hash) -> str:
    """SHA-256 of canonicalized event JSON (event_hash excluded), prefixed with prev_hash."""
    d = {k: v for k, v in event_dict.items() if k != "event_hash"}
    canonical = json.dumps(d, sort_keys=True, ensure_ascii=False)
    data = (prev_hash or "") + canonical
    return _sha256(data)


# --- Composite (multi-member) artifact hashing -------------------------------
#
# Stage 00w (the adaptive context pack) is a *composite* artifact: its content is
# spread across several files enumerated by 00-context/manifest.yaml — the wiki
# index, the evidence ledger, the source inventory, and every active view. Its
# content hash must cover all of them, be stable across cosmetic reformatting,
# and never depend on filesystem ordering. See
# docs/plans/adaptive-context-intelligence-pack.md ("Approval, Hashing, and
# Compatibility") for the canonicalization spec this implements.
#
# Canonicalization rules (pinned — changing them is a breaking format change):
#   - Members are hashed in the FIXED order declared by the manifest's `members`
#     list, never filesystem order.
#   - Markdown members are hashed body-only via hash_artifact_body (frontmatter
#     stripped + CRLF->LF), so frontmatter churn is inert.
#   - YAML members are hashed over a CANONICAL serialization (sorted keys, lists
#     of mappings normalized by their stable `id`), so cosmetic reformatting,
#     comment edits, and key reordering are inert.
#   - The composite hash is SHA-256 over the ordered tuple of per-member hashes
#     (each line "kind:relpath:member_hash"). The manifest's OWN recorded member
#     hashes are excluded from the composite input to avoid the circularity of
#     hashing a file that records the hashes; the manifest's member *list and
#     order* are covered implicitly because they drive the iteration order.

MANIFEST_RELPATH = "00-context/manifest.yaml"


class CompositeHashError(Exception):
    """Raised when a composite artifact's manifest is missing or unsafe."""


def canonical_yaml_hash(file_path: str) -> str:
    """SHA-256 over a canonical serialization of a YAML document.

    Sorted keys and ID-normalized list ordering make cosmetic reformatting,
    comment edits, and key reordering inert — only a semantic change to the data
    moves the hash.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return _sha256(_canonical_yaml_dump(_canonicalize(data)))


def _canonicalize(value):
    """Recursively normalize a parsed-YAML value for stable serialization.

    Mappings keep their keys (sorted at dump time). Lists whose every element is
    a mapping carrying a stable `id` are sorted by that id so that reordering the
    list in the file does not change the hash; all other lists keep their order
    (order is meaningful there).
    """
    if isinstance(value, dict):
        return {k: _canonicalize(v) for k, v in value.items()}
    if isinstance(value, list):
        items = [_canonicalize(v) for v in value]
        if items and all(isinstance(v, dict) and "id" in v for v in items):
            return sorted(items, key=lambda v: str(v["id"]))
        return items
    return value


def _canonical_yaml_dump(data) -> str:
    return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=True)


def composite_member_hash(project_root, member: dict) -> str:
    """Hash a single manifest member by its declared kind (markdown | yaml)."""
    relpath = member.get("path")
    kind = (member.get("kind") or "").lower()
    abspath = Path(project_root) / relpath
    if kind in ("markdown", "md"):
        return hash_artifact_body(str(abspath))
    if kind in ("yaml", "yml"):
        return canonical_yaml_hash(str(abspath))
    raise CompositeHashError(
        f"manifest member '{relpath}' has unknown kind '{member.get('kind')}' "
        "(expected 'markdown' or 'yaml')"
    )


def load_manifest_members(project_root) -> list:
    """Validate the manifest and return its ordered member list.

    Safety: rejects a missing manifest, a missing `members` list, members without
    a path, path traversal / absolute paths, duplicate member paths, members
    pointing at the manifest itself, and members whose file is missing on disk.
    The manifest's own recorded member hashes are NOT trusted here — they are
    validated separately by validate_manifest_hashes against freshly computed
    hashes.
    """
    root = Path(project_root)
    manifest_path = root / MANIFEST_RELPATH
    if not manifest_path.exists():
        raise CompositeHashError(f"context pack manifest not found: {MANIFEST_RELPATH}")
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise CompositeHashError(f"manifest is not valid YAML: {e}")
    if not isinstance(manifest, dict):
        raise CompositeHashError("manifest must be a mapping")
    members = manifest.get("members")
    if not isinstance(members, list) or not members:
        raise CompositeHashError("manifest 'members' must be a non-empty list")

    seen = set()
    for m in members:
        if not isinstance(m, dict) or not m.get("path"):
            raise CompositeHashError("each manifest member needs a 'path'")
        rel = m["path"]
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise CompositeHashError(f"unsafe manifest member path: {rel!r}")
        if rel == MANIFEST_RELPATH:
            raise CompositeHashError("manifest cannot list itself as a member")
        if rel in seen:
            raise CompositeHashError(f"duplicate manifest member path: {rel!r}")
        seen.add(rel)
        if not (root / rel).exists():
            raise CompositeHashError(f"manifest member missing on disk: {rel}")
    return members


def _read_manifest_dict(project_root) -> dict:
    """Parse the manifest YAML (already safety-validated by load_manifest_members)."""
    manifest_path = Path(project_root) / MANIFEST_RELPATH
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def hash_composite_artifact(project_root, manifest_relpath: str = MANIFEST_RELPATH) -> str:
    """SHA-256 over the ordered per-member hashes plus the manifest's routing fields.

    Used for stage 00w (the context pack). Dual-mode callers should fall back to
    hash_artifact_body when no manifest is present (legacy single-file wikis).

    The manifest's `stage_affinities` are folded in because they decide which
    modules each downstream stage reads: editing an affinity after 00w approval
    changes downstream generation inputs, so it must register as drift. Only the
    manifest's per-member `hash` table stays excluded (circular — the member bodies
    are already covered by the per-member hashes above; member list and order are
    covered by the line order).
    """
    members = load_manifest_members(project_root)
    lines = []
    for m in members:
        member_hash = composite_member_hash(project_root, m)
        kind = (m.get("kind") or "").lower()
        lines.append(f"{kind}:{m['path']}:{member_hash}")
    affinities = _read_manifest_dict(project_root).get("stage_affinities") or {}
    lines.append("affinities:" + _canonical_yaml_dump(_canonicalize(affinities)))
    return _sha256("\n".join(lines))


def stage_content_hash(project_root, stage_id: str, artifact_path) -> str:
    """Dispatch: composite hash for a 00w with a manifest, body hash otherwise.

    The single source of truth for "what is this stage's content hash" so the
    pre-stage gate and pm_approve.py never diverge. Dual-mode: a 00w without a
    manifest (legacy single-file wiki) falls through to body hashing, preserving
    its existing hash and behavior.
    """
    if stage_id == "00w" and (Path(project_root) / MANIFEST_RELPATH).exists():
        return hash_composite_artifact(project_root)
    return hash_artifact_body(str(artifact_path))


def validate_manifest_hashes(project_root) -> list:
    """Return the list of members whose recorded hash disagrees with the computed one.

    The manifest may record a per-member `hash`; this re-derives each member's
    hash and reports drift. An empty list means every recorded hash is current.
    Members without a recorded hash are skipped (nothing to validate against).
    """
    members = load_manifest_members(project_root)
    stale = []
    for m in members:
        recorded = m.get("hash")
        if recorded is None:
            continue
        if composite_member_hash(project_root, m) != recorded:
            stale.append(m["path"])
    return stale


def _extract_body(content: str) -> str:
    """Return body after the second --- frontmatter delimiter. LF-normalized."""
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    # Find closing ---
    match = re.search(r"^---\s*\n", content[3:], re.MULTILINE)
    if match:
        return content[3 + match.end():]
    return content


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
