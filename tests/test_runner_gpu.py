"""Gate de GPU no runner compartilhado (Fase 5).

`execute_analysis(require_gpu=True)` delega ao gate central `require_cuda()` e
re-embrulha a falha na fachada `GpuRequiredError` (que a CLI já captura), agora
subclasse de `GpuNotAvailableError`. Sem GPU real.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import pytest

from src.app.runner import GpuRequiredError, execute_analysis
from src.core.gpu import GpuNotAvailableError
from src.core.workspace import Workspace


def test_execute_analysis_require_gpu_fails_early(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cv2.cuda, "getCudaEnabledDeviceCount", lambda: 0)
    ws = Workspace(root=tmp_path / "ws")

    with pytest.raises(GpuRequiredError) as excinfo:
        # Gate roda ANTES de tentar carregar o perfil (que nem existe).
        execute_analysis(ws, "qualquer", require_gpu=True)

    # Fachada de app é subclasse do erro core → quem captura o core também pega esta.
    assert isinstance(excinfo.value, GpuNotAvailableError)
    assert "dispositivo" in str(excinfo.value)


def test_gpu_required_error_is_core_error_subclass() -> None:
    assert issubclass(GpuRequiredError, GpuNotAvailableError)
