# Oportunidades de extração de metadados

> **Documento de pesquisa, não plano de implementação.** Levanta o que *mais* pode ser extraído
> das entradas que o sistema **já** tem (2 vídeos sincronizados + perfil de configuração), sem
> propor hardware novo no corpo principal. Cada proposta diz de que estágio/campo do schema ela
> depende, se cabe no schema atual ou exige mudança, e qual a forma de implementação (plugin puro
> vs. cirurgia de estágio).
>
> Base de leitura: `ARCHITECTURE.md`, `01-visao-produto.md`, `02-entrada-de-dados.md`,
> `03-processamento.md`, `src/core/schema/*`, `src/stages/*`, `plugins/*`,
> `docs/PLUGIN_CONTRACT.md`, `docs/handoffs/PROGRESS.md`,
> `docs/handoffs/fase6-tracker-spike-handoff.md`. Estado do código: rearquitetura das Fases 0→6
> concluída (Fase 5 com packaging CUDA pendente).
>
> Princípio que restringe tudo abaixo: **sem IA no núcleo**. A extração produz dado estruturado
> que alimenta IA/estatística *externa*. Nenhuma proposta aqui embute modelo treinado.

---

## 1. O que o sistema realmente tem hoje

### 1.1 Entradas

| Entrada | Origem | Observações |
|---|---|---|
| Vídeo do topo | `Profile.top_video_path` | BGR, resolução livre |
| Vídeo lateral | `Profile.side_video_path` | idem; **deve** ter o mesmo FPS (pré-condição documentada, **nunca verificada em código**) |
| `box_cm: Point3D` | perfil | dimensões físicas da caixa |
| 4 pontos de perspectiva por câmera | `PerspectiveUi` | definem homografia + ROI |
| 4 pontos de borda por câmera | `BorderUi` | definem `BorderRegion` |
| `BoxOrientationConfig` | `OrientationUi` (Fase 4) | face vista + vértice por ponto clicado, por câmera |

### 1.2 O que cada estágio computa, e o que sobrevive

Este é o mapa que sustenta metade das propostas deste documento — a coluna "sobrevive" é curta.

| Estágio | Computa | Sobrevive para o estágio seguinte |
|---|---|---|
| **Capture** (`src/stages/capture/plugin.py`) | abre os 2 vídeos, `fps` (só do topo, truncado com `int()`), `dimensions()` (w,h por câmera), pares de frames BGR em lockstep | `FramePair(frame_index, top, side)` e `fps`. **Descartado**: fps da câmera lateral, contagem de frames de cada vídeo, duração, `CAP_PROP_POS_MSEC`, o fato de um vídeo ser mais curto que o outro (o generator só para, em silêncio) |
| **Rectify** (`src/stages/rectify/plugin.py`) | `warpPerspective` + `cvtColor(BGR2GRAY)` | `RectifiedFrame.image` **em escala de cinza**. **Descartado**: toda a informação de cor, e tudo fora do ROI |
| **Detect** (`src/stages/detect/plugin.py`) | modelo de fundo (`np.max` de amostras), `absdiff`, duplo threshold 80/127, `findContours` → **lista completa de contornos**, maior contorno, `moments`, centróide, `contourArea` | `FrameDetections` com **no máximo 1** `Detection` contendo `centroid` + `area`. **Descartado**: todos os contornos que não são o maior, `bbox` (campo existe no schema e nunca é preenchido), `confidence` (fixo em `1.0`), a máscara binária, a intensidade dos pixels do alvo |
| **Track** (`src/stages/track/plugin.py`) | escolhe a detecção de maior área | `Track.points: dict[int, Point2D]`. **Descartado aqui**: `area`, `bbox`, `confidence` — `Track` não tem onde guardá-los. **Esta é a maior fronteira de perda de dado do pipeline** |
| **Fuse** (`src/stages/fuse/plugin.py`) | `axis_mapping()`, `px_per_cm` por eixo, interseção dos índices de frame das duas views, conversão px→cm | `Route3D` (cm) + `Calibration`. **Descartado**: a leitura da câmera perdedora no eixo que **as duas** observam (a política "TOP vence" joga fora uma medida independente do mesmo eixo), e os frames em que só uma view detectou |
| **Metadata** | `speed`, `border` (+ terceiros) | `Metric`s em `AnalysisResult.metrics` |
| **Export** | PNG da rota, PDF | arquivos |

### 1.3 O que é persistido

`AnalysisResult` = `schema_version` + `profile` + `calibration` + `routes` + `metrics` +
`border_region`. **Não existe** no resultado persistido: `Track` (2D por view), `FrameDetections`,
contagem total de frames do vídeo, resolução, caminho/hash dos vídeos, nome/versão/parâmetros dos
plugins que rodaram, timestamp do run.

Consequência prática: o `pdf-report` rotula `len(routes[0].points)` como "Quantidade de frames" —
que na verdade é o número de frames **com reconstrução 3D bem-sucedida**, não o número de frames do
vídeo. Sem o denominador, não existe hoje como responder "que fração do experimento o sistema
conseguiu medir?".

### 1.4 O que o contrato de plugin permite sem tocar em nada

- `Metric.value` aceita `str | int | float | bool | None | list | dict` (`JsonSafeValue`). Séries
  temporais por frame já são representáveis — o plugin `speed` faz exatamente isso
  (`dict[str(frame_index), float]`). **Nenhuma proposta que produza série temporal precisa de
  mudança de schema por causa do formato.**
- Ordenação por `[ordering] before/after/priority` permite plugins que consomem métricas de outros
  (padrão do `fish-body-fat`).
