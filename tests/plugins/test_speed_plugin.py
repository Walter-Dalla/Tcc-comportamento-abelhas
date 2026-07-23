"""Teste de regressão do plugin `speed` (Fase 2, plano seção 5).

Fixa o comportamento numérico ATUAL preservando o bug #2 (dupla divisão por
ratio) — serve de diff de comparação quando a Fase 3 corrigir a fórmula.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from src.core.plugin import Plugin
from src.core.schema.geometry import Point3D
from src.core.schema.result import AnalysisContext, AnalysisResult


def test_speed_regression_preserves_double_division(
    load_plugin: Callable[..., Plugin],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    # px_per_cm todos 5 -> ratio = (5+5+5)/3 = 5.0
    points = {
        0: Point3D(x=0.0, y=0.0, z=0.0),
        1: Point3D(x=3.0, y=4.0, z=0.0),  # dist p0->p1 = 5.0
        2: Point3D(x=3.0, y=4.0, z=12.0),  # dist p1->p2 = 12.0
    }
    result = result_factory(points=points)
    ctx = AnalysisContext(result=result)

    plugin = load_plugin("speed")
    plugin.run(ctx)  # type: ignore[attr-defined]

    metrics = ctx.result.metrics
    # distance = dist * ratio/100 ; speed = distance/ratio (bug: divide por ratio 2x)
    # d1 = 5*5/100 = 0.25 ; s1 = 0.25/5 = 0.05
    # d2 = 12*5/100 = 0.60 ; s2 = 0.60/5 = 0.12
    assert metrics["speed"].value == {
        "1": pytest.approx(0.05),
        "2": pytest.approx(0.12),
    }
    assert metrics["distance_total"].value == pytest.approx(0.85)  # 0.25 + 0.60
    assert metrics["distance_total"].unit == "cm"
    # average = (0.05 + 0.12) / len(points)=3  (bug #6 preservado: divide por N, não N-1)
    assert metrics["average_speed"].value == pytest.approx(0.17 / 3)
    assert metrics["speed"].producer == "speed"


def test_speed_missing_route_raises(
    load_plugin: Callable[..., Plugin],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    result = result_factory()
    result.routes = []  # nenhuma rota com entity_id=0
    ctx = AnalysisContext(result=result)
    plugin = load_plugin("speed")
    with pytest.raises(ValueError):
        plugin.run(ctx)  # type: ignore[attr-defined]
