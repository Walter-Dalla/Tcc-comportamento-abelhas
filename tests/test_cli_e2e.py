"""Testes ponta-a-ponta da CLI (Fase 4, workstream A)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.app.cli import app
from src.core.store import ProfileStore
from src.core.workspace import Workspace
from tests.fixtures.golden_config import VIDEOS_DIR, golden_profile

runner = CliRunner()
_REPO_ROOT = Path(__file__).resolve().parent.parent

_videos_missing = not (VIDEOS_DIR / "main_top.avi").exists()
requires_videos = pytest.mark.skipif(
    _videos_missing,
    reason="vídeos de fixture ausentes — rode `python -m tests.fixtures.generate_fixture_videos`",
)


def _seed_workspace(tmp_path: Path, profile_name: str = "fixture01") -> Workspace:
    ws = Workspace(root=tmp_path)
    ws.ensure_dirs()
    ProfileStore(ws).save(golden_profile(name=profile_name))
    return ws


@requires_videos
def test_run_generates_json_and_pdf_headless(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    result = runner.invoke(app, ["run", "--workspace", str(tmp_path), "--profile", "fixture01"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "outputs" / "fixture01.json").exists()
    assert (tmp_path / "outputs" / "fixture01" / "report.pdf").exists()
    assert (tmp_path / "outputs" / "fixture01" / "route.png").exists()


def test_run_missing_profile_exits_nonzero(tmp_path: Path) -> None:
    ws = Workspace(root=tmp_path)
    ws.ensure_dirs()
    result = runner.invoke(app, ["run", "--workspace", str(tmp_path), "--profile", "naoexiste"])
    assert result.exit_code == 1
    assert "Traceback" not in result.output


def test_cli_process_never_imports_tkinter(tmp_path: Path) -> None:
    """O import de `src.app.cli` + a invocação do comando `run` não podem trazer
    tkinter (nem estático nem lazy). Roda num interpretador NOVO (subprocess) para
    não ser poluído por outro teste da mesma sessão pytest que já importou Tk."""
    if not _videos_missing:
        _seed_workspace(tmp_path)
    script = (
        "import sys\n"
        "from src.app.cli import app\n"
        "try:\n"
        f"    app(['run', '--workspace', {str(tmp_path)!r}, '--profile', 'fixture01'],"
        " standalone_mode=False)\n"
        "except (SystemExit, Exception):\n"
        "    pass\n"
        "print('TK_IMPORTED' if 'tkinter' in sys.modules else 'TK_CLEAN')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    assert "TK_CLEAN" in proc.stdout, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