- Descoberta varre **um nível** abaixo de cada raiz de busca; `plugins/` na raiz do repo é varrida
  pela orquestração CPU (`src/stages/orchestration.py::_run_metadata_plugins`).

**Duas restrições reais a considerar em qualquer proposta:**

1. Construtor de plugin precisa ser **zero-arg** (`PluginRegistry.instantiate()`).
2. `run_cpu_analysis` chama **apenas `plugin.run(ctx)`** — nunca `setup(pctx)`. Ou seja, no caminho
   real de análise (CLI/GUI), `ctx.request.overrides` **não chega ao plugin**. Configuração de
   usuário hoje só chega por variável de ambiente (é o que o `fish-body-fat` faz como fallback).
   Qualquer proposta abaixo que precise de parâmetro do pesquisador esbarra nisso — vale tratar
   como item transversal (ver §8, T-1).

---

## 2. Grupo A — Cinemática latente na `Route3D` (plugins puros, risco baixo)

Tudo neste grupo lê `AnalysisResult.routes` + `calibration.fps` e escreve `Metric`s. **Nenhuma
mudança de schema, nenhuma mudança de estágio.** É o grupo com melhor razão valor/risco.

Regra comum a todos: a rota tem **buracos** (`dict[int, Point3D]` sem índices contíguos). Toda
derivada só pode ser calculada entre índices **consecutivos** (`idx+1 == prev_idx+1`); o plugin
`speed` atual ignora isso (usa `zip(indices, indices[1:])` sobre índices ordenados, então trata um
salto de 13 frames como se fosse 1 frame — herda o problema descrito em `03-processamento.md` §5).
Qualquer plugin novo deste grupo deve tratar buracos explicitamente, e **corrigir isso no `speed`
é um achado colateral desta análise**.

### A-1. Aceleração e jerk

- **O que mede / por quê**: segunda e terceira derivadas da posição. `README.md` lista
  "Aceleração (positiva ou negativa)" como objetivo declarado ainda **não alcançado**. Em ensaio
  com inseticida, o perfil de aceleração distingue "voo normal" de "movimento errático/tremor"
  melhor que velocidade média, que é o único indicador hoje.
- **Dados / schema**: `Route3D.points` + `Calibration.fps`. **Cabe no schema como está** — série
  como `dict[str, float]`, escalares como `float`.
- **Implementação**: plugin `metadata` novo (ex. `plugins/kinematics/`), `[ordering] after =
  ["speed"]` para reusar a série `speed` já publicada (acesso defensivo). Métricas sugeridas:
  `acceleration` (série, cm/s²), `jerk` (série, cm/s³), `acceleration_max`, `deceleration_max`,
  `acceleration_rms`.
- **Esforço / risco**: baixo / baixo. ~1 arquivo + testes. Não toca no esqueleto congelado.

### A-2. Direção, ângulo de virada e detecção de curvas fechadas

- **O que mede / por quê**: vetor de deslocamento normalizado por frame (direção — objetivo
  declarado no `README.md`), ângulo entre deslocamentos consecutivos, e contagem de "curvas
  fechadas" (ângulo acima de um limiar) — também objetivo declarado. Distribuição de ângulos de
  virada é o descritor clássico para separar busca local de deslocamento dirigido.
- **Dados / schema**: `Route3D.points`. Cabe como está.
- **Implementação**: mesmo plugin de A-1 ou irmão. Métricas: `heading` (série de vetores como
  `list[float]` de 3 componentes por frame, ou 2 ângulos esféricos), `turn_angle` (série, graus),
  `turn_angle_histogram` (`dict` bin→contagem), `sharp_turn_count`, `sharp_turn_rate` (por minuto).
  Limiar de "curva fechada" precisa ser configurável → esbarra em T-1 (§8); default documentado
  resolve por ora.
- **Esforço / risco**: baixo / baixo.

### A-3. Tortuosidade, índice de retidão e MSD

- **O que mede / por quê**: `straightness = deslocamento_líquido / comprimento_do_caminho` (0 = puro
  giro em torno de si, 1 = linha reta), sinuosidade, e **deslocamento quadrático médio (MSD)** em
  função do intervalo temporal. O expoente do MSD separa movimento difusivo (busca aleatória) de
  balístico (fuga dirigida) — é um dos indicadores mais informativos que uma trajetória oferece e
  não custa nada extra: é aritmética sobre pontos que já existem.
- **Dados / schema**: `Route3D.points`. Cabe como está.
- **Implementação**: plugin `metadata`. Métricas: `path_length` (já existe como `distance_total`),
  `net_displacement`, `straightness_index`, `msd_curve` (`dict` lag→valor), `msd_exponent`.
- **Esforço / risco**: baixo / baixo. Só cuidado numérico com buracos (MSD por lag deve usar apenas
  pares de índices realmente separados por aquele lag).

### A-4. Segmentação repouso × atividade (bouts) e latência ao primeiro movimento

- **O que mede / por quê**: classifica cada frame em "parado" ou "ativo" por limiar de velocidade
  com histerese, e deriva: nº de bouts ativos, duração média/mediana de bout, tempo total parado,
  fração de tempo ativo, e **latência ao primeiro movimento** (frames até a primeira velocidade
  acima do limiar). Latência e tempo total parado são exatamente os endpoints usados em ensaios de
  knockdown por inseticida — hoje o sistema só entrega "tempo em borda", que confunde "pousado" com
  "andando na parede".
- **Dados / schema**: série `speed` (do plugin `speed`) ou `Route3D` direto. Cabe como está.
- **Implementação**: plugin `metadata` com `after = ["speed"]`. Métricas: `rest_frames`,
  `active_frames`, `active_fraction`, `bout_count`, `bout_duration_mean_s`,
  `time_to_first_movement_s`, `rest_bouts` (`list` de `[inicio, fim]`).
