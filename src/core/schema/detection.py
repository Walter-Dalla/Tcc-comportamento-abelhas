"""Detecções espaciais por frame (Fase 1, Wave 1 / T2).

`FrameDetections.detections` aceita lista vazia — é o que substitui a sentinela
`(-1, -1)` do `backgroundRemoveModule.py` legado (nenhuma detecção no frame =
lista vazia, não um valor mágico).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.core.schema.geometry import BBox, Point2D


class Detection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    centroid: Point2D
    bbox: BBox | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    area: float | None = Field(default=None, ge=0.0)


class FrameDetections(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frame_index: int = Field(ge=0)
    view: Literal["top", "side"]
    detections: list[Detection] = Field(default_factory=list)
