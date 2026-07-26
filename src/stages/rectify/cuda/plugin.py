"""CudaPerspectiveRectifier — warp de perspectiva + grayscale na GPU (Fase 5).

Versão GPU do `CpuPerspectiveRectifier` (`src/stages/rectify/plugin.py`), atrás da
MESMA interface — mesmo construtor, mesmas propriedades `role`/`output_shape`,
mesmo `rectify(frame, frame_index) -> RectifiedFrame` — para ser drop-in no
orquestrador. A diferença é só o backend: as operações passam por um `ArrayBackend`
(`CudaArrayBackend` por padrão) em vez de chamar `cv2.warpPerspective`/`cv2.cvtColor`
direto. A matriz de perspectiva é calculada UMA vez no `__init__` (idêntico ao CPU).

Injetável: passar `backend=CpuArrayBackend()` roda o MESMO caminho numérico em CPU
(sem hardware CUDA) — é o que os testes de paridade/plumbing sem GPU usam. Com o
default (`CudaArrayBackend`) o frame fica RESIDENTE na GPU do `upload` ao `download`,
sem round-trip pra RAM entre warp e cvt_color (esse é o ganho de `ArrayBackend`).

**Não exercitável nesta máquina de dev** (opencv-python do PyPI não traz `cudawarping`)
— ver `docs/handoffs/fase5-backends-gpu-handoff.md`. O código é estruturalmente
correto contra a superfície documentada de `cv2.cuda.*`; a validação real (paridade
CPU×GPU) roda só numa máquina/container com OpenCV+CUDA.
"""

from __future__ import annotations

from collections.abc import Sequence

import cv2
import numpy as np

from src.core.array_backend import ArrayBackend, CudaArrayBackend
from src.core.frames import RectifiedFrame
from src.core.plugin import Plugin
from src.core.schema.orientation import BoxOrientationConfig, CameraRole

Point = Sequence[float]


class CudaPerspectiveRectifier(Plugin):
    def __init__(
        self,
        frame_points: Sequence[Point],
        orientation: BoxOrientationConfig | None,
        role: CameraRole,
        video_width: int,
        video_height: int,
        backend: ArrayBackend | None = None,
    ) -> None:
        points = [list(p) for p in frame_points]
        if len(points) != 4:
            # Mesmo fallback default do CPU: warp identidade do frame inteiro.
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
        self._role = role
        self._orientation = orientation
        # Backend só é construído (e o gate CUDA disparado) na primeira necessidade
        # real — permite instanciar/configurar o plugin sem GPU; o gate cai no run.
        self._backend = backend

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
        """(height, width) do frame retificado — análogo a `frame.shape` do CPU."""
        return self._height, self._width

    def _ensure_backend(self) -> ArrayBackend:
        if self._backend is None:
            # `CudaArrayBackend()` chama `require_cuda()` — falha alta/clara sem GPU.
            self._backend = CudaArrayBackend()
        return self._backend

    def rectify(self, frame: np.ndarray, frame_index: int) -> RectifiedFrame:
        # grayscale ANTES do warp (mesma ordem do CpuPerspectiveRectifier, O9): warpar
        # 1 canal em vez de 3 é mais barato e mantém paridade numérica entre os dois.
        backend = self._ensure_backend()
        handle = backend.upload(frame)
        gray_full = backend.cvt_color_gray(handle)
        warped = backend.warp_perspective(gray_full, self._matrix, (self._width, self._height))
        image = backend.download(warped)
        backend.release(handle)
        backend.release(gray_full)
        backend.release(warped)
        return RectifiedFrame(
            image=image,
            role=self._role,
            frame_index=frame_index,
            orientation=self._orientation,
        )
