"""Testes do estágio Capture (Fase 3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.frames import FramePair
from src.core.schema.orientation import CameraRole
from src.stages.capture.plugin import CaptureError, DualVideoFileCapture
from tests.fixtures.golden_config import VIDEOS_DIR

pytestmark = pytest.mark.skipif(
    not (VIDEOS_DIR / "main_top.avi").exists(),
    reason="vídeos de fixture ausentes",
)


def _capture(top: str = "main_top.avi", side: str = "main_side.avi") -> DualVideoFileCapture:
    return DualVideoFileCapture(str(VIDEOS_DIR / top), str(VIDEOS_DIR / side))


def test_open_yields_sequential_framepairs() -> None:
    fps, gen = _capture().open()
    assert fps == 30  # do topo
    first = next(gen)
    assert isinstance(first, FramePair)
    assert first.frame_index == 0
    second = next(gen)
    assert second.frame_index == 1
    # top/side têm dimensões esperadas (BGR)
    assert first.top.shape == (240, 320, 3)
    assert first.side.shape == (240, 320, 3)


def test_open_truncates_at_shorter_video() -> None:
    _fps, gen = _capture(top="uneven_top.avi", side="uneven_side.avi").open()
    count = sum(1 for _ in gen)
    assert count == 1200  # para no top (mais curto), não 1600


def test_open_single_reads_full_own_length_independent_of_partner() -> None:
    cap = _capture(top="uneven_top.avi", side="uneven_side.avi")
    top_count = sum(1 for _ in cap.open_single(CameraRole.TOP))
    side_count = sum(1 for _ in cap.open_single(CameraRole.SIDE))
    # cada view lê o SEU vídeo inteiro — sem lockstep (essencial pro modelo de fundo)
    assert top_count == 1200
    assert side_count == 1600


def test_dimensions() -> None:
    assert _capture().dimensions(CameraRole.TOP) == (320, 240)


def test_bad_path_raises_capture_error(tmp_path: Path) -> None:
    cap = DualVideoFileCapture(str(tmp_path / "nope.avi"), str(VIDEOS_DIR / "main_side.avi"))
    with pytest.raises(CaptureError):
        cap.open()
    with pytest.raises(CaptureError):
        next(cap.open_single(CameraRole.TOP))
