"""PM-OS context overlay loader.

The overlay is a pluggable layer of company/team/stage context that mounts on top
of the generic engine. It lives — as user data — at ``~/.pm-os/context/``, seeded
once from the repo's ``context.example/`` tree and edited in place by the PM. With
no pack filled in, every helper here returns "nothing", so PM-OS behaves exactly as
it does without an overlay (an all-TODO pack is a perfect no-op).

Layering precedence (high -> low): project override > stage pack > global.
"""
import os
import re
import shutil
from pathlib import Path

import yaml

PM_OS_DIR = Path(os.environ.get("PM_OS_DIR", str(Path.home() / ".pm-os")))
CONTEXT_DIR = PM_OS_DIR / "context"
CONTEXT_SEED_DIR = PM_OS_DIR / "context.example"

APPLY_MODES = {"augment", "override", "reference-only"}
DEFAULT_APPLY = "augment"

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _clean(text: str) -> str:
    """Strip overlay scaffolding (HTML comments + blockquote guidance) from a file.

    Keeps headings and real prose; drops the `<!-- TODO -->` comments and the
    leading `> how to fill this in` guidance lines that ship in the seed.
    """
    text = _COMMENT_RE.sub("", text)
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    return "\n".join(lines).strip()


def _has_substance(cleaned: str) -> bool:
    """True if any line is non-blank and not just a markdown heading."""
    for ln in cleaned.splitlines():
        s = ln.strip()
        if s and not s.startswith("#"):
            return True
    return False


def _norm(text: str) -> str:
    """Collapse whitespace for robust seed-vs-live comparison."""
    return "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())


def _union(base, extra) -> list:
    """Base list plus any extra entries not already present, order-preserving."""
    out = list(base or [])
    for item in (extra or []):
        if item not in out:
            out.append(item)
    return out


def _load_manifest(ctx_dir: Path) -> dict:
    path = ctx_dir / "context.yaml"
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        # Fail loud: silently treating a typo'd manifest as "no overlay" would drop
        # the PM's company/guardrail context from generation without warning.
        raise ValueError(
            f"PM-OS context manifest is malformed and is NOT being applied: {path}\n"
            f"  {str(e).splitlines()[0] if str(e) else e}\n"
            f"  Fix the YAML (or remove the file), then retry."
        ) from e


def _read_overlay_file(rel_path: str, ctx_dir: Path, override_dir):
    """Read a file by its manifest-relative path, project override winning.

    Returns cleaned, substantive text, or None if absent/empty/scaffolding-only.
    """
    for base in (override_dir, ctx_dir):
        if base is None:
            continue
        fp = base / rel_path
        if fp.exists():
            cleaned = _clean(fp.read_text(encoding="utf-8"))
            if not _has_substance(cleaned):
                return None
            # Unchanged from the pristine seed = the PM hasn't filled it in. This
            # catches seed scaffolding that survives _clean (e.g. an empty glossary
            # table's header/separator rows), keeping an untouched pack a no-op.
            seed = CONTEXT_SEED_DIR / rel_path
            if seed.exists() and _norm(_clean(seed.read_text(encoding="utf-8"))) == _norm(cleaned):
                return None
            return cleaned
    return None


