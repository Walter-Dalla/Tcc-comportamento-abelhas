"""Isolamento de erro de plugin no Pipeline (Fase 2, plano seções 3 e 5)."""

from __future__ import annotations

from collections.abc import Callable

from src.core.pipeline import Pipeline, RunRequest
from src.core.plugin import PluginKind, PluginManifest
from src.core.plugin_registry import PluginRegistry
from src.core.schema.result import AnalysisContext, AnalysisResult, Metric
from src.core.stages import MetadataPlugin
from src.core.workspace import Workspace


def _manifest(name: str, cls_name: str) -> PluginManifest:
    return PluginManifest(
        name=name,
        version="1.0.0",
        kind=PluginKind.METADATA,
        entry=f"plugin:{cls_name}",
        api_version="1.0",
        schema=">=1.0,<2.0",
    )


class GoodPlugin(MetadataPlugin):
    manifest = _manifest("good", "GoodPlugin")

    def run(self, ctx: AnalysisContext) -> None:
        ctx.add_metric(Metric(name="good_metric", value=1, producer="good"))


class BadPlugin(MetadataPlugin):
    manifest = _manifest("bad", "BadPlugin")

    def run(self, ctx: AnalysisContext) -> None:
        raise RuntimeError("boom")


def test_failing_plugin_isolated(
    saved_workspace: Callable[[AnalysisResult], Workspace],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    ws = saved_workspace(result_factory(profile="iso"))

    registry = PluginRegistry()
    registry.register_instance(GoodPlugin())
    registry.register_instance(BadPlugin())

    request = RunRequest(
        profile="iso",
        workspace=str(ws.root),
        plugin_selection={PluginKind.METADATA: ["good", "bad"]},
    )
    run_result = Pipeline(registry).run(request)

    assert len(run_result.plugin_failures) == 1
    failure = run_result.plugin_failures[0]
    assert failure.name == "bad"
    assert failure.stage == "run"
    assert failure.error_type == "RuntimeError"

    # o plugin que funcionou produziu sua métrica -> não foi pulado pela falha do outro
    assert run_result.result is not None
    assert "good_metric" in run_result.result.metrics
    assert run_result.result.metrics["good_metric"].value == 1

    # falha isolada não derruba o run
    assert run_result.success is True


def test_result_persisted_after_isolated_failure(
    saved_workspace: Callable[[AnalysisResult], Workspace],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    from src.core.store import ResultStore

    ws = saved_workspace(result_factory(profile="iso2"))

    registry = PluginRegistry()
    registry.register_instance(GoodPlugin())
    registry.register_instance(BadPlugin())

    request = RunRequest(
        profile="iso2",
        workspace=str(ws.root),
        plugin_selection={PluginKind.METADATA: ["good", "bad"]},
    )
    Pipeline(registry).run(request)

    reloaded = ResultStore(ws).load("iso2")
    assert "good_metric" in reloaded.metrics
