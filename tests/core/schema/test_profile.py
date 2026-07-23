"""Testes de profile.py (Fase 1)."""

import pytest
from pydantic import ValidationError

from src.core.schema.geometry import Point2D, Point3D
from src.core.schema.orientation import (
    BoxFace,
    BoxOrientationConfig,
    BoxVertex,
    CameraOrientation,
    CameraRole,
)
from src.core.schema.profile import Profile


def _four_points() -> list[Point2D]:
    return [Point2D(x=float(i), y=float(i)) for i in range(4)]


def _orientation() -> BoxOrientationConfig:
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
    return BoxOrientationConfig(top_camera=top, side_camera=side)


def test_empty_profile_round_trip():
    p = Profile(name="fish01")
    assert p.orientation is None
    assert p.box_cm == Point3D(x=0.0, y=0.0, z=0.0)
    assert p.perspective_points_top == []
    assert Profile.model_validate_json(p.model_dump_json()) == p


def test_populated_profile_round_trip():
    p = Profile(
        name="bee",
        top_video_path="top.mp4",
        side_video_path="side.mp4",
        box_cm=Point3D(x=10.0, y=20.0, z=30.0),
        perspective_points_top=_four_points(),
        perspective_points_side=_four_points(),
        border_points_top=_four_points(),
        border_points_side=_four_points(),
        orientation=_orientation(),
    )
    assert Profile.model_validate_json(p.model_dump_json()) == p


@pytest.mark.parametrize(
    "field",
    [
        "perspective_points_top",
        "perspective_points_side",
        "border_points_top",
        "border_points_side",
    ],
)
@pytest.mark.parametrize("n", [2, 3])
def test_wrong_point_count_rejected(field, n):
    points = [Point2D(x=float(i), y=float(i)) for i in range(n)]
    with pytest.raises(ValidationError):
        Profile(name="x", **{field: points})
