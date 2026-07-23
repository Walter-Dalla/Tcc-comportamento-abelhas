# Fase 2 — Sistema de plugin + esqueleto de orquestração (plano detalhado)

> Documento de execução para a Fase 2 do `ARCHITECTURE.md` (seções "Contrato de plugin", "Abstração
> Detector/Tracker" e a entrada "Fase 2" na tabela de fases). Escopo: `src/core/plugin.py`,
> `src/core/plugin_registry.py`, `src/core/pipeline.py`, `src/core/stages.py`, `src/core/gpu.py` (stub de
> probe), e a prova de conceito — portar `MetadataModule/speedModule.py` e `MetadataModule/borderModule.py`
> como os 2 primeiros plugins reais baseados em `plugin.toml`.
>
> Pré-condição assumida: Fase 1 concluída — `src/core/schema/{geometry,detection,track,route,result,
> orientation}.py`, `src/core/workspace.py`, `src/core/store.py` já existem e expõem `AnalysisContext`,
> `AnalysisResult`, `Metric`, `Route3D`, `Calibration`, `Point2D`/`Point3D`, `Workspace`, `ResultStore`.
> Verificado neste repo, na data deste plano, que `src/core/`, `docs/plans/` e `docs/handoffs/` ainda não
> existem — ou seja, este plano descreve o que a Fase 2 deve produzir assumindo que a Fase 1 já rodou antes
> dela, não construindo Fase 1 aqui.

---

## 0. Mecanismo legado que está sendo generalizado (referência de leitura obrigatória)

Antes de qualquer implementação, releia:

- `src/Modules/MetadataModule/modulesInvoker.py` — hoje: varre `./MetadataModule/*.py` (diretório da raiz
  do repo, **não** `src/Modules/MetadataModule/`) com `os.listdir`, carrega cada arquivo com
  `importlib.util.spec_from_file_location` + `module_from_spec` + `exec_module`, chama
  `module.module_call(data)` se o atributo existir, encadeia o mesmo dict `data` por todos os módulos
  encontrados (ordem = ordem do `os.listdir`, não determinística/não configurável), salva o resultado no
  final. Sem manifest, sem versionamento, sem ordenação declarada, sem isolamento de erro (uma exceção em
  qualquer `module_call` derruba `execute_metadata_module_calls` inteiro).
- `MetadataModule/speedModule.py::module_call(data)`:
  ```python
  def module_call(data):
      previusPoint = None
      pixel_to_cm_ratio = float(data["pixel_to_cm_ratio"])
      distanceTotal = 0
      speedTotal = 0
      speedObj = {}
      for index in data["route"]:
          routePoint = data["route"][index]
          point = route_point_to_math_point(routePoint)
          if(index == '0'):
              previusPoint = point
              continue
          distance = math.dist(previusPoint, point) * pixel_to_cm_ratio/100
          speed = distance/pixel_to_cm_ratio     # <-- bug #2: divide por ratio de novo
          speedObj[index] = speed
          speedTotal += speed
          distanceTotal += distance
          previusPoint = point
      data["speed"] = speedObj
      data["averageSpeed"] = speedTotal / len(data["route"])
      data["distanceTotal"] = distanceTotal
      return data
  ```
  `route` é um dict com chaves **string** `'0','1','2',...` (sempre contíguo, sem buracos — o pipeline
  antigo sempre grava `(-1,-1,-1)` em vez de omitir um frame). `index == '0'` é usado como proxy pra "é o
  primeiro frame".
- `MetadataModule/borderModule.py::module_call(data)`:
  ```python
  def module_call(data):
      data["time_border_x"] = 0
      data["time_border_y"] = 0
      data["time_border_z"] = 0
      frame_border_points_top = data["frame_border_points_top"]
      frame_border_points_side = data["frame_border_points_side"]
      border_min_x = min(frame_border_points_top[0][0], frame_border_points_top[1][0])
      border_max_x = max(frame_border_points_top[0][0], frame_border_points_top[1][0])
      border_min_y = min(frame_border_points_top[0][1], frame_border_points_top[1][1],
                         frame_border_points_side[0][0], frame_border_points_side[1][0])
      border_max_y = max(frame_border_points_top[0][1], frame_border_points_top[1][1],
                         frame_border_points_side[0][0], frame_border_points_side[1][0])
      border_min_z = min(frame_border_points_side[0][1], frame_border_points_side[1][1])
      border_max_z = max(frame_border_points_side[0][1], frame_border_points_side[1][1])
      for index in data["route"]:
          value = data["route"][index]
          x, y, z = value['x'], value['y'], value['z']
          if border_min_x <= x <= border_max_x: data["time_border_x"] += 1
          if border_min_y <= y <= border_max_y: data["time_border_y"] += 1
          if border_min_z <= z <= border_max_z: data["time_border_z"] += 1
      return data
  ```
  Note a mistura de eixos em `border_min_y`/`border_max_y`: usa os dois pontos da câmera de **topo** (ambas
  as coordenadas) **e** a primeira coordenada dos dois pontos da câmera **lateral**. Isso não é um bug
  documentado no `ARCHITECTURE.md`. No schema alvo, porém, `BorderRegion` guarda os limites **já resolvidos
  por eixo 3D** (`bounds`) — então essa derivação (e a mistura de eixos) deixa de viver no plugin: pertence
  a quem popula `bounds` (a fixture de teste na Fase 2; `axis_mapping()` na Fase 3). Ver seção abaixo.

**BorderRegion — alinhar com o schema autoritativo (não é mais um gap em aberto)**: o `ARCHITECTURE.md`
(seção "Schema de dados") **já define** `BorderRegion`, como produto da Fase 1:
```python
# src/core/schema/result.py (definido na Fase 1, conforme ARCHITECTURE.md)
class BorderRegion(BaseModel):
    threshold_px: int = 100
    bounds: dict[Literal["x", "y", "z"], tuple[float, float]]   # min/max por eixo 3D
```
Ou seja, `BorderRegion` guarda os limites **já resolvidos por eixo 3D** (`bounds`), **não** os 4 pontos de
pixel crus por câmera. A derivação desses limites a partir dos pontos clicados — e a antiga mistura de
eixos de `MetadataModule/borderModule.py` — é responsabilidade de quem **popula** `bounds`: na Fase 3, via
`axis_mapping()`; na Fase 2, a fixture de teste fornece `bounds` diretamente (sem amarra de compatibilidade
com o output antigo, por decisão do `ARCHITECTURE.md`). O plugin `border` desta fase **consome** `bounds` e
faz só a contagem de containment por eixo — não reproduz a lógica de min/max de pontos de pixel.

Antes de escrever `plugins/border/plugin.py`, o workstream `border` deve apenas **confirmar** que
`src/core/schema/result.py` expõe `BorderRegion` com o formato acima (produto da Fase 1). **Nenhuma
extensão de schema nova é necessária nesta fase** — se `BorderRegion` estiver ausente/divergente, é um
bug/pendência da Fase 1 a ser reportado, não algo a redefinir aqui com um formato diferente.

---

## 1. Lista de tarefas ordenada (arquivo por arquivo)

Ordem de implementação exigida (cada item depende dos anteriores via import, exceto onde indicado
"paralelizável"):

### 1.0 Pré-voo (leitura, sem escrita de código)
Confirmar que `src/core/schema/result.py` expõe `AnalysisContext`, `AnalysisResult`, `Metric`, `Route3D`,
`Calibration`; confirmar `BorderRegion` (ver gap acima). Confirmar `src/core/workspace.py::Workspace` e
`src/core/store.py::ResultStore` existem com a API descrita no `ARCHITECTURE.md`.

### 1.1 `src/core/errors.py` (arquivo novo — não citado literalmente no `ARCHITECTURE.md`, adicionado por
necessidade de implementação: `plugin.py`, `plugin_registry.py` e `pipeline.py` precisam de um vocabulário
de exceção compartilhado sem risco de import circular)

