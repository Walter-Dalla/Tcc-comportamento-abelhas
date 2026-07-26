"""CLI headless (Fase 4, workstream A) — Typer.

Regra dura: NADA aqui importa `tkinter` nem `src.app.gui`, direta ou
transitivamente (verificado por teste em subprocesso limpo, `tests/test_cli_e2e.py`).
Todos os comandos convergem para o mesmo runner que a GUI usa
(`src/app/runner.py` → `run_cpu_analysis`), garantindo caminho idêntico.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from src.app.orientation_util import validate_orientation
from src.app.plugin_install import (
    PluginInstallError,
    install_plugin,
    list_installed,
    remove_plugin,
)
from src.app.plugins import default_search_paths
from src.app.runner import GpuRequiredError, execute_analysis, run_exporter
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.store import ProfileStore, StoreError
from src.core.workspace import Workspace

logger = logging.getLogger("animaltrack.cli")

app = typer.Typer(name="animaltrack", no_args_is_help=True, add_completion=False)

# Grupo `animaltrack plugin ...` (Fase 6, workstream C).
plugin_app = typer.Typer(
    name="plugin", no_args_is_help=True, add_completion=False, help="Gerencia plugins instalados."
)
app.add_typer(plugin_app)

# Exporters rodados por padrão pelo comando `run` (mesma dupla da GUI legada).
_DEFAULT_EXPORTERS = ("route-plot", "pdf-report")


@app.command()
def run(
    profile: str = typer.Option(..., "--profile", help="Nome do perfil de análise"),
    workspace: Path | None = typer.Option(
        None, "--workspace", help="Raiz do workspace (default: $ANIMALTRACK_WORKSPACE ou ~/.animaltrack)"
    ),
    config: Path | None = typer.Option(
        None, "--config", help="Caminho alternativo de pipeline.toml (reservado; não usado nesta fase)"
    ),
    gpu: bool = typer.Option(
        False, "--gpu", help="Força backend GPU; falha alto se indisponível (GPU é requisito, não fallback)"
    ),
    debug_frames: bool = typer.Option(
        False,
        "--debug-frames",
        help="Grava frames de debug do Detect em <workspace>/debug/<perfil>/ (inspeção pós-hoc)",
    ),
) -> None:
    """Roda a pipeline CPU completa sobre um perfil e exporta JSON + gráfico + PDF."""
    ws = Workspace.resolve(workspace)
    try:
        result = execute_analysis(ws, profile, require_gpu=gpu, debug_frames=debug_frames)
    except GpuRequiredError as exc:
        typer.echo(f"erro: {exc}", err=True)
        logger.error("GPU exigida e ausente", exc_info=True)
        raise typer.Exit(code=2) from exc
    except Exception as exc:  # CLI nunca vaza traceback cru ao usuário final
        typer.echo(f"erro ao processar '{profile}': {exc}", err=True)
        logger.error("falha no run de %s", profile, exc_info=True)
        raise typer.Exit(code=1) from exc

    for exporter_name in _DEFAULT_EXPORTERS:
        try:
            out = run_exporter(ws, result, exporter_name)
            typer.echo(f"exportado ({exporter_name}): {out}")
        except Exception as exc:  # export opcional, não derruba o run inteiro
            typer.echo(f"aviso: exporter '{exporter_name}' falhou: {exc}", err=True)
            logger.warning("exporter %s falhou", exporter_name, exc_info=True)

    if debug_frames:
        typer.echo(f"frames de debug em: {ws.debug_dir(profile)}")
    typer.echo(f"OK: resultado salvo em {ws.result_file(profile)}")


@app.command("list-plugins")
def list_plugins(
    workspace: Path | None = typer.Option(None, "--workspace", help="Raiz do workspace"),
    kind: str | None = typer.Option(
        None, "--kind", help="Filtra por tipo: capture|rectify|detector|tracker|fusion|metadata|exporter"
    ),
) -> None:
    """Lista os plugins descobertos (built-in + workspace), opcionalmente por tipo."""
    ws = Workspace.resolve(workspace)
    registry = PluginRegistry()
    registry.discover(default_search_paths(ws))
    try:
        kind_filter = PluginKind(kind) if kind else None
    except ValueError as exc:
        typer.echo(f"erro: tipo de plugin inválido '{kind}'", err=True)
        raise typer.Exit(code=1) from exc
    for manifest in registry.manifests(kind_filter):
        typer.echo(f"{manifest.kind.value:10s} {manifest.name:30s} v{manifest.version}")


@app.command("validate-config")
def validate_config(
    workspace: Path | None = typer.Option(None, "--workspace"),
    profile: str | None = typer.Option(
        None, "--profile", help="Se omitido, valida todos os perfis do workspace"
    ),
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Valida o(s) perfil(is) contra o schema pydantic + regras de orientação,
    sem executar o pipeline."""
    ws = Workspace.resolve(workspace)
    store = ProfileStore(ws)
    names = [profile] if profile else store.list()
    if not names:
        typer.echo("nenhum perfil encontrado no workspace", err=True)
        raise typer.Exit(code=1)

    exit_code = 0
    for name in names:
        errors = _validate_profile(store, name)
        if errors:
            exit_code = 1
            for error in errors:
                typer.echo(f"[{name}] {error}", err=True)
        else:
            typer.echo(f"[{name}] OK")
    raise typer.Exit(code=exit_code)


