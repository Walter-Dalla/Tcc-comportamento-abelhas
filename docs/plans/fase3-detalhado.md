# Fase 3 (detalhado) — Porta a pipeline de cálculo pra estágios streaming

> Plano de execução granular pra Fase 3 de `ARCHITECTURE.md`: a maior e mais arriscada fase da
> rearquitetura — substitui `BasicModule/{processVideoModule,perspectiveModule,backgroundRemoveModule,
> routeAnalizer}.py` e `BasicModule/utils/getData.py` por 5 estágios streaming (Capture → Rectify → Detect
> → Track → Fuse), corrige os bugs #2 e #3 do inventário de `ARCHITECTURE.md`, e introduz a feature de
> Orientação de câmera/caixa como pré-requisito de dado.

## 0. Premissas e escopo

Este plano assume que as **Fases 0, 1 e 2** de `ARCHITECTURE.md` já estão concluídas e são contrato fixo:

- Fase 0: `pyproject.toml`, layout `src/` instalável, `pytest`/`ruff`/`mypy`/CI.
- Fase 1: `src/core/schema/{geometry,detection,track,route,result,orientation}.py` (incluindo
  `BoxOrientationConfig`, `Point2D`, `Point3D`, `Detection`, `FrameDetections`, `Track`, `Route3D`,
  `Calibration`, `AnalysisResult`, `AnalysisContext`), `src/core/workspace.py`, `src/core/store.py`.
- Fase 2: `src/core/plugin.py` (`Plugin` ABC com `setup(ctx)`/`teardown()`), `src/core/plugin_registry.py`,
  `src/core/pipeline.py`, `src/core/stages.py` (`Detector`/`Tracker` ABCs conforme especificado em
  `ARCHITECTURE.md`), e os plugins `metadata` `speed`/`border` já existindo como *adapters finos* (ainda
  chamando a lógica antiga, sem corrigir bugs).

Este documento **não** valida essas premissas contra código real (nenhuma delas existe no repo hoje — o
repo está pré-Fase-0). Se uma sessão futura começar a Fase 3 e essas premissas não se sustentarem, o
primeiro passo é fechar a lacuna em Fase 0–2, não improvisar aqui.

Escopo desta fase:
- **Apaga** `src/Modules/BasicModule/processVideoModule.py` (seu papel vira o orquestrador `pipeline.py`,
  já existente da Fase 2).
- **Refatora** `perspectiveModule.py` → `src/stages/rectify/*`.
- **Refatora** `backgroundRemoveModule.py` → `src/stages/detect/*`.
- **Refatora** `routeAnalizer.py` + `getData.py` → `src/stages/fuse/*` + `Calibration`.
- **Introduz** `src/stages/capture/*` (não existe hoje como conceito separado — capturado implicitamente
  dentro de `perspectiveModule.process_perspective`) e `src/stages/track/*` (não existe hoje — a atribuição
  de "1 entidade" é implícita no fato de `remove_background` só devolver 0 ou 1 posição por frame).
