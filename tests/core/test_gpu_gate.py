"""Gate obrigatório de GPU (Fase 5) — `cuda_device_count`/`require_cuda`.

Todos rodam SEM GPU real: mockam `cv2.cuda.getCudaEnabledDeviceCount` para simular
0/1/2 devices, e simulam builds sem `cv2`/sem submódulo `cuda`. Nenhum é marcado
`gpu` — validam exatamente a linha de verificação da Fase 5 no `ARCHITECTURE.md`
("startup falha limpo sem device CUDA") sem depender de hardware.
"""

from __future__ import annotations

import builtins

import cv2
import pytest

from src.core.gpu import (
    GpuNotAvailableError,
    GpuProbeResult,
    cuda_device_count,
    probe_cuda_devices,
    require_cuda,
)


@pytest.mark.parametrize("count", [0, 1, 2])
def test_cuda_device_count_reports_mocked_value(monkeypatch: pytest.MonkeyPatch, count: int) -> None:
    monkeypatch.setattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: count)
    assert cuda_device_count() == count


def test_cuda_device_count_zero_without_cv2(monkeypatch: pytest.MonkeyPatch) -> None:
    """ImportError (sem cv2) → 0, sem lançar."""
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "cv2":
            raise ImportError("no cv2")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert cuda_device_count() == 0


def test_cuda_device_count_zero_when_cv2_lacks_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    """cv2 presente mas sem submódulo `cuda` (build sem CUDA) → 0, sem lançar."""
    real_import = builtins.__import__

    class _FakeCv2:
        pass  # sem atributo `cuda`

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "cv2":
            return _FakeCv2()
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert cuda_device_count() == 0


def test_probe_delegates_to_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 2)
    result = probe_cuda_devices()
    assert result == GpuProbeResult(available=True, device_count=2)


def test_require_cuda_raises_clean_error_without_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 0)
    with pytest.raises(GpuNotAvailableError) as excinfo:
        require_cuda()
    # mensagem clara com a contagem encontrada (não um traceback fundo do OpenCV)
    assert "0 dispositivo" in str(excinfo.value)


def test_require_cuda_returns_count_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 1)
    assert require_cuda() == 1


def test_require_cuda_respects_min_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 1)
    with pytest.raises(GpuNotAvailableError):
        require_cuda(min_devices=2)
