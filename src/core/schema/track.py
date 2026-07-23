"""Trajetórias temporais 2D com ID de entidade persistente (Fase 1, Wave 1 / T3).

`points` com chave `int` faltando = frame ocluído/sem detecção naquele índice
(buraco representável nativamente, sem sentinela). Pydantic v2 serializa chaves
`int` de dict como string em JSON e as reconverte para `int` na leitura —
comportamento nativo, sem `field_serializer`/`field_validator` manual.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.core.schema.geometry import Point2D


class Track(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: int = Field(ge=0)
    view: Literal["top", "side"]
    points: dict[int, Point2D] = Field(default_factory=dict)