def resolve_context(stage_id: str, project_root=None) -> dict:
    """Resolve the overlay for a stage into substantive blocks + apply mode.

    Reads the installed manifest at ``~/.pm-os/context/context.yaml`` (+ an optional
    per-project ``<project>/context/context.yaml`` that takes precedence), gathers
    the global files and this stage's format/examples, drops empty/TODO content, and
    returns:

        {"has_content": bool, "apply": str,
         "global": [(name, text), ...], "stage_format": text|None,
         "stage_examples": [text, ...]}
    """
    # Bootstrap: if the overlay was never seeded — e.g. the upgrade that introduced
    # update-time seeding ran the OLD updater process, so its finish_update() never
    # called seed_context() — materialize it from the seed on first read. Makes the
    # loader self-healing regardless of how the install arrived.
    if CONTEXT_SEED_DIR.is_dir() and not (CONTEXT_DIR / "context.yaml").exists():
        try:
            seed_context()
        except Exception:
            pass

    override_dir = None
    if project_root is not None:
        cand = Path(project_root) / "context"
        if cand.is_dir():
            override_dir = cand

    # Layer the project manifest ON TOP of the base — a partial project manifest
    # (one extra global file, or one stage's format) must not wipe the shared base
    # global files / stage fields. Project wins per duplicate path/field; lists union.
    base_manifest = _load_manifest(CONTEXT_DIR)
    proj_manifest = _load_manifest(override_dir) if override_dir else {}
    manifest = dict(base_manifest)
    if proj_manifest:
        for key, value in proj_manifest.items():
            if key not in ("global", "stages"):
                manifest[key] = value

        manifest["global"] = _union(base_manifest.get("global"), proj_manifest.get("global"))

        base_stages = base_manifest.get("stages") or {}
        proj_stages = proj_manifest.get("stages") or {}
        merged_stages = {}
        for sid in set(base_stages) | set(proj_stages):
            b = base_stages.get(sid) or {}
            p = proj_stages.get(sid) or {}
            entry = dict(b)
            if p.get("format"):
                entry["format"] = p["format"]          # project format wins
            if p.get("apply"):
                entry["apply"] = p["apply"]             # project apply mode wins
            examples = _union(b.get("examples"), p.get("examples"))
            if examples:
                entry["examples"] = examples            # examples union (base + project)
            merged_stages[sid] = entry
        manifest["stages"] = merged_stages

    empty = {"has_content": False, "apply": DEFAULT_APPLY,
             "global": [], "stage_format": None, "stage_examples": []}
    if not manifest:
        return empty

    # Global blocks (apply to every stage).
    global_blocks = []
    for rel in manifest.get("global", []) or []:
        text = _read_overlay_file(rel, CONTEXT_DIR, override_dir)
        if text:
            name = Path(rel).stem.replace("-", " ").replace("_", " ")
            global_blocks.append((name, text))

    # Stage pack.
    stage_entry = (manifest.get("stages") or {}).get(stage_id) or {}
    apply = stage_entry.get("apply", DEFAULT_APPLY)
    if apply not in APPLY_MODES:
        apply = DEFAULT_APPLY

    stage_format = None
    if stage_entry.get("format"):
        stage_format = _read_overlay_file(stage_entry["format"], CONTEXT_DIR, override_dir)

    stage_examples = []
    for rel in stage_entry.get("examples", []) or []:
        text = _read_overlay_file(rel, CONTEXT_DIR, override_dir)
        if text:
            stage_examples.append(text)

    has_content = bool(global_blocks or stage_format or stage_examples)
    return {"has_content": has_content, "apply": apply,
            "global": global_blocks, "stage_format": stage_format,
            "stage_examples": stage_examples}


_APPLY_DIRECTIVE = {
    "augment": "Keep this stage's required output sections. Fold the format's must-haves and "
               "conventions in, and match any example's depth/structure/tone WITHOUT copying its content.",
    "override": "The format's \"Required sections\" REPLACE this stage's default output spec. "
                "Use the example only for depth/tone.",
    "reference-only": "Use the example(s) only for tone and depth — do not change this stage's "
                      "output structure.",
}


def render_context(stage_id: str, project_root=None) -> str:
    """Render the overlay as a markdown block to inject into a stage prompt.

    Returns "" when no substantive overlay is configured, so an empty/TODO pack is
    a no-op and the stage generates exactly as specified by its skill.
    """
    res = resolve_context(stage_id, project_root)
    if not res["has_content"]:
        return ""

    apply = res["apply"]
    out = [f"# Company & stage context overlay (apply: {apply})",
           "",
           "This is your team's configured context for this stage — treat it as authoritative "
           "background, not a new requirement source. " + _APPLY_DIRECTIVE.get(apply, ""),
           ""]

    if res["global"]:
        out.append("## Global context")
        out.append("")
        for name, text in res["global"]:
            out.append(f"### {name}")
            out.append(text)
            out.append("")

    if res["stage_format"]:
        out.append("## Stage format")
        out.append(res["stage_format"])
        out.append("")

    for i, ex in enumerate(res["stage_examples"], 1):
        out.append(f"## Stage example {i}" if len(res["stage_examples"]) > 1 else "## Stage example")
        out.append(ex)
        out.append("")

    return "\n".join(out).strip()


def seed_context() -> int:
    """Copy any seed file from context.example/ that is missing in context/.

    File-level copy-if-missing: first install populates the whole tree; later-added
    seed files (e.g. new stage packs) reach existing installs; a PM's filled-in files
    are never overwritten. Returns the number of files copied.
    """
    if not CONTEXT_SEED_DIR.is_dir():
        return 0
    copied = 0
    for src in CONTEXT_SEED_DIR.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(CONTEXT_SEED_DIR)
        dest = CONTEXT_DIR / rel
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
    return copied
