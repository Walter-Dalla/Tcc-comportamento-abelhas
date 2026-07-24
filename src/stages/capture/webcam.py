"""Captura de webcam para gravação sincronizada (Fase 4) — porta
`ExportModule/recordVideo.py` corrigindo o bug #5.

Bug #5 (ARCHITECTURE.md): no legado a checagem `if not ret: break` vivia DENTRO de
`if start_recording.is_set()`, então uma falha de leitura na fase de preview
(antes de "Iniciar gravação") nunca era detectada — busy loop 100% CPU + `queue.put`
com frame `None`. Aqui a checagem de `ret` vem ANTES e FORA de `start_recording`,
sempre alcançável, e seta `error_event` (observado pela UI) numa falha após a
abertura bem-sucedida da câmera; `queue.put` só recebe frame válido.
"""

from __future__ import annotations

import logging
import threading
from queue import Queue

import cv2

logger = logging.getLogger("animaltrack.capture.webcam")


def record_webcam_video(
    camera_index: int,
    output_file: str,
    frame_rate: int,
    sync_event: threading.Event,
    stop_event: threading.Event,
    queue: Queue,
    started_event: threading.Event,
    error_event: threading.Event,
    start_recording: threading.Event,
) -> None:
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        logger.error("Erro ao acessar a câmera %s", camera_index + 1)
        error_event.set()
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"XVID")  # type: ignore[attr-defined]
    out = cv2.VideoWriter(output_file, fourcc, frame_rate, (width, height))

    try:
        while not stop_event.is_set():
            sync_event.wait()
            started_event.set()

            ret, frame = cap.read()
            if not ret:
                # bug #5: agora alcançável também na fase de preview.
                logger.error("Erro ao capturar quadro da câmera %s.", camera_index)
                error_event.set()
                break

            queue.put(frame)

            if start_recording.is_set():
                out.write(frame)
    finally:
        cap.release()
        out.release()
        logger.info("Gravação finalizada para a câmera %s.", camera_index)


def start_webcams(
    queue_side: Queue,
    queue_top: Queue,
    output_file_side: str,
    output_file_top: str,
    frame_rate: int,
) -> dict[str, object]:
    """Sobe uma thread por câmera (índices 0/1), sincronizadas por `sync_event`.

    Retorna um dict de eventos/threads/filas — mais legível que a 11-tupla do
    legado (que exigia desempacotamento posicional frágil no controller)."""
    sync_event = threading.Event()
    stop_event = threading.Event()
    start_recording_event_side = threading.Event()
    start_recording_event_top = threading.Event()
    started_event_side = threading.Event()
    started_event_top = threading.Event()
    error_event_side = threading.Event()
    error_event_top = threading.Event()

    thread_side = threading.Thread(
        target=record_webcam_video,
        args=(
            0, output_file_side, frame_rate, sync_event, stop_event, queue_side,
            started_event_side, error_event_side, start_recording_event_side,
        ),
        daemon=True,
    )
    thread_top = threading.Thread(
        target=record_webcam_video,
        args=(
            1, output_file_top, frame_rate, sync_event, stop_event, queue_top,
            started_event_top, error_event_top, start_recording_event_top,
        ),
        daemon=True,
    )
    thread_side.start()
    thread_top.start()
    sync_event.set()

    return {
        "sync_event": sync_event,
        "stop_event": stop_event,
        "thread_side": thread_side,
        "thread_top": thread_top,
        "frame_rate": frame_rate,
        "started_event_side": started_event_side,
        "started_event_top": started_event_top,
        "error_event_side": error_event_side,
        "error_event_top": error_event_top,
        "start_recording_event_side": start_recording_event_side,
        "start_recording_event_top": start_recording_event_top,
    }
