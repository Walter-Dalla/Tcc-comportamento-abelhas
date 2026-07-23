"""Teste do plugin `border` (Fase 2, plano seção 5).

O plugin só conta containment por eixo contra `BorderRegion.bounds` já resolvido —
a derivação/mistura de eixos legada é upstream (fixture aqui / axis_mapping() na
Fase 3), não é responsabilidade do plugin.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from src.core.plugin import Plugin
from src.core.schema.geometry import Point3D
from src.core.schema.result import AnalysisContext, AnalysisResult, BorderRegion


def test_border_counts_containment_per_axis(
    load_plugin: Callable[..., Plugin],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    points = {
        0: Point3D(x=1.0, y=1.0, z=1.0),  # dentro em x, y, z
        1: Point3D(x=50.0, y=1.0, z=1.0),  # fora só em x
        2: Point3D(x=50.0, y=50.0, z=1.0),  # fora em x e y
    }
    border = BorderRegion(bounds={"x": (0.0, 10.0), "y": (0.0, 10.0), "z": (0.0, 10.0)})
    result = result_factory(points=points, border_region=border)
    ctx = AnalysisContext(result=result)

    plugin = load_plugin("border")
    plugin.run(ctx)  # type: ignore[attr-defined]

    metrics = ctx.result.metrics
    assert metrics["time_border_x"].value == 1  # só p0
    assert metrics["time_border_y"].value == 2  # p0, p1
    assert metrics["time_border_z"].value == 3  # p0, p1, p2
    assert metrics["time_border_x"].unit == "frames"
    assert metrics["time_border_z"].producer == "border"


def test_border_missing_region_raises(
    load_plugin: Callable[..., Plugin],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    result = result_factory(border_region=None)
    ctx = AnalysisContext(result=result)
    plugin = load_plugin("border")
    with pytest.raises(ValueError):
        plugin.run(ctx)  # type: ignore[attr-defined]