- **Reescreve** `MetadataModule/speedModule.py` e `MetadataModule/borderModule.py` como plugins `metadata`
  tipados que operam sobre `Route3D`/`Calibration` novos (a Fase 2 só os envolveu como adapter fino; a
  correção real de bug #2/#3 só é possível depois que `Fuse` existir com os tipos novos). Isso é o que a
  tabela de migração de `ARCHITECTURE.md` também aponta para a Fase 3, não a 2.
- Corrige bugs **#2** (fórmula de velocidade) e **#3** (razão px/cm por eixo). Bug **#1** fica obsoleto
  (substituído por `CaptureError` explícito). Bugs #4 e #5 ficam para a Fase 4 (não tocados aqui).
- **Fix adicional, fora do inventário original de 5 bugs** (aprovado explicitamente pelo dono do projeto
  durante o planejamento desta fase): `averageSpeed` hoje é calculado como
  `speedTotal / len(data["route"])`, ou seja, divide pela contagem de *frames*, não pela contagem de
  *amostras de velocidade* (que é `frame_count - 1`, já que o primeiro frame nunca gera uma velocidade —
  o loop de `speedModule.py` pula explicitamente `index == '0'`). Como o plugin `speed` já está sendo
  reescrito do zero nesta fase, a correção (dividir por `len(route) - 1`, ou de forma mais robusta, pelo
  número real de pares consecutivos válidos somados) entra junto. Ver seção 4.3.

---

## 1. Lista de tarefas por estágio

Ordem de execução recomendada dentro da fase (não é sequencial obrigatória entre workstreams — ver seção
6 — mas é a ordem em que cada workstream deve montar sua própria implementação internamente, já que cada
estágio precisa entender o formato de saída do anterior mesmo trabalhando contra tipos fixos):

### 1.1 Capture — `src/stages/capture/`

**Arquivos**: `src/stages/capture/plugin.py`, `src/stages/capture/plugin.toml`.

**Classe**: `DualVideoFileCapture(Capture)`.

**Origem da lógica portada**: `src/Modules/ExportModule/videoUtils.py::open_video` (chamado 2x, um por
câmera) + o laço de leitura hoje embutido em
`src/Modules/BasicModule/perspectiveModule.py::process_perspective` (`while True: success, frame =
originalVideo.read(); if not success: break`).

**O que muda**: separa "abrir e ler frames cru" (Capture) de "aplicar perspectiva" (Rectify) — hoje as
duas coisas vivem juntas dentro de `process_perspective`. Levanta `CaptureError` explícito em vez do
`return False, None` de `open_video` (isso é o que torna bug #1 obsoleto: hoje `process_video` em
`processVideoModule.py` devolve `(False, None, None)` — 3-tupla — no caminho de falha e uma 4-tupla no
sucesso, o que faz `top_success, top_frames, fps, position_top = future_top.result()` estourar
`ValueError: not enough values to unpack` se a abertura falhar de verdade; com uma exceção explícita isso
nunca chega a essa linha).

**Corpo esperado**:

```python
# src/stages/capture/plugin.py
import threading
from queue import Queue, Empty
import cv2

from src.core.plugin import Plugin
from src.core.schema.detection import FramePair  # tipo já fixado na Fase 1/2

class CaptureError(Exception):
    """Levantado quando um arquivo de vídeo não abre ou para de fornecer frames de forma inesperada."""

class DualVideoFileCapture(Plugin):
    manifest: ClassVar[PluginManifest] = ...  # kind="capture"

    def __init__(self, top_video_path: str, side_video_path: str, queue_size: int = 8):
        self._top_path = top_video_path
        self._side_path = side_video_path
        self._queue_size = queue_size

    def open(self) -> "Iterator[FramePair]":
        """Fábrica: cada chamada abre os 2 arquivos do zero e devolve um generator novo.
        Reabertura é necessária pro passe 1/passe 2 do Detect (ver seção 3)."""
        top_cap = cv2.VideoCapture(self._top_path)
        side_cap = cv2.VideoCapture(self._side_path)
        if not top_cap.isOpened():
            raise CaptureError(f"Falha ao abrir vídeo do topo: {self._top_path}")
        if not side_cap.isOpened():
            top_cap.release()
            raise CaptureError(f"Falha ao abrir vídeo lateral: {self._side_path}")

        fps = int(top_cap.get(cv2.CAP_PROP_FPS))  # fps vem só do topo, como hoje (route_module recebe
                                                    # um único `fps` — origem: processVideoModule usa
                                                    # o fps devolvido por process_video(is_side=False))

        top_q: Queue = Queue(maxsize=self._queue_size)
        side_q: Queue = Queue(maxsize=self._queue_size)
        stop_event = threading.Event()

        def _reader(cap, q):
            try:
                while not stop_event.is_set():
                    ok, frame = cap.read()
                    q.put(frame if ok else None)  # None é o sentinela de fim de stream
                    if not ok:
                        break
            finally:
                cap.release()

        threading.Thread(target=_reader, args=(top_cap, top_q), daemon=True).start()
        threading.Thread(target=_reader, args=(side_cap, side_q), daemon=True).start()

        def _generator():
            index = 0
            try:
                while True:
                    top_frame = top_q.get()
                    side_frame = side_q.get()
                    if top_frame is None or side_frame is None:
                        # decisão explícita: para no MENOR dos dois vídeos, não continua
                        # decodificando/entregando o mais longo (ver seção 2)
                        break
                    yield FramePair(frame_index=index, top=top_frame, side=side_frame)
                    index += 1
            finally:
                stop_event.set()

        return fps, _generator()
```

**Nota de fidelidade**: o `fps` de hoje vem só do vídeo do topo (`process_video(..., is_side=False)`
retorna o `fps` usado depois em `data["fps"] = fps` — o `fps` calculado a partir do vídeo lateral é
descartado por `future_side.result()` reatribuir a mesma variável `fps` mas a ordem de atribuição no
código atual faz o valor final ser o do último `.result()` chamado, que é sempre `future_side` primeiro e
depois sobrescrito por `future_top` — **atenção**: no código atual, `fps` acaba sendo o do vídeo do topo
porque a linha `top_success, top_frames, fps, position_top = future_top.result()` roda depois de
`side_success, side_frames, fps, position_side = future_side.result()` e sobrescreve a variável). O plano
replica esse comportamento (fps efetivo = vídeo do topo) explicitamente, não por acidente — deixar
registrado no golden-file test um caso com fps diferente entre os dois vídeos de fixture pra confirmar que
o valor usado é o do topo, igual hoje.

**`plugin.toml`**:
```toml
[plugin]
name = "dual-video-file-capture"
version = "1.0.0"
kind = "capture"
entry = "plugin:DualVideoFileCapture"
api_version = "1.0"
schema = ">=1.0,<2.0"

[requires]
python = ">=3.11"
packages = ["opencv-python>=4.9"]
plugins = []
```

### 1.2 Rectify — `src/stages/rectify/`

**Arquivos**: `src/stages/rectify/plugin.py`, `src/stages/rectify/plugin.toml`.

**Classe**: `CpuPerspectiveRectifier(Plugin)` implementando o protocolo `Rectifier` de `stages.py`.

**Origem da lógica portada**: `perspectiveModule.py::perspective`, `::get_perspective_size`, e o bloco de
fallback de 4 pontos default de `::process_perspective` (`if len(frame_points) != 4: frame_points = [[0,0],
[video_width,0],[0,video_height],[video_width,video_height]]`), mais o `cv2.cvtColor(...,
COLOR_BGR2GRAY)`.

**O que muda**: de "processa a lista inteira de frames de uma vez e devolve `list[ndarray]`" pra "recebe 1
frame por vez, devolve 1 `RectifiedFrame` por vez". A matriz de perspectiva (`cv2.getPerspectiveTransform`)
é calculada **uma vez** em `setup()`, não recalculada a cada frame (hoje `perspective()` recalcula
`get_perspective_size` + `getPerspectiveTransform` a cada chamada, dentro do loop de
`process_perspective` — desperdício que o streaming também corrige de graça).

**Corpo esperado**:

```python
# src/stages/rectify/plugin.py
import cv2
import numpy as np
from src.core.plugin import Plugin
from src.core.schema.orientation import BoxOrientationConfig, CameraRole

class CpuPerspectiveRectifier(Plugin):
    def __init__(self, frame_points: list[list[int]], orientation: BoxOrientationConfig | None,
                 role: CameraRole, video_width: int, video_height: int):
        if len(frame_points) != 4:
            frame_points = [
                [0, 0], [video_width, 0], [0, video_height], [video_width, video_height],
            ]
        self._width, self._height = self._get_perspective_size(frame_points)
        points1 = np.float32(frame_points[0:4])
        points2 = np.float32([(0, 0), (self._width, 0), (0, self._height), (self._width, self._height)])
        self._matrix = cv2.getPerspectiveTransform(points1, points2)
        self._role = role
        self._orientation = orientation  # anexado à saída, não usado no cálculo do warp em si nesta fase

    @staticmethod
    def _get_perspective_size(frame_points):
        width = frame_points[1][0] - frame_points[0][0]
        height = frame_points[2][1] - frame_points[0][1]
        return width, height

    def rectify(self, frame: np.ndarray) -> "RectifiedFrame":
        warped = cv2.warpPerspective(frame, self._matrix, (self._width, self._height))
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        return RectifiedFrame(image=gray, role=self._role, orientation=self._orientation)
```

**Nota sobre `BoxOrientationConfig` no Rectify**: a tabela de camadas de `ARCHITECTURE.md` lista a entrada
de Rectify como `FramePair + BoxOrientationConfig → RectifiedFramePair`, mas a lógica de warp em si (os 4
pontos clicados) não muda com a orientação — os 4 pontos **são** os mesmos pontos que `PerspectiveUi`
sempre coletou. `BoxOrientationConfig` entra aqui só pra **anexar metadado** (`role`, `face_viewed`) ao
`RectifiedFrame`, que o `Fuse` vai precisar mais adiante pra rodar `axis_mapping()` — o Rectify não decide
nada a partir dele nesta fase (isso fica pra uma eventual Fase futura se um dia a retificação depender da
face vista, o que não é o caso hoje). Documentar isso explicitamente evita que o workstream de Rectify
tente over-engineer a orientação dentro do warp.

**`plugin.toml`**: `kind = "rectify"`, `entry = "plugin:CpuPerspectiveRectifier"`.

### 1.3 Detect — `src/stages/detect/`

**Arquivos**: `src/stages/detect/plugin.py`, `src/stages/detect/plugin.toml`.

**Classe**: `BackgroundSubtractionDetector(Detector)`.

**Origem da lógica portada**: `backgroundRemoveModule.py::remove_background` inteiro — construção do
modelo de fundo (amostragem a cada `frame_block = 500` frames + `np.max(selected_random_frames, axis=0)`)
e detecção por frame (`cv2.absdiff` contra `max_frame` → `cv2.threshold(minThreshold=80)` →
`cv2.threshold(127)` → `cv2.findContours(RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)` → maior contorno por
`cv2.contourArea` → centroide via `cv2.moments` com `cy_from_bottom = frame_height - cy_from_top`).

**O que muda**: ver seção 3 inteira — é a mudança mais delicada da fase. Resumo: vira duas passadas
(constrói modelo de fundo streaming-friendly na primeira, detecta na segunda), com o modo debug
(`cv2.imshow`/`waitKey`) **removido** do estágio de produção (fica só em um script de debug manual fora do
pipeline, se necessário — não faz sentido bloquear um generator streaming num `cv2.waitKey(0)`).

**Saída**: em vez do sentinela `(-1, -1)`, devolve `FrameDetections(frame_index=i, view=role,
detections=[])` (lista vazia) quando não há contorno ou `m00 == 0`; senão `detections=[Detection(centroid=
Point2D(x=cx, y=cy_from_bottom), area=cv2.contourArea(max_contour))]`.

### 1.4 Track — `src/stages/track/`

**Arquivos**: `src/stages/track/plugin.py`, `src/stages/track/plugin.toml`.

**Classe**: `SingleEntityTracker(Tracker)`.

**Origem da lógica portada**: não existe como função separada hoje — é o comportamento *implícito* de
`remove_background` sempre devolver no máximo 1 posição por frame (porque só pega o maior contorno) e
`route_module` tratar essa lista posicionalmente por índice de frame, sem noção de identidade.

**Corpo esperado**:

```python
class SingleEntityTracker(Plugin):
    ENTITY_ID = 0

    def __init__(self):
        self._points: dict[int, Point2D] = {}

    def update(self, dets: FrameDetections) -> None:
        if not dets.detections:
            return  # buraco no dict = oclusão/não-detecção, substitui o sentinela (-1,-1)
        # convenção: se por acaso vier mais de 1 detecção (não deveria, Detect já filtra pelo maior
        # contorno), pega a de maior área — trivial e documentado, não é decisão nova de tracking real
        best = max(dets.detections, key=lambda d: d.area or 0.0)
        self._points[dets.frame_index] = best.centroid

    def tracks(self) -> list[Track]:
        return [Track(entity_id=self.ENTITY_ID, view=self._view, points=dict(self._points))]

    def reset(self) -> None:
        self._points.clear()
```

Dois `SingleEntityTracker` são instanciados pelo orquestrador (um por view: `top`, `side`), cada um
consumindo o stream de `FrameDetections` da sua view.

### 1.5 Fuse — `src/stages/fuse/`

**Arquivos**: `src/stages/fuse/plugin.py`, `src/stages/fuse/plugin.toml`.

**Classe**: `Fusion(FusionPlugin)`.

**Origem da lógica portada**: `routeAnalizer.py::route_module` (merge por índice, `frame_count =
min(len(positions_top), len(positions_side))` — que na prática nunca vai truncar nada agora, porque o
Capture já parou no vídeo mais curto, ver seção 2) e `getData.py::get_video_data` +
`::pixel_to_cm` (dimensões da caixa em px/cm), mas dirigido por `axis_mapping()` — ver seção 4 inteira.

Ver seção 4 pro corpo detalhado do cálculo. Resumo da tarefa: `Fusion.fuse(top_track, side_track,
box_orientation, box_cm) -> tuple[list[Route3D], Calibration]`.

**`plugin.toml`**: `kind = "fusion"`.

---

## 2. Capture como generator + streaming lockstep de 2 câmeras

### 2.1 Tipo e contrato

`FramePair(frame_index: int, top: np.ndarray, side: np.ndarray)` — definido na Fase 1 (schema), consumido
aqui. `Capture.open() -> tuple[int, Iterator[FramePair]]` (fps + generator) é o contrato que
`DualVideoFileCapture` implementa (ver corpo completo na seção 1.1).

### 2.2 Onde o lockstep acontece

O pareamento das duas câmeras acontece **dentro do próprio Capture**, não é adiado pro Fuse como hoje. Isso
é uma escolha deliberada e uma mudança de comportamento que precisa ficar registrada:

- **Hoje**: `process_video(is_side=False)` e `process_video(is_side=True)` rodam cada um até o fim do seu
  próprio vídeo, independentemente (via `ThreadPoolExecutor`), produzindo duas listas de posições de
  tamanhos possivelmente diferentes; só depois `route_module` faz `frame_count = min(len(positions_top),
  len(positions_side))` e descarta a sobra da lista mais longa.
- **Proposto**: o generator de `DualVideoFileCapture` para de emitir `FramePair`s assim que **qualquer**
  uma das duas filas devolver `None` (fim de stream). Isso significa que se o vídeo lateral tiver, digamos,
  200 frames a mais que o do topo, esses 200 frames a mais **nunca são lidos/retificados/detectados** — no
  código atual eles são processados inteiramente (decode + warp + grayscale + subtração de fundo) e só
  descartados no merge final.
- **Resultado final**: idêntico ao de hoje (o `min()` já garantia que esses frames extras nunca apareciam
  no `data["route"]` final) — a mudança é só *quando* o corte acontece, não *o que* sobra. Ganho: evita
  trabalho de decode/CPU sobre frames que seriam descartados de qualquer forma; essencial pro objetivo de
  streaming (não faz sentido continuar puxando frames de uma câmera sem ter o par da outra pra avançar o
  pipeline).
- **Risco e mitigação**: essa é uma mudança de timing que pode em teoria expor efeitos colaterais sutis.
  O ponto sensível é o **modelo de fundo**: como ele é por-câmera e independente do parceiro, a truncagem em
  lockstep vale **apenas** para a emissão pareada de `FramePair`s (o passe de detecção/rota), **nunca** para
  a construção do modelo de fundo. O passe 1 do Detect **precisa** ler cada view até o fim do *seu próprio*
  vídeo (não pelo generator pareado, que trava no mais curto — ver seção 3.4); caso contrário o modelo de
  fundo da view mais longa seria construído só sobre a faixa truncada e divergiria silenciosamente do
  comportamento atual, que amostra o vídeo inteiro de cada view de forma independente. A paridade de
  "resultado idêntico ao de hoje" só se sustenta com essa ressalva. **Ação concreta**: o fixture do
  golden-file test (seção 5) deve incluir deliberadamente um caso
  com vídeos top/side de comprimentos diferentes, e o teste deve confirmar que o resultado bate com o que
  o pipeline antigo produziria nesse mesmo caso (rodar o pipeline antigo uma vez sobre a mesma fixture como
  double-check pontual, não como parte da suite permanente — só pra validar a paridade desta decisão
  específica antes de aceitar o golden-file como referência).

### 2.3 Por que Rectify/Detect são per-view mas Fuse não é per-frame

- Rectify e Detect processam **uma imagem por vez, uma view por vez** — o orquestrador (Fase 2,
  `pipeline.py`) itera o generator de `FramePair`s e, pra cada par, chama `rectifier_top.rectify(pair.top)`
  e `rectifier_side.rectify(pair.side)` independentemente, depois `detector_top.detect(...)` e
  `detector_side.detect(...)` independentemente, alimentando `tracker_top.update(...)` e
  `tracker_side.update(...)`. Nenhum desses estágios olha pra "quadro completo" (as duas views juntas) —
  cada um só vê a própria view, frame a frame. Isso é o que permite não reter nenhuma imagem decodificada
  além do frame atual (o ganho real de memória do streaming).
- Fuse, em contraste, só roda **uma vez, no final**, depois que os dois streams inteiros foram consumidos
  — recebe `top_tracker.tracks()` e `side_tracker.tracks()` (cada um um `list[Track]`, aqui sempre com 1
  elemento por causa do `SingleEntityTracker`) já prontos. Isso é idêntico em espírito ao que
  `route_module` já faz hoje (opera sobre as listas completas de posições) — a diferença é que essas listas
  agora guardam só `Point2D` por frame (poucos bytes), não imagens inteiras, então não há motivo pra tornar
  Fuse streaming também: o custo de memória de reter `Track.points` (um dict de `frame_index -> Point2D`
  pro vídeo inteiro) é desprezível comparado ao custo de reter frames de imagem, que é o problema real que
  a Fase 3 resolve.

---

## 3. Modelo de fundo streaming — duas passadas (decisão central de risco da fase)

### 3.1 Por que a amostragem em si não é o problema

A amostragem de hoje (`for index in range(0, len(raw_warpped_frames), frame_block): selected_random_frames
.append(raw_warpped_frames[index])`, com `frame_block = 500`) pega os frames de índice 0, 500, 1000, ... —
apesar do nome da variável (`selected_random_frames`), **não há aleatoriedade real**, é amostragem
determinística a cada 500. Essa regra **não depende** de conhecer o total de frames de antemão: é
equivalente, de forma streaming, a "mantenha um contador `i`; se `i % 500 == 0`, guarde este frame; descarte
os demais imediatamente". Isso por si só já seria memory-bounded (`O(frame_count / 500)` frames retidos, não
`O(frame_count)`).

