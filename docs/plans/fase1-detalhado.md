# Fase 1 — Primitivas core: schema + workspace + store

> Plano de execução detalhado e granular para a Fase 1 da rearquitetura descrita em `ARCHITECTURE.md`
> (seções "Orientação de câmera/caixa", "Schema de dados", "Persistência" e a entrada "Fase 1" em
> "Fases"). Este documento é o que um agente implementador deve seguir para executar a fase sem
> precisar reabrir `ARCHITECTURE.md` frase a frase. Onde `ARCHITECTURE.md` deixou algo com `...` ou
> subespecificado, este documento fecha a decisão explicitamente e sinaliza quando é uma escolha de
> projeto que o dono do repositório deveria revisar.

## Contexto e grounding no código atual

Esta fase substitui o "dict-god-object" hoje espalhado por `data["..."]` (visto em
`routeAnalizer.py`, `getData.py`, `borderModule.py`, `speedModule.py`, `jsonUtils.py`) por modelos
Pydantic v2 tipados, mais uma camada de workspace/persistência atômica. Fase 1 é **só schema +
infraestrutura de arquivo** — nenhuma lógica de estágio (Capture/Rectify/Detect/Track/Fuse) é
escrita aqui; isso é Fase 3. O objetivo é ter tipos que compilam, se serializam/desserializam
corretamente e têm testes de round-trip, prontos para os estágios das fases seguintes consumirem.

Investigação do código atual que fundamenta as decisões de schema abaixo:

- **`MetadataModule/borderModule.py`** (o alvo direto de substituição do futuro `BorderRegion`): lê
  `data["frame_border_points_top"]` e `data["frame_border_points_side"]`, cada um uma lista de 4
  pontos `[x, y]` em pixels vindos de `BorderUi` (um retângulo arrastável). O módulo **só usa os
  índices `[0]` e `[1]`** de cada lista (os dois cantos "de cima" do retângulo) — nunca os índices
  `[2]`/`[3]`. Isso não é um bug de fato para o eixo x (o `BorderUi` mantém o retângulo sempre
  eixo-alinhado: mover um canto arrasta o par, então os cantos 0/1 já determinam o range x completo),
  mas para o que o módulo chama de "y" ele mistura `frame_border_points_top[i][1]` (eixo **v** da
  imagem da câmera do topo) com `frame_border_points_side[i][0]` (eixo **u** da imagem da câmera
  lateral) como se fossem a mesma grandeza — essa é exatamente a família do bug de eixo hardcoded que
  a feature de Orientação resolve. **Decisão de schema**: `BorderRegion` (definido abaixo) não
  reproduz essa mistura; expõe `bounds: dict[eixo, (min,max)]` por eixo 3D explícito, derivado via
  `axis_mapping()` (Fase 3), cada um com uma única fonte de dado, sem combinar eixos de câmeras
  diferentes. Mantém também `threshold_px` (default 100, configurável pelo pesquisador — documentado
  como parâmetro de primeira classe em `02-entrada-de-dados.md` item 5), que o `borderModule.py`
  legado não tem como conceito explícito mas que já é usado como valor fixo hoje; preservá-lo no
  schema dá rastreabilidade no relatório final ("qual threshold gerou esses bounds") e mantém a forma
  alinhada 1:1 com `ARCHITECTURE.md` (fonte de verdade), evitando a divergência entre planos que uma
  revisão cruzada com o plano da Fase 2 identificou.
- **`src/Modules/BasicModule/routeAnalizer.py`** (`route_module`): monta `route[index] = {"x":
  position_top[0], "y": position_top[1], "z": position_side[1]}` — ou seja, usa 3 dos 4 números
  disponíveis por frame (`top.u, top.v, side.v`) e **descarta `side.u` sempre**. Isso vira o caso de
  referência de comportamento para a política de prioridade do `axis_mapping()` desenhada abaixo (a
  câmera do topo "ganha" quando um eixo é observável pelas duas câmeras).
- **`src/Modules/BasicModule/utils/getData.py`** (`pixel_to_cm`): deriva as 3 razões px/cm
  (altura/largura/profundidade) todas de `height_side` — um valor de pixel só sendo usado para os 3
  eixos. Não é problema do Fase 1 em si (schema só *representa* `Calibration.px_per_cm: Point3D` como
  um valor por eixo, não calcula nada), mas o novo schema já **impede a regressão**: exigir
  `px_per_cm: Point3D` força uma implementação futura (Fase 3) a produzir 3 valores de verdade
  independentes, não uma razão repetida 3x.
