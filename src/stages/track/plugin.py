"""Track — atribuição de identidade temporal trivial (Fase 3).

`SingleEntityTracker` porta o comportamento IMPLÍCITO do sistema legado: como
`remove_background` só devolvia no máximo 1 posição por frame (maior contorno) e
`route_module` tratava as posições posicionalmente por índice, sem noção de
identidade. Aqui isso vira explícito: uma única entidade (`entity_id=0`), um ponto
por frame, buracos onde não houve detecção (oclusão) — sem sentinela `(-1,-1)`.

A interface `Tracker` (`stages.py`, Fase 2) já fala em N detecções e `entity_id`
persistente, então um tracker multi-animal (Kalman+Hungarian) futuro é drop-in
sem mudar schema/interface — não é desenhado agora (Fase 6).

Um `SingleEntityTracker` é instanciado por view (`top`, `side`) pelo orquestrador.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from src.core.schema.detection import FrameDetections
from src.core.schema.geometry import Point2D
from src.core.schema.track import Track
from src.core.stages import Tracker


class SingleEntityTracker(Tracker):
    ENTITY_ID: ClassVar[int] = 0

    def __init__(self, view: Literal["top", "side"]) -> None:
        self._view: Literal["top", "side"] = view
        self._points: dict[int, Point2D] = {}

    def update(self, dets: FrameDetections) -> None:
        if not dets.detections:
            return  # buraco no dict = oclusão/não-detecção
        # se por acaso vier >1 detecção (não deveria — o Detect já filtra pelo maior
        # contorno), pega a de maior área. Convenção trivial, não tracking real.
        best = max(dets.detections, key=lambda d: d.area or 0.0)
        self._points[dets.frame_index] = best.centroid

    def tracks(self) -> list[Track]:
        return [Track(entity_id=self.ENTITY_ID, view=self._view, points=dict(self._points))]

    def reset(self) -> None:
        self._points.clear()
