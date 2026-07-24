"""Tela de perspectiva (Fase 4, workstream C) — porta `PerspectiveUi` corrigindo o
bug de thread-safety latente.

No legado, `startUp` rodava inteiro numa thread de fundo, incluindo um
`while not finished: ... self.load_image_on_ui_from_cv2(...); self.show_finish_btn()`
— criação e mutação de widgets Tk FORA do main thread. Aqui: só I/O (cv2) roda em
`run_async(work=...)`; toda mutação de widget acontece em `on_done` (`_apply_*`),
reagendada no main thread via `after()`. O polling `while+sleep` some: o warp é
recomputado UMA vez quando o 4º ponto é clicado (equivalente funcional, visualmente
idêntico — o preview só muda ao atingir 4 pontos).
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps, ImageTk

from src.app.gui.screen import ScreenBase
from src.app.service import AppService


class CaptureError(Exception):
    """Falha ao abrir/ler o vídeo da tela de configuração."""


def _warp_preview(frame: np.ndarray, points: list[list[int]]) -> np.ndarray:
    """Warp de perspectiva só para preview (o warp de produção vive em src/stages/rectify)."""
    width = points[1][0] - points[0][0]
    height = points[2][1] - points[0][1]
    src = np.array(points[0:4], dtype=np.float32)
    dst = np.array([(0, 0), (width, 0), (0, height), (width, height)], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(frame, matrix, (width, height))


class PerspectiveScreen(ScreenBase):
    def __init__(self, service: AppService, role: str, show: Callable[..., None]) -> None:
        self.service = service
        self.role = role  # "top" | "side"
        self.show = show
        self.frame: tk.Frame
        self._video: cv2.VideoCapture | None = None
        self._first_frame: np.ndarray | None = None
        self.finished = False

    @property
    def _points(self) -> list[list[int]]:
        session = self.service.session
        return (
            session.perspective_points_top
            if self.role == "top"
            else session.perspective_points_side
        )

    @_points.setter
    def _points(self, value: list[list[int]]) -> None:
        session = self.service.session
        if self.role == "top":
            session.perspective_points_top = value
        else:
            session.perspective_points_side = value

    # --- construção ------------------------------------------------------------
    def build(self, parent: tk.Misc) -> tk.Frame:
        self.frame = tk.Frame(parent)
        black = Image.new("RGB", (500, 500), (0, 0, 0))
        self._render_image(black)
        self._render_magnifier(Image.new("RGB", (100, 100), (0, 0, 0)))
        ttk.Button(self.frame, text="Voltar", command=self._finish_without_config).grid(
            row=8, column=1, padx=10, pady=10
        )
        self._action_buttons_built = False
        return self.frame

    # --- ciclo de vida ---------------------------------------------------------
    def on_show(self, **kwargs: object) -> None:
        video_path = str(kwargs.get("video_path", ""))
        if not video_path:
            return
        self.finished = False
        # guarda o handle para permitir join em teste (marshalling); a GUI real ignora.
        self._load_thread = self.run_async(
            work=lambda: self._load_first_frame(video_path),
            on_done=self._apply_first_frame,
            on_error=self._show_error,
        )

    def on_hide(self) -> None:
        if self._video is not None:
            self._video.release()
            self._video = None

    # --- trabalho (thread) - SEM Tk --------------------------------------------
    def _load_first_frame(self, video_path: str) -> np.ndarray:
        video = cv2.VideoCapture(video_path)
        if not video.isOpened():
            raise CaptureError(f"Não foi possível abrir o vídeo {video_path}")
        ok, frame = video.read()
        if not ok:
            video.release()
            raise CaptureError("Vídeo sem frames")
        self._video = video
        self._first_frame = frame
        return frame

    # --- callbacks (main thread via after) -------------------------------------
    def _apply_first_frame(self, frame: np.ndarray) -> None:
        self.load_image_on_ui_from_cv2(frame)
        self._maybe_recompute_preview()

    def _maybe_recompute_preview(self) -> None:
        frame = self._first_frame
        if len(self._points) == 4 and frame is not None:
            points = self._points
            self.run_async(
                work=lambda: _warp_preview(frame, points),
                on_done=self._apply_perspective_result,
                on_error=self._show_error,
            )

    def _apply_perspective_result(self, warped: np.ndarray) -> None:
        self.load_image_on_ui_from_cv2(warped)
        self._show_finish_buttons()

    def _show_error(self, exc: Exception) -> None:
        from tkinter import messagebox

        messagebox.showerror("Erro!", str(exc))

    # --- render (main thread) --------------------------------------------------
    def load_image_on_ui_from_cv2(self, image_cv: np.ndarray) -> None:
        self._render_image(Image.fromarray(image_cv))

    def _render_image(self, image: Image.Image) -> None:
        image_height, image_width = image.size
        image.thumbnail((image_height / 2, image_width / 2), Image.Resampling.LANCZOS)
        self._root_image = ImageTk.PhotoImage(image)
        label = ttk.Label(self.frame, image=self._root_image)
        label.grid(row=0, column=0, rowspan=400, padx=10, pady=10)
        label.bind("<Button-1>", self._on_click)
        label.bind("<Motion>", self._on_motion)
        self._image_label = label

    def _render_magnifier(self, image: Image.Image) -> None:
        self._small_image = ImageTk.PhotoImage(image)
        label = ttk.Label(self.frame, image=self._small_image)
        label.grid(row=1, column=1, rowspan=400, padx=10, pady=10)
        self._small_image_label = label

    def _on_click(self, event: tk.Event) -> None:
        if len(self._points) >= 4:
            return
        self._points.append([int(event.x * 2), int(event.y * 2)])
        if len(self._points) == 4:
            self._maybe_recompute_preview()

    def _on_motion(self, event: tk.Event) -> None:
        # Magnifier 100x100 com mira — main thread (bind de evento Tk).
        crop = 100
        x, y = event.x, event.y
        left, upper = max(0, x - crop // 2), max(0, y - crop // 2)
        right, lower = min(self._root_image.width(), x + crop // 2), min(
            self._root_image.height(), y + crop // 2
        )
        image = ImageTk.getimage(self._root_image).crop((left, upper, right, lower))
        expanded = ImageOps.expand(
            image,
            border=(
                max(0, crop // 2 - x),
                max(0, crop // 2 - y),
                max(0, x + crop // 2 - self._root_image.width()),
                max(0, y + crop // 2 - self._root_image.height()),
            ),
            fill="black",
        )
        draw = ImageDraw.Draw(expanded)
        c, r = crop // 2, crop // 4
        draw.ellipse((c - r, c - r, c + r, c + r), outline="red", width=2)
        draw.line((c - 10, c, c + 10, c), fill="red", width=2)
        draw.line((c, c - 10, c, c + 10), fill="red", width=2)
        photo = ImageTk.PhotoImage(expanded)
        self._small_image_label.config(image=photo)
        self._small_image = photo  # segura a referência (evita GC do PhotoImage)

    def _show_finish_buttons(self) -> None:
        if self._action_buttons_built:
            return
        self.finished = True
        ttk.Button(self.frame, text="Finalizar perspectiva", command=self._finish).grid(
            row=6, column=1, padx=10, pady=10
        )
        ttk.Button(self.frame, text="Resetar perspectiva", command=self._reset).grid(
            row=7, column=1, padx=10, pady=10
        )
        self._action_buttons_built = True

    # --- ações -----------------------------------------------------------------
    def _finish(self) -> None:
        self.show("hub")

    def _finish_without_config(self) -> None:
        if not self.finished and self._video is not None:
            width = int(self._video.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self._video.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self._points = [[0, 0], [width, 0], [0, height], [width, height]]
        self.show("hub")

    def _reset(self) -> None:
        self._points = []
        if self._first_frame is not None:
            self.load_image_on_ui_from_cv2(self._first_frame)
