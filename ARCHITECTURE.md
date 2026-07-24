# Arquitetura alvo — Comportamento Animal (ex-TCC abelhas)

> Este documento é a referência viva da rearquitetura do projeto. Substitui o desenho de camadas atual
> (ver `CLAUDE.md` para o estado do código *hoje*) pelo alvo de longo prazo. Planos detalhados por fase
> **já existem** em `docs/plans/fase<N>-detalhado.md` (0 a 6) e `docs/plans/ux-design-detalhado.md` —
> cada um foi produzido por um subagente dedicado que leu o código atual em detalhe e encontrou correções
> reais sobre este documento, já incorporadas abaixo. Progresso de execução (incluindo handoffs entre
> sessões) vive em `docs/handoffs/PROGRESS.md` (ainda não criado — nasce no início da implementação).

## Contexto

Projeto de TCC finalizado em 2024 (extração de trajetória 3D de um inseto único via 2 câmeras, sem IA no
núcleo). O objetivo de longo prazo é evoluir isso pra uma plataforma extensível multi-espécie/multi-animal,
com marketplace de módulos, mantendo o núcleo sem IA (a extração alimenta IA *externa*, não embute uma).

Decisões de visão já fixadas:
- GPU agora é **requisito** (não fallback opcional) — reverte a restrição original de CPU-only.
- Sem amarra de compatibilidade com `configs.json`/outputs antigos — reconstrução de arquitetura, não
  migração incremental.
- Modernização técnica e generalização de espécie avançam em paralelo, não em sequência.
- GUI (Tkinter) continua existindo, ganha modo headless/CLI.
- Marketplace de módulos: formato de backend ainda em aberto, mas o contrato de plugin deve ser
  marketplace-ready desde já.

Instrução que guia este desenho: **arquitetura em camadas/módulos sequenciais é a entrega fundamental** —
tudo mais (multi-animal tracking, marketplace, GPU) deve encaixar como plugin na arquitetura, não ser
codesenhado junto. Prioriza-se o esqueleto (camadas, contratos, schema, plugin registry, orquestração)
sobre qualquer feature específica.

Resultado esperado: repo nunca fica quebrado por mais de 1 PR/commit; cada fase roda e é útil sozinha;
multi-animal e GPU entram depois sem retrabalho de arquitetura.

---

## Arquitetura alvo — camadas

Fluxo estritamente esquerda→direita; cada camada só consome o tipo de saída da anterior (nunca acessa
camadas acima/abaixo diretamente).

```
                     ┌───────────────────────────────────────────┐
                     │ Core transversal (sem lógica de domínio)    │
                     │ workspace · config · plugin registry ·      │
                     │ schema/models · logging · erros             │
                     └───────────────────────────────────────────┘
Interface (IM) ──▶ Orquestração (Pipeline) ──▶ roda a cadeia de estágios abaixo
  GUI (Tk)                 │
  CLI/headless             ▼
        Capture ─▶ Rectify ─▶ Detect ─▶ Track ─▶ Fuse ─▶ Metadata ─▶ Export
        (fonte)  (perspectiva+ (por frame) (temporal)  (rota 3D,   (plugins MM) (plugins EM)
                   orientação)                          calibração)
```

| Camada | Pacote | Entrada → Saída | Tipo de plugin |
|---|---|---|---|
| Interface | `src/app/gui`, `src/app/cli` | intenção do usuário → `RunRequest`; renderiza `RunResult` | `interface` (futuro) |
| Orquestração | `src/core/pipeline.py` | `RunRequest` → `RunResult`; sequenciamento, config, isolamento de erro | motor, não plugin |
| Capture | `src/stages/capture` | `CaptureConfig` → `Iterator[FramePair]` (streaming) | `capture` |
| Rectify | `src/stages/rectify` | `FramePair` + `BoxOrientationConfig` → `RectifiedFramePair` | `rectify` |
| Detect | `src/stages/detect` | `RectifiedFrame` → `FrameDetections` (N blobs/frame/view) | `detector` |
| Track | `src/stages/track` | stream de `FrameDetections` → `list[Track]` (IDs persistentes) | `tracker` |
| Fuse | `src/stages/fuse` | `Track` topo + `Track` lateral + `Calibration` → `list[Route3D]` | `fusion` |
| Metadata | `src/stages/metadata` | `AnalysisContext` → adiciona `Metric`s | `metadata` (MM) |
| Export | `src/stages/export` | `AnalysisResult` → arquivos (JSON/PDF/gráfico) | `exporter` (EM) |

Diferença chave vs. hoje: `BasicModule` hoje colapsa Capture+Rectify+Detect+Fuse numa chamada bloqueante,
vídeo inteiro em RAM. Separamos **Detect** (espacial, por frame, 1 view, N entidades) de **Track**
(temporal, entre frames, atribuição de ID) de **Fuse** (reconstrução 3D entre views). Isso é o que
destrava multi-animal + oclusão depois sem tocar no esqueleto.

