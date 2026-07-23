"""Testes de detection.py (Fase 1)."""

import pytest
from pydantic import ValidationError

from src.core.schema.detection import Detection, FrameDetections
from src.core.schema.geometry import BBox, Point2D


def test_detection_defaults():
    d = Detection(centroid=Point2D(x=1.0, y=2.0))
    assert d.bbox is None
    assert d.confidence == 1.0
    assert d.area is None


def test_detection_round_trip_full():
    d = Detection(
        centroid=Point2D(x=1.0, y=2.0),
        bbox=BBox(x=0.0, y=0.0, w=4.0, h=4.0),
        confidence=0.5,
        area=16.0,
    )
    assert Detection.model_validate_json(d.model_dump_json()) == d


def test_frame_detections_round_trip_empty():
    fd = FrameDetections(frame_index=0, view="top")
    assert fd.detections == []
    assert FrameDetections.model_validate_json(fd.model_dump_json()) == fd


def test_frame_detections_round_trip_populated():
    fd = FrameDetections(
        frame_index=3,
        view="side",
        detections=[
            Detection(centroid=Point2D(x=1.0, y=1.0)),
            Detection(centroid=Point2D(x=2.0, y=2.0), confidence=0.8),
        ],
    )
    assert FrameDetections.model_validate_json(fd.model_dump_json()) == fd


def test_confidence_out_of_range():
    with pytest.raises(ValidationError):
        Detection(centroid=Point2D(x=0.0, y=0.0), confidence=1.5)
    with pytest.raises(ValidationError):
        Detection(centroid=Point2D(x=0.0, y=0.0), confidence=-0.1)


def test_negative_area_rejected():
    with pytest.raises(ValidationError):
        Detection(centroid=Point2D(x=0.0, y=0.0), area=-1.0)


def test_invalid_view_rejected():
    with pytest.raises(ValidationError):
        FrameDetections(frame_index=0, view="front")  # type: ignore[arg-type]


def test_negative_frame_index_rejected():
    with pytest.raises(ValidationError):
        FrameDetections(frame_index=-1, view="top")
