"""Runner compartilhado (Fase 4) — o ponto único onde CLI e GUI se encontram.

Tk-free por construção: importável no caminho headless sem trazer tkinter. Monta
e roda a pipeline CPU completa via `src.stages.orchestration.run_cpu_analysis`
(Fase 3) e persiste o `AnalysisResult` via `ResultStore` — exatamente o mesmo
caminho para os dois pontos de entrada, sem lógica de execução duplicada.

Reconciliação com o plano: `docs/plans/fase4-detalhado.md` escreve `Pipeline.run`
como se ele rodasse a análise inteira, mas o `Pipeline.run` real (Fase 2) só roda
o estágio `metadata` sobre um `AnalysisResult` já persistido. A orquestração
completa (Capture→Fuse + metadata) mora em `run_cpu_analysis(profile)`. Este
runner é a "camada de serviço" que o plano previa — CLI e `AppService` ambos
delegam a ele.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.app.plugins import default_search_paths
from src.core.gpu import probe_cuda_devices
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.schema.result import AnalysisContext, AnalysisResult
from src.core.store import ProfileStore, ResultStore
from src.core.workspace import Workspace
from src.stages.orchestration import run_cpu_analysis


class GpuRequiredError(RuntimeError):
    """`--gpu` pedido mas nenhum device CUDA disponível (GPU é requisito, não fallback)."""


class ExporterNotFoundError(RuntimeError):
    """Nome de exporter pedido não foi descoberto entre os plugins `exporter`."""


def _registry_for(workspace: Workspace) -> PluginRegistry:
    registry = PluginRegistry()
    registry.discover(default_search_paths(workspace))
    return registry


def execute_analysis(
    workspace: Workspace,
    profile_name: str,
    *,
    require_gpu: bool = False,
) -> AnalysisResult:
    """Roda a pipeline CPU completa para um perfil e persiste o resultado.

    Levanta `GpuRequiredError` se `require_gpu` e não houver device CUDA;
    `ProfileNotFoundError` se o perfil não existir; `ValueError` se o perfil não
    tiver `orientation` (pré-requisito de dado da Fase 3)."""
    if require_gpu and not probe_cuda_devices().available:
        raise GpuRequiredError(
            "backend GPU exigido (--gpu) mas nenhum device CUDA foi detectado"
        )
    profile = ProfileStore(workspace).get(profile_name)
    result = run_cpu_analysis(profile)
    ResultStore(workspace).save(result)
    return result


def run_exporter(
    workspace: Workspace,
    result: AnalysisResult,
    exporter_name: str,
    **kwargs: object,
) -> Path:
    """Instancia o plugin `exporter` nomeado e roda seu `export(ctx, workspace)`."""
    registry = _registry_for(workspace)
    names = {m.name for m in registry.manifests(PluginKind.EXPORTER)}
    if exporter_name not in names:
        raise ExporterNotFoundError(
            f"exporter '{exporter_name}' não encontrado (disponíveis: {sorted(names)})"
        )
    plugin = registry.get(PluginKind.EXPORTER, exporter_name)
    ctx = AnalysisContext(result=result)
    export_fn: Callable[..., Path] = plugin.export  # type: ignore[attr-defined]
    return export_fn(ctx, workspace, **kwargs)
