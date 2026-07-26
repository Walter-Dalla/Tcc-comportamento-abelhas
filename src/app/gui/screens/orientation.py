"""Tela de orientação de câmera/caixa (Fase 4, workstream D) — tela NOVA.

Implementa o desenho de UX de `docs/plans/ux-design-detalhado.md` seção 2:

- coluna esquerda: miniatura do 1º frame com os 4 pontos de perspectiva já
  clicados, numerados 1-4 na ordem de clique (2.1), + os 4 comboboxes de vértice
  (2.4) + a mensagem de erro inline (2.5);
- coluna direita: wireframe isométrico do cubo num `Canvas` com **6 polígonos
  clicáveis por face** (2.2), rótulos de vértice TFL/TFR/... (2.2 item 5) e o
  rótulo de confirmação "Face selecionada: X" (2.3);
- trio de botões Resetar/Finalizar/Voltar (2.6), `ttk.Button` + `grid()`.

Nota de projeto sobre os polígonos clicáveis: numa projeção isométrica de um cubo
sólido as 6 faces se sobrepõem em tela (a face de trás, no limite, fica inteira
atrás das outras 5). Para que **todas** as 6 faces sejam clicáveis, cada face é
desenhada como um "adesivo" semi-transparente encolhido em direção ao próprio
centroide (`_PATCH_SCALE`) — assim cada face tem uma área exclusiva de clique,
sem deixar de ser lida como "aquela face daquele cubo". O combobox de face
continua existindo como caminho alternativo (teclado/acessibilidade) e é mantido
em sincronia com o clique.

O magnifier de `PerspectiveScreen` NÃO é reaproveitado aqui (decisão explícita da
seção 2.7: a interação é discreta, não há precisão de pixel a ganhar) — a
miniatura não captura cliques.

Configura UMA câmera por visita (role vem em `on_show(role=...)`). Cada câmera vira
uma `CameraOrientation` guardada em `session.orientation_top/side`; quando ambas
estão completas, compõe o `BoxOrientationConfig` e persiste.
"""

from __future__ import annotations

import logging
import math
import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import ttk

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageTk

from src.app.gui.screen import ScreenBase
from src.app.orientation_util import (
    FACE_LABELS_PT,
    MSG_VERTEX_DUPLICATE,
    VERTEX_LABELS_PT,
    validate_selection,
    vertices_for_face,
)
from src.app.service import AppService
from src.core.schema.orientation import BoxFace, BoxVertex, CameraOrientation, CameraRole

logger = logging.getLogger("animaltrack.gui.orientation")

_CORNER_LABELS = (
    "Ponto 1 (superior-direito)",
    "Ponto 2 (superior-esquerdo)",
    "Ponto 3 (inferior-direito)",
    "Ponto 4 (inferior-esquerdo)",
)

_COMBO_PLACEHOLDER = "Escolha a face primeiro"
_FACE_CHANGED_WARNING = "Face alterada — selecione novamente os vértices dos 4 pontos."

# Vértices projetados em isométrica simples (constantes de módulo, calculadas 1x).
# Frente (z=front) e trás (z=back, deslocada por offset iso).
_FRONT = {
    BoxVertex.TOP_FRONT_LEFT: (100, 150),
    BoxVertex.TOP_FRONT_RIGHT: (220, 150),
    BoxVertex.BOTTOM_FRONT_LEFT: (100, 270),
    BoxVertex.BOTTOM_FRONT_RIGHT: (220, 270),
}
_BACK = {
    BoxVertex.TOP_BACK_LEFT: (160, 90),
    BoxVertex.TOP_BACK_RIGHT: (280, 90),
    BoxVertex.BOTTOM_BACK_LEFT: (160, 210),
    BoxVertex.BOTTOM_BACK_RIGHT: (280, 210),
}
_VERTEX_XY = {**_FRONT, **_BACK}
_VERTEX_ABBR = {
    BoxVertex.TOP_FRONT_LEFT: "TFL",
    BoxVertex.TOP_FRONT_RIGHT: "TFR",
    BoxVertex.TOP_BACK_LEFT: "TBL",
    BoxVertex.TOP_BACK_RIGHT: "TBR",
    BoxVertex.BOTTOM_FRONT_LEFT: "BFL",
    BoxVertex.BOTTOM_FRONT_RIGHT: "BFR",
    BoxVertex.BOTTOM_BACK_LEFT: "BBL",
    BoxVertex.BOTTOM_BACK_RIGHT: "BBR",
}

