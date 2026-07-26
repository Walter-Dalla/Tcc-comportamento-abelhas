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


# --- wireframe clicável por face (UX 2.2 / 2.3) --------------------------------
def test_face_polygon_vertices_match_validation_helper() -> None:
    """O polígono desenhado de cada face tem exatamente os 4 vértices que o
    helper de validação considera daquela face (senão o wireframe mentiria)."""
    from src.app.gui.screens.orientation import _FACE_VERTICES

    for face in BoxFace:
        drawn = _FACE_VERTICES[face]
        assert len(drawn) == 4
        assert set(drawn) == set(vertices_for_face(face))


def test_face_patches_do_not_fully_overlap() -> None:
    """Cada face tem um adesivo clicável próprio, com centroides distintos —
    garante que existe área exclusiva por face na projeção isométrica."""
    from src.app.gui.screens.orientation import _patch_coords

    centroids = set()
    for face in BoxFace:
        coords = _patch_coords(face)
        assert len(coords) == 8  # 4 pontos (x, y)
        cx = sum(coords[0::2]) / 4
        cy = sum(coords[1::2]) / 4
        centroids.add((round(cx, 3), round(cy, 3)))
    assert len(centroids) == 6


@gui
def test_every_face_has_a_clickable_polygon(tmp_path: Path, tk_root: tk.Tk) -> None:
    from src.app.gui.screens.orientation import OrientationScreen, face_tag

    container = tk.Frame(tk_root)
    try:
        screen = OrientationScreen(_service(tmp_path), show=lambda *a, **k: None)
        screen.frame = screen.build(container)
        canvas = screen.wireframe_canvas
        for face in BoxFace:
            tag = face_tag(face)
            assert canvas.find_withtag(tag), f"sem polígono para a face {face.value}"
            assert "<Button-1>" in canvas.tag_bind(tag)
    finally:
        container.destroy()


@gui
def test_clicking_face_polygon_selects_face_and_enables_comboboxes(
    tmp_path: Path, tk_root: tk.Tk
) -> None:
    from src.app.gui.screens.orientation import OrientationScreen

    container = tk.Frame(tk_root)
    try:
        screen = OrientationScreen(_service(tmp_path), show=lambda *a, **k: None)
        screen.frame = screen.build(container)
        # comboboxes começam desabilitados com placeholder (UX 2.4)
        assert all(str(c["state"]) == "disabled" for c in screen._corner_comboboxes)
        assert all(v.get() == "Escolha a face primeiro" for v in screen._corner_vars)

        # o handler ligado ao polígono da face é o mesmo caminho do clique real
        screen._make_face_callback(BoxFace.FRONT)(None)

        assert screen._face is BoxFace.FRONT
        assert screen._face_label.cget("text") == "Face selecionada: Frente"
        for combo in screen._corner_comboboxes:
            assert str(combo["state"]) == "readonly"
            assert len(combo["values"]) == 4
    finally:
        container.destroy()


@gui
def test_face_change_warning_only_after_a_real_change(
    tmp_path: Path, tk_root: tk.Tk
) -> None:
    from src.app.gui.screens.orientation import OrientationScreen

    container = tk.Frame(tk_root)
    try:
        screen = OrientationScreen(_service(tmp_path), show=lambda *a, **k: None)
        screen.frame = screen.build(container)

        screen.set_face(BoxFace.TOP)  # 1ª escolha: nada foi resetado -> sem aviso
        assert screen._error_label.cget("text") == ""

        screen.set_vertex(0, vertices_for_face(BoxFace.TOP)[0])
        screen.set_face(BoxFace.FRONT)  # troca com seleção prévia -> avisa
        assert "Face alterada" in screen._error_label.cget("text")
        assert screen._vertices == [None, None, None, None]
    finally:
        container.destroy()


# --- miniatura com os 4 pontos numerados (UX 2.1) -------------------------------
def test_build_thumbnail_draws_points_and_fits_the_box() -> None:
    import numpy as np

    from src.app.gui.screens.orientation import build_thumbnail

    frame = np.zeros((800, 600, 3), dtype=np.uint8)
    points = [[10, 20], [500, 20], [10, 700], [500, 700]]
    image = build_thumbnail(frame, points)
    assert max(image.size) <= 320
    # os marcadores azuis foram desenhados sobre o frame preto
    assert np.asarray(image)[..., 2].max() > 100


def test_build_thumbnail_without_points_does_not_fail() -> None:
    import numpy as np

    from src.app.gui.screens.orientation import build_thumbnail

    image = build_thumbnail(np.zeros((40, 40, 3), dtype=np.uint8), [])
    assert image.size == (40, 40)


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
