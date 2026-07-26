"""Orquestração da pipeline de cálculo CPU (Fase 3).

Compõe os 5 estágios streaming (Capture → Rectify → Detect → Track → Fuse) num
`AnalysisResult`, e roda os plugins de metadata (`speed`, `border`) por cima.
É o papel que o `processVideoModule.py` legado tinha (agora apagado), mas
streaming e sem colapsar os estágios numa chamada bloqueante com o vídeo inteiro
em RAM.

O acoplamento real da fase (seção 3.4 do plano) mora aqui: o Detect recebe
Capture+Rectify concretos via construtor para a pré-passada do modelo de fundo.
O orquestrador reusa o MESMO objeto rectifier no Detect (passe 1) e na passada
pareada (passe 2), garantindo frames retificados byte-a-byte idênticos entre as
duas passadas.

Metadata: descoberto/ordenado via `PluginRegistry` (Fase 2) a partir de
`plugins/` na raiz do repo — respeita `border after speed`. `border` só roda se
houver `border_region` (pontos de borda configurados no perfil).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.pipeline import PipelineContext, RunRequest
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.schema.geometry import Point2D
from src.core.schema.orientation import CameraRole
from src.core.schema.profile import Profile
from src.core.schema.result import AnalysisContext, AnalysisResult
from src.core.stages import MetadataPlugin
from src.core.workspace import Workspace
from src.stages.capture.plugin import DualVideoFileCapture
from src.stages.detect.debug import DebugFrameWriter
from src.stages.detect.plugin import BackgroundSubtractionDetector
from src.stages.fuse.plugin import Fusion, build_border_region
from src.stages.rectify.plugin import CpuPerspectiveRectifier
from src.stages.track.multi.assignment import hungarian
from src.stages.track.multi.base import MultiEntityTracker

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PLUGINS_DIR = _REPO_ROOT / "plugins"


def _points_to_pixel_list(points: list[Point2D]) -> list[list[float]]:
    return [[p.x, p.y] for p in points]


def run_cpu_analysis(
    profile: Profile,
    *,
    run_metadata: bool = True,
    plugins_dir: Path | None = None,
    frame_block: int = 500,
    debug_dir: Path | None = None,
    overrides: dict[str, Any] | None = None,
    workspace: Workspace | None = None,
) -> AnalysisResult:
    """Roda a pipeline CPU completa sobre um perfil e devolve o `AnalysisResult`.

    Requer `profile.orientation` (a feature de Orientação é pré-requisito de dado
    desta fase; a UI que a popula é Fase 4).

    `debug_dir` liga o export de frames de debug do Detect (UX seção 6, Opção 2):
    máscaras de diferença amostradas + toda falha de detecção vão para
    `<debug_dir>/<view>/`, gravadas por uma thread própria que nunca segura o
    pipeline. `None` (padrão) = custo zero.

    `overrides`/`workspace` (opcionais) chegam até `plugin.setup(PipelineContext)`
    de cada plugin de metadata — mesmo contrato que `Pipeline.run` (Fase 2) já
    honra.
    """
    if profile.orientation is None:
        raise ValueError(
            f"perfil '{profile.name}' não tem orientation configurada — "
            "obrigatória para a pipeline da Fase 3 (axis_mapping)"
        )
    orientation = profile.orientation

    capture = DualVideoFileCapture(profile.top_video_path, profile.side_video_path)
    top_w, top_h = capture.dimensions(CameraRole.TOP)
    side_w, side_h = capture.dimensions(CameraRole.SIDE)

    rect_top = CpuPerspectiveRectifier(
        _points_to_pixel_list(profile.perspective_points_top),
        orientation,
        CameraRole.TOP,
        top_w,
        top_h,
    )
    rect_side = CpuPerspectiveRectifier(
        _points_to_pixel_list(profile.perspective_points_side),
        orientation,
        CameraRole.SIDE,
        side_w,
        side_h,
    )

    debug_writer = DebugFrameWriter(debug_dir) if debug_dir is not None else None
    det_top = BackgroundSubtractionDetector(
        capture, rect_top, CameraRole.TOP, frame_block, debug_writer
    )
    det_side = BackgroundSubtractionDetector(
        capture, rect_side, CameraRole.SIDE, frame_block, debug_writer
    )
    try:
        # passe 1 (modelo de fundo), por câmera, cada um lendo o vídeo inteiro da SUA view
        det_top.setup()
        det_side.setup()

        trk_top = MultiEntityTracker("top", hungarian)
        trk_side = MultiEntityTracker("side", hungarian)

        # passe 2 (pareado): streaming, O(1) frame por vez
        fps, frames = capture.open()
        for pair in frames:
            rt = rect_top.rectify(pair.top, pair.frame_index)
            rs = rect_side.rectify(pair.side, pair.frame_index)
            trk_top.update(det_top.detect(rt))
            trk_side.update(det_side.detect(rs))
    finally:
        if debug_writer is not None:
            debug_writer.close()

    top_track = trk_top.tracks()[0]
    side_track = trk_side.tracks()[0]

    routes, calibration = Fusion().fuse(
        top_track,
        side_track,
        orientation,
        profile.box_cm,
        float(fps),
        rect_top.output_shape,
        rect_side.output_shape,
    )

    border_region = None
    if profile.border_points_top and profile.border_points_side:
        border_region = build_border_region(
            orientation,
            profile.box_cm,
            profile.border_points_top,
            profile.border_points_side,
            rect_top.output_shape,
            rect_side.output_shape,
        )

    result = AnalysisResult(
        profile=profile.name,
        calibration=calibration,
        routes=routes,
        border_region=border_region,
    )

    if run_metadata:
        _run_metadata_plugins(
            result, plugins_dir or _DEFAULT_PLUGINS_DIR, overrides=overrides, workspace=workspace
        )

    return result


def _run_metadata_plugins(
    result: AnalysisResult,
    plugins_dir: Path,
    *,
    overrides: dict[str, Any] | None = None,
    workspace: Workspace | None = None,
) -> None:
    registry = PluginRegistry()
    registry.discover([plugins_dir])
    ctx = AnalysisContext(result=result)

    effective_workspace = workspace if workspace is not None else Workspace(root=Path("."))
    request = RunRequest(
        profile=result.profile, workspace=str(effective_workspace.root), overrides=overrides or {}
    )
    pctx = PipelineContext(request=request, registry=registry, workspace=effective_workspace)

    for plugin in registry.for_kind(PluginKind.METADATA):
        assert isinstance(plugin, MetadataPlugin)
        # border exige border_region; pula em silêncio quando ausente (perfil sem
        # pontos de borda) em vez de deixar o plugin levantar.
        if plugin.manifest.name == "border" and result.border_region is None:
            continue
        plugin.setup(pctx)
        try:
            plugin.run(ctx)
        finally:
            plugin.teardown()