---

## Orientação de câmera/caixa (feature nova — resolve bug de eixo na raiz)

Hoje o sistema assume hardcoded: câmera do topo → sempre (x, z), câmera lateral → sempre y. Não há como o
sistema saber qual face da caixa cada câmera realmente vê, nem qual vértice cada ponto clicado representa.
Isso vira configuração explícita do usuário, não suposição fixa.

`src/core/schema/orientation.py`:
```python
class BoxFace(str, Enum):
    TOP = "top"; BOTTOM = "bottom"
    LEFT = "left"; RIGHT = "right"
    FRONT = "front"; BACK = "back"

class BoxVertex(str, Enum):
    # combinação das 3 dimensões, ex: TOP_FRONT_LEFT ... BOTTOM_BACK_RIGHT (8 vértices)
    ...

class CameraRole(str, Enum):
    TOP = "top"; SIDE = "side"   # fixo em 2 câmeras por decisão de escopo (não N câmeras arbitrárias, por ora)

class CameraOrientation(BaseModel):
    role: CameraRole
    face_viewed: BoxFace                # face da caixa que a câmera enxerga de frente
    corner_vertices: list[BoxVertex]    # os 4 vértices, na mesma ordem de clique do PerspectiveUi
                                          # (superior-direito, superior-esquerdo, inferior-direito, inferior-esquerdo)

class BoxOrientationConfig(BaseModel):
    top_camera: CameraOrientation
    side_camera: CameraOrientation

    def axis_mapping(self) -> "AxisMapping":
        """Deriva, por câmera, qual eixo de imagem (u/v) corresponde a qual eixo 3D da caixa (x/y/z)."""
```

Política de desempate (achado do plano detalhado da Fase 1: como as duas câmeras enxergam faces adjacentes,
mais de um eixo pode ser observável por ambas — ex. largura pode aparecer tanto no topo quanto na lateral
dependendo da orientação): **a câmera TOP tem prioridade** em caso de conflito — `axis_mapping()` sempre usa
a leitura da câmera TOP para um eixo que ambas as câmeras conseguem observar, e só recorre à câmera SIDE
para o eixo que exclusivamente ela enxerga. Espelha o comportamento implícito do `routeAnalizer.py` atual
(`top[0]→x, top[1]→y` sempre vencem; `side[0]` é descartado hoje).

`Calibration` deixa de assumir eixo fixo:
```python
class Calibration(BaseModel):
    box_cm: Point3D
    px_per_cm: Point3D      # por eixo, derivado via axis_mapping() — não mais 3 razões vindas de height_side
    fps: float
    orientation: BoxOrientationConfig
```

Nova tela `OrientationUi` (Fase 4): mostra um wireframe de referência da caixa, usuário escolhe por câmera
qual face ela enxerga e associa cada um dos 4 pontos clicados a um vértice. O `Fuse` stage usa
`axis_mapping()` pra combinar as duas views em x/y/z corretamente — isso substitui o hardcode
`top→(x,z), side→(y,_)` de `routeAnalizer.py` por mapeamento derivado.

Posição exata no fluxo de telas (achado do plano de UX Design): `OrientationUi` roda **imediatamente após
`PerspectiveUi` daquela mesma câmera**, por câmera — `Perspective(topo) → Orientation(topo) →
Perspective(lado) → Orientation(lado) → Border(topo) → Border(lado) → Processar`. Motivo: a tela consome
os 4 pontos já clicados daquela câmera específica ("este ponto é qual vértice?"), então precisa rodar
antes que o usuário mude de contexto pra outra câmera. Widget concreto: wireframe de cubo isométrico
clicável por face (`Canvas` do Tkinter) + dropdown por ponto já clicado, filtrado só pelos 4 vértices da
face escolhida (reduz erro por construção); mesmo trio de botões resetar/finalizar/voltar das telas
existentes. Ver `docs/plans/ux-design-detalhado.md` para o desenho completo.

---

## Contrato de plugin (generalizado de `module_call(data)->data`)

Único ponto de extensão hoje é `modulesInvoker.py`: scan flat de `os.listdir`,
`importlib.util.spec_from_file_location`, contrato duck-typed `module_call`. Mantemos o espírito
(descoberta dinâmica, arquivo solto) mas adicionamos manifest, classe base tipada, ordenação, versionamento
e isolamento de erro — aplicado a **toda** camada, não só MM.

Manifest `plugin.toml` (co-localizado com cada plugin):
```toml
[plugin]
name        = "background-subtraction-detector"
version     = "1.0.0"
kind        = "detector"          # capture|rectify|detector|tracker|fusion|metadata|exporter|interface
entry       = "plugin:BackgroundSubtractionDetector"
api_version = "1.0"
schema      = ">=1.0,<2.0"

[requires]
python   = ">=3.11"
packages = ["opencv-python>=4.9"]
plugins  = []

[ordering]
before = []
after  = ["speed"]
priority = 100
```

