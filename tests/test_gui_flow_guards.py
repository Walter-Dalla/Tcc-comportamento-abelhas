"""Guardas de pré-condição e ordem de fluxo das telas (auditoria de UX).

Cobre `docs/plans/ux-design-detalhado.md` seção 1.2:
- "Processar vídeo" exige vídeo + 4 pontos de perspectiva por câmera + orientação
  válida das DUAS câmeras (mensagens telegráficas do legado / da seção 1.2).
- "Finalizar perspectiva" oferece o próximo passo lógico (orientação da mesma
  câmera), sem forçar — "Depois" volta ao hub como antes.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path

import pytest

from src.app.orientation_util import MSG_ORIENTATION_MISSING
from src.app.service import AppService, SessionState
from src.core.workspace import Workspace
from tests.fixtures.golden_config import golden_orientation
from tests.gui_helpers import has_display

pytestmark = pytest.mark.skipif(not has_display(), reason="precisa de display Tk")


def _service(tmp_path: Path) -> AppService:
    ws = Workspace(root=tmp_path)
    ws.ensure_dirs()
    return AppService(ws)


def _fill_session(service: AppService, *, orientation: bool) -> None:
    session = service.session
    session.profile_name = "fixture01"
    session.top_video_path = "top.avi"
    session.side_video_path = "side.avi"
    session.perspective_points_top = [[0, 0], [10, 0], [0, 10], [10, 10]]
    session.perspective_points_side = [[0, 0], [10, 0], [0, 10], [10, 10]]
    if orientation:
        config = golden_orientation()
        session.orientation_top = config.top_camera
        session.orientation_side = config.side_camera


def _hub(service: AppService, container: tk.Frame):  # type: ignore[no-untyped-def]
    from src.app.gui.screens.config_hub import ConfigHubScreen

    hub = ConfigHubScreen(service, show=lambda *a, **k: None)
    hub.frame = hub.build(container)
    return hub


# --- guardas de "Processar vídeo" ------------------------------------------------
def _break_video(session: SessionState) -> None:
    session.top_video_path = ""


def _break_perspective(session: SessionState) -> None:
    session.perspective_points_top = [[0, 0]]


def _break_orientation(session: SessionState) -> None:
    session.orientation_top = None
    session.orientation_side = None


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (_break_video, "Video não configurado."),
        (_break_perspective, "Bordas não configuradas."),
        (_break_orientation, MSG_ORIENTATION_MISSING),
    ],
)
def test_processing_guard_messages(
    tmp_path: Path,
    tk_root: tk.Tk,
    mutate: Callable[[SessionState], None],
    expected: str,
) -> None:
    container = tk.Frame(tk_root)
    try:
        service = _service(tmp_path)
        _fill_session(service, orientation=True)
        mutate(service.session)
        assert _hub(service, container)._processing_error() == expected
    finally:
        container.destroy()


def test_processing_guard_passes_when_fully_configured(
    tmp_path: Path, tk_root: tk.Tk
) -> None:
    container = tk.Frame(tk_root)
    try:
        service = _service(tmp_path)
        _fill_session(service, orientation=True)
        assert _hub(service, container)._processing_error() is None
    finally:
        container.destroy()


def test_process_video_blocked_without_orientation(
    tmp_path: Path, tk_root: tk.Tk, monkeypatch
) -> None:
    from src.app.gui.screens import config_hub

    container = tk.Frame(tk_root)
    try:
        service = _service(tmp_path)
        _fill_session(service, orientation=False)
        shown: list[str] = []
        monkeypatch.setattr(
            config_hub.messagebox, "showerror", lambda _t, msg, **k: shown.append(msg)
        )

        def _boom(*_a: object, **_k: object) -> object:
            raise AssertionError("run_pipeline não pode ser chamado sem orientação")

        monkeypatch.setattr(service, "run_pipeline", _boom)
        assert _hub(service, container)._on_process_video() is None
        assert shown == [MSG_ORIENTATION_MISSING]
    finally:
        container.destroy()


# --- botão "Executar módulos de metadados" (fluxo 1.1/1.2 do hub) ----------------
def test_hub_metadata_button_delegates_to_service(
    tmp_path: Path, tk_root: tk.Tk, monkeypatch
) -> None:
    from src.app.gui.screens import config_hub

    container = tk.Frame(tk_root)
    try:
        service = _service(tmp_path)
        service.session.profile_name = "fixture01"
        calls: list[str] = []
        monkeypatch.setattr(service, "run_metadata", lambda profile: calls.append(profile))
        monkeypatch.setattr(config_hub.messagebox, "showinfo", lambda *a, **k: tk_root.quit())
        monkeypatch.setattr(config_hub.messagebox, "showerror", lambda *a, **k: tk_root.quit())

        thread = _hub(service, container)._on_process_metadata()
        assert thread is not None
        # deixa o after(0, on_done) do run_async rodar no main thread (mesmo padrão
        # do smoke test); sem mainloop, o marshalling levantaria "main thread is not
        # in main loop".
        tk_root.after(3000, tk_root.quit)  # timeout de segurança
        tk_root.mainloop()
        assert calls == ["fixture01"]
    finally:
        container.destroy()


# --- auto-avanço perspectiva -> orientação (seção 1.2) ---------------------------
@pytest.mark.parametrize(
    ("answer", "expected_screen"), [(True, "orientation"), (False, "hub")]
)
def test_finish_perspective_offers_orientation(
    tmp_path: Path, tk_root: tk.Tk, monkeypatch, answer: bool, expected_screen: str
) -> None:
    from src.app.gui.screens import perspective as perspective_module

    container = tk.Frame(tk_root)
    try:
        navigated: list[tuple[str, dict[str, object]]] = []
        screen = perspective_module.PerspectiveScreen(
            _service(tmp_path),
            role="side",
            show=lambda name, **kwargs: navigated.append((name, kwargs)),
        )
        screen.frame = screen.build(container)
        screen._video_path = "side.avi"
        monkeypatch.setattr(perspective_module.messagebox, "askyesno", lambda *a, **k: answer)

        screen._finish()

        assert navigated[0][0] == expected_screen
        if answer:
            assert navigated[0][1] == {"role": "side", "video_path": "side.avi"}
    finally:
        container.destroy()