# Os 4 vértices de cada face em ordem CÍCLICA (para `create_polygon`) — o conjunto
# tem de bater com `orientation_util.vertices_for_face` (travado por teste).
_FACE_VERTICES: dict[BoxFace, tuple[BoxVertex, ...]] = {
    BoxFace.FRONT: (
        BoxVertex.TOP_FRONT_LEFT,
        BoxVertex.TOP_FRONT_RIGHT,
        BoxVertex.BOTTOM_FRONT_RIGHT,
        BoxVertex.BOTTOM_FRONT_LEFT,
    ),
    BoxFace.BACK: (
        BoxVertex.TOP_BACK_LEFT,
        BoxVertex.TOP_BACK_RIGHT,
        BoxVertex.BOTTOM_BACK_RIGHT,
        BoxVertex.BOTTOM_BACK_LEFT,
    ),
    BoxFace.TOP: (
        BoxVertex.TOP_FRONT_LEFT,
        BoxVertex.TOP_FRONT_RIGHT,
        BoxVertex.TOP_BACK_RIGHT,
        BoxVertex.TOP_BACK_LEFT,
    ),
    BoxFace.BOTTOM: (
        BoxVertex.BOTTOM_FRONT_LEFT,
        BoxVertex.BOTTOM_FRONT_RIGHT,
        BoxVertex.BOTTOM_BACK_RIGHT,
        BoxVertex.BOTTOM_BACK_LEFT,
    ),
    BoxFace.LEFT: (
        BoxVertex.TOP_FRONT_LEFT,
        BoxVertex.TOP_BACK_LEFT,
        BoxVertex.BOTTOM_BACK_LEFT,
        BoxVertex.BOTTOM_FRONT_LEFT,
    ),
    BoxFace.RIGHT: (
        BoxVertex.TOP_FRONT_RIGHT,
        BoxVertex.TOP_BACK_RIGHT,
        BoxVertex.BOTTOM_BACK_RIGHT,
        BoxVertex.BOTTOM_FRONT_RIGHT,
    ),
}
# ordem do pintor: trás -> frente, para que as faces da frente fiquem por cima.
_FACE_DRAW_ORDER = (
    BoxFace.BACK,
    BoxFace.TOP,
    BoxFace.BOTTOM,
    BoxFace.LEFT,
    BoxFace.RIGHT,
    BoxFace.FRONT,
)
_PATCH_SCALE = 0.45
_PATCH_FILL = "#9aa0a6"
_PATCH_FILL_SELECTED = "#1a73e8"

_THUMB_MAX = 320


_CUBE_CENTER = (
    sum(x for x, _ in _VERTEX_XY.values()) / len(_VERTEX_XY),
    sum(y for _, y in _VERTEX_XY.values()) / len(_VERTEX_XY),
)


def _offset_from_center(x: float, y: float, distance: float) -> tuple[float, float]:
    """Desloca um rótulo radialmente a partir do centro do cubo.

    Distância positiva = para fora (rótulos de vértice), negativa = para dentro
    (nomes de face). Na projeção isométrica o centro de uma face coincide em tela
    com um vértice da face oposta (ex.: centro de "Fundo" cai sobre TFR); afastar
    os dois em direções opostas evita a sobreposição de texto.
    """
    dx, dy = x - _CUBE_CENTER[0], y - _CUBE_CENTER[1]
    norm = math.hypot(dx, dy) or 1.0
    return x + dx / norm * distance, y + dy / norm * distance


def face_tag(face: BoxFace) -> str:
    """Tag do polígono clicável daquela face no Canvas (ex. `face_top`)."""
    return f"face_{face.value}"


def _patch_coords(face: BoxFace) -> list[float]:
    """Polígono da face encolhido em direção ao próprio centroide (ver docstring)."""
    points = [_VERTEX_XY[v] for v in _FACE_VERTICES[face]]
    cx = sum(x for x, _ in points) / len(points)
    cy = sum(y for _, y in points) / len(points)
    coords: list[float] = []
    for x, y in points:
        coords.extend((cx + _PATCH_SCALE * (x - cx), cy + _PATCH_SCALE * (y - cy)))
    return coords


def build_thumbnail(frame: np.ndarray, points: Sequence[Sequence[float]]) -> Image.Image:
    """Miniatura do 1º frame com os 4 pontos de perspectiva numerados (UX 2.1).

    Função pura (sem Tk): roda na thread de trabalho de `run_async`. `points` está
    em coordenadas do vídeo original (o `PerspectiveScreen` grava o clique já
    multiplicado por 2), então são reescalados pelo mesmo fator da miniatura.
    """
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if frame.ndim == 3 else frame
    image = Image.fromarray(rgb)
    scale = min(_THUMB_MAX / max(image.width, 1), _THUMB_MAX / max(image.height, 1), 1.0)
    if scale < 1.0:
        image = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    image = image.convert("RGB")
    draw = ImageDraw.Draw(image)
    for number, point in enumerate(points[:4], start=1):
        x, y = float(point[0]) * scale, float(point[1]) * scale
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill="blue", outline="blue")
        draw.text((x + 8, y - 8), str(number), fill="yellow")
    return image


