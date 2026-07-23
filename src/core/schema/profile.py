"""Perfil de análise persistido (Fase 1, Wave 2 / T7).

NOTA DE ESCOPO: este arquivo NÃO está na lista literal de arquivos da Fase 1 em
`ARCHITECTURE.md` (geometry, detection, track, route, result, orientation). É uma
adição deste plano, justificada porque `ProfileStore` (exigido pela própria Fase
1) não pode ser implementado sem *algum* tipo para o que `cache/configs.json`
guarda hoje, e nenhum modelo desse tipo é definido em nenhum outro lugar do
`ARCHITECTURE.md`. Decisão sinalizada ao dono do projeto no handoff da Fase 1.

Mapeamento 1:1 com os campos hoje soltos em `cache/configs.json`
(`configurationUI.py`): `width_box_cm`/`height_box_cm`/`depth_box_cm` viram os 3
componentes de `box_cm: Point3D`; `frame_perspective_points_top/side` e
`frame_border_points_top/side` (listas de `[x,y]` cru) viram listas de `Point2D`.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.schema.geometry import Point2D, Point3D
from src.core.schema.orientation import BoxOrientationConfig


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    top_video_path: str = ""
    side_video_path: str = ""
    box_cm: Point3D = Point3D(x=0.0, y=0.0, z=0.0)
    perspective_points_top: list[Point2D] = Field(default_factory=list)
    perspective_points_side: list[Point2D] = Field(default_factory=list)
    border_points_top: list[Point2D] = Field(default_factory=list)
    border_points_side: list[Point2D] = Field(default_factory=list)
    # Deliberadamente None por padrão: só populado quando a tela OrientationUi (Fase 4) existir.
    orientation: BoxOrientationConfig | None = None

    @field_validator(
        "perspective_points_top",
        "perspective_points_side",
        "border_points_top",
        "border_points_side",
    )
    @classmethod
    def _four_or_empty(cls, value: list[Point2D]) -> list[Point2D]:
        if value and len(value) != 4:
            raise ValueError(f"deve ter exatamente 4 pontos ou estar vazio, recebeu {len(value)}")
        return value
