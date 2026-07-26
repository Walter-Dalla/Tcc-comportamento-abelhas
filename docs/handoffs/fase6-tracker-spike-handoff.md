# Handoff: Fase 6 — Workstream A (spike de tracker multi-animal)
Status: done (critério de interface atingido; escolha de algoritmo **decidida pelo dono em
2026-07-26 — ver seção "Decisão do dono" abaixo**)
Última atualização: 2026-07-26

Este documento acumula o **relatório comparativo** pedido na tarefa 10 do plano
(`docs/plans/fase6-detalhado.md`, seção 1.5) além do handoff normal.

## O que foi feito

### Enquadramento (o que o spike prova, e o que NÃO prova)

**Prova**: a interface `Tracker` (`update`/`tracks`/`reset`), fixada na Fase 2 e
usada pelo `SingleEntityTracker` da Fase 3, **admite tracking multi-entidade com
oclusão sem nenhuma alteração** em schema (`Detection`/`FrameDetections`/`Track`/
`Route3D`), no estágio `Detect`, no `Fuse`, nem no contrato abstrato. Dois plugins
`tracker` novos rodam atrás da mesma interface, construídos e consumidos
exatamente como o baseline.

**NÃO prova / não decide**: qual algoritmo o produto deve usar. Isso continua
pesquisa aberta por decisão explícita do dono (`ARCHITECTURE.md`: *"Algoritmo
continua em aberto — o ponto é provar que a interface admite"*). As métricas abaixo
são **informativas**, não gate de aceite.

### Biblioteca compartilhada (`src/stages/track/multi/`)
- `kalman.py` — `KalmanPointTracker`: filtro de Kalman de velocidade constante para
  um ponto 2D (estado `[x, y, vx, vy]`, `dt=1` frame), em numpy puro. Serve para
  prever a posição de cada entidade e "segurar" a identidade durante oclusão.
- `assignment.py` — as duas estratégias comparadas, **ambas puras, sem `scipy`**
  (decisão: não arrastar dependência nova para um spike; o algoritmo húngaro
  O(n³) com potenciais está implementado à mão, ~50 linhas):
  - `greedy(cost, gate)` — pega repetidamente o par de menor custo global;
  - `hungarian(cost, gate)` — assignment ótimo, com padding a matriz quadrada.
  Ambas devolvem `(matches, unmatched_tracks, unmatched_dets)` e respeitam um
  `gate` de distância máxima.
- `base.py` — `MultiEntityTracker`: a máquina de tracking (predizer → custo →
  associar → corrigir → nascer/aposentar tracks), parametrizada pela estratégia.
  `max_distance=60`, `max_age=12` frames de tolerância a oclusão, `min_hits=3`
  para descartar ids fantasmas.

### Os dois candidatos, como plugins reais
- `plugins/tracker/kalman-greedy/` — candidato 1 (Kalman + greedy).
- `plugins/tracker/kalman-hungarian/` — candidato 2 (Kalman + húngaro).

Ambos com `plugin.toml` descoberto pelo `PluginRegistry`, `kind="tracker"`,
validados contra a classe-base `Tracker`.

### Fixture e harness (`tests/fixtures/tracker/`)
- `trajectories.py` — **fonte única de verdade** das trajetórias paramétricas. A
  correção da auditoria do plano está aplicada: A e B compartilham a **mesma
  baseline vertical com fase oposta**, então de fato convergem. A janela de oclusão
  é **calculada da geometria**, não hardcoded — resultado: **frames 63–66**.
- `gen_synthetic_detections.py` — gera `FrameDetections` por frame para as duas
  views + `ground_truth.json`. Durante a oclusão as duas detecções do topo
  **colapsam numa única** `Detection` (centróide médio, bbox união), replicando o
  que o `BackgroundSubtractionDetector` real veria num contorno de dois blobs
  sobrepostos. A view lateral mantém as duas separadas.
- `metrics.py` — harness: taxa de ID-switch, fragmentação, recuperação
  pós-oclusão, ids estáveis. Marca explicitamente o **caso degenerado**: um tracker
  que produz menos tracks que entidades-verdade recebe uma `note` avisando que
  suas métricas de identidade são trivialmente "perfeitas" por ausência de
  capacidade, não por qualidade.

## Decisão do dono (2026-07-26): `kalman-hungarian` em produção

O dono decidiu: **`kalman-hungarian` (candidato 2) vai para produção**, substituindo o
`SingleEntityTracker` hardcoded em `run_cpu_analysis` (`src/stages/orchestration.py`).

Mecanismo de wiring escolhido: **NÃO** um import do diretório hifenizado
`plugins/tracker/kalman-hungarian/` (esse caminho não é um módulo Python válido e só é
carregado via `PluginRegistry` + `importlib.util.spec_from_file_location`, que é o caminho de
plugin de terceiro, não de import estático em código de produção). Em vez disso,
`orchestration.py` importa `MultiEntityTracker` (`src/stages/track/multi/base.py`) e a
estratégia `hungarian` (`src/stages/track/multi/assignment.py`) diretamente e constrói
`MultiEntityTracker(view, hungarian)` inline — reproduzindo exatamente o que
`KalmanHungarianTracker.__init__` faz (`super().__init__(view, hungarian)`), sem inventar um
mecanismo de import para um caminho que nunca foi pensado para isso.

Nenhum parâmetro de tuning (`max_distance=60`, `max_age=12`, `min_hits=3`) precisou de
override: `tests/test_golden_pipeline.py` (movimento lento, ~0.3px/frame, bem abaixo do gate) e
`tests/test_debug_frames.py` passam sem alteração de golden — o `min_hits=3` não perde frames
porque `MultiEntityTracker.tracks()` acumula `points` desde a criação do track (sem janela
deslizante), então uma entidade rastreada continuamente desde o frame 0 expõe TODOS os seus
pontos assim que cruza o limiar de 3 hits. Nenhuma regressão numérica observada: a suíte
golden roda idêntica porque o `Detect` atual (`BackgroundSubtractionDetector`) sempre devolve no
máximo 1 detecção por frame, e o Kalman só participa da predição de custo de associação —
o ponto gravado em `track.points[frame]` é sempre o centróide bruto da detecção, nunca o
estado filtrado (verificado em `src/stages/track/multi/base.py::MultiEntityTracker.update`).

O item "Nenhum orquestrador usa os candidatos" na seção "O que falta" abaixo está **superado**
por esta decisão — mantido só como registro histórico do estado do spike antes da decisão.

## Relatório comparativo (fixture de 150 frames, 2 entidades, oclusão nos frames 63–66)

| Candidato | Tracks | IDs estáveis | ID-switches | Taxa | Fragmentação | Recuperação pós-oclusão | Perf. (frames/s) |
|---|---|---|---|---|---|---|---|
| **1. Kalman + greedy** | 2 | `[0, 1]` | 0 | 0.000 | 1 | A ✅, B ✅ | ~15.200 |
| **2. Kalman + húngaro** | 2 | `[0, 1]` | 0 | 0.000 | 1 | A ✅, B ✅ | ~15.600 |
| *Controle*: `SingleEntityTracker` | 1 | `[0]` | — | — | — | — | ~630.000 |

**Leitura honesta destes números:**

- **Ambos os candidatos atingem a barra sugerida** do plano (ID-switch = 0 no
  cruzamento, fragmentação ≤ 1 por entidade). A fragmentação 1 é **esperada e
  correta**: durante a oclusão só existe UMA detecção, então uma das duas entidades
  fica legitimamente sem ponto por 4 frames — um buraco em `Track.points`, que é
  exatamente como o schema representa oclusão. Uma entidade sai com 150 pontos, a
  outra com 146.
- **O empate entre greedy e húngaro não significa que sejam equivalentes.** Esta
  fixture tem 2 entidades e uma oclusão limpa — um cenário em que o greedy não
  chega a errar. A vantagem teórica do húngaro (resolver disputa simultânea de
  várias detecções por vários tracks) **só apareceria em cenários mais densos**,
  que esta fixture não cobre. Não conclua "greedy basta" a partir desta tabela.
- **A linha do baseline não é uma comparação de qualidade** — é o controle que
  mostra por que o spike importa: ele colapsa as duas entidades num único
  `entity_id=0`. As colunas de switch/recuperação ficam vazias porque não há
  identidade a trocar. O harness sinaliza isso via `TrackerMetrics.notes`.
- **A performance é irrelevante nesta escala** (poucos blobs por frame, tudo
  ordens de magnitude acima de tempo real). Está registrada só por completude; não
  use como critério de escolha.

### Candidato 3 (correspondência cross-câmera) — *time-boxed, não implementado*

Conforme previsto no plano (tarefa 9: explicitamente time-boxed, "medir o que
der"), o candidato 3 **não foi implementado como plugin**. O que foi medido:

> A view lateral da fixture mantém **2 tracks com ponto em todos os frames
> 63–66** — isto é, durante a janela em que a view de topo vê um blob único, a
> lateral ainda distingue as duas entidades.

Isso **confirma a premissa** do candidato 3 (existe informação independente na
outra câmera capaz de desambiguar identidade durante a oclusão), mas **não mede o
candidato em si** — nenhuma lógica de correspondência entre views foi escrita.

Custo real de implementá-lo, para quem retomar: exige acesso à calibração/
`axis_mapping()` **no momento do tracking**, o que acopla Track e Fuse mais do que
a interface `Tracker` hoje assume (`update` recebe uma `FrameDetections` de UMA
view por vez — não há ponto de entrada para as duas simultaneamente). **Esse é o
achado arquitetural mais relevante do spike**: os candidatos 1 e 2 são drop-in; o
candidato 3 **exigiria mudança de interface**.

*(Nota de rodapé, como o plano pede: tracking por aparência/re-identificação visual
via embeddings foi deixado fora dos candidatos por contrariar a decisão de manter o
núcleo sem IA embutida.)*

## O que falta

- **Decisão do dono: qual algoritmo vai para produção — RESOLVIDO em 2026-07-26**,
  ver seção "Decisão do dono" acima. `kalman-hungarian` está em produção.
- **Candidato 3** — não implementado (ver acima). Se for perseguido, decidir antes
  se a interface `Tracker` muda para receber as duas views.
- **Fixture de vídeo (nível-integração, seção 1.2b do plano)** — **não gerada**. A
  verificação obrigatória da fase (≥2 `entity_id`s estáveis) é atendida pela
  fixture de nível-unidade, que exercita o `Tracker` diretamente com as mesmas
  trajetórias. Gerar um par de vídeos top/side exercitaria também Detect+Track
  juntos; foi deixado de fora por custo de repo/tempo, sem prejuízo do critério.
- ~~Nenhum orquestrador usa os candidatos.~~ **Superado em 2026-07-26**:
  `run_cpu_analysis` agora constrói `MultiEntityTracker(view, hungarian)` (ver
  "Decisão do dono" acima) em vez de `SingleEntityTracker`. Isso continua sendo
  construção direta em código (não via `pipeline.toml`, que ainda não existe — a
  Fase 4 deixou `--config pipeline.toml` aceito mas não parseado). A tarefa 11 do
  plano, na letra ("trocar o plugin ativo apenas via `pipeline.toml`"), **segue
  não cumprida**; o mecanismo real usado foi construção direta da classe
  compartilhada (`MultiEntityTracker` + `hungarian`), não descoberta pelo registry
  em runtime de produção (o registry continua sendo o caminho usado pelos testes
  de interface deste spike, não pelo orquestrador).
- **Lacuna de contrato encontrada**: `PluginRegistry.instantiate()` constrói todo
  plugin com **zero argumentos**. Os candidatos dão default a `view` por isso. O
  `SingleEntityTracker` da Fase 3 exige `view` posicional e portanto **não é
  carregável pelo registry hoje** — nunca apareceu porque a orquestração o importa
  direto. Confirmar com o dono se o baseline deve ganhar default (1 linha) para
  ficar consistente.

## Como verificar o que já foi feito

```bash
pytest tests/test_tracker_multi_entity.py -q     # 18 passed
pytest -q -m "not gpu"                           # suíte inteira: 279 passed
ruff check .                                     # limpo
mypy src tests --python-version 3.13             # limpo

# regenerar o ground truth (imprime a janela de oclusão calculada)
python -m tests.fixtures.tracker.gen_synthetic_detections
```

Os testes cobrem: a fixture realmente cruza e oclui (guarda-corpo contra o bug que
a auditoria do plano corrigiu), ≥2 `entity_id`s estáveis por candidato, ausência de
ids fantasma, o baseline colapsando em 1 id, limiares tolerantes de qualidade,
conformidade com a ABC `Tracker`, `reset`, detecções vazias, drop-in vs. baseline,
e descoberta/instanciação pelo registry.

## Como retomar

1. Ler este relatório e a seção 1 do `docs/plans/fase6-detalhado.md`.
2. O ponto de entrada do algoritmo é `src/stages/track/multi/base.py`; para testar
   uma estratégia nova de associação, escreva uma função com a assinatura
   `(cost, gate) -> (matches, unmatched_tracks, unmatched_dets)` em
   `assignment.py`, crie um `plugins/tracker/<nome>/` apontando para ela e
   acrescente o nome à tupla `CANDIDATES` em `tests/test_tracker_multi_entity.py`
   — toda a bateria de testes passa a rodar contra ele automaticamente.
3. Para cenários mais duros (3+ entidades, oclusões múltiplas), estenda
   `trajectories.py` com uma entidade C e regenere o ground truth; o harness de
   métricas já é agnóstico ao número de entidades.
