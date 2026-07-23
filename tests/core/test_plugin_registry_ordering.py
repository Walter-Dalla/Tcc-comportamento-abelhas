"""Testes de ordenação topológica de plugins (Fase 2, plano seção 5)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from src.core.errors import PluginOrderingCycleError
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry


def _order(registry: PluginRegistry) -> list[str]:
    return [p.manifest.name for p in registry.for_kind(PluginKind.METADATA)]


def test_border_after_speed(make_plugin: Callable[..., Path], tmp_path: Path) -> None:
    """Caso canônico pedido pelo plano: border declara after=[speed]."""
    root = tmp_path / "plugins"
    make_plugin(root, "speed")
    make_plugin(root, "border", after=["speed"])
    registry = PluginRegistry()
    registry.discover([root])
    assert _order(registry) == ["speed", "border"]


def test_before_edge(make_plugin: Callable[..., Path], tmp_path: Path) -> None:
    """`speed.before=[border]` produz a mesma ordem que `border.after=[speed]`."""
    root = tmp_path / "plugins"
    make_plugin(root, "speed", before=["border"])
    make_plugin(root, "border")
    registry = PluginRegistry()
    registry.discover([root])
    assert _order(registry) == ["speed", "border"]


def test_priority_tiebreak(make_plugin: Callable[..., Path], tmp_path: Path) -> None:
    """Sem before/after entre si: maior priority roda primeiro."""
    root = tmp_path / "plugins"
    make_plugin(root, "baixa", priority=0)
    make_plugin(root, "alta", priority=10)
    registry = PluginRegistry()
    registry.discover([root])
    assert _order(registry) == ["alta", "baixa"]


def test_name_tiebreak_when_equal_priority(
    make_plugin: Callable[..., Path], tmp_path: Path
) -> None:
    """Empate total de priority -> ordem alfabética determinística."""
    root = tmp_path / "plugins"
    make_plugin(root, "zebra")
    make_plugin(root, "alpha")
    make_plugin(root, "mango")
    registry = PluginRegistry()
    registry.discover([root])
    assert _order(registry) == ["alpha", "mango", "zebra"]


def test_cycle_detected(make_plugin: Callable[..., Path], tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    make_plugin(root, "A", after=["B"])
    make_plugin(root, "B", after=["A"])
    registry = PluginRegistry()
    registry.discover([root])
    with pytest.raises(PluginOrderingCycleError) as exc_info:
        registry.for_kind(PluginKind.METADATA)
    assert "A" in str(exc_info.value)
    assert "B" in str(exc_info.value)


def test_missing_reference_ignored(make_plugin: Callable[..., Path], tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    make_plugin(root, "A", after=["nao_existe"])
    registry = PluginRegistry()
    registry.discover([root])
    # não levanta: restrição a nome ausente é ignorada com warning; A aparece normal
    assert _order(registry) == ["A"]
