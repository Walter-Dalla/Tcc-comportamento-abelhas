"""Fuse — reconstrução 3D das duas views + calibração por eixo (Fase 3).

Porta `BasicModule/routeAnalizer.py::route_module` (merge por índice) e
`BasicModule/utils/getData.py` (`get_video_data`/`pixel_to_cm`), mas dirigido por
`BoxOrientationConfig.axis_sources()` em vez do hardcode `top→(x,y), side→(_,z)`.

Corrige bug #3 na raiz (`getData.py` derivava as 3 razões px/cm todas de
`height_side` e tirava a mediana — mistura de unidades sem sentido físico). Aqui
`px_per_cm` é por eixo: para cada eixo 3D, usa a dimensão de pixel do eixo de
imagem (u/v) da(s) câmera(s) que de fato observam aquele eixo (resolvido por
`axis_sources()`), dividida pela dimensão em cm da caixa naquele eixo. Quando o
eixo é observado por 2 câmeras, a razão reportada é a MÉDIA das razões por câmera.

Também move a conversão px→cm para DENTRO do Fuse (a rota já sai em cm), o que
elimina o bug #2 na raiz: a conversão acontece uma única vez, no lugar certo, em
vez de cada plugin de metadata reimplementá-la (mal). Ver seção 4.3 do plano.

Nota sobre a convenção de eixos: este módulo usa `axis_sources()` do schema
(Fase 1) como fonte de verdade — NÃO reimplementa o `_resolve_camera_axis_mapping`/
`combine` do rascunho da seção 4.1 do plano, cuja tabela de decomposição de vértice
assumia uma convenção (Y=profundidade, Z=altura) diferente da que o schema fixou e
mergeou (Y=altura via TOP/BOTTOM, Z=profundidade via FRONT/BACK). O schema é o
contrato. Quando um eixo é observado pelas duas câmeras, este módulo faz a MÉDIA
das duas leituras (decisão do dono do projeto) em vez da antiga política
"TOP-camera-vence-empate" da Fase 1.
"""

from __future__ import annotations

from src.core.plugin import Plugin
from src.core.schema.geometry import Point2D, Point3D
from src.core.schema.orientation import (
    AxisSource,
    BoxAxis,
    BoxOrientationConfig,
    Calibration,
    CameraRole,
    ImageAxis,
)
from src.core.schema.result import BorderRegion
from src.core.schema.route import Route3D
from src.core.schema.track import Track

_AXES = ("x", "y", "z")


class FuseConfigError(Exception):
    """Configuração de orientação/dimensão inconsistente (ex.: box_cm zero num eixo)."""


def _px_dimension(source: AxisSource, shapes: dict[CameraRole, tuple[int, int]]) -> int:
    """Dimensão de pixel (width p/ eixo u, height p/ eixo v) da câmera/eixo de imagem
    que fornece um dado eixo 3D. `shapes[role] = (height, width)` do RectifiedFrame,
    análogo a `height, width = frames[0].shape` do getData.py legado."""
    height, width = shapes[source.camera]
    return width if source.image_axis is ImageAxis.U else height


def _compute_px_per_cm(
    sources_by_axis: dict[str, list[AxisSource]],
    shapes: dict[CameraRole, tuple[int, int]],
    box_cm: Point3D,
) -> Point3D:
    """Razão px/cm por eixo. Quando o eixo tem 2 fontes (câmeras), reporta a
    média aritmética das razões por câmera."""
    box_by_axis = {"x": box_cm.x, "y": box_cm.y, "z": box_cm.z}
    ratios: dict[str, float] = {}
    for axis in _AXES:
        cm = box_by_axis[axis]
        if cm <= 0:
            raise FuseConfigError(f"box_cm.{axis} deve ser > 0, recebeu {cm}")
        per_source_ratios = [_px_dimension(source, shapes) / cm for source in sources_by_axis[axis]]
        ratios[axis] = sum(per_source_ratios) / len(per_source_ratios)
    return Point3D(x=ratios["x"], y=ratios["y"], z=ratios["z"])


