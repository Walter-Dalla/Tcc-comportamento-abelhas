"""Capture — leitura streaming de dois arquivos de vídeo (Fase 3).

Porta a lógica de `ExportModule/videoUtils.py::open_video` + o laço de leitura
hoje embutido em `BasicModule/perspectiveModule.py::process_perspective`
(`while True: success, frame = video.read(); if not success: break`), separando
"abrir e ler frames crus" (aqui) de "aplicar perspectiva" (Rectify).

Diferenças de comportamento em relação ao legado (ver `docs/plans/fase3-detalhado.md`):
- Streaming: devolve um `Iterator[FramePair]` em vez de bufferizar o vídeo inteiro
  numa lista (raiz do problema de memória que a Fase 3 resolve).
- `CaptureError` explícito em vez de `return False, None` — é o que torna o bug #1
  (unpack de 3-tupla/4-tupla em `processVideoModule.process_video`) obsoleto.
- Lockstep de 2 câmeras acontece AQUI: o generator para de emitir assim que
  QUALQUER um dos dois vídeos acaba (para no vídeo mais curto). Resultado final
  idêntico ao `min(len(top), len(side))` do `route_module` legado, mas sem
  decodificar/retificar/detectar os frames extras do vídeo mais longo.

Nota de fidelidade — `fps` vem SÓ do vídeo do topo (como no legado: em
`processVideoModule`, `top_success, top_frames, fps, ... = future_top.result()`
roda por último e sobrescreve o `fps` do lado). Ver seção 1.1 do plano.

Decisão de implementação (desvio do corpo sugerido no plano): leitura SÍNCRONA
(sem threads/filas). As threads do plano são uma otimização de throughput (overlap
de decode das 2 câmeras), não de memória — o perfil de memória streaming O(1) é
idêntico. A versão síncrona é determinística e mais simples de raciocinar/testar;
o pipelining por thread fica como otimização de performance para uma fase futura.
"""

from __future__ import annotations

from collections.abc import Iterator

import cv2
import numpy as np

from src.core.frames import FramePair
from src.core.plugin import Plugin
from src.core.schema.orientation import CameraRole


class CaptureError(Exception):
    """Levantado quando um vídeo não abre ou para de fornecer frames de forma inesperada."""


class DualVideoFileCapture(Plugin):
    def __init__(self, top_video_path: str, side_video_path: str) -> None:
        self._top_path = top_video_path
        self._side_path = side_video_path

    def _path_for(self, role: CameraRole) -> str:
        return self._top_path if role is CameraRole.TOP else self._side_path

    def dimensions(self, role: CameraRole) -> tuple[int, int]:
        """(width, height) do vídeo da câmera `role`. Usado pelo Rectify para o
        fallback de 4 pontos default quando nenhum ponto de perspectiva foi clicado."""
        path = self._path_for(role)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise CaptureError(f"Falha ao abrir vídeo ({role.value}): {path}")
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        finally:
            cap.release()
        return width, height

    def open(self) -> tuple[int, Iterator[FramePair]]:
        """Abre os dois vídeos e devolve `(fps, generator)`. Cada chamada abre do
        zero (reabertura é necessária: o Detect faz uma pré-passada por câmera antes
        da passada pareada — ver Detect.setup). O generator para no vídeo mais curto."""
        top_cap = cv2.VideoCapture(self._top_path)
        if not top_cap.isOpened():
            raise CaptureError(f"Falha ao abrir vídeo do topo: {self._top_path}")
        side_cap = cv2.VideoCapture(self._side_path)
        if not side_cap.isOpened():
            top_cap.release()
            raise CaptureError(f"Falha ao abrir vídeo lateral: {self._side_path}")

        fps = int(top_cap.get(cv2.CAP_PROP_FPS))  # fps do topo, como no legado

        def _generator() -> Iterator[FramePair]:
            index = 0
            try:
                while True:
                    ok_top, top_frame = top_cap.read()
                    ok_side, side_frame = side_cap.read()
                    # para no MENOR dos dois vídeos — lockstep explícito (ver docstring)
                    if not ok_top or not ok_side:
                        break
                    yield FramePair(frame_index=index, top=top_frame, side=side_frame)
                    index += 1
            finally:
                top_cap.release()
                side_cap.release()

        return fps, _generator()

    def open_single(self, role: CameraRole) -> Iterator[np.ndarray]:
        """Itera os frames crus de UMA câmera até o fim do SEU próprio vídeo — sem
        lockstep com a outra câmera.

        Necessário para a construção do modelo de fundo do Detect (passe 1), que é
        por-câmera e independente do parceiro: usar o generator pareado `open()`
        truncaria o modelo de fundo da câmera mais longa no comprimento da mais
        curta e divergiria do comportamento legado (que amostra o vídeo inteiro de
        cada câmera). Ver `docs/plans/fase3-detalhado.md` seções 2.2 e 3.4.
        """
        path = self._path_for(role)
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise CaptureError(f"Falha ao abrir vídeo ({role.value}): {path}")

        def _generator() -> Iterator[np.ndarray]:
            try:
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    yield frame
            finally:
                cap.release()

        return _generator()
