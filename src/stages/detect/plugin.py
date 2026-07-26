"""Detect — subtração de fundo por frame, saída N-detecções (Fase 3).

Porta `BasicModule/backgroundRemoveModule.py::remove_background` inteiro:
construção do modelo de fundo (amostragem a cada `frame_block=500` frames +
`np.max(sampled, axis=0)`) e detecção por frame (`cv2.absdiff` → duplo threshold
80/127 → `findContours(RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)` → maior contorno por
área → centroide via `cv2.moments` com `cy_from_bottom = frame_height - cy_from_top`).

Duas mudanças estruturais (ver `docs/plans/fase3-detalhado.md` seção 3):

1. **Duas passadas reais** sobre o mesmo vídeo, porque o algoritmo legado é
   NÃO-CAUSAL: para detectar no frame 0 ele já precisa de `max_frame`, que depende
   de frames futuros (índices 500, 1000, ...). O passe 1 (`setup`) constrói o
   modelo de fundo streaming-friendly (retém só ~`frame_count/500` frames); o passe
   2 (`detect`, chamado por frame pelo orquestrador) faz a detecção. Isso mantém a
   matemática idêntica ao legado (mesmo `np.max` sobre os mesmos índices) sem
   bufferizar o vídeo inteiro.

2. **Sem sentinela `(-1, -1)`**: nenhuma detecção → `FrameDetections(..., detections=[])`.

O modo debug (`cv2.imshow`/`waitKey(0)`) do legado NÃO é portado — um generator
streaming não pode bloquear em `waitKey(0)`. Em seu lugar, o `DebugFrameWriter`
opcional (`debug=`, ver `src/stages/detect/debug.py`) grava frames amostrados em
disco a partir de uma thread própria: é a Opção 2 da seção 6 do
`docs/plans/ux-design-detalhado.md`, que substitui o preview bloqueante por
inspeção pós-hoc sem travar nem o pipeline nem a UI.

Ponto de acoplamento (seção 3.4): o passe 1 precisa instanciar Capture+Rectify.
Em vez do `ctx.capture_factory`/`ctx.rectifier_factory` do rascunho do plano (que
exigiria estender o `PipelineContext` da Fase 2), Capture e Rectify são injetados
via construtor — testável com fakes, sem plumbing de contexto. O passe 1 lê SÓ a
view deste detector, via `capture.open_single(role)`, até o fim do seu próprio
vídeo (nunca o generator pareado, que trunca no mais curto).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol

import cv2
import numpy as np

from src.core.frames import RectifiedFrame
from src.core.schema.detection import Detection, FrameDetections
from src.core.schema.geometry import Point2D
from src.core.schema.orientation import CameraRole
from src.core.stages import Detector
from src.stages.detect.debug import DebugFrameWriter

if TYPE_CHECKING:
    from collections.abc import Iterator

    from src.core.pipeline import PipelineContext

FRAME_BLOCK = 500
_MIN_THRESHOLD = 80


class DetectError(Exception):
    """Modelo de fundo não construído (setup não rodou) ou vídeo sem frames."""


class _CaptureLike(Protocol):
    def open_single(self, role: CameraRole) -> Iterator[np.ndarray]: ...


class _RectifierLike(Protocol):
    def rectify(self, frame: np.ndarray, frame_index: int) -> RectifiedFrame: ...


class BackgroundSubtractionDetector(Detector):
    def __init__(
        self,
        capture: _CaptureLike,
        rectifier: _RectifierLike,
        role: CameraRole,
        frame_block: int = FRAME_BLOCK,
        debug: DebugFrameWriter | None = None,
    ) -> None:
        self._capture = capture
        self._rectifier = rectifier
        self._role = role
        self._frame_block = frame_block
        self._debug = debug
        self._max_frame: np.ndarray | None = None

    @property
    def role(self) -> CameraRole:
        return self._role

    def setup(self, ctx: PipelineContext | None = None) -> None:
        """Passe 1: constrói o modelo de fundo lendo SÓ a view deste detector, até
        o fim do seu próprio vídeo. Retém um único acumulador de max corrente, sem lista."""
        accumulator: np.ndarray | None = None
        counter = 0
        for raw in self._capture.open_single(self._role):
            if counter % self._frame_block == 0:
                rectified = self._rectifier.rectify(raw, counter)
                if accumulator is None:
                    accumulator = rectified.image.astype(np.uint8).copy()
                else:
                    np.maximum(accumulator, rectified.image, out=accumulator)
            counter += 1
        if accumulator is None:
            raise DetectError(
                f"nenhum frame lido para a view {self._role.value} — vídeo vazio ou ilegível"
            )
        self._max_frame = accumulator

    def detect(self, frame: RectifiedFrame) -> FrameDetections:
        """Passe 2: detecta o inseto num frame retificado usando o `max_frame` do passe 1."""
        if self._max_frame is None:
            raise DetectError("detect() chamado antes de setup() — modelo de fundo ausente")

        view: Literal["top", "side"] = "top" if frame.role is CameraRole.TOP else "side"
        dif_frame = cv2.absdiff(self._max_frame, frame.image)
        _, binarizada = cv2.threshold(dif_frame, _MIN_THRESHOLD, 255, cv2.THRESH_BINARY)

        detections = self._detections_from_mask(binarizada, frame.image.shape[0])
        self._emit_debug(view, frame.frame_index, binarizada, detected=bool(detections))
        return FrameDetections(
            frame_index=frame.frame_index, view=view, detections=detections
        )

    @staticmethod
    def _detections_from_mask(mask: np.ndarray, frame_height: int) -> list[Detection]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []
        max_contour = max(contours, key=cv2.contourArea)
        moments = cv2.moments(max_contour)
        if moments["m00"] == 0:
            return []
        cx = int(moments["m10"] / moments["m00"])
        cy_from_top = int(moments["m01"] / moments["m00"])
        cy_from_bottom = frame_height - cy_from_top
        area = float(cv2.contourArea(max_contour))
        return [Detection(centroid=Point2D(x=float(cx), y=float(cy_from_bottom)), area=area)]

    def _emit_debug(
        self, view: str, frame_index: int, mask: np.ndarray, *, detected: bool
    ) -> None:
        """Amostra frames para inspeção pós-hoc (UX seção 6, Opção 2).

        Nunca bloqueia: o writer enfileira e descarta se não acompanhar. Sem
        writer configurado (caso padrão) o custo é um `if`."""
        debug = self._debug
        if debug is None or not debug.should_capture(frame_index, detected=detected):
            return
        debug.submit(view, frame_index, mask, detected=detected)
