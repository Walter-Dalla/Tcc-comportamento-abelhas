"""Resolução dos diretórios de busca de plugin (Fase 4).

Centraliza, num único lugar Tk-free consumido por CLI e GUI, quais diretórios o
`PluginRegistry.discover()` deve varrer:

- `plugins/` na raiz do repo — plugins de metadata built-in (`speed`, `border`).
- `src/stages/export/` — plugins `exporter` built-in (`route-plot`, `pdf-report`).
- `<workspace>/plugins/` — plugins instalados pelo usuário no workspace.

Espelha o `_DEFAULT_PLUGINS_DIR` de `src/stages/orchestration.py` (raiz/plugins)
e adiciona o diretório de exporters da Fase 4, mantendo uma só fonte de verdade.
"""

from __future__ import annotations

from pathlib import Path

from src.core.workspace import Workspace

_REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_PLUGINS_DIR = _REPO_ROOT / "plugins"
EXPORT_PLUGINS_DIR = _REPO_ROOT / "src" / "stages" / "export"


def default_search_paths(workspace: Workspace | None = None) -> list[Path]:
    """Diretórios de busca de plugin, do built-in ao específico do workspace."""
    paths = [METADATA_PLUGINS_DIR, EXPORT_PLUGINS_DIR]
    if workspace is not None:
        paths.append(workspace.plugins)
    return paths
