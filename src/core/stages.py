"""Classes-base por camada de estágio (Fase 2).

Contém o bloco "Abstração Detector/Tracker" do `ARCHITECTURE.md`, mais uma adição
desta fase: `MetadataPlugin`. O `ARCHITECTURE.md` não mostra uma base típica para
o kind `metadata`, mas a prova de conceito da Fase 2 (portar `speed`/`border`)
exige uma classe tipada com um método único de execução — mesmo padrão de
`Detector`/`Tracker`. O nome do método (`run(ctx) -> None`) é fixado por
`ARCHITECTURE.md` (fonte da verdade), NÃO `compute`.

`Detect`/`Track` reais (streaming) chegam na Fase 3; aqui só as interfaces
existem, para o `plugin_registry.py` poder validar o kind→classe-base.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from src.core.plugin import Plugin
from src.core.schema.detection import FrameDetections
from src.core.schema.result import AnalysisContext
from src.core.schema.track import Track

if TYPE_CHECKING:
    # `RectifiedFrame` só existe a partir da Fase 3 (estágio Rectify). Em runtime
    # `Detector` nunca é instanciado nesta fase e, com `from __future__ import
    # annotations`, a anotação nunca é avaliada. Mas o mypy reprovaria uma
    # referência a um nome inexistente — este alias temporário o satisfaz e será
    # trocado pelo tipo real quando Rectify chegar (Fase 3).
    RectifiedFrame = object


class Detector(Plugin):
    @abstractmethod
    def detect(self, frame: RectifiedFrame) -> FrameDetections: ...


class Tracker(Plugin):
    @abstractmethod
    def update(self, dets: FrameDetections) -> None: ...

    @abstractmethod
    def tracks(self) -> list[Track]: ...

    def reset(self) -> None:
        return None


class MetadataPlugin(Plugin):
    """Base do kind='metadata'.

    Substitui o antigo `module_call(data: dict) -> dict`: em vez de receber e
    devolver um dict cru, recebe o `AnalysisContext` tipado e MUTA-O in place via
    `ctx.add_metric(...)`, sem retorno.
    """

    @abstractmethod
    def run(self, ctx: AnalysisContext) -> None: ...