- **Esforço / risco**: baixo / baixo. **Ressalva honesta**: `03-processamento.md` §5 registra que a
  remoção de fundo depende de movimento — um inseto totalmente imóvel **não é detectado**, virando
  buraco na rota em vez de "velocidade zero". Então "tempo parado" hoje é indistinguível de "tempo
  sem detecção". Esta proposta só é confiável combinada com **B-5/C-1** (taxa de oclusão), e essa
  interdependência é ela própria um resultado útil de reportar.

### A-5. Ocupação volumétrica 3D e zonas genéricas (generaliza a borda)

- **O que mede / por quê**: discretiza o volume da caixa em voxels e conta o tempo em cada um.
  Deriva: mapa de ocupação, entropia espacial (quão exploratório é o animal), voxel modal
  ("lugar preferido"), nº de voxels visitados (cobertura), **frequência de revisitação** e tempo
  até a primeira visita por região. Hoje o único conceito espacial é a `BorderRegion` — um
  retângulo por eixo, contado por eixo independente. Ocupação volumétrica generaliza isso para
  qualquer espécie e qualquer pergunta ("prefere o fundo?", "evita o canto onde está o composto?"),
  o que é a direção multi-espécie declarada na visão de produto.
- **Dados / schema**: `Route3D.points` + `Calibration.box_cm` (para normalizar a grade). Cabe como
  está: o mapa vai como `dict` (`"i,j,k" -> contagem`) dentro de um `Metric`.
- **Implementação**: plugin `metadata`. Métricas: `occupancy_grid`, `occupancy_entropy`,
  `voxels_visited`, `coverage_fraction`, `revisit_rate`, `zone_dwell_time` (se zonas nomeadas forem
  configuráveis). Resolução da grade precisa ser parâmetro → T-1.
- **Esforço / risco**: baixo / baixo. Cuidado: com o sinal negativo que `axis_mapping()` pode
  aplicar, as coordenadas em cm **não são garantidamente positivas nem ancoradas em zero** — a
  grade deve ser construída a partir de min/max observados ou de `border_region.bounds`, não
  assumindo `[0, box_cm]`. (Esta é uma pegadinha real do código atual, não hipotética.)

### A-6. Lateralidade / assimetria de movimento

- **O que mede / por quê**: viés de virada para um lado (razão curvas-à-esquerda/à-direita,
  estatística circular sobre a distribuição de ângulos com sinal). Assimetria motora é indicador
  reconhecido de efeito neurotóxico e é literalmente grátis a partir de A-2.
- **Dados / schema**: ângulos com sinal derivados de `Route3D` (projeção no plano horizontal
  x–z, com y = altura pela convenção fixada em `orientation.py`). Cabe como está.
- **Implementação**: extensão do plugin de A-2. Métricas: `turn_bias_index`,
  `left_turn_count`/`right_turn_count`, `circular_mean_turn`.
- **Esforço / risco**: baixo / baixo.

### A-7. Perfil temporal / habituação (métricas por janela)

- **O que mede / por quê**: todas as métricas acima recalculadas em janelas (ex. por minuto), mais
  a tendência (inclinação da regressão). Captura o que uma média sobre o vídeo inteiro apaga:
  declínio progressivo de atividade (efeito do composto agindo ao longo do tempo), habituação ao
  ambiente nos primeiros minutos, ou recuperação. Para um experimento de exposição a agrotóxico,
  **a curva importa mais que a média** — e hoje só a média existe.
- **Dados / schema**: `Route3D` + `fps`. Cabe como está (série de janelas como `list[dict]`).
- **Implementação**: plugin `metadata` que roda por último (`priority` baixa) e recalcula um
  subconjunto de métricas por janela. Métricas: `windowed_stats`, `activity_trend_slope`.
- **Esforço / risco**: baixo / baixo. Risco de duplicar lógica dos outros plugins — mitigação:
  extrair as funções puras de cinemática para um módulo compartilhado dentro do próprio pacote de
  plugins (permitido: plugin multi-arquivo é um pacote Python normal, ver `PLUGIN_CONTRACT.md` §4).

---

## 3. Grupo B — Dado que o Detect já computa e o pipeline joga fora

Este grupo é onde está o dado "de graça mas inacessível": o detector já tem em mãos, e o schema
já modela em parte, mas nada disso chega ao `AnalysisResult`. Todos exigem **mudança de estágio
e/ou de schema** — risco médio, não plugin puro.

### B-1. Série temporal de área do blob

- **O que mede / por quê**: `Detection.area` **já é computada e preenchida hoje**
  (`cv2.contourArea` do maior contorno) e morre no `SingleEntityTracker`. A área ao longo do tempo
  é proxy de: tamanho corporal aparente, postura (asas abertas/fechadas), e — na câmera de topo —
  **distância à câmera**, ou seja, um sinal parcialmente redundante com a altura medida pela
  lateral (útil como verificação cruzada, ver D-1). Para o caso "peixe" da visão de longo prazo,
  área aparente é o insumo mais direto de qualquer estimativa de biomassa/condição corporal — o
  plugin `fish-body-fat` de exemplo hoje é obrigado a inventar uma fórmula sem nenhuma medida de
  tamanho porque **essa medida não sobrevive ao pipeline**, embora exista.
- **Dados / schema**: `Detection.area` — **já existe**. O que falta é transporte: `Track.points` é
  `dict[int, Point2D]` e não tem onde guardar atributos por frame. Precisa de **uma** de:
  (a) `Track.attributes: dict[int, dict[str, float]]` (aditivo, opcional, retrocompatível);
  (b) `AnalysisResult.tracks: list[Track]` persistido (resolve também E-* e D-3);
  (c) o orquestrador acumula um resumo e injeta como `Metric` (hack: mistura papéis, mas não muda
  schema nenhum).
