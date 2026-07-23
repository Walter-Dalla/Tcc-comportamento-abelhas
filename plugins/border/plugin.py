"""Plugin `border` (kind=metadata) — porte fino de MetadataModule/borderModule.py.

Adapter fino: consome `BorderRegion.bounds` (min/max já resolvidos por eixo 3D) e
faz só a contagem de containment por eixo. A antiga derivação de min/max a partir
de pontos de pixel — e a mistura de eixos de borderModule.py — NÃO vive mais aqui:
pertence a quem popula `bounds` (a fixture de teste na Fase 2; `axis_mapping()` na
Fase 3).

`ordering.after = ["speed"]` no plugin.toml é o exemplo canônico do teste de
ordenação topológica.
"""

from __future__ import annotations

from src.core.schema.result import AnalysisContext, Metric
from src.core.stages import MetadataPlugin


class BorderPlugin(MetadataPlugin):
    def run(self, ctx: AnalysisContext) -> None:
        result = ctx.result
        if result.border_region is None:
            raise ValueError("BorderPlugin: border_region ausente em AnalysisResult")
        route = next((r for r in result.routes if r.entity_id == 0), None)
        if route is None:
            raise ValueError("BorderPlugin: nenhuma rota encontrada para entity_id=0")

        bounds = result.border_region.bounds
        min_x, max_x = bounds["x"]
        min_y, max_y = bounds["y"]
        min_z, max_z = bounds["z"]

        time_x = time_y = time_z = 0
        for point in route.points.values():
            if min_x <= point.x <= max_x:
                time_x += 1
            if min_y <= point.y <= max_y:
                time_y += 1
            if min_z <= point.z <= max_z:
                time_z += 1

        ctx.add_metric(Metric(name="time_border_x", value=time_x, unit="frames", producer="border"))
        ctx.add_metric(Metric(name="time_border_y", value=time_y, unit="frames", producer="border"))
        ctx.add_metric(Metric(name="time_border_z", value=time_z, unit="frames", producer="border"))
