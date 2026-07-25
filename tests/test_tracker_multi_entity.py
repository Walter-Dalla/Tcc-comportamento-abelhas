"""Spike de tracker multi-animal — testes de INTERFACE e smoke de candidatos.

Fase 6, workstream A (plano seção 5). O critério de sucesso testado aqui é o de
INTERFACE, não de qualidade de algoritmo:

- os candidatos implementam o MESMO contrato `Tracker` que o `SingleEntityTracker`
  baseline (`update`/`tracks`/`reset`), e são intercambiáveis por substituição
  direta do objeto — drop-in;
- rodando a fixture multi-entidade, produzem ≥2 `entity_id`s estáveis (o baseline
  produz 1, evidenciando por que o spike importa);
- ambos são descobertos e instanciados pelo `PluginRegistry` como plugins
  `kind="tracker"` reais, validados contra a classe-base `Tracker`.

Os smoke tests de métrica usam limiares TOLERANTES de propósito: servem para o
código do spike não apodrecer silenciosamente em refactors futuros, NÃO como bar
de qualidade de produção (a escolha de algoritmo segue pesquisa aberta).
"""

from __future__ import annotations

import pytest

from src.app.plugins import TRACKER_PLUGINS_DIR
from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.schema.detection import FrameDetections
from src.core.stages import Tracker
from src.stages.track.plugin import SingleEntityTracker
from tests.fixtures.tracker.gen_synthetic_detections import build_frames, load_ground_truth
from tests.fixtures.tracker.metrics import compute_metrics
from tests.fixtures.tracker.trajectories import N_FRAMES

CANDIDATES = ("kalman-greedy-tracker", "kalman-hungarian-tracker")


def _load_tracker(name: str, view: str = "top") -> Tracker:
    """Carrega um candidato pelo REGISTRY (não por import direto) — é o caminho
    que um plugin de terceiro percorreria.

    O registry instancia com zero argumentos; para fixar a view usamos a classe
    devolvida (o orquestrador faz o mesmo, um tracker por view).
    """
    registry = PluginRegistry()
    registry.discover([TRACKER_PLUGINS_DIR])
    instance = registry.get(PluginKind.TRACKER, name)
    assert isinstance(instance, Tracker)
    return type(instance)(view)  # type: ignore[call-arg]


def _run(tracker: Tracker) -> list:
    for top, _side in build_frames():
        tracker.update(top)
    return tracker.tracks()


# --- fixture sanity ---------------------------------------------------------
def test_fixture_entities_actually_cross_and_occlude() -> None:
    """Guarda-corpo do bug que a auditoria do plano corrigiu: se A e B nunca
    chegarem à distância de oclusão, a fixture não testa nada de interessante."""
    gt = load_ground_truth()
    assert gt["occlusion_frames"], "fixture sem janela de oclusão — trajetórias não cruzam"
    # a oclusão precisa ser uma janela contígua no meio da sequência, não a borda
    frames = gt["occlusion_frames"]
    assert frames == list(range(min(frames), max(frames) + 1))
    assert 0 < min(frames) < N_FRAMES - 1
    # durante a oclusão o gerador colapsa as duas detecções numa só
    occluded_frame = build_frames()[min(frames)][0]
    assert len(occluded_frame.detections) == 1


# --- critério obrigatório: ≥2 entity_ids estáveis ---------------------------
@pytest.mark.parametrize("name", CANDIDATES)
def test_candidate_produces_at_least_two_stable_entity_ids(name: str) -> None:
    tracks = _run(_load_tracker(name))
    metrics = compute_metrics(tracks, load_ground_truth())

    assert metrics.n_tracks_produced >= 2, "spike falhou: nenhuma capacidade multi-entidade"
    assert len(metrics.stable_entity_ids) >= 2, (
        f"{name}: esperado >=2 entity_ids estáveis atravessando a oclusão, "
        f"obtido {metrics.stable_entity_ids}"
    )
    # sem ids "fantasma": no máximo ground truth + 1 de tolerância (plano seção 5)
    assert metrics.n_tracks_produced <= metrics.n_entities_ground_truth + 1


