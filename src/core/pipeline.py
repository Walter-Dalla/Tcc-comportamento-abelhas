"""Orquestração: RunRequest -> RunResult (Fase 2).

Escopo desta fase: só o estágio `metadata` sobre um `AnalysisResult` já
persistido (carregado via `ResultStore`), reproduzindo o papel do antigo
`execute_metadata_module_calls` — mas com manifest, ordenação e isolamento de
erro. Capture/Rectify/Detect/Track/Fuse chegam na Fase 3 — não há stubs mortos
aqui, só este comentário como marcador de escopo.

Ver `docs/plans/fase2-detalhado.md` seções 1.5 e 3.
"""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from src.core.errors import PluginOrderingCycleError
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.schema.result import AnalysisContext, AnalysisResult
from src.core.stages import MetadataPlugin
from src.core.store import ResultStore
from src.core.workspace import Workspace

logger = logging.getLogger("animaltrack.pipeline")


class RunRequest(BaseModel):
    profile: str
    workspace: str  # path serializável (Workspace.root)
    plugin_selection: dict[PluginKind, list[str]] = Field(default_factory=dict)
    gpu: bool = False
    overrides: dict[str, Any] = Field(default_factory=dict)


class PluginFailure(BaseModel):
    kind: PluginKind
    name: str
    stage: Literal["setup", "run", "teardown"]
    error_type: str
    message: str
    traceback: str | None = None


class RunResult(BaseModel):
    profile: str
    success: bool
    result: AnalysisResult | None = None
    plugin_failures: list[PluginFailure] = Field(default_factory=list)
    duration_seconds: float | None = None


@dataclass
class PipelineContext:
    """Estado vivo de orquestração — objetos não-serializáveis (registry,
    workspace). Deliberadamente NÃO é pydantic: RunRequest/RunResult cruzam
    fronteiras de serialização (CLI, futura API); PipelineContext só existe em
    memória durante `Pipeline.run()`."""

    request: RunRequest
    registry: PluginRegistry
    workspace: Workspace


def _record_failure(
    failures: list[PluginFailure],
    kind: PluginKind,
    name: str,
    stage: Literal["setup", "run", "teardown"],
    exc: BaseException,
) -> None:
    logger.error(
        "plugin %s:%s falhou no estágio %s: %s", kind.value, name, stage, exc, exc_info=True
    )
    failures.append(
        PluginFailure(
            kind=kind,
            name=name,
            stage=stage,
            error_type=type(exc).__name__,
            message=str(exc),
            traceback=traceback.format_exc()[-4000:],
        )
    )


class Pipeline:
    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    def run(self, request: RunRequest) -> RunResult:
        start = time.monotonic()
        workspace = Workspace(root=Path(request.workspace))
        store = ResultStore(workspace)
        result = store.load(request.profile)

        ctx = AnalysisContext(result=result)
        pctx = PipelineContext(request=request, registry=self._registry, workspace=workspace)

        failures: list[PluginFailure] = []
        requested_metadata = set(request.plugin_selection.get(PluginKind.METADATA, []))

        # Ciclo de ordenação é erro de configuração — NÃO isolado por plugin,
        # propaga para fora do run inteiro (fatal).
        try:
            ordered_metadata = self._registry.for_kind(PluginKind.METADATA)
        except PluginOrderingCycleError:
            raise

        for plugin in ordered_metadata:
            if requested_metadata and plugin.manifest.name not in requested_metadata:
                continue
            # `for_kind(METADATA)` só devolve subclasses de MetadataPlugin
            # (garantido pelo registry via _KIND_BASE_CLASS).
            self._execute_metadata_plugin(cast(MetadataPlugin, plugin), pctx, ctx, failures)

        store.save(ctx.result)

        return RunResult(
            profile=request.profile,
            # Falhas de plugin isoladas NÃO derrubam o run — só um erro fatal
            # (perfil ausente, ciclo) impede chegar até aqui. Ver plano seção 3.
            success=True,
            result=ctx.result,
            plugin_failures=failures,
            duration_seconds=time.monotonic() - start,
        )

    @staticmethod
    def _execute_metadata_plugin(
        plugin: MetadataPlugin,
        pctx: PipelineContext,
        ctx: AnalysisContext,
        failures: list[PluginFailure],
    ) -> None:
        """Roda setup -> run -> teardown de um plugin com isolamento de erro.

        Se `setup` falha, `run`/`teardown` NÃO rodam. Se `setup` teve sucesso,
        `teardown` roda SEMPRE (try/finally), mesmo que `run` falhe — corrige o
        gap do plano onde um `break` puro pularia o teardown de um plugin com
        estado/recurso. Cada estágio que falha vira um `PluginFailure` isolado; o
        laço externo continua para o próximo plugin.
        """
        kind = plugin.manifest.kind
        name = plugin.manifest.name

        try:
            plugin.setup(pctx)
        except Exception as exc:
            _record_failure(failures, kind, name, "setup", exc)
            return  # setup falhou -> não roda run/teardown

        try:
            plugin.run(ctx)
        except Exception as exc:
            _record_failure(failures, kind, name, "run", exc)
        finally:
            try:
                plugin.teardown()
            except Exception as exc:
                _record_failure(failures, kind, name, "teardown", exc)
