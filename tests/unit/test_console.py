"""Unit tests for lib/console.py — deciding whether a human is at stdin, so prompts
take their non-interactive branch inside agents. See docs/guides/testing.md §5 (T1)."""
import subprocess
import sys

import pytest

import console
from helpers import REPO_ROOT

pytestmark = pytest.mark.unit


class _Stream:
    def __init__(self, tty, raises=False):
        self._tty, self._raises = tty, raises

    def isatty(self):
        if self._raises:
            raise ValueError("I/O operation on closed file")
        return self._tty

    def fileno(self):
        raise OSError("no handle")


def test_non_tty_and_broken_streams_are_not_interactive():
    """A stream that says it is not a TTY, and a closed stream whose isatty() raises,
    are both non-interactive."""
    assert console.stdin_is_interactive(_Stream(False)) is False
    assert console.stdin_is_interactive(_Stream(True, raises=True)) is False


def test_tty_on_posix_is_interactive(monkeypatch):
    """Off Windows, a stream that reports isatty() True is trusted as before."""
    monkeypatch.setattr(console.sys, "platform", "linux")
    assert console.stdin_is_interactive(_Stream(True)) is True


def test_tty_on_windows_requires_a_console_handle(monkeypatch):
    """On Windows, isatty() alone is not enough: without a console handle (here, a
    stream with no usable file descriptor) the answer is non-interactive."""
    monkeypatch.setattr(console.sys, "platform", "win32")
    assert console.stdin_is_interactive(_Stream(True)) is False


@pytest.mark.skipif(sys.platform != "win32", reason="the NUL-device quirk is Windows-only")
def test_windows_nul_stdin_is_not_interactive():
    """Backlog #54. With stdin redirected from NUL (what an agent's shell gives a child
    process), Windows reports isatty() True, but stdin_is_interactive() is False."""
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import console; "
            "print(sys.stdin.isatty(), console.stdin_is_interactive())")
    out = subprocess.run([sys.executable, "-c", code, str(REPO_ROOT / "lib")],
                         stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    assert out.stdout.split() == ["True", "False"], out.stdout + out.stderr
