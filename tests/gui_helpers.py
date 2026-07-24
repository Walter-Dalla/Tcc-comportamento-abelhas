"""Helpers de teste da GUI (Fase 4): detecção de display Tk."""

from __future__ import annotations

import functools
import tkinter as tk


@functools.lru_cache(maxsize=1)
def has_display() -> bool:
    """True se um root Tk pode ser criado (há display disponível).

    Cacheado: criar/destruir vários `tk.Tk()` na mesma sessão pode falhar na 2ª
    criação em alguns ambientes, o que faria módulos coletados depois pularem por
    engano. Avaliamos uma única vez."""
    try:
        root = tk.Tk()
    except tk.TclError:
        return False
    root.destroy()
    return True
