"""Testes de route.py (Fase 1)."""

import pytest
from pydantic import ValidationError

from src.core.schema.geometry import Point3D
from src.core.schema.route import Route3D


def test_route_round_trip_empty():
    r = Route3D(entity_id=0)
    assert r.points == {}
    assert Route3D.model_validate_json(r.model_dump_json()) == r


def test_route_round_trip_contiguous():
    r = Route3D(
        entity_id=1,
        points={i: Point3D(x=float(i), y=float(i), z=float(i)) for i in range(3)},
    )
    assert Route3D.model_validate_json(r.model_dump_json()) == r


def test_route_round_trip_with_hole():
    r = Route3D(
        entity_id=2,
        points={0: Point3D(x=0.0, y=0.0, z=0.0), 5: Point3D(x=5.0, y=5.0, z=5.0)},
    )
    restored = Route3D.model_validate_json(r.model_dump_json())
    assert restored == r
    assert set(restored.points) == {0, 5}


def test_int_keys_survive_round_trip():
    r = Route3D(entity_id=0, points={0: Point3D(x=0.0, y=0.0, z=0.0)})
    restored = Route3D.model_validate_json(r.model_dump_json())
    assert all(isinstance(k, int) for k in restored.points)


def test_negative_entity_id_rejected():
    with pytest.raises(ValidationError):
        Route3D(entity_id=-1)