class OrientationScreen(ScreenBase):
    def __init__(self, service: AppService, show: Callable[..., None]) -> None:
        self.service = service
        self.show = show
        self.frame: tk.Frame
        self.role: str = "top"
        self._face: BoxFace | None = None
        self._vertices: list[BoxVertex | None] = [None, None, None, None]
        self._thumb_photo: ImageTk.PhotoImage | None = None

    # --- construção ------------------------------------------------------------
    def build(self, parent: tk.Misc) -> tk.Frame:
        self.frame = tk.Frame(parent)

        left = tk.Frame(self.frame)
        left.grid(row=0, column=0, padx=10, pady=10, sticky="n")
        right = tk.Frame(self.frame)
        right.grid(row=0, column=1, padx=10, pady=10, sticky="n")

        # --- coluna esquerda: miniatura + 4 pontos + erro inline ---
        self._thumb_label = ttk.Label(left, text="Miniatura do vídeo (pontos 1-4)")
        self._thumb_label.grid(row=0, column=0, columnspan=2, padx=10, pady=10)

        self._corner_vars: list[tk.StringVar] = []
        self._corner_comboboxes: list[ttk.Combobox] = []
        for i, label in enumerate(_CORNER_LABELS):
            tk.Label(left, text=label).grid(row=1 + i, column=0, padx=10, pady=5, sticky="e")
            var = tk.StringVar()
            combo = ttk.Combobox(left, textvariable=var, state="disabled", width=24)
            combo.grid(row=1 + i, column=1, padx=10, pady=5, sticky="w")
            combo.bind("<<ComboboxSelected>>", self._make_vertex_callback(i))
            self._corner_vars.append(var)
            self._corner_comboboxes.append(combo)

        self._error_label = ttk.Label(left, text="", foreground="red", wraplength=380)
        self._error_label.grid(row=5, column=0, columnspan=2, padx=10, pady=5)

        # --- coluna direita: wireframe clicável + confirmação da face ---
        tk.Label(right, text="Qual face da caixa esta câmera enxerga de frente?").grid(
            row=0, column=0, padx=10, pady=10
        )
        self.wireframe_canvas = tk.Canvas(right, width=400, height=360)
        self.wireframe_canvas.grid(row=1, column=0, padx=10, pady=10)
        self._draw_wireframe()

        self._face_label = ttk.Label(right, text="Face selecionada: —")
        self._face_label.grid(row=2, column=0, padx=10, pady=5)

        self.face_var = tk.StringVar()
        self.face_combobox = ttk.Combobox(
            right, textvariable=self.face_var, state="readonly",
            values=[FACE_LABELS_PT[f] for f in BoxFace],
        )
        self.face_combobox.grid(row=3, column=0, padx=10, pady=5)
        self.face_combobox.bind("<<ComboboxSelected>>", self._on_face_combobox)

        buttons = tk.Frame(self.frame)
        buttons.grid(row=1, column=0, columnspan=2, pady=10)
        ttk.Button(buttons, text="Resetar orientação", command=self._reset).grid(
            row=0, column=0, padx=10, pady=10
        )
        ttk.Button(buttons, text="Finalizar orientação", command=self._on_save).grid(
            row=0, column=1, padx=10, pady=10
        )
        ttk.Button(buttons, text="Voltar", command=lambda: self.show("hub")).grid(
            row=0, column=2, padx=10, pady=10
        )
        self._reset()
        return self.frame

    def _draw_wireframe(self) -> None:
        canvas = self.wireframe_canvas
        # 1) adesivos clicáveis por face (ordem do pintor: trás -> frente)
        for face in _FACE_DRAW_ORDER:
            canvas.create_polygon(
                _patch_coords(face),
                fill=_PATCH_FILL,
                stipple="gray25",
                outline="gray50",
                activefill=_PATCH_FILL_SELECTED,
                tags=(face_tag(face), "face"),
            )

        # 2) as 12 arestas do wireframe, por cima dos adesivos
        edges = [
            (BoxVertex.TOP_FRONT_LEFT, BoxVertex.TOP_FRONT_RIGHT),
            (BoxVertex.TOP_FRONT_RIGHT, BoxVertex.BOTTOM_FRONT_RIGHT),
            (BoxVertex.BOTTOM_FRONT_RIGHT, BoxVertex.BOTTOM_FRONT_LEFT),
            (BoxVertex.BOTTOM_FRONT_LEFT, BoxVertex.TOP_FRONT_LEFT),
            (BoxVertex.TOP_BACK_LEFT, BoxVertex.TOP_BACK_RIGHT),
            (BoxVertex.TOP_BACK_RIGHT, BoxVertex.BOTTOM_BACK_RIGHT),
            (BoxVertex.BOTTOM_BACK_RIGHT, BoxVertex.BOTTOM_BACK_LEFT),
            (BoxVertex.BOTTOM_BACK_LEFT, BoxVertex.TOP_BACK_LEFT),
            (BoxVertex.TOP_FRONT_LEFT, BoxVertex.TOP_BACK_LEFT),
            (BoxVertex.TOP_FRONT_RIGHT, BoxVertex.TOP_BACK_RIGHT),
            (BoxVertex.BOTTOM_FRONT_LEFT, BoxVertex.BOTTOM_BACK_LEFT),
            (BoxVertex.BOTTOM_FRONT_RIGHT, BoxVertex.BOTTOM_BACK_RIGHT),
        ]
        for a, b in edges:
            canvas.create_line(*_VERTEX_XY[a], *_VERTEX_XY[b], fill="gray40", width=2)

        # 3) rótulos dos 8 vértices + legenda
        for vertex, (x, y) in _VERTEX_XY.items():
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="black")
            label_x, label_y = _offset_from_center(x, y, 14)
            canvas.create_text(
                label_x, label_y, text=_VERTEX_ABBR[vertex], font=("TkDefaultFont", 8)
            )

        # 4) nome PT da face sobre cada adesivo + binding de clique (a tag cobre
        #    polígono E texto, então clicar no rótulo também escolhe a face).
        for face in _FACE_DRAW_ORDER:
            tag = face_tag(face)
            coords = _patch_coords(face)
            text_x, text_y = _offset_from_center(
                sum(coords[0::2]) / 4, sum(coords[1::2]) / 4, -9
            )
            canvas.create_text(
                text_x,
                text_y,
                text=FACE_LABELS_PT[face],
                font=("TkDefaultFont", 8),
                tags=(tag, "face"),
            )
            canvas.tag_bind(tag, "<Button-1>", self._make_face_callback(face))
        canvas.create_text(
            200, 310,
            text="T = topo/B = base, F = frente/B = trás, L = esquerda/R = direita",
            font=("TkDefaultFont", 8),
        )
        canvas.create_text(
            200, 330,
            text="Clique na face que esta câmera enxerga de frente",
            font=("TkDefaultFont", 8),
            fill="gray30",
        )

    def _make_vertex_callback(self, index: int) -> Callable[[object], None]:
        return lambda _event: self._on_vertex_combobox(index)

    def _make_face_callback(self, face: BoxFace) -> Callable[[object], None]:
        return lambda _event: self.set_face(face)

    # --- ciclo de vida ---------------------------------------------------------
    def on_show(self, **kwargs: object) -> None:
        role = str(kwargs.get("role", "top"))
        self.role = role
        existing = (
            self.service.session.orientation_top
            if role == "top"
            else self.service.session.orientation_side
        )
        if existing is not None:
            self.set_face(existing.face_viewed)
            for i, vertex in enumerate(existing.corner_vertices):
                self.set_vertex(i, vertex)
        else:
            self._reset()
        self._load_thumbnail(str(kwargs.get("video_path", "")))

    # --- miniatura (UX 2.1) ----------------------------------------------------
    def _load_thumbnail(self, video_path: str) -> None:
        """Carrega o 1º frame fora do main thread; desenha em `on_done`.

        A miniatura é um auxílio visual: se o vídeo não abrir, a tela continua
        utilizável (só troca o texto do label) — nada de `messagebox` modal.
        """
        if not video_path:
            return
        points = list(self._perspective_points())
        self.run_async(
            work=lambda: self._read_thumbnail(video_path, points),
            on_done=self._apply_thumbnail,
            on_error=self._thumbnail_failed,
        )

    def _perspective_points(self) -> list[list[int]]:
        session = self.service.session
        return (
            session.perspective_points_top
            if self.role == "top"
            else session.perspective_points_side
        )

    @staticmethod
    def _read_thumbnail(video_path: str, points: list[list[int]]) -> Image.Image:
        video = cv2.VideoCapture(video_path)
        try:
            if not video.isOpened():
                raise OSError(f"Não foi possível abrir o vídeo {video_path}")
            ok, frame = video.read()
            if not ok:
                raise OSError("Vídeo sem frames")
        finally:
            video.release()
        return build_thumbnail(frame, points)

    def _apply_thumbnail(self, image: Image.Image) -> None:
        self._thumb_photo = ImageTk.PhotoImage(image)
        self._thumb_label.config(image=self._thumb_photo, text="")

    def _thumbnail_failed(self, exc: Exception) -> None:
        logger.warning("miniatura de orientação indisponível: %s", exc)
        self._thumb_label.config(image="", text="Miniatura do vídeo indisponível")

    # --- lógica de seleção (usada por widgets E testes) ------------------------
    def set_face(self, face: BoxFace) -> None:
        had_selection = self._face is not None and any(v is not None for v in self._vertices)
        changed = self._face is not None and self._face is not face
        self._face = face
        self._vertices = [None, None, None, None]
        self.face_var.set(FACE_LABELS_PT[face])
        self._face_label.config(text=f"Face selecionada: {FACE_LABELS_PT[face]}")
        self._highlight_face(face)
        labels = [VERTEX_LABELS_PT[v] for v in vertices_for_face(face)]
        for var, combo in zip(self._corner_vars, self._corner_comboboxes, strict=True):
            var.set("")
            combo.config(values=labels, state="readonly")
        # o aviso só faz sentido quando algo REALMENTE foi resetado (UX 2.4);
        # na primeira escolha de face não há seleção anterior a refazer.
        self._error_label.config(text=_FACE_CHANGED_WARNING if (changed and had_selection) else "")

    def _highlight_face(self, face: BoxFace | None) -> None:
        canvas = self.wireframe_canvas
        for candidate in _FACE_DRAW_ORDER:
            selected = candidate is face
            for item in canvas.find_withtag(face_tag(candidate)):
                # só o polígono muda de cor; o rótulo de texto da face continua legível
                if canvas.type(item) != "polygon":
                    continue
                canvas.itemconfig(
                    item,
                    fill=_PATCH_FILL_SELECTED if selected else _PATCH_FILL,
                    stipple="" if selected else "gray25",
                )

    def set_vertex(self, index: int, vertex: BoxVertex) -> None:
        self._vertices[index] = vertex
        self._corner_vars[index].set(VERTEX_LABELS_PT[vertex])
        self._error_label.config(text="")

    def _on_face_combobox(self, _event: object) -> None:
        label = self.face_var.get()
        for face, pt in FACE_LABELS_PT.items():
            if pt == label:
                self.set_face(face)
                return

    def _on_vertex_combobox(self, index: int) -> None:
        if self._face is None:
            return
        label = self._corner_vars[index].get()
        chosen = next(
            (v for v in vertices_for_face(self._face) if VERTEX_LABELS_PT[v] == label), None
        )
        if chosen is None:
            return
        if chosen in [v for j, v in enumerate(self._vertices) if j != index]:
            # vértice já usado em outro combo: reverte + erro inline.
            self._corner_vars[index].set("")
            self._vertices[index] = None
            self._error_label.config(text=MSG_VERTEX_DUPLICATE)
            return
        self.set_vertex(index, chosen)

    # --- ações -----------------------------------------------------------------
    def _on_save(self) -> str | None:
        """Valida e persiste; retorna a mensagem de erro (ou None se sucesso).
        O retorno existe para testabilidade headless — a UI mostra o erro inline."""
        error = validate_selection(self._face, self._vertices)
        if error is not None:
            self._error_label.config(text=error)
            return error

        assert self._face is not None
        corners = [v for v in self._vertices if v is not None]
        role = CameraRole.TOP if self.role == "top" else CameraRole.SIDE
        camera = CameraOrientation(role=role, face_viewed=self._face, corner_vertices=corners)

        session = self.service.session
        if self.role == "top":
            session.orientation_top = camera
        else:
            session.orientation_side = camera

        config = session.build_orientation()
        if config is not None and session.profile_name:
            self.service.save_orientation(session.profile_name, config)

        self._error_label.config(text="")
        self.show("hub")
        return None

    def _reset(self) -> None:
        self._face = None
        self._vertices = [None, None, None, None]
        self.face_var.set("")
        self._face_label.config(text="Face selecionada: —")
        self._highlight_face(None)
        for var, combo in zip(self._corner_vars, self._corner_comboboxes, strict=True):
            var.set(_COMBO_PLACEHOLDER)
            combo.config(values=[], state="disabled")
        self._error_label.config(text="")
