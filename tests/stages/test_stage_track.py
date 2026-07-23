"""Testes do estágio Track (Fase 3)."""

from __future__ import annotations

from src.core.schema.detection import Detection, FrameDetections
from src.core.schema.geometry import Point2D
from src.stages.track.plugin import SingleEntityTracker


def _dets(frame_index: int, *detections: Detection) -> FrameDetections:
    return FrameDetections(frame_index=frame_index, view="top", detections=list(detections))


def test_accumulates_points_across_frames() -> None:
    trk = SingleEntityTracker("top")
    trk.update(_dets(0, Detection(centroid=Point2D(x=1.0, y=2.0), area=10.0)))
    trk.update(_dets(1, Detection(centroid=Point2D(x=3.0, y=4.0), area=10.0)))
    tracks = trk.tracks()
    assert len(tracks) == 1
    track = tracks[0]
    assert track.entity_id == 0
    assert track.view == "top"
    assert track.points == {0: Point2D(x=1.0, y=2.0), 1: Point2D(x=3.0, y=4.0)}


def test_empty_detection_is_a_hole() -> None:
    trk = SingleEntityTracker("side")
    trk.update(_dets(0, Detection(centroid=Point2D(x=1.0, y=2.0), area=10.0)))
    trk.update(FrameDetections(frame_index=1, view="side", detections=[]))  # oclusão
    trk.update(_dets(2, Detection(centroid=Point2D(x=5.0, y=6.0), area=10.0)))
    points = trk.tracks()[0].points
    assert set(points) == {0, 2}  # frame 1 é buraco, sem sentinela


def test_picks_largest_area_when_multiple() -> None:
    trk = SingleEntityTracker("top")
    trk.update(
        _dets(
            0,
            Detection(centroid=Point2D(x=1.0, y=1.0), area=5.0),
            Detection(centroid=Point2D(x=9.0, y=9.0), area=50.0),
        )
    )
    assert trk.tracks()[0].points[0] == Point2D(x=9.0, y=9.0)


def test_tracks_returns_copy_and_reset_clears() -> None:
    trk = SingleEntityTracker("top")
    trk.update(_dets(0, Detection(centroid=Point2D(x=1.0, y=1.0), area=1.0)))
    snapshot = trk.tracks()[0].points
    trk.update(_dets(1, Detection(centroid=Point2D(x=2.0, y=2.0), area=1.0)))
    assert snapshot == {0: Point2D(x=1.0, y=1.0)}  # cópia, não afetada por update posterior
    trk.reset()
    assert trk.tracks()[0].points == {}
