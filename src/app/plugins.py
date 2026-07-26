"""Resolução dos diretórios de busca de plugin (Fase 4).

Centraliza, num único lugar Tk-free consumido por CLI e GUI, quais diretórios o
`PluginRegistry.discover()` deve varrer:

- `plugins/` na raiz do repo — plugins de metadata built-in (`speed`, `border`).
- `src/stages/export/` — plugins `exporter` built-in (`route-plot`, `pdf-report`).
- `plugins/tracker/` — plugins `tracker` do spike multi-animal (Fase 6).
- `plugins/metadata/` — plugins `metadata` de exemplo/referência (Fase 6).
- `<workspace>/plugins/` — plugins instalados pelo usuário no workspace
  (`animaltrack plugin install`).

Espelha o `_DEFAULT_PLUGINS_DIR` de `src/stages/orchestration.py` (raiz/plugins)
e adiciona o diretório de exporters da Fase 4, mantendo uma só fonte de verdade.

Nota (Fase 6): `PluginRegistry.discover()` varre UM nível (`<root>/<nome>/plugin.toml`).
Por isso subpastas de agrupamento como `plugins/tracker/` e `plugins/metadata/`
precisam entrar como raízes de busca próprias — não são alcançadas pela varredura
de `plugins/`. Ver `docs/PLUGIN_CONTRACT.md`, seção de convenção de diretório.
"""

from __future__ import annotations

from pathlib import Path

from src.core.workspace import Workspace

_REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_PLUGINS_DIR = _REPO_ROOT / "plugins"
EXPORT_PLUGINS_DIR = _REPO_ROOT / "src" / "stages" / "export"
TRACKER_PLUGINS_DIR = _REPO_ROOT / "plugins" / "tracker"
EXAMPLE_METADATA_PLUGINS_DIR = _REPO_ROOT / "plugins" / "metadata"


def default_search_paths(workspace: Workspace | None = None) -> list[Path]:
    """Diretórios de busca de plugin, do built-in ao específico do workspace."""
    paths = [
        METADATA_PLUGINS_DIR,
        EXPORT_PLUGINS_DIR,
        TRACKER_PLUGINS_DIR,
        EXAMPLE_METADATA_PLUGINS_DIR,
    ]
    if workspace is not None:
        paths.append(workspace.plugins)
    return paths


def metadata_search_paths(workspace: Workspace | None = None) -> list[Path]:
    """Subconjunto usado por "Executar módulos de metadados" (`Pipeline.run`).

    Deliberadamente MAIS estreito que `default_search_paths`: só os plugins de
    metadata built-in (`plugins/`) + os instalados pelo usuário no workspace. Os
    plugins de metadata de *exemplo* (`plugins/metadata/`, ex. `fish-body-fat`)
    ficam de fora para que a re-execução de metadata da GUI produza exatamente o
    mesmo conjunto de métricas que `run_cpu_analysis` (que só varre `plugins/`) —
    caso contrário reprocessar metadata mudaria o resultado de um run completo.
    """
    paths = [METADATA_PLUGINS_DIR]
    if workspace is not None:
        paths.append(workspace.plugins)
    return paths
