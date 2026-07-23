"""Plugin `speed` (kind=metadata) — reescrito na Fase 3 (corrige bugs #2 e #6).

Diferente do adapter fino da Fase 2 (que preservava os bugs de propósito): agora a
`Route3D` já chega em CENTÍMETROS (a conversão px→cm acontece uma única vez no
estágio Fuse, via `axis_mapping()`/`px_per_cm` por eixo). Então este plugin só faz
geometria pura em cm — nenhuma divisão por `pixel_to_cm_ratio` aparece aqui, o que
mata o bug #2 na raiz (o legado fazia `distance = dist * ratio/100` seguido de
`speed = distance/ratio`, cancelando o ratio algebricamente e deixando a velocidade
numa unidade sem sentido físico).

Fórmulas corrigidas (ARCHITECTURE.md, bugs #2/#6; plano seção 4.4):
- velocidade = distância_cm / (1/fps)  == distância_cm * fps  [cm/s]
- average_speed = soma das velocidades / número de AMOSTRAS de velocidade
  (pares consecutivos válidos = frame_count - 1), não / número de frames.
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

        fps = result.calibration.fps
        dt = 1.0 / fps  # intervalo entre frames consecutivos

        indices = sorted(route.points)
        speed_by_frame: dict[str, float] = {}
        distance_total = 0.0
        speed_total = 0.0
        sample_count = 0

        for prev_idx, idx in zip(indices, indices[1:], strict=False):
            p1 = route.points[prev_idx]
            p2 = route.points[idx]
            distance_cm = math.dist((p1.x, p1.y, p1.z), (p2.x, p2.y, p2.z))  # já em cm
            speed_cm_s = distance_cm / dt  # == distance_cm * fps
            speed_by_frame[str(idx)] = speed_cm_s
            distance_total += distance_cm
            speed_total += speed_cm_s
            sample_count += 1

        # bug #6 corrigido: divide pelo número de amostras de velocidade (n-1), não n.
        average_speed = speed_total / sample_count if sample_count else 0.0

        ctx.add_metric(
            Metric(name="speed", value=speed_by_frame, unit="cm/s", producer="speed")
        )
        ctx.add_metric(
            Metric(name="average_speed", value=average_speed, unit="cm/s", producer="speed")
        )
        ctx.add_metric(
            Metric(name="distance_total", value=distance_total, unit="cm", producer="speed")
        )
