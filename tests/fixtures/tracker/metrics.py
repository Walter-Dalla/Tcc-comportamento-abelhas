"""Harness de métricas do spike de tracker (Fase 6, workstream A, tarefa 3).

Recebe a `list[Track]` produzida por um `Tracker` candidato + o ground truth
sintético e calcula, objetivamente (só possível porque a verdade é conhecida por
construção), as métricas INFORMATIVAS da seção 1.3 do plano:

- `id_switches` / `id_switch_rate`: por frame com 2+ entidades-verdade, para cada
  entidade-verdade acha o track mais próximo (por centróide); um switch conta
  quando esse `entity_id` mais-próximo muda em relação ao frame anterior sem que a
  entidade tenha reaparecido de uma oclusão longa.
- `fragmentation`: nº de segmentos contíguos de `Track.points` a mais do que o nº
  de entidades-verdade (0 = 1 segmento por entidade = perfeito).
- `post_occlusion_recovery`: por evento de oclusão, o `entity_id` de cada entidade
  antes é o mesmo depois (recuperação correta) ou trocou.

Estas métricas alimentam o RELATÓRIO comparativo — não são gate de aceite da fase
(o gate é o critério de INTERFACE: ≥2 entity_ids estáveis). Ver plano seção 1.3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.core.schema.track import Track


@dataclass
class TrackerMetrics:
    n_entities_ground_truth: int
    n_tracks_produced: int
    stable_entity_ids: list[int]
    id_switches: int
    id_switch_rate: float
    fragmentation: int
    post_occlusion_recovery: dict[str, bool]
    frames_evaluated: int = 0
    notes: list[str] = field(default_factory=list)


def _nearest_track_id(
    pos: tuple[float, float], tracks: list[Track], frame_index: int
) -> int | None:
    """entity_id do track cujo ponto NESTE frame é o mais próximo de `pos`."""
    best_id: int | None = None
    best_dist = math.inf
    for track in tracks:
        pt = track.points.get(frame_index)
        if pt is None:
            continue
        d = math.dist(pos, (pt.x, pt.y))
        if d < best_dist:
            best_dist = d
            best_id = track.entity_id
    return best_id


def _count_segments(track: Track) -> int:
    """Nº de segmentos contíguos (interrompidos por buraco) em `track.points`."""
    if not track.points:
        return 0
    indices = sorted(track.points)
    segments = 1
    for prev, cur in zip(indices, indices[1:], strict=False):
        if cur != prev + 1:
            segments += 1
    return segments


def compute_metrics(tracks: list[Track], ground_truth: dict) -> TrackerMetrics:
    entity_names: list[str] = ground_truth["entity_names"]
    frames: list[dict] = ground_truth["frames"]
    occlusion_frames: set[int] = set(ground_truth["occlusion_frames"])
    n_gt = len(entity_names)

    # --- ID-switch + associação verdade→track por frame ---------------------
    prev_assignment: dict[str, int | None] = {}
    id_switches = 0
    frames_evaluated = 0
    for frame in frames:
        fi = frame["frame_index"]
        if frame["occluded"]:
            # durante oclusão a verdade colapsa; não conta switch aqui.
            continue
        assignment: dict[str, int | None] = {}
        for name in entity_names:
            ent = frame["entities"][name]
            assignment[name] = _nearest_track_id((ent["x"], ent["y"]), tracks, fi)
        # só conta em frames com 2+ entidades distinguíveis
        if sum(1 for v in assignment.values() if v is not None) >= 2:
            frames_evaluated += 1
            for name in entity_names:
                prev = prev_assignment.get(name)
                cur = assignment[name]
                if prev is not None and cur is not None and cur != prev:
                    # ignora troca logo após oclusão longa (reaparecimento legítimo)
                    if fi - 1 not in occlusion_frames:
                        id_switches += 1
        prev_assignment = assignment

    id_switch_rate = id_switches / frames_evaluated if frames_evaluated else 0.0

    # --- fragmentação -------------------------------------------------------
    total_segments = sum(_count_segments(t) for t in tracks)
    fragmentation = max(0, total_segments - n_gt)

    # --- recuperação pós-oclusão -------------------------------------------
    recovery = _post_occlusion_recovery(tracks, frames, occlusion_frames, entity_names)

    # --- ids estáveis (aparecem antes e depois da oclusão) ------------------
    stable = _stable_entity_ids(tracks, occlusion_frames)

    notes: list[str] = []
    if len(tracks) < n_gt:
        # Caso degenerado (ex. SingleEntityTracker baseline): o tracker não
        # distingue entidade nenhuma, então TODA entidade-verdade casa com o mesmo
        # track. id_switches=0 e recovery=True saem trivialmente verdadeiros e NÃO
        # significam qualidade — significam ausência de capacidade multi-entidade.
        # Ver plano seção 1.5, tarefa 4 ("baseline sem capacidade multi-entidade").
        notes.append(
            f"produziu {len(tracks)} track(s) para {n_gt} entidades-verdade: sem capacidade "
            f"multi-entidade — id_switch/recuperação são trivialmente 'perfeitos' e não "
            f"devem ser lidos como qualidade."
        )

    return TrackerMetrics(
        n_entities_ground_truth=n_gt,
        n_tracks_produced=len(tracks),
        stable_entity_ids=sorted(stable),
        id_switches=id_switches,
        id_switch_rate=id_switch_rate,
        fragmentation=fragmentation,
        post_occlusion_recovery=recovery,
        frames_evaluated=frames_evaluated,
        notes=notes,
    )


def _post_occlusion_recovery(
    tracks: list[Track],
    frames: list[dict],
    occlusion_frames: set[int],
    entity_names: list[str],
) -> dict[str, bool]:
    if not occlusion_frames:
        return {name: True for name in entity_names}
    before_fi = min(occlusion_frames) - 1
    after_fi = max(occlusion_frames) + 1
    recovery: dict[str, bool] = {}
    for name in entity_names:
        before_frame = next((f for f in frames if f["frame_index"] == before_fi), None)
        after_frame = next((f for f in frames if f["frame_index"] == after_fi), None)
        if before_frame is None or after_frame is None:
            recovery[name] = False
            continue
        b = before_frame["entities"][name]
        a = after_frame["entities"][name]
        id_before = _nearest_track_id((b["x"], b["y"]), tracks, before_fi)
        id_after = _nearest_track_id((a["x"], a["y"]), tracks, after_fi)
        recovery[name] = id_before is not None and id_before == id_after
    return recovery


def _stable_entity_ids(tracks: list[Track], occlusion_frames: set[int]) -> set[int]:
    """entity_ids presentes tanto antes quanto depois da janela de oclusão."""
    if not occlusion_frames:
        return {t.entity_id for t in tracks if t.points}
    before_fi = min(occlusion_frames) - 1
    after_fi = max(occlusion_frames) + 1
    stable: set[int] = set()
    for track in tracks:
        has_before = any(fi <= before_fi for fi in track.points)
        has_after = any(fi >= after_fi for fi in track.points)
        if has_before and has_after:
            stable.add(track.entity_id)
    return stable
