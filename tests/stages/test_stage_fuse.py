"""Testes do estágio Fuse (Fase 3): axis_sources, px/cm por eixo (bug #3), cm na rota."""

from __future__ import annotations

import pytest

from src.core.schema.geometry import Point2D, Point3D
from src.core.schema.orientation import AxisSource, BoxAxis, CameraRole, ImageAxis
from src.core.schema.track import Track
from src.stages.fuse.plugin import FuseConfigError, Fusion, build_border_region
from tests.fixtures.golden_config import golden_orientation


def _tracks(top_pts: dict[int, Point2D], side_pts: dict[int, Point2D]) -> tuple[Track, Track]:
    return (
        Track(entity_id=0, view="top", points=top_pts),
        Track(entity_id=0, view="side", points=side_pts),
    )


def test_axis_mapping_reproduces_legacy_sources() -> None:
    """Y e Z continuam vindo de uma única câmera como no legado (route_module:
    y=top[1], z=side[1]). X, porém, agora é observado por AMBAS as câmeras
    (top.U e side.U) e é feito a MÉDIA das duas leituras em `Fusion.fuse()` — ver
    decisão do dono do projeto que substitui a antiga política
    'TOP-camera-vence-empate' (sob a qual X vinha só de top.U)."""
    sources = golden_orientation().axis_sources()
    assert sources[BoxAxis.X] == [
        AxisSource(camera=CameraRole.TOP, image_axis=ImageAxis.U, sign=1),
        AxisSource(camera=CameraRole.SIDE, image_axis=ImageAxis.U, sign=1),
    ]
    assert sources[BoxAxis.Y] == [AxisSource(camera=CameraRole.TOP, image_axis=ImageAxis.V, sign=1)]
    assert sources[BoxAxis.Z] == [AxisSource(camera=CameraRole.SIDE, image_axis=ImageAxis.V, sign=1)]


def test_px_per_cm_is_per_axis_not_median() -> None:
    """Bug #3: o legado derivava as 3 razões px/cm todas de height_side (mediana
    espúria). Agora cada eixo usa a dimensão de pixel do eixo de imagem que o
    observa. top_shape=(240,320), side_shape=(240,320), box=(16,12,12):
      x <- top.U (width 320) / 16 = 20
      y <- top.V (height 240) / 12 = 20
      z <- side.V (height 240) / 12 = 20
    """
    top, side = _tracks(
        {0: Point2D(x=0.0, y=0.0)}, {0: Point2D(x=0.0, y=0.0)}
    )
    _routes, calib = Fusion().fuse(
        top, side, golden_orientation(), Point3D(x=16.0, y=12.0, z=12.0),
        fps=30.0, top_shape=(240, 320), side_shape=(240, 320),
    )
    assert calib.px_per_cm.x == pytest.approx(20.0)
    assert calib.px_per_cm.y == pytest.approx(20.0)
    assert calib.px_per_cm.z == pytest.approx(20.0)


def test_px_per_cm_distinct_when_box_dims_differ() -> None:
    # box não-cúbica -> razões distintas por eixo (prova que não é a mesma razão pra todos)
    top, side = _tracks({0: Point2D(x=0.0, y=0.0)}, {0: Point2D(x=0.0, y=0.0)})
    _routes, calib = Fusion().fuse(
        top, side, golden_orientation(), Point3D(x=32.0, y=24.0, z=8.0),
        fps=30.0, top_shape=(240, 320), side_shape=(240, 320),
    )
    assert calib.px_per_cm.x == pytest.approx(10.0)  # 320/32
    assert calib.px_per_cm.y == pytest.approx(10.0)  # 240/24
    assert calib.px_per_cm.z == pytest.approx(30.0)  # 240/8


def test_route_is_in_cm() -> None:
    """X agora é a MÉDIA de top.U e side.U (ambos observam X nesta orientação —
    ver test_axis_mapping_reproduces_legacy_sources). px_per_cm=20 em todos os
    eixos (box 16x12x12 cm, frames 320x240): top.x=40.0 -> 40/20=2.0 cm; side.x=80.0
    -> 80/20=4.0 cm; média = (2.0+4.0)/2 = 3.0 cm. Y vem só de top.V (60/20=3.0,
    inalterado) e Z só de side.V (80/20=4.0, mesmo valor de side.x mas eixo
    diferente — não confundir: aqui é side.y=80.0 alimentando Z, não side.x)."""
    top, side = _tracks(
        {0: Point2D(x=40.0, y=60.0)}, {0: Point2D(x=80.0, y=80.0)}
    )
    routes, _calib = Fusion().fuse(
        top, side, golden_orientation(), Point3D(x=16.0, y=12.0, z=12.0),
        fps=30.0, top_shape=(240, 320), side_shape=(240, 320),
    )
    pt = routes[0].points[0]
    assert pt.x == pytest.approx(3.0)  # média de top.x=2.0 e side.x=4.0
    assert pt.y == pytest.approx(3.0)  # top.V, sinal +1, único
    assert pt.z == pytest.approx(4.0)  # side.V, sinal +1, único


def test_fuse_uses_index_intersection() -> None:
    top, side = _tracks(
        {0: Point2D(x=0.0, y=0.0), 1: Point2D(x=20.0, y=20.0), 2: Point2D(x=40.0, y=40.0)},
        {1: Point2D(x=0.0, y=20.0), 2: Point2D(x=0.0, y=40.0)},  # sem frame 0
    )
    routes, _calib = Fusion().fuse(
        top, side, golden_orientation(), Point3D(x=16.0, y=12.0, z=12.0),
        fps=30.0, top_shape=(240, 320), side_shape=(240, 320),
    )
    assert set(routes[0].points) == {1, 2}  # só onde as duas views têm ponto


def test_box_cm_zero_raises() -> None:
    top, side = _tracks({0: Point2D(x=0.0, y=0.0)}, {0: Point2D(x=0.0, y=0.0)})
    with pytest.raises(FuseConfigError):
        Fusion().fuse(
            top, side, golden_orientation(), Point3D(x=0.0, y=12.0, z=12.0),
            fps=30.0, top_shape=(240, 320), side_shape=(240, 320),
        )


def test_build_border_region_converts_pixels_to_cm() -> None:
    # retângulo de borda em pixel (from-top); box_cm=(16,12,12) reproduz px_per_cm=20
    # em todos os eixos com frames 320x240 (mesma fixture golden: 320/16=20, 240/12=20).
    # X tem 2 fontes (top.U e side.U) mas rect é IDÊNTICO nas duas views e as razões
    # batem -> a média não muda o resultado (sanity check da via de 2 fontes).
    rect = [Point2D(x=60.0, y=100.0), Point2D(x=140.0, y=100.0),
            Point2D(x=60.0, y=180.0), Point2D(x=140.0, y=180.0)]
    region = build_border_region(
        golden_orientation(), Point3D(x=16.0, y=12.0, z=12.0),
        border_points_top=rect, border_points_side=rect,
        top_shape=(240, 320), side_shape=(240, 320),
    )
    # x <- top.U: pixels 60..140 /20 = 3..7
    assert region.bounds["x"] == pytest.approx((3.0, 7.0))
    # y <- top.V: (240-180, 240-100)=(60,140) /20 = (3,7) (flip de v)
    assert region.bounds["y"] == pytest.approx((3.0, 7.0))
    assert region.bounds["z"] == pytest.approx((3.0, 7.0))
