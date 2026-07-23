"""Plugin `speed` (kind=metadata) — porte fino de MetadataModule/speedModule.py.

Adapter fino: preserva VERBATIM o comportamento numérico do legado, incluindo o
bug #2 do ARCHITECTURE.md (dupla divisão por ratio). NÃO corrigir aqui — a
correção é tarefa explícita da Fase 3.
"""

from __future__ import annotations

import math

from src.core.schema.result import AnalysisContext, Metric
from src.core.stages import MetadataPlugin


class SpeedPlugin(MetadataPlugin):
    def run(self, ctx: AnalysisContext) -> None:
        result = ctx.result
        route = next((r for r in result.routes if r.entity_id == 0), None)
        if route is None or not route.points:
            raise ValueError("SpeedPlugin: nenhuma rota encontrada para entity_id=0")

        # `pixel_to_cm_ratio` escalar do legado -> Calibration.px_per_cm é por eixo
        # (Point3D) no schema novo (bug #3, só corrigido via axis_mapping() na Fase
        # 3). Aqui usamos a média dos 3 componentes como aproximação equivalente ao
        # escalar antigo — decisão explícita para manter o adapter fino executável.
        px_per_cm = result.calibration.px_per_cm
        ratio = (px_per_cm.x + px_per_cm.y + px_per_cm.z) / 3

        # "Primeiro ponto disponível" é o análogo correto de "frame 0" no schema
        # novo: Route3D.points pode ter buracos (oclusão), diferente do dict antigo
        # sempre contíguo com sentinela (-1,-1,-1).
        ordered = sorted(route.points.items())  # [(frame_index, Point3D), ...]
        previous = None
        speed_by_frame: dict[str, float] = {}
        distance_total = 0.0
        speed_total = 0.0

        for _frame_index, point in ordered:
            if previous is None:
                previous = point
                continue
            distance = (
                math.dist(
                    (previous.x, previous.y, previous.z),
                    (point.x, point.y, point.z),
                )
                * ratio
                / 100
            )
            # BUG #2 PRESERVADO DELIBERADAMENTE: divide por ratio de novo (o legado
            # fazia `speed = distance/pixel_to_cm_ratio`). NÃO corrigir nesta fase.
            speed = distance / ratio
            speed_by_frame[str(_frame_index)] = speed
            distance_total += distance
            speed_total += speed
            previous = point

        average_speed = speed_total / len(route.points) if route.points else 0.0

        ctx.add_metric(Metric(name="speed", value=speed_by_frame, unit=None, producer="speed"))
        ctx.add_metric(
            Metric(name="average_speed", value=average_speed, unit=None, producer="speed")
        )
        ctx.add_metric(
            Metric(name="distance_total", value=distance_total, unit="cm", producer="speed")
        )
