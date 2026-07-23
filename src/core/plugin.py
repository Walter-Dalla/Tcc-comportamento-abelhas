"""Contrato de plugin: manifest tipado + classe-base (Fase 2).

Generaliza o mecanismo legado de `MetadataModule/modulesInvoker.py` (scan flat +
`module_call` duck-typed) para um contrato marketplace-ready: manifest declarado
em `plugin.toml`, classe-base tipada, versionamento (`api_version`/`schema`) e
ordenação (`before`/`after`/`priority`). Ver `ARCHITECTURE.md` seção "Contrato de
plugin" e `docs/plans/fase2-detalhado.md` seção 1.2.
"""

from __future__ import annotations

import tomllib
from abc import ABC
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    # Import só-de-tipo: `Plugin.setup` referencia `PipelineContext`, definido em
    # `pipeline.py` (camada acima). Com `from __future__ import annotations` a
    # anotação nunca é avaliada em runtime — sem import circular — mas o mypy
    # precisa deste import para resolver o nome. Ver plano seção 1.2.
    from src.core.pipeline import PipelineContext


class PluginKind(str, Enum):  # noqa: UP042
    CAPTURE = "capture"
    RECTIFY = "rectify"
    DETECTOR = "detector"
    TRACKER = "tracker"
    FUSION = "fusion"
    METADATA = "metadata"
    EXPORTER = "exporter"
    INTERFACE = "interface"


class PluginRequires(BaseModel):
    model_config = ConfigDict(extra="forbid")
    python: str = ">=3.11"
    packages: list[str] = Field(default_factory=list)
    plugins: list[str] = Field(default_factory=list)


class PluginOrdering(BaseModel):
    model_config = ConfigDict(extra="forbid")
    before: list[str] = Field(default_factory=list)
    after: list[str] = Field(default_factory=list)
    priority: int = 0


class PluginManifest(BaseModel):
    """Espelho tipado de `plugin.toml`. `from_toml` é a ÚNICA forma suportada de
    instanciar um manifest a partir de disco — mantém o `plugin.toml` como fonte
    única de verdade (um plugin.py nunca lê o próprio manifest)."""

    model_config = ConfigDict(extra="forbid")
    name: str
    version: str
    kind: PluginKind
    entry: str  # formato "modulo:NomeDaClasse", ex. "plugin:SpeedPlugin"
    api_version: str  # ex. "1.0"
    # `schema` é um range PEP 440 (ex. ">=1.0,<2.0") checado contra
    # AnalysisResult.schema_version pelo registry. O nome de campo `schema`
    # sombreia um atributo deprecado de BaseModel (pydantic emite UserWarning
    # benigno); mantido por fidelidade ao contrato do manifest do ARCHITECTURE.md.
    schema: str = Field()  # type: ignore[assignment]  # shadow benigno de BaseModel.schema, ver comentário acima
    requires: PluginRequires = Field(default_factory=PluginRequires)
    ordering: PluginOrdering = Field(default_factory=PluginOrdering)

    @classmethod
    def from_toml(cls, path: Path) -> PluginManifest:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
        plugin_tbl = raw.get("plugin", {})
        flattened = {
            **plugin_tbl,
            "requires": raw.get("requires", {}),
            "ordering": raw.get("ordering", {}),
        }
        return cls.model_validate(flattened)


class PluginSpec(BaseModel):
    """Manifest + diretório de origem (contém `plugin.toml` + o módulo do entry).
    `entry` é resolvido pelo registry relativo a `source_dir`."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    manifest: PluginManifest
    source_dir: Path


class Plugin(ABC):
    """Classe-base de todo plugin.

    `manifest` é atribuído pelo `PluginRegistry` logo após o import bem-sucedido
    (`cls.manifest = spec.manifest`), ANTES de instanciar — o `plugin.py` de um
    plugin nunca carrega seu próprio `plugin.toml`.
    """

    manifest: ClassVar[PluginManifest]

    def setup(self, ctx: PipelineContext) -> None:
        """Hook opcional, chamado antes da execução do estágio. No-op por padrão."""
        return None

    def teardown(self) -> None:
        """Hook opcional, chamado depois da execução do estágio. No-op por padrão."""
        return None
