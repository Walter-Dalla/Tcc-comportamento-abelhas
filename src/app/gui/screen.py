"""Protocolo único de tela da GUI + mixin de marshalling (Fase 4.0).

Substitui o padrão inconsistente do legado (`startUp(videoPath)` disparado em
`threading.Thread(...).start()` de `mainUI.run_background_tasks`, tocando widgets
Tk direto na thread de fundo — o bug de thread-safety latente do ARCHITECTURE.md).

Regra de ouro para toda tela concreta: NENHUM método `tk`/`ttk` pode ser chamado
de dentro de código rodando em thread não-main. Trabalho pesado vai para
`run_async(work=...)`; toda mutação de widget acontece em `on_done`/`on_error`,
que `run_async` reagenda no main thread via `self.frame.after(0, ...)`.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from collections.abc import Callable
from typing import Protocol, TypeVar, runtime_checkable

logger = logging.getLogger("animaltrack.gui.screen")
T = TypeVar("T")


@runtime_checkable
class Screen(Protocol):
    """Contrato único para toda tela da GUI. Substitui o startUp(videoPath) ad-hoc."""

    frame: tk.Frame

    def build(self, parent: tk.Misc) -> tk.Frame:
        """Cria e retorna o tk.Frame da tela (chamado 1x, na montagem do MainWindow)."""
        ...

    def on_show(self, **kwargs: object) -> None:
        """Chamado toda vez que a tela é exibida. Recebe kwargs nomeados
        (ex. on_show(video_path=...)). Nunca bloquear o main thread aqui —
        disparar trabalho pesado via self.run_async."""
        ...

    def on_hide(self) -> None:
        """Chamado ao sair da tela (libera captura de vídeo, cancela polling, etc)."""
        ...

    def teardown(self) -> None:
        """Chamado 1x no shutdown do app inteiro."""
        ...


class ScreenBase:
    """Mixin concreto com o helper de marshalling. Toda tela concreta herda disso."""

    frame: tk.Frame

    def run_async(
        self,
        work: Callable[[], T],
        on_done: Callable[[T], object],
        on_error: Callable[[Exception], object] | None = None,
    ) -> threading.Thread:
        """Roda `work` numa thread daemon; `on_done`/`on_error` SEMPRE executam no
        main thread do Tk, via `self.frame.after(0, ...)`. Nenhum código de tela
        deve chamar métodos Tk fora de on_done/on_error/on_show/on_hide."""

        def _worker() -> None:
            try:
                result = work()
            except Exception as exc:  # intencional: converte em callback marshalled, nunca silencioso
                logger.exception("Falha em run_async de %s", type(self).__name__)
                if on_error is not None:
                    self.frame.after(0, on_error, exc)
                return
            self.frame.after(0, on_done, result)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread

    # Defaults no-op do ciclo de vida: MainWindow.show() chama on_hide() em TODA
    # tela a cada troca e teardown() em todas no shutdown. Sem estes no-ops, o
    # dispatcher quebraria com AttributeError na 1ª troca de tela para telas que
    # só definem build/on_show. build() continua obrigatório em cada tela.
    def on_show(self, **kwargs: object) -> None: ...

    def on_hide(self) -> None: ...

    def teardown(self) -> None: ...
