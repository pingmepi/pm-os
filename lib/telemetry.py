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


def flush_pending() -> None:
    """No-op for MVP — writes are synchronous."""
    pass