def _validate_profile(store: ProfileStore, name: str) -> list[str]:
    """Carrega e valida um perfil; retorna mensagens de erro (vazio = válido)."""
    try:
        profile = store.get(name)
    except StoreError as exc:
        return [str(exc)]
    return validate_orientation(profile.orientation)


# --- grupo `plugin` (Fase 6, workstream C) ----------------------------------
@plugin_app.command("install")
def plugin_install(
    source: str = typer.Argument(
        ..., help="Caminho local do plugin OU URL git literal (não há índice/backend)"
    ),
    workspace: Path | None = typer.Option(None, "--workspace", help="Raiz do workspace"),
    force: bool = typer.Option(
        False, "--force", help="Sobrescreve um plugin já instalado com o mesmo nome"
    ),
) -> None:
    """Instala um plugin em `<workspace>/plugins/<nome>/`, validando o manifest antes.

    Curadoria é manual (estilo git-tap): não existe servidor de marketplace que
    resolva nome → pacote. Ver `docs/PLUGIN_CONTRACT.md`.
    """
    ws = Workspace.resolve(workspace)
    try:
        installed = install_plugin(source, ws, force=force)
    except PluginInstallError as exc:
        # imprime TODAS as falhas encontradas, não só a primeira (saída scriptável)
        for error in exc.errors:
            typer.echo(f"erro: {error}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"instalado: {installed.name} v{installed.version} ({installed.kind.value})")
    typer.echo(f"destino: {installed.path}")


@plugin_app.command("list")
def plugin_list(
    workspace: Path | None = typer.Option(None, "--workspace", help="Raiz do workspace"),
) -> None:
    """Lista os plugins instalados no workspace (não os built-in do repo)."""
    ws = Workspace.resolve(workspace)
    manifests = list_installed(ws)
    if not manifests:
        typer.echo(f"nenhum plugin instalado em {ws.plugins}")
        return
    for manifest in manifests:
        typer.echo(f"{manifest.kind.value:10s} {manifest.name:30s} v{manifest.version}")


@plugin_app.command("remove")
def plugin_remove(
    name: str = typer.Argument(..., help="Nome do plugin (campo [plugin].name do manifest)"),
    workspace: Path | None = typer.Option(None, "--workspace", help="Raiz do workspace"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Não pedir confirmação"),
) -> None:
    """Remove `<workspace>/plugins/<nome>/`."""
    ws = Workspace.resolve(workspace)
    if not yes:
        typer.confirm(f"remover o plugin '{name}' de {ws.plugins}?", abort=True)
    try:
        removed = remove_plugin(name, ws)
    except PluginInstallError as exc:
        for error in exc.errors:
            typer.echo(f"erro: {error}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"removido: {removed}")
