"""Testes de `animaltrack plugin install|list|remove` (Fase 6, workstream C).

Cobre o plano seção 5: instalação de um plugin EXTERNO (criado fora dos diretórios
de busca built-in), descoberta pelo registry, execução real dentro de um
`Pipeline.run`, e os casos negativos (manifest inválido, colisão de nome).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.app.cli import app
from src.core.pipeline import Pipeline, RunRequest
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.store import ResultStore
from src.core.workspace import Workspace
from tests.conftest import make_result

runner = CliRunner()

_EXTERNAL_PLUGIN_SRC = textwrap.dedent(
    """\
    from src.core.schema.result import Metric
    from src.core.stages import MetadataPlugin


    class ExternalPlugin(MetadataPlugin):
        def run(self, ctx):
            ctx.add_metric(
                Metric(name="external_marker", value=42.0, unit="u", producer="external-demo")
            )
    """
)


def _write_plugin(
    root: Path,
    *,
    name: str = "external-demo",
    version: str = "1.0.0",
    kind: str = "metadata",
    entry: str = "plugin:ExternalPlugin",
    api_version: str = "1.0",
    schema: str = ">=1.0,<2.0",
    src: str | None = _EXTERNAL_PLUGIN_SRC,
    omit_field: str | None = None,
) -> Path:
    """Escreve um plugin de teste num diretório qualquer (fora das search paths)."""
    plugin_dir = root / f"{name}-source"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    fields = {
        "name": f'"{name}"',
        "version": f'"{version}"',
        "kind": f'"{kind}"',
        "entry": f'"{entry}"',
        "api_version": f'"{api_version}"',
        "schema": f'"{schema}"',
    }
    if omit_field:
        fields.pop(omit_field)
    body = "\n".join(f"{k} = {v}" for k, v in fields.items())
    (plugin_dir / "plugin.toml").write_text(f"[plugin]\n{body}\n", encoding="utf-8")
    if src is not None:
        (plugin_dir / "plugin.py").write_text(src, encoding="utf-8")
    return plugin_dir


# --- caminho feliz ----------------------------------------------------------
def test_install_from_local_path_then_discover_and_run(tmp_path: Path) -> None:
    source = _write_plugin(tmp_path)
    ws_root = tmp_path / "ws"

    result = runner.invoke(app, ["plugin", "install", str(source), "--workspace", str(ws_root)])
    assert result.exit_code == 0, result.output
    assert "external-demo" in result.output

    # 1. arquivos copiados para <workspace>/plugins/<name>/ (nome vem do MANIFEST)
    installed_dir = ws_root / "plugins" / "external-demo"
    assert (installed_dir / "plugin.toml").is_file()
    assert (installed_dir / "plugin.py").is_file()

    # 2. o registry encontra o plugin recém-instalado
    ws = Workspace(root=ws_root)
    registry = PluginRegistry()
    registry.discover([ws.plugins])
    assert "external-demo" in {m.name for m in registry.manifests(PluginKind.METADATA)}

    # 3. ele roda de verdade num Pipeline e sua métrica aparece no AnalysisResult
    ResultStore(ws).save(make_result(profile="p"))
    run_result = Pipeline(registry).run(RunRequest(profile="p", workspace=str(ws_root)))
    assert run_result.plugin_failures == []
    assert run_result.result is not None
    assert run_result.result.metrics["external_marker"].value == 42.0


def test_installed_plugin_appears_in_plugin_list(tmp_path: Path) -> None:
    source = _write_plugin(tmp_path)
    ws_root = tmp_path / "ws"
    runner.invoke(app, ["plugin", "install", str(source), "--workspace", str(ws_root)])

    result = runner.invoke(app, ["plugin", "list", "--workspace", str(ws_root)])

    assert result.exit_code == 0
    assert "external-demo" in result.output


def test_plugin_list_empty_workspace(tmp_path: Path) -> None:
    result = runner.invoke(app, ["plugin", "list", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    assert "nenhum plugin instalado" in result.output


def test_installed_plugin_is_visible_to_list_plugins(tmp_path: Path) -> None:
    """`list-plugins` (built-in + workspace) também enxerga o plugin instalado."""
    source = _write_plugin(tmp_path)
    ws_root = tmp_path / "ws"
    runner.invoke(app, ["plugin", "install", str(source), "--workspace", str(ws_root)])

    result = runner.invoke(app, ["list-plugins", "--workspace", str(ws_root)])

    assert result.exit_code == 0
    assert "external-demo" in result.output


# --- casos negativos --------------------------------------------------------
def test_invalid_manifest_missing_required_field_writes_nothing(tmp_path: Path) -> None:
    source = _write_plugin(tmp_path, omit_field="version")
    ws_root = tmp_path / "ws"

    result = runner.invoke(app, ["plugin", "install", str(source), "--workspace", str(ws_root)])

    assert result.exit_code != 0
    assert "erro:" in result.output
    # nada escrito no workspace
    assert not (ws_root / "plugins" / "external-demo").exists()


def test_entry_class_wrong_base_is_rejected(tmp_path: Path) -> None:
    """`entry` resolve mas a classe não é subclasse da base do kind declarado."""
    source = _write_plugin(
        tmp_path, src="class ExternalPlugin:\n    pass\n"
    )
    ws_root = tmp_path / "ws"

    result = runner.invoke(app, ["plugin", "install", str(source), "--workspace", str(ws_root)])

    assert result.exit_code != 0
    assert not (ws_root / "plugins" / "external-demo").exists()


def test_missing_entry_module_is_rejected(tmp_path: Path) -> None:
    source = _write_plugin(tmp_path, src=None)  # sem plugin.py
    ws_root = tmp_path / "ws"

    result = runner.invoke(app, ["plugin", "install", str(source), "--workspace", str(ws_root)])

    assert result.exit_code != 0
    assert not (ws_root / "plugins" / "external-demo").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [("api_version", "99.0"), ("schema", ">=99.0,<100.0"), ("kind", "naoexiste")],
)
def test_incompatible_manifest_fields_are_rejected(tmp_path: Path, field: str, value: str) -> None:
    source = _write_plugin(tmp_path, **{field: value})  # type: ignore[arg-type]
    ws_root = tmp_path / "ws"

    result = runner.invoke(app, ["plugin", "install", str(source), "--workspace", str(ws_root)])

    assert result.exit_code != 0
    assert not (ws_root / "plugins" / "external-demo").exists()


def test_name_collision_refused_without_force_then_accepted_with_force(tmp_path: Path) -> None:
    ws_root = tmp_path / "ws"
    first = _write_plugin(tmp_path / "v1", version="1.0.0")
    assert (
        runner.invoke(app, ["plugin", "install", str(first), "--workspace", str(ws_root)]).exit_code
        == 0
    )

    installed_toml = ws_root / "plugins" / "external-demo" / "plugin.toml"
    second = _write_plugin(tmp_path / "v2", version="2.0.0")

    # sem --force: recusa e mantém o original intacto
    refused = runner.invoke(app, ["plugin", "install", str(second), "--workspace", str(ws_root)])
    assert refused.exit_code != 0
    assert "--force" in refused.output
    assert '"1.0.0"' in installed_toml.read_text(encoding="utf-8")

    # com --force: substitui
    forced = runner.invoke(
        app, ["plugin", "install", str(second), "--workspace", str(ws_root), "--force"]
    )
    assert forced.exit_code == 0
    assert '"2.0.0"' in installed_toml.read_text(encoding="utf-8")


def test_nonexistent_source_falls_through_to_git_clone_and_fails(tmp_path: Path) -> None:
    """Origem que não é path existente vira tentativa de `git clone`.

    Usa um caminho local inexistente (não uma URL remota) de propósito: o clone
    falha na hora, sem depender de rede/DNS — o que importa aqui é que a falha é
    reportada com exit code != 0 e nada é escrito no workspace.
    """
    ws_root = tmp_path / "ws"
    result = runner.invoke(
        app, ["plugin", "install", str(tmp_path / "nao-existe"), "--workspace", str(ws_root)]
    )
    assert result.exit_code != 0
    assert "erro:" in result.output
    assert not (ws_root / "plugins").exists()


# --- remove -----------------------------------------------------------------
def test_remove_deletes_installed_plugin(tmp_path: Path) -> None:
    source = _write_plugin(tmp_path)
    ws_root = tmp_path / "ws"
    runner.invoke(app, ["plugin", "install", str(source), "--workspace", str(ws_root)])
    installed_dir = ws_root / "plugins" / "external-demo"
    assert installed_dir.exists()

    result = runner.invoke(
        app, ["plugin", "remove", "external-demo", "--workspace", str(ws_root), "--yes"]
    )

    assert result.exit_code == 0
    assert not installed_dir.exists()


def test_remove_unknown_plugin_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["plugin", "remove", "nao-instalado", "--workspace", str(tmp_path), "--yes"]
    )
    assert result.exit_code != 0
