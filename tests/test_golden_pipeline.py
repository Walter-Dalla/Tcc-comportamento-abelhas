"""Golden-file + memória + validação independente da pipeline CPU completa (Fase 3).

Este é o guard-rail principal da fase (seção 5/7 do plano): estágios isolados
corretos NÃO implicam composição correta. Aqui a pipeline inteira
(Capture→Rectify→Detect→Track→Fuse + metadata) roda sobre vídeos de fixture
commitados e o `AnalysisResult` é comparado com uma referência commitada.

Tolerâncias (seção 5.3):
- determinístico sem acumulação (px_per_cm, box_cm, pontos de rota): abs=1e-6
- soma acumulada (distance_total, average_speed, speed por frame): abs=1e-4
- estrutural (índices de frame, entity_id, contagem, contagens de borda): exato
"""

from __future__ import annotations

import tracemalloc
from pathlib import Path

import pytest

from src.core.schema.result import AnalysisResult
from src.stages.orchestration import run_cpu_analysis
from tests.fixtures.generate_fixture_videos import MAIN_FRAMES, synthetic_path
from tests.fixtures.golden_config import VIDEOS_DIR, golden_profile

GOLDEN_PATH = Path(__file__).resolve().parent / "fixtures" / "golden" / "expected_result.json"

pytestmark = pytest.mark.skipif(
    not (VIDEOS_DIR / "main_top.avi").exists(),
    reason="vídeos de fixture ausentes — rode `python -m tests.fixtures.generate_fixture_videos`",
)


@pytest.fixture(scope="module")
def actual() -> AnalysisResult:
    return run_cpu_analysis(golden_profile())


@pytest.fixture(scope="module")
def expected() -> AnalysisResult:
    return AnalysisResult.model_validate_json(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_golden_calibration(actual: AnalysisResult, expected: AnalysisResult) -> None:
    assert actual.calibration.fps == expected.calibration.fps  # estrutural: fps do topo (30, não 15)
    for axis in ("x", "y", "z"):
        assert getattr(actual.calibration.px_per_cm, axis) == pytest.approx(
            getattr(expected.calibration.px_per_cm, axis), abs=1e-6
        )
        assert getattr(actual.calibration.box_cm, axis) == pytest.approx(
            getattr(expected.calibration.box_cm, axis), abs=1e-6
        )


def test_golden_route_structural_and_values(
    actual: AnalysisResult, expected: AnalysisResult
) -> None:
    a_route = actual.routes[0]
    e_route = expected.routes[0]
    # estrutural: exato
    assert a_route.entity_id == e_route.entity_id
    assert set(a_route.points) == set(e_route.points)
    assert len(a_route.points) == len(e_route.points)
    # valores: determinístico sem acumulação -> abs=1e-6
    for idx, e_point in e_route.points.items():
        a_point = a_route.points[idx]
        assert a_point.x == pytest.approx(e_point.x, abs=1e-6)
        assert a_point.y == pytest.approx(e_point.y, abs=1e-6)
        assert a_point.z == pytest.approx(e_point.z, abs=1e-6)


def test_golden_metrics(actual: AnalysisResult, expected: AnalysisResult) -> None:
    # somas acumuladas -> abs=1e-4
    assert actual.metrics["distance_total"].value == pytest.approx(
        expected.metrics["distance_total"].value, abs=1e-4
    )
    assert actual.metrics["average_speed"].value == pytest.approx(
        expected.metrics["average_speed"].value, abs=1e-4
    )
    a_speed = actual.metrics["speed"].value
    e_speed = expected.metrics["speed"].value
    assert isinstance(a_speed, dict) and isinstance(e_speed, dict)
    assert set(a_speed) == set(e_speed)  # estrutural
    for key, e_val in e_speed.items():
        assert a_speed[key] == pytest.approx(e_val, abs=1e-4)
    # contagens de borda -> estrutural, exato
    for key in ("time_border_x", "time_border_y", "time_border_z"):
        assert actual.metrics[key].value == expected.metrics[key].value


def test_golden_border_region(actual: AnalysisResult, expected: AnalysisResult) -> None:
    assert actual.border_region is not None
    assert expected.border_region is not None
    for axis in ("x", "y", "z"):
        a_lo, a_hi = actual.border_region.bounds[axis]  # type: ignore[index]
        e_lo, e_hi = expected.border_region.bounds[axis]  # type: ignore[index]
        assert a_lo == pytest.approx(e_lo, abs=1e-6)
        assert a_hi == pytest.approx(e_hi, abs=1e-6)


def test_recovered_route_approximates_synthetic(actual: AnalysisResult) -> None:
    """Validação independente (seção 5.2): a rota recuperada aproxima o caminho
    sintético conhecido — evita commitar um golden que já contém um bug. Tolerância
    generosa (0.5 cm) absorve discretização de pixel/contorno."""
    route = actual.routes[0]
    assert len(route.points) == MAIN_FRAMES  # nenhuma detecção perdida
    for idx, point in route.points.items():
        ex, ey, ez = synthetic_path(idx, MAIN_FRAMES)
        assert point.x == pytest.approx(ex, abs=0.5)
        assert point.y == pytest.approx(ey, abs=0.5)
        assert point.z == pytest.approx(ez, abs=0.5)


def test_fps_comes_from_top_camera(actual: AnalysisResult) -> None:
    """Fidelidade ao legado: fps efetivo = vídeo do topo (30), não do lateral (15)."""
    assert actual.calibration.fps == 30.0


def test_uneven_length_truncates_at_shorter(actual: AnalysisResult) -> None:
    """Vídeos top(1200)/side(1600) de comprimentos diferentes: a passada pareada
    para no mais curto (1200 rotas), e o modelo de fundo por-view lê o vídeo inteiro
    da SUA câmera (seção 2.2/3.4). Como top e os primeiros 1200 frames de side são
    idênticos à fixture principal — e o modelo de fundo (np.max de blobs escuros) é
    invariante às posições amostradas —, a rota resultante deve bater EXATAMENTE com
    a fixture principal."""
    uneven = run_cpu_analysis(
        golden_profile(name="uneven", top="uneven_top.avi", side="uneven_side.avi")
    )
    u_route = uneven.routes[0]
    assert len(u_route.points) == MAIN_FRAMES  # truncou no mais curto, não 1600
    a_route = actual.routes[0]
    assert set(u_route.points) == set(a_route.points)
    for idx, a_point in a_route.points.items():
        u_point = u_route.points[idx]
        assert u_point.x == a_point.x
        assert u_point.y == a_point.y
        assert u_point.z == a_point.z


def test_memory_bounded() -> None:
    """Streaming retém O(1) frame por vez (+ ~3 amostras/view do modelo de fundo).
    Teto de 50 MB: discriminante porque o código legado bufferizava o vídeo inteiro
    (~88 MB/view de frames retificados + a lista de diffs -> ~176 MB/view na fixture
    de 1200 frames 320x240), muito acima de 50 MB. Guarda-corpo grosseiro (tracemalloc
    é cross-platform, ao contrário de resource.getrusage), não medição de precisão."""
    tracemalloc.start()
    try:
        run_cpu_analysis(golden_profile())
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    ceiling = 50 * 1024 * 1024
    assert peak < ceiling, f"pico {peak / 1024 / 1024:.1f} MB excedeu o teto de 50 MB"
