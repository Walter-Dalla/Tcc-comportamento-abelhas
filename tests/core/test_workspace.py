"""Testes de workspace.py (Fase 1)."""

from pathlib import Path

from src.core.workspace import Workspace


def test_subpaths_under_root():
    ws = Workspace(root=Path("/some/root"))
    assert ws.config_path == Path("/some/root/config")
    assert ws.outputs == Path("/some/root/outputs")
    assert ws.plugins == Path("/some/root/plugins")
    assert ws.profiles_file() == Path("/some/root/config/profiles.json")
    assert ws.result_file("fish01") == Path("/some/root/outputs/fish01.json")


def test_resolve_cli_path_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("ANIMALTRACK_WORKSPACE", str(tmp_path / "env"))
    ws = Workspace.resolve(cli_path=tmp_path / "cli")
    assert ws.root == tmp_path / "cli"


def test_resolve_env_used_when_no_cli(monkeypatch, tmp_path):
    monkeypatch.setenv("ANIMALTRACK_WORKSPACE", str(tmp_path / "env"))
    ws = Workspace.resolve()
    assert ws.root == tmp_path / "env"


def test_resolve_default_home(monkeypatch, tmp_path):
    monkeypatch.delenv("ANIMALTRACK_WORKSPACE", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    ws = Workspace.resolve()
    assert ws.root == tmp_path / ".animaltrack"


def test_ensure_dirs_creates_and_is_idempotent(tmp_workspace):
    tmp_workspace.ensure_dirs()
    assert tmp_workspace.config_path.is_dir()
    assert tmp_workspace.outputs.is_dir()
    assert tmp_workspace.plugins.is_dir()
    # idempotente: chamar 2x não levanta erro.
    tmp_workspace.ensure_dirs()