Esse manifest tem o mesmo formato que uma entrada de marketplace futura carregaria (nome/versão/tipo/
requisitos) — pronto pra marketplace sem comprometer backend agora. Plugins locais em
`plugins/<nome>/{plugin.toml, plugin.py}`.

`src/core/plugin.py`:
```python
class Plugin(ABC):
    manifest: ClassVar[PluginManifest]
    def setup(self, ctx: "PipelineContext") -> None: ...
    def teardown(self) -> None: ...
```

`src/core/plugin_registry.py`:
```python
class PluginRegistry:
    def discover(self, search_paths: list[Path]) -> None: ...
    def get(self, kind: PluginKind, name: str) -> Plugin: ...
    def for_kind(self, kind: PluginKind) -> list[Plugin]: ...   # ordenado topologicamente por before/after/priority
    def instantiate(self, spec: PluginSpec) -> Plugin: ...       # importlib + checagem api/schema version
```

Discovery varre `search_paths` (built-in `src/stages/**/plugins`, `workspace/plugins/`, dirs extras via
config), valida manifest, registra lazy. Loading checa `api_version`/`schema`, plugin quebrado é
**pulado com log**, nunca derruba o run inteiro (corrige a fragilidade atual de KeyError em cascata).

---

## Schema de dados (substitui o dict-god-object)

Pydantic v2 em `src/core/schema/`. Cada saída de estágio é um modelo; pipeline passa `AnalysisContext`
tipado, não dict cru.

```python
# geometry.py
class Point2D(BaseModel): x: float; y: float
class Point3D(BaseModel): x: float; y: float; z: float
class BBox(BaseModel): x: float; y: float; w: float; h: float

# detection.py
class Detection(BaseModel):
    centroid: Point2D
    bbox: BBox | None = None
    confidence: float = 1.0
    area: float | None = None
class FrameDetections(BaseModel):
    frame_index: int
    view: Literal["top", "side"]
    detections: list[Detection]      # 0..N — sem mais sentinela (-1,-1)

# track.py
class Track(BaseModel):
    entity_id: int                   # persistente entre frames — habilita multi-animal
    view: Literal["top", "side"]
    points: dict[int, Point2D]       # frame_index -> posição (buracos = oclusão)

# route.py
class Route3D(BaseModel):
    entity_id: int
    points: dict[int, Point3D]

# result.py
SCHEMA_VERSION = "1.0"
JsonSafeValue = Union[str, int, float, bool, None, list["JsonSafeValue"], dict[str, "JsonSafeValue"]]
class Metric(BaseModel):
    name: str; value: JsonSafeValue; unit: str | None = None; producer: str
class AnalysisResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    profile: str
    calibration: Calibration
    routes: list[Route3D]
    metrics: dict[str, Metric] = {}
    border_region: BorderRegion | None = None
class AnalysisContext(BaseModel):
    result: AnalysisResult
    def add_metric(self, m: Metric) -> None: ...
    def get_metric(self, name: str) -> Metric | None: ...   # defensivo, sem KeyError
```

`Metric.value` usa um union `JsonSafeValue` fechado, não `Any` — mantém a garantia de round-trip JSON sem
perder tipagem estática (achado do plano detalhado da Fase 1).

`BorderRegion` (referenciado acima mas nunca definido no desenho original — gap encontrado e fechado pelo
plano detalhado da Fase 1, derivado do comportamento real de `MetadataModule/borderModule.py`):
```python
# result.py (cont.)
class BorderRegion(BaseModel):
    threshold_px: int = 100          # distância da borda pro centro que separa "pousado" de "voando"
    bounds: dict[Literal["x", "y", "z"], tuple[float, float]]   # min/max por eixo 3D, derivado via axis_mapping()
```
Substitui o comportamento atual de `borderModule.py`, que mistura eixo v da câmera do topo com eixo u da
lateral pra montar os limites — com `axis_mapping()` já resolvido, `bounds` é montado por eixo 3D real, não
por combinação ad hoc de coordenadas de câmeras diferentes.

Versionamento: `schema_version` gravado em todo `AnalysisResult` persistido; plugins declaram range
`schema` no manifest; registry recusa rodar plugin fora do range. Substitui a fragilidade de "plugin
assumiu que a chave X existe" (`pdfFactory`/`borderModule` hoje).

---

## Abstração Detector/Tracker

`src/core/stages.py`:
```python
class Detector(Plugin):
    @abstractmethod
    def detect(self, frame: RectifiedFrame) -> FrameDetections: ...

class Tracker(Plugin):
    @abstractmethod
    def update(self, dets: FrameDetections) -> None: ...
    @abstractmethod
    def tracks(self) -> list[Track]: ...
    def reset(self) -> None: ...

class MetadataPlugin(Plugin):
    @abstractmethod
    def run(self, ctx: "AnalysisContext") -> None: ...   # substitui module_call(data)->data; muta ctx.result in-place
```

