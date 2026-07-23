"""Testes de rejeição de versão api/schema (Fase 2, plano seção 5)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from src.core.errors import PluginApiVersionError, PluginSchemaVersionError
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry


def test_unsupported_api_version_excluded(make_plugin: Callable[..., Path], tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    make_plugin(root, "ok")
    make_plugin(root, "futuro", api_version="99.0")
    registry = PluginRegistry()
    registry.discover([root])

    names = [p.manifest.name for p in registry.for_kind(PluginKind.METADATA)]
    assert names == ["ok"]
    assert any("PluginApiVersionError" in w and "futuro" in w for w in registry.discovery_warnings)


def test_incompatible_schema_range_excluded(
    make_plugin: Callable[..., Path], tmp_path: Path
) -> None:
    root = tmp_path / "plugins"
    make_plugin(root, "ok")
    make_plugin(root, "schema_futuro", schema=">=99.0")
    registry = PluginRegistry()
    registry.discover([root])

    names = [p.manifest.name for p in registry.for_kind(PluginKind.METADATA)]
    assert names == ["ok"]
    assert any(
        "PluginSchemaVersionError" in w and "schema_futuro" in w
        for w in registry.discovery_warnings
    )


def test_instantiate_raises_directly_on_api_mismatch(
    make_plugin: Callable[..., Path], tmp_path: Path
) -> None:
    root = tmp_path / "plugins"
    make_plugin(root, "futuro", api_version="99.0")
    registry = PluginRegistry()
    registry.discover([root])
    spec = registry._specs[(PluginKind.METADATA, "futuro")]
    with pytest.raises(PluginApiVersionError):
        registry.instantiate(spec)


def test_instantiate_raises_directly_on_schema_mismatch(
    make_plugin: Callable[..., Path], tmp_path: Path
) -> None:
    root = tmp_path / "plugins"
    make_plugin(root, "schema_futuro", schema=">=99.0")
    registry = PluginRegistry()
    registry.discover([root])
    spec = registry._specs[(PluginKind.METADATA, "schema_futuro")]
    with pytest.raises(PluginSchemaVersionError):
        registry.instantiate(spec)