- **Implementação**: mudança no `Track`/`Tracker` (schema + os 3 trackers existentes) **ou** um
  atalho via orquestração. Depois disso, o consumo é plugin `metadata` puro.
- **Esforço / risco**: médio / médio — mexe em schema (`SCHEMA_VERSION` pode ter que subir) e nos
  trackers. É o pré-requisito compartilhado de B-2, B-3 e boa parte do Grupo F, o que muda o
  cálculo custo/benefício: **uma mudança destrava quatro famílias de métricas**.

### B-2. Bounding box, razão de aspecto e orientação corporal

- **O que mede / por quê**: `Detection.bbox` **existe no schema e nunca é preenchido**. Preenchê-lo
  custa uma linha (`cv2.boundingRect(max_contour)`). Com bbox vem razão de aspecto (proxy de
  postura/alongamento) e, com `cv2.minAreaRect`/`fitEllipse` sobre o **mesmo contorno já
  calculado**, o **ângulo do eixo principal do corpo** — isto é, "Orientação do inseto", objetivo
  declarado no `README.md` e nunca atingido. Comparar ângulo corporal com direção de deslocamento
  (A-2) distingue "andando para frente" de "sendo arrastado/recuando", e detecta rotação no lugar.
- **Dados / schema**: `bbox` já existe; o **ângulo** não tem campo (`BBox` é alinhada aos eixos).
  Precisa de `Detection.orientation_deg: float | None` (aditivo) ou de um campo genérico de
  atributos. Mais o transporte de B-1.
- **Implementação**: mudança pequena no `BackgroundSubtractionDetector` (e no `CudaMOG2Detector`,
  que replica o passo final) + transporte + plugin `metadata` de consumo.
- **Esforço / risco**: médio / médio-baixo. A mudança no Detect é aditiva e não altera o centróide
  → o teste golden-file (`tests/test_golden_pipeline.py`) só quebra na comparação de JSON, não na
  matemática; regenerar o golden é esperado e controlado.

### B-3. Confiança de detecção real (hoje é constante `1.0`)

- **O que mede / por quê**: `Detection.confidence` existe, é sempre `1.0`, e portanto não informa
  nada. Sinais de confiança computáveis a partir do que o detector já tem, **sem IA**:
  (i) razão entre a área do maior contorno e a soma das áreas de todos os contornos (dominância —
  cai quando reflexo/sombra competem com o inseto); (ii) número de contornos acima da área mínima;
  (iii) intensidade média do `absdiff` dentro do contorno (contraste do alvo contra o fundo);
  (iv) desvio da área em relação à mediana móvel (um blob que triplica de tamanho num frame é o
  falso positivo de "batida de asa + ruído" descrito em `03-processamento.md` §5).
  Isso ataca diretamente o problema **não resolvido** de interferência do vidro: em vez de "o
  sistema errou em algum lugar", o output passa a dizer **onde** e **quanto** confiar.
- **Dados / schema**: `confidence` já existe no `Detection`; os insumos são todos internos ao
  Detect (contornos e máscara, hoje descartados). Transporte: mesmo problema de B-1.
- **Implementação**: mudança no Detect (calcular) + transporte + plugin `metadata` (agregar:
  `confidence_mean`, `low_confidence_frames`, `confidence_series`).
- **Esforço / risco**: médio / médio. Definir a fórmula de confiança é decisão de projeto (não há
  resposta única); recomenda-se publicar os componentes crus separadamente em vez de um número
  mágico agregado.

### B-4. Emitir N detecções por frame (destrava multi-animal de verdade)

- **O que mede / por quê**: o detector descarta **todos** os contornos exceto o maior. O schema
  (`FrameDetections.detections: list[Detection]`) e a interface `Tracker` já foram desenhados para
  N entidades, e a Fase 6 provou que os trackers multi-entidade funcionam — **mas com detecções
  sintéticas**, porque o detector real nunca emite mais de uma. Ou seja: o gargalo do multi-animal
  hoje **não é o tracker, é o Detect**. Emitir todos os contornos acima de uma área mínima é uma
  mudança de poucas linhas e, além do multi-animal, dá de brinde a contagem de blobs espúrios por
  frame (insumo de B-3) e a possibilidade de rejeitar o reflexo como entidade separada.
- **Dados / schema**: **nenhuma mudança de schema** — `FrameDetections` já aceita lista. Muda só o
  comportamento do detector (e é preciso um limiar de área mínima, hoje inexistente).
- **Implementação**: mudança no `BackgroundSubtractionDetector` (+ CUDA), com o comportamento de
  "1 detecção" preservado por default para não quebrar o golden. O `SingleEntityTracker` já lida
  com N (pega o de maior área).
- **Esforço / risco**: baixo-médio / médio — é o estágio mais sensível do pipeline (guardado pelo
  golden-file). Mas é o único caminho para o multi-animal sair do spike.

### B-5. Taxa de oclusão e análise de lacunas como métrica de qualidade do próprio output

- **O que mede / por quê**: fração de frames sem detecção (por view e após fusão), maior lacuna
  consecutiva, distribuição de tamanhos de lacuna, nº de segmentos contíguos. `03-processamento.md`
  §5 registra lacunas de até 13 frames consecutivos por reflexo no vidro — **hoje esse número não
  aparece em lugar nenhum do output**. É a métrica que qualifica todas as outras: uma velocidade
  média calculada sobre 40% dos frames vale menos que a mesma média sobre 98%, e nada no
  `AnalysisResult` permite distinguir os dois casos.
