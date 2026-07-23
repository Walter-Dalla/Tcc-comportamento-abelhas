"""Testes de track.py (Fase 1)."""

import pytest
from pydantic import ValidationError

from src.core.schema.geometry import Point2D
from src.core.schema.track import Track


def test_track_round_trip_empty():
    t = Track(entity_id=0, view="top")
    assert t.points == {}
    assert Track.model_validate_json(t.model_dump_json()) == t


def test_track_round_trip_contiguous():
    t = Track(
        entity_id=1,
        view="side",
        points={i: Point2D(x=float(i), y=float(i)) for i in range(3)},
    )
    assert Track.model_validate_json(t.model_dump_json()) == t


def test_track_round_trip_with_hole():
    # buraco (frames 1-4 faltando) representa oclusão nativamente.
    t = Track(entity_id=2, view="top", points={0: Point2D(x=0.0, y=0.0), 5: Point2D(x=5.0, y=5.0)})
    restored = Track.model_validate_json(t.model_dump_json())
    assert restored == t
    assert set(restored.points) == {0, 5}


def test_int_keys_survive_round_trip():
    t = Track(entity_id=0, view="top", points={0: Point2D(x=0.0, y=0.0), 7: Point2D(x=1.0, y=1.0)})
    restored = Track.model_validate_json(t.model_dump_json())
    # Pydantic v2 serializa a chave int como string em JSON e reconverte para int na leitura.
    assert all(isinstance(k, int) for k in restored.points)


def test_negative_entity_id_rejected():
    with pytest.raises(ValidationError):
        Track(entity_id=-1, view="top")
