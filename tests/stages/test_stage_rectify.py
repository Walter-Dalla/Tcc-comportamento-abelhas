"""Testes do estágio Rectify (Fase 3)."""

from __future__ import annotations

import numpy as np

from src.core.frames import RectifiedFrame
from src.core.schema.orientation import CameraRole
from src.stages.rectify.plugin import CpuPerspectiveRectifier


def _bgr(h: int = 240, w: int = 320) -> np.ndarray:
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)


def test_default_points_full_frame_identity_grayscale() -> None:
    rect = CpuPerspectiveRectifier([], None, CameraRole.TOP, 320, 240)
    assert rect.output_shape == (240, 320)  # (height, width)
    frame = _bgr()
    out = rect.rectify(frame, frame_index=7)
    assert isinstance(out, RectifiedFrame)
    assert out.role is CameraRole.TOP
    assert out.frame_index == 7
    assert out.image.ndim == 2  # grayscale
    assert out.image.shape == (240, 320)
    # warp identidade + grayscale = cvtColor direto do frame
    import cv2

    assert np.array_equal(out.image, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))


def test_explicit_four_points_crop_size() -> None:
    # get_perspective_size (legado): width = fp[1][0]-fp[0][0]; height = fp[2][1]-fp[0][1]
    points = [[10, 20], [100, 20], [10, 220], [100, 220]]  # width=90, height=200
    rect = CpuPerspectiveRectifier(points, None, CameraRole.SIDE, 320, 240)
    assert rect.output_shape == (200, 90)  # (height, width)
    out = rect.rectify(_bgr(), 0)
    assert out.image.shape == (200, 90)


def test_orientation_metadata_attached() -> None:
    from tests.fixtures.golden_config import golden_orientation

    orient = golden_orientation()
    rect = CpuPerspectiveRectifier([], orient, CameraRole.SIDE, 320, 240)
    out = rect.rectify(_bgr(), 0)
    assert out.orientation is orient
    assert out.role is CameraRole.SIDE
