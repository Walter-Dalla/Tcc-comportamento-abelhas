"""Testes de PluginRegistry.discover (Fase 2, plano seção 5)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry


def test_valid_plugin_discovered(make_plugin: Callable[..., Path], tmp_path: Path) -> None:
    root = tmp_path / "plugins"
    make_plugin(root, "valido")
    registry = PluginRegistry()
    registry.discover([root])
    names = [p.manifest.name for p in registry.for_kind(PluginKind.METADATA)]
    assert names == ["valido"]


def test_invalid_manifests_skipped_with_warning(
    make_plugin: Callable[..., Path], tmp_path: Path, caplog
) -> None:
    root = tmp_path / "plugins"
    make_plugin(root, "valido")

    # inválido: sem `entry`
    sem_entry = root / "invalido_sem_entry"
    sem_entry.mkdir(parents=True)
    (sem_entry / "plugin.toml").write_text(
        '[plugin]\nname="invalido_sem_entry"\nversion="1.0.0"\nkind="metadata"\n'
        'api_version="1.0"\nschema=">=1.0"\n',
        encoding="utf-8",
    )

    # inválido: kind desconhecido
    kind_ruim = root / "invalido_kind_ruim"
    kind_ruim.mkdir(parents=True)
    (kind_ruim / "plugin.toml").write_text(
        '[plugin]\nname="invalido_kind_ruim"\nversion="1.0.0"\nkind="foo"\n'
        'entry="plugin:X"\napi_version="1.0"\nschema=">=1.0"\n',
        encoding="utf-8",
    )

    registry = PluginRegistry()
    with caplog.at_level(logging.WARNING):
        registry.discover([root])

    keys = set(registry._specs.keys())
    assert (PluginKind.METADATA, "valido") in keys
    assert not any(name.startswith("invalido") for _kind, name in keys)
    # cada inválido gerou uma entrada em discovery_warnings + um WARNING logado
    assert len(registry.discovery_warnings) == 2
    joined = " ".join(registry.discovery_warnings)
    assert "invalido_sem_entry" in joined
    assert "invalido_kind_ruim" in joined
    assert "manifest inválido" in caplog.text


def test_nonexistent_search_path_ignored(tmp_path: Path) -> None:
    registry = PluginRegistry()
    registry.discover([tmp_path / "nao_existe"])
    assert registry._specs == {}
    assert registry.discovery_warnings == []


def test_duplicate_plugin_keeps_first(make_plugin: Callable[..., Path], tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    make_plugin(root_a, "dup")
    make_plugin(root_b, "dup")
    registry = PluginRegistry()
    registry.discover([root_a, root_b])
    spec = registry._specs[(PluginKind.METADATA, "dup")]
    assert spec.source_dir == root_a / "dup"
    assert any("duplicado" in w for w in registry.discovery_warnings)