```python
# src/core/errors.py
class PluginError(Exception):
    """Erro base de todo o subsistema de plugin."""

class PluginManifestError(PluginError):
    """plugin.toml malformado ou faltando campo obrigatório."""

class PluginApiVersionError(PluginError):
    """Plugin declara api_version fora do que o PluginRegistry suporta."""

class PluginSchemaVersionError(PluginError):
    """Plugin declara schema (range) incompatível com SCHEMA_VERSION atual."""

class PluginContractError(PluginError):
    """Classe apontada por entry não é subclasse de Plugin, ou não é subclasse da
    classe-base exigida pelo kind declarado (ex.: kind=metadata exige MetadataPlugin)."""

class PluginNotFoundError(PluginError):
    """PluginRegistry.get(kind, name) chamado para um (kind, name) não descoberto."""

class PluginOrderingCycleError(PluginError):
    """Ciclo detectado entre before/after de um conjunto de plugins do mesmo kind.
    Erro de configuração — não é isolado por plugin, propaga."""

class PluginLoadError(PluginError):
    """Falha ao importar o módulo do entry point ou ao instanciar a classe (cls())."""
```

### 1.2 `src/core/plugin.py`

```python
# src/core/plugin.py
from __future__ import annotations
from abc import ABC
from enum import Enum
from pathlib import Path
from typing import ClassVar
import tomllib

from pydantic import BaseModel, Field

class PluginKind(str, Enum):
    CAPTURE = "capture"
    RECTIFY = "rectify"
    DETECTOR = "detector"
    TRACKER = "tracker"
    FUSION = "fusion"
    METADATA = "metadata"
    EXPORTER = "exporter"
    INTERFACE = "interface"

class PluginRequires(BaseModel):
    python: str = ">=3.11"
    packages: list[str] = Field(default_factory=list)
    plugins: list[str] = Field(default_factory=list)

class PluginOrdering(BaseModel):
    before: list[str] = Field(default_factory=list)
    after: list[str] = Field(default_factory=list)
    priority: int = 0

class PluginManifest(BaseModel):
    name: str
    version: str
    kind: PluginKind
    entry: str                 # formato "modulo:NomeDaClasse", ex. "plugin:SpeedPlugin"
    api_version: str           # ex. "1.0"
    schema: str                # ex. ">=1.0,<2.0" (range contra AnalysisResult.schema_version)
    requires: PluginRequires = Field(default_factory=PluginRequires)
    ordering: PluginOrdering = Field(default_factory=PluginOrdering)

    @classmethod
    def from_toml(cls, path: Path) -> "PluginManifest":
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
    model_config = {"arbitrary_types_allowed": True}
    manifest: PluginManifest
    source_dir: Path            # diretório contendo plugin.toml + plugin.py

class Plugin(ABC):
    """Classe-base de todo plugin. `manifest` é atribuído pelo PluginRegistry logo após
    o import bem-sucedido (cls.manifest = spec.manifest), ANTES de instanciar — o
    arquivo plugin.py de um plugin nunca carrega seu próprio plugin.toml."""
    manifest: ClassVar[PluginManifest]

    def setup(self, ctx: "PipelineContext") -> None:
        """Hook opcional, chamado antes da execução do estágio. No-op por padrão."""
        return None

    def teardown(self) -> None:
        """Hook opcional, chamado depois da execução do estágio. No-op por padrão."""
        return None
```

Notas de design a registrar no código (docstring/comentário):
- `PluginManifest.from_toml` é a **única** forma suportada de instanciar um manifest a partir de disco —
  mantém o `plugin.toml` como fonte única de verdade.
- `entry` é resolvido pelo registry relativo a `source_dir` (ex. `"plugin:SpeedPlugin"` → importa
  `source_dir / "plugin.py"`, pega `SpeedPlugin`).
- `Plugin.setup(self, ctx: "PipelineContext")` referencia um tipo definido em `pipeline.py` (camada acima).
  Em runtime não há circularidade (`from __future__ import annotations` mantém a anotação como string, nunca
  avaliada), mas para `mypy` passar `plugin.py` precisa de `if TYPE_CHECKING: from src.core.pipeline import
  PipelineContext`. Esse import só-de-tipo não cria import circular em runtime e o `mypy` resolve o ciclo
  normalmente; sem ele, `mypy` reprova `Name "PipelineContext" is not defined`.

### 1.3 `src/core/stages.py`

Contém, na íntegra, o bloco "Abstração Detector/Tracker" do `ARCHITECTURE.md`, **mais uma adição desta
fase** (`MetadataPlugin`), justificada por comentário no próprio arquivo: o `ARCHITECTURE.md` não mostra
uma base típica pro kind `metadata`, mas a prova de conceito da Fase 2 (portar `speed`/`border`) exige uma
classe tipada com um método único de execução — generaliza o mesmo padrão de `Detector`/`Tracker`.

