"""Gerador determinístico de vídeos de fixture para o golden-file test (Fase 3).

NÃO faz parte do pacote de produção. Renderiza um blob escuro (círculo preenchido)
sobre fundo cinza-claro uniforme, movendo-se ao longo de um caminho 3D sintético
conhecido em cm. Os `.avi` gerados são COMMITADOS em `tests/fixtures/videos/` — não
são regenerados a cada run de CI (determinismo de codec entre máquinas/versões de
OpenCV é frágil o bastante pra não confiar em regerar on-the-fly). Este script fica
disponível pra recriar as fixtures manualmente se um dia precisarem mudar:

    python -m tests.fixtures.generate_fixture_videos

Convenção de eixos da fixture (casada com a orientação de `golden_orientation()`,
cujo `axis_mapping()` resolve x←top.U(+1), y←top.V(+1), z←side.V(+1) — as MESMAS
fontes que o hardcode legado usava: x=top.x, y=top.y, z=side.y):

- vídeo do topo: blob em (cx = x_cm * PX_PER_CM, cy_de_cima = H - y_cm * PX_PER_CM)
- vídeo lateral: blob em (cx = x_cm * PX_PER_CM, cy_de_cima = H - z_cm * PX_PER_CM)

O Detect mede `cy_de_baixo = H - cy_de_cima`, então recupera y_cm/z_cm de volta.
`PX_PER_CM` abaixo é só um parâmetro do gerador — o pipeline recalcula seu próprio
`px_per_cm` a partir das dimensões do frame + `box_cm`.
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

WIDTH = 320
HEIGHT = 240
PX_PER_CM = 20.0  # só parâmetro de renderização
CIRCLE_RADIUS = 10
BG_GRAY = 200
BLOB_GRAY = 30

MAIN_FRAMES = 1200  # > frame_block(500) -> amostra índices 0, 500, 1000 (np.max multi-frame real)
TOP_FPS = 30
SIDE_FPS = 15  # diferente do topo de propósito: golden confirma que fps efetivo = topo

VIDEOS_DIR = Path(__file__).resolve().parent / "videos"


def synthetic_path(frame_index: int, total_frames: int) -> tuple[float, float, float]:
    """Caminho 3D determinístico em cm. Movimento circular em (x,y), subida lenta em z."""
    t = frame_index / total_frames
    x_cm = 5.0 + 3.0 * math.cos(2 * math.pi * t)
    y_cm = 5.0 + 3.0 * math.sin(2 * math.pi * t)
    z_cm = 2.0 + 1.5 * t
    return x_cm, y_cm, z_cm


def _draw(cx_px: float, cy_from_top: float) -> np.ndarray:
    frame = np.full((HEIGHT, WIDTH, 3), BG_GRAY, dtype=np.uint8)
    cv2.circle(frame, (int(round(cx_px)), int(round(cy_from_top))), CIRCLE_RADIUS,
               (BLOB_GRAY, BLOB_GRAY, BLOB_GRAY), thickness=-1)
    return frame


def _writer(path: Path, fps: int) -> cv2.VideoWriter:
    # FFV1 = lossless -> decode pixel-exato entre versões de OpenCV (evita drift de
    # centroide que um codec lossy introduziria no golden).
    fourcc = cv2.VideoWriter_fourcc(*"FFV1")  # type: ignore[attr-defined]  # existe em runtime (4.9/5.0); stub varia
    writer = cv2.VideoWriter(str(path), fourcc, fps, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError(f"VideoWriter FFV1 não abriu para {path} — codec indisponível")
    return writer


def _render_pair(top_path: Path, side_path: Path, top_frames: int, side_frames: int,
                 path_total: int) -> None:
    top = _writer(top_path, TOP_FPS)
    side = _writer(side_path, SIDE_FPS)
    try:
        max_frames = max(top_frames, side_frames)
        for i in range(max_frames):
            x_cm, y_cm, z_cm = synthetic_path(i, path_total)
            if i < top_frames:
                top.write(_draw(x_cm * PX_PER_CM, HEIGHT - y_cm * PX_PER_CM))
            if i < side_frames:
                side.write(_draw(x_cm * PX_PER_CM, HEIGHT - z_cm * PX_PER_CM))
    finally:
        top.release()
        side.release()


def generate_all() -> None:
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    # Fixture principal: top e side de mesmo comprimento (1200).
    _render_pair(
        VIDEOS_DIR / "main_top.avi", VIDEOS_DIR / "main_side.avi",
        top_frames=MAIN_FRAMES, side_frames=MAIN_FRAMES, path_total=MAIN_FRAMES,
    )
    # Fixture de comprimentos diferentes: top=1200, side=1600 (diferença ATRAVESSA a
    # fronteira de amostragem 500 -> side tem uma amostra em 1500 além do fim do top).
    # Valida a decisão da seção 2.2/3.4: o passe 1 do modelo de fundo lê o vídeo
    # inteiro da SUA view (side até 1600), a passada pareada trunca no mais curto (1200).
    _render_pair(
        VIDEOS_DIR / "uneven_top.avi", VIDEOS_DIR / "uneven_side.avi",
        top_frames=1200, side_frames=1600, path_total=1200,
    )
    print(f"Fixtures geradas em {VIDEOS_DIR}")


if __name__ == "__main__":
    generate_all()
