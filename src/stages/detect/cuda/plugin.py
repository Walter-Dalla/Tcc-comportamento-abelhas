"""CudaMOG2Detector — subtração de fundo MOG2 na GPU (Fase 5).

Implementa a MESMA interface `Detector` (`src/core/stages.py`) que o
`BackgroundSubtractionDetector` da Fase 3: `detect(frame) -> FrameDetections`,
propriedade `role`, hook `setup()`. É drop-in por contrato — mas é um algoritmo
DIFERENTE, não a versão GPU do detector CPU.

**Assimetria de algoritmo (registrar — não é bug, é decisão de ARCHITECTURE.md)**:
- CPU (`BackgroundSubtractionDetector`): subtração de fundo por *imagem de máximo
  estático* (`np.max` de amostras) + `cv2.absdiff` + duplo threshold fixo (80/127),
  em duas passadas não-causais. Sem estado a aquecer.
- GPU (este): MOG2 (`cv2.cuda.createBackgroundSubtractorMOG2`) — primitiva de GPU
  escolhida em `ARCHITECTURE.md` ("Estratégia GPU"). É *stateful* e *causal*: precisa
  de N frames de aquecimento para convergir; não tem imagem de máximo nem os
  thresholds fixos do CPU.

Só o PASSO FINAL (maior contorno por área → centroide via `cv2.moments`, com
`cy_from_bottom = frame_height - cy_from_top`) é idêntico ao CPU — replicado aqui
para manter o plugin autocontido. Por isso os testes de "paridade" são de
EQUIVALÊNCIA COMPORTAMENTAL na fixture (mesmo alvo, ~mesmo centroide dentro de
tolerância), NÃO paridade de máscara/bit. Ver `docs/plans/fase5-detalhado.md` seção 3.

**Nota de escopo GPU (limitação real do `cv2.cuda`)**: `cv2.cuda` não expõe
`findContours`/`moments` práticos em Python. Só a subtração MOG2 (`apply`) roda na
GPU; a máscara de foreground é baixada pra CPU e o resto (contorno/centroide) roda
em CPU — idêntico ao caminho CPU. Não é "tudo na GPU".

**Não exercitável nesta máquina de dev** (opencv-python do PyPI não traz
`cudabgsegm`) — ver `docs/handoffs/fase5-backends-gpu-handoff.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import cv2

from src.core.array_backend import ArrayBackend, CudaArrayBackend
from src.core.frames import RectifiedFrame
from src.core.gpu import require_cuda
from src.core.schema.detection import Detection, FrameDetections
from src.core.schema.geometry import Point2D
from src.core.schema.orientation import CameraRole
from src.core.stages import Detector

if TYPE_CHECKING:
    from src.core.pipeline import PipelineContext

# Defaults de MOG2 (só existem no lado GPU — o CPU usa thresholds fixos 80/127).
_HISTORY = 500
_VAR_THRESHOLD = 16.0
_DETECT_SHADOWS = False
# Threshold da máscara de foreground pós-MOG2 (sombras, se habilitadas, saem como
# cinza ~127; usamos 200 para pegar só foreground forte, coerente com o alvo sólido).
_FG_THRESHOLD = 200


class DetectError(Exception):
    """Subtractor MOG2 não construído (setup não rodou) ou frame inválido."""


class CudaMOG2Detector(Detector):
    def __init__(
        self,
        role: CameraRole = CameraRole.TOP,
        *,
        backend: ArrayBackend | None = None,
        subtractor: Any | None = None,
        history: int = _HISTORY,
        var_threshold: float = _VAR_THRESHOLD,
        detect_shadows: bool = _DETECT_SHADOWS,
    ) -> None:
        self._role = role
        self._backend = backend
        # `subtractor` injetável (testes/fakes); em produção é criado no `setup()`,
        # NÃO no __init__ — assim instanciar o plugin não exige CUDA (o gate cai no
        # run). `cv2.cuda.createBackgroundSubtractorMOG2` nem existe sem contrib+CUDA.
        self._subtractor = subtractor
        self._history = history
        self._var_threshold = var_threshold
        self._detect_shadows = detect_shadows

    @property
    def role(self) -> CameraRole:
        return self._role

    def setup(self, ctx: PipelineContext | None = None) -> None:
        """Constrói backend + subtractor MOG2, disparando o gate CUDA. MOG2 é online
        (causal): não há pré-passada sobre o vídeo como no CPU — o modelo converge
        ao longo dos primeiros frames do próprio `detect()` (aquecimento)."""
        require_cuda()
        if self._backend is None:
            self._backend = CudaArrayBackend()
        if self._subtractor is None:
            # `# type: ignore[attr-defined]` — fricção conhecida do plano Fase 5 (seção
            # 5): stubs do OpenCV não declaram `cv2.cuda.createBackgroundSubtractorMOG2`
            # (módulo contrib `cudabgsegm` ausente na wheel padrão). Ignore pontual.
            self._subtractor = cv2.cuda.createBackgroundSubtractorMOG2(  # type: ignore[attr-defined]
                self._history, self._var_threshold, self._detect_shadows
            )

    def detect(self, frame: RectifiedFrame) -> FrameDetections:
        if self._subtractor is None or self._backend is None:
            raise DetectError("detect() chamado antes de setup() — subtractor MOG2 ausente")

        view: Literal["top", "side"] = "top" if frame.role is CameraRole.TOP else "side"

        handle = self._backend.upload(frame.image)
        fg_gpu = self._subtractor.apply(handle, -1, cv2.cuda.Stream_Null())  # type: ignore[attr-defined]
        fg_mask = self._backend.download(fg_gpu)  # sai da GPU aqui — ver nota de escopo
        self._backend.release(handle)
        self._backend.release(fg_gpu)

        # --- daqui pra baixo: idêntico ao passo final do detector CPU (roda em CPU) ---
        _, binarizada = cv2.threshold(fg_mask, _FG_THRESHOLD, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(
            binarizada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return FrameDetections(frame_index=frame.frame_index, view=view, detections=[])

        max_contour = max(contours, key=cv2.contourArea)
        moments = cv2.moments(max_contour)
        if moments["m00"] == 0:
            return FrameDetections(frame_index=frame.frame_index, view=view, detections=[])

        cx = int(moments["m10"] / moments["m00"])
        cy_from_top = int(moments["m01"] / moments["m00"])
        frame_height = frame.image.shape[0]
        cy_from_bottom = frame_height - cy_from_top
        area = float(cv2.contourArea(max_contour))

        detection = Detection(centroid=Point2D(x=float(cx), y=float(cy_from_bottom)), area=area)
        return FrameDetections(
            frame_index=frame.frame_index, view=view, detections=[detection]
        )
