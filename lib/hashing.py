import hashlib
import json
import re


def hash_artifact_body(file_path: str) -> str:
    """SHA-256 of artifact body (everything after the closing frontmatter ---)."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    body = _extract_body(content)
    return _sha256(body)


def hash_event(event_dict: dict, prev_hash) -> str:
    """SHA-256 of canonicalized event JSON (event_hash excluded), prefixed with prev_hash."""
    d = {k: v for k, v in event_dict.items() if k != "event_hash"}
    canonical = json.dumps(d, sort_keys=True, ensure_ascii=False)
    data = (prev_hash or "") + canonical
    return _sha256(data)


def _extract_body(content: str) -> str:
    """Return body after the second --- frontmatter delimiter. LF-normalized."""
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    # Find closing ---
    match = re.search(r"^---\s*\n", content[3:], re.MULTILINE)
    if match:
        return content[3 + match.end():]
    return content


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
