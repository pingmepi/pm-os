"""Per-project record of the last central-sync attempt (backlog #62).

``git_sync`` writes it after every attempt; ``/pm-status`` reads it. It lives
apart from ``git_sync`` so read-only commands never import the network code.
The background push writes only to ``.pm-os-sync.log``, so before this record a
sync that failed every time (no credentials) was invisible to the PM.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

SYNC_STATUS_FILENAME = ".pm-os-sync.json"
# git messages meaning "no credentials for the feedback repo", not a network blip.
AUTH_FAILURE_MARKERS = (
    "could not read username", "could not read password", "authentication failed",
    "terminal prompts disabled", "permission denied (publickey)", "invalid username or password",
)


def is_auth_failure(reason: str | None) -> bool:
    """True when a sync failure reason means credentials are missing or rejected."""
    text = (reason or "").lower()
    return any(marker in text for marker in AUTH_FAILURE_MARKERS)


def read_sync_status(project_root) -> dict | None:
    """The last recorded sync attempt for a project, or None if none was recorded."""
    path = Path(project_root) / SYNC_STATUS_FILENAME
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def record_sync_status(roots, result: dict) -> None:
    """Write each project's sync outcome. Best-effort: never breaks a sync."""
    now = datetime.now(timezone.utc).isoformat()
    failed = set(result.get("failed") or [])
    for root in roots:
        root = Path(root)
        if not (root / ".meta.yaml").exists():
            continue
        ok = bool(result.get("ok")) and root.name not in failed
        status = read_sync_status(root) or {}
        status.update({"last_attempt_at": now, "ok": ok, "reason": result.get("reason")})
        if ok:
            status["last_success_at"] = now
        try:
            (root / SYNC_STATUS_FILENAME).write_text(json.dumps(status, indent=2) + "\n",
                                                     encoding="utf-8")
        except OSError:
            pass
