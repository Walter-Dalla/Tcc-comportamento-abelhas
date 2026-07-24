"""Prova de que as telas nunca tocam Tk fora do main thread (Fase 4, workstream C).

Substitui `PerspectiveScreen.frame` por um dublê cujo `.after(delay, fn, *a)` chama
`fn` imediatamente marcando um flag `in_after`; espia `load_image_on_ui_from_cv2`
para garantir que toda mutação de widget só ocorre durante a chamada de `.after`
(main thread), nunca dentro do `work` da thread de fundo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.app.gui.screens.perspective import PerspectiveScreen
from src.app.service import AppService
from src.core.workspace import Workspace
from tests.fixtures.golden_config import VIDEOS_DIR

pytestmark = pytest.mark.skipif(
    not (VIDEOS_DIR / "main_top.avi").exists(), reason="vídeos de fixture ausentes"
)


class _DummyFrame:
    def __init__(self) -> None:
        self.in_after = False

    def after(self, _delay, fn, *args):
        self.in_after = True
        try:
            fn(*args)
        finally:
            self.in_after = False


def test_perspective_screen_never_touches_tk_off_main_thread(tmp_path: Path) -> None:
    ws = Workspace(root=tmp_path)
    ws.ensure_dirs()
    screen = PerspectiveScreen(AppService(ws), role="top", show=lambda *a, **k: None)
    dummy = _DummyFrame()
    screen.frame = dummy  # type: ignore[assignment]

    mutations_off_main: list[str] = []

    def spy_load(_frame) -> None:
        if not dummy.in_after:
            mutations_off_main.append("load_image_on_ui_from_cv2")

    screen.load_image_on_ui_from_cv2 = spy_load  # type: ignore[method-assign,assignment]

    screen.on_show(video_path=str(VIDEOS_DIR / "main_top.avi"))
    screen._load_thread.join(timeout=3)

    assert mutations_off_main == []  # nenhuma mutação de widget fora de after()
