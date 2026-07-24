"""Launcher fino (Fase 4): despacha para a CLI (Typer) ou a GUI (Tkinter) por argv.

Se o 1º argumento for um comando reconhecido da CLI, despacha para `src.app.cli`
SEM nunca importar tkinter nesse caminho (garante o modo headless real). Sem
argumentos, abre a GUI. `src/app/cli.py` não importa `src/app/gui` (nem
transitivamente) — é isso que sustenta a promessa headless.
"""

from __future__ import annotations

import sys

CLI_COMMANDS = {"run", "list-plugins", "validate-config", "--help", "-h"}


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] in CLI_COMMANDS:
        from src.app.cli import app as cli_app

        cli_app()
        return 0

    from src.app.gui import main as gui_main

    gui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
