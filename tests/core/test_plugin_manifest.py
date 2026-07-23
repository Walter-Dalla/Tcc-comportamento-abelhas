"""Testes de PluginManifest.from_toml (Fase 2, plano seção 5)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.plugin import PluginKind, PluginManifest, PluginOrdering, PluginRequires


def _write(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_valid_manifest_parses(tmp_path: Path) -> None:
    toml = _write(
        tmp_path / "plugin.toml",
        """\
        [plugin]
        name        = "background-subtraction-detector"
        version     = "1.0.0"
        kind        = "detector"
        entry       = "plugin:BackgroundSubtractionDetector"
        api_version = "1.0"
        schema      = ">=1.0,<2.0"

        [requires]
        python   = ">=3.11"
        packages = ["opencv-python>=4.9"]
        plugins  = []

        [ordering]
        before = []
        after  = ["speed"]
        priority = 100
        """,
    )
    manifest = PluginManifest.from_toml(toml)
    assert manifest.name == "background-subtraction-detector"
    assert manifest.kind is PluginKind.DETECTOR
    assert manifest.entry == "plugin:BackgroundSubtractionDetector"
    assert manifest.schema == ">=1.0,<2.0"
    assert manifest.requires.packages == ["opencv-python>=4.9"]
    assert manifest.ordering.after == ["speed"]
    assert manifest.ordering.priority == 100


def test_unknown_kind_rejected(tmp_path: Path) -> None:
    toml = _write(
        tmp_path / "plugin.toml",
        """\
        [plugin]
        name        = "x"
        version     = "1.0.0"
        kind        = "foo"
        entry       = "plugin:X"
        api_version = "1.0"
        schema      = ">=1.0"
        """,
    )
    with pytest.raises(ValidationError):
        PluginManifest.from_toml(toml)


def test_missing_entry_rejected(tmp_path: Path) -> None:
    toml = _write(
        tmp_path / "plugin.toml",
        """\
        [plugin]
        name        = "x"
        version     = "1.0.0"
        kind        = "metadata"
        api_version = "1.0"
        schema      = ">=1.0"
        """,
    )
    with pytest.raises(ValidationError):
        PluginManifest.from_toml(toml)


def test_missing_requires_and_ordering_use_defaults(tmp_path: Path) -> None:
    toml = _write(
        tmp_path / "plugin.toml",
        """\
        [plugin]
        name        = "x"
        version     = "1.0.0"
        kind        = "metadata"
        entry       = "plugin:X"
        api_version = "1.0"
        schema      = ">=1.0"
        """,
    )
    manifest = PluginManifest.from_toml(toml)
    assert manifest.requires == PluginRequires()
    assert manifest.ordering == PluginOrdering()
    assert manifest.ordering.priority == 0
