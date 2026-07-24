"""CudaPerspectiveRectifier (Fase 5) — testado sem GPU injetando `CpuArrayBackend`.

Injetar o backend CPU roda o MESMO caminho numérico do rectifier CUDA em CPU: prova
que o plumbing (matriz calculada uma vez, upload→warp→cvt_color→download,
`RectifiedFrame` montado) está correto, e que a saída é IDÊNTICA à do
`CpuPerspectiveRectifier` de produção. A paridade CPU×CUDA real é `@pytest.mark.gpu`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.array_backend import CpuArrayBackend
from src.core.plugin import Plugin, PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.schema.orientation import CameraRole
from src.stages.rectify.cuda.plugin import CudaPerspectiveRectifier
from src.stages.rectify.plugin import CpuPerspectiveRectifier

_RECTIFY_DIR = Path(__file__).resolve().parents[2] / "src" / "stages" / "rectify"
_POINTS = [[10, 10], [90, 12], [8, 100], [92, 98]]


@pytest.fixture
def frame() -> np.ndarray:
    rng = np.random.default_rng(7)
    return rng.integers(0, 256, size=(120, 110, 3), dtype=np.uint8)


def _make_cuda(backend: CpuArrayBackend) -> CudaPerspectiveRectifier:
    return CudaPerspectiveRectifier(_POINTS, None, CameraRole.TOP, 110, 120, backend=backend)


def test_is_plugin_subclass() -> None:
    assert issubclass(CudaPerspectiveRectifier, Plugin)


def test_output_shape_and_role_match_cpu() -> None:
    cuda = _make_cuda(CpuArrayBackend())
    cpu = CpuPerspectiveRectifier(_POINTS, None, CameraRole.TOP, 110, 120)
    assert cuda.output_shape == cpu.output_shape
    assert cuda.role is CameraRole.TOP


def test_rectify_matches_cpu_rectifier_bit_for_bit(frame: np.ndarray) -> None:
    """Mesmo backend numérico (cv2) dos dois lados → saída idêntica."""
    cuda = _make_cuda(CpuArrayBackend())
    cpu = CpuPerspectiveRectifier(_POINTS, None, CameraRole.TOP, 110, 120)

    got = cuda.rectify(frame, 3)
    expected = cpu.rectify(frame, 3)

    assert np.array_equal(got.image, expected.image)
    assert got.role is expected.role
    assert got.frame_index == expected.frame_index == 3
    assert got.image.ndim == 2  # grayscale


def test_default_backend_gates_on_cuda(monkeypatch: pytest.MonkeyPatch, frame: np.ndarray) -> None:
    """Sem backend injetado e sem device CUDA, `rectify` falha limpo (o gate cai no
    uso real, não na construção — configurar o perfil não exige GPU)."""
    import cv2

    from src.core.gpu import GpuNotAvailableError

    monkeypatch.setattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 0)
    rect = CudaPerspectiveRectifier(_POINTS, None, CameraRole.TOP, 110, 120)  # sem backend
    with pytest.raises(GpuNotAvailableError):
        rect.rectify(frame, 0)


def test_manifest_discoverable(tmp_path: Path) -> None:
    """O `plugin.toml` do rectifier CUDA é descoberto pelo registry do mesmo jeito
    que os demais plugins (glob `<root>/*/plugin.toml`)."""
    registry = PluginRegistry()
    registry.discover([_RECTIFY_DIR])
    names = {m.name for m in registry.manifests(PluginKind.RECTIFY)}
    assert "cuda-perspective-rectifier" in names
    manifest = next(m for m in registry.manifests(PluginKind.RECTIFY)
                    if m.name == "cuda-perspective-rectifier")
    assert manifest.kind is PluginKind.RECTIFY
    assert manifest.entry == "plugin:CudaPerspectiveRectifier"
