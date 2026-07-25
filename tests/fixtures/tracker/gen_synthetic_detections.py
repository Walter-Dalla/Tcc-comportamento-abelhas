"""Gerador de fixture de nível-unidade: `FrameDetections` sintéticas + ground truth.

Fase 6, workstream A, tarefa 1 do `docs/plans/fase6-detalhado.md`. Produz, para N
frames, um par `(top, side)` de `FrameDetections` seguindo as trajetórias de
`trajectories.py`, e o ground truth por frame (posição real de cada entidade
nomeada + flag `occluded`). Ciclo de avaliação rápido: não depende de Detect nem
de codificação de vídeo.

Durante a janela de oclusão da view de topo, as duas detecções colapsam numa
ÚNICA `Detection` (centróide médio, bbox união) — replicando o que o
`BackgroundSubtractionDetector` real veria ao observar um contorno de dois blobs
sobrepostos. A view lateral mantém sempre 2 detecções separadas.

Rodar como script (`python -m tests.fixtures.tracker.gen_synthetic_detections`)
reescreve o `ground_truth.json` commitado.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from src.core.schema.detection import BBox, Detection, FrameDetections
from src.core.schema.geometry import Point2D
from tests.fixtures.tracker import trajectories as tj

_GROUND_TRUTH_PATH = Path(__file__).with_name("ground_truth.json")
_AREA = math.pi * tj.RADIUS**2


def _detection(x: float, y: float, radius: float, area: float) -> Detection:
    return Detection(
        centroid=Point2D(x=x, y=y),
        bbox=BBox(x=x - radius, y=y - radius, w=2 * radius, h=2 * radius),
        area=area,
    )


def _merged_detection(
    a: tuple[float, float], b: tuple[float, float]
) -> Detection:
    """Blob único quando duas entidades ocluem: centróide médio, bbox união."""
    cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    min_x = min(a[0], b[0]) - tj.RADIUS
    min_y = min(a[1], b[1]) - tj.RADIUS
    max_x = max(a[0], b[0]) + tj.RADIUS
    max_y = max(a[1], b[1]) + tj.RADIUS
    return Detection(
        centroid=Point2D(x=cx, y=cy),
        bbox=BBox(x=min_x, y=min_y, w=max_x - min_x, h=max_y - min_y),
        area=2 * _AREA,
    )


def build_frames() -> list[tuple[FrameDetections, FrameDetections]]:
    """Lista por frame de `(top, side)` FrameDetections."""
    occluded = set(tj.occlusion_frames())
    frames: list[tuple[FrameDetections, FrameDetections]] = []
    for t in range(tj.N_FRAMES):
        a_top, b_top = tj.pos_a_top(t), tj.pos_b_top(t)
        a_side, b_side = tj.pos_a_side(t), tj.pos_b_side(t)

        if t in occluded:
            top_dets = [_merged_detection(a_top, b_top)]
        else:
            # A antes de B (ordem determinística => id estável por primeira aparição).
            top_dets = [
                _detection(*a_top, tj.RADIUS, _AREA),
                _detection(*b_top, tj.RADIUS, _AREA),
            ]
        side_dets = [
            _detection(*a_side, tj.RADIUS, _AREA),
            _detection(*b_side, tj.RADIUS, _AREA),
        ]
        frames.append(
            (
                FrameDetections(frame_index=t, view="top", detections=top_dets),
                FrameDetections(frame_index=t, view="side", detections=side_dets),
            )
        )
    return frames


def build_ground_truth() -> dict:
    """Ground truth por frame: posição real de cada entidade + flag `occluded`."""
    occluded = set(tj.occlusion_frames())
    frames = []
    for t in range(tj.N_FRAMES):
        a_top, b_top = tj.pos_a_top(t), tj.pos_b_top(t)
        frames.append(
            {
                "frame_index": t,
                "occluded": t in occluded,
                "entities": {
                    "entity_A": {"x": a_top[0], "y": a_top[1]},
                    "entity_B": {"x": b_top[0], "y": b_top[1]},
                },
            }
        )
    return {
        "view": "top",
        "n_frames": tj.N_FRAMES,
        "radius": tj.RADIUS,
        "occlusion_dist": tj.OCCLUSION_DIST,
        "occlusion_frames": sorted(occluded),
        "entity_names": ["entity_A", "entity_B"],
        "frames": frames,
    }


def load_ground_truth() -> dict:
    return json.loads(_GROUND_TRUTH_PATH.read_text(encoding="utf-8"))


def write_ground_truth() -> Path:
    _GROUND_TRUTH_PATH.write_text(
        json.dumps(build_ground_truth(), indent=2), encoding="utf-8"
    )
    return _GROUND_TRUTH_PATH


if __name__ == "__main__":
    path = write_ground_truth()
    gt = load_ground_truth()
    print(f"ground truth escrito em {path}")
    print(f"frames de oclusão (topo): {gt['occlusion_frames']}")
