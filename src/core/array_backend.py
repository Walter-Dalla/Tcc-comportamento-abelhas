"""`ArrayBackend` — abstração numpy (CPU) vs `cv2.cuda_GpuMat` (GPU) (Fase 5).

Existe para que um frame permaneça RESIDENTE na GPU ao atravessar Rectify→Detect
sem round-trip pra RAM (ver `ARCHITECTURE.md`, "Estratégia GPU"). O `handle`
opaco que trafega entre os métodos é um `np.ndarray` no backend CPU e um
`cv2.cuda_GpuMat` no backend CUDA — o estágio que usa o backend nunca inspeciona
o tipo concreto do handle, só o passa adiante.

Escopo mínimo necessário para os dois estágios pesados desta fase:
- Rectify: `upload` → `warp_perspective` → `cvt_color_gray` → `download`.
- Detect (MOG2): `upload` da imagem retificada; a subtração de fundo em si roda no
  `cv2.cuda_BackgroundSubtractorMOG2` (fora deste protocolo), e o `download` traz
  a máscara de foreground de volta pra CPU.

**Nota de escopo importante (limitação real do `cv2.cuda`, não escolha de design
evitável)**: `cv2.cuda` NÃO expõe `findContours`/`moments` utilizáveis em Python
de forma prática. Logo, no caminho GPU, só o warp de perspectiva (`cudawarping`),
a conversão de cor (`cudaimgproc`) e a subtração de fundo MOG2 (`cudabgsegm`) rodam
de fato na GPU; a extração do centroide do maior contorno (o passo final, comum ao
caminho CPU) continua em CPU sobre a máscara já baixada. Deixar isto explícito
evita a expectativa de "tudo roda na GPU".

Migração futura pra CuPy/PyTorch é só outro `ArrayBackend` — a interface não muda.
"""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, runtime_checkable

import numpy as np

from src.core.gpu import GpuNotAvailableError, require_cuda


@runtime_checkable
class ArrayBackend(Protocol):
    """Protocolo estrutural — qualquer objeto com estes métodos serve. `name` é só
    para logs/manifests, nunca para lógica de branch (o polimorfismo é o backend)."""

    name: ClassVar[str]

    def upload(self, frame: np.ndarray) -> Any:
        """CPU: retorna o próprio ndarray. CUDA: `cv2.cuda_GpuMat().upload(frame)`."""
        ...

    def download(self, handle: Any) -> np.ndarray:
        """Inverso de `upload` — sempre retorna ndarray em RAM (fronteira de saída)."""
        ...

    def warp_perspective(self, handle: Any, matrix: np.ndarray, dsize: tuple[int, int]) -> Any:
        """CPU: `cv2.warpPerspective`. CUDA: `cv2.cuda.warpPerspective`."""
        ...

    def cvt_color_gray(self, handle: Any) -> Any:
        """CPU: `cv2.cvtColor(..., COLOR_BGR2GRAY)`. CUDA: `cv2.cuda.cvtColor`."""
        ...

    def release(self, handle: Any) -> None:
        """No-op em CPU. Em CUDA, ponto de extensão para reciclar `GpuMat` de um pool
        (otimização futura, não obrigatória nesta versão)."""
        ...


class CpuArrayBackend:
    """Backend CPU: `handle` é um `np.ndarray`; upload/download são identidade.

    Existe por dois motivos: (a) os testes de paridade têm os dois lados do MESMO
    protocolo, e (b) permite exercitar o algoritmo dos estágios CUDA
    (`CudaPerspectiveRectifier`, etc.) SEM hardware CUDA, injetando este backend —
    o caminho numérico é idêntico ao das operações `cv2.*` diretas.

    Decisão explícita (plano Fase 5, seção 1.2): NÃO é obrigatório reescrever o
    `CpuPerspectiveRectifier` de produção (já validado pelo golden-file da Fase 3)
    para usar este backend; ele existe para teste/paridade e para os estágios CUDA."""

    name: ClassVar[str] = "cpu"

    def upload(self, frame: np.ndarray) -> np.ndarray:
        return frame

    def download(self, handle: np.ndarray) -> np.ndarray:
        return handle

    def warp_perspective(
        self, handle: np.ndarray, matrix: np.ndarray, dsize: tuple[int, int]
    ) -> np.ndarray:
        import cv2

        return cv2.warpPerspective(handle, matrix, dsize)

    def cvt_color_gray(self, handle: np.ndarray) -> np.ndarray:
        import cv2

        return cv2.cvtColor(handle, cv2.COLOR_BGR2GRAY)

    def release(self, handle: np.ndarray) -> None:
        return None


class CudaArrayBackend:
    """Backend CUDA: `handle` é um `cv2.cuda_GpuMat`; as operações rodam na GPU.

    Construção guardada: exige um build de OpenCV com o módulo `cuda` (e os módulos
    de `opencv_contrib` `cudawarping`/`cudaimgproc`). Em uma build sem CUDA o
    atributo `cv2.cuda` nem existe / não tem device — a construção levanta
    `GpuNotAvailableError` com mensagem clara, em vez de virar silenciosamente um
    no-op ou estourar um `AttributeError` cru fundo do OpenCV.

    NÃO instanciável nesta máquina de dev (opencv-python do PyPI não traz CUDA) —
    ver `docs/handoffs/fase5-backends-gpu-handoff.md`. O código é estruturalmente
    correto contra a superfície documentada da API `cv2.cuda.*`, mas só exercitável
    numa máquina/container com OpenCV+CUDA real."""

    name: ClassVar[str] = "cuda"

    def __init__(self) -> None:
        import cv2

        # Falha alto e claro se não há CUDA utilizável, ANTES de tentar tocar em
        # `cv2.cuda.*` (que estouraria um AttributeError/cv2.error cru).
        require_cuda()
        if not hasattr(cv2, "cuda"):
            raise GpuNotAvailableError(
                "OpenCV instalado não tem o submódulo `cuda` — build sem "
                "-DWITH_CUDA=ON. Ver docs/handoffs/fase5-backends-gpu-handoff.md."
            )
        self._cv2 = cv2

    # Os `# type: ignore[attr-defined]` abaixo são a fricção conhecida do plano Fase 5
    # (seção 5): os stubs de tipo do OpenCV disponíveis não declaram os símbolos de
    # `cv2.cuda`/`cudawarping`/`cudaimgproc` (módulos contrib+CUDA ausentes na wheel
    # padrão). Decisão de time: ignores PONTUAIS documentados, não silenciar mypy
    # globalmente para o módulo.
    def upload(self, frame: np.ndarray) -> Any:
        gpu_mat = self._cv2.cuda_GpuMat()  # type: ignore[attr-defined]
        gpu_mat.upload(frame)
        return gpu_mat

    def download(self, handle: Any) -> np.ndarray:
        result: np.ndarray = handle.download()
        return result

    def warp_perspective(self, handle: Any, matrix: np.ndarray, dsize: tuple[int, int]) -> Any:
        return self._cv2.cuda.warpPerspective(handle, matrix, dsize)  # type: ignore[attr-defined]

    def cvt_color_gray(self, handle: Any) -> Any:
        return self._cv2.cuda.cvtColor(handle, self._cv2.COLOR_BGR2GRAY)  # type: ignore[attr-defined]

    def release(self, handle: Any) -> None:
        # GpuMat expõe `.release()`; em versões onde não existe, no-op tolerante.
        releaser = getattr(handle, "release", None)
        if callable(releaser):
            releaser()
