"""Value objects geométricos puros (Fase 1, Wave 1 / T1).

`frozen=True` -> imutáveis e hasháveis (úteis como chave de set/dict em código
futuro de tracking); `extra="forbid"` -> nenhum campo extra aceito
silenciosamente. Sem validadores de negócio: são só coordenadas.
"""

from pydantic import BaseModel, ConfigDict


class Point2D(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    x: float
    y: float


class Point3D(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    x: float
    y: float
    z: float


class BBox(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    x: float
    y: float
    w: float
    h: float
