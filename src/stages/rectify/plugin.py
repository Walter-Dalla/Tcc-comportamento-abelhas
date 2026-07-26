"""Rectify — warp de perspectiva + grayscale, um frame por vez (Fase 3).

Porta `BasicModule/perspectiveModule.py` (`perspective`, `get_perspective_size`,
o fallback de 4 pontos default de `process_perspective`, e o
`cv2.cvtColor(..., COLOR_BGR2GRAY)`).

O que muda em relação ao legado: a matriz de perspectiva
(`cv2.getPerspectiveTransform`) é calculada UMA vez em `__init__`, não recalculada
a cada frame como no `perspective()` legado (que roda dentro do loop de
`process_perspective`). E processa 1 frame → 1 `RectifiedFrame`, em vez da lista
inteira de uma vez.

Sobre `BoxOrientationConfig` aqui: o warp em si (os 4 pontos clicados) NÃO depende
da orientação — os 4 pontos são os mesmos que o `PerspectiveUi` sempre coletou. A
orientação entra só como metadado anexado ao `RectifiedFrame`, que o Fuse vai
consumir via `axis_mapping()`. O Rectify não decide nada a partir dela nesta fase.
Ver `docs/plans/fase3-detalhado.md` seção 1.2.
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from src.core.frames import RectifiedFrame
from src.core.plugin import Plugin
from src.core.schema.orientation import BoxOrientationConfig, CameraRole

Point = Sequence[float]


class CpuPerspectiveRectifier(Plugin):
    def __init__(
        self,
        frame_points: Sequence[Point],
        orientation: BoxOrientationConfig | None,
        role: CameraRole,
        video_width: int,
        video_height: int,
    ) -> None:
        points = [list(p) for p in frame_points]
        if len(points) != 4:
            # fallback default do process_perspective legado: warp identidade do frame inteiro
            points = [
                [0, 0],
                [video_width, 0],
                [0, video_height],
                [video_width, video_height],
            ]
        self._width, self._height = self._get_perspective_size(points)
        points1 = np.array(points[0:4], dtype=np.float32)
        points2 = np.array(
            [(0, 0), (self._width, 0), (0, self._height), (self._width, self._height)],
            dtype=np.float32,
        )
        self._matrix = cv2.getPerspectiveTransform(points1, points2)
        self._is_identity = bool(
            np.allclose(self._matrix, np.eye(3), atol=1e-3)
            and self._width == video_width
            and self._height == video_height
        )
        self._role = role
        self._orientation = orientation

    @staticmethod
    def _get_perspective_size(frame_points: Sequence[Point]) -> tuple[int, int]:
        width = int(frame_points[1][0] - frame_points[0][0])
        height = int(frame_points[2][1] - frame_points[0][1])
        return width, height

    @property
    def role(self) -> CameraRole:
        return self._role

    @property
    def output_shape(self) -> tuple[int, int]:
        """(height, width) do frame retificado — análogo a `frame.shape` do legado."""
        return self._height, self._width

    def rectify(self, frame: np.ndarray, frame_index: int) -> RectifiedFrame:
        # converte para grayscale primeiro: warpPerspective em 1 canal é mais barato
        # que em 3 (BGR) — pula o warp quando a matriz é identidade (sem pontos reais
        # de perspectiva), igual antes.
        gray_full = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = (
            gray_full
            if self._is_identity
            else cv2.warpPerspective(gray_full, self._matrix, (self._width, self._height))
        )
        return RectifiedFrame(
            image=gray,
            role=self._role,
            frame_index=frame_index,
            orientation=self._orientation,
        )
