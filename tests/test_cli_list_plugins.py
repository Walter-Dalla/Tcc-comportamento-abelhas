"""Testes do comando `animaltrack list-plugins` (Fase 4, workstream A)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from src.app.cli import app

runner = CliRunner()


def test_list_plugins_filters_by_kind(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["list-plugins", "--workspace", str(tmp_path), "--kind", "exporter"]
    )
    assert result.exit_code == 0
    assert "route-plot" in result.stdout
    assert "pdf-report" in result.stdout
    assert "speed" not in result.stdout  # metadata, filtrado fora


def test_list_plugins_without_filter_lists_all(tmp_path: Path) -> None:
    result = runner.invoke(app, ["list-plugins", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    for name in ("speed", "border", "route-plot", "pdf-report"):
        assert name in result.stdout


def test_list_plugins_invalid_kind_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["list-plugins", "--workspace", str(tmp_path), "--kind", "naoexiste"]
    )
    assert result.exit_code == 1
