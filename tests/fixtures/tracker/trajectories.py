"""Trajetórias paramétricas da fixture multi-entidade (Fase 6, workstream A).

FONTE ÚNICA DE VERDADE das trajetórias — reusada pelo gerador de detecções de
nível-unidade (`gen_synthetic_detections.py`), pelo ground truth e por qualquer
gerador de vídeo futuro. Parametrização exata (reprodutível) da seção 1.2(a) do
`docs/plans/fase6-detalhado.md`, com a correção de auditoria já aplicada (as
entidades A e B compartilham a MESMA baseline vertical, fase oposta, para de fato
cruzarem e colapsarem em oclusão — sem isso a janela de cruzamento ficava vazia).

Convenções:
- Frame index `t` = 0..N_FRAMES-1.
- View de TOPO: onde A e B cruzam em x e ocluem (mesma faixa vertical).
- View LATERAL: projeção trivial em que A e B permanecem SEPARADAS (faixas de x
  distintas, sem oclusão) — o foco do spike é o comportamento do `Tracker` na view
  de topo, não a reconstrução do `Fuse`. Manter a lateral separável dá ao teste de
  integração ids limpos por-view para parear entre views (ver handoff — pareamento
  cross-view real é o candidato 3, pesquisa aberta).
"""

from __future__ import annotations

import math

N_FRAMES = 150
RADIUS = 12.0  # raio do blob de cada entidade (px)
OCCLUSION_DIST = 2 * RADIUS  # centróides mais próximos que isto => um único blob


def pos_a_top(t: int) -> tuple[float, float]:
    """Entidade A na view de topo: esquerda→direita, oscilação vertical leve."""
    return (40.0 + 4.0 * t, 100.0 + 15.0 * math.sin(2 * math.pi * t / 60.0))


def pos_b_top(t: int) -> tuple[float, float]:
    """Entidade B na view de topo: direita→esquerda, mesma baseline (fase oposta)."""
    return (560.0 - 4.0 * t, 100.0 - 15.0 * math.sin(2 * math.pi * t / 60.0))


def pos_a_side(t: int) -> tuple[float, float]:
    """Entidade A na view lateral (projeção trivial, faixa de x baixa, separável)."""
    return (120.0, 100.0 + 15.0 * math.sin(2 * math.pi * t / 60.0))


def pos_b_side(t: int) -> tuple[float, float]:
    """Entidade B na view lateral (projeção trivial, faixa de x alta, separável)."""
    return (400.0, 100.0 - 15.0 * math.sin(2 * math.pi * t / 60.0))


def top_distance(t: int) -> float:
    ax, ay = pos_a_top(t)
    bx, by = pos_b_top(t)
    return math.dist((ax, ay), (bx, by))


def occlusion_frames() -> list[int]:
    """Frames em que A e B colapsam num único blob na view de topo (dist < 2R).

    Calculado a partir da geometria (não hardcoded 'no olho') — é o ground truth
    da janela de oclusão da seção 1.2(a) do plano.
    """
    return [t for t in range(N_FRAMES) if top_distance(t) < OCCLUSION_DIST]
