"""Testes dos plugins de export (Fase 4, workstream B)."""

from __future__ import annotations

from pathlib import Path

from src.app.plugins import EXPORT_PLUGINS_DIR
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.schema.geometry import Point3D
from src.core.schema.orientation import Calibration
from src.core.schema.result import AnalysisContext, AnalysisResult, Metric
from src.core.schema.route import Route3D
from src.core.workspace import Workspace
from src.stages.export.pdf.template import render_html
from src.stages.export.plot.plugin import route_segments
from tests.fixtures.golden_config import golden_orientation


def _calibration() -> Calibration:
    return Calibration(
        box_cm=Point3D(x=16.0, y=12.0, z=12.0),
        px_per_cm=Point3D(x=20.0, y=20.0, z=20.0),
        fps=30.0,
        orientation=golden_orientation(),
    )


def _context(*, with_border_metrics: bool = True, points=None) -> AnalysisContext:
    route = Route3D(entity_id=0, points=points or {0: Point3D(x=1.0, y=2.0, z=3.0)})
    result = AnalysisResult(profile="fixture01", calibration=_calibration(), routes=[route])
    ctx = AnalysisContext(result=result)
    if with_border_metrics:
        for axis in ("x", "y", "z"):
            ctx.add_metric(Metric(name=f"time_border_{axis}", value=5, producer="border"))
    return ctx


def test_pdf_render_html_missing_border_metrics_shows_placeholder() -> None:
    ctx = _context(with_border_metrics=False)
    html = render_html(ctx, "fixture01")
    assert html.count("N/D") == 3  # 3 tempos de borda ausentes


def test_pdf_render_html_includes_per_axis_px_per_cm() -> None:
    html = render_html(_context(), "fixture01")
    assert "Razão px/cm (X)" in html
    assert "Razão px/cm (Y)" in html
    assert "Razão px/cm (Z)" in html


def test_pdf_exporter_writes_file(tmp_path: Path) -> None:
    registry = PluginRegistry()
    registry.discover([EXPORT_PLUGINS_DIR])
    exporter = registry.get(PluginKind.EXPORTER, "pdf-report")
    ws = Workspace(root=tmp_path)
    out = exporter.export(_context(), ws)  # type: ignore[attr-defined]
    assert out.exists()
    assert out.name == "report.pdf"


def test_plot_exporter_breaks_segments_on_missing_frame_index() -> None:
    points = {
        0: Point3D(x=0.0, y=0.0, z=0.0),
        1: Point3D(x=1.0, y=1.0, z=1.0),
        # buraco no índice 2 (oclusão)
        3: Point3D(x=3.0, y=3.0, z=3.0),
        4: Point3D(x=4.0, y=4.0, z=4.0),
    }
    route = Route3D(entity_id=0, points=points)
    segments = route_segments(route)
    assert len(segments) == 2
    assert len(segments[0]) == 2
    assert len(segments[1]) == 2


def test_plot_exporter_writes_file(tmp_path: Path) -> None:
    registry = PluginRegistry()
    registry.discover([EXPORT_PLUGINS_DIR])
    exporter = registry.get(PluginKind.EXPORTER, "route-plot")
    ws = Workspace(root=tmp_path)
    out = exporter.export(_context(), ws)  # type: ignore[attr-defined]
    assert out.exists()
    assert out.name == "route.png"


def test_export_plugin_manifests_discovered_as_exporter_kind() -> None:
    registry = PluginRegistry()
    registry.discover([EXPORT_PLUGINS_DIR])
    names = {m.name for m in registry.manifests(PluginKind.EXPORTER)}
    assert names == {"route-plot", "pdf-report"}