`MetadataPlugin` (achado do plano detalhado da Fase 2: `stages.py` precisa dessa classe além de
`Detector`/`Tracker` pra existir a prova de conceito de porte de `speed`/`border`) é o que os plugins `MM`
implementam — substitui diretamente o contrato antigo `module_call(data: dict) -> dict` por
`run(ctx: AnalysisContext) -> None`, mutando `ctx.result` via `add_metric()`.

- `remove_background()` atual vira `BackgroundSubtractionDetector` (plugin `detector`), retornando 0 ou 1
  detecção em vez de `(-1,-1)`.
- `SingleEntityTracker` trivial (atribui `entity_id=0` a toda detecção) porta o comportamento atual.
- Como a interface já fala em N `Detection`s e `entity_id` persistente, um futuro tracker Kalman+Hungarian
  multi-animal é plugin **drop-in** — sem mudar schema/interface. **Não desenhamos esse algoritmo agora**
  (Fase 6, pesquisa aberta).
- Oclusão é representável nativamente: buraco em `Track.points` = entidade ocluída; re-identificação entre
  views é trabalho do tracker futuro, que tem as duas `FrameDetections` disponíveis.

---

## Estratégia GPU

GPU é requisito agora, entra **atrás das interfaces existentes** — sem duplicar lógica de pipeline:

- Entra em Rectify (warp de perspectiva) e Detect (subtração de fundo) — os 2 estágios pesados.
- Caminho mínimo viável: módulo CUDA do OpenCV — `cv2.cuda.warpPerspective`,
  `cv2.cuda.createBackgroundSubtractorMOG2`, `cv2.cuda_GpuMat`. Reaproveita dependência já existente
  (OpenCV), sem framework novo pesado.
- `src/core/gpu.py`: probe de capacidade (`cv2.cuda.getCudaEnabledDeviceCount()`) valida requisito no
  startup, falha alto se ausente (GPU é requisito, não fallback). **Decisão de produto fechada** (achado
  do plano detalhado da Fase 5): o probe/`require_cuda()` gate apenas `Pipeline.run` (execução real de
  processamento) — nunca o boot da GUI ou as telas de configuração (perspectiva/orientação/borda). Um
  pesquisador sem GPU consegue abrir a GUI e configurar um perfil normalmente; o erro só aparece ao tentar
  processar de fato.
- **Risco de infraestrutura real, não só de código** (achado do plano detalhado da Fase 5): o pacote PyPI
  `opencv-python` (e mesmo `opencv-contrib-python`) **não vem com CUDA habilitado** — os módulos
  `cudawarping`/`cudabgsegm` exigem um build próprio do OpenCV+opencv_contrib com `-DWITH_CUDA=ON`. Build
  nativo no Windows é historicamente frágil; caminho recomendado é Docker com imagem base CUDA rodando via
  WSL2 (Windows 11 suporta passthrough de GPU nativo), escopado só ao caminho headless/CLI — a GUI Tkinter
  continua rodando nativa/CPU-only pra configuração. Wheel de terceiro é fallback tático, não plano
  principal. Tratar isso como um item de várias sessões no roadmap, não um detalhe de código.
- `ArrayBackend` (numpy vs GpuMat) mantém frame residente na GPU entre Rectify→Detect sem round-trip pra
  RAM. Migração futura pra CuPy/PyTorch é só outro `ArrayBackend` — interface não muda.
- Streaming é pré-requisito (Fase 3): hoje vídeo inteiro é bufferizado em lista Python — trava GPU
  pipelining. Capture→Rectify→Detect vira generator-based (`Iterator[FramePair]`).
- GUI e CLI se beneficiam igual, pois ambos chamam a mesma orquestração — GPU é campo de
  config/`RunRequest`, não código separado.

---

## Entrada headless/CLI

- `src/app/cli.py` (Typer): `animaltrack run --workspace ./ws --profile fish01 [--config pipeline.toml]
  [--gpu]`, `animaltrack list-plugins`, `animaltrack validate-config`.
- GUI e CLI constroem `RunRequest` e chamam `Pipeline.run(request)` — caminho idêntico. Tkinter nunca
  entra na pipeline.
- `src/core/workspace.py` substitui todo caminho relativo a CWD:
```python
class Workspace:
    root: Path
    @property
    def config_path(self) -> Path: return self.root / "config"
    @property
    def outputs(self) -> Path: return self.root / "outputs"
    @property
    def plugins(self) -> Path: return self.root / "plugins"
```
  Resolução: `--workspace` → env `ANIMALTRACK_WORKSPACE` → default `~/.animaltrack`. Tudo via `pathlib`
  (multiplataforma).
