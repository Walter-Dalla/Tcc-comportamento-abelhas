"""GUI Tkinter (Fase 4). `main()` cria o root, monta o MainWindow e roda o mainloop."""

from __future__ import annotations

import tkinter as tk

from src.app.gui.main_window import MainWindow
from src.app.service import AppService
from src.core.workspace import Workspace


def main() -> None:
    root = tk.Tk()
    root.title("Ferramenta para a analise comportamental de insetos")

    window_width, window_height = 800, 800
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = int((screen_width / 2) - (window_width / 2))
    y = int((screen_height / 2) - (window_height / 2))
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    workspace = Workspace.resolve(None)
    workspace.ensure_dirs()
    service = AppService(workspace)
    MainWindow(root, service)
    root.mainloop()
