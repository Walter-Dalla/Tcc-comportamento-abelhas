"""Configuração compartilhada do golden-file test (Fase 3).

Define a orientação e o perfil usados tanto na geração do golden quanto no teste.
A orientação é escolhida de forma que `axis_mapping()` resolva x←top.U, y←top.V,
z←side.V — as MESMAS fontes que o hardcode legado (`route_module`) usava
(x=top.x, y=top.y, z=side.y) — validando que a generalização não regride o caso comum.
"""

from __future__ import annotations

from pathlib import Path

from src.core.schema.geometry import Point2D, Point3D
from src.core.schema.orientation import (
    BoxFace,
    BoxOrientationConfig,
    BoxVertex,
    CameraOrientation,
    CameraRole,
)
from src.core.schema.profile import Profile

VIDEOS_DIR = Path(__file__).resolve().parent / "videos"

# box_cm escolhido pra dar px_per_cm = 20 em todos os eixos com frame 320x240:
#   x: top width 320 / 16 = 20 ; y: top height 240 / 12 = 20 ; z: side height 240 / 12 = 20
BOX_CM = Point3D(x=16.0, y=12.0, z=12.0)


def golden_orientation() -> BoxOrientationConfig:
    top = CameraOrientation(
        role=CameraRole.TOP,
        face_viewed=BoxFace.FRONT,
        corner_vertices=[
            BoxVertex.TOP_FRONT_RIGHT,
            BoxVertex.TOP_FRONT_LEFT,
            BoxVertex.BOTTOM_FRONT_RIGHT,
            BoxVertex.BOTTOM_FRONT_LEFT,
        ],
    )
    side = CameraOrientation(
        role=CameraRole.SIDE,
        face_viewed=BoxFace.TOP,
        corner_vertices=[
            BoxVertex.TOP_BACK_RIGHT,
            BoxVertex.TOP_BACK_LEFT,
            BoxVertex.TOP_FRONT_RIGHT,
            BoxVertex.TOP_FRONT_LEFT,
        ],
    )
    return BoxOrientationConfig(top_camera=top, side_camera=side)


def _border_rect(x0: float, y0: float, x1: float, y1: float) -> list[Point2D]:
    return [Point2D(x=x0, y=y0), Point2D(x=x1, y=y0), Point2D(x=x0, y=y1), Point2D(x=x1, y=y1)]


def golden_profile(name: str = "golden", *, top: str = "main_top.avi",
                   side: str = "main_side.avi") -> Profile:
    return Profile(
        name=name,
        top_video_path=str(VIDEOS_DIR / top),
        side_video_path=str(VIDEOS_DIR / side),
        box_cm=BOX_CM,
        # sem pontos de perspectiva -> Rectify usa o fallback default (warp identidade
        # do frame inteiro), exatamente como o process_perspective legado sem 4 pontos.
        perspective_points_top=[],
        perspective_points_side=[],
        # borda: retângulo em pixel (from-top) em cada view — build_border_region converte pra cm.
        border_points_top=_border_rect(60.0, 100.0, 140.0, 180.0),
        border_points_side=_border_rect(60.0, 100.0, 140.0, 180.0),
        orientation=golden_orientation(),
    )