```python
# src/core/stages.py
from __future__ import annotations
from abc import abstractmethod

from src.core.plugin import Plugin
from src.core.schema.detection import FrameDetections
from src.core.schema.track import Track
from src.core.schema.result import AnalysisContext

class Detector(Plugin):
    @abstractmethod
    def detect(self, frame: "RectifiedFrame") -> FrameDetections: ...

class Tracker(Plugin):
    @abstractmethod
    def update(self, dets: FrameDetections) -> None: ...
    @abstractmethod
    def tracks(self) -> list[Track]: ...
    def reset(self) -> None:
        return None

class MetadataPlugin(Plugin):
    """Base do kind='metadata'. O ARCHITECTURE.md ("Abstração Detector/Tracker") já
    inclui esta classe e fixa o nome do método como `run(ctx) -> None` — este plano usa
    exatamente esse nome (fonte da verdade). Substitui o antigo
    module_call(data: dict) -> dict: em vez de receber e devolver um dict cru, recebe o
    AnalysisContext tipado e MUTA-O in place via ctx.add_metric(...), sem retorno."""
    @abstractmethod
    def run(self, ctx: AnalysisContext) -> None: ...
```

`RectifiedFrame` ainda não existe (chega na Fase 3, junto do estágio Rectify). Em runtime isso não quebra a
Fase 2 (Detector não é instanciado, só declarado, e com `from __future__ import annotations` a anotação
nunca é avaliada). **Mas `mypy src/core/stages.py` (comando da seção 6) reprova uma referência a um nome
inexistente** — e um `TYPE_CHECKING` import de um módulo que ainda não existe reprova igual. Solução da Fase
2: definir um alias temporário no próprio `stages.py` sob `TYPE_CHECKING`
(`if TYPE_CHECKING: RectifiedFrame = object`), trocado pelo tipo real quando o estágio Rectify chegar na
Fase 3; alternativa: tipar `detect(self, frame: object)` por ora. Sem uma das duas, o critério "mypy limpo"
da fase falha.

### 1.4 `src/core/plugin_registry.py`

```python
# src/core/plugin_registry.py
from __future__ import annotations
import importlib.util
import logging
from pathlib import Path

from packaging.specifiers import SpecifierSet

from src.core.plugin import Plugin, PluginKind, PluginManifest, PluginSpec
from src.core.stages import Detector, Tracker, MetadataPlugin
from src.core.schema.result import SCHEMA_VERSION
from src.core.errors import (
    PluginApiVersionError, PluginSchemaVersionError, PluginContractError,
    PluginNotFoundError, PluginOrderingCycleError, PluginLoadError,
)

logger = logging.getLogger("animaltrack.plugin_registry")

SUPPORTED_API_VERSIONS = {"1.0"}

_KIND_BASE_CLASS: dict[PluginKind, type[Plugin]] = {
    PluginKind.DETECTOR: Detector,
    PluginKind.TRACKER: Tracker,
    PluginKind.METADATA: MetadataPlugin,
    # demais kinds (capture/rectify/fusion/exporter/interface) só exigem Plugin
    # até a classe-base própria existir (Fase 3/4).
}


class PluginRegistry:
    def __init__(self) -> None:
        self._specs: dict[tuple[PluginKind, str], PluginSpec] = {}
        self._instances: dict[tuple[PluginKind, str], Plugin] = {}
        self.discovery_warnings: list[str] = []

    # ---- discovery -------------------------------------------------
    def discover(self, search_paths: list[Path]) -> None:
        """Varre cada diretório em search_paths por <root>/<nome>/plugin.toml (1 nível).
        Registro é 'preguiçoso': só lê e valida o manifest, não importa plugin.py
        ainda. Manifest inválido é logado e pulado — nunca derruba a descoberta."""
        for root in search_paths:
            if not root.is_dir():
                continue
            for manifest_path in sorted(root.glob("*/plugin.toml")):
                try:
                    manifest = PluginManifest.from_toml(manifest_path)
                except Exception as exc:  # manifest malformado
                    msg = f"manifest inválido em {manifest_path}: {exc}"
                    logger.warning(msg)
                    self.discovery_warnings.append(msg)
                    continue

                key = (manifest.kind, manifest.name)
                if key in self._specs:
                    msg = (f"plugin duplicado {key} encontrado em {manifest_path} "
                           f"(mantendo o primeiro descoberto: {self._specs[key].source_dir})")
                    logger.warning(msg)
                    self.discovery_warnings.append(msg)
                    continue

                self._specs[key] = PluginSpec(manifest=manifest, source_dir=manifest_path.parent)

    # ---- instantiate -------------------------------------------------
    def instantiate(self, spec: PluginSpec) -> Plugin:
        """1) valida api_version; 2) valida schema range; 3) importa entry;
        4) valida subclasse; 5) injeta manifest; 6) instancia."""
        if spec.manifest.api_version not in SUPPORTED_API_VERSIONS:
            raise PluginApiVersionError(
                f"{spec.manifest.name}: api_version {spec.manifest.api_version} não suportada "
                f"(suportadas: {sorted(SUPPORTED_API_VERSIONS)})"
            )

        if not SpecifierSet(spec.manifest.schema).contains(SCHEMA_VERSION):
            raise PluginSchemaVersionError(
                f"{spec.manifest.name}: schema {spec.manifest.schema} incompatível "
                f"com SCHEMA_VERSION={SCHEMA_VERSION}"
            )

        module_name, _, class_name = spec.manifest.entry.partition(":")
        module_path = spec.source_dir / f"{module_name}.py"
        try:
            mod_spec = importlib.util.spec_from_file_location(
                f"animaltrack_plugin_{spec.manifest.kind}_{spec.manifest.name}", module_path
            )
            module = importlib.util.module_from_spec(mod_spec)
            mod_spec.loader.exec_module(module)  # type: ignore[union-attr]
            plugin_cls = getattr(module, class_name)
        except Exception as exc:
            raise PluginLoadError(f"{spec.manifest.name}: falha ao importar {module_path}: {exc}") from exc

        required_base = _KIND_BASE_CLASS.get(spec.manifest.kind, Plugin)
        if not (isinstance(plugin_cls, type) and issubclass(plugin_cls, required_base)):
            raise PluginContractError(
                f"{spec.manifest.name}: {class_name} não é subclasse de {required_base.__name__}"
            )

        plugin_cls.manifest = spec.manifest  # injeção pós-import, ver Plugin docstring
        try:
            return plugin_cls()
        except Exception as exc:
            raise PluginLoadError(f"{spec.manifest.name}: falha ao instanciar: {exc}") from exc

    # ---- get / for_kind -------------------------------------------------
    def get(self, kind: PluginKind, name: str) -> Plugin:
        key = (kind, name)
        if key in self._instances:
            return self._instances[key]
        if key not in self._specs:
            raise PluginNotFoundError(f"plugin não encontrado: kind={kind} name={name}")
        instance = self.instantiate(self._specs[key])
        self._instances[key] = instance
        return instance

    def for_kind(self, kind: PluginKind) -> list[Plugin]:
        """Instancia (com isolamento de erro — ver seção 3) todos os specs do kind,
        depois ordena topologicamente por before/after/priority."""
        candidates: list[Plugin] = []
        for (k, name), spec in self._specs.items():
            if k != kind:
                continue
            try:
                candidates.append(self.get(kind, name))
            except Exception as exc:
                # inclui type(exc).__name__ para que discovery_warnings mencione a classe
                # de erro (ex. PluginApiVersionError) — checado pelos testes de versionamento.
                msg = f"plugin {kind}:{name} não pôde ser instanciado ({type(exc).__name__}), pulado: {exc}"
                logger.warning(msg)
                self.discovery_warnings.append(msg)
                continue
        return _topological_order(candidates)


def _topological_order(nodes: list[Plugin]) -> list[Plugin]:
    """Kahn's algorithm com desempate por priority (maior primeiro) e depois por nome
    (determinístico). Ver passo a passo abaixo do bloco de código."""
    by_name = {n.manifest.name: n for n in nodes}
    names = set(by_name)

    # arestas: A -> B significa "A deve rodar antes de B"
    edges: dict[str, set[str]] = {n: set() for n in names}
    in_degree: dict[str, int] = {n: 0 for n in names}

    def add_edge(a: str, b: str) -> None:
        if b not in edges[a]:
            edges[a].add(b)
            in_degree[b] += 1

    for name, node in by_name.items():
        ordering = node.manifest.ordering
        for other in ordering.after:
            if other not in names:
                logger.warning(f"{name}: ordering.after referencia '{other}', não descoberto no kind atual — ignorado")
                continue
            add_edge(other, name)          # other roda antes de name
        for other in ordering.before:
            if other not in names:
                logger.warning(f"{name}: ordering.before referencia '{other}', não descoberto no kind atual — ignorado")
                continue
            add_edge(name, other)          # name roda antes de other

    ready = sorted(
        (n for n in names if in_degree[n] == 0),
        key=lambda n: (-by_name[n].manifest.ordering.priority, n),
    )
    result: list[Plugin] = []
    while ready:
        current = ready.pop(0)
        result.append(by_name[current])
        for successor in sorted(edges[current]):
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                ready.append(successor)
        ready.sort(key=lambda n: (-by_name[n].manifest.ordering.priority, n))

    if len(result) != len(names):
        stuck = names - {n.manifest.name for n in result}
        raise PluginOrderingCycleError(f"ciclo de ordenação detectado entre: {sorted(stuck)}")

    return result
```