- `pipeline.toml` por perfil nomeia plugins escolhidos (capture/rectify/detector/tracker/fusion) e listas
  ordenadas de metadata/exporter. GUI edita esse mesmo arquivo — hub não guarda mais StringVar no root Tk.

---

## Persistência

`src/core/store.py` — atômico, com schema, 2 stores separadas:
- `ProfileStore` — perfis/config de pipeline (era `cache/configs.json`).
- `ResultStore` — `AnalysisResult` por run (era `cache/outputs/<perfil>.json`), com `schema_version`.
- Escrita atômica (tmp file + `os.replace`), (de)serialização pydantic. Sem SQLite por ora (só se surgir
  necessidade real de query relacional).

---

## Migração / descontinuação (strangler-fig, sem amarra de compat)

| Arquivo atual | Destino | Fase |
|---|---|---|
| `src/Modules/MetadataModule/modulesInvoker.py` | **Substitui** → `plugin_registry.py` | 2 |
| `MetadataModule/speedModule.py`, `borderModule.py` | **Refatora** → plugins `metadata` com manifest, contexto tipado | 3 |
| `backgroundRemoveModule.py` | **Refatora** → `BackgroundSubtractionDetector` | 3 |
| `perspectiveModule.py` | **Refatora** → `CpuPerspectiveRectifier` + capture streaming | 3 |
| `routeAnalizer.py` + `getData.py` | **Refatora** → `Fusion` + `Calibration` (usa `axis_mapping()`, corrige bug de eixo) | 3 |
| `processVideoModule.py` | **Apaga** (papel vira o orquestrador) | 3 |
| `jsonUtils.py` | **Substitui** → `store.py` | 1 |
| `ExportModule/{plotRoute,pdfFactory}.py` | **Refatora** → plugins `exporter` (acesso defensivo a métricas) | 4 |
| `ExportModule/{recordVideo,videoUtils,folderUtils}.py` | **Refatora** → Capture stage / utils de workspace | 3–4 |
| `InterfaceModule/*` (mainUI, configurationUI, perspectiveUi, borderUi) | **Envolve depois refatora**: UX igual, ações repontadas pra camada de serviço/orquestração; lifecycle de tela normalizado | 4 |
| `InterfaceModule/*` + nova `OrientationUi` | **Nova tela** de orientação de câmera/caixa | 4 |
| `recodWebCamVideo/*` | **Refatora** em Capture + lifecycle normalizado | 4 |
| `__init__.py` | **Substitui** → launcher fino que despacha pra `app.gui` ou `app.cli` | 4 |

Telas antigas mantidas visualmente próximas da referência durante a transição, pra não reabrir decisões de
UI não relacionadas.

---

## Bugs conhecidos — disposição

1. **`process_video` retorna 3-tupla no caminho de falha de abertura, 4-tupla no sucesso** (crash de
   unpack em falha real) — *Obsoleto na Fase 3* quando `processVideoModule` é apagado e vira Capture
   streaming (levanta `CaptureError` explícito). Teste de regressão na Fase 3.
2. **`speedModule.py` divide distância por `pixel_to_cm_ratio` duas vezes** — *Correção explícita na Fase
   3*: fórmula corrigida pra `velocidade = distância_cm / (1/fps)`, sem divisão dupla. Decisão tomada por
   julgamento técnico (bug óbvio de unidade); revisar durante a Fase 3 se o resultado não bater com dado
   experimental conhecido.
3. **`getData.py` deriva as 3 razões px/cm todas de `height_side`** — *Corrigido na raiz pela feature de
   Orientação* (Fase 3): `px_per_cm` vira por eixo via `axis_mapping()`, não mais 3 razões da mesma medida.
4. **`get_image_from_frame_queue(self, queue, image_size)` com `self` sobrando, engolido por `except:`
   nu** — *Correção explícita na Fase 4* durante refatoração de Capture/GUI; remove o `except` nu pra
   falhas aparecerem. Detalhe adicional achado pelo plano detalhado da Fase 4: a chamada com aridade errada
   é na verdade engolida por um `except:` nu **externo**, em `show_recoding_video` (não um `except` próprio
   da função) — a correção precisa remover/estreitar os dois pontos, não só um.
5. **`record_video()` checagem de falha de leitura inalcançável até começar a gravar → loop infinito
   potencial** — *Obsoleto + corrigido na Fase 4* pelo novo loop de Capture (checagem de falha explícita e
   alcançável). Teste simulando câmera falhando.
6. **`averageSpeed` divide por `frame_count` em vez de `frame_count − 1`** (bug adicional, fora da lista
   original de 5, achado pelo plano detalhado da Fase 3) — número de amostras de velocidade é sempre
   `frame_count - 1` (distância entre pontos consecutivos), não `frame_count`. *Correção explícita na Fase
   3*, junto com o bug #2, já que o plugin de velocidade está sendo reescrito de qualquer forma.

---

## Execução: subagentes paralelos e handoff

