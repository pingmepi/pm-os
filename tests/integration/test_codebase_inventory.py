"""E2 deterministic whole-repo inventory and affected-slice/impact-cone evidence."""
from __future__ import annotations

import hashlib
import json
import zipfile
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


def _zip_dir(repo: Path, zip_path: Path, wrap: str | None = None) -> Path:
    with zipfile.ZipFile(zip_path, "w") as archive:
        for path in sorted(repo.rglob("*")):
            if path.is_file():
                rel = path.relative_to(repo).as_posix()
                archive.write(path, f"{wrap}/{rel}" if wrap else rel)
    return zip_path


def test_scan_accepts_a_zip_archive_matching_the_directory_scan(pmos, tmp_path):
    """A zipped codebase scans read-only to the same slice as the extracted dir."""
    repo = _fixture_repo(tmp_path)
    zip_path = _zip_dir(repo, tmp_path / "monorepo.zip", wrap="monorepo")
    before = _digest(repo)
    ask = "add account export API with a web action"

    from_dir = run_script(pmos, "pm_codebase_inventory.py", "--path", str(repo), "--ask", ask, "--json")
    from_zip = run_script(pmos, "pm_codebase_inventory.py", "--path", str(zip_path), "--ask", ask, "--json")

    assert from_dir.returncode == 0, from_dir.stderr
    assert from_zip.returncode == 0, from_zip.stderr
    dir_data = json.loads(from_dir.stdout)
    zip_data = json.loads(from_zip.stdout)
    # Same evidence regardless of source shape.
    assert zip_data["inventory"]["files"] == dir_data["inventory"]["files"]
    assert {i["path"] for i in zip_data["affected_slice"]} == {i["path"] for i in dir_data["affected_slice"]}
    assert zip_data["affected_surfaces"] == dir_data["affected_surfaces"]
    # The report names the archive, not the throwaway temp dir.
    assert zip_data["repository"]["path"] == str(zip_path.resolve())
    assert zip_data["repository"]["source_archive"] == "monorepo.zip"
    assert _digest(repo) == before  # the source tree is never touched


def test_relative_imports_pull_dependencies_into_the_impact_cone(pmos, tmp_path):
    """Python dotted (`from .helpers`) and JS/TS path (`./client`) relative imports
    resolve, so a non-ask-matched dependency is traced into the cone, not non-touch."""
    repo = tmp_path / "relrepo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "pkg" / "orders.py").write_text(
        "from .helpers import fmt\ndef order_listing_page(): return fmt()\n", encoding="utf-8")
    (repo / "pkg" / "helpers.py").write_text("def fmt(): return 1\n", encoding="utf-8")
    (repo / "web").mkdir()
    (repo / "web" / "OrdersPage.tsx").write_text(
        "import { send } from './client'\nexport const view = () => send()\n", encoding="utf-8")
    (repo / "web" / "client.ts").write_text(
        "export const send = () => fetch('/x')\n", encoding="utf-8")

    result = run_script(pmos, "pm_codebase_inventory.py", "--path", str(repo),
                        "--ask", "order listing page", "--json")

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    direct = {i["path"] for i in data["affected_slice"] if i["score"] >= 2}
    cone = {i["path"] for i in data["impact_cone"]}
    non_touch = {i["path"] for i in data["explicit_non_touch"]}
    assert {"pkg/orders.py", "web/OrdersPage.tsx"} <= direct
    assert "pkg/helpers.py" in cone, "python relative dependency not traced"
    assert "web/client.ts" in cone, "ts relative dependency not traced"
    assert not ({"pkg/helpers.py", "web/client.ts"} & non_touch)


def test_scan_rejects_a_non_archive_file(pmos, tmp_path):
    """A plain file that is not a valid zip is a clear error, not a traceback."""
    bogus = tmp_path / "notes.txt"
    bogus.write_text("not a codebase\n", encoding="utf-8")

    result = run_script(pmos, "pm_codebase_inventory.py", "--path", str(bogus), "--ask", "x", "--json")

    assert result.returncode != 0
    assert "not a valid .zip archive" in result.stderr
