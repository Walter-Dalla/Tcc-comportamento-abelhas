"""Testes de orientation.py (Fase 1), incluindo o algoritmo axis_mapping()."""

import pytest

from src.core.schema.geometry import Point2D, Point3D
from src.core.schema.orientation import (
    AxisMapping,
    AxisSource,
    BoxFace,
    BoxOrientationConfig,
    BoxVertex,
    Calibration,
    CameraOrientation,
    CameraRole,
    ImageAxis,
)


# ---- fixture canônica (exemplo calculado à mão na seção 1 do plano) ----------

def _canonical_config() -> BoxOrientationConfig:
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


# ---- BoxVertex ---------------------------------------------------------------

def test_box_vertex_has_8_members():
    assert len(list(BoxVertex)) == 8


def test_box_vertex_exact_names():
    expected = {
        "TOP_FRONT_LEFT",
        "TOP_FRONT_RIGHT",
        "TOP_BACK_LEFT",
        "TOP_BACK_RIGHT",
        "BOTTOM_FRONT_LEFT",
        "BOTTOM_FRONT_RIGHT",
        "BOTTOM_BACK_LEFT",
        "BOTTOM_BACK_RIGHT",
    }
    assert {v.name for v in BoxVertex} == expected


# ---- CameraOrientation -------------------------------------------------------

@pytest.mark.parametrize("n", [3, 5])
def test_corner_vertices_wrong_length_rejected(n):
    verts = list(BoxVertex)[:n]
    with pytest.raises(ValueError):
        CameraOrientation(role=CameraRole.TOP, face_viewed=BoxFace.TOP, corner_vertices=verts)


def test_corner_vertices_duplicate_rejected():
    with pytest.raises(ValueError):
        CameraOrientation(
            role=CameraRole.TOP,
            face_viewed=BoxFace.TOP,
            corner_vertices=[
                BoxVertex.TOP_FRONT_LEFT,
                BoxVertex.TOP_FRONT_LEFT,
                BoxVertex.TOP_BACK_RIGHT,
                BoxVertex.TOP_BACK_LEFT,
            ],
        )


# ---- BoxOrientationConfig role validation ------------------------------------

def test_swapped_roles_rejected():
    top_as_side = CameraOrientation(
        role=CameraRole.SIDE,  # errado
        face_viewed=BoxFace.TOP,
        corner_vertices=[
            BoxVertex.TOP_FRONT_RIGHT,
            BoxVertex.TOP_FRONT_LEFT,
            BoxVertex.TOP_BACK_RIGHT,
            BoxVertex.TOP_BACK_LEFT,
        ],
    )
    good_side = _canonical_config().side_camera
    with pytest.raises(ValueError):
        BoxOrientationConfig(top_camera=top_as_side, side_camera=good_side)

    good_top = _canonical_config().top_camera
    side_as_top = CameraOrientation(
        role=CameraRole.TOP,  # errado
        face_viewed=BoxFace.FRONT,
        corner_vertices=[
            BoxVertex.TOP_FRONT_RIGHT,
            BoxVertex.TOP_FRONT_LEFT,
            BoxVertex.BOTTOM_FRONT_RIGHT,
            BoxVertex.BOTTOM_FRONT_LEFT,
        ],
    )
    with pytest.raises(ValueError):
        BoxOrientationConfig(top_camera=good_top, side_camera=side_as_top)


# ---- axis_mapping() ----------------------------------------------------------

def test_axis_mapping_canonical():
    mapping = _canonical_config().axis_mapping()
    assert mapping.x == AxisSource(camera=CameraRole.TOP, image_axis=ImageAxis.U, sign=1)
    assert mapping.y == AxisSource(camera=CameraRole.SIDE, image_axis=ImageAxis.V, sign=1)
    assert mapping.z == AxisSource(camera=CameraRole.TOP, image_axis=ImageAxis.V, sign=-1)


def test_axis_mapping_adjacent_vertices_must_differ_in_one_component():
    # corner_vertices[0] e [2] diferem em 2 componentes (x e y) -> ValueError.
    bad_top = CameraOrientation(
        role=CameraRole.TOP,
        face_viewed=BoxFace.TOP,
        corner_vertices=[
            BoxVertex.TOP_FRONT_RIGHT,
            BoxVertex.TOP_FRONT_LEFT,
            BoxVertex.BOTTOM_BACK_RIGHT,  # difere de [0] em y e z
            BoxVertex.TOP_BACK_LEFT,
        ],
    )
    cfg = BoxOrientationConfig(top_camera=bad_top, side_camera=_canonical_config().side_camera)
    with pytest.raises(ValueError):
        cfg.axis_mapping()


def test_axis_mapping_unobservable_axis():
    # Ambas as câmeras observam apenas X (u) e Y (v); nenhuma observa Z -> ValueError.
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
        face_viewed=BoxFace.FRONT,
        corner_vertices=[
            BoxVertex.TOP_FRONT_RIGHT,
            BoxVertex.TOP_FRONT_LEFT,
            BoxVertex.BOTTOM_FRONT_RIGHT,
            BoxVertex.BOTTOM_FRONT_LEFT,
        ],
    )
    cfg = BoxOrientationConfig(top_camera=top, side_camera=side)
    with pytest.raises(ValueError):
        cfg.axis_mapping()


def test_axis_mapping_resolve():
    mapping = _canonical_config().axis_mapping()
    # top_point=(u=10, v=20), side_point=(u=30, v=40)
    # x = top.u * +1 = 10 ; y = side.v * +1 = 40 ; z = top.v * -1 = -20
    result = mapping.resolve(Point2D(x=10.0, y=20.0), Point2D(x=30.0, y=40.0))
    assert result == Point3D(x=10.0, y=40.0, z=-20.0)


def test_axis_mapping_distinct_sources_validator():
    src = AxisSource(camera=CameraRole.TOP, image_axis=ImageAxis.U, sign=1)
    with pytest.raises(ValueError):
        AxisMapping(x=src, y=src, z=src)


# ---- Calibration round-trip --------------------------------------------------

def test_calibration_round_trip():
    calib = Calibration(
        box_cm=Point3D(x=10.0, y=20.0, z=30.0),
        px_per_cm=Point3D(x=5.0, y=5.0, z=5.0),
        fps=30.0,
        orientation=_canonical_config(),
    )
    restored = Calibration.model_validate_json(calib.model_dump_json())
    assert restored == calib


def test_calibration_fps_must_be_positive():
    with pytest.raises(ValueError):
        Calibration(
            box_cm=Point3D(x=1.0, y=1.0, z=1.0),
            px_per_cm=Point3D(x=1.0, y=1.0, z=1.0),
            fps=0.0,
            orientation=_canonical_config(),
        )
