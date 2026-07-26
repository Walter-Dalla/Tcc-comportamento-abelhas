"""Testes da seção `[config]` opcional de `plugin.toml` (Fase 6, aditivo).

Cobre `PluginManifest.config` (populado por `from_toml`) e o helper
`PluginManifest.validate_overrides()` — documentação + checagem de tipo
OPCIONAL, nunca allowlist nem gate de execução. Ver `docs/PLUGIN_CONTRACT.md`
seção 2 e `plugins/metadata/fish-body-fat/plugin.toml` para o exemplo real.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from src.core.plugin import PluginConfigField, PluginManifest


def _write(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def _base_manifest_toml(extra: str = "") -> str:
    return (
        """\
        [plugin]
        name        = "x"
        version     = "1.0.0"
        kind        = "metadata"
        entry       = "plugin:X"
        api_version = "1.0"
        schema      = ">=1.0"
        """
        + extra
    )


# --- parsing -----------------------------------------------------------------
def test_config_section_parses_into_typed_fields(tmp_path: Path) -> None:
    toml = _write(
        tmp_path / "plugin.toml",
        _base_manifest_toml(
            """
            [config]
            fish_length_cm = { type = "float", required = false, description = "Comprimento do peixe em cm" }
            sample_rate = { type = "int", required = true, default = 10 }
            """
        ),
    )
    manifest = PluginManifest.from_toml(toml)

    assert set(manifest.config) == {"fish_length_cm", "sample_rate"}

    fish_field = manifest.config["fish_length_cm"]
    assert fish_field == PluginConfigField(
        type="float", required=False, description="Comprimento do peixe em cm"
    )

    rate_field = manifest.config["sample_rate"]
    assert rate_field.type == "int"
    assert rate_field.required is True
    assert rate_field.default == 10
    assert rate_field.description == ""


def test_missing_config_section_defaults_to_empty_dict(tmp_path: Path) -> None:
    """Backward compat: manifestos existentes (sem `[config]`) continuam válidos."""
    toml = _write(tmp_path / "plugin.toml", _base_manifest_toml())

    manifest = PluginManifest.from_toml(toml)

    assert manifest.config == {}


# --- validate_overrides ------------------------------------------------------
def _manifest_with_config(tmp_path: Path, config_toml_body: str) -> PluginManifest:
    toml = _write(
        tmp_path / "plugin.toml",
        _base_manifest_toml(f"\n[config]\n{config_toml_body}\n"),
    )
    return PluginManifest.from_toml(toml)


def test_validate_overrides_reports_missing_required_field(tmp_path: Path) -> None:
    manifest = _manifest_with_config(
        tmp_path, 'fish_length_cm = { type = "float", required = true }'
    )

    errors = manifest.validate_overrides({})

    assert len(errors) == 1
    assert "fish_length_cm" in errors[0]


def test_validate_overrides_empty_when_required_field_satisfied(tmp_path: Path) -> None:
    manifest = _manifest_with_config(
        tmp_path, 'fish_length_cm = { type = "float", required = true }'
    )

    errors = manifest.validate_overrides({"fish_length_cm": 12.5})

    assert errors == []


def test_validate_overrides_reports_type_mismatch(tmp_path: Path) -> None:
    manifest = _manifest_with_config(
        tmp_path, 'fish_length_cm = { type = "float", required = false }'
    )

    errors = manifest.validate_overrides({"fish_length_cm": "not-a-number"})

    assert len(errors) == 1
    assert "fish_length_cm" in errors[0]


def test_validate_overrides_accepts_int_for_float_field(tmp_path: Path) -> None:
    """Leniência deliberada: coerção numérica int->float é comum em JSON/TOML."""
    manifest = _manifest_with_config(
        tmp_path, 'fish_length_cm = { type = "float", required = false }'
    )

    errors = manifest.validate_overrides({"fish_length_cm": 12})

    assert errors == []


def test_validate_overrides_rejects_bool_for_int_field(tmp_path: Path) -> None:
    """Gotcha explícito: bool é subclasse de int em Python, mas não deve satisfazer
    um campo declarado 'int' (nem 'float') — trocaria silenciosamente um valor."""
    manifest = _manifest_with_config(tmp_path, 'flag_like = { type = "int", required = false }')

    errors = manifest.validate_overrides({"flag_like": True})

    assert len(errors) == 1


def test_validate_overrides_ignores_undeclared_keys(tmp_path: Path) -> None:
    """`[config]` não é allowlist — overrides livres, não declarados, continuam ok."""
    manifest = _manifest_with_config(
        tmp_path, 'fish_length_cm = { type = "float", required = false }'
    )

    errors = manifest.validate_overrides({"fish_length_cm": 10.0, "some_other_key": "whatever"})

    assert errors == []
