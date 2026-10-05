"""T3 — Windows portability contracts (backlog #54, #60, GH #77-6/#77-7/#77-8).
Static checks that keep the Windows fixes from regressing: explicit UTF-8 on all
text I/O, UTF-8 console output in every entry point, the console-aware stdin
check for prompts, and skill snippets that resolve ~/.pm-os/lib in Python rather
than through the shell's $HOME. See docs/guides/testing.md §5 (T3)."""
import ast

import pytest

from helpers import REPO_ROOT

pytestmark = pytest.mark.contract

CODE_FILES = sorted(
    [*(REPO_ROOT / "lib").glob("*.py"), *(REPO_ROOT / "scripts").glob("*.py"),
     *(REPO_ROOT / "hooks").glob("*.py")]
)
# Entry points that print only ASCII and deliberately import nothing from lib/.
ASCII_ONLY_ENTRY_POINTS = {"discover_tracking_context.py", "pm_codebase_inventory.py"}


def _text_io_without_encoding(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or any(k.arg == "encoding" for k in node.keywords):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ("read_text", "write_text"):
            yield node.lineno, func.attr
        elif isinstance(func, ast.Name) and func.id == "open":
            mode = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else None
            for k in node.keywords:
                if k.arg == "mode" and isinstance(k.value, ast.Constant):
                    mode = k.value.value
            if not (mode and "b" in mode):
                yield node.lineno, "open"


def test_all_text_io_names_utf8():
    """GH #77-7. Every read_text/write_text/text-mode open() in lib/, scripts/ and
    hooks/ passes encoding=. Without it Windows uses cp1252: an em dash was written
    as byte 0x97 and corrupted .sources.yaml."""
    offenders = [f"{p.relative_to(REPO_ROOT)}:{line} {call}"
                 for p in CODE_FILES for line, call in _text_io_without_encoding(p)]
    assert not offenders, "text I/O without encoding=:\n" + "\n".join(offenders)


def test_every_entry_point_sets_utf8_console_output():
    """Backlog #60 / GH #77-8. Each script and hook makes stdout/stderr UTF-8 on
    Windows at startup, so printing ✓ into a piped (cp1252) stdout cannot crash it."""
    missing = []
    for path in [*(REPO_ROOT / "scripts").glob("*.py"), *(REPO_ROOT / "hooks").glob("*.py")]:
        if path.name in ASCII_ONLY_ENTRY_POINTS:
            continue
        text = path.read_text(encoding="utf-8")
        if "ensure_utf8_stdio()" not in text and 'reconfigure(encoding="utf-8"' not in text:
            missing.append(path.name)
    assert not missing, f"entry points without UTF-8 console setup: {missing}"


def test_prompts_use_the_console_aware_stdin_check():
    """Backlog #54. Nothing outside lib/console.py decides "is a human there?" with
    sys.stdin.isatty(): on Windows an agent's NUL stdin reports True."""
    offenders = [str(p.relative_to(REPO_ROOT)) for p in CODE_FILES
                 if p.name != "console.py" and "sys.stdin.isatty()" in p.read_text(encoding="utf-8")]
    assert not offenders, offenders


def test_skill_snippets_do_not_resolve_lib_through_shell_home():
    """GH #77-6. Skill snippets add ~/.pm-os/lib with os.path.expanduser in Python.
    Interpolating $HOME into the Python string breaks under Git Bash on Windows,
    where $HOME is /c/Users/... and Python cannot import from it."""
    offenders = [str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "skills").rglob("SKILL.md")
                 if "'$HOME/.pm-os/lib'" in p.read_text(encoding="utf-8")]
    assert not offenders, offenders
