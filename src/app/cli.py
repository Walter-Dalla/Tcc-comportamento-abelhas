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
from src.app.plugins import default_search_paths
from src.app.runner import GpuRequiredError, execute_analysis, run_exporter
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.store import ProfileStore, StoreError
from src.core.workspace import Workspace

logger = logging.getLogger("animaltrack.cli")

app = typer.Typer(name="animaltrack", no_args_is_help=True, add_completion=False)

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
) -> None:
    """Roda a pipeline CPU completa sobre um perfil e exporta JSON + gráfico + PDF."""
    ws = Workspace.resolve(workspace)
    try:
        result = execute_analysis(ws, profile, require_gpu=gpu)
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