Cada fase deve ser executada disparando subagentes por workstream independente dentro da fase, não como
um fluxo sequencial único. Regra: workstreams que tocam arquivos diferentes e não dependem de contrato um
do outro rodam em paralelo (isolamento por git worktree, evita conflito de arquivo); workstreams que
dependem de um tipo/contrato definido em outro lugar (ex: Detect precisa do tipo `RectifiedFrame` que
Rectify produz) esperam a **interface** estar fixada (não a implementação completa) antes de paralelizar.

### Protocolo de handoff (obrigatório pra todo subagente)

Motivo: uma sessão de trabalho pode acabar o orçamento de contexto/token no meio de uma fase grande (ex:
Fase 3, que mexe em 5+ arquivos). Sem handoff, a próxima sessão perde raciocínio e decisões intermediárias
e precisa re-explorar do zero.

Regra: todo subagente, antes de encerrar — seja por ter terminado o workstream, seja por perceber que está
perto do limite de contexto/token — escreve um arquivo em `docs/handoffs/<fase>-<workstream>-handoff.md`:

```markdown
# Handoff: Fase <N> — <workstream>
Status: done | in-progress | blocked
Última atualização: <data>

## O que foi feito
- arquivos criados/alterados (path:linha quando relevante)
- decisões tomadas e por quê

## O que falta
- TODOs concretos, na ordem em que devem ser feitos

## Como verificar o que já foi feito
- comando exato (pytest -k ..., ruff check ...) e resultado esperado

## Como retomar
- próximo passo exato pra quem pegar esse handoff continuar
- qualquer decisão pendente que só o dono do projeto pode confirmar
```

Mantém-se também `docs/handoffs/PROGRESS.md` — arquivo mestre, atualizado após cada fase/workstream
concluído: status de cada fase, link pros handoffs individuais, próxima ação. É o primeiro arquivo a ler
ao retomar trabalho depois de perda de contexto/token, antes de reabrir qualquer código.

### Paralelização por fase

| Fase | Workstreams paralelizáveis | Antes de paralelizar |
|---|---|---|
| 0 | `pyproject.toml`+layout de pacote (workstream A, T1-T8) / CI workflow (workstream B, T9) | nada — 2 workstreams direto em paralelo (ARCHITECTURE.md já entregue, não é mais deliverable desta fase) |
| 1 | `geometry+detection+track+route` / `orientation.py` / **`workspace.py`** (achado do plano detalhado: sem dependência de tipo do schema, só `pathlib` — pode começar em paralelo com os outros 2 desde t0, não precisa esperar) | nada entre os 3; só `profile.py`+`result.py` (Wave 2) esperam a Wave 1 completa, e `store.py` (Wave 3) espera a Wave 2 |
| 2 | plugin `speed` / plugin `border` (adapters finos) / **`gpu.py`** (achado do plano detalhado: sem dependência de `plugin_registry`/`pipeline`, pode rodar em paralelo desde t0) | `plugin.py`+`plugin_registry.py`+`pipeline.py` continuam sequenciais (1 agente); os 2 plugins de metadata esperam esse core, `gpu.py` não espera nada |
| 3 | Capture / Rectify / Detect / Track / Fuse | espera protocolos de `stages.py` (Fase 2) fixados; paralelo em worktrees separados, **mas com uma exceção real não só de tipo** (achado do plano detalhado): o modelo de fundo em duas passadas do Detect precisa instanciar Capture+Rectify reais na sua própria pré-passada (`setup()`), o que quebra paralelismo limpo com esses dois estágios — mitigação: Detect usa fakes de Capture/Rectify pros próprios testes unitários, só liga às implementações reais na integração sequencial final; integração + golden-file test sequencial no final |
| 4 | CLI / GUI (refatoração de telas) / plugins Export / `OrientationUi` | **Fase 4.0 sequencial primeiro** (achado do plano detalhado): GUI-refactor e `OrientationUi` mexem no mesmo contrato (`Screen` protocol + `ProfileConfig`) — esse contrato precisa ficar congelado por 1 agente antes de abrir os 4 workstreams paralelos, senão os dois reinventam a interface de formas incompatíveis; depois da Fase 4.0, os 4 workstreams (CLI/GUI/Export/OrientationUi) rodam em paralelo normalmente |
| 5 | `CudaPerspectiveRectifier` / `CudaMOG2Detector` | espera `ArrayBackend`+`gpu.py` (prerequisito sequencial compartilhado pelos dois, achado do plano detalhado) + interfaces `Rectifier`/`Detector` (Fase 3); só depois disso os 2 plugins CUDA são paralelo total |
| 6 | spike de tracker multi-animal / plugin de exemplo (peixe) / docs de marketplace | nada entre si — paralelo total |

