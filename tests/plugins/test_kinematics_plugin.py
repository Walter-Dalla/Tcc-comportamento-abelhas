"""Testes do plugin `kinematics` (A-1 a A-4 de docs/research/metadata-extraction-opportunities.md).

Cobre: reta com velocidade constante (aceleração ~0, virada ~0, retidão ~1), curva de
90°+ (sharp_turn_count detecta), buraco de índice de frame (guardas de contiguidade não
quebram nem fabricam passo sobre o buraco), segmento "parado" longo (bouts/latência
plausíveis) e ausência de rota para entity_id=0 (levanta ValueError, mesma convenção de
`SpeedPlugin`/`BorderPlugin`).
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pytest

from src.core.plugin import Plugin
from src.core.schema.geometry import Point3D
from src.core.schema.result import AnalysisContext, AnalysisResult

FPS = 30.0  # make_calibration() default (tests/conftest.py)
DT = 1.0 / FPS


def test_straight_line_constant_speed(
    load_plugin: Callable[..., Plugin],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    # 6 frames, passo de 1cm em linha reta no eixo x: velocidade constante -> aceleração
    # ~0; sem mudança de direção -> ângulo de virada ~0; caminho == deslocamento -> retidão 1.
    points = {i: Point3D(x=float(i), y=0.0, z=0.0) for i in range(6)}
    result = result_factory(points=points)
    ctx = AnalysisContext(result=result)

    plugin = load_plugin("kinematics")
    plugin.run(ctx)  # type: ignore[attr-defined]
    metrics = ctx.result.metrics

    accel = metrics["acceleration"].value
    assert isinstance(accel, dict)
    assert accel  # não vazio: 4 amostras de aceleração para 6 frames contíguos
    for v in accel.values():
        assert v == pytest.approx(0.0, abs=1e-9)
    assert metrics["acceleration_max"].value == pytest.approx(0.0, abs=1e-9)
    assert metrics["deceleration_max"].value == pytest.approx(0.0, abs=1e-9)
    assert metrics["acceleration_rms"].value == pytest.approx(0.0, abs=1e-9)

    turn_angle = metrics["turn_angle"].value
    assert isinstance(turn_angle, dict)
    assert turn_angle
    for v in turn_angle.values():
        assert v == pytest.approx(0.0, abs=1e-9)
    assert metrics["sharp_turn_count"].value == 0

    assert metrics["net_displacement"].value == pytest.approx(5.0)
    assert metrics["straightness_index"].value == pytest.approx(1.0, abs=1e-9)


def test_sharp_turn_detected(
    load_plugin: Callable[..., Plugin],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    # frames 0->1->2 seguem +x; frames 2->3 vira 90 graus para +y. A trinca (1,2,3)
    # produz ângulo de virada de exatamente 90 graus.
    points = {
        0: Point3D(x=0.0, y=0.0, z=0.0),
        1: Point3D(x=1.0, y=0.0, z=0.0),
        2: Point3D(x=2.0, y=0.0, z=0.0),
        3: Point3D(x=2.0, y=1.0, z=0.0),
    }
    result = result_factory(points=points)
    ctx = AnalysisContext(result=result)

    plugin = load_plugin("kinematics")
    plugin.run(ctx)  # type: ignore[attr-defined]
    metrics = ctx.result.metrics

    turn_angle = metrics["turn_angle"].value
    assert isinstance(turn_angle, dict)
    # trinca (0,1,2): reta, ~0 graus; trinca (1,2,3): virada de 90 graus, chaveada pelo
    # índice de frame do meio (2).
    assert turn_angle["1"] == pytest.approx(0.0, abs=1e-9)
    assert turn_angle["2"] == pytest.approx(90.0, abs=1e-6)

    assert metrics["sharp_turn_count"].value == 1
    histogram = metrics["turn_angle_histogram"].value
    assert isinstance(histogram, dict)
    assert histogram["90-108"] == 1

    # duração coberta = (3-0)/30/60 min; taxa = 1 curva / duração
    duration_min = (3 - 0) / FPS / 60.0
    assert metrics["sharp_turn_rate"].value == pytest.approx(1.0 / duration_min)


def test_frame_gap_does_not_fabricate_step(
    load_plugin: Callable[..., Plugin],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    # duas corridas contíguas (0,1,2) e (10,11,12) separadas por um buraco de detecção.
    points = {
        0: Point3D(x=0.0, y=0.0, z=0.0),
        1: Point3D(x=1.0, y=0.0, z=0.0),
        2: Point3D(x=2.0, y=0.0, z=0.0),
        10: Point3D(x=2.0, y=1.0, z=0.0),
        11: Point3D(x=2.0, y=2.0, z=0.0),
        12: Point3D(x=2.0, y=3.0, z=0.0),
    }
    result = result_factory(points=points)
    ctx = AnalysisContext(result=result)

    plugin = load_plugin("kinematics")
    plugin.run(ctx)  # type: ignore[attr-defined]  # não deve levantar/crashar
    metrics = ctx.result.metrics

    # velocidade (interna): só pares (0,1),(1,2),(10,11),(11,12) — nunca (2,10). Logo
    # aceleração só tem chave onde 2 amostras de velocidade são consecutivas: (1,2)->"2"
    # e (11,12)->"12"; nunca através do buraco (2 e 11 diferem por 9, não 1).
    accel = metrics["acceleration"].value
    assert isinstance(accel, dict)
    assert set(accel.keys()) == {"2", "12"}
    # jerk precisaria de 2 amostras de aceleração consecutivas — não há nenhuma aqui.
    assert metrics["jerk"].value == {}

    turn_angle = metrics["turn_angle"].value
    assert isinstance(turn_angle, dict)
    # só uma trinca contígua por corrida: (0,1,2)->chave "1" e (10,11,12)->chave "11".
    assert set(turn_angle.keys()) == {"1", "11"}


def test_parked_segment_bouts(
    load_plugin: Callable[..., Plugin],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    # frames 0-2: movimento rápido (5cm/passo -> 150 cm/s, bem acima do limiar de 0.5).
    # frames 2-6: parado (mesma posição -> velocidade 0, abaixo do limiar).
    # frames 6-8: movimento rápido de novo.
    points = {
        0: Point3D(x=0.0, y=0.0, z=0.0),
        1: Point3D(x=5.0, y=0.0, z=0.0),
        2: Point3D(x=10.0, y=0.0, z=0.0),
        3: Point3D(x=10.0, y=0.0, z=0.0),
        4: Point3D(x=10.0, y=0.0, z=0.0),
        5: Point3D(x=10.0, y=0.0, z=0.0),
        6: Point3D(x=10.0, y=0.0, z=0.0),
        7: Point3D(x=15.0, y=0.0, z=0.0),
        8: Point3D(x=20.0, y=0.0, z=0.0),
    }
    result = result_factory(points=points)
    ctx = AnalysisContext(result=result)

    plugin = load_plugin("kinematics")
    plugin.run(ctx)  # type: ignore[attr-defined]
    metrics = ctx.result.metrics

    assert metrics["active_frames"].value == 4  # frames 1,2,7,8
    assert metrics["rest_frames"].value == 4  # frames 3,4,5,6
    assert metrics["active_fraction"].value == pytest.approx(0.5)
    assert metrics["bout_count"].value == 2  # [1,2] e [7,8]

    expected_bout_duration = (2 - 1 + 1) * DT  # cada bout ativo tem 2 frames
    assert metrics["bout_duration_mean_s"].value == pytest.approx(expected_bout_duration)

    # primeiro frame válido da rota = 0; primeiro frame ativo = 1.
    assert metrics["time_to_first_movement_s"].value == pytest.approx((1 - 0) * DT)

    rest_bouts = metrics["rest_bouts"].value
    assert rest_bouts == [[3, 6]]


def test_missing_route_raises(
    load_plugin: Callable[..., Plugin],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    result = result_factory()
    result.routes = []  # nenhuma rota com entity_id=0
    ctx = AnalysisContext(result=result)
    plugin = load_plugin("kinematics")
    with pytest.raises(ValueError):
        plugin.run(ctx)  # type: ignore[attr-defined]


def test_msd_curve_and_exponent_for_ballistic_motion(
    load_plugin: Callable[..., Plugin],
    result_factory: Callable[..., AnalysisResult],
) -> None:
    # movimento retilíneo uniforme: MSD(lag) = (velocidade*lag)^2 -> expoente ~2 (balístico).
    points = {i: Point3D(x=float(i), y=0.0, z=0.0) for i in range(20)}
    result = result_factory(points=points)
    ctx = AnalysisContext(result=result)

    plugin = load_plugin("kinematics")
    plugin.run(ctx)  # type: ignore[attr-defined]
    metrics = ctx.result.metrics

    msd_curve = metrics["msd_curve"].value
    assert isinstance(msd_curve, dict)
    assert msd_curve["1"] == pytest.approx(1.0)
    assert msd_curve["2"] == pytest.approx(4.0)

    assert "msd_exponent" in metrics
    exponent = metrics["msd_exponent"].value
    assert isinstance(exponent, float)
    assert math.isclose(exponent, 2.0, abs_tol=1e-6)
