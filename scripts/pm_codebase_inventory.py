#!/usr/bin/env python3
"""Read-only repository inventory plus ask-focused dependency impact evidence."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "vendor",
    "dist", "build", "coverage", "__pycache__", ".next", ".turbo",
}
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
    ".gz", ".tar", ".jar", ".class", ".pyc", ".so", ".dylib", ".dll",
    ".woff", ".woff2", ".ttf", ".mp3", ".mp4", ".mov",
}
MANIFEST_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "poetry.lock", "uv.lock",
    "cargo.toml", "go.mod", "gemfile", "pom.xml", "build.gradle", "composer.json",
}
STOP_WORDS = {
    "add", "with", "from", "into", "that", "this", "without", "change", "new",
    "the", "and", "for", "user", "users", "action", "feature", "product", "make",
}
SURFACE_TERMS = {"ui", "web", "api", "data", "service", "event", "integration", "operations"}
DYNAMIC_PATTERNS = (
    "__import__(", "importlib.", "eval(", "exec(", "dynamic import", "reflect.",
    "class.forname", "require(variable", "import(variable",
)


def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """Extract a zip, refusing any member that would escape ``dest_dir`` (zip-slip)."""
    dest_dir = dest_dir.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.namelist():
            resolved = (dest_dir / member).resolve()
            if resolved != dest_dir and dest_dir not in resolved.parents:
                raise ValueError(f"zip entry escapes the extraction directory: {member!r}")
        archive.extractall(dest_dir)


def _extract_zip_for_scan(zip_path: Path, dest_dir: Path) -> Path:
    """Extract a zip into ``dest_dir`` and return the code root (single wrapper unwrapped)."""
    _safe_extract_zip(zip_path, dest_dir)
    entries = [item for item in dest_dir.iterdir() if item.name != "__MACOSX"]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return dest_dir


def _git(path: Path, *args: str) -> Optional[str]:
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def _tokens(text: str) -> Set[str]:
    return {
        token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)
        if token.lower() not in STOP_WORDS
    }


def _collect_files(root: Path) -> Tuple[List[str], Dict[str, str], List[dict]]:
    files = []
    contents = {}
    exclusions = []
    for current, directories, names in os.walk(root, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in EXCLUDED_DIRS)
        current_path = Path(current)
        for name in sorted(names):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                exclusions.append({"path": relative, "reason": "symlink not followed"})
                continue
            if path.suffix.lower() in BINARY_SUFFIXES:
                exclusions.append({"path": relative, "reason": "binary asset"})
                continue
            try:
                if path.stat().st_size > 1024 * 1024:
                    exclusions.append({"path": relative, "reason": "file exceeds 1 MiB scan limit"})
                    continue
                raw = path.read_bytes()
            except OSError as exc:
                exclusions.append({"path": relative, "reason": f"unreadable: {exc}"})
                continue
            if b"\0" in raw:
                exclusions.append({"path": relative, "reason": "binary content"})
                continue
            files.append(relative)
            contents[relative] = raw.decode("utf-8", errors="replace")
    return files, contents, exclusions


def _score(path: str, content: str, ask_tokens: Set[str], subpath: Optional[str]) -> Tuple[int, List[str]]:
    lower_path = path.lower()
    lower_content = content.lower()
    reasons = []
    score = 0
    for token in sorted(ask_tokens):
        if token in lower_path:
            score += 1 if token in SURFACE_TERMS else 5
            reasons.append(f"ask term '{token}' in path")
        count = lower_content.count(token)
        if count:
            score += 0 if token in SURFACE_TERMS else min(count, 3)
            reasons.append(f"ask term '{token}' in content")
    if subpath and (path == subpath or path.startswith(subpath.rstrip("/") + "/")):
        score += 2
        reasons.append("inside requested monorepo subpath")
    return score, reasons


def _module_candidates(module: str) -> List[str]:
    normalized = module.strip().lstrip(".").replace(".", "/")
    if not normalized:
        return []
    return [normalized + suffix for suffix in (".py", ".ts", ".tsx", ".js", ".jsx", "/__init__.py")]


def _imports(content: str) -> Set[str]:
    values = set()
    for pattern in (
        r"(?m)^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+",
        r"(?m)^\s*import\s+([A-Za-z0-9_\.]+)",
        r"(?:from\s+|require\s*\(|import\s*\()\s*['\"]([^'\"]+)['\"]",
    ):
        values.update(match.group(1) for match in re.finditer(pattern, content))
    return values


def _resolve_import(source: str, module: str, all_paths: Set[str]) -> Optional[str]:
    candidates = []
    if module.startswith("."):
        base = (Path(source).parent / module).as_posix()
        normalized = str(Path(base))
        candidates.extend(normalized + suffix for suffix in (".py", ".ts", ".tsx", ".js", ".jsx"))
        candidates.extend(
            f"{normalized}/index{suffix}" for suffix in (".ts", ".tsx", ".js", ".jsx")
        )
    else:
        candidates.extend(_module_candidates(module))
    for candidate in candidates:
        if candidate in all_paths:
            return candidate
    suffix_matches = [
        path for path in all_paths
        for candidate in _module_candidates(module)
        if path == candidate or path.endswith("/" + candidate)
    ]
    unique = sorted(set(suffix_matches))
    return unique[0] if len(unique) == 1 else None


def _dependency_graph(contents: Dict[str, str]):
    paths = set(contents)
    outbound = {path: set() for path in paths}
    inbound = {path: set() for path in paths}
    for source, content in contents.items():
        for module in _imports(content):
            target = _resolve_import(source, module, paths)
            if target and target != source:
                outbound[source].add(target)
                inbound[target].add(source)
    return outbound, inbound


def _surface(path: str, content: str) -> Set[str]:
    lower = "/" + path.lower()
    surfaces = set()
    if any(token in lower for token in ("/web/", "/ui/", "/frontend/", "/components/")) or Path(path).suffix.lower() in {".tsx", ".jsx", ".vue", ".svelte"}:
        surfaces.add("ui")
    if any(token in lower for token in ("/api/", "/routes/", "/controllers/")) or "/api/" in content.lower():
        surfaces.add("api")
    if any(token in lower for token in ("/data/", "/models/", "/schema", "/migrations/")) or Path(path).suffix.lower() == ".sql":
        surfaces.add("data")
    if any(token in lower for token in ("/services/", "/service/")):
        surfaces.add("service")
    if any(token in lower for token in ("/events/", "/queues/", "/workers/")):
        surfaces.add("event")
    if any(token in lower for token in ("/integrations/", "/webhooks/", "/clients/")):
        surfaces.add("integration")
    if any(token in lower for token in ("/deploy/", "/infra/", "/ops/", "/.github/")) or "docker" in lower:
        surfaces.add("operations")
    if any(token in lower for token in ("/shared/", "/common/", "/packages/")):
        surfaces.add("cross-cutting")
    return surfaces


def scan(root: Path, ask: str, subpath: Optional[str] = None) -> dict:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"repository path is not a directory: {root}")
    if subpath:
        candidate = (root / subpath).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            raise ValueError("monorepo subpath escapes repository root")
        if not candidate.is_dir():
            raise ValueError(f"monorepo subpath is not a directory: {subpath}")

    files, contents, exclusions = _collect_files(root)
    ask_tokens = _tokens(ask)
    scored = []
    for path in files:
        score, reasons = _score(path, contents[path], ask_tokens, subpath)
        if score > 0:
            scored.append({"path": path, "score": score, "reasons": reasons})
    scored.sort(key=lambda item: (-item["score"], item["path"]))
    direct_paths = {item["path"] for item in scored[:50] if item["score"] >= 2}

    outbound, inbound = _dependency_graph(contents)
    cone_reasons: Dict[str, Set[str]] = {}
    for direct in direct_paths:
        for dependency in outbound.get(direct, set()):
            if dependency not in direct_paths:
                cone_reasons.setdefault(dependency, set()).add(f"dependency of {direct}")
        for consumer in inbound.get(direct, set()):
            if consumer not in direct_paths:
                cone_reasons.setdefault(consumer, set()).add(f"consumer of {direct}")
    # A second bounded hop catches shared dependencies/consumers without turning the cone
    # into the whole transitive repository.
    for first_hop in list(cone_reasons):
        for dependency in outbound.get(first_hop, set()):
            if dependency not in direct_paths and dependency not in cone_reasons:
                cone_reasons.setdefault(dependency, set()).add(f"dependency of impacted {first_hop}")
        for consumer in inbound.get(first_hop, set()):
            if consumer not in direct_paths and consumer not in cone_reasons:
                cone_reasons.setdefault(consumer, set()).add(f"consumer of impacted {first_hop}")

    impact = [
        {"path": path, "reasons": sorted(reasons)}
        for path, reasons in sorted(cone_reasons.items())
    ]
    relevant = direct_paths | set(cone_reasons)
    non_touch = [
        {"path": path, "reason": "inventoried; no ask match or dependency edge to affected slice"}
        for path in files if path not in relevant
    ]
    gaps = []
    for path in sorted(relevant):
        lower = contents.get(path, "").lower()
        if any(pattern in lower for pattern in DYNAMIC_PATTERNS):
            gaps.append({
                "kind": "dynamic-boundary",
                "path": path,
                "detail": "dynamic loading/reflection prevents complete static dependency proof",
            })

    surfaces = set()
    for path in sorted(relevant):
        surfaces.update(_surface(path, contents.get(path, "")))
    confidence = "low" if not direct_paths else ("medium" if gaps else "high")
    manifests = [path for path in files if Path(path).name.lower() in MANIFEST_NAMES]
    tests = [path for path in files if "test" in Path(path).name.lower() or "/tests/" in "/" + path.lower()]
    ci = [path for path in files if path.startswith(".github/") or "/ci/" in "/" + path.lower()]
    deployment = [path for path in files if any(token in path.lower() for token in ("deploy", "docker", "infra", "k8s", "helm"))]
    entry_points = [path for path in files if Path(path).name.lower() in {"main.py", "app.py", "index.ts", "index.js", "server.ts", "server.js", "manage.py"}]

    return {
        "schema_version": 1,
        "repository": {
            "path": str(root),
            "resolved_sha": _git(root, "rev-parse", "HEAD"),
            "dirty": bool(_git(root, "status", "--porcelain", "--untracked-files=all") or ""),
            "subpath": subpath,
        },
        "ask": ask,
        "inventory": {
            "files": files,
            "manifests": manifests,
            "entry_points": entry_points,
            "tests": tests,
            "ci": ci,
            "deployment": deployment,
            "top_level_boundaries": sorted({path.split("/", 1)[0] for path in files}),
        },
        "affected_slice": scored[:50],
        "impact_cone": impact,
        "affected_surfaces": sorted(surfaces),
        "explicit_non_touch": non_touch,
        "coverage": {
            "files_considered": len(files),
            "files_read": len(contents),
            "exclusions": exclusions,
            "gaps": gaps,
            "confidence": confidence,
        },
    }


def _markdown(data: dict) -> str:
    lines = [
        "## Repository identity",
        f"- Path: `{data['repository']['path']}`",
        f"- Resolved SHA: `{data['repository']['resolved_sha'] or 'not a Git checkout'}`",
        f"- Dirty: `{str(data['repository']['dirty']).lower()}`",
        "",
        "## Inventory & ownership boundaries",
        f"- Files considered: {data['coverage']['files_considered']}",
        f"- Top-level boundaries: {', '.join(data['inventory']['top_level_boundaries']) or 'none'}",
        "",
        "## Enhancement ask",
        data["ask"],
        "",
        "## Affected slice",
    ]
    lines.extend(f"- `{item['path']}` — {'; '.join(item['reasons'])}" for item in data["affected_slice"])
    lines.extend(["", "## Impact cone"])
    lines.extend(f"- `{item['path']}` — {'; '.join(item['reasons'])}" for item in data["impact_cone"])
    lines.extend(["", "## Explicit non-touch surfaces"])
    non_touch = data["explicit_non_touch"]
    NON_TOUCH_SAMPLE = 25
    if non_touch:
        lines.append(
            f"- {len(non_touch)} file(s) inventoried with no ask match or dependency "
            "edge to the affected slice"
        )
        touched_boundaries = {
            item["path"].split("/", 1)[0] for item in data["affected_slice"]
        } | {item["path"].split("/", 1)[0] for item in data["impact_cone"]}
        untouched_boundaries = sorted(
            {item["path"].split("/", 1)[0] for item in non_touch} - touched_boundaries
        )
        if untouched_boundaries:
            lines.append(
                f"- Top-level boundaries with no affected files: "
                f"{', '.join(untouched_boundaries)}"
            )
        lines.append(f"- Sample (first {min(NON_TOUCH_SAMPLE, len(non_touch))}):")
        lines.extend(f"  - `{item['path']}`" for item in non_touch[:NON_TOUCH_SAMPLE])
        if len(non_touch) > NON_TOUCH_SAMPLE:
            lines.append(
                f"  - … and {len(non_touch) - NON_TOUCH_SAMPLE} more "
                "(see machine-readable `--json` output for the full list)"
            )
    else:
        lines.append("- None; every inventoried file traces to the affected slice.")
    lines.extend([
        "", "## Coverage, exclusions & confidence",
        f"- Confidence: {data['coverage']['confidence']}",
        f"- Affected surfaces: {', '.join(data['affected_surfaces']) or 'not determined'}",
        f"- Exclusions: {len(data['coverage']['exclusions'])}",
        f"- Gaps: {len(data['coverage']['gaps'])}",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only E2 repository inventory and impact scan.")
    parser.add_argument("--path", required=True, help="A directory or a .zip archive to scan.")
    parser.add_argument("--ask", required=True)
    parser.add_argument("--subpath", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    source = Path(args.path).expanduser()
    try:
        if source.is_file() and zipfile.is_zipfile(source):
            # A zip is extracted read-only into a throwaway temp tree, scanned,
            # then discarded; the report still names the original archive.
            with tempfile.TemporaryDirectory(prefix="pm-os-scan-") as tmp:
                extracted = _extract_zip_for_scan(source, Path(tmp))
                data = scan(extracted, args.ask, args.subpath)
            data["repository"]["path"] = str(source.resolve())
            data["repository"]["source_archive"] = source.name
        elif source.is_file():
            raise ValueError(f"path is a file but not a valid .zip archive: {args.path}")
        else:
            data = scan(source, args.ask, args.subpath)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(data, ensure_ascii=False, sort_keys=True) if args.json else _markdown(data), end="")


if __name__ == "__main__":
    main()
