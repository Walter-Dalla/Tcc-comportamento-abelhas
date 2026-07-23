"""Integração real ponta-a-ponta do estágio metadata (Fase 2, plano seção 5).

Descobre os plugins REAIS (`plugins/speed`, `plugins/border`), roda o Pipeline
sobre um AnalysisResult persistido e verifica que todas as métricas de ambos
aparecem, na ordem topológica correta (border after speed).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.core.pipeline import Pipeline, RunRequest
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.schema.geometry import Point3D
from src.core.schema.result import AnalysisResult, BorderRegion
from src.core.store import ResultStore
from src.core.workspace import Workspace


def test_metadata_pipeline_e2e(
    plugins_dir: Path,
    saved_workspace: Callable[[AnalysisResult], Workspace],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    points = {
        0: Point3D(x=1.0, y=1.0, z=1.0),
        1: Point3D(x=3.0, y=4.0, z=1.0),
        2: Point3D(x=3.0, y=4.0, z=12.0),
    }
    result = result_factory(
        profile="e2e",
        points=points,
        border_region=BorderRegion(
            bounds={"x": (0.0, 10.0), "y": (0.0, 10.0), "z": (0.0, 10.0)}
        ),
    )
    ws = saved_workspace(result)

    registry = PluginRegistry()
    registry.discover([plugins_dir])

    request = RunRequest(
        profile="e2e",
        workspace=str(ws.root),
        plugin_selection={PluginKind.METADATA: ["speed", "border"]},
    )
    run_result = Pipeline(registry).run(request)

    assert run_result.success is True
    assert run_result.plugin_failures == []
    assert run_result.result is not None

    metrics = run_result.result.metrics
    for key in (
        "speed",
        "average_speed",
        "distance_total",
        "time_border_x",
        "time_border_y",
        "time_border_z",
    ):
        assert key in metrics, f"métrica ausente: {key}"

    # ordem topológica: border declara after=[speed]
    ordered = [p.manifest.name for p in registry.for_kind(PluginKind.METADATA)]
    assert ordered == ["speed", "border"]

    # métricas persistidas em disco
    reloaded = ResultStore(ws).load("e2e")
    assert "distance_total" in reloaded.metrics
    assert "time_border_z" in reloaded.metrics


def test_metadata_pipeline_runs_all_when_no_selection(
    plugins_dir: Path,
    saved_workspace: Callable[[AnalysisResult], Workspace],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    """plugin_selection vazio para o kind = roda todos os descobertos."""
    result = result_factory(
        profile="e2e_all",
        border_region=BorderRegion(
            bounds={"x": (-1000.0, 1000.0), "y": (-1000.0, 1000.0), "z": (-1000.0, 1000.0)}
        ),
    )
    ws = saved_workspace(result)

    registry = PluginRegistry()
    registry.discover([plugins_dir])

    request = RunRequest(profile="e2e_all", workspace=str(ws.root))
    run_result = Pipeline(registry).run(request)

    assert run_result.plugin_failures == []
    assert run_result.result is not None
    assert "speed" in run_result.result.metrics
    assert "time_border_x" in run_result.result.metrics
