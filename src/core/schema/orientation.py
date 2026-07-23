"""Orientação de câmera/caixa e derivação de eixos (Fase 1, Wave 1 / T5).

Resolve na raiz o bug de eixo hardcoded do sistema legado (topo -> sempre (x,z),
lateral -> sempre y). Aqui a orientação vira configuração explícita: cada câmera
declara qual face da caixa enxerga e qual vértice cada ponto clicado representa,
e `BoxOrientationConfig.axis_mapping()` deriva, por eixo 3D, de qual câmera/eixo
de imagem ele vem.

Política de desempate (achado do plano da Fase 1): quando um eixo é observável
pelas duas câmeras, a câmera TOP tem prioridade — reproduz o comportamento
implícito do `routeAnalizer.py` atual (top vence, side só contribui o eixo que o
topo não vê). Decisão de projeto sinalizada no handoff da Fase 1.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.schema.geometry import Point2D, Point3D


# NOTA: `str, Enum` (não `enum.StrEnum`) é a forma mandada explicitamente pelo plano
# da Fase 1 (seção 2) e por ARCHITECTURE.md — garante serialização como string simples
# em JSON. UP042 é suprimido por classe abaixo por esse motivo deliberado.
class BoxFace(str, Enum):  # noqa: UP042
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    FRONT = "front"
    BACK = "back"


class BoxVertex(str, Enum):  # noqa: UP042
    """Um dos 8 vértices da caixa, como combinação de 3 componentes binários.

    Convenção de eixo fixada aqui (documentada porque nenhum outro lugar do
    projeto fixa isso hoje):
      - X (largura)      <- componente LEFT/RIGHT
      - Y (altura)       <- componente TOP/BOTTOM
      - Z (profundidade) <- componente FRONT/BACK
    """

    TOP_FRONT_LEFT = "top_front_left"
    TOP_FRONT_RIGHT = "top_front_right"
    TOP_BACK_LEFT = "top_back_left"
    TOP_BACK_RIGHT = "top_back_right"
    BOTTOM_FRONT_LEFT = "bottom_front_left"
    BOTTOM_FRONT_RIGHT = "bottom_front_right"
    BOTTOM_BACK_LEFT = "bottom_back_left"
    BOTTOM_BACK_RIGHT = "bottom_back_right"


# tabela de decomposição de BoxVertex nos 3 componentes — usada pelo algoritmo de axis_mapping()
_VERTEX_COMPONENTS: dict[BoxVertex, dict[str, str]] = {
    BoxVertex.TOP_FRONT_LEFT:      {"y": "top",    "z": "front", "x": "left"},
    BoxVertex.TOP_FRONT_RIGHT:     {"y": "top",    "z": "front", "x": "right"},
    BoxVertex.TOP_BACK_LEFT:       {"y": "top",    "z": "back",  "x": "left"},
    BoxVertex.TOP_BACK_RIGHT:      {"y": "top",    "z": "back",  "x": "right"},
    BoxVertex.BOTTOM_FRONT_LEFT:   {"y": "bottom", "z": "front", "x": "left"},
    BoxVertex.BOTTOM_FRONT_RIGHT:  {"y": "bottom", "z": "front", "x": "right"},
    BoxVertex.BOTTOM_BACK_LEFT:    {"y": "bottom", "z": "back",  "x": "left"},
    BoxVertex.BOTTOM_BACK_RIGHT:   {"y": "bottom", "z": "back",  "x": "right"},
}

# ordem canônica "menor -> maior" por eixo, usada para derivar o sinal em axis_mapping()
_AXIS_ORDER: dict[str, tuple[str, str]] = {
    "x": ("left", "right"),
    "y": ("bottom", "top"),
    "z": ("front", "back"),
}


class CameraRole(str, Enum):  # noqa: UP042
    TOP = "top"
    SIDE = "side"


class CameraOrientation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: CameraRole
    face_viewed: BoxFace
    corner_vertices: list[BoxVertex]  # ordem: sup-direito, sup-esquerdo, inf-direito, inf-esquerdo

    @model_validator(mode="after")
    def _validate_corners(self) -> "CameraOrientation":
        if len(self.corner_vertices) != 4:
            raise ValueError(
                f"corner_vertices deve ter exatamente 4 itens, recebeu {len(self.corner_vertices)}"
            )
        if len(set(self.corner_vertices)) != 4:
            raise ValueError("corner_vertices não pode ter vértices duplicados")
        return self


class ImageAxis(str, Enum):  # noqa: UP042
    U = "u"  # eixo horizontal de pixel (largura da imagem)
    V = "v"  # eixo vertical de pixel (altura da imagem)


class BoxAxis(str, Enum):  # noqa: UP042
    X = "x"
    Y = "y"
    Z = "z"


class AxisSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    camera: CameraRole
    image_axis: ImageAxis
    sign: Literal[1, -1] = 1


class AxisMapping(BaseModel):
    """Retorno de BoxOrientationConfig.axis_mapping(): de onde vem cada eixo 3D da caixa."""

    model_config = ConfigDict(extra="forbid")
    x: AxisSource
    y: AxisSource
    z: AxisSource

    @model_validator(mode="after")
    def _distinct_sources(self) -> "AxisMapping":
        keys = [
            (self.x.camera, self.x.image_axis),
            (self.y.camera, self.y.image_axis),
            (self.z.camera, self.z.image_axis),
        ]
        if len(set(keys)) != 3:
            raise ValueError(
                "dois eixos 3D não podem ler o mesmo par (câmera, eixo de imagem) — "
                f"fontes: x={keys[0]}, y={keys[1]}, z={keys[2]}"
            )
        return self

    def resolve(self, top_point: Point2D, side_point: Point2D) -> Point3D:
        """Aplica o mapeamento a um ponto 2D de cada câmera e retorna o Point3D combinado."""
        raw = {
            (CameraRole.TOP, ImageAxis.U): top_point.x,
            (CameraRole.TOP, ImageAxis.V): top_point.y,
            (CameraRole.SIDE, ImageAxis.U): side_point.x,
            (CameraRole.SIDE, ImageAxis.V): side_point.y,
        }

        def _value(source: AxisSource) -> float:
            return raw[(source.camera, source.image_axis)] * source.sign

        return Point3D(x=_value(self.x), y=_value(self.y), z=_value(self.z))


class BoxOrientationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    top_camera: CameraOrientation
    side_camera: CameraOrientation

    @model_validator(mode="after")
    def _validate_roles(self) -> "BoxOrientationConfig":
        if self.top_camera.role is not CameraRole.TOP:
            raise ValueError("top_camera.role deve ser CameraRole.TOP")
        if self.side_camera.role is not CameraRole.SIDE:
            raise ValueError("side_camera.role deve ser CameraRole.SIDE")
        return self

    def axis_mapping(self) -> AxisMapping:
        """Deriva, por câmera, qual eixo de imagem (u/v) corresponde a qual eixo 3D (x/y/z).

        Algoritmo (ver seção 1.5 do docs/plans/fase1-detalhado.md para o raciocínio completo):
          1. Para cada câmera, o componente que difere entre corner_vertices[0] e [1] (ambos
             "de cima" na ordem de clique, variam só em u) define o BoxAxis do eixo-u daquela
             câmera; o componente que difere entre [0] e [2] (variam só em v) define o BoxAxis
             do eixo-v.
          2. O sinal é derivado da convenção canônica menor->maior por eixo: se o componente de
             corner_vertices[0] for o lado "maior" da convenção, sign=+1, senão -1.
          3. Cada um dos 3 BoxAxis deve ser observável por pelo menos uma câmera; se um eixo for
             observável pelas duas, a câmera TOP tem prioridade como fonte canônica (reproduz o
             comportamento do routeAnalizer.py atual, que sempre usa a câmera do topo quando
             disponível e só recorre à lateral para o eixo que o topo não vê).
        """
        top_axes = _derive_candidate_axes(self.top_camera)
        side_axes = _derive_candidate_axes(self.side_camera)

        candidates: dict[BoxAxis, list[AxisSource]] = {BoxAxis.X: [], BoxAxis.Y: [], BoxAxis.Z: []}
        for image_axis, (box_axis, sign) in top_axes.items():
            candidates[box_axis].append(
                AxisSource(camera=CameraRole.TOP, image_axis=image_axis, sign=sign)
            )
        for image_axis, (box_axis, sign) in side_axes.items():
            candidates[box_axis].append(
                AxisSource(camera=CameraRole.SIDE, image_axis=image_axis, sign=sign)
            )

        chosen: dict[BoxAxis, AxisSource] = {}
        for box_axis, sources in candidates.items():
            if not sources:
                raise ValueError(
                    f"eixo {box_axis.value} não é observável por nenhuma câmera nesta configuração "
                    "de orientação"
                )
            # prioridade: TOP antes de SIDE
            sources_sorted = sorted(sources, key=lambda s: 0 if s.camera is CameraRole.TOP else 1)
            chosen[box_axis] = sources_sorted[0]

        return AxisMapping(x=chosen[BoxAxis.X], y=chosen[BoxAxis.Y], z=chosen[BoxAxis.Z])


def _derive_candidate_axes(
    camera: CameraOrientation,
) -> dict[ImageAxis, tuple[BoxAxis, Literal[1, -1]]]:
    v0, v1, v2, _v3 = camera.corner_vertices  # sup-dir, sup-esq, inf-dir, inf-esq
    return {
        ImageAxis.U: _differing_component(v0, v1),
        ImageAxis.V: _differing_component(v0, v2),
    }


def _differing_component(v0: BoxVertex, v1: BoxVertex) -> tuple[BoxAxis, Literal[1, -1]]:
    c0, c1 = _VERTEX_COMPONENTS[v0], _VERTEX_COMPONENTS[v1]
    diffs = [axis for axis in ("x", "y", "z") if c0[axis] != c1[axis]]
    if len(diffs) != 1:
        raise ValueError(
            f"vértices {v0.value} e {v1.value} devem diferir em exatamente um eixo, "
            f"diferem em {diffs}"
        )
    axis = diffs[0]
    _lesser, greater = _AXIS_ORDER[axis]
    sign: Literal[1, -1] = 1 if c0[axis] == greater else -1
    return BoxAxis(axis), sign


class Calibration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    box_cm: Point3D
    px_per_cm: Point3D
    fps: float = Field(gt=0)
    orientation: BoxOrientationConfig