- **Dados / schema**: parcialmente disponível — buracos em `Route3D.points` são visíveis, mas
  **falta o denominador**: `AnalysisResult` não guarda o total de frames processados, e nem os
  totais por view. Precisa de um campo novo (ver C-1: um único acréscimo de "estatísticas do run"
  resolve C-1, B-5 e D-3 juntos).
- **Implementação**: acréscimo de schema mínimo (`frame_count`, contagem de detecções por view) +
  plugin `metadata` que deriva as taxas. Alternativa sem schema: o orquestrador publica os
  contadores como `Metric`s (`producer="pipeline"`) — funciona, mas mistura papéis.
- **Esforço / risco**: baixo-médio / baixo. **Melhor relação valor/esforço de todo o Grupo B.**

---

## 4. Grupo C — Qualidade e proveniência do run

Metadados *sobre a medição*, não sobre o animal. Baratos, e são o que torna o output publicável
(reprodutibilidade) — relevante para um trabalho acadêmico e para a ambição de plataforma.

### C-1. Estatísticas de captura: contagem de frames, FPS real, divergência entre câmeras

- **O que mede / por quê**: hoje o `Capture` lê `fps` **só do topo**, com `int()` (um vídeo a
  29.97 fps vira 29 — erro sistemático de ~3% em **toda** velocidade derivada), **ignora** o fps da
  lateral e **não verifica** a pré-condição documentada de que ambos sejam iguais. E quando um
  vídeo é mais curto, o generator simplesmente para, sem registrar quantos frames do outro vídeo
  foram desprezados (`03-processamento.md` §5 conhece o comportamento; o output não o reporta).
  Publicar: `frame_count` processado, frames totais de cada vídeo, fps de cada câmera, resolução de
  cada câmera, duração, e um **aviso explícito** quando os fps divergem ou os comprimentos diferem
  além de uma tolerância.
- **Dados / schema**: tudo já disponível via `cv2.CAP_PROP_*` no Capture, hoje não lido (exceto
  w/h em `dimensions()`). Precisa de campo novo: sugerido `AnalysisResult.run_stats` ou
  `Calibration.capture` (aditivo, opcional). `Calibration.fps` deveria virar `float` real
  (já é `float` no schema — a truncagem acontece no `int()` do Capture, ou seja, é **bug de
  estágio, não limitação de schema**).
- **Implementação**: mudança pequena no Capture + campo de schema + exibição no PDF.
- **Esforço / risco**: baixo / baixo. Corrige de quebra um erro de precisão que contamina todas as
  métricas de velocidade.

### C-2. Estabilidade de iluminação e do modelo de fundo

- **O que mede / por quê**: média e desvio de intensidade por frame (ou amostrado a cada N frames),
  e deriva do fundo ao longo do vídeo — isto é, **quanto o pressuposto do algoritmo foi violado**.
  `02-entrada-de-dados.md` exige explicitamente "a luz não pode variar durante o experimento", e
  `CLAUDE.md` lista interferência do vidro/reflexo como problema conhecido não resolvido. Uma
  métrica de deriva de iluminação transforma "o resultado ficou ruim, não sei por quê" em
  "a iluminação variou 22% a partir do minuto 4". Também dá um sinal indireto de reflexo: picos de
  intensidade máxima localizados que aparecem e somem.
- **Dados / schema**: os frames retificados já passam pelo Detect frame a frame; `np.mean`/`np.std`
  por frame é custo desprezível. Nenhum campo apropriado hoje → mesma solução de C-1/B-5.
- **Implementação**: computar no Detect (ou num detector "wrapper" de diagnóstico) e publicar como
  série. Alternativa **totalmente plugin, sem tocar no pipeline**: um plugin `metadata` que reabre
  o vídeo por conta própria e amostra frames — mais lento e duplica leitura, mas risco zero para o
  esqueleto. Vale considerar como primeira versão.
- **Esforço / risco**: baixo (versão plugin que reabre o vídeo) a médio (versão integrada) / baixo.

### C-3. Proveniência e reprodutibilidade do run

- **O que mede / por quê**: qual detector/tracker/rectifier rodou, com quais parâmetros
  (`frame_block=500`, thresholds 80/127, `max_distance`, `min_hits`…), versões dos plugins, versão
  do OpenCV/numpy, hash dos arquivos de vídeo, timestamp, se rodou em GPU ou CPU. Sem isso, dois
  `AnalysisResult` com números diferentes são inexplicáveis — e o `PROGRESS.md` já registra que
  golden files divergem entre versões do OpenCV, o que prova que a versão da biblioteca **é** dado
  relevante. Além disso, `RunResult.plugin_failures` (que sabe quais plugins falharam) **não é
  persistido** no `AnalysisResult`: um resultado a que faltam métricas é indistinguível de um
  resultado onde o plugin nem existia.
- **Dados / schema**: nada existe. Precisa de `AnalysisResult.provenance` (aditivo) ou registro de
  falhas persistido.
- **Implementação**: preenchido pelo orquestrador/`Pipeline`, não por plugin.
- **Esforço / risco**: baixo-médio / baixo. É acréscimo puro; nenhum consumidor atual quebra.

---

## 5. Grupo D — Metadados de fusão (cross-view)

O ponto mais subutilizado do sistema: **duas câmeras observam um eixo em comum e o sistema descarta
uma das duas medidas**. `axis_mapping()` resolve conflito com "TOP vence" e o `Fusion` nunca olha
para a leitura perdedora. Essa leitura descartada é uma **medida independente da mesma grandeza** —
a matéria-prima de uma estimativa de erro.

