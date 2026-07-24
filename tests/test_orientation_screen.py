"""Testes da OrientationScreen e do helper de orientação (Fase 4, workstream D)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from src.app.orientation_util import (
    MSG_VERTEX_DUPLICATE,
    validate_selection,
    vertices_for_face,
)
from src.app.service import AppService
from src.core.schema.orientation import BoxFace, BoxOrientationConfig
from src.core.workspace import Workspace
from tests.fixtures.golden_config import golden_orientation
from tests.gui_helpers import has_display


# --- helper puro (sem Tk) -------------------------------------------------------
def test_vertices_for_face_returns_4_distinct_vertices_per_face() -> None:
    for face in BoxFace:
        vertices = vertices_for_face(face)
        assert len(vertices) == 4
        assert len(set(vertices)) == 4


def test_validate_selection_rejects_duplicate_vertex() -> None:
    from src.core.schema.orientation import BoxVertex

    face = BoxFace.TOP
    verts = vertices_for_face(face)
    # duplica o primeiro vértice na 2ª posição
    selection: list[BoxVertex | None] = [verts[0], verts[0], verts[2], verts[3]]
    assert validate_selection(face, selection) == MSG_VERTEX_DUPLICATE


# --- tela (precisa de display) --------------------------------------------------
gui = pytest.mark.skipif(not has_display(), reason="precisa de display Tk")


def _service(tmp_path: Path) -> AppService:
    ws = Workspace(root=tmp_path)
    ws.ensure_dirs()
    return AppService(ws)


@gui
def test_save_orientation_rejects_duplicate_vertex_assignment(
    tmp_path: Path, tk_root: tk.Tk
) -> None:
    from src.app.gui.screens.orientation import OrientationScreen

    container = tk.Frame(tk_root)
    try:
        screen = OrientationScreen(_service(tmp_path), show=lambda *a, **k: None)
        screen.frame = screen.build(container)
        verts = vertices_for_face(BoxFace.TOP)
        screen._face = BoxFace.TOP
        screen._vertices = [verts[0], verts[0], verts[2], verts[3]]  # duplicado
        error = screen._on_save()
        assert error == MSG_VERTEX_DUPLICATE
    finally:
        container.destroy()


@gui
def test_save_orientation_writes_profile_config(
    tmp_path: Path, tk_root: tk.Tk, monkeypatch
) -> None:
    from src.app.gui.screens.orientation import OrientationScreen

    container = tk.Frame(tk_root)
    try:
        service = _service(tmp_path)
        received: list[BoxOrientationConfig] = []
        monkeypatch.setattr(
            service, "save_orientation", lambda name, cfg: received.append(cfg)
        )
        # a câmera lateral já está configurada na sessão:
        service.session.orientation_side = golden_orientation().side_camera
        service.session.profile_name = "fixture01"

        screen = OrientationScreen(service, show=lambda *a, **k: None)
        screen.frame = screen.build(container)
        screen.on_show(role="top")

        top_face = golden_orientation().top_camera.face_viewed
        top_verts = list(golden_orientation().top_camera.corner_vertices)
        screen.set_face(top_face)
        for i, vertex in enumerate(top_verts):
            screen.set_vertex(i, vertex)

        error = screen._on_save()
        assert error is None
        assert len(received) == 1
        assert received[0].top_camera.face_viewed == top_face
        assert list(received[0].top_camera.corner_vertices) == top_verts
    finally:
        container.destroy()