Isolamento: worktree separado pra todo workstream que escreve código (evita conflito de arquivo entre
agentes paralelos); workstreams só de leitura/pesquisa (spikes, docs) não precisam de worktree. Depois que
os agentes paralelos de uma fase terminam, integração é sequencial: merge dos worktrees, roda verificação
da fase inteira, só então grava o handoff consolidado em `PROGRESS.md`.

---

## Fases

Cada fase é útil e roda sozinha. Suite de teste entra já na **Fase 0** com **pytest**; cada fase seguinte
adiciona teste do que constrói. CI via GitHub Actions.

### Fase 0 — Ferramental e fundação de pacote (sem mudança de comportamento)
- `pyproject.toml` (PEP 621): Python **≥3.11**, deps (numpy, opencv-python, pydantic v2, typer, matplotlib,
  xhtml2pdf, pandas, **pillow** — achado do plano detalhado: usada em 4 arquivos hoje, faltava na lista),
  dev deps (pytest, ruff, mypy). Aposenta `requirements.txt`.
- Layout `src/` instalável, `ruff`+`mypy` configurados, `tests/` com smoke test, CI
  (`.github/workflows/ci.yml`).
- **Risco crítico (R1, achado do plano detalhado)**: todo código atual importa com o prefixo literal
  `from src.Modules...` — `src` precisa continuar sendo o nome do pacote top-level de verdade. Um layout
  `src/`-padrão com `package-dir` remapeando `src` pra fora do nome do pacote quebraria silenciosamente
  todo import existente. Usar `[tool.setuptools.packages.find]` com `include=["src","src.*"]`, sem
  `package-dir` remap, e validar com `python __init__.py` manual além de `pytest`.
- **Arquivos**: `pyproject.toml`, `tests/test_smoke.py`, config ruff/mypy, `.github/workflows/ci.yml`.
- **Verificação**: `pip install -e .` ok; `pytest` verde; `ruff check` limpo; `python __init__.py` abre a
  GUI normalmente (prova de que o import prefix não quebrou); nenhum comportamento de runtime tocado.

### Fase 1 — Primitivas core: schema + workspace + store
- `src/core/schema/*` (incluindo `orientation.py`), `src/core/workspace.py`, `src/core/store.py`
  (escrita atômica, `ProfileStore`/`ResultStore`).
- **Arquivos**: `src/core/schema/{geometry,detection,track,route,result,orientation}.py`,
  `src/core/workspace.py`, `src/core/store.py`.
- **Verificação**: testes round-trip JSON de cada modelo; teste de escrita atômica simulando crash (tmp
  sobra, alvo intacto); `schema_version` conferido.

### Fase 2 — Sistema de plugin + esqueleto de orquestração
- `src/core/plugin.py`, `src/core/plugin_registry.py`, `src/core/pipeline.py`, `src/core/gpu.py`
  (stub de probe).
- Prova de conceito: envolve a lógica de metadata *atual* como os 2 primeiros plugins reais (adapters
  finos, sem reescrever ainda), descobertos via `plugin.toml`.
- **Arquivos**: `src/core/plugin.py`, `src/core/plugin_registry.py`, `src/core/pipeline.py`,
  `src/core/stages.py`, `src/core/errors.py` (achado do plano detalhado: tipos de exceção próprios —
  `PluginLoadError`, `PluginVersionMismatch`, `PluginCycleError` etc. — não estavam na lista original),
  `plugins/speed/{plugin.toml,plugin.py}`, `plugins/border/{plugin.toml,plugin.py}`.
- **Verificação**: testes de discovery (manifest válido/inválido), rejeição de versão api/schema,
  ordenação topológica (`border after speed`), isolamento de erro (plugin que lança exceção é pulado, run
  continua).

### Fase 3 — Porta a pipeline de cálculo pra estágios streaming (a grande refatoração)
- Capture (`Iterator[FramePair]`, streaming), Rectify (`CpuPerspectiveRectifier` +
  `BoxOrientationConfig`), Detect (`BackgroundSubtractionDetector`, saída N-detecções), Track
  (`SingleEntityTracker`), Fuse (`Fusion` + `Calibration` via `axis_mapping()`).
- **Modelo/lógica de Orientação** entra em vigor aqui como pré-requisito de dado (a UI em si é Fase 4).
- Corrige bugs #2 e #3; #1 obsoleto. Apaga `processVideoModule.py`.
- **Arquivos**: `src/stages/capture/*`, `src/stages/rectify/*`, `src/stages/detect/*`,
  `src/stages/track/*`, `src/stages/fuse/*` (+ `plugin.toml` de cada).
- **Verificação**: teste golden-file (roda pipeline CPU completa em vídeo fixture curto, compara
  `AnalysisResult` com referência commitada, tolerância definida); teste de memória limitada (streaming);
  testes de regressão pras fórmulas corrigidas de velocidade/razão.

