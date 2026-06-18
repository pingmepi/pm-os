#!/usr/bin/env python3
"""Discover roadmap tracking candidates and repo change signals.

This helper is read-only. It prints a compact Markdown report for the agent to
use before editing roadmap, implementation-plan, or status documents.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".next",
    ".nuxt",
    ".turbo",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "target",
    "vendor",
}

TRACKING_TERMS = (
    "roadmap",
    "implementation",
    "tracking",
    "tracker",
    "status",
    "plan",
    "milestone",
    "backlog",
    "release",
    "readiness",
    "todo",
)

PRODUCT_TERMS = (
    "brief",
    "scope",
    "prd",
    "requirements",
    "design",
    "spec",
    "qa",
    "metrics",
    "trd",
    "business",
    "context",
    "understanding",
)

CODE_LANDMARKS = {
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "Dockerfile",
    "docker-compose.yml",
}


def run_git(root: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def iter_files(root: Path, limit: int) -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".cache"))
        for name in sorted(names):
            path = Path(current) / name
            files.append(path)
            if len(files) >= limit:
                return files
    return files


def read_head(path: Path, limit: int = 65536) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit].lower()
    except OSError:
        return ""


def score(path: Path, root: Path, terms: tuple[str, ...]) -> int:
    rel = path.relative_to(root).as_posix().lower()
    name = path.name.lower()
    value = 0
    for term in terms:
        if term in name:
            value += 8
        if term in rel:
            value += 3
    if rel.startswith(("docs/", "plans/", "product/", "spec/", "requirements/")):
        value += 4
    if path.suffix.lower() in {".md", ".mdx", ".txt", ".rst"}:
        value += 2
        head = read_head(path)
        for marker in ("status", "owner", "horizon", "milestone", "updated", "blocker", "next step"):
            if marker in head:
                value += 2
    return value


def top_candidates(files: list[Path], root: Path, terms: tuple[str, ...], minimum: int) -> list[tuple[int, Path]]:
    candidates = [(score(path, root, terms), path) for path in files if path.suffix.lower() in {".md", ".mdx", ".txt", ".rst"}]
    return sorted((item for item in candidates if item[0] >= minimum), key=lambda item: (-item[0], item[1].as_posix()))[:20]


def print_lines(title: str, lines: list[str]) -> None:
    print(f"## {title}")
    if not lines:
        print("- None found")
    else:
        for line in lines:
            print(f"- {line}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover roadmap tracking docs and repo state.")
    parser.add_argument("root", nargs="?", default=".", help="Product repo or project root")
    parser.add_argument("--limit", type=int, default=6000, help="Maximum files to scan")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        parser.error(f"root is not a directory: {root}")

    files = iter_files(root, args.limit)
    branch = run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    head = run_git(root, ["rev-parse", "--short", "HEAD"])
    status = run_git(root, ["status", "--short"])
    diff_names = run_git(root, ["diff", "--name-status"])
    staged_names = run_git(root, ["diff", "--cached", "--name-status"])

    print(f"# Roadmap Tracking Discovery")
    print()
    print(f"- Root: `{root}`")
    print(f"- Files scanned: {len(files)}")
    if branch or head:
        print(f"- Git: `{branch or 'unknown'}` @ `{head or 'unknown'}`")
    else:
        print("- Git: not detected")
    print()

    print_lines("Git Status", status.splitlines()[:80] if status else [])
    print_lines("Unstaged Changes", diff_names.splitlines()[:80] if diff_names else [])
    print_lines("Staged Changes", staged_names.splitlines()[:80] if staged_names else [])

    tracking = top_candidates(files, root, TRACKING_TERMS, minimum=8)
    product = top_candidates(files, root, PRODUCT_TERMS, minimum=8)
    landmarks = sorted(path.relative_to(root).as_posix() for path in files if path.name in CODE_LANDMARKS)[:40]

    print_lines(
        "Likely Tracking Docs",
        [f"`{path.relative_to(root).as_posix()}` (score {points})" for points, path in tracking],
    )
    print_lines(
        "Likely Product Docs",
        [f"`{path.relative_to(root).as_posix()}` (score {points})" for points, path in product],
    )
    print_lines("Codebase Landmarks", [f"`{item}`" for item in landmarks])

    if len(files) >= args.limit:
        print(f"> Scan stopped at --limit {args.limit}; rerun with a larger limit if needed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
