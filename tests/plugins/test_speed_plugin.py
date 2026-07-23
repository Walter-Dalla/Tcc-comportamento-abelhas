"""Teste de regressão do plugin `speed` (reescrito na Fase 3, plano seção 4.4).

Fixa o comportamento numérico CORRIGIDO: bug #2 (dupla divisão por ratio) eliminado
— a rota já chega em cm, então velocidade = distância_cm / (1/fps), sem nenhuma
divisão por ratio — e bug #6 (média divide por n-1 amostras, não n frames).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from src.core.plugin import Plugin
from src.core.schema.geometry import Point3D
from src.core.schema.result import AnalysisContext, AnalysisResult


def test_speed_formula_corrected(
    load_plugin: Callable[..., Plugin],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    # rota JÁ em cm; make_calibration usa fps=30 -> dt = 1/30, velocidade = dist_cm * 30
    points = {
        0: Point3D(x=0.0, y=0.0, z=0.0),
        1: Point3D(x=3.0, y=4.0, z=0.0),  # dist p0->p1 = 5.0 cm
        2: Point3D(x=3.0, y=4.0, z=12.0),  # dist p1->p2 = 12.0 cm
    }
    result = result_factory(points=points)
    ctx = AnalysisContext(result=result)

    plugin = load_plugin("speed")
    plugin.run(ctx)  # type: ignore[attr-defined]

    metrics = ctx.result.metrics
    # s1 = 5.0 / (1/30) = 150.0 cm/s ; s2 = 12.0 / (1/30) = 360.0 cm/s
    assert metrics["speed"].value == {
        "1": pytest.approx(150.0),
        "2": pytest.approx(360.0),
    }
    assert metrics["speed"].unit == "cm/s"
    assert metrics["distance_total"].value == pytest.approx(17.0)  # 5.0 + 12.0
    assert metrics["distance_total"].unit == "cm"
    # bug #6 corrigido: média divide por 2 amostras (n-1), não por len(points)=3
    assert metrics["average_speed"].value == pytest.approx(255.0)  # (150 + 360) / 2
    assert metrics["average_speed"].unit == "cm/s"
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