### Fase 4 — Interface dupla: CLI + GUI na mesma orquestração
- `src/app/cli.py` (typer), `src/app/gui/*` (refatora telas Tk existentes pra chamar `Pipeline.run`),
  camada de serviço fina substituindo StringVar no root Tk. Lifecycle de tela normalizado (protocolo
  `Screen` único, trabalho em background marshalled de volta pro main thread do Tk via `after()` — corrige
  bug de thread-safety latente). Nova tela `OrientationUi`. Plugins de Export refatorados (`plotRoute`,
  `pdfFactory` com acesso defensivo a métrica). Corrige bugs #4 e #5. Novo `__init__.py`/launcher.
- **Arquivos**: `src/app/cli.py`, `src/app/gui/{main_window,screens/*}.py`, `src/app/service.py`,
  `src/stages/export/{plot,pdf}/*`, entry point novo no `pyproject.toml`.
- **Verificação**: teste ponta-a-ponta CLI (`animaltrack run` em fixture → JSON+PDF gerados headless, sem
  importar Tk); smoke test de GUI (run dispara o mesmo `Pipeline.run`); teste de métrica ausente não
  quebra mais o exporter de PDF.

### Fase 5 — Backends GPU (plugins puros, sem mudar esqueleto)
- `CudaPerspectiveRectifier`, `CudaMOG2Detector`, `ArrayBackend` (numpy/GpuMat), probe de GPU obrigatório
  (`require_cuda()`) chamado só no `Pipeline.run`/caminho de análise (nunca no boot da GUI).
- **Arquivos**: `src/stages/rectify/cuda/*`, `src/stages/detect/cuda/*`, `src/core/gpu.py`,
  `src/core/array_backend.py`.
- **Verificação**: teste de paridade (CUDA vs CPU produzem detecções equivalentes na fixture, dentro de
  tolerância); startup falha limpo sem device CUDA.
- **Status (2026-07): código completo e verde sem CUDA** (`pytest -m "not gpu"`, `ruff`, `mypy
  --python-version 3.13`). Testes de paridade que exigem hardware são `@pytest.mark.gpu`, pulados
  automaticamente sem device. **Pendente: empacotamento OpenCV+CUDA** — a wheel PyPI não traz o módulo
  `cuda` (confirmado local: `cv2 5.0.0` sem `cuda.warpPerspective`/`createBackgroundSubtractorMOG2`), então
  o caminho CUDA ainda não foi executado de verdade. Ver `docs/handoffs/fase5-backends-gpu-handoff.md`.
  Nota de ambiente: máquina de dev usa Python 3.13 com cv2 5.0.0/numpy 2.5.1 (substitutos dos pins
  4.9.0.80/1.26.3 sem wheel 3.13); CI fixa 3.11.

### Fase 6 — Pesquisa e prontidão de marketplace (interface já estável)
- **Spike de tracker multi-animal**: segundo plugin `tracker` (ex: Kalman + Hungarian) atrás da interface
  `Tracker` já fixada; avaliar em fixtures multi-entidade. Algoritmo continua em aberto — o ponto é provar
  que a interface admite.
- **Exemplo de generalização de espécie**: plugin `metadata` de % de gordura de peixe (referência de
  módulo de terceiro).
- **Prontidão de marketplace**: novo `docs/PLUGIN_CONTRACT.md` documenta `plugin.toml` como contrato
  público, `animaltrack plugin install <path/git-url>` (estilo git-tap curado, clona/copia pra
  `workspace/plugins/<nome>/`, valida manifest antes de aceitar). Sem backend definido ainda.
- **Verificação**: fixture multi-entidade gera ≥2 `entity_id`s estáveis; plugin externo instalado é
  descoberto e roda; contrato documentado.

---

## Ordem — por quê

0→1→2 constroem a espinha (ferramental, tipos, motor de plugin) sem mudança de comportamento arriscada.
3 é a única refatoração grande inevitável (streaming + split de estágio + orientação), garantida pelo
teste golden-file. 4 torna usável pelos 2 pontos de entrada. 5 e 6 são plugins aditivos que as fases
anteriores deliberadamente tornaram possíveis sem mais cirurgia de arquitetura.

## Decisões já fechadas
- GPU é requisito (não fallback opcional).
- Orientação de câmera/caixa vira feature de primeira classe (Fase 3+4), 2 câmeras fixas (topo+lateral)
  por ora — não N câmeras arbitrárias.
- Stack completo aceito: pydantic v2, typer, ruff, mypy, pytest, CI.
- Sem amarra de compatibilidade com `configs.json`/outputs antigos.

## Verificação geral
Rodar `pytest` a cada fase concluída; `ruff check` + `mypy` limpos antes de cada commit; teste golden-file
da Fase 3 é o guard-rail principal de "comportamento preservado" na grande refatoração. A partir da Fase
4, rodar `animaltrack run` numa fixture real e comparar visualmente o gráfico 3D/PDF gerado com o output
do sistema antigo antes de apagar o código legado correspondente.