### 3.2 Por que isso não resolve o problema todo — não-causalidade do modelo de fundo

O algoritmo de hoje usa `max_frame = np.max(selected_random_frames, axis=0)` **para diffar o frame 0**
(primeira iteração do segundo loop, `for i, frame in enumerate(raw_warpped_frames)`) — ou seja, pra
detectar o inseto no frame 0, o algoritmo já precisa do máximo de intensidade entre os frames 0, 500, 1000,
..., incluindo frames que só existem **no futuro** relativo ao frame 0. Isso é **não-causal**: é
estruturalmente incompatível com uma detecção genuinamente single-pass/online (onde cada frame só pode
depender de frames já vistos).

### 3.3 Decisão: duas passadas reais sobre o mesmo vídeo

- **Passe 1 (construção do modelo de fundo)**: uma mini-pipeline interna Capture→Rectify (sem Detect,
  sem Track) itera o vídeo da view em questão do início ao fim, mantém só um contador `i` e a lista
  `sampled_frames` (append só quando `i % 500 == 0`), e ao final do stream computa
  `max_frame = np.max(sampled_frames, axis=0).astype(np.uint8)` — idêntico matematicamente ao de hoje.
  Memória: `O(frame_count / 500)` frames retificados, não o vídeo inteiro.
- **Passe 2 (detecção)**: reabre o **mesmo** vídeo do zero (nova instância de Capture, nova iteração de
  Rectify — determinístico e sem estado, então produz frames retificados byte-a-byte idênticos aos do
  passe 1), e para cada frame retificado chama a lógica de detecção de hoje
  (`cv2.absdiff(max_frame, frame)` → thresholds → contornos → centroide) já com `max_frame` fixo do passe
  1, emitindo `FrameDetections` um por vez. Memória: `O(1)` frame retido por vez.