class Fusion(Plugin):
    def fuse(
        self,
        top_track: Track,
        side_track: Track,
        box_orientation: BoxOrientationConfig,
        box_cm: Point3D,
        fps: float,
        top_shape: tuple[int, int],
        side_shape: tuple[int, int],
    ) -> tuple[list[Route3D], Calibration]:
        sources = box_orientation.axis_sources()
        sources_by_axis: dict[str, list[AxisSource]] = {
            "x": sources[BoxAxis.X],
            "y": sources[BoxAxis.Y],
            "z": sources[BoxAxis.Z],
        }
        shapes = {CameraRole.TOP: top_shape, CameraRole.SIDE: side_shape}
        # `_compute_px_per_cm` levanta FuseConfigError por eixo se box_cm <= 0, antes de
        # computar qualquer razão para aquele eixo — mesmo comportamento de antes.
        px_per_cm = _compute_px_per_cm(sources_by_axis, shapes, box_cm)

        box_by_axis = {"x": box_cm.x, "y": box_cm.y, "z": box_cm.z}
        # razão própria de cada fonte (por câmera) — usada para converter cada leitura
        # de pixel pra cm ANTES de fazer a média entre câmeras, nunca depois.
        ratios_by_axis: dict[str, list[float]] = {
            axis: [_px_dimension(source, shapes) / box_by_axis[axis] for source in sources_by_axis[axis]]
            for axis in _AXES
        }

        tracks_by_role = {CameraRole.TOP: top_track, CameraRole.SIDE: side_track}

        # interseção explícita dos índices — substitui o `min(len(top), len(side))`
        # de route_module por algo robusto a buracos em qualquer das views.
        frame_indices = sorted(set(top_track.points) & set(side_track.points))

        points: dict[int, Point3D] = {}
        for idx in frame_indices:
            values: dict[str, float] = {}
            for axis in _AXES:
                cm_readings: list[float] = []
                for source, ratio in zip(sources_by_axis[axis], ratios_by_axis[axis], strict=True):
                    centroid = tracks_by_role[source.camera].points[idx]
                    raw_px = centroid.x if source.image_axis is ImageAxis.U else centroid.y
                    cm_readings.append((source.sign * raw_px) / ratio)
                values[axis] = sum(cm_readings) / len(cm_readings)
            points[idx] = Point3D(x=values["x"], y=values["y"], z=values["z"])

        route = Route3D(entity_id=top_track.entity_id, points=points)
        calibration = Calibration(
            box_cm=box_cm, px_per_cm=px_per_cm, fps=fps, orientation=box_orientation
        )
        return [route], calibration


def build_border_region(
    box_orientation: BoxOrientationConfig,
    box_cm: Point3D,
    border_points_top: list[Point2D],
    border_points_side: list[Point2D],
    top_shape: tuple[int, int],
    side_shape: tuple[int, int],
    threshold_px: int = 100,
) -> BorderRegion:
    """Constrói `BorderRegion.bounds` em cm, por eixo 3D, usando as MESMAS fontes
    (`axis_sources()`) da rota, recomputando a razão px/cm de cada câmera a partir
    de `box_cm` (em vez de receber um `px_per_cm` já pronto — que, para um eixo
    observado por 2 câmeras, seria uma média que não serve pra converter os pontos
    de borda de CADA câmera corretamente).

    Resolve o bug latente descrito na seção 4.5 do plano: os pontos de borda são
    clicados em pixel (`BorderUi`), enquanto a rota já está em cm — comparar pixel
    bruto contra cm daria contagem errada. Aqui cada eixo 3D pega os pontos de
    borda da(s) câmera(s) que o observam (via `axis_sources()`), converte o eixo de
    imagem relevante pra cm (com o mesmo flip de v-de-baixo do Detect e o mesmo
    sinal) usando a razão própria daquela câmera, e toma min/max. Quando o eixo é
    observado por 2 câmeras, os bounds (min, max) de cada câmera são calculados
    independentemente e depois a MÉDIA é tomada elemento a elemento
    (`avg_min=(min1+min2)/2`, `avg_max=(max1+max2)/2`) — mesma política de média
    usada em `Fusion.fuse()`. O `BorderPlugin` (contagem de containment) então
    compara cm contra cm — sem mistura de espaço de pixel nem de câmeras
    diferentes, ao contrário do borderModule.py legado.
    """
    sources = box_orientation.axis_sources()
    sources_by_axis: dict[str, list[AxisSource]] = {
        "x": sources[BoxAxis.X],
        "y": sources[BoxAxis.Y],
        "z": sources[BoxAxis.Z],
    }
    shapes = {CameraRole.TOP: top_shape, CameraRole.SIDE: side_shape}
    points_by_role = {
        CameraRole.TOP: border_points_top,
        CameraRole.SIDE: border_points_side,
    }
    box_by_axis = {"x": box_cm.x, "y": box_cm.y, "z": box_cm.z}
    for axis in _AXES:
        if box_by_axis[axis] <= 0:
            raise FuseConfigError(f"box_cm.{axis} deve ser > 0, recebeu {box_by_axis[axis]}")

    bounds: dict[str, tuple[float, float]] = {}
    for axis in _AXES:
        per_source_bounds: list[tuple[float, float]] = []
        for source in sources_by_axis[axis]:
            ratio = _px_dimension(source, shapes) / box_by_axis[axis]
            height, _width = shapes[source.camera]
            border_points = points_by_role[source.camera]
            values: list[float] = []
            for p in border_points:
                # mesma convenção do Detect: eixo v é medido de baixo pra cima.
                coord = p.x if source.image_axis is ImageAxis.U else (height - p.y)
                values.append((source.sign * coord) / ratio)
            per_source_bounds.append((min(values), max(values)))

        mins = [b[0] for b in per_source_bounds]
        maxs = [b[1] for b in per_source_bounds]
        bounds[axis] = (sum(mins) / len(mins), sum(maxs) / len(maxs))

    return BorderRegion(
        threshold_px=threshold_px,
        bounds={"x": bounds["x"], "y": bounds["y"], "z": bounds["z"]},
    )
