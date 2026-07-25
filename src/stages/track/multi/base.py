"""Tracker multi-entidade parametrizável (Fase 6, workstream A).

Implementa o contrato abstrato `Tracker` (`update`/`tracks`/`reset`) de
`src/core/stages.py` EXATAMENTE como o `SingleEntityTracker` baseline — mesma
assinatura, mesmo `__init__(view)` construído por-view pelo orquestrador — mas
mantendo N entidades simultâneas com `entity_id` persistente.

Fluxo por frame (`update`):
  1. Prevê a posição de cada track ativo (Kalman).
  2. Monta matriz de custo track×detecção (distância euclidiana da PREDIÇÃO à
     detecção), com gating (`max_distance`).
  3. Associa via estratégia injetada (greedy ou hungarian).
  4. Casados: corrige o Kalman e grava o ponto observado.
  5. Detecções sem par: nascem tracks novos (novo `entity_id`).
  6. Tracks sem par: contam "miss". Continuam prevendo (segurando a posição) por
     até `max_age` frames — é isso que permite reassociar o MESMO id após uma
     oclusão curta.

`tracks()` devolve um `Track` por entidade que acumulou pelo menos `min_hits`
observações (filtra ids fantasmas de 1-2 frames, ruído), com buracos onde a
entidade esteve ocluída — oclusão representável nativamente no schema, sem
sentinela.

A diferença entre os dois candidatos do spike é SÓ a função de associação passada
no construtor — a máquina de tracking é a mesma. Ver `docs/plans/fase6-detalhado.md`
seção 1.4 e o handoff do workstream.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Literal

from src.core.schema.detection import FrameDetections
from src.core.schema.geometry import Point2D
from src.core.schema.track import Track
from src.core.stages import Tracker
from src.stages.track.multi.assignment import AssignmentResult
from src.stages.track.multi.kalman import KalmanPointTracker

# Estratégia de associação: (cost, gate) -> (matches, unmatched_tracks, unmatched_dets)
AssignFn = Callable[[list[list[float]], float], AssignmentResult]


class _EntityTrack:
    __slots__ = ("entity_id", "kalman", "points", "misses", "hits")

    def __init__(self, entity_id: int, x: float, y: float, frame_index: int) -> None:
        self.entity_id = entity_id
        self.kalman = KalmanPointTracker(x, y)
        self.points: dict[int, Point2D] = {frame_index: Point2D(x=x, y=y)}
        self.misses = 0
        self.hits = 1


class MultiEntityTracker(Tracker):
    """Tracker multi-entidade; a estratégia de associação é injetada."""

    def __init__(
        self,
        view: Literal["top", "side"],
        assign_fn: AssignFn,
        *,
        max_distance: float = 60.0,
        max_age: int = 12,
        min_hits: int = 3,
    ) -> None:
        self._view: Literal["top", "side"] = view
        self._assign = assign_fn
        self._max_distance = max_distance
        self._max_age = max_age
        self._min_hits = min_hits
        self._active: list[_EntityTrack] = []
        self._retired: list[_EntityTrack] = []
        self._next_id = 0

    def update(self, dets: FrameDetections) -> None:
        frame_index = dets.frame_index
        detections = dets.detections

        # 1. prediz cada track ativo
        predicted: list[tuple[float, float]] = [t.kalman.predict() for t in self._active]

        # 2. matriz de custo (distância predição→detecção)
        cost: list[list[float]] = [
            [math.dist(predicted[i], (d.centroid.x, d.centroid.y)) for d in detections]
            for i in range(len(self._active))
        ]

        # 3. associação
        matches: AssignmentResult
        if self._active and detections:
            matches = self._assign(cost, self._max_distance)
        else:
            matches = ([], list(range(len(self._active))), list(range(len(detections))))
        matched, unmatched_tracks, unmatched_dets = matches

        # 4. casados: corrige Kalman + grava ponto
        for ti, dj in matched:
            track = self._active[ti]
            det = detections[dj]
            track.kalman.update(det.centroid.x, det.centroid.y)
            track.points[frame_index] = det.centroid
            track.misses = 0
            track.hits += 1

        # 5. detecções sem par: nascem tracks novos
        for dj in unmatched_dets:
            det = detections[dj]
            self._active.append(
                _EntityTrack(self._next_id, det.centroid.x, det.centroid.y, frame_index)
            )
            self._next_id += 1

        # 6. tracks sem par: conta miss; aposenta se passar de max_age
        still_active: list[_EntityTrack] = []
        for i, track in enumerate(self._active):
            if i in unmatched_tracks:
                track.misses += 1
                if track.misses > self._max_age:
                    self._retired.append(track)
                    continue
            still_active.append(track)
        self._active = still_active

    def tracks(self) -> list[Track]:
        out: list[Track] = []
        for track in [*self._active, *self._retired]:
            if track.hits < self._min_hits:
                continue  # descarta ids fantasmas (ruído de 1-2 frames)
            out.append(
                Track(entity_id=track.entity_id, view=self._view, points=dict(track.points))
            )
        out.sort(key=lambda t: t.entity_id)
        return out

    def reset(self) -> None:
        self._active.clear()
        self._retired.clear()
        self._next_id = 0
