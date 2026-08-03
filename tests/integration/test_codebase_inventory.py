"""E2 deterministic whole-repo inventory and affected-slice/impact-cone evidence."""
import hashlib
import json
from pathlib import Path

import pytest

from helpers import run_script

pytestmark = pytest.mark.integration


def _digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "monorepo"
    files = {
        "README.md": "Account platform with an API and dashboard.\n",
        "package.json": '{"workspaces":["apps/*","packages/*"]}\n',
        "apps/api/routes/account.py": (
            "from services.export import export_account\n"
            "def account_export_route(user_id): return export_account(user_id)\n"
        ),
        "apps/api/services/export.py": (
            "from packages.auth.session import require_session\n"
            "from packages.data.account import Account\n"
            "def export_account(user_id):\n"
            "    require_session(user_id)\n"
            "    return Account.load(user_id).as_json()\n"
        ),
        "apps/api/services/billing.py": "def charge_card(): return True\n",
        "apps/web/account/ExportButton.tsx": (
            "export const ExportButton = () => fetch('/api/account/export')\n"
        ),
        "packages/auth/session.py": "def require_session(user_id): return user_id\n",
        "packages/data/account.py": "class Account:\n    pass\n",
        "tests/test_account_export.py": (
            "from apps.api.services.export import export_account\n"
            "def test_export(): assert export_account\n"
        ),
        ".github/workflows/test.yml": "name: test\n",
        "deploy/api.yaml": "service: account-api\n",
    }
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return repo


def test_inventory_finds_slice_impact_cone_surfaces_and_non_touch_paths(pmos, tmp_path):
    """Inventory starts wide, focuses by ask, and follows consumers/dependencies."""
    repo = _fixture_repo(tmp_path)
    before = _digest(repo)

    result = run_script(
        pmos,
        "pm_codebase_inventory.py",
        "--path",
        str(repo),
        "--ask",
        "add account export API with a web action",
        "--json",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    inventory_paths = data["inventory"]["files"]
    direct = {item["path"] for item in data["affected_slice"]}
    cone = {item["path"] for item in data["impact_cone"]}
    non_touch = {item["path"] for item in data["explicit_non_touch"]}
    assert "package.json" in inventory_paths
    assert "apps/api/services/export.py" in direct
    assert "apps/api/routes/account.py" in direct | cone
    assert "apps/web/account/ExportButton.tsx" in direct | cone
    assert "packages/auth/session.py" in cone
    assert "packages/data/account.py" in direct | cone
    assert "tests/test_account_export.py" in direct | cone
    assert "apps/api/services/billing.py" in non_touch
    assert {"ui", "api", "data", "service"}.issubset(set(data["affected_surfaces"]))
    assert data["coverage"]["files_considered"] == len(inventory_paths)
    assert data["coverage"]["confidence"] in {"high", "medium"}
    assert _digest(repo) == before


def test_inventory_reports_dynamic_boundaries_as_gaps(pmos, tmp_path):
    """Reflection/dynamic loading widens uncertainty instead of claiming full coverage."""
    repo = _fixture_repo(tmp_path)
    dynamic = repo / "apps" / "api" / "services" / "export.py"
    dynamic.write_text(
        dynamic.read_text(encoding="utf-8")
        + "\nhandler = __import__('plugins.' + user_id)\n",
        encoding="utf-8",
    )

    result = run_script(
        pmos,
        "pm_codebase_inventory.py",
        "--path",
        str(repo),
        "--ask",
        "account export",
        "--json",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    assert any(gap["kind"] == "dynamic-boundary" for gap in data["coverage"]["gaps"])
    assert data["coverage"]["confidence"] == "medium"
