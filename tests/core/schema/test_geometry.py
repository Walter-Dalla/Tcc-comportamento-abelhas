"""Testes de geometry.py (Fase 1)."""

import pytest
from pydantic import ValidationError

from src.core.schema.geometry import BBox, Point2D, Point3D


def test_point2d_round_trip():
    p = Point2D(x=1.5, y=-2.0)
    restored = Point2D.model_validate_json(p.model_dump_json())
    assert restored == p


def test_point3d_round_trip():
    p = Point3D(x=1.0, y=2.0, z=3.0)
    restored = Point3D.model_validate_json(p.model_dump_json())
    assert restored == p


def test_bbox_round_trip():
    b = BBox(x=0.0, y=0.0, w=10.0, h=20.0)
    restored = BBox.model_validate_json(b.model_dump_json())
    assert restored == b


def test_point2d_is_frozen():
    p = Point2D(x=1.0, y=2.0)
    with pytest.raises(ValidationError):
        p.x = 5.0  # type: ignore[misc]


def test_point3d_is_frozen():
    p = Point3D(x=1.0, y=2.0, z=3.0)
    with pytest.raises(ValidationError):
        p.z = 9.0  # type: ignore[misc]


def test_geometry_is_hashable():
    # frozen=True -> hasháveis; úteis como chave de set/dict.
    assert len({Point2D(x=1.0, y=2.0), Point2D(x=1.0, y=2.0)}) == 1
    assert len({Point3D(x=1.0, y=2.0, z=3.0), Point3D(x=0.0, y=0.0, z=0.0)}) == 2


def test_extra_field_forbidden():
    with pytest.raises(ValidationError):
        Point2D(x=1.0, y=2.0, z=3.0)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        BBox(x=0.0, y=0.0, w=1.0, h=1.0, extra=1)  # type: ignore[call-arg]
