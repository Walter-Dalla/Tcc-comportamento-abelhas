"""Testes do estágio Fuse (Fase 3): axis_mapping, px/cm por eixo (bug #3), cm na rota."""

from __future__ import annotations

import pytest

from src.core.schema.geometry import Point2D, Point3D
from src.core.schema.orientation import CameraRole, ImageAxis
from src.core.schema.track import Track
from src.stages.fuse.plugin import FuseConfigError, Fusion, build_border_region
from tests.fixtures.golden_config import golden_orientation


def _tracks(top_pts: dict[int, Point2D], side_pts: dict[int, Point2D]) -> tuple[Track, Track]:
    return (
        Track(entity_id=0, view="top", points=top_pts),
        Track(entity_id=0, view="side", points=side_pts),
    )


def test_axis_mapping_reproduces_legacy_sources() -> None:
    """Regressão do caso comum (bug #3 / seção 4.1): a orientação da fixture faz
    axis_mapping() resolver x←top.U, y←top.V, z←side.V — as MESMAS fontes que o
    hardcode legado (route_module: x=top[0], y=top[1], z=side[1]). Garante que a
    generalização por orientação não regride o caso que o sistema legado tratava."""
    mapping = golden_orientation().axis_mapping()
    assert (mapping.x.camera, mapping.x.image_axis) == (CameraRole.TOP, ImageAxis.U)
    assert (mapping.y.camera, mapping.y.image_axis) == (CameraRole.TOP, ImageAxis.V)
    assert (mapping.z.camera, mapping.z.image_axis) == (CameraRole.SIDE, ImageAxis.V)


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
    # px_per_cm todos 20; ponto top (40, 60) -> x=40/20=2, y=60/20=3; side y=80 -> z=80/20=4
    top, side = _tracks(
        {0: Point2D(x=40.0, y=60.0)}, {0: Point2D(x=999.0, y=80.0)}
    )
    routes, _calib = Fusion().fuse(
        top, side, golden_orientation(), Point3D(x=16.0, y=12.0, z=12.0),
        fps=30.0, top_shape=(240, 320), side_shape=(240, 320),
    )
    pt = routes[0].points[0]
    assert pt.x == pytest.approx(2.0)
    assert pt.y == pytest.approx(3.0)
    assert pt.z == pytest.approx(4.0)  # z vem de side.V, sinal +1 nesta orientação


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
    # retângulo de borda em pixel (from-top); px_per_cm=20; height=240
    rect = [Point2D(x=60.0, y=100.0), Point2D(x=140.0, y=100.0),
            Point2D(x=60.0, y=180.0), Point2D(x=140.0, y=180.0)]
    region = build_border_region(
        golden_orientation(), Point3D(x=20.0, y=20.0, z=20.0),
        border_points_top=rect, border_points_side=rect,
        top_shape=(240, 320), side_shape=(240, 320),
    )
    # x <- top.U: pixels 60..140 /20 = 3..7
    assert region.bounds["x"] == pytest.approx((3.0, 7.0))
    # y <- top.V: (240-180, 240-100)=(60,140) /20 = (3,7) (flip de v)
    assert region.bounds["y"] == pytest.approx((3.0, 7.0))
    assert region.bounds["z"] == pytest.approx((3.0, 7.0))
