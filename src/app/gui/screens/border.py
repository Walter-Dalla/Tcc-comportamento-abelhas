"""Tela de borda/vidro (Fase 4, workstream C) — porta `BorderUi`.

O 1º frame é carregado via `run_async` (I/O fora do main thread); a lógica de
arrastar cantos (`start_move`/`move_line`/`stop_move`) já roda inteiramente a partir
de binds de evento do Tk (main thread) — só precisa de porte pro novo protocolo, sem
correção de thread-safety. Retângulo axis-aligned de 4 cantos arrastáveis, idêntico
ao legado (ux-design-detalhado.md seção 5: comportamento a preservar).
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import Canvas, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from src.app.gui.screen import ScreenBase
from src.app.service import AppService

_DEFAULT_RECT = [[50, 50], [450, 50], [50, 450], [450, 450]]


class BorderScreen(ScreenBase):
    def __init__(self, service: AppService, role: str, show: Callable[..., None]) -> None:
        self.service = service
        self.role = role
        self.show = show
        self.frame: tk.Frame
        self._moving_corner: int | None = None

    @property
    def _border_points(self) -> list[list[int]]:
        session = self.service.session
        points = session.border_points_top if self.role == "top" else session.border_points_side
        if not points:
            points = [list(p) for p in _DEFAULT_RECT]
            self._border_points = points
        return points

    @_border_points.setter
    def _border_points(self, value: list[list[int]]) -> None:
        session = self.service.session
        if self.role == "top":
            session.border_points_top = value
        else:
            session.border_points_side = value

    def build(self, parent: tk.Misc) -> tk.Frame:
        self.frame = tk.Frame(parent)
        self._render_image(Image.new("RGB", (500, 500), (0, 0, 0)))
        ttk.Button(self.frame, text="Finalizar", command=self._finish).grid(
            row=8, column=1, padx=10, pady=10
        )
        ttk.Button(self.frame, text="Resetar", command=self._reset).grid(
            row=8, column=2, padx=10, pady=10
        )
        return self.frame

    def on_show(self, **kwargs: object) -> None:
        video_path = str(kwargs.get("video_path", ""))
        if not video_path:
            return
        self.run_async(
            work=lambda: self._load_first_frame(video_path),
            on_done=self.load_image_on_ui_from_cv2,
            on_error=self._show_error,
        )

    def _load_first_frame(self, video_path: str) -> np.ndarray:
        video = cv2.VideoCapture(video_path)
        try:
            if not video.isOpened():
                raise RuntimeError(f"Não foi possível abrir o vídeo {video_path}")
            ok, frame = video.read()
            if not ok:
                raise RuntimeError("Vídeo sem frames")
            return frame
        finally:
            video.release()

    def load_image_on_ui_from_cv2(self, image_cv: np.ndarray) -> None:
        self._render_image(Image.fromarray(image_cv))

    def _render_image(self, image: Image.Image) -> None:
        image_height, image_width = image.size
        image.thumbnail((image_height / 2, image_width / 2), Image.Resampling.LANCZOS)
        self._root_image = ImageTk.PhotoImage(image)
        self.image_width = image.width
        self.image_height = image.height
        self.canvas = Canvas(self.frame, width=image.width, height=image.height)
        self.canvas.grid(row=0, column=0, rowspan=400, padx=10, pady=10)
        self.canvas.create_image(0, 0, anchor="nw", image=self._root_image)
        self._draw_lines()
        self.canvas.bind("<ButtonPress-1>", self._start_move)
        self.canvas.bind("<B1-Motion>", self._move_line)
        self.canvas.bind("<ButtonRelease-1>", self._stop_move)

    def _draw_lines(self) -> None:
        self.canvas.delete("line")
        self.canvas.delete("corner")
        points = self._border_points
        pairs = [(0, 1), (1, 3), (3, 2), (2, 0)]
        for a, b in pairs:
            self.canvas.create_line(
                points[a][0], points[a][1], points[b][0], points[b][1],
                fill="red", width=2, tags="line",
            )
        for i, (x, y) in enumerate(points):
            self.canvas.create_oval(
                x - 5, y - 5, x + 5, y + 5, fill="blue", outline="blue",
                tags=("corner", f"corner_{i}"),
            )

    def _start_move(self, event: tk.Event) -> None:
        for i, (x, y) in enumerate(self._border_points):
            if abs(event.x - x) < 10 and abs(event.y - y) < 10:
                self._moving_corner = i
                break

    def _move_line(self, event: tk.Event) -> None:
        corner = self._moving_corner
        if corner is None:
            return
        points = self._border_points
        # espelha o retângulo axis-aligned: mover um canto reposiciona as arestas adjacentes.
        y_partner = {0: 1, 1: 0, 2: 3, 3: 2}[corner]
        x_partner = {0: 2, 1: 3, 2: 0, 3: 1}[corner]
        points[corner][1] = event.y
        points[y_partner][1] = event.y
        points[corner][0] = event.x
        points[x_partner][0] = event.x
        self._draw_lines()

    def _stop_move(self, _event: tk.Event) -> None:
        self._moving_corner = None

    def _show_error(self, exc: Exception) -> None:
        from tkinter import messagebox

        messagebox.showerror("Erro!", str(exc))

    def _finish(self) -> None:
        self.show("hub")

    def _reset(self) -> None:
        self._border_points = [
            [50, 50],
            [self.image_width - 50, 50],
            [50, self.image_height - 50],
            [self.image_width - 50, self.image_height - 50],
        ]
        self._draw_lines()
