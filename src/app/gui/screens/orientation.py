"""Tela de orientação de câmera/caixa (Fase 4, workstream D) — tela NOVA.

Implementa a forma técnica mínima do plano (seção 4) + o desenho de UX
(`ux-design-detalhado.md` seção 2): wireframe isométrico de cubo clicável por face,
4 dropdowns de vértice filtrados pela face escolhida, validação com mensagens em
português (fonte única em `orientation_util`), e gravação de `BoxOrientationConfig`
via `service.save_orientation`.

Configura UMA câmera por visita (role vem em `on_show(role=...)`). Cada câmera vira
uma `CameraOrientation` guardada em `session.orientation_top/side`; quando ambas
estão completas, compõe o `BoxOrientationConfig` e persiste.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from src.app.gui.screen import ScreenBase
from src.app.orientation_util import (
    FACE_LABELS_PT,
    VERTEX_LABELS_PT,
    validate_selection,
    vertices_for_face,
)
from src.app.service import AppService
from src.core.schema.orientation import BoxFace, BoxVertex, CameraOrientation, CameraRole

_CORNER_LABELS = (
    "Ponto 1 (superior-direito)",
    "Ponto 2 (superior-esquerdo)",
    "Ponto 3 (inferior-direito)",
    "Ponto 4 (inferior-esquerdo)",
)

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


class OrientationScreen(ScreenBase):
    def __init__(self, service: AppService, show: Callable[..., None]) -> None:
        self.service = service
        self.show = show
        self.frame: tk.Frame
        self.role: str = "top"
        self._face: BoxFace | None = None
        self._vertices: list[BoxVertex | None] = [None, None, None, None]

    # --- construção ------------------------------------------------------------
    def build(self, parent: tk.Misc) -> tk.Frame:
        self.frame = tk.Frame(parent)

        tk.Label(
            self.frame, text="Qual face da caixa esta câmera enxerga de frente?"
        ).grid(row=0, column=1, padx=10, pady=10)

        self.wireframe_canvas = tk.Canvas(self.frame, width=400, height=400)
        self.wireframe_canvas.grid(row=1, column=1, rowspan=6, padx=10, pady=10)
        self._draw_wireframe()

        self._face_label = ttk.Label(self.frame, text="Face selecionada: —")
        self._face_label.grid(row=7, column=1, padx=10, pady=5)

        self.face_var = tk.StringVar()
        self.face_combobox = ttk.Combobox(
            self.frame, textvariable=self.face_var, state="readonly",
            values=[FACE_LABELS_PT[f] for f in BoxFace],
        )
        self.face_combobox.grid(row=8, column=1, padx=10, pady=5)
        self.face_combobox.bind("<<ComboboxSelected>>", self._on_face_combobox)

        self._corner_vars: list[tk.StringVar] = []
        self._corner_comboboxes: list[ttk.Combobox] = []
        for i, label in enumerate(_CORNER_LABELS):
            tk.Label(self.frame, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")
            var = tk.StringVar()
            combo = ttk.Combobox(self.frame, textvariable=var, state="disabled")
            combo.grid(row=i, column=0, padx=10, pady=5, sticky="w")
            combo.bind("<<ComboboxSelected>>", self._make_vertex_callback(i))
            self._corner_vars.append(var)
            self._corner_comboboxes.append(combo)

        self._error_label = ttk.Label(self.frame, text="", foreground="red")
        self._error_label.grid(row=5, column=0, padx=10, pady=5)

        ttk.Button(self.frame, text="Resetar orientação", command=self._reset).grid(
            row=9, column=0, padx=10, pady=10
        )
        ttk.Button(self.frame, text="Finalizar orientação", command=self._on_save).grid(
            row=9, column=1, padx=10, pady=10
        )
        ttk.Button(self.frame, text="Voltar", command=lambda: self.show("hub")).grid(
            row=9, column=2, padx=10, pady=10
        )
        return self.frame

    def _draw_wireframe(self) -> None:
        canvas = self.wireframe_canvas
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
        for vertex, (x, y) in _VERTEX_XY.items():
            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="black")
            canvas.create_text(x, y - 12, text=_VERTEX_ABBR[vertex], font=("TkDefaultFont", 8))
        canvas.create_text(
            200, 320,
            text="T = topo/B = base, F = frente/B = trás, L = esquerda/R = direita",
            font=("TkDefaultFont", 8),
        )

    def _make_vertex_callback(self, index: int) -> Callable[[object], None]:
        return lambda _event: self._on_vertex_combobox(index)

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

    # --- lógica de seleção (usada por widgets E testes) ------------------------
    def set_face(self, face: BoxFace) -> None:
        self._face = face
        self._vertices = [None, None, None, None]
        self.face_var.set(FACE_LABELS_PT[face])
        self._face_label.config(text=f"Face selecionada: {FACE_LABELS_PT[face]}")
        labels = [VERTEX_LABELS_PT[v] for v in vertices_for_face(face)]
        for var, combo in zip(self._corner_vars, self._corner_comboboxes, strict=True):
            var.set("")
            combo.config(values=labels, state="readonly")
        self._error_label.config(text="Face alterada — selecione novamente os vértices dos 4 pontos.")

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
            from src.app.orientation_util import MSG_VERTEX_DUPLICATE

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
        for var, combo in zip(self._corner_vars, self._corner_comboboxes, strict=True):
            var.set("")
            combo.config(values=[], state="disabled")
        self._error_label.config(text="")
