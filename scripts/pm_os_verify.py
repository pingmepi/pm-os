#!/usr/bin/env python3
"""PM-OS install verifier.

Confirms a PM-OS installation is healthy for a given runtime and that the
deterministic gate logic runs in the current Python environment. This is the
verifier referenced by pm_os_update.py ("run the PM-OS verifier for your
runtime, if installed").

Runtime-agnostic: the same checks run under Claude and Codex. The gate is
exercised through the exact `python3 ~/.pm-os/hooks/pre-stage.py` invocation
the stage skills use, so a pass here proves parity, not just file presence.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PM_OS_DIR = Path(os.environ.get("PM_OS_DIR", str(Path.home() / ".pm-os")))
LIB_DIR = PM_OS_DIR / "lib"
HOOKS_DIR = PM_OS_DIR / "hooks"
CLAUDE_SKILLS_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))) / "skills"
CODEX_SKILLS_DIR = Path(os.environ.get("CODEX_SKILLS_DIR", str(Path.home() / ".agents" / "skills")))

REQUIRED_LIB_MODULES = ["project", "hashing", "frontmatter", "telemetry", "config"]
REQUIRED_HOOKS = ["pre-stage.py", "post-approve.py"]


class Result:
    def __init__(self):
        self.checks = []  # (ok: bool, label: str, detail: str)

    def add(self, ok, label, detail=""):
        self.checks.append((ok, label, detail))
        mark = "✓" if ok else "✗"
        line = f"  {mark} {label}"
        if detail:
            line += f"\n      {detail}"
        print(line)

    @property
    def ok(self):
        return all(c[0] for c in self.checks)


def check_install_dir(r: Result):
    r.add(PM_OS_DIR.is_dir(), f"PM-OS install present ({PM_OS_DIR})",
          "" if PM_OS_DIR.is_dir() else "Run the installer first.")


def check_version(r: Result):
    vpath = PM_OS_DIR / "VERSION"
    if vpath.exists():
        r.add(True, f"VERSION readable ({vpath.read_text().strip()})")
    else:
        r.add(False, "VERSION readable", f"Missing {vpath}")


def check_lib(r: Result):
    if not LIB_DIR.is_dir():
        r.add(False, "Installed lib present", f"Missing {LIB_DIR}")
        return
    sys.path.insert(0, str(LIB_DIR))
    missing = []
    for mod in REQUIRED_LIB_MODULES:
        try:
            __import__(mod)
        except Exception as e:  # noqa: BLE001 — surface any import failure
            missing.append(f"{mod} ({e.__class__.__name__})")
    r.add(not missing, "Shared lib imports",
          "" if not missing else "Failed: " + ", ".join(missing))


def check_hooks(r: Result):
    missing = [h for h in REQUIRED_HOOKS if not (HOOKS_DIR / h).exists()]
    r.add(not missing, f"Gate hooks present ({HOOKS_DIR})",
          "" if not missing else "Missing: " + ", ".join(missing))


def check_config(r: Result):
    try:
        from config import load_config  # imported from installed lib
        cfg = load_config()
        keys = ["pm_user", "feedback_repo", "projects_dir"]
        missing = [k for k in keys if not cfg.get(k)]
        r.add(not missing, "Config valid (~/.pm-os/config.yaml)",
              "" if not missing else "Missing keys: " + ", ".join(missing))
    except Exception as e:  # noqa: BLE001
        r.add(False, "Config valid (~/.pm-os/config.yaml)", str(e).splitlines()[0])


def check_skills(r: Result, runtime: str):
    src = PM_OS_DIR / "skills"
    if not src.is_dir():
        r.add(False, "Source skills present", f"Missing {src}")
        return
    expected = {p.name for p in src.iterdir() if p.is_dir()}
    candidates = []
    if runtime in ("claude", "all"):
        candidates.append(("claude", CLAUDE_SKILLS_DIR))
    if runtime in ("codex", "all"):
        candidates.append(("codex", CODEX_SKILLS_DIR))

    if runtime == "all":
        # A normal install targets a single runtime, so only check runtimes that
        # are actually installed; an absent dir means "not installed", not "broken".
        targets = [(name, sdir) for name, sdir in candidates if sdir.is_dir()]
        if not targets:
            r.add(False, "Skills installed",
                  "No runtime skills directory found — run the installer.")
            return
    else:
        # An explicitly requested runtime must be present.
        targets = candidates

    for name, sdir in targets:
        if not sdir.is_dir():
            r.add(False, f"{name} skills installed ({sdir})", "Directory missing — run the installer.")
            continue
        installed = {p.name for p in sdir.iterdir() if p.is_dir()}
        missing = sorted(expected - installed)
        r.add(not missing, f"{name} skills installed ({len(expected & installed)}/{len(expected)})",
              "" if not missing else "Missing: " + ", ".join(missing))


def check_gate_selftest(r: Result):
    """Run pre-stage.py exactly as skills do, in a throwaway project.

    Proves the gate (a) blocks when upstream is unapproved, (b) allows the
    first stage, and (c) does not hang on non-interactive stdin.
    """
    pre_stage = HOOKS_DIR / "pre-stage.py"
    if not pre_stage.exists():
        r.add(False, "Gate self-test", "pre-stage.py not found")
        return

    meta = (
        "schema_version: 2\n"
        "project_slug: pm-os-verify-selftest\n"
        "project_name: PM-OS Verify Self-Test\n"
        "genai_flag: false\n"
        'pm_os_version: "0"\n'
        "stages:\n"
        '  - id: "00"\n    name: business-statement\n    status: approved\n'
        "    content_hash: null\n    upstream_hashes_at_approval: {}\n    regeneration_count: 0\n    origin: generated\n"
        '  - id: "01"\n    name: brief\n    status: pending\n'
        "    content_hash: null\n    upstream_hashes_at_approval: {}\n    regeneration_count: 0\n    origin: generated\n"
        '  - id: "02"\n    name: scope\n    status: pending\n'
        "    content_hash: null\n    upstream_hashes_at_approval: {}\n    regeneration_count: 0\n    origin: generated\n"
    )

    def run_gate(stage, cwd):
        env = os.environ.copy()
        env["PM_OS_STAGE"] = stage
        return subprocess.run(
            [sys.executable, str(pre_stage)],
            cwd=cwd, env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=30,
        ).returncode

    with tempfile.TemporaryDirectory(prefix="pmos-verify-") as tmp:
        (Path(tmp) / ".meta.yaml").write_text(meta)
        try:
            blocked = run_gate("02", tmp)   # upstream 01 pending -> must block
            allowed = run_gate("01", tmp)   # upstream 00 approved -> must pass
        except subprocess.TimeoutExpired:
            r.add(False, "Gate self-test", "pre-stage.py hung (non-interactive timeout)")
            return

    ok = blocked != 0 and allowed == 0
    detail = "" if ok else f"expected block!=0/allow==0, got block={blocked}, allow={allowed}"
    r.add(ok, "Gate self-test (blocks unapproved upstream, allows first stage)", detail)


def check_telemetry_selftest(r: Result):
    """Log events into a throwaway project; assert they append, the hash chain
    validates, and push_all returns a clear status (without any network call)."""
    try:
        sys.path.insert(0, str(LIB_DIR))
        from telemetry import log, verify_chain
        from git_sync import push_all
    except Exception as e:  # noqa: BLE001
        r.add(False, "Telemetry self-test", f"import failed: {e}")
        return

    with tempfile.TemporaryDirectory(prefix="pmos-telemetry-") as tmp:
        proj = Path(tmp) / "proj"
        proj.mkdir()
        (proj / ".meta.yaml").write_text(
            "schema_version: 2\nproject_slug: pmos-verify-telemetry\n"
            "project_name: PM-OS Verify Telemetry\nstages: []\n"
        )
        try:
            log("stage_started", proj, "01", {"selftest": True})
            log("stage_generated", proj, "01", {"selftest": True})
        except Exception as e:  # noqa: BLE001
            r.add(False, "Telemetry self-test", f"log() raised: {e}")
            return

        tpath = proj / "telemetry.jsonl"
        n = sum(1 for ln in tpath.read_text().splitlines() if ln.strip()) if tpath.exists() else 0
        chain = verify_chain(proj)

        # push_all against an empty projects dir must report a clear status with
        # no git/network operation (the "no projects" branch).
        empty = Path(tmp) / "empty"
        empty.mkdir()
        status = push_all(str(empty))

    ok = n == 2 and chain["ok"] and isinstance(status, dict) and "ok" in status
    detail = "" if ok else f"events={n}, chain={chain}, push_status={status}"
    r.add(ok, "Telemetry self-test (append + hash chain + push status)", detail)


def check_context_pack(r: Result):
    """If a context overlay is installed, its manifest must parse; missing referenced
    files are warned (not failed). No overlay at all is fine (optional feature)."""
    ctx_dir = PM_OS_DIR / "context"
    manifest = ctx_dir / "context.yaml"
    if not manifest.exists():
        r.add(True, "Context overlay", "not configured (optional)")
        return
    try:
        import yaml
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        r.add(False, "Context overlay manifest parses", str(e).splitlines()[0])
        return

    referenced = list(data.get("global", []) or [])
    for entry in (data.get("stages") or {}).values():
        entry = entry or {}
        if entry.get("format"):
            referenced.append(entry["format"])
        referenced.extend(entry.get("examples", []) or [])
    missing = [rel for rel in referenced if not (ctx_dir / rel).exists()]

    # Dangling references are a warning, not a hard fail (the pack is optional and
    # a PM may be mid-edit) — surface them but keep the check green.
    detail = "manifest OK" if not missing else "WARNING — missing referenced files: " + ", ".join(missing)
    r.add(True, "Context overlay manifest", detail)


def main():
    parser = argparse.ArgumentParser(description="Verify a PM-OS installation.")
    parser.add_argument("--runtime", choices=["claude", "codex", "all"], default="all",
                        help="Which runtime's installed skills to check. "
                             "'all' checks every installed runtime and skips absent ones (default).")
    args = parser.parse_args()

    print("PM-OS Verify")
    print("============")
    print(f"Runtime: {args.runtime}\n")

    r = Result()
    check_install_dir(r)
    if not PM_OS_DIR.is_dir():
        print("\nFAIL: PM-OS is not installed.")
        sys.exit(1)
    check_version(r)
    check_lib(r)
    check_hooks(r)
    check_config(r)
    check_skills(r, args.runtime)
    check_gate_selftest(r)
    check_telemetry_selftest(r)
    check_context_pack(r)

    print()
    if r.ok:
        print("PASS: PM-OS install is healthy.")
        sys.exit(0)
    failed = sum(1 for c in r.checks if not c[0])
    print(f"FAIL: {failed} check(s) failed. See above.")
    sys.exit(1)


if __name__ == "__main__":
    main()
