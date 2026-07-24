"""CudaMOG2Detector (Fase 5) — testado sem GPU injetando backend CPU + subtractor fake.

O passo pesado (MOG2) é injetável; o passo final (maior contorno → centroide), que
é idêntico ao detector CPU, roda em CPU e é o que estes testes exercitam. A validação
MOG2 real + paridade comportamental com o detector CPU é `@pytest.mark.gpu`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from src.core.array_backend import CpuArrayBackend
from src.core.frames import RectifiedFrame
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.schema.orientation import CameraRole
from src.core.stages import Detector
from src.stages.detect.cuda.plugin import CudaMOG2Detector, DetectError

_DETECT_DIR = Path(__file__).resolve().parents[2] / "src" / "stages" / "detect"


class _FakeSubtractor:
    """Devolve uma máscara de foreground fixa a cada `apply` (o "resultado" do MOG2)."""

    def __init__(self, mask: np.ndarray) -> None:
        self._mask = mask
        self.calls = 0

    def apply(self, handle: Any, learning_rate: float, stream: Any) -> np.ndarray:
        self.calls += 1
        return self._mask


@pytest.fixture(autouse=True)
def _stub_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """`detect` chama `cv2.cuda.Stream_Null()` só para passar ao subtractor; num build
    sem CUDA esse símbolo pode faltar. Stub inofensivo para robustez entre builds."""
    monkeypatch.setattr(cv2.cuda, "Stream_Null", lambda: None, raising=False)


def _frame(gray: np.ndarray, role: CameraRole = CameraRole.TOP, idx: int = 5) -> RectifiedFrame:
    return RectifiedFrame(image=gray, role=role, frame_index=idx, orientation=None)


def test_is_detector_subclass() -> None:
    assert issubclass(CudaMOG2Detector, Detector)
    assert isinstance(CudaMOG2Detector(), Detector)


def test_constructible_without_cuda() -> None:
    """Instanciar não exige GPU (subtractor é adiado pro setup)."""
    det = CudaMOG2Detector(CameraRole.SIDE)
    assert det.role is CameraRole.SIDE


def test_detect_before_setup_raises() -> None:
    det = CudaMOG2Detector(CameraRole.TOP)
    with pytest.raises(DetectError):
        det.detect(_frame(np.zeros((10, 10), dtype=np.uint8)))


def test_detect_extracts_centroid_from_fake_mask() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[30:51, 40:61] = 255  # blob: linhas 30..50, colunas 40..60
    det = CudaMOG2Detector(
        CameraRole.TOP, backend=CpuArrayBackend(), subtractor=_FakeSubtractor(mask)
    )

    result = det.detect(_frame(np.zeros((100, 100), dtype=np.uint8), idx=5))

    assert result.frame_index == 5
    assert result.view == "top"
    assert len(result.detections) == 1
    det0 = result.detections[0]
    # Centroide do blob: cx ~50, cy_from_top ~40 → cy_from_bottom = 100-40 = 60.
    assert det0.centroid.x == pytest.approx(50, abs=2)
    assert det0.centroid.y == pytest.approx(60, abs=2)
    assert det0.area is not None and det0.area > 0


def test_detect_side_view_and_empty_mask() -> None:
    empty = np.zeros((50, 50), dtype=np.uint8)
    det = CudaMOG2Detector(
        CameraRole.SIDE, backend=CpuArrayBackend(), subtractor=_FakeSubtractor(empty)
    )
    result = det.detect(_frame(empty, role=CameraRole.SIDE, idx=2))
    assert result.view == "side"
    assert result.detections == []


def test_manifest_discoverable() -> None:
    registry = PluginRegistry()
    registry.discover([_DETECT_DIR])
    manifests = registry.manifests(PluginKind.DETECTOR)
    names = {m.name for m in manifests}
    assert "cuda-mog2-detector" in names
    manifest = next(m for m in manifests if m.name == "cuda-mog2-detector")
    assert manifest.kind is PluginKind.DETECTOR
    assert manifest.entry == "plugin:CudaMOG2Detector"


def test_registry_instantiates_and_validates_detector_contract() -> None:
    """Descoberta → instanciação via registry: valida subclasse `Detector` e o
    construtor zero-arg (o gate CUDA só cai no `setup()`, não na construção)."""
    registry = PluginRegistry()
    registry.discover([_DETECT_DIR])
    plugin = registry.get(PluginKind.DETECTOR, "cuda-mog2-detector")
    assert isinstance(plugin, Detector)
    assert plugin.manifest.name == "cuda-mog2-detector"
