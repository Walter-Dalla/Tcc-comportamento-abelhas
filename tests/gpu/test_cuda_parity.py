"""Testes de paridade CUDA×CPU (Fase 5, plano seção 3) — SÓ com GPU real.

Todos marcados `@pytest.mark.gpu`: pulados automaticamente (via `tests/conftest.py`)
quando nenhum device CUDA é detectado — caso desta máquina de dev (opencv-python do
PyPI, sem módulo cuda) e dos runners padrão do CI. Rodar manualmente com `pytest -m
gpu` numa máquina/container com OpenCV+CUDA.

Assimetria de algoritmo (NÃO reabrir aqui — ver plano seção 3): o detector CPU usa
máximo-estático + absdiff + threshold fixo; o GPU usa MOG2. Só o passo final de
contorno/centroide coincide. Por isso o Teste 2 é EQUIVALÊNCIA COMPORTAMENTAL na
fixture (mesmo alvo, ~mesmo centroide dentro de tolerância), não paridade de bit.
"""

from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.gpu

# Tolerâncias nomeadas (plano seção 3). Ajustáveis por fixture/resolução.
PARITY_MEAN_DIFF_MAX = 2.0  # média de |diff| por pixel, 8 bits
PARITY_MAX_DIFF = 5  # diferença máxima por pixel (arredondamento subpixel)

_POINTS = [[10, 10], [90, 12], [8, 100], [92, 98]]


@pytest.fixture
def bgr_frame() -> np.ndarray:
    rng = np.random.default_rng(99)
    return rng.integers(0, 256, size=(120, 110, 3), dtype=np.uint8)


def test_rectifier_parity_cpu_vs_cuda(bgr_frame: np.ndarray) -> None:
    """Teste 1 — paridade do rectifier isolado (isola do ruído estocástico do MOG2).

    Mesmo frame + mesma homografia via `CpuArrayBackend` e `CudaArrayBackend`; a
    diferença absoluta média por pixel deve ser <= tolerância (folga para
    arredondamento subpixel entre a interpolação CPU e CUDA do warpPerspective)."""
    from src.core.array_backend import CpuArrayBackend, CudaArrayBackend
    from src.core.schema.orientation import CameraRole
    from src.stages.rectify.cuda.plugin import CudaPerspectiveRectifier

    cpu = CudaPerspectiveRectifier(
        _POINTS, None, CameraRole.TOP, 110, 120, backend=CpuArrayBackend()
    )
    gpu = CudaPerspectiveRectifier(
        _POINTS, None, CameraRole.TOP, 110, 120, backend=CudaArrayBackend()
    )

    cpu_img = cpu.rectify(bgr_frame, 0).image.astype(np.int16)
    gpu_img = gpu.rectify(bgr_frame, 0).image.astype(np.int16)

    diff = np.abs(cpu_img - gpu_img)
    assert diff.mean() <= PARITY_MEAN_DIFF_MAX
    assert diff.max() <= PARITY_MAX_DIFF


@pytest.mark.skip(
    reason="Paridade comportamental detector completo (Teste 2, plano seção 3): "
    "requer a fixture de vídeo da Fase 3 + CPU BackgroundSubtractionDetector vs "
    "GPU CudaMOG2Detector com descarte de frames de aquecimento do MOG2. Estruturar "
    "quando o ambiente OpenCV+CUDA existir — ver handoff fase5-backends-gpu."
)
def test_detector_behavioral_parity_placeholder() -> None:  # pragma: no cover
    """Placeholder rastreável do Teste 2 (paridade de detector completo).

    Desenho (plano seção 3): rodar a fixture inteira pelos dois caminhos, comparar
    por frame onde AMBOS detectam — distância de centroide <= 3.0 px
    (PARITY_CENTROID_TOLERANCE_PX), área relativa <= 15%, taxa de discordância de
    presença <= 2%. Não implementado como asserção real ainda porque exige rodar
    MOG2 real (sem hardware CUDA aqui). Fica `skip` explícito, não um teste falso-verde."""
