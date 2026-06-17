import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from hashing import hash_event
from config import load_config


def log(event_type: str, project_root: Path, stage, payload: dict) -> None:
    """Append a hash-chained telemetry event to project telemetry.jsonl."""
    telemetry_path = project_root / "telemetry.jsonl"

    try:
        pm = load_config()["pm_user"]
    except Exception:
        pm = "unknown"
    meta_path = project_root / ".meta.yaml"

    import yaml
    with open(meta_path, "r") as f:
        meta = yaml.safe_load(f)

    prev_hash = _last_event_hash(telemetry_path)

    event = {
        "event_id": str(uuid.uuid4()),
        "prev_event_hash": prev_hash,
        "event_hash": None,  # filled in after computing
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pm": pm,
        "project": meta["project_slug"],
        "pm_os_version": meta.get("pm_os_version", "0.1.0"),
        "event_type": event_type,
        "stage": stage,
        "payload": payload,
    }

    event["event_hash"] = hash_event(event, prev_hash)

    with open(telemetry_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _last_event_hash(telemetry_path: Path):
    if not telemetry_path.exists():
        return None
    last_line = None
    with open(telemetry_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                last_line = line
    if last_line is None:
        return None
    event = json.loads(last_line)
    return event.get("event_hash")


def last_event(project_root: Path, event_type=None, stage=None):
    """Return the most recent telemetry event, optionally filtered by type/stage.

    telemetry.jsonl is append-only and chronological, so the last matching line
    is the most recent event. Returns the parsed event dict, or None if there is
    no match (or no telemetry file yet).
    """
    telemetry_path = Path(project_root) / "telemetry.jsonl"
    if not telemetry_path.exists():
        return None
    found = None
    with open(telemetry_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if event_type is not None and ev.get("event_type") != event_type:
                continue
            if stage is not None and ev.get("stage") != stage:
                continue
            found = ev
    return found


def verify_chain(project_root) -> dict:
    """Recompute a project's telemetry hash chain and report the first break.

    Returns {"ok", "events", "break_at", "reason"}. break_at is the 1-based line
    number of the first inconsistent event (None when intact).
    """
    telemetry_path = Path(project_root) / "telemetry.jsonl"
    if not telemetry_path.exists():
        return {"ok": True, "events": 0, "break_at": None, "reason": "no telemetry file"}

    prev = None
    n = 0
    with open(telemetry_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            n += 1
            try:
                ev = json.loads(line)
            except Exception as e:
                return {"ok": False, "events": n, "break_at": i, "reason": f"invalid JSON ({e})"}
            if ev.get("prev_event_hash") != prev:
                return {"ok": False, "events": n, "break_at": i, "reason": "prev_event_hash does not match prior event"}
            if hash_event(ev, prev) != ev.get("event_hash"):
                return {"ok": False, "events": n, "break_at": i, "reason": "event_hash mismatch (tampered or corrupted)"}
            prev = ev.get("event_hash")
    return {"ok": True, "events": n, "break_at": None, "reason": "intact"}


def flush_pending() -> None:
    """No-op for MVP — writes are synchronous."""
    pass
