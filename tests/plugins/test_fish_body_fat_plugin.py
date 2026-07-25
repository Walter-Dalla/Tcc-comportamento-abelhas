"""Testes do plugin de exemplo `fish-body-fat-estimator` (Fase 6, workstream B).

Cobre o plano seção 2.6: fórmula, clamp, ausência da métrica de entrada e
ausência da configuração obrigatória — os dois últimos devem falhar de forma
LOCALIZADA (log + métrica pulada), nunca derrubar o run.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from src.app.plugins import EXAMPLE_METADATA_PLUGINS_DIR
from src.core.pipeline import PipelineContext, RunRequest
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.schema.result import AnalysisContext, AnalysisResult, Metric
from src.core.stages import MetadataPlugin
from src.core.workspace import Workspace

PLUGIN_NAME = "fish-body-fat-estimator"


def _load() -> MetadataPlugin:
    registry = PluginRegistry()
    registry.discover([EXAMPLE_METADATA_PLUGINS_DIR])
    plugin = registry.get(PluginKind.METADATA, PLUGIN_NAME)
    assert isinstance(plugin, MetadataPlugin)
    return plugin


def _ctx(result: AnalysisResult, average_speed: float | None = 5.0) -> AnalysisContext:
    ctx = AnalysisContext(result=result)
    if average_speed is not None:
        ctx.add_metric(
            Metric(name="average_speed", value=average_speed, unit="cm/s", producer="speed")
        )
    return ctx


def _configure(plugin: MetadataPlugin, tmp_path: Path, length_cm: float | None) -> None:
    """Entrega `fish_length_cm` pelo caminho de produção: overrides do RunRequest."""
    overrides = {} if length_cm is None else {"fish_length_cm": length_cm}
    request = RunRequest(profile="p", workspace=str(tmp_path), overrides=overrides)
    plugin.setup(
        PipelineContext(
            request=request, registry=PluginRegistry(), workspace=Workspace(root=tmp_path)
        )
    )


# --- fórmula ---------------------------------------------------------------
def test_computes_expected_value(
    result_factory: Callable[..., AnalysisResult], tmp_path: Path
) -> None:
    result = result_factory()  # 3 frames com posição
    plugin = _load()
    _configure(plugin, tmp_path, 20.0)
    ctx = _ctx(result, average_speed=5.0)

    plugin.run(ctx)

    metric = ctx.get_metric("fish_body_fat_pct")
    assert metric is not None
    assert metric.unit == "%"
    assert metric.producer == PLUGIN_NAME

    # 25.0 - 0.8*5.0 + 0.15*duracao + 0.05*20.0, duracao = (3/30)/60 min
    duration_min = (3 / result.calibration.fps) / 60.0
    expected = 25.0 - 0.8 * 5.0 + 0.15 * duration_min + 0.05 * 20.0
    assert metric.value == pytest.approx(expected)


@pytest.mark.parametrize(
    ("average_speed", "length_cm"),
    [(1000.0, 10.0), (0.0, 5000.0)],  # força abaixo de 0 / acima de 100
)
def test_result_is_clamped_to_percentage_range(
    result_factory: Callable[..., AnalysisResult],
    tmp_path: Path,
    average_speed: float,
    length_cm: float,
) -> None:
    plugin = _load()
    _configure(plugin, tmp_path, length_cm)
    ctx = _ctx(result_factory(), average_speed=average_speed)

    plugin.run(ctx)

    value = ctx.get_metric("fish_body_fat_pct")
    assert value is not None
    assert 0.0 <= float(value.value) <= 100.0  # type: ignore[arg-type]


# --- falhas localizadas -----------------------------------------------------
def test_skips_without_average_speed(
    result_factory: Callable[..., AnalysisResult], tmp_path: Path
) -> None:
    plugin = _load()
    _configure(plugin, tmp_path, 20.0)
    ctx = _ctx(result_factory(), average_speed=None)

    plugin.run(ctx)  # não levanta

    assert ctx.get_metric("fish_body_fat_pct") is None


def test_skips_without_fish_length_config(
    result_factory: Callable[..., AnalysisResult],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANIMALTRACK_FISH_LENGTH_CM", raising=False)
    plugin = _load()
    _configure(plugin, tmp_path, None)
    ctx = _ctx(result_factory())

    plugin.run(ctx)  # não levanta — não inventa default para dado medido

    assert ctx.get_metric("fish_body_fat_pct") is None


def test_env_var_is_used_when_setup_did_not_run(
    result_factory: Callable[..., AnalysisResult], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caminho `run_cpu_analysis`, que roda metadata sem chamar `setup()`."""
    monkeypatch.setenv("ANIMALTRACK_FISH_LENGTH_CM", "18.0")
    ctx = _ctx(result_factory())

    _load().run(ctx)

    assert ctx.get_metric("fish_body_fat_pct") is not None


@pytest.mark.parametrize("bad", ["nao-numero", "-5", "0"])
def test_invalid_fish_length_is_rejected_not_defaulted(
    result_factory: Callable[..., AnalysisResult], monkeypatch: pytest.MonkeyPatch, bad: str
) -> None:
    monkeypatch.setenv("ANIMALTRACK_FISH_LENGTH_CM", bad)
    ctx = _ctx(result_factory())

    _load().run(ctx)

    assert ctx.get_metric("fish_body_fat_pct") is None


def test_skips_when_average_speed_is_not_numeric(
    result_factory: Callable[..., AnalysisResult], tmp_path: Path
) -> None:
    plugin = _load()
    _configure(plugin, tmp_path, 20.0)
    ctx = AnalysisContext(result=result_factory())
    # `speed` publica um dict por frame; se alguém ler a métrica errada, não quebra
    ctx.add_metric(Metric(name="average_speed", value={"0": 1.0}, producer="speed"))

    plugin.run(ctx)

    assert ctx.get_metric("fish_body_fat_pct") is None


# --- contrato/descoberta ----------------------------------------------------
def test_is_discoverable_and_ordered_after_speed() -> None:
    registry = PluginRegistry()
    registry.discover([EXAMPLE_METADATA_PLUGINS_DIR])
    manifests = {m.name: m for m in registry.manifests(PluginKind.METADATA)}
    assert PLUGIN_NAME in manifests
    assert manifests[PLUGIN_NAME].ordering.after == ["speed"]
