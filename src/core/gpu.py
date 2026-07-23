"""Probe de capacidade CUDA (stub da Fase 2 — enforcement real chega na Fase 5).

`probe_cuda_devices()` NUNCA lança: no startup da Fase 5 ele decidirá se o
requisito de GPU está satisfeito, mas o gate ("falhar alto se ausente") só entra
na Fase 5. Aqui é só o report. Workstream independente — sem nenhuma dependência
de `Plugin`/`PluginRegistry`/`Pipeline` (só `cv2` opcional e `pydantic`).
"""

from __future__ import annotations

from pydantic import BaseModel


class GpuProbeResult(BaseModel):
    available: bool
    device_count: int
    driver_info: str | None = None


def probe_cuda_devices() -> GpuProbeResult:
    """Probe de capacidade CUDA via OpenCV. Nunca lança."""
    try:
        import cv2

        count = cv2.cuda.getCudaEnabledDeviceCount()
        return GpuProbeResult(available=count > 0, device_count=count)
    except Exception:
        # Captura ampla deliberada — cobre ImportError (sem cv2), AttributeError
        # (cv2 sem submódulo `cuda`) e cv2.error (build sem suporte CUDA que
        # levanta em vez de retornar 0). A promessa "nunca lança" exige isso.
        return GpuProbeResult(available=False, device_count=0)
