"""Fixtures compartilhadas dos testes da Fase 2 (plugin/pipeline/plugins).

Helpers para (a) montar `AnalysisResult`/`Calibration` válidos sem repetir o
boilerplate de orientação, (b) escrever diretórios de plugin em disco
(`plugin.toml` + `plugin.py`) para os testes de descoberta/ordenação, e (c)
persistir um `AnalysisResult` num workspace temporário via `ResultStore`.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

from src.core.plugin import Plugin, PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.schema.geometry import Point3D
from src.core.schema.orientation import (
    BoxFace,
    BoxOrientationConfig,
    BoxVertex,
    Calibration,
    CameraOrientation,
    CameraRole,
)
from src.core.schema.result import AnalysisResult, BorderRegion
from src.core.schema.route import Route3D
from src.core.store import ResultStore
from src.core.workspace import Workspace

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"


def make_calibration(px_per_cm: Point3D | None = None) -> Calibration:
    top = CameraOrientation(
        role=CameraRole.TOP,
        face_viewed=BoxFace.TOP,
        corner_vertices=[
            BoxVertex.TOP_FRONT_RIGHT,
            BoxVertex.TOP_FRONT_LEFT,
            BoxVertex.TOP_BACK_RIGHT,
            BoxVertex.TOP_BACK_LEFT,
        ],
    )
    side = CameraOrientation(
        role=CameraRole.SIDE,
        face_viewed=BoxFace.FRONT,
        corner_vertices=[
            BoxVertex.TOP_FRONT_RIGHT,
            BoxVertex.TOP_FRONT_LEFT,
            BoxVertex.BOTTOM_FRONT_RIGHT,
            BoxVertex.BOTTOM_FRONT_LEFT,
        ],
    )
    return Calibration(
        box_cm=Point3D(x=10.0, y=20.0, z=30.0),
        px_per_cm=px_per_cm or Point3D(x=5.0, y=5.0, z=5.0),
        fps=30.0,
        orientation=BoxOrientationConfig(top_camera=top, side_camera=side),
    )


def make_result(
    *,
    profile: str = "fixture",
    points: dict[int, Point3D] | None = None,
    px_per_cm: Point3D | None = None,
    border_region: BorderRegion | None = None,
) -> AnalysisResult:
    if points is None:
        points = {
            0: Point3D(x=0.0, y=0.0, z=0.0),
            1: Point3D(x=3.0, y=4.0, z=0.0),
            2: Point3D(x=3.0, y=4.0, z=12.0),
        }
    return AnalysisResult(
        profile=profile,
        calibration=make_calibration(px_per_cm),
        routes=[Route3D(entity_id=0, points=points)],
        border_region=border_region,
    )


@pytest.fixture
def calibration() -> Calibration:
    return make_calibration()


@pytest.fixture
def analysis_result() -> AnalysisResult:
    return make_result()


@pytest.fixture
def result_factory() -> Callable[..., AnalysisResult]:
    """Devolve o construtor `make_result` para testes que precisam variar pontos/bounds."""
    return make_result


@pytest.fixture
def plugins_dir() -> Path:
    """Diretório real dos plugins portados (`plugins/` na raiz do repo)."""
    return PLUGINS_DIR


@pytest.fixture
def load_plugin() -> Callable[..., Plugin]:
    """Carrega um plugin real de `plugins/` via PluginRegistry (com validação/import)."""

    def _load(name: str, kind: PluginKind = PluginKind.METADATA) -> Plugin:
        registry = PluginRegistry()
        registry.discover([PLUGINS_DIR])
        return registry.get(kind, name)

    return _load


@pytest.fixture
def saved_workspace(tmp_path: Path) -> Callable[[AnalysisResult], Workspace]:
    """Retorna uma função que persiste um AnalysisResult num workspace temporário."""

    def _save(result: AnalysisResult) -> Workspace:
        ws = Workspace(root=tmp_path / "ws")
        ResultStore(ws).save(result)
        return ws

    return _save


_DEFAULT_PLUGIN_SRC = textwrap.dedent(
    """\
    from src.core.stages import MetadataPlugin


    class P(MetadataPlugin):
        def run(self, ctx):
            return None
    """
)


@pytest.fixture
def make_plugin() -> Callable[..., Path]:
    """Fixture-fábrica: escreve `<root>/<name>/{plugin.toml,plugin.py}` e devolve o dir do plugin."""

    def _make(
        root: Path,
        name: str,
        *,
        kind: str = "metadata",
        entry: str = "plugin:P",
        api_version: str = "1.0",
        schema: str = ">=1.0,<2.0",
        before: list[str] | None = None,
        after: list[str] | None = None,
        priority: int = 0,
        plugin_src: str = _DEFAULT_PLUGIN_SRC,
    ) -> Path:
        before = before or []
        after = after or []
        plugin_dir = root / name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        toml = textwrap.dedent(
            f"""\
            [plugin]
            name        = "{name}"
            version     = "1.0.0"
            kind        = "{kind}"
            entry       = "{entry}"
            api_version = "{api_version}"
            schema      = "{schema}"

            [ordering]
            before = {before!r}
            after  = {after!r}
            priority = {priority}
            """
        )
        (plugin_dir / "plugin.toml").write_text(toml, encoding="utf-8")
        (plugin_dir / "plugin.py").write_text(plugin_src, encoding="utf-8")
        return plugin_dir

    return _make
