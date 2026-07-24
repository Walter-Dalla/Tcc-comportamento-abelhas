"""Smoke test da GUI (Fase 4, workstream C)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from src.app.service import AppService
from src.core.workspace import Workspace
from tests.gui_helpers import has_display

pytestmark = pytest.mark.skipif(not has_display(), reason="precisa de display Tk")

_EXPECTED = {
    "hub",
    "perspective_top",
    "perspective_side",
    "border_top",
    "border_side",
    "record_webcam",
    "orientation",
}


def _service(tmp_path: Path) -> AppService:
    ws = Workspace(root=tmp_path)
    ws.ensure_dirs()
    return AppService(ws)


def test_main_window_builds_all_screens(tmp_path: Path, tk_root: tk.Tk) -> None:
    from src.app.gui.main_window import MainWindow

    container = tk.Toplevel(tk_root)
    try:
        window = MainWindow(container, _service(tmp_path))  # type: ignore[arg-type]
        assert set(window.screens) == _EXPECTED
    finally:
        container.destroy()


def test_hub_process_video_calls_same_pipeline_as_cli(
    tmp_path: Path, tk_root: tk.Tk, monkeypatch
) -> None:
    from src.app.gui.screens import config_hub

    container = tk.Frame(tk_root)
    try:
        service = _service(tmp_path)
        calls: list[str] = []

        def fake_run_pipeline(profile, on_progress=None, *, require_gpu=False):
            calls.append(profile)
            return object()

        monkeypatch.setattr(service, "run_pipeline", fake_run_pipeline)
        # o callback marshalled (on_done) chama showinfo — encerra o mainloop nele.
        monkeypatch.setattr(config_hub.messagebox, "showinfo", lambda *a, **k: tk_root.quit())
        monkeypatch.setattr(config_hub.messagebox, "showerror", lambda *a, **k: tk_root.quit())

        hub = config_hub.ConfigHubScreen(service, show=lambda *a, **k: None)
        hub.frame = hub.build(container)
        service.session.profile_name = "fixture01"

        thread = hub._on_process_video()
        assert thread is not None
        tk_root.after(3000, tk_root.quit)  # timeout de segurança
        tk_root.mainloop()  # deixa o after(0, on_done) do run_async rodar no main thread

        assert calls == ["fixture01"]
    finally:
        container.destroy()
