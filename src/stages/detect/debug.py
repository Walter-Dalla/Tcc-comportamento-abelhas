"""Export de frames de debug do Detect (resolve a seção 6 do `ux-design-detalhado.md`).

A seção 6 do UX deixou uma pergunta em aberto: como substituir o modo debug do
`backgroundRemoveModule.py` legado (`cv2.imshow` + `cv2.waitKey(0)` **bloqueante**)
num pipeline streaming com GUI não bloqueante. Das duas opções propostas, esta é a
**Opção 2** (recomendação implícita do próprio documento): sem preview ao vivo, o
Detect grava as imagens relevantes numa pasta do workspace e a GUI só oferece
"Abrir pasta de debug".

Garantia central: **nunca bloquear a thread do pipeline**. O `cv2.imwrite` roda numa
thread daemon própria, alimentada por uma fila LIMITADA com `put_nowait` — se a
gravação não acompanha o processamento, o frame é DESCARTADO (contado em
`dropped`) em vez de segurar o pipeline. Debug é diagnóstico, não dado de análise:
perder amostra é preferível a atrasar o run. A thread do Tk nunca é tocada aqui.

Critério de captura (mínimo viável, seção 6): 1 a cada N frames **ou** todo frame
em que a detecção falhou — que é justamente o caso que o pesquisador quer inspecionar.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from queue import Empty, Full, Queue

import cv2
import numpy as np

logger = logging.getLogger("animaltrack.detect.debug")

DEFAULT_EVERY = 100
DEFAULT_MAX_QUEUE = 64


class DebugFrameWriter:
    """Escreve PNGs de debug em `<root>/<view>/` a partir de uma thread própria."""

    def __init__(
        self,
        root: Path,
        *,
        every: int = DEFAULT_EVERY,
        max_queue: int = DEFAULT_MAX_QUEUE,
    ) -> None:
        if every < 1:
            raise ValueError("every deve ser >= 1")
        self.root = Path(root)
        self.every = every
        self._queue: Queue[tuple[Path, np.ndarray] | None] = Queue(maxsize=max_queue)
        self._written = 0
        self._dropped = 0
        self._lock = threading.Lock()
        self._closed = False
        self.root.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(
            target=self._consume, name="animaltrack-debug-writer", daemon=True
        )
        self._thread.start()

    # --- contadores (lidos por teste/log) --------------------------------------
    @property
    def written(self) -> int:
        with self._lock:
            return self._written

    @property
    def dropped(self) -> int:
        with self._lock:
            return self._dropped

    # --- API usada pelo Detect --------------------------------------------------
    def should_capture(self, frame_index: int, *, detected: bool) -> bool:
        """Amostragem: 1 a cada `every` frames, mais TODA falha de detecção."""
        return (not detected) or frame_index % self.every == 0

    def submit(
        self, view: str, frame_index: int, image: np.ndarray, *, detected: bool
    ) -> bool:
        """Enfileira um frame para gravação. Retorna False se descartou (fila cheia).

        Não bloqueia nunca: `put_nowait` + descarte contabilizado.
        """
        if self._closed:
            return False
        status = "det" if detected else "nodet"
        path = self.root / view / f"frame_{frame_index:06d}_{status}.png"
        try:
            self._queue.put_nowait((path, image))
        except Full:
            with self._lock:
                self._dropped += 1
            return False
        return True

    def close(self, timeout: float = 10.0) -> None:
        """Drena a fila e encerra a thread. Idempotente."""
        if self._closed:
            return
        self._closed = True
        try:
            self._queue.put(None, timeout=timeout)
        except Full:  # pragma: no cover - fila cheia e consumidor travado
            logger.warning("fila de debug cheia no close; encerrando sem drenar")
        self._thread.join(timeout=timeout)
        logger.info(
            "frames de debug: %d gravados, %d descartados em %s",
            self.written, self.dropped, self.root,
        )

    # --- thread de gravação -----------------------------------------------------
    def _consume(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=1.0)
            except Empty:
                if self._closed:
                    return
                continue
            if item is None:
                return
            path, image = item
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                if cv2.imwrite(str(path), image):
                    with self._lock:
                        self._written += 1
                else:  # pragma: no cover - depende do encoder do OpenCV
                    logger.warning("cv2.imwrite recusou %s", path)
            except Exception:  # debug nunca derruba o run
                logger.warning("falha ao gravar frame de debug %s", path, exc_info=True)
