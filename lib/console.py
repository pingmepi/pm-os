"""Console helpers shared by the scripts and hooks.

``stdin_is_interactive`` answers "is a human at a keyboard on the other end of
stdin?". Code that prompts with ``input()`` must call it instead of
``sys.stdin.isatty()`` (CLAUDE.md, non-interactive safety).

Plain ``isatty()`` gives the wrong answer on Windows. The ``NUL`` device is a
character device, and the C runtime's isatty is "is this a character device",
so an agent shell whose stdin is redirected from ``NUL`` reports
``isatty() == True``. ``input()`` then hits EOF, and any harness that feeds
stdin a byte could answer a PM-only prompt on the PM's behalf (backlog #54). On
Windows we therefore also require the handle to be a real console:
``GetConsoleMode`` succeeds only for console handles, and fails for ``NUL``,
pipes and files. Every other platform keeps the plain ``isatty()`` answer.
"""
from __future__ import annotations

import sys


def _is_windows_console(stream) -> bool:
    """True only when ``stream`` is backed by a Windows console handle."""
    try:
        import ctypes
        import msvcrt

        handle = msvcrt.get_osfhandle(stream.fileno())
        mode = ctypes.c_uint32()
        return bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)))
    except Exception:
        # Cannot prove a console is attached, so treat it as non-interactive:
        # the prompting code then takes its safe, non-interactive branch.
        return False


def stdin_is_interactive(stream=None) -> bool:
    """True when ``stream`` (default ``sys.stdin``) is an interactive terminal."""
    stream = sys.stdin if stream is None else stream
    try:
        if stream is None or not stream.isatty():
            return False
    except (AttributeError, ValueError, OSError):
        return False
    if sys.platform == "win32":
        return _is_windows_console(stream)
    return True


def ensure_utf8_stdio() -> None:
    """On Windows, make stdout/stderr UTF-8 so printing ✓, → or — cannot crash.

    When output is piped (an agent capturing it), Windows Python encodes stdout
    with the ANSI code page (cp1252). The first non-Latin-1 character then
    raises UnicodeEncodeError and kills the script mid-run (backlog #60). Only
    Windows is touched; every other platform already defaults to UTF-8. Call
    this once, at the top of each entry point.
    """
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # not a TextIOWrapper (e.g. replaced by a test harness)
            pass
