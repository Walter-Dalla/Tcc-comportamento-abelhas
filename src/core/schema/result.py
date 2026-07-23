"""Resultado de análise, métricas e região de borda (Fase 1, Wave 2 / T8).

`Metric.value` usa o union fechado `JsonSafeValue` (não `Any` puro):
`ARCHITECTURE.md` mostra `value: Any`, mas restringir aqui impede que um plugin
de metadata coloque um objeto Python arbitrário (ex. array numpy) num `Metric` e
faça `ResultStore.save` falhar de forma obscura no meio da serialização JSON, em
vez de falhar cedo no ponto onde o plugin errou. Desvio sinalizado no handoff.

`BorderRegion` mantém a forma literal de `ARCHITECTURE.md` (`threshold_px` +
`bounds: dict[eixo, (min,max)]`) — só dado, sem lógica de classificação embutida
(isso é responsabilidade do `BorderPlugin`, Fase 2).
"""

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    Strict,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from src.core.schema.orientation import Calibration
from src.core.schema.route import Route3D

SCHEMA_VERSION = "1.0"

# União fechada de valores seguros para JSON. `ARCHITECTURE.md` usa `value: Any`;
# o plano da Fase 1 (decisão c) restringe para este union. A forma literal do
# plano (`list[Any] | dict[str, Any]`) NÃO cumpre a própria intenção declarada:
# em modo lax, `list[Any]` coage `set`/`tuple`/`numpy.ndarray` para list e engole
# itens numpy não-validados, que então quebram `model_dump_json()` tardiamente —
# exatamente a "falha obscura de serialização" que a restrição deveria prevenir.
# Por isso `list`/`dict` são marcados `Strict()`: um `numpy.ndarray`/`set`/`tuple`
# ou objeto arbitrário passado como `Metric.value` é rejeitado na construção do
# Metric (falha cedo, no ponto onde o plugin errou), não na serialização. Um
# union recursivo (que validaria também elementos aninhados) foi avaliado e
# descartado: `TypeAliasType` recursivo quebra o mypy ("cyclic definition") e o
# `TypeAlias` recursivo entra em RecursionError no pydantic — o custo de brigar
# com a toolchain não compensa para o caso aninhado (raro). Desvio (mais estrito
# que a letra do plano, fiel à sua intenção) sinalizado no handoff da Fase 1.
JsonSafeValue = (
    StrictStr
    | StrictInt
    | StrictFloat
    | StrictBool
    | None
    | Annotated[list[Any], Strict()]
    | Annotated[dict[str, Any], Strict()]
)


class Metric(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    # ARCHITECTURE.md usa `value: Any` — restringido aqui deliberadamente (ver docstring do módulo).
    value: JsonSafeValue
    unit: str | None = None
    producer: str


class BorderRegion(BaseModel):
    """Região de borda/vidro em coordenadas 3D da rota, por eixo — substitui o
    MetadataModule/borderModule.py legado (que só usava 2 dos 4 cantos e misturava eixo v do topo
    com eixo u do lado). Forma alinhada a ARCHITECTURE.md: só dado (threshold configurável + bounds
    calculados), sem lógica de classificação embutida — a classificação "dentro/fora da borda por
    eixo" é responsabilidade do `BorderPlugin` (Fase 2, `run(ctx)`), não deste modelo. Cada eixo do
    `bounds` tem uma única fonte de dado (via `axis_mapping()`, Fase 3), sem ambiguidade de espaço de
    pixel nem mistura de câmeras."""

    model_config = ConfigDict(extra="forbid")
    threshold_px: int = 100
    bounds: dict[Literal["x", "y", "z"], tuple[float, float]]

    @model_validator(mode="after")
    def _bounds_ordered(self) -> "BorderRegion":
        for axis, (lo, hi) in self.bounds.items():
            if lo > hi:
                raise ValueError(f"{axis}: min ({lo}) não pode ser maior que max ({hi})")
        return self

    @model_validator(mode="after")
    def _bounds_complete(self) -> "BorderRegion":
        missing = {"x", "y", "z"} - set(self.bounds)
        if missing:
            raise ValueError(f"bounds incompleto, faltam eixos: {sorted(missing)}")
        return self


class AnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = SCHEMA_VERSION
    profile: str
    calibration: Calibration
    routes: list[Route3D] = Field(default_factory=list)
    metrics: dict[str, Metric] = Field(default_factory=dict)
    border_region: BorderRegion | None = None


class AnalysisContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: AnalysisResult

    def add_metric(self, metric: Metric) -> None:
        self.result.metrics[metric.name] = metric

    def get_metric(self, name: str) -> Metric | None:
        return self.result.metrics.get(name)