- **`src/Modules/InterfaceModule/borderUi.py`** / **`perspectiveUi.py`**: confirmam a convenção de
  ordem de clique/canto usada em `ARCHITECTURE.md` ("superior-direito, superior-esquerdo,
  inferior-direito, inferior-esquerdo") — em `borderUi.py` os 4 pontos são
  `[top-left, top-right, bottom-left, bottom-right]` por posição de índice no array de default
  (`[[50,50],[450,50],[50,450],[450,450]]`), com as linhas desenhadas `0-1` (aresta de cima), `1-3`
  (aresta direita), `3-2` (aresta de baixo), `2-0` (aresta esquerda) — geometria de retângulo
  eixo-alinhado consistente com a convenção usada no algoritmo de `axis_mapping()` (seção 1.5).
- **`src/Modules/InterfaceModule/configurationUI.py`** (`save_config`/`load_selected_config`):
  confirma os campos exatos hoje persistidos em `cache/configs.json` por perfil:
  `top_video_path, side_video_path, frame_perspective_points_top, frame_perspective_points_side,
  width_box_cm, height_box_cm, depth_box_cm, frame_border_points_top, frame_border_points_side`. Não
  existe hoje **nenhum schema tipado** para isso — é só um dict populado direto de `tk.Entry`/lista
  Python. `ProfileStore` (Fase 1) não pode ser implementado sem um tipo para isso, então este
  documento propõe `src/core/schema/profile.py` como adição (ver nota de escopo na seção 1).
- **`src/Modules/ExportModule/jsonUtils.py`** (`import_data_from_file`/`export_data_to_file`): hoje,
  se o arquivo não existe, **cria um vazio silenciosamente**; não há tratamento de JSON corrompido;
  `export_data_to_file` escreve direto no destino (sem arquivo temporário, sem atomicidade — um
  crash no meio da escrita corrompe o arquivo de saída). `store.py` (Fase 1) faz o oposto em ambos os
  pontos, deliberadamente (seção 3).

Verificado via `ls`: `src/core/`, `docs/`, `pyproject.toml` e `tests/` **ainda não existem** neste
repo — ou seja, a Fase 0 (ferramental) ainda não rodou. Ver nota de pré-requisito na seção 0.

---

## 0. Pré-requisitos / nota de escopo

Fase 1, conforme `ARCHITECTURE.md`, assume que a Fase 0 já rodou: `pyproject.toml` com `pydantic`
(v2), `pytest`, layout `src/` instalável (`pip install -e .`), `ruff`/`mypy` configurados. **Nenhum
desses arquivos existe neste repositório no momento em que este plano foi escrito.**

Se a Fase 0 já tiver rodado quando este plano for executado: pular direto para a seção 1 e usar
`pip install -e .[dev]`.

Se a Fase 0 **não** tiver rodado ainda (situação atual confirmada): a Fase 1 não deve ficar travada
esperando por isso. Fallback mínimo, sem tentar fazer o trabalho da Fase 0:
1. `pip install "pydantic>=2,<3" pytest` (ambiente local, sem `pyproject.toml`).
2. Criar um `pytest.ini` mínimo na raiz do repo (ou `conftest.py` com `sys.path` ajustado) só o
   suficiente para `pytest` encontrar `src/core` e `tests/core` — **não** é escopo deste plano
   desenhar o `pyproject.toml` completo da Fase 0; é só o mínimo pra não bloquear a verificação da
   Fase 1.
3. Sinalizar explicitamente no handoff da Fase 1 que esse fallback foi usado, para a Fase 0 "real"
   substituir depois sem perder o trabalho da Fase 1.

Este plano assume Python ≥3.11 (decisão já fechada em `ARCHITECTURE.md`).

---

## 1. Lista ordenada de tarefas — arquivo exato + modelos exatos

Notação: `Wave` = ponto de sincronização obrigatório (tudo dentro da wave anterior precisa estar
pronto antes de começar); dentro de uma wave, os workstreams rotulados A/B/C são independentes entre
si e podem rodar em paralelo (worktrees separados). Ver seção 4 para a justificativa completa da
divisão em waves (é uma correção da tabela original de `ARCHITECTURE.md`).

### Wave 1 — paralelo, 3 workstreams, nenhuma dependência cruzada

#### Workstream A — `geometry.py` → `detection.py` + `track.py` + `route.py`

**T1 — `src/core/schema/geometry.py`**

```python
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
```

Value objects puros: `frozen=True` (imutáveis, hasháveis — útil para usar como chave de `set`/`dict`
em código futuro de tracking) e `extra="forbid"` (nenhum campo extra silenciosamente aceito). Sem
validadores adicionais — são só coordenadas, sem invariante de negócio no nível de tipo.

**T2 — `src/core/schema/detection.py`** (depende de T1)

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from src.core.schema.geometry import Point2D, BBox

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
```

`detections` aceita lista vazia — isso é literalmente o que substitui a sentinela `(-1, -1)` do
`backgroundRemoveModule.py` atual (nenhuma detecção no frame = lista vazia, não um valor mágico).

**T3 — `src/core/schema/track.py`** (depende de T1)

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from src.core.schema.geometry import Point2D

class Track(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: int = Field(ge=0)
    view: Literal["top", "side"]
    points: dict[int, Point2D] = Field(default_factory=dict)
```

`points` com chave `int` faltando = frame ocluído/sem detecção naquele índice (buraco representável
nativamente, sem sentinela). Nota de implementação: Pydantic v2 serializa chaves `int` de `dict` como
string em JSON e as reconverte para `int` na leitura — comportamento nativo, não precisa de
`field_serializer`/`field_validator` manual; vira caso de teste explícito (seção 5).

**T4 — `src/core/schema/route.py`** (depende de T1)

```python
from pydantic import BaseModel, ConfigDict, Field
from src.core.schema.geometry import Point3D

class Route3D(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: int = Field(ge=0)
    points: dict[int, Point3D] = Field(default_factory=dict)
```

Mesmo padrão de `Track`, em 3D — é a saída do futuro estágio `Fuse`.

#### Workstream B — `orientation.py` (depende só de T1; roda em paralelo ao workstream A)

**T5 — `src/core/schema/orientation.py`**

```python
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from src.core.schema.geometry import Point2D, Point3D


class BoxFace(str, Enum):
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    FRONT = "front"
    BACK = "back"


class BoxVertex(str, Enum):
    """Um dos 8 vértices da caixa, como combinação de 3 componentes binários.

    Convenção de eixo fixada aqui (documentada porque nenhum outro lugar do projeto fixa isso hoje):
      - X (largura)      <- componente LEFT/RIGHT
      - Y (altura)       <- componente TOP/BOTTOM
      - Z (profundidade) <- componente FRONT/BACK
    """
    TOP_FRONT_LEFT = "top_front_left"
    TOP_FRONT_RIGHT = "top_front_right"
    TOP_BACK_LEFT = "top_back_left"
    TOP_BACK_RIGHT = "top_back_right"
    BOTTOM_FRONT_LEFT = "bottom_front_left"
    BOTTOM_FRONT_RIGHT = "bottom_front_right"
    BOTTOM_BACK_LEFT = "bottom_back_left"
    BOTTOM_BACK_RIGHT = "bottom_back_right"


# tabela de decomposição de BoxVertex nos 3 componentes — usada pelo algoritmo de axis_mapping()
_VERTEX_COMPONENTS: dict[BoxVertex, dict[str, str]] = {
    BoxVertex.TOP_FRONT_LEFT:      {"y": "top",    "z": "front", "x": "left"},
    BoxVertex.TOP_FRONT_RIGHT:     {"y": "top",    "z": "front", "x": "right"},
    BoxVertex.TOP_BACK_LEFT:       {"y": "top",    "z": "back",  "x": "left"},
    BoxVertex.TOP_BACK_RIGHT:      {"y": "top",    "z": "back",  "x": "right"},
    BoxVertex.BOTTOM_FRONT_LEFT:   {"y": "bottom", "z": "front", "x": "left"},
    BoxVertex.BOTTOM_FRONT_RIGHT:  {"y": "bottom", "z": "front", "x": "right"},
    BoxVertex.BOTTOM_BACK_LEFT:    {"y": "bottom", "z": "back",  "x": "left"},
    BoxVertex.BOTTOM_BACK_RIGHT:   {"y": "bottom", "z": "back",  "x": "right"},
}

# ordem canônica "menor -> maior" por eixo, usada para derivar o sinal em axis_mapping()
_AXIS_ORDER: dict[str, tuple[str, str]] = {
    "x": ("left", "right"),
    "y": ("bottom", "top"),
    "z": ("front", "back"),
}


class CameraRole(str, Enum):
    TOP = "top"
    SIDE = "side"


class CameraOrientation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: CameraRole
    face_viewed: BoxFace
    corner_vertices: list[BoxVertex]  # ordem: sup-direito, sup-esquerdo, inf-direito, inf-esquerdo

    @model_validator(mode="after")
    def _validate_corners(self) -> "CameraOrientation":
        if len(self.corner_vertices) != 4:
            raise ValueError(
                f"corner_vertices deve ter exatamente 4 itens, recebeu {len(self.corner_vertices)}"
            )
        if len(set(self.corner_vertices)) != 4:
            raise ValueError("corner_vertices não pode ter vértices duplicados")
        return self


class ImageAxis(str, Enum):
    U = "u"  # eixo horizontal de pixel (largura da imagem)
    V = "v"  # eixo vertical de pixel (altura da imagem)


class BoxAxis(str, Enum):
    X = "x"
    Y = "y"
    Z = "z"


class AxisSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    camera: CameraRole
    image_axis: ImageAxis
    sign: Literal[1, -1] = 1


class AxisMapping(BaseModel):
    """Retorno de BoxOrientationConfig.axis_mapping(): de onde vem cada eixo 3D da caixa."""
    model_config = ConfigDict(extra="forbid")
    x: AxisSource
    y: AxisSource
    z: AxisSource

    @model_validator(mode="after")
    def _distinct_sources(self) -> "AxisMapping":
        keys = [(self.x.camera, self.x.image_axis),
                (self.y.camera, self.y.image_axis),
                (self.z.camera, self.z.image_axis)]
        if len(set(keys)) != 3:
            raise ValueError(
                "dois eixos 3D não podem ler o mesmo par (câmera, eixo de imagem) — "
                f"fontes: x={keys[0]}, y={keys[1]}, z={keys[2]}"
            )
        return self

    def resolve(self, top_point: Point2D, side_point: Point2D) -> Point3D:
        """Aplica o mapeamento a um ponto 2D de cada câmera e retorna o Point3D combinado."""
        raw = {
            (CameraRole.TOP, ImageAxis.U): top_point.x,
            (CameraRole.TOP, ImageAxis.V): top_point.y,
            (CameraRole.SIDE, ImageAxis.U): side_point.x,
            (CameraRole.SIDE, ImageAxis.V): side_point.y,
        }

        def _value(source: AxisSource) -> float:
            return raw[(source.camera, source.image_axis)] * source.sign

        return Point3D(x=_value(self.x), y=_value(self.y), z=_value(self.z))


class BoxOrientationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    top_camera: CameraOrientation
    side_camera: CameraOrientation

    @model_validator(mode="after")
    def _validate_roles(self) -> "BoxOrientationConfig":
        if self.top_camera.role is not CameraRole.TOP:
            raise ValueError("top_camera.role deve ser CameraRole.TOP")
        if self.side_camera.role is not CameraRole.SIDE:
            raise ValueError("side_camera.role deve ser CameraRole.SIDE")
        return self

    def axis_mapping(self) -> AxisMapping:
        """Deriva, por câmera, qual eixo de imagem (u/v) corresponde a qual eixo 3D (x/y/z).

        Algoritmo (ver seção 1.5 do docs/plans/fase1-detalhado.md para o raciocínio completo):
          1. Para cada câmera, o componente que difere entre corner_vertices[0] e [1] (ambos
             "de cima" na ordem de clique, variam só em u) define o BoxAxis do eixo-u daquela
             câmera; o componente que difere entre [0] e [2] (variam só em v) define o BoxAxis
             do eixo-v.
          2. O sinal é derivado da convenção canônica menor->maior por eixo: se o componente de
             corner_vertices[0] for o lado "maior" da convenção, sign=+1, senão -1.
          3. Cada um dos 3 BoxAxis deve ser observável por pelo menos uma câmera; se um eixo for
             observável pelas duas, a câmera TOP tem prioridade como fonte canônica (reproduz o
             comportamento do routeAnalizer.py atual, que sempre usa a câmera do topo quando
             disponível e só recorre à lateral para o eixo que o topo não vê).
        """
        top_axes = _derive_candidate_axes(self.top_camera)
        side_axes = _derive_candidate_axes(self.side_camera)

        candidates: dict[BoxAxis, list[AxisSource]] = {BoxAxis.X: [], BoxAxis.Y: [], BoxAxis.Z: []}
        for image_axis, (box_axis, sign) in top_axes.items():
            candidates[box_axis].append(AxisSource(camera=CameraRole.TOP, image_axis=image_axis, sign=sign))
        for image_axis, (box_axis, sign) in side_axes.items():
            candidates[box_axis].append(AxisSource(camera=CameraRole.SIDE, image_axis=image_axis, sign=sign))

        chosen: dict[BoxAxis, AxisSource] = {}
        for box_axis, sources in candidates.items():
            if not sources:
                raise ValueError(
                    f"eixo {box_axis.value} não é observável por nenhuma câmera nesta configuração "
                    "de orientação"
                )
            # prioridade: TOP antes de SIDE
            sources_sorted = sorted(sources, key=lambda s: 0 if s.camera is CameraRole.TOP else 1)
            chosen[box_axis] = sources_sorted[0]

        return AxisMapping(x=chosen[BoxAxis.X], y=chosen[BoxAxis.Y], z=chosen[BoxAxis.Z])


def _derive_candidate_axes(camera: CameraOrientation) -> dict[ImageAxis, tuple[BoxAxis, Literal[1, -1]]]:
    v0, v1, v2, _v3 = camera.corner_vertices  # sup-dir, sup-esq, inf-dir, inf-esq
    return {
        ImageAxis.U: _differing_component(v0, v1),
        ImageAxis.V: _differing_component(v0, v2),
    }


def _differing_component(v0: BoxVertex, v1: BoxVertex) -> tuple[BoxAxis, Literal[1, -1]]:
    c0, c1 = _VERTEX_COMPONENTS[v0], _VERTEX_COMPONENTS[v1]
    diffs = [axis for axis in ("x", "y", "z") if c0[axis] != c1[axis]]
    if len(diffs) != 1:
        raise ValueError(
            f"vértices {v0.value} e {v1.value} devem diferir em exatamente um eixo, "
            f"diferem em {diffs}"
        )
    axis = diffs[0]
    lesser, greater = _AXIS_ORDER[axis]
    sign: Literal[1, -1] = 1 if c0[axis] == greater else -1
    return BoxAxis(axis), sign


class Calibration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    box_cm: Point3D
    px_per_cm: Point3D
    fps: float = Field(gt=0)
    orientation: BoxOrientationConfig
```

**Exemplo de referência (fixture canônica para os testes da seção 5)**: câmera `TOP` vendo
`BoxFace.TOP` com `corner_vertices = [TOP_FRONT_RIGHT, TOP_FRONT_LEFT, TOP_BACK_RIGHT,
TOP_BACK_LEFT]`; câmera `SIDE` vendo `BoxFace.FRONT` com `corner_vertices = [TOP_FRONT_RIGHT,
TOP_FRONT_LEFT, BOTTOM_FRONT_RIGHT, BOTTOM_FRONT_LEFT]`.

Cálculo à mão:
- `top`: `v0=TOP_FRONT_RIGHT` vs `v1=TOP_FRONT_LEFT` → diferem só em `x` (`right` vs `left`) →
  eixo-u do topo = `X`, sinal: `c0["x"]="right"` = lado maior → `sign=+1`.
  `v0=TOP_FRONT_RIGHT` vs `v2=TOP_BACK_RIGHT` → diferem só em `z` (`front` vs `back`) → eixo-v do
  topo = `Z`, sinal: `c0["z"]="front"` = lado menor → `sign=-1`.
- `side`: `v0=TOP_FRONT_RIGHT` vs `v1=TOP_FRONT_LEFT` → diferem só em `x` → eixo-u do lado = `X`,
  `sign=+1` (mesmo raciocínio). `v0=TOP_FRONT_RIGHT` vs `v2=BOTTOM_FRONT_RIGHT` → diferem só em `y`
  (`top` vs `bottom`) → eixo-v do lado = `Y`, sinal: `c0["y"]="top"` = lado maior → `sign=+1`.
- Candidatos: `X` observável por `top.u` e `side.u` (empate → TOP ganha); `Y` só por `side.v`; `Z` só
  por `top.v`.
- **Resultado esperado**: `AxisMapping(x=AxisSource(TOP, U, +1), y=AxisSource(SIDE, V, +1),
  z=AxisSource(TOP, V, -1))`.

Isso reproduz o comportamento atual (`x` e uma segunda coordenada vindas do topo, `side` só
contribuindo o eixo que o topo não vê) com sinais explícitos — é o teste principal de
`test_orientation.py`.

> **Decisão de projeto sinalizada para confirmação do dono do repositório**: a prioridade "TOP ganha
> quando o eixo é observável pelas duas câmeras" é uma escolha de compatibilidade comportamental com
> o `routeAnalizer.py` atual, não uma verdade geométrica universal. Um esquema alternativo (média das
> duas leituras quando redundantes) seria mais robusto a ruído mas mudaria o comportamento numérico
> hoje existente. Registrar essa decisão no handoff da Fase 1 como pendência de confirmação.

#### Workstream C — `workspace.py` (nenhuma dependência de schema; roda em paralelo aos workstreams A e B)

**T6 — `src/core/workspace.py`**

```python
import os
from pathlib import Path
from pydantic import BaseModel, ConfigDict


class Workspace(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=False)
    root: Path

    @property
    def config_path(self) -> Path:
        return self.root / "config"

    @property
    def outputs(self) -> Path:
        return self.root / "outputs"

    @property
    def plugins(self) -> Path:
        return self.root / "plugins"

    def profiles_file(self) -> Path:
        return self.config_path / "profiles.json"

    def result_file(self, profile: str) -> Path:
        return self.outputs / f"{profile}.json"

    def ensure_dirs(self) -> None:
        for path in (self.config_path, self.outputs, self.plugins):
            path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def resolve(cls, cli_path: Path | None = None) -> "Workspace":
        """Precedência: --workspace (cli_path) -> env ANIMALTRACK_WORKSPACE -> ~/.animaltrack."""
        if cli_path is not None:
            return cls(root=cli_path)
        env_value = os.environ.get("ANIMALTRACK_WORKSPACE")
        if env_value:
            return cls(root=Path(env_value))
        return cls(root=Path.home() / ".animaltrack")
```

Pydantic v2 tem suporte nativo a `pathlib.Path` como tipo de campo — nenhum validador customizado é
necessário. `resolve()` **não** cria os diretórios sozinho (separação de responsabilidade: resolver
o caminho é uma operação pura; `ensure_dirs()` é o efeito colateral explícito, chamado pelo chamador
quando realmente for escrever algo).

### Wave 2 — sequencial, espera Wave 1 completa (A **e** B; C só é necessário para `store.py` na Wave 3)

**T7 — `src/core/schema/profile.py`** (depende de `geometry.py` e `orientation.py`)

> **Nota de escopo**: este arquivo **não está na lista literal de arquivos da Fase 1** em
> `ARCHITECTURE.md` (`geometry, detection, track, route, result, orientation`). Ele é uma adição
> deste plano, justificada porque `ProfileStore` (exigido pela própria Fase 1) não pode ser
> implementado sem *algum* tipo para o que `cache/configs.json` guarda hoje, e nenhum modelo desse
> tipo é definido em nenhum outro lugar do `ARCHITECTURE.md`. Sinalizar esta adição ao dono do
> projeto ao concluir a fase.

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator
from src.core.schema.geometry import Point2D, Point3D
from src.core.schema.orientation import BoxOrientationConfig


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    top_video_path: str = ""
    side_video_path: str = ""
    box_cm: Point3D = Point3D(x=0.0, y=0.0, z=0.0)
    perspective_points_top: list[Point2D] = Field(default_factory=list)
    perspective_points_side: list[Point2D] = Field(default_factory=list)
    border_points_top: list[Point2D] = Field(default_factory=list)
    border_points_side: list[Point2D] = Field(default_factory=list)
    # Deliberadamente None por padrão: só populado quando a tela OrientationUi (Fase 4) existir.
    orientation: BoxOrientationConfig | None = None

    @field_validator(
        "perspective_points_top", "perspective_points_side",
        "border_points_top", "border_points_side",
    )
    @classmethod
    def _four_or_empty(cls, value: list[Point2D]) -> list[Point2D]:
        if value and len(value) != 4:
            raise ValueError(f"deve ter exatamente 4 pontos ou estar vazio, recebeu {len(value)}")
        return value
```

Mapeamento 1:1 com os campos hoje soltos em `cache/configs.json` (visto em `configurationUI.py`):
`width_box_cm/height_box_cm/depth_box_cm` viram os 3 componentes de `box_cm: Point3D`;
`frame_perspective_points_top/side` e `frame_border_points_top/side` (listas de `[x,y]` cru) viram
listas de `Point2D` tipadas.

**T8 — `src/core/schema/result.py`** (depende de `route.py` (T4) e `orientation.py` — `Calibration`
(T5); pode ser feito em paralelo a T7 dentro da Wave 2, já que T7 e T8 não dependem um do outro)

```python
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator
from src.core.schema.geometry import Point3D
from src.core.schema.orientation import Calibration
from src.core.schema.route import Route3D

SCHEMA_VERSION = "1.0"

JsonSafeValue = (
    StrictStr | StrictInt | StrictFloat | StrictBool | list[Any] | dict[str, Any] | None
)


class Metric(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    # ARCHITECTURE.md usa `value: Any` — restringido aqui deliberadamente (ver seção 1, nota abaixo).
    value: JsonSafeValue
    unit: str | None = None
    producer: str


class BorderRegion(BaseModel):
    """Região de borda/vidro em coordenadas 3D da rota, por eixo — substitui o
    MetadataModule/borderModule.py legado (que só usava 2 dos 4 cantos e misturava eixo v do topo
    com eixo u do lado; ver seção "Contexto e grounding" acima). Forma alinhada a ARCHITECTURE.md:
    só dado (threshold configurável + bounds calculados), sem lógica de classificação embutida —
    a classificação "dentro/fora da borda por eixo" é responsabilidade do `BorderPlugin` (Fase 2,
    `run(ctx)`), não deste modelo de schema. Cada eixo do `bounds` tem uma única fonte de dado
    (via `axis_mapping()`, Fase 3), sem ambiguidade de espaço de pixel nem mistura de câmeras."""
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
```

**Desvio sinalizado**: `ARCHITECTURE.md` mostra `Metric.value: Any` literalmente. Este plano
restringe para o union `JsonSafeValue` acima porque `Any` permitiria um plugin de metadata colocar um
objeto Python arbitrário (ex. um array numpy) num `Metric`, o que faria `ResultStore.save` falhar de
forma obscura no meio da serialização JSON em vez de falhar cedo, no ponto onde o plugin errou. Se o
dono do projeto preferir manter `Any` literal (para não restringir plugins futuros de forma alguma),
é uma reversão de uma linha — mas a recomendação deste plano é manter o union.

**Decisão reconciliada (`BorderRegion`)**: uma revisão cruzada com o plano da Fase 2
(`docs/plans/fase2-detalhado.md`, que já consome `BorderRegion` no `BorderPlugin`) e o dono do projeto
confirmaram manter a forma literal de `ARCHITECTURE.md` — `threshold_px: int = 100` +
`bounds: dict[Literal["x","y","z"], tuple[float, float]]` — em vez da variante anterior deste plano (6
campos `float` planos + método `dwell_axes()`). Motivo: (1) separação de camada — classificação
"dentro/fora da borda" é lógica de plugin (Fase 2), não deve viver como método no modelo de dado da Fase
1; (2) `threshold_px` é parâmetro configurável de primeira classe (`02-entrada-de-dados.md` item 5), não
uma adição especulativa — descartá-lo do schema perderia rastreabilidade no relatório final. `bounds` como
`dict[eixo, tuple]` (em vez de 6 campos planos) também casa 1:1 com a chave usada por `axis_mapping()`
(Fase 3) e pelo `BorderPlugin` (Fase 2). Este plano já foi atualizado para essa forma (ver classe
`BorderRegion` acima); nenhuma reconciliação pendente resta.

### Wave 3 — sequencial, espera Wave 2 completa e Workstream C (T6)

**T9 — `src/core/store.py`**

```python
import json
import os
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from src.core.schema.profile import Profile
from src.core.schema.result import SCHEMA_VERSION, AnalysisResult
from src.core.workspace import Workspace


class StoreError(Exception):
    """Base de todo erro de persistência do core."""


class ProfileNotFoundError(StoreError):
    def __init__(self, name: str) -> None:
        super().__init__(f"perfil '{name}' não encontrado")
        self.name = name


class ResultNotFoundError(StoreError):
    def __init__(self, profile: str) -> None:
        super().__init__(f"resultado para o perfil '{profile}' não encontrado")
        self.profile = profile


class CorruptStoreError(StoreError):
    """JSON malformado ou falha de validação Pydantic ao carregar um arquivo do store."""


class SchemaVersionError(CorruptStoreError):
    """schema_version do arquivo carregado é diferente da SCHEMA_VERSION atual do core."""


class StoreWriteError(StoreError):
    """Falha ao escrever atomicamente (ex.: os.replace falhou)."""


def atomic_write_json(path: Path, content: str) -> None:
    """Escreve `content` em `path` de forma atômica.

    Sequência: cria arquivo temporário no MESMO diretório do destino (necessário para o
    os.replace final ser atômico em qualquer filesystem/SO), escreve+flush+fsync, depois
    os.replace(tmp, destino).

    Comportamento deliberado em caso de crash entre o fsync e o os.replace (ex. processo morto,
    queda de energia): o arquivo temporário FICA ÓRFÃO no diretório (não há bloco
    try/except/finally de limpeza ao redor do os.replace) — e o arquivo de destino permanece
    exatamente como estava antes (inteiro, se já existia; ausente, se não existia), porque
    os.replace() é atômico tanto em POSIX quanto no Windows. Essa é a garantia que importa
    (destino nunca fica parcialmente escrito); o arquivo .tmp-* órfão é um efeito colateral aceito,
    não um bug — uma rotina de limpeza de workspace (fora do escopo da Fase 1) pode varrer esses
    arquivos depois."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp-{uuid4().hex[:8]}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
    except OSError as exc:
        raise StoreWriteError(f"falha ao escrever arquivo temporário {tmp_path}: {exc}") from exc

    try:
        os.replace(tmp_path, path)
    except OSError as exc:
        raise StoreWriteError(f"falha ao substituir {path} atomicamente: {exc}") from exc


class ProfileStore:
    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def _load_all(self) -> dict[str, Profile]:
        path = self._workspace.profiles_file()
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CorruptStoreError(f"profiles.json corrompido: {exc}") from exc
        try:
            return {name: Profile.model_validate(data) for name, data in raw.items()}
        except ValidationError as exc:
            raise CorruptStoreError(f"profiles.json com dado inválido: {exc}") from exc

    def list(self) -> list[str]:
        return sorted(self._load_all().keys())

    def get(self, name: str) -> Profile:
        profiles = self._load_all()
        if name not in profiles:
            raise ProfileNotFoundError(name)
        return profiles[name]

    def save(self, profile: Profile) -> None:
        profiles = self._load_all()
        profiles[profile.name] = profile
        payload = {name: p.model_dump(mode="json") for name, p in profiles.items()}
        atomic_write_json(self._workspace.profiles_file(), json.dumps(payload, indent=2))

    def delete(self, name: str) -> None:
        profiles = self._load_all()
        if name not in profiles:
            raise ProfileNotFoundError(name)
        del profiles[name]
        payload = {n: p.model_dump(mode="json") for n, p in profiles.items()}
        atomic_write_json(self._workspace.profiles_file(), json.dumps(payload, indent=2))


class ResultStore:
    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def save(self, result: AnalysisResult) -> None:
        path = self._workspace.result_file(result.profile)
        atomic_write_json(path, result.model_dump_json(indent=2))

    def load(self, profile: str) -> AnalysisResult:
        path = self._workspace.result_file(profile)
        if not path.exists():
            raise ResultNotFoundError(profile)
        try:
            result = AnalysisResult.model_validate_json(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise CorruptStoreError(f"resultado de '{profile}' corrompido: {exc}") from exc
        if result.schema_version != SCHEMA_VERSION:
            raise SchemaVersionError(
                f"resultado de '{profile}' tem schema_version={result.schema_version!r}, "
                f"esperado {SCHEMA_VERSION!r}"
            )
        return result

    def exists(self, profile: str) -> bool:
        return self._workspace.result_file(profile).exists()
```

Notas de implementação:
- `ProfileStore` reescreve o `profiles.json` inteiro a cada `save`/`delete` (arquivo único, todos os
  perfis — mesmo modelo do `cache/configs.json` atual). Isso é aceitável na escala deste projeto
  (dezenas de perfis, não milhares); se crescer, é candidato a virar 1-arquivo-por-perfil numa fase
  futura, mas está fora do escopo da Fase 1 mudar isso.
- `ResultStore` é 1 arquivo por perfil (`outputs/<profile>.json`), preservando a estrutura atual de
  `cache/outputs/<profile>.json`.
- Nenhum dos dois **cria arquivo vazio automaticamente quando ausente** — comportamento oposto ao
  `jsonUtils.import_data_from_file` atual, deliberado (ver "Contexto e grounding").

---

## 2. Padrões Pydantic v2 exatos (aplicados em todos os modelos acima)

- `model_config = ConfigDict(extra="forbid")` em **todo** modelo — pega campo digitado errado ou
  campo removido/renomeado sem atualizar o schema. O dict-god-object legado nunca teve esse tipo de
  proteção (qualquer chave podia ser lida/gravada silenciosamente).
- `frozen=True` **só** nos value objects puros de `geometry.py` (`Point2D`, `Point3D`, `BBox`) —
  imutáveis e hasháveis, sem estado de pipeline. Os demais modelos ficam mutáveis por padrão (são
  estado de pipeline que plugins/estágios populam incrementalmente, ex. `AnalysisContext.add_metric`).
- Validação: `@field_validator` (API v2, nunca o `@validator` de v1) para regras de campo único
  (ex. `Profile._four_or_empty`); `@model_validator(mode="after")` para invariantes entre campos
  (`BorderRegion._bounds_ordered`, `AxisMapping._distinct_sources`, `CameraOrientation._validate_corners`,
  `BoxOrientationConfig._validate_roles`). `mode="after"` é usado (não `"before"`) porque as
  validações dependem dos campos já convertidos para os tipos finais (enums, listas tipadas).
- Chaves inteiras em dicionário (`Track.points`, `Route3D.points`, `dict[int, Point2D/Point3D]`):
  comportamento nativo do Pydantic v2 — serializa a chave como string em JSON
  (`{"0": {...}, "1": {...}}`) e recompõe para `int` na leitura via `model_validate_json`. Não requer
  `field_serializer`/`field_validator` manual; vira teste explícito de round-trip (seção 5) para
  travar essa garantia.
- Round-trip padrão usado em **todos** os testes de schema:
  ```python
  dumped = instance.model_dump_json()
  restored = Model.model_validate_json(dumped)
  assert restored == instance
  ```
  Nunca `json.dumps(model.model_dump())` manual — usa sempre a serialização nativa do Pydantic
  (`model_dump_json`/`model_validate_json`), que já lida com `Enum`, `Path`, `datetime`, etc.
  corretamente.
- Enums sempre como `str, Enum` (`class Foo(str, Enum)`) — serializam como string simples em JSON
  (não como `{"value": "..."}`), o que mantém o JSON legível/compatível com ferramentas externas
  (ex. um futuro manifest de marketplace lendo o resultado).
- Export de JSON Schema: teste leve (`test_json_schema_export.py`, seção 5) chamando
  `Model.model_json_schema()` para cada modelo público e checando que não lança exceção e que o
  dict resultante tem a chave `"properties"`. Não é over-engineering — dá a base de introspecção que
  o `plugin.toml`/`schema = ">=1.0,<2.0"` da Fase 2 vai precisar para validar contratos de plugin.

---

## 3. `Workspace` e `store.py` — métodos e comportamento de erro

### `Workspace` (`src/core/workspace.py`)
| Método/propriedade | Retorno | Comportamento |
|---|---|---|
| `root` | `Path` | Campo direto, raiz do workspace. |
| `config_path` | `Path` | `root/"config"` (property, não cria o diretório). |
| `outputs` | `Path` | `root/"outputs"` (property, não cria o diretório). |
| `plugins` | `Path` | `root/"plugins"` (property, não cria o diretório). |
| `profiles_file()` | `Path` | `config_path/"profiles.json"`. |
| `result_file(profile: str)` | `Path` | `outputs/f"{profile}.json"`. |
| `ensure_dirs()` | `None` | `mkdir(parents=True, exist_ok=True)` nos 3 diretórios; idempotente. |
| `Workspace.resolve(cli_path=None)` (classmethod) | `Workspace` | Precedência `cli_path` → env `ANIMALTRACK_WORKSPACE` → `~/.animaltrack`. Não cria diretórios. |

### `store.py` — exceções e quando cada uma é levantada
| Situação | Exceção levantada | Encadeamento (`from e`) |
|---|---|---|
| `ProfileStore.get`/`delete` com nome inexistente | `ProfileNotFoundError` | não (é um caso esperado, não um erro de baixo nível) |
| `ResultStore.load` com arquivo ausente | `ResultNotFoundError` | não |
| `profiles.json`/resultado com JSON malformado | `CorruptStoreError` | sim, a partir de `json.JSONDecodeError` |
| `profiles.json`/resultado com dado que não valida no schema Pydantic | `CorruptStoreError` | sim, a partir de `pydantic.ValidationError` |
| `AnalysisResult.schema_version` carregado ≠ `SCHEMA_VERSION` atual | `SchemaVersionError` (subclasse de `CorruptStoreError`) | não (é uma checagem explícita depois do parse, não uma exceção de terceiros) |
| Falha de I/O durante a escrita atômica (`open`/`fsync`/`os.replace`) | `StoreWriteError` | sim, a partir de `OSError` |

Nenhum desses métodos jamais deixa vazar um `KeyError`, `FileNotFoundError` ou
`json.JSONDecodeError`/`pydantic.ValidationError` cru para o chamador — tudo é traduzido para uma das
exceções tipadas acima, mantendo o contrato público de `store.py` estável independentemente da lib de
serialização por baixo. Isso corrige diretamente a fragilidade de "plugin assumiu que a chave X
existe" citada em `ARCHITECTURE.md` (linha ~227), pelo menos na camada de persistência.

**Tmp file órfão em caso de crash**: como descrito no docstring de `atomic_write_json` acima, este é
o comportamento **esperado e testado** (não uma falha de limpeza) — corresponde literalmente à
descrição de verificação da Fase 1 em `ARCHITECTURE.md`: *"teste de escrita atômica simulando crash
(tmp sobra, alvo intacto)"*.

---

## 4. Paralelização — grupo corrigido em relação a `ARCHITECTURE.md`

A tabela original (`ARCHITECTURE.md`, seção "Paralelização por fase") diz: *"Fase 1 |
`geometry+detection+track+route` / `orientation.py` | nada entre si; `result.py` e
`store.py`/`workspace.py` esperam os dois anteriores (sequencial depois)"*.

**Confirmação da parte correta**: `result.py` de fato depende dos dois grupos anteriores —
`AnalysisResult.routes: list[Route3D]` precisa de `route.py` (grupo A), e
`AnalysisResult.calibration: Calibration` precisa de `Calibration`, que só existe em `orientation.py`
(grupo B), já que `ARCHITECTURE.md` não lista nenhum outro arquivo pra `Calibration`. Então
`result.py` realmente só pode começar depois que **ambos** A e B terminarem — a tabela original está
certa nisso.

**Correção encontrada**: a tabela original trata `workspace.py` como sequencial, agrupado com
`store.py`, esperando o schema terminar. Isso não corresponde à dependência de tipos real:
`Workspace` (seção 1, T6) usa só `pathlib.Path` e `pydantic.BaseModel` — **nenhum import de
`src/core/schema/*`**. Não há motivo de tipo para `workspace.py` esperar `geometry.py`,
`orientation.py` ou qualquer outro arquivo de schema. Ele pode e deve rodar como um **terceiro
workstream totalmente paralelo desde o início da fase**, não esperar sequencialmente.

Grupo final de paralelização (substitui a tabela original para a Fase 1):

| Wave | Workstream | Arquivos | Depende de |
|---|---|---|---|
| 1 (paralelo, 3 agentes/worktrees) | A | `geometry.py` → `detection.py`, `track.py`, `route.py` | nada |
| 1 | B | `orientation.py` | `geometry.py` (mas pode ser o mesmo agente do A ou outro — só precisa que `Point2D`/`Point3D` existam; na prática, como `geometry.py` é trivial (~15 linhas), o agente de B pode escrevê-lo junto no início do seu próprio workstream sem esperar A, desde que não haja conflito de arquivo — recomendação: A escreve `geometry.py` primeiro e sinaliza pronto antes de B/C começarem a importar dele, é a única sincronização fina dentro da Wave 1) |
| 1 | C | `workspace.py` | nada |
| 2 (sequencial, espera Wave 1 inteira) | — | `profile.py`, `result.py` (podem ser 2 agentes em paralelo entre si, já que não dependem um do outro, mas ambos esperam A+B) | A + B |
| 3 (sequencial, espera Wave 2 + C) | — | `store.py` | Wave 2 (`profile.py` para `ProfileStore`, `result.py` para `ResultStore`) + C (`workspace.py`) |

Justificativa de por que `profile.py` não entra na Wave 1: ele importa `BoxOrientationConfig` de
`orientation.py` (campo opcional `orientation`), então depende do grupo B — não pode ser paralelo à
Wave 1, mesmo sendo um arquivo pequeno.

---

## 5. Plano de teste — arquivos exatos e o que cada um garante

`tests/conftest.py`:
- Fixture `tmp_workspace(tmp_path) -> Workspace`: `Workspace(root=tmp_path / "ws")` (diretórios ainda
  não existem — cada teste decide se chama `ensure_dirs()`).

`tests/core/schema/test_geometry.py`:
- Round-trip `Point2D`, `Point3D`, `BBox` (`model_dump_json` → `model_validate_json` → `==`).
- Tentar setar atributo em instância já criada levanta erro (frozen).
- Passar campo extra no construtor levanta `ValidationError` (`extra="forbid"`).

`tests/core/schema/test_detection.py`:
- `Detection` só com `centroid` usa defaults corretos (`bbox=None, confidence=1.0, area=None`).
- `FrameDetections` round-trip com `detections=[]` e com `detections` populado (2+ itens).
- `confidence` fora de `[0,1]` levanta `ValidationError`.
- `view="front"` (fora do `Literal["top","side"]`) levanta `ValidationError`.

`tests/core/schema/test_track.py`:
- Round-trip `Track` com `points` vazio, com índices contíguos e com **buraco** (ex. `{0: ..., 5:
  ...}`, faltando 1-4 — representa oclusão).
- Depois do round-trip, as chaves de `points` são `int` (não `str`) — trava o comportamento nativo do
  Pydantic v2 descrito na seção 2.

`tests/core/schema/test_route.py`:
- Mesma bateria de `test_track.py`, para `Route3D`/`Point3D`.

`tests/core/schema/test_orientation.py`:
- `len(list(BoxVertex))== 8` e os 8 nomes batem exatamente com os listados em T5.
- `CameraOrientation` com `corner_vertices` de tamanho 3 ou 5 levanta `ValueError`.
- `CameraOrientation` com vértice duplicado (ex. `[TOP_FRONT_LEFT, TOP_FRONT_LEFT, ...]`) levanta
  `ValueError`.
- `BoxOrientationConfig` com papéis trocados (ex. `top_camera` com `role=CameraRole.SIDE`, ou
  `side_camera` com `role=CameraRole.TOP`) levanta `ValueError` — trava o `_validate_roles` (T5).
- `BoxOrientationConfig.axis_mapping()` na fixture canônica (TOP vendo `BoxFace.TOP`, SIDE vendo
  `BoxFace.FRONT`, vértices exatamente como no exemplo calculado na seção 1) retorna
  `AxisMapping(x=AxisSource(TOP,U,+1), y=AxisSource(SIDE,V,+1), z=AxisSource(TOP,V,-1))` — comparar
  campo a campo com o valor calculado à mão.
- `axis_mapping()` levanta `ValueError` quando dois vértices adjacentes (`[0]`/`[1]` ou `[0]`/`[2]`)
  não diferem em exatamente 1 componente (fixture proposital com vértices que diferem em 2 ou 0
  componentes).
- `axis_mapping()` levanta `ValueError` quando um eixo (`x`, `y` ou `z`) não é observável por
  nenhuma das duas câmeras (fixture proposital onde as duas câmeras "veem" os mesmos 2 eixos).
- `AxisMapping.resolve(top_point, side_point)` na fixture canônica retorna o `Point3D` esperado para
  um par de pontos de entrada conhecido (calculado à mão).
- Round-trip completo de `Calibration` (aninhando `BoxOrientationConfig` com as duas
  `CameraOrientation`).

`tests/core/schema/test_profile.py`:
- Round-trip com todas as listas de pontos vazias (perfil recém-criado, nada configurado ainda).
- Round-trip com listas de 4 pontos em todas.
- Lista de 2 ou 3 pontos em qualquer um dos 4 campos levanta `ValidationError`.
- `orientation` default é `None`; round-trip com `orientation` populado também funciona.
- `box_cm` default é `Point3D(x=0,y=0,z=0)`.

`tests/core/schema/test_result.py`:
- `Metric` round-trip com `unit=None` (default) e com `unit` populado.
- `Metric.value` aceita `str`, `int`, `float`, `bool`, `list`, `dict`, `None`; um valor não-JSON-safe
  (ex. passar um `set()` ou uma instância de classe arbitrária) levanta `ValidationError` — trava o
  desvio sinalizado na seção 1 (union `JsonSafeValue` em vez de `Any` puro).
- `BorderRegion` round-trip com `threshold_px` default (100) e customizado; `bounds` com min>max em
  qualquer eixo (`x`/`y`/`z`) levanta `ValueError` (`_bounds_ordered`); `bounds` faltando um eixo levanta
  `ValueError` (`_bounds_complete`).
- `AnalysisResult` round-trip vazio (`routes=[]`, `metrics={}`, `border_region=None`) e populado
  (2+ rotas, 2+ métricas, `border_region` presente).
- `AnalysisResult().schema_version == SCHEMA_VERSION` por default.
- `AnalysisContext.add_metric` seguido de `get_metric(nome)` retorna a métrica; `get_metric` de nome
  inexistente retorna `None` (nunca `KeyError`).

`tests/core/test_workspace.py`:
- `config_path`/`outputs`/`plugins` retornam os subcaminhos esperados sob `root`.
- `Workspace.resolve(cli_path=X)` sempre usa `X`, independente de env/`~`.
- `Workspace.resolve()` sem `cli_path`, com `ANIMALTRACK_WORKSPACE` setado (via `monkeypatch.setenv`),
  usa o valor do env.
- `Workspace.resolve()` sem `cli_path` e sem env usa `~/.animaltrack` — testado com
  `monkeypatch.setenv("HOME"/"USERPROFILE", tmp_path)` (ou `monkeypatch.setattr(Path, "home", ...)`
  no Windows) para não tocar o `$HOME` real da máquina que roda o teste.
- `ensure_dirs()` cria os 3 diretórios (checar `Path.is_dir()` para cada um) e é idempotente (chamar
  2x não levanta erro).

`tests/core/test_store.py`:
- `ProfileStore.save` seguido de `get`/`list` retorna o mesmo `Profile` (round-trip via disco, não só
  em memória).
- `ProfileStore.get("inexistente")` e `ProfileStore.delete("inexistente")` levantam
  `ProfileNotFoundError`.
- `ProfileStore.delete` remove o perfil; `get` subsequente levanta `ProfileNotFoundError`.
- `ResultStore.save` seguido de `load` retorna o mesmo `AnalysisResult`.
- `ResultStore.load("inexistente")` levanta `ResultNotFoundError`.
- `ResultStore.load` sobre um arquivo com bytes JSON inválidos escritos manualmente no teste
  (`path.write_text("{not json")`) levanta `CorruptStoreError`, com `__cause__` sendo o
  `json.JSONDecodeError`/`ValidationError` original (checar `exc.__cause__ is not None`).
- `ResultStore.load` sobre um arquivo JSON válido mas com `"schema_version": "0.1"` (escrito
  manualmente no teste) levanta `SchemaVersionError`.
- **Teste de crash de escrita atômica** (`test_atomic_write_crash_simulation`): usa
  `monkeypatch.setattr(os, "replace", <função que levanta OSError>)`; chama `atomic_write_json`
  (ou `ResultStore.save`) sobre um destino que **já existe com conteúdo conhecido**; depois da
  chamada (que deve propagar `StoreWriteError`), verificar: (a) o conteúdo do arquivo de destino é
  **idêntico ao anterior** (não foi tocado); (b) existe **exatamente 1** arquivo `.tmp-*` órfão no
  diretório (prova que o tmp "sobra", conforme o texto do `ARCHITECTURE.md`); (c) a exceção
  propagada é `StoreWriteError` com `__cause__` sendo o `OSError` simulado.
- Teste complementar `test_atomic_write_success_leaves_no_tmp`: uma escrita bem-sucedida normal (sem
  monkeypatch) não deixa **nenhum** arquivo `.tmp-*` no diretório depois — só o arquivo final.

`tests/core/schema/test_json_schema_export.py`:
- Para cada modelo público dos 6 módulos de schema + `profile.py` (~20 classes), chama
  `Model.model_json_schema()` dentro de um loop parametrizado (`pytest.mark.parametrize`) e garante
  que não lança exceção e que o dict resultante contém a chave `"properties"` (ou, para os `Enum`,
  `"enum"`).

---

## 6. Comandos de verificação

```bash
# Fase 0 já rodou:
pip install -e .[dev]

# Fase 0 ainda não rodou (fallback descrito na seção 0):
pip install "pydantic>=2,<3" pytest

# Suíte da Fase 1
pytest tests/core -v

# Cobertura (opcional, útil para achar branch não testado no axis_mapping())
pytest tests/core --cov=src/core --cov-report=term-missing

# Smoke manual do schema mais profundo da fase
python -c "from src.core.schema.result import AnalysisResult; print(AnalysisResult.model_json_schema())"

# Lint/tipagem (best-effort se a Fase 0 já configurou; não bloqueante se ainda não configurou)
ruff check src/core tests/core
mypy src/core
```

Critério de "Fase 1 concluída": todos os arquivos da seção 1 existem, `pytest tests/core -v` passa
100% (incluindo os testes de crash simulado e de round-trip de todo modelo), e o smoke manual acima
não lança exceção.

---

## 7. Handoff-readiness — checkpoints seguros, em ordem crescente

Todo checkpoint abaixo é seguro para escrever
`docs/handoffs/fase1-<workstream>-handoff.md` e parar, caso o orçamento de contexto/token acabe no
meio da fase — o próximo agente retoma exatamente dali sem precisar re-explorar.

1. **`geometry.py` feito e testado, mais nada.** Menor checkpoint útil — tudo mais depende dele, mas
   é rápido de refazer se perdido; ainda assim vale registrar para não obrigar rehash do
   `test_geometry.py`.
2. **Qualquer subconjunto da Wave 1 completo e testado é seguro isoladamente**, porque A, B e C não
   têm dependência cruzada entre si (só de `geometry.py`, que é trivial):
   - `detection.py + track.py + route.py` feitos e testados, `orientation.py` não iniciado — seguro.
   - `orientation.py` feito e testado, `detection/track/route` não iniciados — seguro.
   - `workspace.py` feito e testado sozinho, nada mais da Wave 1 tocado — seguro.
   - **Wave 1 inteira (A+B+C) feita e testada** — o checkpoint mais sólido antes de abrir a Wave 2;
     registrar no handoff que `profile.py`/`result.py` podem começar em paralelo a partir daqui.
3. **Wave 2 completa** (`profile.py` **e** `result.py` feitos e testados) — só é um checkpoint válido
   depois que TODA a Wave 1 estiver feita (diferente da Wave 1, aqui não há subconjunto seguro: se só
   `profile.py` estiver pronto e `result.py` não, isso ainda é um checkpoint razoável para registrar,
   mas deixar claro no handoff que `store.py` (Wave 3) não pode começar até `result.py` também
   terminar).
4. **Wave 3 completa** (`store.py` feito, testado, incluindo os testes de crash de escrita atômica) +
   suíte inteira (`pytest tests/core`) verde — **Fase 1 concluída**. Este é o ponto de:
   - Atualizar `docs/handoffs/PROGRESS.md` marcando a Fase 1 como concluída, com link para os
     handoffs individuais de cada workstream.
   - Registrar explicitamente no handoff consolidado as três decisões de projeto ainda pendentes de
     confirmação do dono do repositório (a divergência de `BorderRegion`, item (d) anterior, já foi
     reconciliada — ver nota na seção 1 — e não precisa mais de confirmação):
     (a) a adição de `src/core/schema/profile.py` fora da lista literal do `ARCHITECTURE.md`;
     (b) a política "TOP-camera-ganha-empate" em `axis_mapping()` (seção 1, workstream B);
     (c) a restrição de `Metric.value` de `Any` para o union `JsonSafeValue` (seção 1, T8).
   - Liberar a Fase 2 (`plugin.py`, `plugin_registry.py`, `pipeline.py`).

Cada handoff intermediário (checkpoints 1–3) segue o template obrigatório do protocolo de
`ARCHITECTURE.md` (`docs/handoffs/fase1-<workstream>-handoff.md`): `Status`/`Última atualização`,
`O que foi feito` (arquivos com path:linha), `O que falta` (lista ordenada de TODOs concretos),
`Como verificar` (comando `pytest` exato + resultado esperado) e `Como retomar` (próximo passo exato
+ qualquer decisão pendente que só o dono do projeto pode confirmar — citando as quatro decisões
listadas no item 4 acima sempre que relevante ao workstream em questão).
