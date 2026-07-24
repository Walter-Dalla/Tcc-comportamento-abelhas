"""Plugin `route-plot` (kind=exporter) — porta `ExportModule/plotRoute.py`.

Renderiza a rota 3D fundida com matplotlib e salva um PNG (headless-safe: usa o
backend Agg e `fig.savefig`, NUNCA `plt.show()` — o exporter roda igual em CLI sem
display e na GUI).

Correção arrastada da migração de schema: o legado quebrava a linha em segmentos
comparando `x == -1` (sentinela numérica). O schema novo (`Route3D.points:
dict[int, Point3D]`) não usa sentinela — um buraco de índice no dict = oclusão.
`route_segments` detecta esses buracos e quebra a linha entre eles.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from src.core.plugin import Plugin, PluginManifest
from src.core.schema.result import AnalysisContext
from src.core.schema.route import Route3D
from src.core.workspace import Workspace

Segment = list[tuple[float, float, float]]


def route_segments(route: Route3D) -> list[Segment]:
    """Quebra a rota em segmentos contíguos: um salto no `frame_index` (buraco no
    dict = oclusão) encerra o segmento atual e começa outro."""
    segments: list[Segment] = []
    current: Segment = []
    prev_idx: int | None = None
    for idx in sorted(route.points):
        point = route.points[idx]
        if prev_idx is not None and idx != prev_idx + 1:
            if current:
                segments.append(current)
            current = []
        current.append((point.x, point.y, point.z))
        prev_idx = idx
    if current:
        segments.append(current)
    return segments


class PlotRouteExporter(Plugin):
    manifest: ClassVar[PluginManifest]

    def export(self, ctx: AnalysisContext, workspace: Workspace, **kwargs: object) -> Path:
        import matplotlib

        matplotlib.use("Agg")  # headless: nenhum display necessário
        import matplotlib.pyplot as plt

        result = ctx.result
        out = workspace.outputs / result.profile / "route.png"
        out.parent.mkdir(parents=True, exist_ok=True)

        fig = plt.figure()
        try:
            ax = fig.add_subplot(111, projection="3d")
            ax.set_title("Gráfico 3D do movimento do inseto")
            ax.set_xlabel("x")
            ax.set_ylabel("y")
            ax.set_zlabel("z")
            ax.set_box_aspect([1, 1, 1])

            if result.routes:
                for segment in route_segments(result.routes[0]):
                    if not segment:
                        continue
                    xs, ys, zs = zip(*segment, strict=True)
                    ax.plot(xs, ys, zs, "b-")
            ax.view_init(elev=45, azim=-135)
            fig.savefig(out, dpi=100)
        finally:
            plt.close(fig)
        return out