### D-1. Resíduo cross-view do eixo compartilhado (estimativa de erro da reconstrução 3D)

- **O que mede / por quê**: para o eixo que ambas as câmeras observam, calcular
  `|valor_top(t) − valor_side(t)|` em cm, por frame. Deriva: resíduo médio, RMS, p95, e a série
  temporal. É a **única** métrica de erro que o sistema pode produzir sem ground truth externo, e
  responde a perguntas que hoje não têm resposta: os pontos de perspectiva foram clicados
  corretamente? A `BoxOrientationConfig` está certa (um resíduo enorme e sistemático indica
  orientação/vértices trocados)? A distorção de perspectiva do mundo real — problema explicitamente
  não resolvido em `CLAUDE.md` — está degradando a medição, e quanto?
- **Dados / schema**: tudo já existe **dentro** do `Fusion.fuse()` no momento do cálculo — os dois
  `Track`s e o `px_per_cm` estão em mãos, e o código já escolhe uma fonte e ignora a outra. Nenhum
  dado novo precisa ser capturado; falta apenas **não jogar fora**. Publicação: como `Metric`
  (série + escalares) — cabe no schema como está, se o `Fusion` puder emitir métricas.
- **Implementação**: mudança no `Fuse` (calcular e devolver) + o orquestrador transforma em
  `Metric`. Alternativa mais limpa arquiteturalmente: persistir os `Track`s (B-1 opção b) e deixar
  um plugin `metadata` puro recalcular o resíduo — **duas propostas convergem para a mesma mudança
  de schema**, o que reforça persistir `tracks`.
- **Esforço / risco**: médio-baixo / baixo-médio. O `Fuse` é pequeno e bem testado.

### D-2. Estimativa de desalinhamento temporal entre as câmeras

- **O que mede / por quê**: correlação cruzada, em função do atraso (lag), entre os dois sinais
  independentes do eixo compartilhado (ou entre os perfis de velocidade 2D de cada view). O lag que
  maximiza a correlação estima **em quantos frames as câmeras estão dessincronizadas**.
  `02-entrada-de-dados.md` exige acionamento simultâneo como pré-condição física, e hoje **nada
  verifica isso** — uma gravação com 5 frames de defasagem produz uma rota 3D silenciosamente
  errada, sem nenhum sinal de alerta. Esta métrica converte uma pré-condição de confiança em um
  número medido.
- **Dados / schema**: os mesmos dois `Track`s do D-1. Cabe como `Metric` escalar
  (`estimated_sync_offset_frames`) + valor de correlação de pico.
- **Implementação**: junto de D-1 (mesmos insumos) ou plugin puro se os tracks forem persistidos.
- **Esforço / risco**: baixo (uma vez que D-1 exista) / baixo. Alto valor diagnóstico.

### D-3. Cobertura de reconstrução por view

- **O que mede / por quê**: o `Fusion` usa a **interseção** dos índices das duas views; frames em
  que só uma câmera detectou são descartados em silêncio. Reportar: frames detectados no topo,
  na lateral, em ambos, e em nenhum. Diz **qual câmera** é o gargalo — informação acionável
  (reposicionar/reiluminar aquela câmera) que hoje se perde.
- **Dados / schema**: disponível no `Fuse`; falta campo (mesmo acréscimo de C-1/B-5).
- **Implementação**: contadores no `Fuse` + `Metric`s.
- **Esforço / risco**: baixo / baixo. Deve ser feito junto com B-5/C-1 — é a mesma família.

---

## 6. Grupo E — Metadados multi-entidade

Habilitados pela interface provada na Fase 6, mas com um **pré-requisito real**: o detector precisa
emitir N detecções (B-4). Sem isso, nada aqui roda sobre dado verdadeiro. Segundo pré-requisito,
para métricas em **3D**: o `Fusion` hoje funde `top_track` com `side_track` assumindo uma entidade
— a correspondência de identidade **entre câmeras** para N entidades é o "candidato 3" que o spike
mediu como plausível mas **não implementou**, e que o handoff aponta como exigindo mudança da
interface `Tracker`. Portanto:

- Métricas E-* em **2D por view** (usando `Track`) são viáveis assim que B-4 + persistência de
  tracks existirem.
- Métricas E-* em **3D** dependem, além disso, de fusão multi-entidade.

### E-1. Distância inter-indivíduo ao longo do tempo

- **O que mede / por quê**: série de distâncias entre pares de entidades, distância mínima, tempo
  abaixo de um limiar de proximidade, distribuição de distância ao vizinho mais próximo. Base de
  toda leitura social (agregação vs. dispersão) — que é o passo natural do projeto para abelhas
  (comportamento social é o interesse biológico central da espécie).
- **Dados / schema**: `Route3D` já é **por entidade** (`entity_id`), então quando houver mais de
  uma rota, este plugin é **100% plugin puro, sem mudança nenhuma de schema**.
- **Implementação**: plugin `metadata` iterando pares de `result.routes`. Pode ser escrito
  **hoje**, com teste em `AnalysisResult` sintético de 2 rotas, e fica dormente até o pipeline
  produzir 2 rotas.
- **Esforço / risco**: baixo / baixo (o risco está nos pré-requisitos, não no plugin).

### E-2. Eventos de aproximação e afastamento

- **O que mede / por quê**: detecta cruzamentos do limiar de proximidade na série de E-1 e
  classifica por sinal da derivada: encontro (aproximação), separação (evitação), com contagem,
  duração e velocidade relativa. Interações são eventos discretos; a série bruta de distância não é
  o que o pesquisador quer ler.
