"""Testes de result.py (Fase 1)."""

import pytest
from pydantic import ValidationError

from src.core.schema.geometry import Point3D
from src.core.schema.orientation import (
    BoxFace,
    BoxOrientationConfig,
    BoxVertex,
    Calibration,
    CameraOrientation,
    CameraRole,
)
from src.core.schema.result import (
    SCHEMA_VERSION,
    AnalysisContext,
    AnalysisResult,
    BorderRegion,
    Metric,
)
from src.core.schema.route import Route3D


def _calibration() -> Calibration:
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
        px_per_cm=Point3D(x=5.0, y=5.0, z=5.0),
        fps=30.0,
        orientation=BoxOrientationConfig(top_camera=top, side_camera=side),
    )


# ---- Metric ------------------------------------------------------------------

def test_metric_round_trip_default_unit():
    m = Metric(name="speed", value=1.5, producer="speed-plugin")
    assert m.unit is None
    assert Metric.model_validate_json(m.model_dump_json()) == m


def test_metric_round_trip_with_unit():
    m = Metric(name="speed", value=1.5, unit="cm/s", producer="speed-plugin")
    assert Metric.model_validate_json(m.model_dump_json()) == m


@pytest.mark.parametrize(
    "value",
    ["str", 3, 2.5, True, [1, 2, 3], {"a": 1}, None],
)
def test_metric_accepts_json_safe_values(value):
    m = Metric(name="x", value=value, producer="p")
    assert m.value == value


@pytest.mark.parametrize("bad", [{1, 2, 3}, object()])
def test_metric_rejects_non_json_safe_values(bad):
    with pytest.raises(ValidationError):
        Metric(name="x", value=bad, producer="p")


# ---- BorderRegion ------------------------------------------------------------

def test_border_region_default_threshold():
    br = BorderRegion(bounds={"x": (0.0, 1.0), "y": (0.0, 1.0), "z": (0.0, 1.0)})
    assert br.threshold_px == 100
    assert BorderRegion.model_validate_json(br.model_dump_json()) == br


def test_border_region_custom_threshold_round_trip():
    br = BorderRegion(threshold_px=50, bounds={"x": (0.0, 5.0), "y": (1.0, 2.0), "z": (-3.0, 3.0)})
    assert BorderRegion.model_validate_json(br.model_dump_json()) == br


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_border_region_min_gt_max_rejected(axis):
    bounds = {"x": (0.0, 1.0), "y": (0.0, 1.0), "z": (0.0, 1.0)}
    bounds[axis] = (5.0, 1.0)
    with pytest.raises(ValidationError):
        BorderRegion(bounds=bounds)


def test_border_region_missing_axis_rejected():
    with pytest.raises(ValidationError):
        BorderRegion(bounds={"x": (0.0, 1.0), "y": (0.0, 1.0)})


# ---- AnalysisResult ----------------------------------------------------------

def test_analysis_result_default_schema_version():
    r = AnalysisResult(profile="p", calibration=_calibration())
    assert r.schema_version == SCHEMA_VERSION
    assert r.routes == []
    assert r.metrics == {}
    assert r.border_region is None


def test_analysis_result_round_trip_empty():
    r = AnalysisResult(profile="p", calibration=_calibration())
    assert AnalysisResult.model_validate_json(r.model_dump_json()) == r


def test_analysis_result_round_trip_populated():
    r = AnalysisResult(
        profile="p",
        calibration=_calibration(),
        routes=[
            Route3D(entity_id=0, points={0: Point3D(x=0.0, y=0.0, z=0.0)}),
            Route3D(entity_id=1, points={0: Point3D(x=1.0, y=1.0, z=1.0)}),
        ],
        metrics={
            "speed": Metric(name="speed", value=1.5, unit="cm/s", producer="speed"),
            "distance": Metric(name="distance", value=10.0, producer="speed"),
        },
        border_region=BorderRegion(bounds={"x": (0.0, 1.0), "y": (0.0, 1.0), "z": (0.0, 1.0)}),
    )
    assert AnalysisResult.model_validate_json(r.model_dump_json()) == r


# ---- AnalysisContext ---------------------------------------------------------

def test_context_add_and_get_metric():
    ctx = AnalysisContext(result=AnalysisResult(profile="p", calibration=_calibration()))
    m = Metric(name="speed", value=2.0, producer="speed")
    ctx.add_metric(m)
    assert ctx.get_metric("speed") == m


def test_context_get_missing_metric_returns_none():
    ctx = AnalysisContext(result=AnalysisResult(profile="p", calibration=_calibration()))
    assert ctx.get_metric("nope") is None
