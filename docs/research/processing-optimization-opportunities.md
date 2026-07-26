# Oportunidades de otimização de processamento

> Documento de **pesquisa/planejamento**. Nada aqui foi implementado. Não altera contrato de
> estágio, não propõe mudança de arquitetura — é um inventário do que a pipeline realmente faz
> hoje, com propostas concretas e o custo/risco de cada uma.
>
> Escopo: os estágios de cálculo (Capture → Rectify → Detect → Track → Fuse → Metadata), o
> caminho GPU da Fase 5 e a orquestração (`src/stages/orchestration.py`). Fora de escopo:
> Export, GUI, marketplace.

---

## 1. O que foi medido vs. o que foi inferido

**Honestidade metodológica primeiro.** Isto é essencialmente uma **passada de leitura de
código**, não uma campanha de profiling. Não houve `cProfile`/`py-spy`, não houve execução com
material real (vídeo de caixa com vidro, inseto real, resolução de produção). O que existe:

**Medido de fato** (nesta máquina de dev: Windows 11, 16 threads de CPU, `cv2 5.0.0` com
backend FFMPEG, `numpy 2.5.1`, Python 3.13):

- Cronometragem ad-hoc da pipeline CPU real sobre a fixture da Fase 3
  (`tests/fixtures/videos/main_*.avi`: 320×240, 1200 frames, FFV1 lossless, 30/15 fps),
  instrumentando `run_cpu_analysis` por fase.
- Microbenchmarks das operações OpenCV por-frame em 320×240, 1280×720 e 1920×1080.
- Comparação de custo de extração de centroide com máscara limpa vs. máscara ruidosa.
- Custo de amostragem por `seek` (`CAP_PROP_POS_FRAMES`) vs. leitura sequencial completa.
- Custo de construção dos modelos pydantic por frame.

**Inferido / estimado** (marcado como tal em cada proposta): tudo que envolve resolução ou
duração de produção, comportamento de codec long-GOP (H.264/H.265 — a fixture é FFV1 all-intra),
qualidade de detecção em footage real com vidro, e **absolutamente todo número sobre GPU** — o
caminho CUDA nunca foi executado (ver `docs/handoffs/fase5-backends-gpu-handoff.md`).

**Antes de acreditar em qualquer estimativa de impacto sobre material de produção, rode um
profiling de verdade sobre um vídeo real.** As medições abaixo foram feitas numa fixture
deliberadamente minúscula; ela é ótima como guard-rail de correção (golden-file) e péssima como
proxy de custo.

### 1.1 Escala real contra a qual o sistema é validado hoje

| Parâmetro | Fixture atual (`tests/fixtures/generate_fixture_videos.py`) |
|---|---|
| Resolução | 320×240 |
| Frames | 1200 (top e side) — ~40 s a 30 fps |
| Codec | FFV1 (lossless, all-intra) |
| Conteúdo | 1 blob circular escuro, r=10 px, sobre fundo cinza uniforme |
| Entidades | 1 |

Isso é **cerca de 0,04 megapixel por frame**. Um vídeo de laboratório realista (1080p, 10 min,
30 fps) é ~2,1 MP × 18.000 frames — **~800× mais trabalho de pixel por câmera**. Toda proposta
abaixo está calibrada por esse fator: o que é irrelevante na fixture pode ser dominante em
produção, e vice-versa. Onde a conclusão for "isto não importa em nenhuma escala plausível", o
documento diz isso explicitamente em vez de fabricar um problema.

### 1.2 Números medidos — pipeline completa na fixture

`run_cpu_analysis` decomposto (fixture 320×240, 1200 pares):

| Fase | Tempo | Observação |
|---|---|---|
| `det_top.setup()` + `det_side.setup()` (passe 1) | **0,709 s** | 2 leituras completas + retificação de 100% dos frames |
| Passada pareada (passe 2) | **0,788 s** | 1522 pares/s |
| — decode (dentro do passe 2) | ~0,269 s | |
| — rectify 2 views | 0,306 s | |
| — detect + track 2 views | 0,213 s | |
| **Total (setup + passe 2)** | **~1,50 s** | ~27× tempo real |

Decode isolado de 1 view: 0,200 s (≈6000 fps). Decode+rectify de 1 view: 0,357 s → **rectify
≈0,131 ms/frame** nesta resolução.

**Fato estrutural mais importante desta tabela: ~47% do tempo total está no passe 1**, cuja
única saída é uma imagem de fundo construída a partir de **3 frames** (índices 0, 500, 1000).

### 1.3 Números medidos — custo por operação, por resolução

| Operação | 320×240 | 1280×720 | 1920×1080 |
|---|---|---|---|
| `warpPerspective` (BGR, 3 canais) | 0,080 ms | 0,957 ms | 1,941 ms |
| `warpPerspective` (GRAY, 1 canal) | 0,041 ms | 0,263 ms | 0,820 ms |
| `cvtColor BGR2GRAY` | 0,023 ms | 0,071 ms | 0,600 ms |
| `absdiff` | 0,005 ms | 0,039 ms | 0,488 ms |
| `threshold` ×2 (+absdiff) | 0,012 ms | 0,679 ms | 1,813 ms |
| `MOG2.apply` (CPU, referência) | 0,831 ms | 4,711 ms | 11,511 ms |

Extração do centroide (máscara **limpa**, 1 blob vs. máscara **ruidosa** com 2% de sal-e-pimenta
sintético):

| Abordagem | 320×240 limpa | 320×240 ruidosa | 1920×1080 limpa | 1920×1080 ruidosa |
|---|---|---|---|---|
| `findContours`+`moments` (o que o código faz) | 0,018 ms | 1,874 ms | 0,929 ms | **65,5 ms** |
| `connectedComponentsWithStats` | 0,113 ms | 1,134 ms | 5,054 ms | 19,3 ms |
| `morphologyEx(OPEN 5×5)` + `findContours` | 0,059 ms | 0,064 ms | 2,963 ms | **3,175 ms** |

Ressalva honesta: a "máscara ruidosa" é ruído sal-e-pimenta sintético (worst case: 38 mil
componentes a 1080p), não uma máscara real de footage com vidro. Serve para mostrar a **forma da
curva de custo** — `findContours` é barato com máscara limpa e explode com máscara suja —, não
para prever o número exato em produção.

---

## 2. Inventário: o que a pipeline realmente faz hoje

Resumo factual (leitura do código, não do `ARCHITECTURE.md`), porque várias propostas dependem
de detalhes que os documentos de plano não refletem exatamente.

### Capture — `src/stages/capture/plugin.py::DualVideoFileCapture`
- `open()` abre dois `cv2.VideoCapture` e devolve um generator **síncrono**: um `read()` do topo
  seguido de um `read()` do lado, no mesmo thread, por frame. Para no vídeo mais curto.
- `open_single(role)` abre um terceiro/quarto `VideoCapture` para leitura por-view sem lockstep
  (usado pelo passe 1 do Detect).
