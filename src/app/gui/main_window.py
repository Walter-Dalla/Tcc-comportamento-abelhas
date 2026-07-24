"""MainWindow — dispatcher único de telas (Fase 4, workstream C).

Substitui o `run_background_tasks` + os `show*Frame` ad-hoc de `mainUI.py`. Todas as
telas são criadas 1x na montagem, empilhadas no mesmo grid, e trocadas por um único
`show(name, **kwargs)` que chama `on_hide()` em todas e `on_show(**kwargs)` na alvo —
inclusive `record_webcam`, que no legado era a exceção que quebrava o padrão.
"""

from __future__ import annotations

import tkinter as tk

from src.app.gui.screen import Screen
from src.app.gui.screens.border import BorderScreen
from src.app.gui.screens.config_hub import ConfigHubScreen
from src.app.gui.screens.orientation import OrientationScreen
from src.app.gui.screens.perspective import PerspectiveScreen
from src.app.gui.screens.record_webcam import RecordWebcamScreen
from src.app.service import AppService


class MainWindow:
    def __init__(self, root: tk.Tk, service: AppService) -> None:
        self.root = root
        self.service = service
        self.screens: dict[str, Screen] = {
            "hub": ConfigHubScreen(service, show=self.show),
            "perspective_top": PerspectiveScreen(service, role="top", show=self.show),
            "perspective_side": PerspectiveScreen(service, role="side", show=self.show),
            "border_top": BorderScreen(service, role="top", show=self.show),
            "border_side": BorderScreen(service, role="side", show=self.show),
            "record_webcam": RecordWebcamScreen(service, show=self.show),
            "orientation": OrientationScreen(service, show=self.show),
        }
        for screen in self.screens.values():
            screen.frame = screen.build(root)
            screen.frame.grid(row=0, column=0, sticky="nsew")
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.show("hub")

    def show(self, name: str, **kwargs: object) -> None:
        for screen in self.screens.values():
            screen.on_hide()
        target = self.screens[name]
        target.frame.tkraise()
        target.on_show(**kwargs)

    def _on_close(self) -> None:
        for screen in self.screens.values():
            screen.teardown()
        self.root.destroy()
