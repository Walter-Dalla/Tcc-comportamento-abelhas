"""Abre uma pasta no explorador de arquivos do SO (Tk-free, não bloqueante).

Usado pelo botão "Abrir pasta de debug" do hub — a metade "GUI" da Opção 2 da
seção 6 do `docs/plans/ux-design-detalhado.md`. Nunca bloqueia a main thread do
Tk: `os.startfile` (Windows) retorna imediatamente e os equivalentes de
macOS/Linux vão por `subprocess.Popen` (sem `wait`/`communicate`).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class OpenFolderError(RuntimeError):
    """Não foi possível pedir ao SO que abrisse a pasta."""


def open_folder(path: Path) -> None:
    """Abre `path` no explorador do SO, criando o diretório se ainda não existir.

    Criar é intencional: o usuário pode clicar antes de rodar qualquer análise com
    debug ligado — abrir uma pasta vazia comunica melhor que um erro.
    """
    path.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            startfile = getattr(os, "startfile", None)  # só existe no Windows
            if startfile is None:  # pragma: no cover - defensivo
                raise OpenFolderError("os.startfile indisponível nesta plataforma")
            startfile(str(path))
            return
        command = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([command, str(path)])  # noqa: S603,S607 - caminho do próprio workspace
    except OSError as exc:
        raise OpenFolderError(f"não foi possível abrir {path}: {exc}") from exc