- **Custo assumido**: 2x decode + 2x warp de perspectiva por vídeo (uma vez no passe 1, uma vez no passe
  2). Aceito como tradeoff correto — decode+warp é ordens de magnitude mais barato que reter o vídeo
  inteiro em RAM, que é o problema que a Fase 3 existe pra resolver. **Alternativa descartada**: modelo de
  fundo incremental (running-max atualizado frame a frame, sem segunda passada) foi considerado e
  rejeitado porque muda a matemática do algoritmo atual (o running-max num ponto do vídeo não é igual ao
  max completo sobre as amostras 0,500,1000,...) — arriscaria não bater com o golden-file e mudaria
  resultados de análises já validadas no TCC original. Fica registrado como otimização de performance
  possível para uma fase futura, fora do escopo de paridade de comportamento da Fase 3.

### 3.4 O ponto de acoplamento real — e por que ele existe

O protocolo `Detector` fixado na Fase 2 (`stages.py`) expõe só `detect(frame: RectifiedFrame) ->
FrameDetections` como método abstrato. O passe 1 não cabe dentro desse método (ele processa o vídeo
inteiro, não um frame). Solução: o passe 1 roda dentro de `BackgroundSubtractionDetector.setup(ctx)` — o
hook de lifecycle que já vem de `Plugin` (não de `Detector`), então **não exige mudar a assinatura de
`Detector`** fixada na Fase 2.

Só que `setup(ctx)` precisa, pra rodar o passe 1, instanciar sua **própria** mini Capture+Rectify a partir
da config que `ctx` já carrega (caminho do vídeo, pontos de perspectiva, orientação) — ou seja, o
workstream de **Detect** passa a ter uma dependência real (de implementação, não só de tipo) das classes
concretas `DualVideoFileCapture` e `CpuPerspectiveRectifier`. Isso é diferente da relação "tipo-apenas" que
os outros estágios têm entre si (que só dependem dos tipos do schema, fixados desde a Fase 1/2, nunca da
implementação concreta um do outro).

**Ponto crítico de paridade** (ver seção 2.2): o passe 1 lê **só a view deste detector**, e a lê até o fim
do *seu próprio* vídeo — **não** usa o generator pareado `open()`, que trava no vídeo mais curto e
truncaria o modelo de fundo da view mais longa. Por isso `DualVideoFileCapture` expõe um iterador de view
única `open_single(role) -> Iterator[np.ndarray]` (pequena extensão do contrato de Capture da seção 1.1),
que só lê e entrega frames crus de uma câmera, sem lockstep. Bônus: evita decodificar o vídeo da outra
câmera nas pré-passadas (com 2 detectores, o `open()` pareado decodificaria os dois vídeos duas vezes).

```python
# dentro de BackgroundSubtractionDetector.setup(ctx)
def setup(self, ctx: "PipelineContext") -> None:
    # passe 1: lê APENAS esta view, até o fim do SEU próprio vídeo (não o generator pareado, que
    # trunca no mais curto — ver seção 2.2). Modelo de fundo é por-câmera e independente do parceiro.
    frames = ctx.capture_factory.open_single(self._role)  # Iterator[np.ndarray] de uma só câmera
    rectifier = ctx.rectifier_factory.build()  # mesma config de pontos/orientação já usada no passe real
    counter = 0
    sampled = []
    for raw in frames:
        rectified = rectifier.rectify(raw)
        if counter % 500 == 0:
            sampled.append(rectified.image)
        counter += 1
    self._max_frame = np.max(sampled, axis=0).astype(np.uint8)
```

Isso é o **único** furo real na paralelização "limpa" dos 5 workstreams (ver seção 6) — fica marcado
explicitamente aqui e reiterado lá, com a mitigação: durante o desenvolvimento paralelo, o workstream de
Detect usa uma Capture+Rectify **fake/stub** (geradores em memória que produzem frames sintéticos
conhecidos) só pra seus próprios testes unitários de `setup()`, e só troca pelas implementações reais no
passo de integração sequencial no final da fase — dessa forma o paralelismo se mantém até o nível "meus
testes unitários passam", e o acoplamento real só aparece (e só precisa ser resolvido) na integração.

### 3.5 Modo debug removido do estágio de produção

O bloco `if debug_mode: cv2.imshow(...); cv2.waitKey(0)` de `remove_background` **não** é portado pro
`BackgroundSubtractionDetector` de produção — um generator streaming não deve bloquear em `waitKey(0)`.
Se inspeção visual for necessária durante o desenvolvimento, fica como um script manual solto fora do
pipeline (`scripts/debug_detect.py`, fora do escopo desta fase salvo necessidade explícita).

---

## 4. Correção dos bugs #2 e #3 — algoritmo exato

### 4.1 `axis_mapping()` — bug #3

**Passo 1 — tabela estática de vértices.** Cada `BoxVertex` (dos 8 definidos em `orientation.py`, Fase 1)
é decomposto numa tripla de lados, um por eixo, `MIN` ou `MAX`:

| Componente do vértice | Eixo | Lado |
|---|---|---|
| `LEFT` | x (largura) | `MIN` |
| `RIGHT` | x (largura) | `MAX` |
| `FRONT` | y (profundidade) | `MIN` |
| `BACK` | y (profundidade) | `MAX` |
| `BOTTOM` | z (altura) | `MIN` |
| `TOP` | z (altura) | `MAX` |

