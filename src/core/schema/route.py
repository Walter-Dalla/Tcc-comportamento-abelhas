"""Rota 3D reconstruída por entidade (Fase 1, Wave 1 / T4).

Mesmo padrão de `Track`, em 3D — é a saída do futuro estágio `Fuse` (Fase 3).
Buracos em `points` representam oclusão nativamente.
"""

from pydantic import BaseModel, ConfigDict, Field

from src.core.schema.geometry import Point3D


class Route3D(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: int = Field(ge=0)
    points: dict[int, Point3D] = Field(default_factory=dict)
