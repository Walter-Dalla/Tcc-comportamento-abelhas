"""Regressão dos bugs #4 e #5 (Fase 4, seção 5 do plano)."""

from __future__ import annotations

import inspect
import threading

import pytest

from src.app.gui import preview
from src.stages.capture import webcam


# --- bug #4 ---------------------------------------------------------------------
def test_get_image_from_frame_queue_signature_has_no_self() -> None:
    params = list(inspect.signature(preview.get_image_from_frame_queue).parameters)
    assert params == ["queue", "image_size"]
    assert "self" not in params


def test_get_image_from_frame_queue_unexpected_exception_propagates() -> None:
    class ExplodingQueue:
        def get(self, timeout=None):
            raise RuntimeError("falha inesperada da fila")

    with pytest.raises(RuntimeError):
        preview.get_image_from_frame_queue(ExplodingQueue(), (10, 10))  # type: ignore[arg-type]


# --- bug #5 ---------------------------------------------------------------------
class _FakeCap:
    def __init__(self, *_args) -> None:
        self.reads = 0

    def isOpened(self) -> bool:
        return True

    def get(self, _prop) -> int:
        return 320

    def read(self):
        self.reads += 1
        return False, None  # falha de leitura já na 1ª chamada (fase de preview)

    def release(self) -> None:
        pass


class _FakeWriter:
    def __init__(self, *_args) -> None:
        pass

    def write(self, _frame) -> None:
        pass

    def release(self) -> None:
        pass


def test_record_loop_read_failure_before_recording_sets_error_and_exits(monkeypatch) -> None:
    monkeypatch.setattr(webcam.cv2, "VideoCapture", _FakeCap)
    monkeypatch.setattr(webcam.cv2, "VideoWriter", _FakeWriter)
    monkeypatch.setattr(webcam.cv2, "VideoWriter_fourcc", lambda *a: 0)

    sync = threading.Event()
    stop = threading.Event()
    started = threading.Event()
    error = threading.Event()
    start_recording = threading.Event()  # NÃO setado: ainda em preview
    from queue import Queue

    queue: Queue = Queue()
    sync.set()

    thread = threading.Thread(
        target=webcam.record_webcam_video,
        args=(0, "out.avi", 30, sync, stop, queue, started, error, start_recording),
    )
    thread.start()
    thread.join(timeout=2)

    assert not thread.is_alive()  # não há mais loop infinito
    assert error.is_set()  # falha detectada mesmo antes de gravar
