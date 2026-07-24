"""Gate de GPU dentro de `Pipeline.run` (Fase 5).

Valida a decisão de produto fechada: o probe gate SÓ o `Pipeline.run` quando o run
pede GPU, falha ALTA e CEDO (antes de tocar em disco), sem escrever resultado
parcial. Nenhum teste precisa de GPU real.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import pytest

from src.core.gpu import GpuNotAvailableError
from src.core.pipeline import Pipeline, RunRequest
from src.core.plugin_registry import PluginRegistry
from src.core.store import StoreError


def _pipeline() -> Pipeline:
    return Pipeline(PluginRegistry())


def test_run_with_gpu_fails_early_without_device(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 0)
    ws = tmp_path / "ws"
    req = RunRequest(profile="inexistente", workspace=str(ws), gpu=True)

    with pytest.raises(GpuNotAvailableError):
        _pipeline().run(req)

    # Gate falhou ANTES do store.load — nenhum resultado parcial escrito.
    assert not ws.exists() or not list(ws.rglob("*.json"))


def test_run_with_gpu_passes_gate_when_device_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Com device presente o gate passa; o run então falha mais adiante (perfil
    inexistente) — provando que o gate NÃO é o que barra aqui."""
    monkeypatch.setattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 1)
    ws = tmp_path / "ws"
    req = RunRequest(profile="inexistente", workspace=str(ws), gpu=True)

    with pytest.raises(StoreError):
        _pipeline().run(req)


def test_run_without_gpu_never_gates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`gpu=False` (default) nunca chama o gate — mesmo com 0 devices, a falha é a
    do perfil inexistente (StoreError), não GpuNotAvailableError."""
    monkeypatch.setattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 0)
    ws = tmp_path / "ws"
    req = RunRequest(profile="inexistente", workspace=str(ws), gpu=False)

    with pytest.raises(StoreError):
        _pipeline().run(req)
