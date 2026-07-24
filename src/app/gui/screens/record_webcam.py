"""Tela de gravação dupla de webcam (Fase 4, workstream C) — porta
`RecordWebcamVideoUI`, normalizada no protocolo Screen e com os bugs #4/#5
corrigidos.

Mudanças vs. legado:
- Entra pelo dispatcher uniforme (`on_show`), não mais por chamada direta a
  `initial_screen_state()` fora do padrão (era a exceção que quebrava a
  uniformidade das telas).
- O preview NÃO roda mais numa thread solta tocando Tk direto (`thread_show_recoding_video`).
  Vira reagendamento leve via `self.frame.after(33, self._poll_preview)` (~30fps),
  que faz `queue.get_nowait()` e atualiza os Labels JÁ no main thread.
- Usa a função livre `get_image_from_frame_queue` (bug #4: sem `self` sobrando,
  `except Empty` em vez de `except:` nu) e o loop de captura corrigido (bug #5).
- O `except:` nu externo do legado vira captura restrita a `tk.TclError`.
"""

from __future__ import annotations

import logging
import time
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from queue import Queue
from tkinter import ttk
from typing import Any

from PIL import Image, ImageTk

from src.app.gui.preview import get_image_from_frame_queue
from src.app.gui.screen import ScreenBase
from src.app.service import AppService
from src.stages.capture.webcam import start_webcams

logger = logging.getLogger("animaltrack.gui.record_webcam")
_PREVIEW_SIZE = (400, 400)
_RECORDS_DIR = Path("./records/")


class RecordWebcamScreen(ScreenBase):
    def __init__(self, service: AppService, show: Callable[..., None]) -> None:
        self.service = service
        self.show = show
        self.frame: tk.Frame
        self.labels: dict[str, ttk.Label] = {}
        self.buttons: dict[str, ttk.Button] = {}
        self.entry: dict[str, ttk.Entry] = {}
        self._cache: dict[str, object] = {}
        self._images: dict[str, ImageTk.PhotoImage] = {}
        self._preview_job: str | None = None

    def build(self, parent: tk.Misc) -> tk.Frame:
        self.frame = tk.Frame(parent)
        return self.frame

    def on_show(self, **_: object) -> None:
        self._initial_screen_state()

    def on_hide(self) -> None:
        self._cancel_preview()

    def teardown(self) -> None:
        self._cancel_preview()
        stop_event = self._cache.get("stop_event")
        if stop_event is not None:
            stop_event.set()  # type: ignore[attr-defined]

    # --- screen states ---------------------------------------------------------
    def _clear(self) -> None:
        for widget in self.frame.winfo_children():
            widget.destroy()
        self.labels.clear()
        self.buttons.clear()

    def _initial_screen_state(self) -> None:
        self._clear()
        self.labels["fps"] = ttk.Label(self.frame, text="FPS")
        self.labels["fps"].grid(row=1, column=2, padx=10, pady=10)
        self.entry["fps"] = ttk.Entry(self.frame)
        self.entry["fps"].grid(row=2, column=2, padx=10, pady=10)
        self.entry["fps"].insert(0, "30")
        self.buttons["prepare"] = ttk.Button(
            self.frame, text="Preparar para gravar", command=self._prepare_recording
        )
        self.buttons["prepare"].grid(row=3, column=2, padx=10, pady=10)
        self.buttons["back"] = ttk.Button(self.frame, text="Voltar", command=self._close)
        self.buttons["back"].grid(row=4, column=2, padx=10, pady=10)

    def _recording_layout(self) -> None:
        self._clear()
        self.labels["side_text"] = ttk.Label(self.frame, text="Lado")
        self.labels["side_text"].grid(row=2, column=1)
        self.labels["side_image"] = ttk.Label(self.frame)
        self.labels["side_image"].grid(row=3, column=1)
        self.labels["top_text"] = ttk.Label(self.frame, text="Superior")
        self.labels["top_text"].grid(row=2, column=2)
        self.labels["top_image"] = ttk.Label(self.frame)
        self.labels["top_image"].grid(row=3, column=2)

    # --- gravação --------------------------------------------------------------
    def _prepare_recording(self) -> None:
        _RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        frame_rate = int(self.entry["fps"].get())
        queue_side: Queue = Queue()
        queue_top: Queue = Queue()
        handles = start_webcams(
            queue_side, queue_top,
            str(_RECORDS_DIR / f"{stamp}_side.avi"),
            str(_RECORDS_DIR / f"{stamp}_top.avi"),
            frame_rate,
        )
        self._cache = {**handles, "queue_side": queue_side, "queue_top": queue_top}
        self._recording_layout()
        self.buttons["start"] = ttk.Button(
            self.frame, text="Iniciar gravação", command=self._init_recording
        )
        self.buttons["start"].grid(row=1, column=1, padx=10, pady=10)
        self._schedule_preview()

    def _init_recording(self) -> None:
        self._event("start_recording_event_side").set()
        self._event("start_recording_event_top").set()
        self.buttons["start"].config(text="Parar gravação", command=self._stop_recording)

    def _stop_recording(self) -> None:
        self._cancel_preview()
        stop = self._cache.get("stop_event")
        if stop is not None:
            stop.set()  # type: ignore[attr-defined]
        self._close()

    def _close(self) -> None:
        self._cancel_preview()
        self._clear()
        self.show("hub")

    # --- preview (main thread via after) --------------------------------------
    def _schedule_preview(self) -> None:
        self._preview_job = self.frame.after(33, self._poll_preview)

    def _cancel_preview(self) -> None:
        if self._preview_job is not None:
            try:
                self.frame.after_cancel(self._preview_job)
            except tk.TclError:
                pass
            self._preview_job = None

    def _poll_preview(self) -> None:
        try:
            self._update_view("side_image", "queue_side", "error_event_side")
            self._update_view("top_image", "queue_top", "error_event_top")
        except tk.TclError:
            # widget destruído durante shutdown — único caso "esperado" de verdade.
            logger.debug("preview interrompido: widget destruído")
            return
        stop = self._cache.get("stop_event")
        if stop is not None and stop.is_set():  # type: ignore[attr-defined]
            return
        self._schedule_preview()

    def _update_view(self, label_key: str, queue_key: str, error_key: str) -> None:
        error_event = self._cache.get(error_key)
        if error_event is not None and error_event.is_set():  # type: ignore[attr-defined]
            image = ImageTk.PhotoImage(Image.new("RGB", _PREVIEW_SIZE, "black"))
        else:
            queue = self._cache[queue_key]
            image = get_image_from_frame_queue(queue, _PREVIEW_SIZE)  # type: ignore[arg-type]
        self.labels[label_key].config(image=image)
        self._images[label_key] = image  # segura a referência

    def _event(self, key: str) -> Any:
        return self._cache[key]
