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
from typing import TYPE_CHECKING, Any, ClassVar, Literal

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


class PluginConfigField(BaseModel):
    """Declaração de UM campo de config esperado por um plugin, lida da seção
    `[config]` de `plugin.toml`. Documentação + checagem de tipo OPCIONAL — não é
    allowlist nem gate de execução (ver `PluginManifest.validate_overrides`)."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["str", "int", "float", "bool"]
    required: bool = False
    default: str | int | float | bool | None = None
    description: str = ""


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
    # Documentação + checagem de tipo OPCIONAL da config esperada em
    # `ctx.request.overrides` (ver `PluginConfigField`). Nada em `Pipeline.run`/
    # `run_cpu_analysis` lê ou aplica isto automaticamente — é o próprio plugin,
    # via `setup()`, que pode chamar `validate_overrides()` se quiser.
    config: dict[str, PluginConfigField] = Field(default_factory=dict)

    @classmethod
    def from_toml(cls, path: Path) -> PluginManifest:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
        plugin_tbl = raw.get("plugin", {})
        flattened = {
            **plugin_tbl,
            "requires": raw.get("requires", {}),
            "ordering": raw.get("ordering", {}),
            "config": raw.get("config", {}),
        }
        return cls.model_validate(flattened)

    def validate_overrides(self, overrides: dict[str, Any]) -> list[str]:
        """Retorna lista de mensagens de erro (vazia = ok). NÃO levanta — quem chama
        decide o que fazer com os erros (log, pular, falhar). Checa: campos
        `required=True` ausentes de `overrides`; campos presentes com tipo
        incompatível com o declarado. Não valida campos de `overrides` que não
        estão declarados em `config` (overrides livres continuam permitidos,
        `[config]` é documentação/checagem, não allowlist)."""
        errors: list[str] = []
        for key, field in self.config.items():
            if key not in overrides:
                if field.required:
                    errors.append(f"campo obrigatório '{key}' ausente em overrides")
                continue
            value = overrides[key]
            if not _matches_declared_type(value, field.type):
                errors.append(
                    f"campo '{key}' esperava tipo '{field.type}', recebeu "
                    f"{type(value).__name__!r} ({value!r})"
                )
        return errors


def _matches_declared_type(value: Any, declared: Literal["str", "int", "float", "bool"]) -> bool:
    """Checagem de tipo deliberadamente leniente (ver `validate_overrides`):
    `"float"` aceita `int` também, por coerção numérica comum em JSON/TOML — mas
    `bool` NUNCA satisfaz `"int"`/`"float"`, apesar de `bool` ser subclasse de `int`
    em Python, porque isso trocaria silenciosamente `True`/`False` por um número."""
    if declared == "bool":
        return isinstance(value, bool)
    if declared == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if declared == "str":
        return isinstance(value, str)
    return False


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