```python
_VERTEX_SIDES: dict[BoxVertex, dict[str, str]] = {
    BoxVertex.TOP_FRONT_LEFT:     {"x": "MIN", "y": "MIN", "z": "MAX"},
    BoxVertex.TOP_FRONT_RIGHT:    {"x": "MAX", "y": "MIN", "z": "MAX"},
    BoxVertex.TOP_BACK_LEFT:      {"x": "MIN", "y": "MAX", "z": "MAX"},
    BoxVertex.TOP_BACK_RIGHT:     {"x": "MAX", "y": "MAX", "z": "MAX"},
    BoxVertex.BOTTOM_FRONT_LEFT:  {"x": "MIN", "y": "MIN", "z": "MIN"},
    BoxVertex.BOTTOM_FRONT_RIGHT: {"x": "MAX", "y": "MIN", "z": "MIN"},
    BoxVertex.BOTTOM_BACK_LEFT:   {"x": "MIN", "y": "MAX", "z": "MIN"},
    BoxVertex.BOTTOM_BACK_RIGHT:  {"x": "MAX", "y": "MAX", "z": "MIN"},
}
```

**Passo 2 — resolver os 4 cantos clicados.** `CameraOrientation.corner_vertices` guarda os 4 vértices na
mesma ordem de clique que `PerspectiveUi` sempre usou: `[superior-direito (TR), superior-esquerdo (TL),
inferior-direito (BR), inferior-esquerdo (BL)]` — a mesma ordem que `frame_points[0:4]` assume hoje em
`perspectiveModule.perspective` (`points1 = np.float32(frame_points[0:4])` mapeado pra `[(0,0), (width,0),
(0,height), (width,height)]`, ou seja `TR→(0,0), TL→(width,0)`... **atenção**: a ordem exata de
`get_perspective_size`/`perspective` hoje é `frame_points[0]=TR, [1]=TL, [2]=BR, [3]=BL` implicitamente
pela forma como `width = frame_points[1][0]-frame_points[0][0]` e `height = frame_points[2][1] -
frame_points[0][1]` são calculados — replicar exatamente essa ordem ao definir `corner_vertices`, já que
`PerspectiveUi` (Fase 4) vai gerar essa lista na mesma ordem de clique de sempre.

Pra cada uma das 4 posições (TR, TL, BR, BL), resolve a tripla `(lado_x, lado_y, lado_z)` via
`_VERTEX_SIDES[vertex]`.

**Passo 3 — determinar o eixo de imagem u (horizontal).** Compara a tripla do par direito (TR, BR) com a
tripla do par esquerdo (TL, BL): o eixo cujo lado é constante dentro de cada par mas difere entre os dois
pares é o eixo que varia ao longo de u.

**Passo 4 — determinar o eixo de imagem v (vertical).** Mesma lógica comparando o par de cima (TR, TL)
com o par de baixo (BR, BL).

**Passo 5 — eixo constante (não observável).** O eixo que não varia em nenhuma das 4 combinações é o eixo
perpendicular à `face_viewed` dessa câmera — não é observável a partir dela (precisa vir da outra câmera,
ou é conhecido por outra via, ex. profundidade fixa da caixa).

**Passo 6 — sinal/direção.**
- Se o par direito (TR, BR) tem lado `MAX` no eixo mapeado pra u e o par esquerdo (TL, BL) tem `MIN` →
  `u_sign = +1` (u cresce no mesmo sentido do eixo 3D); caso inverso → `u_sign = -1`.
- Se o par de cima (TR, TL) tem lado `MAX` no eixo mapeado pra v (respeitando que hoje `v` já é medido de
  baixo pra cima via `cy_from_bottom = frame_height - cy_from_top` em `backgroundRemoveModule.py`) e o par
  de baixo (BR, BL) tem `MIN` → `v_sign = +1`; caso inverso → `v_sign = -1`.

```python
@dataclass(frozen=True)
class AxisMapping:
    u_axis: Literal["x", "y", "z"] | None
    u_sign: int
    v_axis: Literal["x", "y", "z"] | None
    v_sign: int
    constant_axis: Literal["x", "y", "z"]

def _resolve_camera_axis_mapping(orientation: CameraOrientation) -> AxisMapping:
    tr, tl, br, bl = (_VERTEX_SIDES[v] for v in orientation.corner_vertices)
    axes = ("x", "y", "z")

    u_axis = next(a for a in axes if tr[a] == br[a] and tl[a] == bl[a] and tr[a] != tl[a])
    v_axis = next(a for a in axes if tr[a] == tl[a] and br[a] == bl[a] and tr[a] != br[a])
    constant_axis = next(a for a in axes if a != u_axis and a != v_axis)

    u_sign = 1 if tr[u_axis] == "MAX" else -1
    v_sign = 1 if tr[v_axis] == "MAX" else -1

    return AxisMapping(u_axis=u_axis, u_sign=u_sign, v_axis=v_axis, v_sign=v_sign,
                        constant_axis=constant_axis)
```

**Passo 7 — combinar as duas câmeras no `Fuse`.** Pra cada eixo x/y/z, procura qual câmera+eixo de imagem
(u ou v) fornece o dado:

```python
def combine(top_mapping: AxisMapping, side_mapping: AxisMapping) -> dict[str, tuple[CameraRole, str, int]]:
    """Retorna, por eixo 3D, (camera, 'u'|'v', sinal)."""
    providers: dict[str, list[tuple[CameraRole, str, int]]] = {"x": [], "y": [], "z": []}
    for role, mapping in ((CameraRole.TOP, top_mapping), (CameraRole.SIDE, side_mapping)):
        if mapping.u_axis:
            providers[mapping.u_axis].append((role, "u", mapping.u_sign))
        if mapping.v_axis:
            providers[mapping.v_axis].append((role, "v", mapping.v_sign))

    resolved = {}
    for axis, candidates in providers.items():
        if not candidates:
            raise FuseConfigError(f"Nenhuma câmera fornece o eixo '{axis}' — configuração de orientação "
                                   f"incompleta.")
        if len(candidates) == 1:
            resolved[axis] = candidates[0]
        else:
            # redundância: as duas câmeras enxergam o mesmo eixo — política determinística: prioriza TOP
            preferred = next((c for c in candidates if c[0] == CameraRole.TOP), candidates[0])
            logger.warning("Eixo '%s' fornecido por ambas as câmeras; usando %s (política: top > side).",
                            axis, preferred[0])
            resolved[axis] = preferred
    return resolved
```

Isso substitui o hardcode de hoje em `route_module` (`x`/`y` sempre do topo, `z` sempre da 2ª coordenada
lateral) por uma derivação genérica, mas **replica exatamente esse resultado** quando a configuração de
orientação típica (câmera do topo olhando `BoxFace.TOP`, câmera lateral olhando `BoxFace.FRONT`, por
exemplo) é usada — importante deixar isso testado explicitamente no golden-file (seção 5): a configuração
de orientação da fixture deve ser escolhida de forma que `axis_mapping()` produza o mesmo resultado que o
hardcode antigo, validando que a generalização não introduziu regressão no caso comum.

### 4.2 `px_per_cm` por eixo — completando o bug #3

Substitui `getData.py::pixel_to_cm` (que hoje calcula as 3 razões — largura, altura, profundidade — todas
a partir de `height_side`, e tira a mediana das três, o que é uma mistura de unidades sem sentido físico).
Novo cálculo, um por eixo, usando a dimensão de pixel do frame retificado no eixo de imagem correto (via
`AxisMapping` resolvido no passo 7 acima):

```python
def compute_px_per_cm(resolved: dict[str, tuple[CameraRole, str, int]],
                       top_frame_shape: tuple[int, int], side_frame_shape: tuple[int, int],
                       box_cm: Point3D) -> Point3D:
    # top_frame_shape / side_frame_shape = (height_px, width_px) do RectifiedFrame, análogo a
    # `height_top, width_top = top_frames[0].shape` de getData.py hoje
    dims = {
        (CameraRole.TOP, "u"): top_frame_shape[1],
        (CameraRole.TOP, "v"): top_frame_shape[0],
        (CameraRole.SIDE, "u"): side_frame_shape[1],
        (CameraRole.SIDE, "v"): side_frame_shape[0],
    }
    box_cm_by_axis = {"x": box_cm.x, "y": box_cm.y, "z": box_cm.z}
    ratios = {}
    for axis, (role, image_axis, _sign) in resolved.items():
        px_dim = dims[(role, image_axis)]
        ratios[axis] = px_dim / box_cm_by_axis[axis]
    return Point3D(x=ratios["x"], y=ratios["y"], z=ratios["z"])
```

Isso substitui a mediana espúria de hoje por 3 razões fisicamente corretas, cada uma derivada da dimensão
de pixel real do eixo de imagem que de fato observa aquele eixo 3D.

### 4.3 Conversão px→cm já dentro do Fuse — raiz do bug #2

Decisão de design: `Fusion.fuse(...)` já entrega `Route3D` em **centímetros**, convertendo cada eixo
independentemente no momento da fusão (usando o `sign` resolvido no passo 7 pra orientação correta, e
`px_per_cm` do passo acima):

```python
def fuse(top_track: Track, side_track: Track, box_orientation: BoxOrientationConfig,
         box_cm: Point3D, fps: float, top_shape, side_shape) -> tuple[list[Route3D], Calibration]:
    top_mapping = _resolve_camera_axis_mapping(box_orientation.top_camera)
    side_mapping = _resolve_camera_axis_mapping(box_orientation.side_camera)
    resolved = combine(top_mapping, side_mapping)
    px_per_cm = compute_px_per_cm(resolved, top_shape, side_shape, box_cm)

    tracks_by_role = {CameraRole.TOP: top_track, CameraRole.SIDE: side_track}
    px_per_cm_by_axis = {"x": px_per_cm.x, "y": px_per_cm.y, "z": px_per_cm.z}

    frame_indices = sorted(set(top_track.points) & set(side_track.points))  # substitui o
                                                                              # `min(len(...), len(...))`
                                                                              # de route_module por
                                                                              # interseção explícita —
                                                                              # ainda mais robusto a buracos

    points: dict[int, Point3D] = {}
    for idx in frame_indices:
        values = {}
        for axis, (role, image_axis, sign) in resolved.items():
            centroid = tracks_by_role[role].points[idx]
            raw_px = centroid.x if image_axis == "u" else centroid.y
            values[axis] = (sign * raw_px) / px_per_cm_by_axis[axis]
        points[idx] = Point3D(**values)

    route = Route3D(entity_id=SingleEntityTracker.ENTITY_ID, points=points)
    calibration = Calibration(box_cm=box_cm, px_per_cm=px_per_cm, fps=fps, orientation=box_orientation)
    return [route], calibration
```

Isso move a conversão px→cm pra **dentro** do Fuse, de uma vez, corretamente por eixo — em vez de deixar
pra cada plugin de metadata reimplementar (mal) essa conversão como acontece hoje. É essa mudança
estrutural, mais do que só "trocar a fórmula", que elimina o bug #2 na raiz.

### 4.4 Fórmula de velocidade corrigida — bug #2

Com `Route3D` já em cm, o plugin `speed` (reescrito, `plugins/speed/plugin.py`, substitui
`MetadataModule/speedModule.py`) fica assim:

```python
def module_call(ctx: AnalysisContext) -> None:
    route = ctx.result.routes[0]  # SingleEntityTracker garante 1 rota nesta fase
    fps = ctx.result.calibration.fps
    dt = 1.0 / fps

    indices = sorted(route.points)
    speed_by_frame: dict[int, float] = {}
    distance_total = 0.0
    speed_total = 0.0
    sample_count = 0

    for prev_idx, idx in zip(indices, indices[1:]):
        p1, p2 = route.points[prev_idx], route.points[idx]
        distance_cm = math.dist((p1.x, p1.y, p1.z), (p2.x, p2.y, p2.z))  # já em cm — sem
                                                                           # `* pixel_to_cm_ratio / 100`
                                                                           # nem qualquer outra conversão
        speed_cm_s = distance_cm / dt  # == distance_cm * fps — fórmula pedida:
                                        # velocidade = distância_cm / (1/fps)
        speed_by_frame[idx] = speed_cm_s
        distance_total += distance_cm
        speed_total += speed_cm_s
        sample_count += 1

    average_speed = speed_total / sample_count if sample_count else 0.0  # FIX ADICIONAL (aprovado,
                                                                            # fora do inventário original):
                                                                            # hoje divide por
                                                                            # len(data["route"]) (contagem
                                                                            # de FRAMES); correto é dividir
                                                                            # pela contagem de AMOSTRAS de
                                                                            # velocidade (frame_count - 1,
                                                                            # ou 0 quando não há pares)

    ctx.add_metric(Metric(name="speed_by_frame", value=speed_by_frame, unit="cm/s", producer="speed"))
    ctx.add_metric(Metric(name="average_speed", value=average_speed, unit="cm/s", producer="speed"))
    ctx.add_metric(Metric(name="distance_total", value=distance_total, unit="cm", producer="speed"))
```

Note que **nenhuma divisão por `pixel_to_cm_ratio`** aparece aqui — isso é o que efetivamente mata o bug
(hoje: `distance = math.dist(...) * pixel_to_cm_ratio / 100` seguido de `speed = distance /
pixel_to_cm_ratio`, o que faz o `pixel_to_cm_ratio` se cancelar algebricamente e deixar `speedTotal` numa
unidade sem sentido físico — nem "px" nem "cm" de verdade). Com a conversão feita uma única vez, no lugar
certo (Fuse), o plugin de velocidade só faz geometria pura em cm.

### 4.5 Plugin `border` — nota de escopo

`MetadataModule/borderModule.py` também é reescrito nesta fase (a tabela de migração de `ARCHITECTURE.md`
aponta Fase 3, não 4). Como `Route3D` agora está em cm, os pontos de borda (hoje clicados em pixel via
`BorderUi`, armazenados como `frame_border_points_top`/`_side`) precisam da mesma conversão
px→cm/`axis_mapping` pra ficarem na mesma unidade das rotas antes de comparar `border_min_x <= x <=
border_max_x`. Este plano **não** redesenha a tela `BorderUi` (isso é Fase 4) — só especifica que o novo
`plugins/border/plugin.py` deve converter os 2 pontos de borda de cada view pra cm usando o mesmo
`px_per_cm`/`axis_mapping` já calculado e guardado em `Calibration`, antes de fazer a comparação, em vez de
comparar pixel bruto contra coordenada já em cm (bug latente que seria introduzido se o border plugin não
fosse atualizado junto). Corpo exato fica a cargo do workstream (é um adapter mecânico da mesma lógica de
min/max de hoje, só trocando a fonte das coordenadas), não detalhado linha a linha aqui por não estar
entre os bugs #2/#3 nomeados — mas **é tarefa obrigatória desta fase**, não opcional.

---

## 5. Estratégia de teste golden-file

### 5.1 Geração da fixture sintética

Não existe vídeo de fixture real no repo hoje. Script só-de-teste, **não faz parte do pacote de produção**:
`tests/fixtures/generate_fixture_videos.py`.

Abordagem:
1. Define um caminho 3D sintético determinístico em cm, por frame, ex. movimento circular simples:
   ```python
   def synthetic_path(frame_index: int, total_frames: int) -> tuple[float, float, float]:
       t = frame_index / total_frames
       x_cm = 5.0 + 3.0 * math.cos(2 * math.pi * t)
       y_cm = 5.0 + 3.0 * math.sin(2 * math.pi * t)
       z_cm = 2.0 + 1.5 * t  # sobe lentamente ao longo do vídeo
       return x_cm, y_cm, z_cm
   ```
2. Define uma resolução de fixture pequena (320x240), `fps=30`, `total_frames=1200` (40s), e um
   `px_per_cm_synthetic` conhecido (ex. 20 px/cm) só pra gerar as imagens — **não** é o valor que o pipeline
   deve recuperar via `axis_mapping`, é só um parâmetro do gerador (o pipeline recalcula seu próprio
   `px_per_cm` a partir das dimensões de frame + `box_cm` configurado no teste, como faria com qualquer
   vídeo real). **`total_frames` precisa ser maior que `frame_block` (500)**: com a fixture curta de 150
   frames originalmente proposta, `range(0, 150, 500)` amostra **só o índice 0**, e o `np.max` sobre uma
   única imagem é a identidade — o modelo de fundo de duas passadas (seção 3) ficaria trivialmente
   exercitado e uma regressão na lógica de amostragem (stride errado, off-by-one no contador) passaria
   despercebida. Com 1200 frames amostram-se os índices 0, 500 e 1000 (3 frames), exercitando de fato o
   `np.max` multi-frame. Alternativa equivalente, se preferir manter a fixture curta: tornar `frame_block`
   injetável no detector e passar um valor pequeno (ex. 50) no teste — mas isso muda a API de produção, então
   aumentar a fixture é o caminho mais fiel.
3. Renderiza o vídeo do topo (mostrando `x_cm, y_cm`) e o vídeo lateral (mostrando `y_cm` ou uma constante,
   `z_cm` — replicando a mesma convenção `top→(x,y), side→(_,z)` de hoje) como fundo cinza-claro uniforme
   com um círculo escuro preenchido (`cv2.circle`) desenhado na posição de pixel correspondente a cada
   frame, gravando com `cv2.VideoWriter` (codec `mp4v` ou `XVID`, o que estiver disponível no ambiente de
   CI).
4. Inclui uma segunda variante da fixture com vídeos top/side de comprimentos diferentes, especificamente
   para validar a decisão de truncamento da seção 2.2. A diferença de comprimento deve **atravessar uma
   fronteira de amostragem** (múltiplo de `frame_block=500`): ex. top com 1200 frames e side com 1600, de
   forma que o side tenha um frame de amostra (índice 1500) além do fim do top. Isso torna o teste capaz de
   pegar a regressão da seção 3.4/2.2 — se o passe 1 do modelo de fundo truncasse o side no comprimento do
   top (1200) em vez de ler o vídeo inteiro do side (1600), a amostra 1500 sumiria, `max_frame` mudaria e o
   resultado divergiria. Uma diferença de só 20 frames (< 500) nunca exporia isso.
5. Os `.mp4`/`.avi` gerados (ainda pequenos — ~1 MB por vídeo pra 1200 frames em 320x240, já que são fundo
   uniforme + 1 círculo, altamente compressível) são **commitados** em
   `tests/fixtures/videos/` — não regenerados a cada run de CI (determinismo de codec de vídeo entre
   máquinas/versões de OpenCV é frágil o bastante pra não confiar em regerar on-the-fly no pipeline de
   teste principal; o script gerador fica disponível pra quem precisar recriar as fixtures manualmente se
   um dia precisarem mudar).

### 5.2 Geração e commit do `AnalysisResult` de referência

1. Depois que a pipeline Fase 3 estiver implementada e integrada, rodar 1 vez sobre a fixture principal.
2. **Antes de aceitar a saída como golden file**, validar independentemente contra o caminho sintético
   conhecido: um teste separado (não o golden-file test) assevera que a rota recuperada por
   `axis_mapping`/Fuse aproxima o `synthetic_path(frame_index, total_frames)` original dentro de uma
   tolerância generosa de detecção (ex. `abs(recovered_x_cm - expected_x_cm) < 0.5` cm, contabilizando
   erro de discretização de pixel/contorno) — isso existe **especificamente** pra evitar committar um
   golden file que já contém um bug (o golden file sozinho só protege contra regressão futura, não contra
   um bug presente desde o commit inicial).
3. Só depois desse double-check passar, serializa `AnalysisResult` (pydantic `.model_dump_json()`) pra
   `tests/fixtures/golden/expected_result.json` e commita.

### 5.3 Tolerância de comparação

- Campos determinísticos sem acumulação (`calibration.px_per_cm`, `calibration.box_cm`,
  `route.points[i].{x,y,z}` individuais): `pytest.approx(expected, abs=1e-6)` — todo o cálculo é
  determinístico (mesma imagem sintética, mesmas operações OpenCV), então divergência além de ruído de
  ponto flutuante é bug, não tolerância aceitável.
- Campos com soma acumulada (`distance_total`, `average_speed`, `speed_by_frame` somado): tolerância um
  pouco mais frouxa, `abs=1e-4`, pra absorver possível diferença de ordem de soma em ponto flutuante entre
  o loop antigo e o acumulador novo (mesmo que ambos processem os mesmos números, a ordem de operações de
  ponto flutuante já mudou entre o código legado e o novo, o que é esperado e aceitável).
- Campos estruturais (`frame_index`, `entity_id`, contagem de pontos, presença/ausência de detecção por
  frame): **igualdade exata**, sem tolerância — divergência aqui indica um bug real de composição entre
  estágios (ex. off-by-one em algum stage), não ruído numérico.

### 5.4 Teste de memória limitada

`tests/test_golden_pipeline.py::test_memory_bounded` usa `tracemalloc` (cross-platform, ao contrário de
`resource.getrusage` que não existe no Windows — relevante já que o ambiente de dev deste projeto é
Windows): mede o pico de memória alocada durante o run completo da pipeline sobre a fixture e assevera que
fica abaixo de um teto pequeno e explícito (ex. `50 * 1024 * 1024` — 50 MB). O teto só é discriminante se o
comportamento antigo (vídeo inteiro em RAM) o ultrapassar de fato na fixture: um frame grayscale 320x240 é
`320*240 ≈ 0,073 MB`, então a **fixture de 1200 frames** (seção 5.1) bufferizada inteira dá `≈ 88 MB por
view` — e o código atual mantém **duas** listas por view (os frames retificados crus **e** a lista de
frames de diff), somando ~176 MB por view, muito acima dos 50 MB. (É por isso que a fixture curta de 150
frames originalmente proposta não servia: a ~11,5 MB por view ela *passaria* no teto de 50 MB mesmo
bufferizando tudo, tornando o teste inócuo.) O streaming da Fase 3 retém `O(1)` frame por vez (mais as ~3
amostras do modelo de fundo), ordens de magnitude abaixo dos 50 MB — o teto é frouxo o bastante pra não ser
frágil a overhead de Python/numpy, mas, com a fixture de 1200 frames, apertado o bastante pra pegar uma
regressão grosseira tipo "voltou a bufferizar tudo em lista". Guarda-corpo grosseiro mas eficaz, não uma
medição de precisão de memória.

---

## 6. Paralelização — conflitos reais confirmados

Recapitulando a regra de `ARCHITECTURE.md`: workstreams que só dependem de tipo (já fixado em `stages.py`/
schema desde a Fase 1/2) paralelizam limpo; workstreams que dependem de *implementação* concreta um do
outro não.

| Par de workstreams | Tipo de dependência | Paraleliza limpo? |
|---|---|---|
| Rectify → tipo `FramePair` (de Capture) | só tipo (schema, Fase 1) | Sim |
| Detect → tipo `RectifiedFrame` (de Rectify) | só tipo | Sim, **exceto** o passe 1 do modelo de fundo (ver abaixo) |
| Track → tipo `FrameDetections` (de Detect) | só tipo | Sim |
| Fuse → tipo `Track` (de Track) + `Calibration` | só tipo | Sim — Fuse pode ser escrito/testado contra um `Track` fake sem esperar o Track real |
| **Detect → implementação de Capture+Rectify** | **implementação concreta**, por causa do passe 1 (seção 3.4) | **Não** — único furo real |

Confirmação da análise pedida: Fuse **não** precisa conhecer nada do formato de saída do Track além do que
já está em `stages.py`/schema — a suposição de que "provavelmente está tudo bem porque é tipado" se
confirma pra esse par. O mesmo vale pra Rectify vs. Capture e Track vs. Detect.

O único furo real é Detect vs. Capture/Rectify, e é estrutural (não incidental): nasce da decisão de duas
passadas da seção 3, que exige que o `setup()` do detector monte sua própria mini Capture+Rectify. Mitigação
confirmada e detalhada:

- Durante o desenvolvimento paralelo, o workstream de Detect implementa e testa `setup()` contra um
  **fake** de Capture+Rectify local ao seu próprio conjunto de testes (`tests/stages/detect/fakes.py`) —
  um `capture_factory.open_single(role)` fake que devolve uma sequência conhecida de frames crus em memória,
  mais um `rectifier_factory.build()` fake (identidade ou warp trivial), sem depender de arquivo de vídeo
  nem das classes reais `DualVideoFileCapture`/`CpuPerspectiveRectifier`.
- Isso mantém os 5 workstreams paralelizáveis até o nível "testes unitários do meu próprio estágio
  passam, com fakes onde necessário" — que é exatamente o ponto de handoff seguro descrito na seção 8.
- O acoplamento real só **precisa** ser resolvido no passo de integração sequencial no final da fase
  (quando o `setup()` de Detect passa a instanciar as classes reais dos outros dois workstreams) — nesse
  ponto os 3 workstreams (Capture, Rectify, Detect) já precisam estar mergeados antes de rodar o
  golden-file test.

Isolamento de arquivo: cada workstream escreve só na sua própria árvore (`src/stages/<estagio>/*` +
`tests/stages/<estagio>/*`) — nenhum workstream edita arquivo de outro, então usar 1 worktree git por
workstream (conforme protocolo de `ARCHITECTURE.md`) não gera conflito de merge mecânico; o único risco é
semântico (o furo do Detect acima), não de arquivo.

---

## 7. Comandos de verificação e critério de "passou"

Por estágio, durante desenvolvimento paralelo (rodar dentro de cada worktree):
```
pytest tests/stages/capture -v
pytest tests/stages/rectify -v
pytest tests/stages/detect -v      # contra fakes de Capture/Rectify, ver seção 6
pytest tests/stages/track -v
pytest tests/stages/fuse -v        # contra Track fake, ver seção 6
ruff check src/stages/<estagio>
mypy src/stages/<estagio>
```

Depois do merge de todos os worktrees (integração sequencial):
```
pytest tests/test_golden_pipeline.py -v         # golden-file + teste de memória limitada
pytest tests/stages -v                          # suite completa dos 5 estágios, agora sem fakes onde antes havia
ruff check src/stages
mypy src/stages
```

**Critério de "passou" pra fase inteira**:
1. Todos os testes unitários por estágio verdes (com ou sem fakes, dependendo do momento).
2. `test_golden_pipeline.py` verde: `AnalysisResult` produzido pela pipeline nova bate com
   `tests/fixtures/golden/expected_result.json` dentro das tolerâncias da seção 5.3.
3. `test_memory_bounded` verde (seção 5.4).
4. Teste de regressão específico pras fórmulas corrigidas (`test_speed_formula`, `test_px_per_cm_per_axis`)
   verde — validando explicitamente que a fórmula de velocidade e a razão px/cm por eixo batem com os
   valores calculados manualmente pra fixture (não só que o golden file bate — isso pega o caso de um bug
   ter entrado igual nos dois lados).
5. `ruff check` e `mypy` limpos em `src/stages/**`.
6. `processVideoModule.py`, `perspectiveModule.py`, `backgroundRemoveModule.py`, `routeAnalizer.py`,
   `getData.py` removidos do repo (ou marcados obsoletos se uma remoção completa quebrar algo da GUI ainda
   não migrado — a GUI só migra na Fase 4, então pode ser necessário manter um shim temporário chamando a
   pipeline nova a partir do botão "Processar vídeo" existente; decisão a confirmar durante a execução,
   não bloqueante pra esta fase em si).

---

## 8. Handoff — granularidade de checkpoint

Esta é a fase com maior risco de estouro de orçamento de contexto/token da rearquitetura inteira (mexe em
5+ arquivos-fonte simultaneamente, mais os 2 plugins de metadata). Granularidade de checkpoint:

- **Checkpoint seguro por estágio** (handoff individual): `docs/handoffs/fase3-capture-handoff.md`,
  `fase3-rectify-handoff.md`, `fase3-detect-handoff.md`, `fase3-track-handoff.md`, `fase3-fuse-handoff.md`
  — cada um escrito assim que os testes unitários **daquele estágio** passarem (com fakes onde aplicável,
  seção 6), mesmo que nenhum outro estágio tenha começado. Este é um ponto de handoff seguro: quem retomar
  pode confiar que aquele estágio isolado funciona, sem precisar re-explorar o raciocínio.
- Cada handoff de estágio deve registrar explicitamente, na seção "O que falta": se `setup()`/integração
  ainda depende de um fake (caso do Detect) ou já está pronto pra receber a implementação real.
- **Checkpoint de integração** (separado, mais crítico): `docs/handoffs/fase3-integracao-handoff.md`,
  escrito só depois que os 5 worktrees forem mergeados e o golden-file test for **de fato executado** (não
  "deveria passar" — rodado e com resultado real registrado). Enquanto esse teste não tiver rodado com
  sucesso, o handoff de integração **deve dizer explicitamente**, em destaque:
  > "Integração não tentada / tentada mas falhando — não assumir que os estágios compõem corretamente até
  > o golden-file test passar. Não prosseguir para a Fase 4 a partir deste ponto."
- Se uma sessão precisar encerrar no meio da integração (ex. depois de mergear 3 dos 5 worktrees mas antes
  de rodar o golden-file), o handoff de integração deve nomear exatamente quais worktrees já foram
  mergeados, qual o próximo a mergear, e qualquer erro de composição já observado (ex. incompatibilidade de
  tipo descoberta ao ligar dois estágios reais pela primeira vez) — isso é precisamente o tipo de
  informação que se perde sem handoff explícito e que forçaria uma sessão nova a re-explorar do zero.
- `docs/handoffs/PROGRESS.md` (arquivo mestre) só deve marcar "Fase 3: concluída" depois que o critério da
  seção 7 inteiro estiver satisfeito — nunca marcar concluído com base em "estágios individuais passam",
  já que isso especificamente é o que este documento identifica como o risco central da fase (estágios
  isolados corretos não implicam composição correta, dado o acoplamento real da seção 3.4/6).
