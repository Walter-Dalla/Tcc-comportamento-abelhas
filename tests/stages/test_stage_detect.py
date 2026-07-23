"""Testes do estágio Detect (Fase 3), contra fakes de Capture/Rectify (seção 6).

Não depende das classes reais DualVideoFileCapture/CpuPerspectiveRectifier — usa
fakes em memória, exatamente o padrão de handoff seguro da seção 6/8 do plano.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pytest

from src.core.frames import RectifiedFrame
from src.core.schema.orientation import CameraRole
from src.stages.detect.plugin import BackgroundSubtractionDetector, DetectError


class FakeCapture:
    """`open_single(role)` devolve uma sequência conhecida de frames crus em memória."""

    def __init__(self, frames: list[np.ndarray]) -> None:
        self._frames = frames
        self.open_single_calls: list[CameraRole] = []

    def open_single(self, role: CameraRole) -> Iterator[np.ndarray]:
        self.open_single_calls.append(role)
        yield from self._frames


class IdentityRectifier:
    """Warp trivial: devolve o frame cru como imagem grayscale (já 2D)."""

    def rectify(self, frame: np.ndarray, frame_index: int) -> RectifiedFrame:
        return RectifiedFrame(
            image=frame, role=CameraRole.TOP, frame_index=frame_index, orientation=None
        )


def _uniform(value: int, h: int = 40, w: int = 40) -> np.ndarray:
    return np.full((h, w), value, dtype=np.uint8)


def _with_dark_block(bg: int, dark: int, r0: int, r1: int, c0: int, c1: int) -> np.ndarray:
    img = _uniform(bg)
    img[r0:r1, c0:c1] = dark
    return img


def test_setup_samples_every_frame_block() -> None:
    # 12 frames uniformes, frame_block=5 -> amostra índices 0,5,10 = 3 frames
    frames = [_uniform(200) for _ in range(12)]
    cap = FakeCapture(frames)
    det = BackgroundSubtractionDetector(cap, IdentityRectifier(), CameraRole.TOP, frame_block=5)
    det.setup()
    assert cap.open_single_calls == [CameraRole.TOP]  # leu só a própria view
    # max_frame de frames uniformes 200 = 200 em todo lugar
    assert det._max_frame is not None
    assert np.all(det._max_frame == 200)


def test_setup_reads_full_length_not_truncated() -> None:
    # o fake sempre entrega todos os frames; confirma que setup consome até o fim
    consumed = []

    class CountingCapture(FakeCapture):
        def open_single(self, role: CameraRole) -> Iterator[np.ndarray]:
            for f in self._frames:
                consumed.append(f)
                yield f

    frames = [_uniform(200) for _ in range(17)]
    det = BackgroundSubtractionDetector(
        CountingCapture(frames), IdentityRectifier(), CameraRole.SIDE, frame_block=5
    )
    det.setup()
    assert len(consumed) == 17  # leu o vídeo inteiro da própria view


def test_setup_empty_video_raises() -> None:
    det = BackgroundSubtractionDetector(FakeCapture([]), IdentityRectifier(), CameraRole.TOP)
    with pytest.raises(DetectError):
        det.setup()


def test_detect_before_setup_raises() -> None:
    det = BackgroundSubtractionDetector(FakeCapture([]), IdentityRectifier(), CameraRole.TOP)
    frame = RectifiedFrame(image=_uniform(200), role=CameraRole.TOP, frame_index=0)
    with pytest.raises(DetectError):
        det.detect(frame)


def test_detect_returns_empty_when_no_blob() -> None:
    frames = [_uniform(200) for _ in range(3)]
    det = BackgroundSubtractionDetector(FakeCapture(frames), IdentityRectifier(), CameraRole.TOP)
    det.setup()
    # frame idêntico ao fundo -> sem contorno -> detecção vazia (não sentinela -1,-1)
    out = det.detect(RectifiedFrame(image=_uniform(200), role=CameraRole.TOP, frame_index=2))
    assert out.frame_index == 2
    assert out.view == "top"
    assert out.detections == []


def test_detect_centroid_with_v_flip() -> None:
    frames = [_uniform(200) for _ in range(3)]  # fundo claro -> max_frame=200
    det = BackgroundSubtractionDetector(FakeCapture(frames), IdentityRectifier(), CameraRole.SIDE)
    det.setup()
    # bloco escuro nas linhas 4..14 (topo da imagem), colunas 10..20 -> centro ~ (15, 9)
    frame = _with_dark_block(bg=200, dark=20, r0=4, r1=14, c0=10, c1=20)
    out = det.detect(RectifiedFrame(image=frame, role=CameraRole.SIDE, frame_index=1))
    assert out.view == "side"
    assert len(out.detections) == 1
    det0 = out.detections[0]
    assert det0.centroid.x == pytest.approx(14.5, abs=1.0)  # cx ~ (10+20)/2
    # cy_from_top ~ 9 ; height=40 -> cy_from_bottom ~ 31 (eixo v medido de baixo)
    assert det0.centroid.y == pytest.approx(31.0, abs=1.0)
    assert det0.area is not None and det0.area > 0


def test_detect_picks_largest_contour() -> None:
    frames = [_uniform(200) for _ in range(3)]
    det = BackgroundSubtractionDetector(FakeCapture(frames), IdentityRectifier(), CameraRole.TOP)
    det.setup()
    img = _uniform(200)
    img[2:5, 2:5] = 20  # bloco pequeno
    img[20:34, 20:34] = 20  # bloco grande
    out = det.detect(RectifiedFrame(image=img, role=CameraRole.TOP, frame_index=0))
    assert len(out.detections) == 1
    # centroide deve cair no bloco grande (cx ~ 26)
    assert out.detections[0].centroid.x == pytest.approx(26.5, abs=1.5)
