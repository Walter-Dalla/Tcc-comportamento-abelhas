"""Probe de capacidade CUDA + gate obrigatório (Fase 5).

Dois níveis de API, deliberadamente separados:

- `probe_cuda_devices()` / `cuda_device_count()` — reports NÃO-lançantes. Cobrem
  todos os cenários de indisponibilidade (sem `cv2`, `cv2` sem submódulo `cuda`,
  build sem suporte CUDA que levanta `cv2.error` em vez de retornar 0). Seguros
  para chamar em qualquer lugar, inclusive listagem/diagnóstico.
- `require_cuda()` — o GATE obrigatório da Fase 5. Levanta `GpuNotAvailableError`
  (RuntimeError) se nenhum device CUDA utilizável é encontrado. GPU é REQUISITO,
  não fallback (ver `ARCHITECTURE.md`, "Estratégia GPU").

**Decisão de produto fechada** (ver `docs/plans/fase5-detalhado.md`, topo): o gate
`require_cuda()` roda APENAS quando um processamento real é disparado — dentro de
`Pipeline.run()` (quando `RunRequest.gpu`) e no caminho de análise da CLI/serviço.
NUNCA no boot da GUI/processo Tk, nunca ao abrir telas de configuração
(perspectiva/orientação/borda). Configurar um perfil deve funcionar em qualquer
máquina, com ou sem GPU.

`require_cuda()` NÃO faz `sys.exit` nem log-and-continue nem mostra UI — só levanta.
A apresentação ao usuário (messagebox na GUI, `typer.Exit` na CLI) mora na camada
de app, mantendo `core/` livre de side-effect de processo/UI.

Sem nenhuma dependência de `Plugin`/`PluginRegistry`/`Pipeline` (só `cv2` opcional
e `pydantic`).
"""

from __future__ import annotations

from pydantic import BaseModel


class GpuNotAvailableError(RuntimeError):
    """GPU CUDA é requisito para RODAR o pipeline (ARCHITECTURE.md — Estratégia
    GPU); levantada por `require_cuda()` quando nenhum dispositivo CUDA utilizável
    é encontrado no momento de um `Pipeline.run()`/comando `run`."""


class GpuProbeResult(BaseModel):
    available: bool
    device_count: int
    driver_info: str | None = None


def cuda_device_count() -> int:
    """Wrapper fino e NÃO-lançante sobre `cv2.cuda.getCudaEnabledDeviceCount()`.

    Retorna 0 em qualquer cenário de indisponibilidade: sem GPU física, driver
    ausente, sem `cv2` instalado, OU build do OpenCV sem módulo `cuda` (nesse caso
    `cv2.cuda` nem existe como atributo — `AttributeError` — ou levanta `cv2.error`
    ao ser chamado). Nunca lança."""
    try:
        import cv2

        return int(cv2.cuda.getCudaEnabledDeviceCount())
    except Exception:
        # Captura ampla deliberada — ImportError (sem cv2), AttributeError (cv2 sem
        # submódulo `cuda`) e cv2.error (build sem suporte CUDA). "Nunca lança".
        return 0


def probe_cuda_devices() -> GpuProbeResult:
    """Probe de capacidade CUDA via OpenCV. Nunca lança."""
    count = cuda_device_count()
    return GpuProbeResult(available=count > 0, device_count=count)


def require_cuda(min_devices: int = 1) -> int:
    """Gate obrigatório de GPU. Levanta `GpuNotAvailableError` se
    `cuda_device_count() < min_devices`; retorna a contagem em caso de sucesso
    (útil para log). NÃO faz `sys.exit`, NÃO faz log-and-continue.

    Ponto de chamada — DECIDIDO (ver docstring do módulo e plano da Fase 5): uma
    vez, no início de um processamento real (`Pipeline.run()` com `gpu=True` /
    caminho de análise da CLI), ANTES de instanciar qualquer plugin GPU. NUNCA no
    boot do processo (GUI ou CLI), nunca ao abrir telas de configuração."""
    count = cuda_device_count()
    if count < min_devices:
        raise GpuNotAvailableError(
            f"GPU CUDA obrigatória para processar: {count} dispositivo(s) encontrado(s), "
            f"esperado >= {min_devices}. O pacote PyPI opencv-python não vem com suporte "
            "CUDA — ver docs/plans/fase5-detalhado.md (seção 2) e docs/handoffs/"
            "fase5-backends-gpu-handoff.md para como obter um OpenCV com módulo cuda."
        )
    return count