- `dimensions(role)` abre e fecha o arquivo só para ler duas propriedades.
- Sem threads, sem fila, sem prefetch — decisão deliberada e documentada da Fase 3 ("threading
  fica como otimização de throughput futura").

### Rectify — `src/stages/rectify/plugin.py::CpuPerspectiveRectifier`
- Matriz de perspectiva calculada **1× no `__init__`** (correção real sobre o legado, que
  recalculava por frame).
- Por frame: `cv2.warpPerspective(frame_BGR)` → `cv2.cvtColor(..., BGR2GRAY)`. **Nesta ordem.**
- Se o perfil não tem 4 pontos de perspectiva, o fallback monta os 4 cantos do frame inteiro →
  a matriz resultante é a **identidade** e o `warpPerspective` vira uma cópia cara. **É
  exatamente a configuração do golden** (`tests/fixtures/golden_config.py`:
  `perspective_points_top=[]`).

### Detect (CPU) — `src/stages/detect/plugin.py::BackgroundSubtractionDetector`
Confirmado por leitura do código: **não é MOG2**. É o algoritmo legado, portado fielmente:
- **Passe 1 (`setup`)**: itera *todos* os frames da própria view, **retifica cada um**, e guarda
  em `sampled` apenas os de índice múltiplo de `frame_block=500`. Depois
  `np.max(sampled, axis=0)` → imagem de fundo estática (máximo de intensidade).
- **Passe 2 (`detect`)**: `absdiff(max_frame, image)` → `threshold(80)` → `threshold(127)` →
  `findContours(RETR_EXTERNAL)` → maior contorno por área → centroide via `moments`, com
  `cy_from_bottom = H − cy_from_top`.
- Algoritmo **não-causal** (precisa de frames futuros para detectar no frame 0) — essa é a razão
  arquitetural das duas passadas.
- Pressuposto físico embutido: **o alvo é mais escuro que o fundo** (imagem de máximo). Um alvo
  mais claro que o fundo é absorvido pelo modelo de fundo e some.

### Detect (CUDA) — `src/stages/detect/cuda/plugin.py::CudaMOG2Detector`
**Algoritmo diferente, não porte de hardware do mesmo algoritmo** — assimetria conhecida e
documentada, confirmada no código:
- `cv2.cuda.createBackgroundSubtractorMOG2` — modelo de mistura de gaussianas, **stateful e
  causal**, com aquecimento; sem imagem de máximo, sem thresholds 80/127.
- Só o `apply` roda na GPU; a máscara é **baixada para a RAM** e `threshold`/`findContours`/
  `moments` rodam em CPU (limitação real do `cv2.cuda` em Python, documentada em
  `src/core/array_backend.py`).
- Consequência prática: os dois detectores **não produzem os mesmos números**, e o teste de
  paridade comportamental completo ainda é um `skip` rastreável.

### Track — `src/stages/track/plugin.py::SingleEntityTracker`
Trivial: guarda 1 ponto por frame num dict, `entity_id=0`. Custo desprezível em qualquer escala.

### Track multi (spike Fase 6) — `src/stages/track/multi/`
- `KalmanPointTracker` em numpy puro (matrizes 4×4 / 2×2), `MultiEntityTracker` com matriz de
  custo em listas Python, e duas estratégias de associação: `greedy` e `hungarian` (Kuhn-Munkres
  O(n³) implementado à mão, ~50 linhas, para evitar dependência de `scipy`).
- O próprio handoff mede: ~15.200 e ~15.600 frames/s respectivamente — **empate, e ambos ordens
  de magnitude acima de tempo real**.

### Fuse / Metadata — `src/stages/fuse/plugin.py`, `plugins/{speed,border}/plugin.py`
Laços Python sobre `route.points` (N = número de frames). Aritmética escalar simples. Todos
O(N) com constante minúscula.

### Registry — `src/core/plugin_registry.py`
`discover()` + `for_kind()` são chamados **uma vez por run**, em `_run_metadata_plugins`, depois
que todos os frames já foram processados. **Zero lookup de plugin no caminho quente.** O
`importlib.util.spec_from_file_location` roda 2–4 vezes por run, não 1200×.

---

## 3. Propostas

Cada proposta segue o formato: **o que é caro hoje → o que fazer → impacto esperado → risco/custo**.

---

### Grupo A — Trabalho redundante na orquestração (o maior ganho disponível hoje)

#### O1. O passe 1 retifica 1200 frames para usar 3

**O que é caro hoje.** `src/stages/detect/plugin.py::BackgroundSubtractionDetector.setup`:

```python
for raw in self._capture.open_single(self._role):
    rectified = self._rectifier.rectify(raw, counter)      # <- roda em TODO frame
    if counter % self._frame_block == 0:                   # <- 1 em 500 é guardado
        sampled.append(rectified.image)
    counter += 1
```

Numa fixture de 1200 frames, `rectify` roda 1200× por view para produzir 3 imagens úteis —
**99,75% do trabalho de warp+cvtColor do passe 1 é jogado fora**. Medido: retificação custa
0,157 s dos 0,357 s de uma leitura completa de 1 view.

**Otimização.** Mover a chamada de `rectify` para dentro do `if`:

```python
if counter % self._frame_block == 0:
    sampled.append(self._rectifier.rectify(raw, counter).image)
```

Matematicamente **idêntico** — `rectify` é puro (matriz fixa, sem estado), então retificar só os
frames amostrados produz exatamente as mesmas amostras. O golden não muda.

**Impacto esperado.** Reduz o passe 1 a decode puro. Medido: 0,357 s → ~0,20 s por view;
o passe 1 (2 views) cairia de 0,709 s para ~0,40 s → **~20% do tempo total da pipeline** na
fixture. **Em 1080p o ganho relativo é maior**, porque o warp de BGR passa a custar 1,94 ms/frame
(vs. 0,08 ms na fixture) enquanto o decode não cresce na mesma proporção — estimativa (não
medida) de 40–60% do passe 1.

**Risco/custo.** Mínimo. Mudança **local de 3 linhas dentro de um plugin**, sem tocar em
nenhuma interface congelada (Fase 2/3), sem dependência nova. O único cuidado: o `frame_index`
passado ao `rectify` deixa de ser sequencial (vira 0, 500, 1000) — irrelevante, o passe 1
descarta tudo menos `.image`. Requer confirmar que nenhum teste unitário de Detect conta chamadas
de `rectify` no fake.

---

#### O2. O modelo de fundo lê o vídeo inteiro para amostrar 1 frame a cada 500

**O que é caro hoje.** Mesmo lugar (`setup`) + `DualVideoFileCapture.open_single`. Mesmo depois
de O1, o passe 1 **decodifica todos os 1200 frames** só para chegar aos índices 0/500/1000.

**Otimização.** Amostrar por `seek`: `cap.set(cv2.CAP_PROP_POS_FRAMES, i)` + `read()`, para
`i` em `range(0, frame_count, frame_block)`, usando `CAP_PROP_FRAME_COUNT` para saber o total.

**Impacto esperado.** Medido na fixture: **0,021 s vs. 0,192 s** (≈9× mais rápido), com os
frames amostrados **byte-idênticos** (verificado por média de pixel). Combinado com O1, o passe
1 inteiro (2 views) cairia de 0,709 s para ~0,05 s — **elimina praticamente 45% do tempo total
da pipeline**.

**Risco/custo — o mais alto deste grupo, e precisa ser dito.** A fixture é FFV1 (all-intra):
seek é exato e barato. Em codecs long-GOP (H.264/H.265, que é o que uma webcam ou câmera real
grava), `CAP_PROP_POS_FRAMES` **pode não posicionar no frame exato** — implementações do FFMPEG
frequentemente saltam para o keyframe anterior, e `CAP_PROP_FRAME_COUNT` pode ser estimado, não
exato. Um seek impreciso amostraria frames *diferentes* dos que o algoritmo legado amostrava.

Para o modelo de fundo isso é quase sempre **inofensivo** (um `np.max` sobre amostras esparsas é
altamente insensível a *qual* amostra exatamente foi pega — o próprio teste da Fase 3 observa
que "o modelo de fundo é invariante às posições amostradas" com blobs escuros), **mas quebra a
reprodutibilidade bit-a-bit do golden** se algum frame amostrado mudar. Mitigação recomendada:
implementar como estratégia selecionável com fallback (`sample_strategy="seek"|"sequential"`),
default `sequential` até haver validação em codec long-GOP real, e comparar os dois caminhos num
teste. Mudança local ao Detect + um método novo no Capture (aditivo, não quebra a interface).

---

#### O3. Os dois passes 1 rodam em sequência

**O que é caro hoje.** `src/stages/orchestration.py:86-87`:

```python
det_top.setup()
det_side.setup()
```

Duas leituras completas de arquivos **diferentes**, totalmente independentes, executadas uma
depois da outra. Medido: 0,709 s combinados.

**Otimização.** Rodar as duas em um `ThreadPoolExecutor(max_workers=2)`. `VideoCapture.read()` e
as chamadas `cv2.*` **liberam a GIL**, então dois threads realmente sobrepõem I/O e trabalho de
pixel aqui — este é um dos poucos pontos da pipeline onde threading em Python de fato paga.

**Impacto esperado.** Até ~2× no passe 1 (limitado por I/O de disco se os dois vídeos estiverem
no mesmo dispositivo lento). Na fixture: 0,709 s → ~0,4 s, ~20% do total. **Mas note: se O1+O2
forem feitos, o passe 1 vira ~0,05 s e esta otimização perde quase toda a relevância.** Fazer
O1/O2 primeiro; reavaliar O3 depois.

**Risco/custo.** Baixo, mas não nulo: cada `setup()` grava estado no seu próprio detector
(objetos distintos), então não há corrida de dados — porém os dois detectores compartilham o
mesmo objeto `capture` (o orquestrador passa a mesma instância). `open_single` abre um
`VideoCapture` novo por chamada e não muta o objeto `DualVideoFileCapture`, então é seguro hoje;
isso vira um **invariante implícito que precisa de comentário/teste** para não ser quebrado
depois. Mudança local ao orquestrador, sem tocar em interface.

---

#### O4. `np.max(sampled, axis=0)` materializa todas as amostras

**O que é caro hoje.** `setup` acumula `sampled: list[np.ndarray]` e no fim chama
`np.max(sampled, axis=0)`, o que **empilha a lista num array (N, H, W)** antes de reduzir.

Na fixture: 3 amostras × 76,8 KB = irrelevante. **Em produção não é**: 1080p em escala de cinza
= 2,07 MB/frame; um vídeo de 30 min a 30 fps = 54.000 frames → 108 amostras → **~224 MB retidos
+ ~224 MB transitórios no empilhamento**. Para 4K, ~900 MB + 900 MB.

**Otimização.** Máximo incremental, O(1) em memória:

```python
if acc is None: acc = img.copy()
else: np.maximum(acc, img, out=acc)
```

Resultado numericamente idêntico ao `np.max` (máximo é associativo e comutativo, sem
acumulação de ponto flutuante — são `uint8`).

**Impacto esperado.** Memória do passe 1 vai de O(duração do vídeo) para **O(1)** — de ~450 MB
para ~2 MB no cenário 1080p/30min acima. Tempo: neutro a levemente melhor (evita uma alocação
grande). **É uma correção de escalabilidade, não de velocidade** — o teto de 50 MB do
`test_memory_bounded` passa hoje só porque a fixture é minúscula.

**Risco/custo.** Muito baixo. ~5 linhas dentro de um plugin, sem mudança de interface,
sem dependência nova, sem mudança de resultado. Combina naturalmente com O1/O2.

---

### Grupo B — Detect: custo e qualidade por frame

#### O5. O segundo `threshold` é matematicamente uma identidade

**O que é caro hoje.** `src/stages/detect/plugin.py::detect`:

```python
_, diff = cv2.threshold(dif_frame, 80, 255, cv2.THRESH_BINARY)
_, binarizada = cv2.threshold(diff, 127, 255, cv2.THRESH_BINARY)
```

Depois do primeiro threshold, `diff` só contém 0 e 255. O segundo mapeia 0→0 e 255→255: **é uma
cópia cara do frame inteiro, exatamente uma no-op**. Porte fiel de uma redundância do código
legado (`backgroundRemoveModule.py`), não um bug introduzido na refatoração.

**Otimização.** Remover a segunda linha (e a constante `_BINARY_THRESHOLD`).

**Impacto esperado.** Uma varredura de frame inteiro a menos por frame **por view**. Medido
indiretamente (o par absdiff+2 thresholds custa 0,012 ms em 320×240 e 1,813 ms em 1080p);
estimativa: ~0,6–0,9 ms/frame/view economizados a 1080p → **~1,5 ms por par de frames**, ou
~27 s num vídeo de 10 min. Marginal na escala atual, gratuito em qualquer escala.

**Risco/custo.** Praticamente zero — a saída é **idêntica bit-a-bit** (verificado empiricamente:
`np.array_equal(diff, binarizada) == True`). Mudança de 1 linha, local ao plugin. Ainda assim,
rodar o golden depois (custo: 1 comando).

---

#### O6. Nada limpa a máscara antes do `findContours`

**O que é caro hoje.** `detect` vai direto de `threshold` para
`findContours(RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)` seguido de `max(contours, key=contourArea)`.
Com a fixture sintética (fundo perfeitamente uniforme) a máscara tem 1 componente e isso é
baratíssimo (0,018 ms). **Com footage real — vidro, reflexo, ruído de sensor, iluminação
oscilante — a máscara terá centenas ou milhares de componentes espúrios**, e o custo de
`findContours` + o `max` sobre a lista de contornos cresce com o **número de componentes**, não
com o número de pixels.

Medido (worst case sintético a 1080p): 0,93 ms com máscara limpa → **65,5 ms** com máscara
ruidosa. Isso é ~70× e derrubaria a pipeline abaixo de tempo real sozinho.

**Otimização.** Uma `cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_5x5)` antes do
`findContours` — remove componentes menores que o kernel de uma vez, em custo **proporcional a
pixels**, não a componentes.

**Impacto esperado.** Medido: máscara ruidosa 1080p vai de 65,5 ms para **3,18 ms** (~20×).
Com máscara limpa, a morfologia **custa** ~2 ms extra a 1080p (0,93 → 2,96 ms) — ou seja,
**é um seguro que se paga só quando há ruído**. Ganho colateral de qualidade: elimina detecções
falsas de 1–2 px que hoje podem vencer o `max(contourArea)` quando o inseto está ocluído.

Alternativa considerada e **rejeitada**: `connectedComponentsWithStats` (que daria área+centroide
direto, sem `moments`). Medido: é **mais lento** que `findContours` com máscara limpa a 1080p
(5,05 ms vs. 0,93 ms) e só ganha no caso ruidoso — onde a morfologia ganha mais e mais barato.

**Risco/custo.** Baixo tecnicamente (local ao plugin, sem dependência nova), **mas muda o
resultado numérico**: erodir/dilatar desloca o centroide em fração de pixel e o golden
(`tolerância 1e-6`) falharia — exige **regeneração de `expected_result.json`** e uma decisão
consciente de que a nova referência é a correta. Recomendação: introduzir como parâmetro
opcional (`morph_kernel: int = 0`, desligado por default) para não invalidar o golden, e ligar
quando houver footage real para validar.

---

#### O7. Toda a busca é global, mesmo quando a posição anterior é conhecida

**O que é caro hoje.** `detect(frame)` opera sobre o frame retificado **inteiro**, todo frame,
sem nenhum conhecimento de onde a entidade estava no frame anterior. A interface `Detector` é
deliberadamente sem estado temporal (isso é papel do Track) — o que é a decisão arquitetural
certa, mas deixa performance na mesa.

**Otimização.** Gating espacial (ROI): manter a última posição conhecida e rodar
absdiff+threshold+contour numa janela de, digamos, 4× o diâmetro esperado do alvo em torno da
predição; cair para busca global só quando a janela falha ou depois de N frames sem detecção.

**Impacto esperado.** O custo por frame passa a ser proporcional à área da ROI, não à do frame.
Para um inseto de ~40 px de diâmetro numa imagem 1080p, uma ROI de 160×160 é **~1/80 da área** —
`absdiff`+`threshold`+`findContours` cairiam quase a zero, deixando decode e warp como únicos
custos relevantes. Estimativa **não medida** (depende do tamanho do alvo em produção; irrelevante
na fixture, onde o frame inteiro já custa 0,035 ms).

**Risco/custo — o mais alto deste grupo.** Introduz **estado temporal no Detect**, que é
exatamente a separação que a Fase 3 lutou para estabelecer (Detect = espacial, Track = temporal).
Duas saídas possíveis, ambas com custo arquitetural real:
1. Um `Detector` novo (plugin separado, `roi-background-detector`), mantendo o atual intacto —
   preserva a separação conceitual à custa de duplicar o algoritmo;
2. Estender a interface `Detector` com um hint opcional (`detect(frame, hint: Point2D | None)`) —
   **toca uma interface congelada da Fase 2**, exige versionar `api_version`.

Também há risco de **qualidade**: uma ROI que perde o alvo (movimento rápido, teleporte pós-
oclusão) pode custar mais em detecções perdidas do que ganha em ms. Não fazer isto sem antes ter
material real e o problema de performance efetivamente comprovado.

---

#### O8. O modelo de fundo não-causal é a causa raiz das duas passadas

**O que é caro hoje.** A imagem de máximo estático (`np.max` de amostras espalhadas por todo o
vídeo) exige conhecer o futuro para detectar no frame 0 — o que **força** a arquitetura de duas
passadas descrita em O1/O2/O3, ou seja, dobra o decode do vídeo inteiro.

Além do custo, o modelo tem limitações de qualidade documentáveis:
- assume alvo **mais escuro** que o fundo (um alvo mais claro é absorvido pelo fundo);
- é **estático**: iluminação que muda ao longo do vídeo (nuvem passando, lâmpada oscilando)
  degrada a detecção uniformemente para todo o vídeo, sem adaptação;
- os thresholds 80/127 são **absolutos e fixos**, não derivados do contraste real da cena.

**Otimização (menu de opções, em ordem crescente de mudança).**

**(a) Fundo por mediana em vez de máximo.** Mesma estrutura de duas passadas, mas
`np.median(sampled, axis=0)` em vez de `np.max` + `absdiff` bidirecional. Remove o pressuposto
"alvo é escuro" e é robusto a um alvo que fica parado numa amostra. Custo: mediana é mais cara
que máximo, mas roda **uma vez por run**, não por frame — irrelevante.

**(b) Threshold derivado da cena** (ex.: Otsu, ou `média + k·desvio` do `dif_frame`) em vez do 80
fixo. Custo por frame: `cv2.threshold(..., THRESH_OTSU)` é da ordem de um threshold normal.
Ganho de robustez a mudança de exposição entre gravações.

**(c) Fundo causal com média corrida** (`cv2.accumulateWeighted`, ~1 linha) ou MOG2 em CPU.
**Isto elimina a segunda passada inteira** e torna a pipeline verdadeiramente single-pass e
streaming de ponta a ponta — o modelo se adapta a iluminação variável. Custo por frame medido:
MOG2 CPU = 0,83 ms a 320×240 e 11,5 ms a 1080p, **muito mais caro por frame** que
absdiff+threshold (0,012 ms / 1,8 ms). Ou seja: **(c) troca uma passada inteira de decode+warp
por ~10 ms/frame de subtração adaptativa**. Cujo lado ganha depende do custo do decode em
produção — precisa ser medido, não estimado.

**Nota importante:** (c) é *exatamente* o que o `CudaMOG2Detector` já faz. Adotar MOG2 no CPU
**eliminaria a assimetria de algoritmo CPU×GPU** documentada na Fase 5 e tornaria o teste de
paridade genuinamente comparável (hoje ele só pode ser "equivalência comportamental" porque os
dois lados rodam algoritmos diferentes). Esse é provavelmente o argumento mais forte a favor de
(c), acima de qualquer ganho de tempo.

**Impacto esperado.** (a) e (b): neutros em tempo, positivos em robustez. (c): elimina ~45% do
tempo (a passada 1) e adiciona ~10 ms/frame a 1080p — **provavelmente negativo em tempo puro,
positivo em qualidade e em coerência arquitetural**. Nenhum destes números substitui um teste em
footage real.

**Risco/custo.** Alto em *validação*, baixo em *código*. Todos são mudanças locais ao plugin
(ou plugins novos), mas **qualquer um invalida o golden** e, mais sério, muda o comportamento
científico do instrumento — a trajetória extraída é o dado do TCC. Recomendação forte:
implementar como **detectores alternativos** (plugins novos), medir os três lado a lado sobre a
mesma footage real com ground truth conhecido, e só então escolher o default. É pesquisa, não
refatoração.

---

#### O8b. Detectar em resolução reduzida

**O que é caro hoje.** Todas as operações de detecção rodam na resolução nativa do frame
retificado.

**Otimização.** `cv2.pyrDown` (ou `resize` por fator 2) antes de detectar, e escalar o centroide
de volta. Opcionalmente refinar com uma segunda passada só na ROI em resolução plena.

**Impacto esperado.** Custo por pixel cai 4× por nível. A 1080p, absdiff+threshold+contour
cairiam de ~2,7 ms para ~0,7 ms por view. **Perda de precisão: o centroide fica quantizado ao
dobro do pixel** — que, convertido pela calibração típica do projeto (`px_per_cm ≈ 20`), é ~0,1
cm de erro adicional. Comparar com a tolerância que o próprio golden usa para a validação
independente: 0,5 cm. Ou seja, **provavelmente aceitável**, mas é uma decisão de precisão
científica, não de engenharia.

**Risco/custo.** Baixo em código (local ao plugin, parametrizável), médio em ciência (degrada a
resolução da medida). Só vale a pena se o profiling em produção mostrar que a detecção — e não o
decode — domina.

---

### Grupo C — Rectify

#### O9. Warp de 3 canais seguido de conversão para 1 canal (ordem invertida)

**O que é caro hoje.** `CpuPerspectiveRectifier.rectify` (e, idem, `CudaPerspectiveRectifier`):

```python
warped = cv2.warpPerspective(frame, self._matrix, (w, h))   # 3 canais
gray   = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)           # -> 1 canal
```

O warp — a operação cara — é feito sobre **3× mais dados do que o necessário**, e só depois os
canais são colapsados.

**Otimização.** Inverter: `cvtColor` primeiro (1 canal), depois `warpPerspective` sobre a
imagem em escala de cinza.

**Impacto esperado (medido).** A 1080p: `warp(BGR) + cvt` = 1,941 + 0,600 = **2,541 ms**;
`cvt + warp(GRAY)` = 0,600 + 0,820 = **1,420 ms** → **~44% mais rápido no estágio Rectify**. A
720p: 1,028 → 0,334 ms (**~68%**). Na fixture 320×240: 0,103 → 0,064 ms. Como Rectify é
0,306 s dos 1,50 s totais na fixture (e cresce mais rápido que o decode com a resolução), é um
dos melhores ganhos por linha de código do documento.

**Risco/custo.** Baixo tecnicamente — 2 linhas trocadas de lugar, local ao plugin, sem
dependência nova, sem tocar em interface. **Mas o resultado não é bit-idêntico**: a interpolação
bilinear e a conversão para cinza são ambas lineares, então em aritmética exata as duas ordens
coincidem; em `uint8` os arredondamentos intermediários diferem. **Medido** sobre um warp não
trivial de 320×240: diferença **máxima de 1 nível de cinza**, média absoluta 0,22 — ou seja, a
divergência é o arredondamento e nada mais. Ainda assim pode deslocar o centroide em fração de
pixel → **o golden (1e-6) falha e precisa ser regenerado**. Recomendação: aplicar, regenerar o golden e verificar que
`test_recovered_route_approximates_synthetic` (tolerância 0,5 cm) continua passando folgado —
esse é o teste que atesta que a mudança não degradou a medida.

Se a fidelidade bit-a-bit ao legado for requisito, uma variante sem esse problema: pedir ao
decoder já em cinza não é possível via `VideoCapture`, mas fazer o `cvtColor` com a **mesma**
matriz de pesos e depois warp continua sendo a única forma; não há caminho que seja
simultaneamente mais rápido e bit-idêntico.

---

#### O10. Warp identidade quando o perfil não tem pontos de perspectiva

**O que é caro hoje.** O fallback do `__init__` (`if len(points) != 4`) monta os 4 cantos do
frame inteiro, o que gera uma matriz **identidade** — e `warpPerspective` com identidade é uma
cópia integral do frame, com todo o custo de amostragem/interpolação e nenhum efeito.
**Esta é a configuração do golden** e presumivelmente a de qualquer usuário que não calibrou
perspectiva.

**Otimização.** Detectar `np.allclose(self._matrix, np.eye(3))` no `__init__` e, se verdade,
pular o `warpPerspective` no `rectify` (só `cvtColor`).

**Impacto esperado.** Elimina 100% do custo de warp nesse caso: medido 0,131 ms/frame na fixture
(→ ~0,02 ms, só a conversão de cor), ou seja **~0,3 s dos 1,50 s totais** da fixture (~20%). A
1080p seriam ~1,9 ms/frame/view eliminados. Ganho **condicional** — zero para quem calibrou
perspectiva de verdade, que é o caso de uso pretendido.

**Risco/custo.** Muito baixo: mudança local, saída **bit-idêntica** — verificado empiricamente
(`warpPerspective` com matriz identidade devolve exatamente o array de entrada, incluindo
bordas). Combina com O9 (fazer só `cvtColor` e retornar direto).

---

### Grupo D — I/O, decode e paralelismo

#### O11. As duas câmeras são decodificadas em série no mesmo thread

**O que é caro hoje.** `DualVideoFileCapture.open()`:

```python
ok_top,  top_frame  = top_cap.read()
ok_side, side_frame = side_cap.read()
```

Decisão explícita e documentada da Fase 3 ("leitura SÍNCRONA... o pipelining por thread fica
como otimização de performance para uma fase futura"). Medido: o decode é ~0,269 s dos 0,788 s
do passe 2 — **34% do passe 2 é decode serializado**.

Nota histórica relevante: o `process_basic_modules` legado usava `ThreadPoolExecutor` para rodar
os dois vídeos em paralelo. A Fase 3 **removeu esse paralelismo** ao trocar buffer-inteiro por
streaming lockstep. O perfil de memória melhorou drasticamente; o paralelismo de câmera foi
perdido no caminho, e isso não está registrado como regressão em lugar nenhum.

**Otimização.** Produtor/consumidor: um thread por câmera, cada um alimentando uma
`queue.Queue(maxsize=k)` pequena (k = 4–8 frames), e o generator pareando o que sai das duas
filas. `VideoCapture.read()` **libera a GIL** durante o decode, então o overlap é real.

**Impacto esperado.** Até ~2× no componente de decode; ~15% do passe 2 na fixture. Em produção
(H.264 1080p, onde o decode é muito mais caro que FFV1 320×240 — **inferido, não medido**) o
decode passa a ser uma fração maior do total e o ganho cresce proporcionalmente.

**Risco/custo.** Médio. Mudança **contida no plugin de Capture** (a interface
`open() -> (fps, Iterator[FramePair])` não muda), mas introduz threads, filas e um caminho de
shutdown que precisa liberar os `VideoCapture` corretamente mesmo se o consumidor abandonar o
generator no meio (`GeneratorExit`). Custa também o determinismo simples que a Fase 3
deliberadamente escolheu — o resultado continua determinístico (o pareamento por índice é
preservado), mas a ordem de execução deixa de ser. Requer teste de vazamento de recurso e de
abandono precoce do generator. `maxsize` limitado mantém a memória O(k), não O(vídeo).

---

#### O12. Alocação de um array novo por frame no `read()`

**O que é caro hoje.** Cada `cap.read()` aloca um `np.ndarray` novo (H×W×3). A 1080p são 6,2 MB
por frame, 2 câmeras, 30×/s → **~370 MB/s de churn de alocação**, tudo imediatamente descartado.

**Otimização.** O binding Python do OpenCV aceita um array de saída (`cap.read(buf)`), permitindo
reciclar buffers. Combinado com O11, um pool pequeno de buffers por câmera.

**Impacto esperado.** **Provavelmente pequeno e não medido.** O alocador do numpy é eficiente e
o custo real é dominado pela largura de banda de memória do próprio decode, não pelo `malloc`.
Vale medir antes de fazer; listado por completude, não como recomendação.

**Risco/custo.** Baixo em código, mas **cria aliasing**: o `FramePair` é `frozen`, mas o
`np.ndarray` que ele carrega não é imutável — reciclar buffers significa que um consumidor que
guarde a referência a um frame verá o conteúdo mudar embaixo dele. Isso quebra o passe 1 do
Detect, que faz exatamente isso (`sampled.append(rectified.image)`) — embora ali seja a imagem
*retificada* (array novo), não o buffer de decode. Exige contrato explícito de "o frame só é
válido até o próximo `next()`", que é uma armadilha clássica para autores de plugin de terceiro.
**Não recomendado antes de haver medição que justifique.**

---

#### O13. Threads vs. processos: onde a GIL importa e onde não

Não é uma proposta única, é o critério para avaliar as propostas de paralelismo (O3, O11) e
evitar propostas ruins:

- **`cv2.*` e `VideoCapture.read()` liberam a GIL.** Threading funciona de verdade para
  decode, warp, absdiff, threshold, findContours. É por isso que O3 e O11 são viáveis.
- **O laço Python que os chama não libera nada.** No passe 2, o corpo do `for pair in frames`
  (construção dos modelos pydantic, dicts do tracker, chamadas de método) é puro Python e
  serializa. Medido: pydantic custa 0,0033 ms por `FrameDetections` — **~4% do tempo de
  detect+track na fixture, e proporcionalmente menos em resoluções maiores**. Não é o gargalo.
- **`cv2` já usa 16 threads internamente** nesta máquina (`cv2.getNumThreads() == 16`). Adicionar
  paralelismo próprio por cima **pode piorar** por sobre-subscrição. Se O3/O11 forem
  implementados, medir também com `cv2.setNumThreads(n)` reduzido.
- **Multiprocessing**: os dados que cruzariam a fronteira de processo são **frames de vídeo**
  (MB por item). O custo de pickle/IPC come qualquer ganho, a menos que se particione por
  **arquivo inteiro** (um processo por câmera, cada um lendo seu próprio vídeo do disco e
  devolvendo só a lista de centroides — payload minúsculo). **Essa é a única forma de
  multiprocessing que faz sentido aqui**, e ela é essencialmente O3 aplicado às duas passadas
  inteiras, com a complicação de que o passe 2 é intrinsecamente pareado (o lockstep exige as
  duas views no mesmo lugar). Conclusão: threading resolve; multiprocessing não se justifica.

---

### Grupo E — O caminho GPU: o que a arquitetura promete vs. o que o código entrega

Esta seção é deliberadamente cética. O `ARCHITECTURE.md` descreve um caminho GPU que o código
**não implementa hoje**, e repetir a moldura do documento como se já fosse verdade seria enganoso.

#### O14. `--gpu` não seleciona nenhum plugin GPU

**Estado real, verificado no código.** `src/app/cli.py` aceita `--gpu`, que chega a
`src/app/runner.py::execute_analysis(require_gpu=True)`, que chama `require_cuda()` — e **em
seguida chama `run_cpu_analysis(profile)`**. `src/stages/orchestration.py` importa e instancia
**diretamente** `CpuPerspectiveRectifier` e `BackgroundSubtractionDetector`, hardcoded. Idem
`Pipeline.run` (que, na prática, só roda metadata).

Ou seja: hoje **`--gpu` é um gate que exige uma GPU e depois processa tudo em CPU**. Isso está
listado como pendência ("Wiring de orquestração GPU") no handoff da Fase 5, mas vale registrar
sem eufemismo: **o caminho GPU não está conectado a nada**. Não é uma otimização a fazer, é uma
funcionalidade ausente — e qualquer estimativa de ganho de GPU é irrelevante até isso existir.

**O que fazer.** Parametrizar `run_cpu_analysis` com fábricas de rectifier/detector (ou um
`run_analysis(profile, backend="cpu"|"cuda")`). Os plugins CUDA já satisfazem o contrato.

**Impacto/risco.** Sem impacto de performance por si; é pré-requisito de tudo em GPU. Risco
baixo (mudança local ao orquestrador), **mas só faz sentido depois** de existir um OpenCV com
módulo `cuda` — hoje o código nem poderia ser testado.

---

#### O15. `ArrayBackend` **não** mantém o frame residente na GPU entre Rectify e Detect

**Estado real, verificado no código.** O docstring de `src/core/array_backend.py` diz "Frame
fica residente na GPU entre Rectify→Detect (sem round-trip RAM)". O código não faz isso:

- `CudaPerspectiveRectifier.rectify` termina com
  `image = backend.download(gray)` e devolve `RectifiedFrame(image=image, ...)`.
- `RectifiedFrame.image` é anotado `np.ndarray` (`src/core/frames.py`) — o tipo do contrato
  **é RAM por construção**.
- `CudaMOG2Detector.detect` começa com `self._backend.upload(frame.image)`.

Portanto o fluxo real por frame é: `upload → warp → cvtColor → **download** → **upload** →
MOG2 → download`. **Há dois round-trips PCIe por frame por view que a arquitetura afirma não
existirem.** A abstração existe e está correta *dentro* de cada estágio; ela só não atravessa a
fronteira entre estágios, porque a fronteira é tipada como `np.ndarray`.

**Quanto isso custa (estimado, não medido — não há hardware).** Um frame 1080p em cinza são
2,07 MB; BGR são 6,2 MB. Sobre PCIe 3.0 x16 (~12 GB/s efetivos, pinned; bem menos com memória
paginável, que é o que `GpuMat.upload` de um array numpy comum usa): o par download+upload
desnecessário custa da ordem de **0,3–1,0 ms por frame por view**, mais a latência de
sincronização de cada transferência (que serializa o pipeline: transferências em `Stream_Null`
são bloqueantes). Compare com o ganho: `warpPerspective` a 1080p custa 1,94 ms em CPU e
tipicamente **dezenas de microssegundos** em GPU. **O round-trip evitável é da mesma ordem de
grandeza do trabalho que a GPU faz** — é o tipo de detalhe que transforma "aceleração de 20×" em
"aceleração de 2×".

**Otimização.** Duas opções, ambas com custo de contrato:
1. Tornar `RectifiedFrame.image` opaco (`Any`/union `np.ndarray | GpuMat`) + um `backend` no
   próprio `RectifiedFrame`, deixando o download acontecer **só onde a CPU é obrigatória**
   (extração de contorno). **Toca `src/core/frames.py`, que é tipo compartilhado entre estágios
   congelados desde a Fase 3** — mudança de contrato, não local.
2. Fundir Rectify+Detect num único plugin GPU (`CudaRectifyDetect`), mantendo a fronteira
   pública em `np.ndarray`. Não mexe em contrato, mas duplica lógica e fura a separação de
   camadas que é a entrega central do projeto. **Não recomendado.**

**Impacto esperado.** Estimado (não medido): eliminar 1 round-trip por frame por view deveria
valer 20–50% do tempo do caminho GPU a 1080p. **Impossível confirmar sem hardware.**

**Risco/custo.** Opção 1 é a arquiteturalmente correta e a mais cara: toca tipo compartilhado,
exige revisitar todos os consumidores de `RectifiedFrame.image` (Detect CPU, Detect CUDA, testes
de estágio) e potencialmente bumpar `api_version` de plugin. **Não fazer antes de a Fase 5
rodar de verdade em hardware** — é otimização de um caminho que ninguém nunca executou.

---

#### O16. `Stream_Null` serializa; não há pipelining assíncrono

**O que é caro (estimado).** `CudaMOG2Detector.detect` usa `cv2.cuda.Stream_Null()`, e
`CudaArrayBackend` não usa streams em nenhuma operação — tudo é síncrono e bloqueante. O padrão
que dá ganho real em GPU (sobrepor `upload(frame N+1)` com `compute(frame N)` e
`download(frame N−1)` usando 2–3 streams e memória pinned) **não existe**.

**Otimização.** Streams explícitos + buffers pinned + um pool de `GpuMat` reciclados (o método
`release` do `ArrayBackend` já está documentado como "ponto de extensão para reciclar `GpuMat` de
um pool").

**Impacto esperado.** Em pipelines de vídeo em GPU, o pipelining assíncrono tipicamente vale
1,5–3× sobre a versão síncrona ingênua. **Estimativa de literatura, zero medição aqui.**

**Risco/custo.** Alto e prematuro. Requer hardware, requer O14 e O15 antes, e adiciona
complexidade de sincronização a um caminho que ainda não tem um único teste executado. Listado
para completude do roadmap, **não para fazer agora**.

---

### Grupo F — Memória

#### O17. O perfil de memória já está resolvido na escala atual; o risco é de escala

**Estado real.** `test_memory_bounded` mede pico de ~2,9 MB contra teto de 50 MB. O problema que
a Fase 3 resolveu (vídeo inteiro em RAM, ~88 MB/view de frames retificados + a lista de diffs)
está genuinamente resolvido: o streaming retém O(1) frame por vez.

O que **não** escala é o `sampled` do passe 1 (ver O4), que é O(duração do vídeo ÷ 500). Em
1080p:

| Vídeo | Amostras | RAM retida | + pico transitório do `np.max` |
|---|---|---|---|
| 40 s (fixture, 320×240) | 3 | 0,2 MB | 0,2 MB |
| 10 min, 1080p | 36 | 75 MB | +75 MB |
| 30 min, 1080p | 108 | 224 MB | +224 MB |
| 30 min, 4K | 108 | 895 MB | +895 MB |

**O `test_memory_bounded` com teto de 50 MB passaria hoje e falharia com um vídeo de produção** —
o teste não é um guard-rail de escala, é um guard-rail contra a regressão específica do legado.

**Otimização.** O4 (máximo incremental) resolve completamente: memória O(1) independente da
duração. Vale também considerar tornar `frame_block` proporcional à duração (hoje é fixo em 500,
o que significa "amostrar mais quanto mais longo o vídeo" — para um modelo de fundo, ~20–30
amostras bem espalhadas já saturam o benefício; 108 amostras de um vídeo de 30 min não compram
nada sobre 30).

**Risco/custo.** O4: mínimo (ver acima). Tornar `frame_block` adaptativo **muda quais frames
são amostrados** → muda o modelo de fundo → invalida o golden; fazer só junto com uma decisão
consciente sobre o detector (O8).

---

### Grupo G — Onde procurei gargalo e **não** encontrei (achados negativos)

Achados negativos importam tanto quanto positivos — evitam trabalho inútil no futuro.

#### O18. O húngaro O(n³) escrito à mão **não** é um gargalo, e não vai ser

`src/stages/track/multi/assignment.py::_hungarian_square` é uma implementação Kuhn-Munkres em
listas Python puras, deliberadamente sem `scipy`. O(n³) soa alarmante; **na escala real deste
sistema é irrelevante**, e o próprio handoff da Fase 6 já mediu isso:

| Tracker | frames/s (medido no handoff da Fase 6) |
|---|---|
| Kalman + greedy | ~15.200 |
| Kalman + húngaro | ~15.600 |
| `SingleEntityTracker` (controle) | ~630.000 |

O húngaro empatou (ligeiramente à frente, dentro do ruído) com o greedy. Motivo: `n` é o número
de **entidades simultâneas**, tipicamente 1–5, no máximo talvez algumas dezenas numa colmeia. Com
n=10, n³ = 1000 operações de ponto flutuante por frame — ~0,05 ms. Para o custo do húngaro se
igualar ao de um único `warpPerspective` a 1080p seria preciso **n ≈ 100+ entidades
simultaneamente visíveis**, um regime em que o gargalo científico (segmentar 100 abelhas
sobrepostas com subtração de fundo) explodiria muito antes do computacional.

**Conclusão: não substituir por `scipy.optimize.linear_sum_assignment`.** A dependência nova não
se paga, e a decisão original de manter os plugins livres de `scipy` continua correta. Se um dia
o número de entidades crescer uma ordem de magnitude, isto se torna 5 linhas de mudança e uma
dependência — trivial de fazer *quando* houver razão.

#### O18b. `PluginRegistry` / `importlib` não estão no caminho quente

`registry.discover()` + `for_kind()` são chamados **uma vez por run**, em `_run_metadata_plugins`
(`src/stages/orchestration.py:137`), **depois** de todos os frames terem sido processados.
`instantiate()` faz `importlib.util.spec_from_file_location` 2–4 vezes por run (speed, border, e
os exporters quando pedidos). Não há nenhum `registry.get()` dentro do laço de frames. A
ordenação topológica (Kahn com re-sort a cada iteração — O(n² log n)) roda sobre 2 plugins.
**Custo total: ruído de medição. Nada a fazer.**

#### O18c. Construção de modelos pydantic por frame não é gargalo

Medido: `Detection` + `Point2D` + `FrameDetections` = **0,0033 ms** por frame/view. Numa fixture
de 1200 frames × 2 views = ~8 ms sobre 1500 ms totais (~0,5%). A 1080p a fração cai ainda mais,
porque as operações de pixel crescem e a validação não. A escolha da Fase 3 de manter
`FramePair`/`RectifiedFrame` como **dataclasses** (fora do pydantic) já cobriu o caso que
realmente importaria — validar arrays de imagem por frame. **Nada a fazer.**

#### O18d. Fuse, `speed` e `border` são O(N) triviais

`Fusion.fuse`, `SpeedPlugin.run` e `BorderPlugin.run` percorrem `route.points` (N = frames) com
aritmética escalar. Para N = 18.000 (10 min a 30 fps) isso é da ordem de 10–50 ms **por run
inteiro**. Vetorizar em numpy (empilhar os pontos num array (N,3) e fazer `np.diff`+`np.linalg.
norm`) daria talvez 10× nesses milissegundos — **economizando dezenas de milissegundos num run
que leva minutos**. Não vale a legibilidade perdida nem o risco de mudar o resultado por ordem de
somatório diferente (o golden compara `distance_total` com tolerância 1e-4). **Não fazer.**

---

## 4. Shortlist priorizada

Ordenado por (impacto medido ÷ risco), considerando a escala real que o sistema processa hoje.

| # | Proposta | Impacto | Risco | Golden muda? |
|---|---|---|---|---|
| **1** | **O1** — retificar só os frames amostrados no passe 1 | ~20% do tempo total (medido); mais a 1080p | Mínimo (3 linhas, 1 plugin) | **Não** |
| **2** | **O9** — `cvtColor` antes do `warpPerspective` | 44% do estágio Rectify a 1080p, 68% a 720p (medido) | Baixo (2 linhas, 1 plugin) | Sim (±1 em uint8) |
| **3** | **O4** — máximo incremental no modelo de fundo | Memória O(duração) → O(1); ~450 MB → 2 MB em 1080p/30min | Mínimo (5 linhas, 1 plugin) | **Não** |
| **4** | **O5** — remover o segundo `threshold` (é identidade) | Pequeno mas gratuito; ~1,5 ms/par a 1080p | Praticamente zero | **Não** |
| **5** | **O10** — curto-circuito de warp identidade | ~20% do total *no caso sem pontos de perspectiva* (medido) | Muito baixo | Não (verificar bordas) |

**Nota de sequenciamento:** O1 + O4 + O5 + O10 juntos são um único PR pequeno, todos locais a
dois plugins, e **nenhum deles muda o golden** — ou seja, o próprio golden-file test valida a
mudança inteira de graça. Esse é o ponto de partida óbvio. O9 vem em seguida, isolado, junto com
a regeneração consciente do golden.

Candidatas fortes de segunda onda, dependentes de profiling em material real: **O2** (seek —
grande ganho, mas precisa de validação em codec long-GOP), **O11** (decode paralelo das duas
câmeras — recupera o paralelismo que a Fase 3 perdeu) e **O6** (morfologia — provavelmente
essencial assim que houver footage com vidro, e hoje impossível de justificar com a fixture
sintética).

---

## 5. NÃO faça isto ainda

Coisas que considerei e concluí serem otimização prematura **na escala real que este sistema
processa hoje** (um punhado de vídeos curtos de laboratório, 1 entidade, execução em desktop):

1. **Substituir o húngaro por `scipy.optimize.linear_sum_assignment`.** Medido: empata com o
   greedy em 15.600 frames/s com 2 entidades. `n` é o número de animais na caixa, não o número de
   frames. Adicionar `scipy` para isso é custo de dependência sem retorno. Ver O18.
2. **Vetorizar Fuse/speed/border em numpy.** São O(N) com constante minúscula; a economia é de
   dezenas de milissegundos num run de minutos, e o risco de mexer no somatório que o golden
   compara com 1e-4 é real. Ver O18d.
3. **Otimizar overhead de plugin/`importlib`/registry.** Roda 2–4 vezes por run, fora do caminho
   quente. Ver O18b.
4. **Substituir os modelos pydantic por dataclasses no caminho de detecção.** Medido em 0,5% do
   tempo. A Fase 3 já tomou a decisão certa onde importava (`FramePair`/`RectifiedFrame` são
   dataclasses). Ver O18c.
5. **Qualquer otimização do caminho CUDA (streams, pool de `GpuMat`, memória pinned, residência
   de frame na GPU).** O caminho **nunca foi executado** — não há OpenCV com módulo `cuda`
   disponível. Otimizar código que ninguém rodou é a forma mais pura de otimização prematura.
   A ordem correta é: (a) empacotamento CUDA funcionando → (b) O14 (wiring do orquestrador) →
   (c) **medir** → (d) só então O15/O16. Ver Grupo E.
6. **Reciclagem de buffers de decode (O12).** Ganho não medido e provavelmente pequeno; o custo
   é criar um contrato de aliasing ("o frame só vale até o próximo `next()`") que é uma armadilha
   para autores de plugin de terceiro — exatamente o público que o `docs/PLUGIN_CONTRACT.md`
   pretende atender.
7. **Multiprocessing.** Os dados que cruzariam a fronteira de processo são frames (MB por item).
   A única partição sensata (um processo por câmera) é o que O3/O11 já fazem com threads, mais
   barato, porque `cv2` libera a GIL. Ver O13.
8. **Processamento distribuído / batch em cluster / GPU multi-device.** A carga de trabalho é
   "dois arquivos de vídeo de laboratório num desktop". Fora de escala por várias ordens de
   grandeza.
9. **Trocar o algoritmo do detector (O8) sem footage real.** A fixture é um blob perfeito sobre
   fundo uniforme — ela **não consegue distinguir** um detector bom de um ruim. Trocar máximo
   estático por MOG2/mediana/threshold adaptativo é pesquisa que exige material real com ground
   truth, não uma decisão de performance. O que dá para fazer hoje sem material real é preparar o
   terreno: implementar os candidatos como **plugins alternativos**, não como substituição do
   default.

---

## 6. Lacunas honestas deste documento

- **Nenhum profiling real.** Cronometragem manual por fase e microbenchmarks de operação isolada
  não substituem `cProfile`/`py-spy` sobre um run de produção. As atribuições de tempo do §1.2
  são grosseiras (o instrumento mede o que eu escolhi medir).
- **Nenhum dado de produção.** Toda extrapolação para 720p/1080p usa microbenchmarks de operação
  isolada sobre arrays sintéticos, sem custo de decode de codec real, sem cache miss de working
  set grande, sem I/O de disco real.
- **Zero medição de GPU.** Todos os números do Grupo E são estimativas de largura de banda PCIe
  e de literatura. Trate-os como hipóteses a testar, não como previsões.
- **Máquina única.** Windows 11, 16 threads, `cv2 5.0.0`. O CI roda 3.11 com `opencv-python
  4.9.0.80`; custos relativos entre operações OpenCV podem diferir entre versões (o próprio
  handoff da Fase 3 já registra esse risco para o golden).
