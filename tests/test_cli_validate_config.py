"""Testes do comando `animaltrack validate-config` (Fase 4, workstream A)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from src.app.cli import app
from src.core.schema.profile import Profile
from src.core.store import ProfileStore
from src.core.workspace import Workspace
from tests.fixtures.golden_config import golden_orientation

runner = CliRunner()


def _store(tmp_path: Path) -> ProfileStore:
    ws = Workspace(root=tmp_path)
    ws.ensure_dirs()
    return ProfileStore(ws)


def test_validate_config_reports_errors_without_traceback(tmp_path: Path) -> None:
    _store(tmp_path).save(Profile(name="sem_orientacao"))  # orientation=None
    result = runner.invoke(
        app, ["validate-config", "--workspace", str(tmp_path), "--profile", "sem_orientacao"]
    )
    assert result.exit_code == 1
    assert "Orientação da câmera não configurada." in result.output
    assert "Traceback" not in result.output


def test_validate_config_ok_for_valid_profile(tmp_path: Path) -> None:
    _store(tmp_path).save(Profile(name="ok", orientation=golden_orientation()))
    result = runner.invoke(
        app, ["validate-config", "--workspace", str(tmp_path), "--profile", "ok"]
    )
    assert result.exit_code == 0
    assert "[ok] OK" in result.stdout


def test_validate_config_all_profiles_when_no_profile_flag(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(Profile(name="ok", orientation=golden_orientation()))
    store.save(Profile(name="ruim"))
    result = runner.invoke(app, ["validate-config", "--workspace", str(tmp_path)])
    assert result.exit_code == 1  # pelo menos um inválido
