import re
from pathlib import Path
from typing import Any

import yaml


def read(file_path: str) -> tuple[dict, str]:
    """Parse YAML frontmatter and body from a markdown file."""
    content = Path(file_path).read_text(encoding="utf-8")
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    if not content.startswith("---\n"):
        return {}, content

    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content

    fm_text = content[4:end]
    body = content[end + 5:]
    fm = yaml.safe_load(fm_text) or {}
    return fm, body


def write(file_path: str, frontmatter_dict: dict, body: str) -> None:
    """Write frontmatter + body to file."""
    fm_text = yaml.dump(frontmatter_dict, default_flow_style=False, allow_unicode=True, sort_keys=False)
    content = f"---\n{fm_text}---\n{body}"
    Path(file_path).write_text(content, encoding="utf-8")


def update_status(file_path: str, new_status: str, **kwargs: Any) -> None:
    """Flip status field and update any additional frontmatter fields atomically."""
    fm, body = read(file_path)
    fm["status"] = new_status
    for k, v in kwargs.items():
        fm[k] = v
    write(file_path, fm, body)