def test_baseline_single_entity_tracker_collapses_to_one_id() -> None:
    """Controle (plano seção 1.5, tarefa 4): evidencia por que o spike importa."""
    metrics = compute_metrics(_run(SingleEntityTracker("top")), load_ground_truth())
    assert metrics.n_tracks_produced == 1
    assert len(metrics.stable_entity_ids) == 1
    # o harness precisa SINALIZAR que as métricas de identidade são degeneradas aqui
    assert metrics.notes, "harness deve marcar o baseline como sem capacidade multi-entidade"


# --- smoke de qualidade (limiares tolerantes, não bar de produção) ----------
@pytest.mark.parametrize("name", CANDIDATES)
def test_candidate_metrics_within_tolerant_thresholds(name: str) -> None:
    metrics = compute_metrics(_run(_load_tracker(name)), load_ground_truth())
    assert metrics.id_switch_rate <= 0.05
    assert metrics.fragmentation <= metrics.n_entities_ground_truth
    assert all(metrics.post_occlusion_recovery.values()), (
        f"{name}: identidade não recuperada após oclusão: {metrics.post_occlusion_recovery}"
    )


# --- contrato de interface --------------------------------------------------
@pytest.mark.parametrize("name", CANDIDATES)
def test_candidate_satisfies_tracker_abc_like_the_baseline(name: str) -> None:
    tracker = _load_tracker(name)
    assert isinstance(tracker, Tracker)
    # mesma superfície do baseline: nada além de update/tracks/reset é exigido
    for method in ("update", "tracks", "reset"):
        assert callable(getattr(tracker, method))


@pytest.mark.parametrize("name", CANDIDATES)
def test_reset_clears_state(name: str) -> None:
    tracker = _load_tracker(name)
    _run(tracker)
    assert tracker.tracks()
    tracker.reset()
    assert tracker.tracks() == []


@pytest.mark.parametrize("name", CANDIDATES)
def test_empty_detections_do_not_crash_and_leave_holes(name: str) -> None:
    tracker = _load_tracker(name)
    tracker.update(FrameDetections(frame_index=0, view="top", detections=[]))
    assert tracker.tracks() == []


@pytest.mark.parametrize("name", CANDIDATES)
def test_candidate_is_drop_in_for_the_baseline(name: str) -> None:
    """Substituir o baseline pelo candidato não exige NENHUMA outra mudança: mesma
    construção `Cls(view)`, mesmo consumo `update(FrameDetections)` -> `tracks()`."""
    frames = [top for top, _side in build_frames()]

    def drive(cls_instance: Tracker) -> list:
        for f in frames:
            cls_instance.update(f)
        return cls_instance.tracks()

    baseline_tracks = drive(SingleEntityTracker("top"))
    candidate_tracks = drive(_load_tracker(name))

    # ambos devolvem list[Track] com a mesma view; só o nº de entidades difere
    assert {t.view for t in baseline_tracks} == {"top"}
    assert {t.view for t in candidate_tracks} == {"top"}
    assert len(candidate_tracks) > len(baseline_tracks)


# --- descoberta como plugin real -------------------------------------------
@pytest.mark.parametrize("name", CANDIDATES)
def test_candidate_is_discoverable_as_tracker_plugin(name: str) -> None:
    registry = PluginRegistry()
    registry.discover([TRACKER_PLUGINS_DIR])
    manifests = {m.name: m for m in registry.manifests(PluginKind.TRACKER)}
    assert name in manifests
    assert manifests[name].kind is PluginKind.TRACKER


@pytest.mark.parametrize("name", CANDIDATES)
def test_candidate_is_instantiable_by_registry_with_zero_args(name: str) -> None:
    """`PluginRegistry.instantiate()` chama `plugin_cls()` sem argumentos.

    Trava a restrição real do contrato (documentada em `docs/PLUGIN_CONTRACT.md`):
    um plugin só é carregável pelo registry se o construtor for zero-arg. Os
    candidatos dão default a `view` por isso — ao contrário do `SingleEntityTracker`
    da Fase 3, que exige `view` posicional e NÃO é carregável pelo registry hoje
    (lacuna registrada no handoff do workstream).
    """
    registry = PluginRegistry()
    registry.discover([TRACKER_PLUGINS_DIR])
    instance = registry.get(PluginKind.TRACKER, name)
    assert isinstance(instance, Tracker)