**Algoritmo de ordenação topológica, passo a passo** (documentar exatamente assim no plano/handoff, é o
núcleo do requisito de "spell out the algorithm"):
1. Nós = nomes dos plugins **já instanciados com sucesso** daquele `kind` (falhas de instanciação já foram
   isoladas e removidas em `for_kind`, antes de chegar aqui).
2. Arestas: para cada plugin `P`, cada nome em `P.ordering.after` gera aresta `outro → P` ("outro roda antes
   de P"); cada nome em `P.ordering.before` gera aresta `P → outro` ("P roda antes de outro"). Se `outro`
   não estiver entre os nós descobertos deste `kind`, a restrição é **ignorada com warning** (não é erro
   fatal — o plugin referenciado pode não estar instalado neste ambiente).
3. Calcula grau de entrada (`in_degree`) de cada nó a partir das arestas mantidas.
4. Fila de prontos = nós com `in_degree == 0`, ordenada por `(-priority, nome)` — ou seja, **maior
   `priority` primeiro**; em empate, ordem alfabética do nome (determinístico, sem depender de hash/seed).
5. Laço de Kahn: remove o primeiro da fila de prontos, adiciona ao resultado, decrementa `in_degree` de
   cada sucessor; sucessor que chega a zero entra na fila de prontos; refaz o sort da fila a cada iteração
   (mantém o desempate correto conforme novos nós entram).
6. Se ao final `len(resultado) != len(nós)`, sobrou pelo menos um nó nunca liberado — **ciclo** — levanta
   `PluginOrderingCycleError` nomeando os nós presos. Este erro **não é isolado por plugin** — é erro de
   configuração e propaga para fora de `for_kind`/`Pipeline.run`.
7. Convenção de `priority` documentada explicitamente (o `ARCHITECTURE.md` não define a direção): **maior
   número roda mais cedo** dentre os candidatos sem dependência pendente no momento.

**Dependência nova (`packaging`)**: `SpecifierSet` (usado em `instantiate` para validar o range `schema`)
vem do pacote `packaging`, que **não** está na lista de dependências da Fase 0 do `ARCHITECTURE.md`
(numpy/opencv-python/pydantic/typer/matplotlib/xhtml2pdf/pandas/pillow). `packaging` costuma vir
transitivamente (setuptools/pip o vendorizam), mas depender disso é frágil e mypy/CI podem não tê-lo.
Declará-lo explicitamente no `pyproject.toml` é pré-requisito de `plugin_registry.py` nesta fase.

### 1.5 `src/core/pipeline.py`

```python
# src/core/pipeline.py
from __future__ import annotations
import logging
import time
import traceback
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.core.plugin import PluginKind
from src.core.plugin_registry import PluginRegistry
from src.core.workspace import Workspace
from src.core.store import ResultStore
from src.core.schema.result import AnalysisContext, AnalysisResult
from src.core.errors import PluginOrderingCycleError

logger = logging.getLogger("animaltrack.pipeline")


class RunRequest(BaseModel):
    profile: str
    workspace: str                                    # path serializável (Workspace.root)
    plugin_selection: dict[PluginKind, list[str]] = Field(default_factory=dict)
    gpu: bool = False
    overrides: dict[str, Any] = Field(default_factory=dict)


class PluginFailure(BaseModel):
    kind: PluginKind
    name: str
    stage: Literal["setup", "run", "teardown"]
    error_type: str
    message: str
    traceback: str | None = None


class RunResult(BaseModel):
    profile: str
    success: bool
    result: AnalysisResult | None = None
    plugin_failures: list[PluginFailure] = Field(default_factory=list)
    duration_seconds: float | None = None


@dataclass
class PipelineContext:
    """Estado vivo de orquestração — objetos não-serializáveis (registry, workspace).
    Deliberadamente NÃO é pydantic: RunRequest/RunResult cruzam fronteiras de
    serialização (CLI, futura API); PipelineContext só existe em memória durante
    Pipeline.run()."""
    request: RunRequest
    registry: PluginRegistry
    workspace: Workspace


class Pipeline:
    """Escopo da Fase 2: só o estágio metadata sobre um AnalysisResult já persistido.
    Capture/Rectify/Detect/Track/Fuse chegam na Fase 3 — não há stubs mortos aqui, só
    este comentário como marcador de escopo."""

    def __init__(self, registry: PluginRegistry) -> None:
        self._registry = registry

    def run(self, request: RunRequest) -> RunResult:
        start = time.monotonic()
        workspace = Workspace(root=request.workspace)
        store = ResultStore(workspace)
        result = store.load(request.profile)

        ctx = AnalysisContext(result=result)
        pctx = PipelineContext(request=request, registry=self._registry, workspace=workspace)

        failures: list[PluginFailure] = []
        requested_metadata = set(request.plugin_selection.get(PluginKind.METADATA, []))

        try:
            ordered_metadata = self._registry.for_kind(PluginKind.METADATA)
        except PluginOrderingCycleError:
            raise  # erro de configuração — fatal, propaga (não é isolado por plugin)

        for plugin in ordered_metadata:
            if requested_metadata and plugin.manifest.name not in requested_metadata:
                continue
            for stage, action in (
                ("setup", lambda: plugin.setup(pctx)),
                ("run", lambda: plugin.run(ctx)),
                ("teardown", lambda: plugin.teardown()),
            ):
                try:
                    action()
                except Exception as exc:
                    logger.error(
                        "plugin %s:%s falhou no estágio %s: %s",
                        plugin.manifest.kind, plugin.manifest.name, stage, exc,
                        exc_info=True,
                    )
                    failures.append(PluginFailure(
                        kind=plugin.manifest.kind,
                        name=plugin.manifest.name,
                        stage=stage,
                        error_type=type(exc).__name__,
                        message=str(exc),
                        traceback=traceback.format_exc()[-4000:],
                    ))
                    break  # não roda run/teardown se setup já falhou p/ este plugin

        store.save(request.profile, ctx.result)

        return RunResult(
            profile=request.profile,
            success=True,   # falhas de plugin isoladas não derrubam o run — ver seção 3
            result=ctx.result,
            plugin_failures=failures,
            duration_seconds=time.monotonic() - start,
        )
```

Notas de escopo a manter no código:
- `Capture`/`Rectify`/`Detect`/`Track`/`Fuse` **não aparecem** no corpo de `run()` nesta fase — só chegam na
  Fase 3. O único estágio exercitado de ponta a ponta é `metadata`, operando sobre um `AnalysisResult`
  **já existente** (carregado via `ResultStore`), reproduzindo exatamente o papel do antigo
  `execute_metadata_module_calls` (recalcular metadata de um perfil já processado), só que generalizado.
- `plugin_selection` vazio pra um kind = "rodar todos os descobertos daquele kind, na ordem do registry".

### 1.6 `src/core/gpu.py` (paralelizável desde o início — ver seção 4)

```python
# src/core/gpu.py
from __future__ import annotations
from pydantic import BaseModel


class GpuProbeResult(BaseModel):
    available: bool
    device_count: int
    driver_info: str | None = None


def probe_cuda_devices() -> GpuProbeResult:
    """Probe de capacidade CUDA. Nunca lança — é usado no startup (Fase 5) pra decidir
    se o requisito de GPU é satisfeito, mas o enforcement em si (falhar alto se
    ausente) só entra na Fase 5. Aqui é só o stub de report."""
    try:
        import cv2
        count = cv2.cuda.getCudaEnabledDeviceCount()
        return GpuProbeResult(available=count > 0, device_count=count)
    except Exception:
        # cobre ImportError (sem cv2), AttributeError (cv2 sem submódulo cuda) e
        # cv2.error (build sem suporte CUDA que levanta em vez de retornar 0) — a
        # promessa "nunca lança" exige captura ampla aqui.
        return GpuProbeResult(available=False, device_count=0)
```

### 1.7 `plugins/speed/plugin.toml` + `plugins/speed/plugin.py`

`plugins/speed/plugin.toml`:
```toml
[plugin]
name        = "speed"
version     = "1.0.0"
kind        = "metadata"
entry       = "plugin:SpeedPlugin"
api_version = "1.0"
schema      = ">=1.0,<2.0"

[requires]
python   = ">=3.11"
packages = []
plugins  = []

[ordering]
before = []
after  = []
priority = 0
```

`plugins/speed/plugin.py`:
```python
# plugins/speed/plugin.py
from __future__ import annotations
import math

from src.core.stages import MetadataPlugin
from src.core.schema.result import AnalysisContext, Metric


class SpeedPlugin(MetadataPlugin):
    def run(self, ctx: AnalysisContext) -> None:
        result = ctx.result
        route = next((r for r in result.routes if r.entity_id == 0), None)
        if route is None or not route.points:
            raise ValueError("SpeedPlugin: nenhuma rota encontrada para entity_id=0")

        # TODO(fase3, bug #2 do ARCHITECTURE.md): a fórmula abaixo preserva o bug de
        # dupla divisão por ratio do MetadataModule/speedModule.py original
        # (distance já embute o ratio, e speed divide por ratio de novo). NÃO
        # CORRIGIR AQUI — adapter fino, correção é tarefa explícita da Fase 3.
        px_per_cm = result.calibration.px_per_cm
        # ratio único: o antigo pixel_to_cm_ratio era escalar; o novo Calibration é por
        # eixo (bug #3 do ARCHITECTURE.md, só corrigido via axis_mapping() na Fase 3).
        # Aqui usamos a média dos 3 componentes como aproximação equivalente ao escalar
        # antigo, só para manter o adapter fino executável nesta fase.
        ratio = (px_per_cm.x + px_per_cm.y + px_per_cm.z) / 3

        ordered = sorted(route.points.items())  # [(frame_index, Point3D), ...]
        previous = None
        speed_by_frame: dict[str, float] = {}
        distance_total = 0.0
        speed_total = 0.0

        for frame_index, point in ordered:
            if previous is None:
                previous = point
                continue
            distance = math.dist(
                (previous.x, previous.y, previous.z), (point.x, point.y, point.z)
            ) * ratio / 100
            speed = distance / ratio
            speed_by_frame[str(frame_index)] = speed
            distance_total += distance
            speed_total += speed
            previous = point

        average_speed = speed_total / len(route.points) if route.points else 0.0

        ctx.add_metric(Metric(name="speed", value=speed_by_frame, unit=None, producer="speed"))
        ctx.add_metric(Metric(name="average_speed", value=average_speed, unit=None, producer="speed"))
        ctx.add_metric(Metric(name="distance_total", value=distance_total, unit="cm", producer="speed"))
```

Diferenças deliberadas vs. o original (documentar no handoff, não são "correções" — são adaptações
necessárias pro novo tipo, sem mudar o resultado numérico do caso feliz):
- Iteração por `sorted(route.points.items())` em vez de checar `index == '0'`: `Route3D.points` pode ter
  buracos (oclusão), diferente do dict antigo que sempre tinha `'0','1',2,...` contíguos com sentinela
  `(-1,-1,-1)`. "Primeiro ponto disponível" é o análogo correto de "frame 0" no novo schema.
- `pixel_to_cm_ratio` escalar → média dos 3 componentes de `Calibration.px_per_cm`. Decisão explícita,
  documentada inline, não escondida.
- Chaves do dict `speed` são `str(frame_index)`, não `int`: (a) o `speedObj` antigo já usava chaves string
  (o `route` original tinha chaves `'0','1',...`), então preserva o comportamento; (b) `Metric.value` é
  `JsonSafeValue`, cujo tipo de dict é `dict[str, JsonSafeValue]` — chave `int` violaria a tipagem estática
  do round-trip JSON.
- Falta de rota → `ValueError` explícito (vira `PluginFailure` isolado pelo pipeline, não um `KeyError`
  solto como seria com o dict antigo).

### 1.8 `plugins/border/plugin.toml` + `plugins/border/plugin.py`

`plugins/border/plugin.toml`:
```toml
[plugin]
name        = "border"
version     = "1.0.0"
kind        = "metadata"
entry       = "plugin:BorderPlugin"
api_version = "1.0"
schema      = ">=1.0,<2.0"

[requires]
python   = ">=3.11"
packages = []
plugins  = []

[ordering]
before = []
after  = ["speed"]
priority = 0
```

`plugins/border/plugin.py`:
```python
# plugins/border/plugin.py
from __future__ import annotations

from src.core.stages import MetadataPlugin
from src.core.schema.result import AnalysisContext, Metric


class BorderPlugin(MetadataPlugin):
    def run(self, ctx: AnalysisContext) -> None:
        result = ctx.result
        if result.border_region is None:
            raise ValueError("BorderPlugin: border_region ausente em AnalysisResult")
        route = next((r for r in result.routes if r.entity_id == 0), None)
        if route is None:
            raise ValueError("BorderPlugin: nenhuma rota encontrada para entity_id=0")

        # BorderRegion.bounds já traz min/max por eixo 3D (ver seção 0). O plugin só conta
        # containment — a antiga derivação de min/max a partir de pontos de pixel (e a
        # mistura de eixos de borderModule.py) vive upstream de quem popula `bounds`.
        bounds = result.border_region.bounds
        min_x, max_x = bounds["x"]
        min_y, max_y = bounds["y"]
        min_z, max_z = bounds["z"]

        time_x = time_y = time_z = 0
        for point in route.points.values():
            if min_x <= point.x <= max_x:
                time_x += 1
            if min_y <= point.y <= max_y:
                time_y += 1
            if min_z <= point.z <= max_z:
                time_z += 1

        ctx.add_metric(Metric(name="time_border_x", value=time_x, unit="frames", producer="border"))
        ctx.add_metric(Metric(name="time_border_y", value=time_y, unit="frames", producer="border"))
        ctx.add_metric(Metric(name="time_border_z", value=time_z, unit="frames", producer="border"))
```

`ordering.after = ["speed"]` é o exemplo canônico pedido para o teste de ordenação topológica (seção 5).

**Pré-requisito deste workstream**: confirmar que `src/core/schema/result.py` expõe `BorderRegion` no
formato `{threshold_px, bounds}` da Fase 1 (ver seção 0). Se estiver ausente/divergente, é pendência da
Fase 1 a reportar — não redefinir aqui com outro formato.

---

## 2. Mapeamento de contrato — resumo

| Antigo | Novo |
|---|---|
| `module_call(data: dict) -> dict` | `MetadataPlugin.run(self, ctx: AnalysisContext) -> None` |
| retorna dict mutado | muta `ctx` in place via `ctx.add_metric(Metric(...))`, sem retorno |
| descoberta: `os.listdir` + `importlib` direto no chamador | `PluginRegistry.discover()` + `for_kind()`, manifest + versionamento + ordenação |
| ordem: ordem do `os.listdir` (não determinística) | ordem topológica declarada via `plugin.toml` (`before`/`after`/`priority`) |
| erro em um módulo derruba `execute_metadata_module_calls` inteiro | erro isolado por plugin/estágio, vira `PluginFailure`, run continua (seção 3) |
| `data["pixel_to_cm_ratio"]` (dict cru, `KeyError` se ausente) | `ctx.result.calibration.px_per_cm` (tipado, `Point3D`, sem `KeyError` solto) |

---

## 3. Isolamento de erro — comportamento exato

**Onde cada tipo de falha é tratado:**

1. **Falha de instanciação de plugin** (manifest com `api_version`/`schema` incompatível, import quebrado,
   classe não é subclasse da base exigida) — tratada **dentro de `PluginRegistry.for_kind()`**: cada
   candidato é envolto em `try/except Exception`; em falha, loga `WARNING` com nome do plugin + causa,
   adiciona a mensagem em `registry.discovery_warnings`, e **exclui** o plugin da lista retornada. Essas
   falhas **nunca aparecem em `RunResult.plugin_failures`** — não chegaram a rodar, são um problema de
   descoberta/configuração, visíveis só via log e via `discovery_warnings` (útil para um futuro
   `animaltrack list-plugins --verbose`).
2. **Ciclo de ordenação** (`PluginOrderingCycleError`) — **não é isolado por plugin**. É erro de
   configuração do conjunto (dois manifests se referenciam circularmente via `before`/`after`), propaga
   para fora de `for_kind()` e de `Pipeline.run()` — o run inteiro falha (fatal), porque não há uma ordem
   válida possível de decidir sozinho.
3. **Falha durante execução de um plugin já instanciado** (exceção dentro de `setup`, `run` ou
   `teardown`) — tratada **dentro de `Pipeline.run()`**: cada chamada de estágio (`setup`/`run`/
   `teardown`) de cada plugin roda em seu próprio `try/except Exception`. Em falha:
   - Log `ERROR` via `logging.getLogger("animaltrack.pipeline")`, `exc_info=True` (traceback completo vai
     pro handler de log, não necessariamente pro resultado persistido).
   - Registra `PluginFailure(kind, name, stage, error_type=type(exc).__name__, message=str(exc),
     traceback=<últimos 4000 chars de traceback.format_exc()>)` em `RunResult.plugin_failures`.
   - O `break` no laço de estágios significa que, se `setup` falhar, `run`/`teardown` não rodam; e se `run`
     falhar, `teardown` **também** não roda para aquele plugin. Para os plugins desta fase (`teardown` é
     no-op) isso é inofensivo, mas quando surgirem plugins com estado/recursos, `teardown` deveria rodar
     sempre que `setup` teve sucesso — trocar o `break` por um `try/finally` em torno de `run`/`teardown`. O
     laço externo **continua** para o próximo plugin normalmente.
   - `ctx`/`AnalysisResult` acumulado por plugins anteriores bem-sucedidos **não é revertido** — não há
     rollback automático de contexto. Documentar como responsabilidade do autor do plugin manter
     `run()` o mais atômico possível (calcular tudo localmente, só então `ctx.add_metric(...)` no final,
     nunca metade das métricas).
4. **`RunResult.success`** permanece `True` sempre que o run **chegou a terminar o laço de plugins e
   salvar o resultado** — mesmo com `plugin_failures` não vazio ("run degradado, mas completo"). Só fica
   `False`/a exceção propaga quando algo fatal acontece **antes** de chegar ao laço de plugins (perfil não
   encontrado no `ResultStore`, `PluginOrderingCycleError`). Consumidores (CLI/GUI, Fase 4) devem checar
   `if run_result.plugin_failures:` para exibir aviso, mesmo com `success=True`.

---

## 4. Paralelização — confirmação e refinamento

Confirmando a estrutura proposta, com um refinamento:

- **Agente A (sequencial, 1 agente)**: `src/core/errors.py` → `src/core/plugin.py` → `src/core/stages.py`
  → `src/core/plugin_registry.py` → `src/core/pipeline.py`, nessa ordem exata — cada um importa o
  anterior (`stages.py` importa `Plugin` de `plugin.py`; `plugin_registry.py` importa `stages.py` para o
  mapa `_KIND_BASE_CLASS` e `errors.py`; `pipeline.py` importa `plugin_registry.py`).
- **Agente B (`src/core/gpu.py`) — refinamento confirmado**: `gpu.py` não tem nenhuma dependência de
  `Plugin`/`PluginRegistry`/`Pipeline` (só usa `cv2` e `pydantic.BaseModel`). Roda em **paralelo total ao
  Agente A, desde o início** — não há razão para esperar a cadeia sequencial. Isso é uma correção ao
  desenho ingênuo de "3 arquivos sequenciais" — `gpu.py` sai do meio da cadeia e vira um workstream
  independente de zero dependências.
- **Agentes C e D (`plugins/speed`, `plugins/border`)**: mantida a recomendação do `ARCHITECTURE.md` de
  esperar a cadeia completa do Agente A (`plugin.py`+`stages.py`+`plugin_registry.py`+`pipeline.py`)
  terminar e mergear antes de abrir os 2 workstreams em paralelo. Nota técnica registrada: os dois plugins
  só importam `MetadataPlugin` (de `stages.py`) e tipos de schema — estritamente falando poderiam começar
  assim que `plugin.py`+`stages.py` estiverem prontos e testados, sem esperar `plugin_registry.py`/
  `pipeline.py`. Essa aceleração é **opcional**, não a recomendação padrão: esperar a cadeia inteira reduz
  o risco de `plugin_registry.py` revelar, durante sua implementação, algum ajuste necessário em
  `PluginManifest`/`Plugin` que obrigaria retrabalho nos plugins já escritos. Escolher a aceleração só se
  houver 4 agentes disponíveis simultaneamente e o dono do projeto aceitar o risco de retrabalho.
  Isolamento por worktree: `plugins/speed/*` e `plugins/border/*` são diretórios disjuntos — zero conflito
  de arquivo entre C e D.

Resumo da linha do tempo recomendada:
```
t0 ────────────────────────────────────────────────────────────────▶
Agente A: errors.py → plugin.py → stages.py → plugin_registry.py → pipeline.py ─┐
Agente B: gpu.py (paralelo total, começa em t0)                                 │
                                                                                  ├─▶ merge A
                                                                    Agente C: plugins/speed   (paralelo)
                                                                    Agente D: plugins/border  (paralelo)
                                                                                  └─▶ merge C+D → testes de integração
```

---

## 5. Plano de teste

### `tests/core/test_plugin_manifest.py`
- Manifest válido (todas as chaves do exemplo do `ARCHITECTURE.md`) parseia sem erro via
  `PluginManifest.from_toml`.
- Manifest com `kind` desconhecido (ex. `"foo"`) rejeitado (`ValidationError`/`PluginManifestError`).
- Manifest sem `entry` (campo obrigatório) rejeitado.
- Manifest sem seções `[requires]`/`[ordering]` usa defaults (`PluginRequires()`/`PluginOrdering()`).

### `tests/core/test_plugin_registry_discovery.py`
- Fixtures em `tests/fixtures/plugins/{valido, invalido_sem_entry, invalido_kind_ruim}/plugin.toml`
  (+ `plugin.py` mínimo pro caso válido).
- `registry.discover([tests_fixtures_dir])`; assert plugin válido presente em `registry._specs` (ou via
  `for_kind`); assert inválidos ausentes e cada um gerou entrada em `registry.discovery_warnings`
  (`caplog` captura o `WARNING` também).

### `tests/core/test_plugin_registry_versioning.py`
- Plugin com `api_version = "99.0"` → `for_kind` não o inclui no resultado; `discovery_warnings` menciona
  `PluginApiVersionError`.
- Plugin com `schema = ">=99.0"` → idem, `PluginSchemaVersionError`.

### `tests/core/test_plugin_registry_ordering.py`
- **Caso concreto pedido — "border after speed"**: 2 fixtures `kind=metadata`: `speed` (`ordering`
  default) e `border` (`ordering.after = ["speed"]`). `registry.for_kind(PluginKind.METADATA)` deve
  devolver `[speed_instance, border_instance]` nessa ordem exata (`[p.manifest.name for p in ...] ==
  ["speed", "border"]`).
- Caso de desempate por `priority`: 2 plugins sem relação `before`/`after` entre si, `priority=10` e
  `priority=0` — o de `priority=10` vem primeiro.
- Caso de ciclo: `A.ordering.after = ["B"]`, `B.ordering.after = ["A"]` → `for_kind` levanta
  `PluginOrderingCycleError` nomeando `{"A", "B"}`.
- Caso de referência a nome ausente: `A.ordering.after = ["nao_existe"]` → não levanta erro, só warning,
  `A` aparece normalmente no resultado.

### `tests/core/test_pipeline_error_isolation.py`
- 2 plugins dummy `kind=metadata` registrados diretamente no registry (sem passar por disco, via
  instância manual ou fixture on-disk); um deles lança `RuntimeError` dentro de `run`.
- `Pipeline(registry).run(request)` com os dois selecionados.
- Assert: `len(run_result.plugin_failures) == 1`, `plugin_failures[0].name` == nome do plugin quebrado,
  `plugin_failures[0].stage == "run"`.
- Assert: a métrica produzida pelo plugin **que funcionou** está presente em
  `run_result.result.metrics` — prova que ele não foi pulado/abortado pela falha do outro.
- Assert: `run_result.success is True` (falha isolada não derruba o run).

### `tests/core/test_gpu_probe.py`
- `probe_cuda_devices()` não lança mesmo com `cv2.cuda` ausente/removido via monkeypatch (simula
  `AttributeError`); resultado `GpuProbeResult(available=False, device_count=0)`.
- (Se ambiente de CI tiver `cv2` sem submódulo cuda de verdade, esse já é o caminho natural — não precisa
  necessariamente mockar.)

### `tests/plugins/test_speed_plugin.py`
- Fixture: `AnalysisResult` mínimo com `routes=[Route3D(entity_id=0, points={0: Point3D(...), 1:
  Point3D(...), 2: Point3D(...)})]` e `calibration.px_per_cm` fixo.
- Roda `SpeedPlugin().run(ctx)`; assert `ctx.result.metrics["speed"].value`, `["average_speed"].value`,
  `["distance_total"].value` batem com valores calculados à mão usando a **fórmula antiga preservando o
  bug** (dupla divisão por ratio) — este teste é intencionalmente um teste de regressão que fixa o
  comportamento atual (mesmo sabendo que é "errado"), para servir de diff de comparação quando a Fase 3
  corrigir o bug #2.
- Caso de erro: `AnalysisResult` sem nenhuma rota com `entity_id=0` → `run` levanta `ValueError`.

### `tests/plugins/test_border_plugin.py`
- Fixture: `AnalysisResult` com `border_region=BorderRegion(bounds={"x": (0.0, 10.0), "y": (0.0, 10.0),
  "z": (0.0, 10.0)})` e uma rota com pontos dentro/fora desses limites.
- Assert `time_border_x/y/z` batem com a contagem calculada à mão de containment por eixo contra `bounds`
  (a derivação/mistura de eixos legada é upstream, não é responsabilidade deste plugin — ver seção 0).
- Caso de erro: `border_region is None` → `ValueError`.

### `tests/core/test_pipeline_metadata_e2e.py`
- Integração real (não dummy): `registry.discover([Path("plugins")])`, `Pipeline(registry).run(RunRequest(
  profile=..., plugin_selection={PluginKind.METADATA: ["speed", "border"]}))` sobre uma fixture de
  `AnalysisResult` gravada via `ResultStore` antes do teste.
- Assert `run_result.result.metrics` contém todas as chaves: `speed`, `average_speed`, `distance_total`,
  `time_border_x`, `time_border_y`, `time_border_z`.
- Assert ordem de execução respeitada (checável indiretamente, ou via um hook de instrumentação simples
  nos plugins de teste, se necessário).

---

## 6. Comandos de verificação

```bash
# testes
pytest tests/core tests/plugins -q

# lint
ruff check src/core/plugin.py src/core/plugin_registry.py src/core/pipeline.py \
           src/core/stages.py src/core/gpu.py src/core/errors.py \
           plugins/speed plugins/border

# tipos
mypy src/core/plugin.py src/core/plugin_registry.py src/core/pipeline.py \
     src/core/stages.py src/core/gpu.py src/core/errors.py

# smoke manual de discovery + ordenação
python -c "
from pathlib import Path
from src.core.plugin_registry import PluginRegistry
from src.core.plugin import PluginKind
r = PluginRegistry()
r.discover([Path('plugins')])
print([p.manifest.name for p in r.for_kind(PluginKind.METADATA)])
"
# saída esperada: ['speed', 'border']
```

Critério de "fase concluída": todos os comandos acima passam limpos, mais os testes end-to-end de
`test_pipeline_metadata_e2e.py` verdes rodando os plugins reais (não dummies) contra uma fixture de
`AnalysisResult`.

---

## 7. Prontidão para handoff — checkpoints seguros

Registrar em `docs/handoffs/fase2-<workstream>-handoff.md` a cada checkpoint (protocolo obrigatório do
`ARCHITECTURE.md`), e consolidar em `docs/handoffs/PROGRESS.md` ao final da fase.

- **Checkpoint 1** — fim de `errors.py` + `plugin.py` + `stages.py`, com `test_plugin_manifest.py` verde.
  Seguro pausar aqui: o próximo passo (`plugin_registry.py`) é aditivo, não exige revisitar nada já feito.
- **Checkpoint 2** (mais valioso) — fim de `plugin_registry.py`, com `test_plugin_registry_discovery.py`,
  `test_plugin_registry_versioning.py` e `test_plugin_registry_ordering.py` verdes. Em tese já libera o
  início dos workstreams `speed`/`border` (ver nota de aceleração opcional na seção 4), mesmo que
  `pipeline.py` ainda não exista.
- **Checkpoint 3** — fim de `pipeline.py`, com `test_pipeline_error_isolation.py` verde. Fim oficial do
  Agente A — ponto padrão de fork para os Agentes C/D.
- **Checkpoint 4** — `gpu.py` com `test_gpu_probe.py` verde (independente dos demais, pode ser marcado
  "done" a qualquer momento a partir de t0).
- **Checkpoint 5a/5b** — um dos dois plugins portados (`speed` ou `border`) concluído e testado
  individualmente. Se só houver 1 agente disponível para os dois workstreams em sequência (em vez de 2 em
  paralelo): fazer `speed` primeiro (sem dependência de gap de schema), só depois `border` (que exige
  checar/estender `BorderRegion` primeiro — ver seção 0).
- **Checkpoint final** — os dois plugins mergeados + `test_pipeline_metadata_e2e.py` verde: fase 2
  encerrada, consolidar `docs/handoffs/PROGRESS.md` e liberar a Fase 3.
