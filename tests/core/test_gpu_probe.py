"""Testes do probe de GPU (Fase 2, plano seção 5)."""

from __future__ import annotations

import builtins

import pytest

from src.core.gpu import GpuProbeResult, probe_cuda_devices


def test_probe_never_raises_without_cv2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simula ausência total de cv2 (ImportError) — probe reporta indisponível."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cv2":
            raise ImportError("no cv2")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = probe_cuda_devices()
    assert result == GpuProbeResult(available=False, device_count=0)


def test_probe_handles_cv2_without_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    """cv2 presente mas sem submódulo `cuda` (AttributeError) — indisponível."""
    real_import = builtins.__import__

    class _FakeCv2:
        pass  # sem atributo `cuda`

    def fake_import(name, *args, **kwargs):
        if name == "cv2":
            return _FakeCv2()
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = probe_cuda_devices()
    assert result.available is False
    assert result.device_count == 0


def test_probe_returns_result_type() -> None:
    """Executa o probe real do ambiente — só verifica que devolve o tipo e não lança."""
    result = probe_cuda_devices()
    assert isinstance(result, GpuProbeResult)
    assert result.device_count >= 0
