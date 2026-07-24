"""`ArrayBackend` (Fase 5) — caminho CPU testado a fundo; caminho CUDA só a falha
limpa de construção sem device (o round-trip real é `@pytest.mark.gpu`)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from src.core.array_backend import ArrayBackend, CpuArrayBackend, CudaArrayBackend
from src.core.gpu import GpuNotAvailableError


@pytest.fixture
def bgr_image() -> np.ndarray:
    rng = np.random.default_rng(1234)
    return rng.integers(0, 256, size=(40, 50, 3), dtype=np.uint8)


def test_cpu_backend_satisfies_protocol() -> None:
    assert isinstance(CpuArrayBackend(), ArrayBackend)
    assert CpuArrayBackend().name == "cpu"


def test_cpu_upload_download_roundtrip_identity(bgr_image: np.ndarray) -> None:
    backend = CpuArrayBackend()
    handle = backend.upload(bgr_image)
    out = backend.download(handle)
    assert np.array_equal(out, bgr_image)


def test_cpu_warp_matches_direct_cv2(bgr_image: np.ndarray) -> None:
    backend = CpuArrayBackend()
    src = np.array([[0, 0], [50, 0], [0, 40], [50, 40]], dtype=np.float32)
    dst = np.array([[2, 1], [48, 0], [1, 39], [49, 41]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    got = backend.warp_perspective(backend.upload(bgr_image), matrix, (50, 40))
    expected = cv2.warpPerspective(bgr_image, matrix, (50, 40))
    assert np.array_equal(got, expected)


def test_cpu_cvt_color_gray_matches_direct_cv2(bgr_image: np.ndarray) -> None:
    backend = CpuArrayBackend()
    got = backend.cvt_color_gray(backend.upload(bgr_image))
    expected = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    assert np.array_equal(got, expected)
    assert got.ndim == 2  # grayscale


def test_cpu_release_is_noop(bgr_image: np.ndarray) -> None:
    # Não deve lançar nem alterar o array.
    CpuArrayBackend().release(bgr_image)


def test_cuda_backend_construction_fails_clean_without_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem device CUDA, construir `CudaArrayBackend` levanta `GpuNotAvailableError`
    (erro claro), NÃO um AttributeError cru do OpenCV nem um no-op silencioso."""
    monkeypatch.setattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 0)
    with pytest.raises(GpuNotAvailableError):
        CudaArrayBackend()


@pytest.mark.gpu
def test_cuda_backend_roundtrip_real(bgr_image: np.ndarray) -> None:
    """Só roda na máquina com OpenCV+CUDA real (senão skip via conftest)."""
    backend = CudaArrayBackend()
    handle = backend.upload(bgr_image)
    out = backend.download(handle)
    assert np.array_equal(out, bgr_image)