- **Dados / schema**: derivado de E-1. Sem mudança.
- **Implementação**: mesmo plugin de E-1 ou irmão com `after = ["inter-entity-distance"]`.
- **Esforço / risco**: baixo / baixo.

### E-3. Sobreposição espacial e sincronia

- **O que mede / por quê**: interseção dos mapas de ocupação de A-5 entre indivíduos (índice de
  sobreposição de "território"), correlação temporal entre os perfis de velocidade (movimento
  sincronizado), e se um indivíduo tende a seguir a trajetória do outro com atraso (correlação
  cruzada com lag — mesma máquina de D-2 aplicada a outro par de sinais).
- **Dados / schema**: `Route3D` por entidade. Sem mudança.
- **Implementação**: plugin `metadata` reusando as funções de A-5.
- **Esforço / risco**: baixo / baixo.

---

## 7. Grupo F — Extrair mais dos pixels que já são lidos

Aqui o dado existe no frame, o pipeline o toca, e nada é extraído. Exige mudança de estágio.

### F-1. Recorte (crop) do inseto por frame — a "ponte para a IA externa"

- **O que mede / por quê**: salvar um recorte pequeno (ex. 64×64) centrado no centróide, por frame
  ou a cada N frames, mais um índice JSON (frame → arquivo/offset). O `README.md` lista exatamente
  isso no roadmap ("Crop da imagem ao redor do inseto → análise de imagem para mais detalhes").
  É o artefato de maior alavancagem do documento inteiro **precisamente porque o núcleo não faz
  IA**: um dataset de recortes alinhados e rotulados por frame/entidade é o insumo natural de
  qualquer classificador externo (postura, espécie, estado). O sistema entrega o dado estruturado;
  a IA é de outra pessoa. Isso é a filosofia do projeto executada literalmente.
- **Dados / schema**: precisa do centróide (existe) e idealmente da bbox (B-2). O recorte é
  **imagem**, não cabe em `Metric` (`JsonSafeValue` rejeita array) — é um **artefato de export**,
  não uma métrica: arquivo em `workspace.outputs/<perfil>/crops/` + `Metric` apontando o caminho e
  a contagem.
- **Implementação**: mais natural como **novo plugin `exporter`** alimentado por um buffer do
  Detect, ou como um detector-wrapper que grava crops enquanto detecta. Exige decidir onde o frame
  cru fica disponível — o `RectifiedFrame` é **grayscale** (o Rectify já descartou a cor), então
  crops coloridos exigiriam também F-2.
- **Esforço / risco**: médio / médio. Custo de disco não trivial (documentar; amostragem por
  padrão). Nenhuma métrica existente é afetada.

### F-2. Preservar cor: intensidade/contraste do alvo e marcação por cor

- **O que mede / por quê**: o `Rectify` converte para cinza e a cor morre ali. Preservá-la (ou
  manter o frame BGR ao lado do cinza) destrava: (i) intensidade/contraste médio do alvo contra o
  fundo (diagnóstico de sombra e reflexo — problema em aberto); (ii) **identificação de indivíduos
  por marcação colorida**, prática padrão em estudos com abelhas (ponto de tinta no tórax), que é um
  caminho de re-identificação multi-animal **sem IA nenhuma**, alinhado à decisão de núcleo sem IA e
  complementar ao tracking por movimento (que perde identidade em oclusão longa); (iii) para
  espécies coloridas (peixe), qualquer métrica cromática de condição.
- **Dados / schema**: `RectifiedFrame.image` é um único array. Precisaria de campo adicional
  (ex. `RectifiedFrame.color: np.ndarray | None`) — `frames.py` é dataclass em memória, **não é
  schema serializado**, então é a mudança de "schema" mais barata do documento. Custo real é de
  memória/GPU (dois arrays residentes por frame).
- **Implementação**: mudança no Rectify (+ variante CUDA) e no Detect (para amostrar cor dentro do
  contorno). Métricas derivadas viram série; a marcação por cor seria um **detector alternativo**
  (plugin `detector` novo), não uma mudança do existente — o que é exatamente para o que o contrato
  de plugin serve.
- **Esforço / risco**: médio / médio (a marcação por cor como detector novo: médio-alto, mas
  isolada em plugin).

### F-3. Descritores de forma do contorno já calculado

- **O que mede / por quê**: sobre o **mesmo** `max_contour` que já é achado, `cv2` entrega de graça:
  perímetro, solidez (área/área do casco convexo), excentricidade da elipse ajustada, momentos de
  Hu. Solidez cai quando as asas abrem; excentricidade indica alongamento corporal; Hu é invariante
  a rotação/escala e serve de assinatura de forma estável — útil como **âncora de re-identificação
  não-IA** entre frames e potencialmente entre views (uma pista adicional para o candidato 3 do
  spike de tracker).
- **Dados / schema**: contorno já existe no Detect; nenhum campo hoje. Mesmo transporte de B-1/B-2.
- **Implementação**: Detect calcula, transporte carrega, plugin `metadata` agrega.
- **Esforço / risco**: baixo (cálculo) + médio (transporte, compartilhado com B-1/B-2) / médio.

---

## 8. Itens transversais (bloqueadores compartilhados)

Não são metadados, são o que várias propostas acima precisam. Vale tratá-los uma vez.

- **T-1. Configuração de plugin não chega ao plugin no caminho real.**
  `run_cpu_analysis::_run_metadata_plugins` chama só `plugin.run(ctx)` — nunca `setup(pctx)`. Logo
  `ctx.request.overrides` é inacessível no caminho CLI/GUI, e o `fish-body-fat` só funciona por
  variável de ambiente. Quase toda proposta com limiar (A-2 "curva fechada", A-4 velocidade de
  repouso, A-5 resolução de voxel, E-1 proximidade) precisa disso. Ligado à decisão em aberto sobre
  a seção `[config]` no `plugin.toml` (`PROGRESS.md`, Fase 6). **Baixo esforço, destrava muita
  coisa.**
