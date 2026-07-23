"""Introspecção de JSON Schema de todos os modelos públicos (Fase 1).

Garante que `model_json_schema()` não lança para nenhum modelo (base leve que o
`plugin.toml`/`schema = ">=1.0,<2.0"` da Fase 2 precisará para validar contratos)
e que os enums públicos expõem `model_json_schema()` (`__get_pydantic_json_schema__`)
com a chave `"enum"`.
"""

import pytest
from pydantic import BaseModel, TypeAdapter

from src.core.schema.detection import Detection, FrameDetections
from src.core.schema.geometry import BBox, Point2D, Point3D
from src.core.schema.orientation import (
    AxisMapping,
    AxisSource,
    BoxAxis,
    BoxFace,
    BoxOrientationConfig,
    BoxVertex,
    Calibration,
    CameraOrientation,
    CameraRole,
    ImageAxis,
)
from src.core.schema.profile import Profile
from src.core.schema.result import (
    AnalysisContext,
    AnalysisResult,
    BorderRegion,
    Metric,
)
from src.core.schema.route import Route3D
from src.core.schema.track import Track

MODELS = [
    Point2D,
    Point3D,
    BBox,
    Detection,
    FrameDetections,
    Track,
    Route3D,
    AxisSource,
    AxisMapping,
    CameraOrientation,
    BoxOrientationConfig,
    Calibration,
    Profile,
    Metric,
    BorderRegion,
    AnalysisResult,
    AnalysisContext,
]

ENUMS = [BoxFace, BoxVertex, CameraRole, ImageAxis, BoxAxis]


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_model_json_schema_has_properties(model: type[BaseModel]):
    schema = model.model_json_schema()
    assert "properties" in schema


@pytest.mark.parametrize("enum", ENUMS, ids=lambda e: e.__name__)
def test_enum_json_schema_has_enum_key(enum):
    schema = TypeAdapter(enum).json_schema()
    assert "enum" in schema