- **T-2. Nenhum `Track`/`FrameDetections` é persistido.** É o pré-requisito compartilhado de B-1,
  B-2, B-3, D-1, D-3, E-* (em 2D) e F-3. Persistir `tracks` num `AnalysisResult` (campo aditivo,
  opcional) é a **única** mudança de schema que converte sete propostas de "mudança de estágio" em
  "plugin puro". Recomendação forte: se apenas uma mudança estrutural for feita, que seja esta.
- **T-3. Não há campo de estatísticas do run.** B-5, C-1, C-2, C-3 e D-3 querem todos o mesmo tipo
  de campo. Um único acréscimo (`run_stats`/`provenance`) atende todos.
- **T-4. Buracos na rota são tratados incorretamente pelo `speed` atual** (salto de N frames tratado
  como 1 frame). Corrigir antes de construir A-1/A-3/A-4 em cima, senão os erros se propagam.

---

## 9. Ideias que exigiriam hardware que o sistema não tem

Fora do escopo principal por definição; listadas para não serem confundidas com as acima.

| Ideia | Hardware necessário | Comentário |
|---|---|---|
| Frequência de batida de asa | Câmera de alta taxa (≥500 fps) | Abelha bate asa a ~200 Hz; a 30 fps o sinal está irremediavelmente sub-amostrado. Nenhum truque de software resolve. |
| Frequência de batida de asa por áudio | Microfone | Barato e surpreendentemente informativo; mas é uma **entrada nova**, com sincronização própria. |
| Reconstrução 3D robusta a oclusão | 3ª câmera | Resolveria estruturalmente as lacunas de detecção que hoje só podem ser *reportadas* (B-5). |
| Profundidade direta / postura 3D | Câmera de profundidade (estéreo/ToF) | Elimina a dependência de duas câmeras ortogonais; mudaria o estágio Fuse inteiro. |
| Comportamento no escuro / ciclo noturno | Iluminação IR + câmera sem filtro IR | Compatível com a subtração de fundo atual; muda só a iluminação, não o algoritmo. Talvez o *stretch* mais barato da lista. |
| Identificação individual confiável | Câmera de maior resolução + etiquetas/QR no tórax | Torna a re-identificação determinística, sem IA — coerente com a filosofia do projeto. |
| Temperatura corporal | Imageamento térmico | Explicitamente fora de escopo. |

---

## 10. Recomendação: por onde começar

Critério: valor científico × esforço × risco para o esqueleto congelado.

| # | Proposta | Por quê primeiro | Esforço / risco |
|---|---|---|---|
| **1** | **A-1 + A-2 + A-3 + A-4** num único plugin `kinematics` (aceleração, jerk, ângulos de virada, curvas fechadas, tortuosidade, bouts de repouso, latência ao primeiro movimento) | Fecha **quatro objetivos declarados no `README.md` que nunca foram atingidos** (aceleração, direção, curvas fechadas, tempo de repouso decente), sem tocar em uma linha do pipeline. Puro plugin `metadata`, exatamente o ponto de extensão que o produto vende. | baixo / baixo |
| **2** | **C-1 + B-5 + D-3**: estatísticas de captura + taxa de oclusão + cobertura por view (um acréscimo de schema, três famílias de métrica) | Hoje é impossível saber se um resultado é confiável. Isso qualifica **todo** o resto — inclusive corrige a truncagem de FPS (`int()`) que enviesa toda velocidade em até ~3%, e o rótulo enganoso "Quantidade de frames" do PDF. | baixo-médio / baixo |
| **3** | **D-1 + D-2**: resíduo cross-view do eixo compartilhado e estimativa de dessincronização | Usa dado que o `Fuse` **já tem em mãos e descarta**. É a única estimativa de erro possível sem ground truth, e verifica duas pré-condições físicas hoje assumidas por fé (perspectiva/orientação corretas; câmeras sincronizadas). Custo pequeno, valor científico desproporcional. | médio-baixo / baixo-médio |
| **4** | **T-2 + B-1 + B-2 + B-3**: persistir `Track` com atributos por frame, e o Detect passar a preencher `bbox`, ângulo do eixo principal e uma `confidence` real | Uma mudança estrutural destrava sete propostas e converte várias delas em plugin puro daí em diante. Entrega "Orientação do inseto" (objetivo do `README.md`) e a primeira medida de tamanho corporal real — que é o que falta para o caso peixe da visão de longo prazo deixar de ser fórmula-placeholder. | médio / médio |
| **5** | **B-4 + E-1 + E-2**: detector emitindo N detecções + métricas de interação social | Move o multi-animal do spike para o pipeline real. O gargalo é o **Detect**, não o tracker (o spike já provou o tracker). E-1/E-2 são plugins puros e podem ser escritos/testados antes, sobre `AnalysisResult` sintético. | médio / médio-alto (Fuse multi-entidade continua em aberto) |

**Menção honrosa fora do top 5**: **F-1 (crops por frame)** é a proposta de maior alavancagem
estratégica do documento — é literalmente a ponte entre "núcleo sem IA" e "IA externa" que a visão
do projeto descreve. Ficou fora do top 5 só por custo de disco e por depender de B-2; assim que o
item 4 estiver feito, é o candidato natural seguinte.

**Ordem sugerida**: 1 → 2 → 3 → T-1 → 4 → 5 → F-1. Os três primeiros não têm dependência entre si e
poderiam ser paralelizados por workstream, no mesmo padrão das fases anteriores.
