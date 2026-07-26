# PROGRESS — rearquitetura Comportamento Animal

Arquivo mestre de progresso. **Ler primeiro** ao retomar trabalho após perda de
contexto/token, antes de reabrir qualquer código. Referências: `ARCHITECTURE.md` (alvo) e
`docs/plans/fase<N>-detalhado.md` (planos por fase).

## Status por fase

| Fase | Descrição | Status | Handoff |
|---|---|---|---|
| 0 | Ferramental e fundação de pacote | ✅ done | [fase0-pacote-handoff.md](fase0-pacote-handoff.md) |
| 1 | Primitivas core: schema + workspace + store | ✅ done | [fase1-schema-store-handoff.md](fase1-schema-store-handoff.md) |
| 2 | Sistema de plugin + esqueleto de orquestração | ✅ done | [fase2-plugin-orquestracao-handoff.md](fase2-plugin-orquestracao-handoff.md) |
| 3 | Porta pipeline de cálculo pra estágios streaming | ✅ done | [fase3-integracao-handoff.md](fase3-integracao-handoff.md) |
| 4 | Interface dupla: CLI + GUI na mesma orquestração | ✅ done | [fase4-integracao-handoff.md](fase4-integracao-handoff.md) |
| 5 | Backends GPU (plugins puros) | 🟨 código feito, packaging CUDA pendente | [fase5-backends-gpu-handoff.md](fase5-backends-gpu-handoff.md) |
| 6 | Pesquisa e prontidão de marketplace | ✅ done | [A](fase6-tracker-spike-handoff.md) · [B](fase6-plugin-exemplo-handoff.md) · [C](fase6-marketplace-handoff.md) |
| — | UX audit (GUI real × `ux-design-detalhado.md`) | ✅ done | [ux-audit-gui-handoff.md](ux-audit-gui-handoff.md) |
| — | Otimização O1+O4+O5+O10 + bugs fps/speed/PDF | ✅ done | [otimizacao-bugs-handoff.md](otimizacao-bugs-handoff.md) |

## Próxima ação

**A rearquitetura 0→6 está COMPLETA em código** (mais a auditoria de UX pós-Fase 4,
seção abaixo). Todas as sete fases foram entregues e verificadas
(`pytest -m "not gpu"`: 311 passed após a auditoria; `ruff`/`mypy` limpos).
Não há próxima fase — o que resta são follow-ups pontuais, listados abaixo em ordem
de importância. Nenhum deles bloqueia o uso do sistema.

1. **Fase 5 — validação de CUDA em hardware real (única lacuna de execução do
   roadmap).** O caminho GPU foi escrito e verificado estruturalmente, mas **nunca
   executado**: nenhuma máquina/CI disponível tem OpenCV com módulo `cuda`. Falta
   montar `Dockerfile.cuda` + `docs/gpu-setup.md`, obter um `cv2` com CUDA e rodar
   `pytest -m gpu` de verdade (hoje pulam limpo). Ver
   [fase5-backends-gpu-handoff.md](fase5-backends-gpu-handoff.md). **É por isso que
   a Fase 5 segue marcada 🟨 e não `done`.**
2. **Decisões pendentes do dono, acumuladas** (nenhuma bloqueia código; todas já
   implementadas conforme a recomendação, faltando só o "ok"): 3 da Fase 1, 3 da
   Fase 4, o débito de manifest da Fase 5, e as 2 da Fase 6 (abaixo).
3. **Escolha do algoritmo de tracking de produção** — o spike da Fase 6 provou que a
   interface admite multi-entidade e comparou 2 candidatos, mas **não escolhe**
   (decisão explicitamente do dono). Ver
   [fase6-tracker-spike-handoff.md](fase6-tracker-spike-handoff.md).
4. **Restante do doc de pesquisa de otimização/metadados** (ver
   `docs/handoffs/next-agent-handout.md`): O1/O4/O5/O10 + bugs fps/speed/PDF já
   feitos ([handoff](otimizacao-bugs-handoff.md)). Falta: O9 (muda golden-file,
   precisa regeneração consciente), gap `setup(pctx)` nunca chamado em
   `run_cpu_analysis`, plugin de metadados `kinematics` (shortlist #1 do doc de
   metadados).

Fase 6 concluída: spike de tracker multi-animal (`kalman-greedy` e
`kalman-hungarian` como plugins reais atrás da MESMA interface `Tracker`, ambos
produzindo 2 `entity_id`s estáveis com 0 ID-switches através de uma oclusão real;
baseline colapsa em 1 id), plugin de exemplo `fish-body-fat-estimator`
(generalização de espécie + template para terceiros), `docs/PLUGIN_CONTRACT.md`
(contrato público) e `animaltrack plugin install/list/remove` com validação de
manifest antes de aceitar. Verificação da fase atendida: plugin externo criado fora
das raízes built-in é instalado, descoberto e **roda dentro de um `Pipeline.run`
real**, com sua métrica no `AnalysisResult`.

Fase 4 concluída: CLI Typer (`run`/`list-plugins`/`validate-config`) headless +
GUI refatorada (protocolo `Screen` único, dispatcher, marshalling via `after()` —
bug de thread-safety corrigido), nova `OrientationUi`, plugins exporter
(`route-plot`/`pdf-report`) com acesso defensivo, bugs #4/#5 corrigidos, launcher
fino. Botão "Processar vídeo" religado a `run_cpu_analysis` (mesmo caminho da CLI).
`pytest` 204 passed, `ruff`/`mypy` limpos, GUI abre sem erro de import.

## UX audit (pós-Fase 4)

Auditoria da GUI implementada contra `docs/plans/ux-design-detalhado.md` (escrito
ANTES da implementação da Fase 4), com correção das lacunas reais e **resolução da
pergunta em aberto da seção 6**. Detalhe em
[ux-audit-gui-handoff.md](ux-audit-gui-handoff.md). Resumo:

- Fluxo (seção 1.2): "Processar vídeo" ganhou as guardas do legado + a guarda de
  orientação das duas câmeras; "Finalizar perspectiva" passou a oferecer o
  auto-avanço opcional para a orientação daquela câmera; botão "Executar módulos de
  metadados" restaurado no hub (ligado a `Pipeline.run`).
- `OrientationScreen` (seção 2): as 6 faces do wireframe viraram **polígonos
  clicáveis** com nome PT (antes só havia combobox de face), a miniatura do 1º frame
  com os 4 pontos numerados foi implementada (era o incremento pendente da Fase 4),
  mais placeholder dos comboboxes, aviso de troca de face corrigido e o bug de
  layout (rótulo e combobox na mesma célula do grid).
- Seção 6 resolvida pela **Opção 2**: `DebugFrameWriter` grava frames amostrados do
  Detect em `<workspace>/debug/<perfil>/` a partir de uma thread própria com fila
  limitada (descarta em vez de bloquear), exposto por `animaltrack run
  --debug-frames` e pelos controles "Exportar frames de debug" / "Abrir pasta de
  debug" no hub. Nenhum `cv2.imshow`/`waitKey` reintroduzido.
- Verificação: `pytest` **311 passed, 3 skipped** (+32 testes), `ruff`/`mypy` limpos,
  smoke manual da GUI real feito (janela abre, `OrientationUi` navega e não quebra).

## Notas de acompanhamento abertas

- **Fase 1 — 3 decisões pendentes de confirmação do dono** (detalhe no
  [handoff da Fase 1](fase1-schema-store-handoff.md)): (a) adição de `profile.py`
  fora da lista literal; (b) política "TOP-camera-vence-empate" em `axis_mapping()`;
  (c) `Metric.value` como union estrito (mais restrito que a letra do plano, fiel à
  intenção). Todas implementadas conforme a recomendação; só falta o "ok" do dono.
- Confirmar com o dono a inclusão de `pillow` na lista oficial de deps do `ARCHITECTURE.md`
  (foi adicionada ao `pyproject.toml` na Fase 0 como correção factual — R4).
- Fase 0 deixou `extend-exclude` (ruff) e `ignore_errors` (mypy) sobre `src/Modules/**`;
  remover entrada a entrada conforme cada módulo legado é reescrito nas Fases 3-4.
- CI roda em Python 3.11 (onde os pins numpy/opencv têm wheel). Máquina local de dev com
  Python 3.13 precisa de versões substitutas dessas duas libs (ver handoffs Fase 0/1);
  rodar `mypy` local com `--python-version 3.13` para contornar stubs da numpy 2.5.
- **Fase 3 — golden gerado sob cv2 5.0.0/numpy 2.5.1 (local); CI fixa 4.9.0.80/1.26.3.** Se
  `tests/test_golden_pipeline.py` falhar no CI por diferença de centroide de `findContours`/
  `moments` entre versões do OpenCV, regenerar `tests/fixtures/golden/expected_result.json`
  sob o OpenCV do CI (reexecutar o pipeline e reserializar; os vídeos FFV1 não mudam).
  Detalhe no [handoff da Fase 3](fase3-integracao-handoff.md).
- **Fase 4 — 3 decisões a confirmar com o dono** (detalhe no
  [handoff da Fase 4](fase4-integracao-handoff.md)): (a) rotulagem PT no PDF segue a
  convenção real do schema (`Altura=box_cm.y`, `Profundidade=box_cm.z`), não o exemplo do
  plano que trocava y/z; (b) CLI/GUI chamam `run_cpu_analysis` (análise completa), com
  `Pipeline.run` mantido só para metadata como Fase 2/3 deixaram; (c) `SessionState` no
  `AppService` centraliza o estado antes espalhado entre telas. Todas seguem a recomendação
  do plano/schema; falta o "ok" do dono.
- **Fase 4 — `--config pipeline.toml` do CLI é aceito mas não parseado** (reservado para
  quando o `pipeline.toml` por perfil existir). A `OrientationScreen` implementa a forma
  técnica mínima (sem a miniatura de vídeo com pontos numerados da UX 2.1 — incremento
  opcional não bloqueante).
- **Fase 4 — deps `typer` e `xhtml2pdf`** já pinadas no `pyproject.toml` mas podem faltar em
  ambientes que só tinham as deps das fases anteriores; `pip install -e .[dev]` resolve.
- **Fase 5 — BLOQUEIO de empacotamento (não é código, é infra)**: o caminho CUDA foi escrito
  e verificado estruturalmente, mas NUNCA executado — nenhuma máquina/CI disponível tem um
  OpenCV com módulo `cuda` (o PyPI `opencv-python`/`opencv-contrib-python` não traz CUDA;
  confirmado: `cv2 5.0.0` local tem `cuda_GpuMat` mas não `cuda.warpPerspective`/
  `createBackgroundSubtractorMOG2`, e `getCudaEnabledDeviceCount()==0`). Próximo passo:
  `Dockerfile.cuda` + `docs/gpu-setup.md` (ver handoff Fase 5). Testes `gpu` pulam limpo até lá.
- **Fase 5 — débito de manifest**: `PluginRequires` (`extra="forbid"`) não expressa "precisa
  de build com CUDA". Não foi adicionado `requires.capabilities` para não mexer no schema/
  discovery da Fase 2 nesta fase; a exigência está nos comentários dos `plugin.toml` CUDA e no
  handoff. Confirmar com o dono se/quando formalizar o campo.
- **Fase 5 — decisão de produto JÁ confirmada (não reabrir)**: `require_cuda()` gate apenas
  `Pipeline.run`/caminho de análise, nunca boot da GUI ou telas de configuração.
- **Fase 6 — 2 decisões a confirmar com o dono**: (a) formalizar ou não a seção `[config]`
  no `plugin.toml` — NÃO foi implementada nesta fase para não mexer no schema/discovery de
  manifest da Fase 2 (mesmo critério do débito da Fase 5); o plugin de peixe usa o mecanismo
  já existente `setup(PipelineContext)` → `request.overrides`, com fallback por env var.
  (b) dar default ao parâmetro `view` do `SingleEntityTracker` (Fase 3) para ficar
  consistente com os candidatos novos — ver item abaixo.
- **Fase 6 — lacuna de contrato encontrada**: `PluginRegistry.instantiate()` constrói todo
  plugin com **zero argumentos**. O `SingleEntityTracker` exige `view` posicional e por isso
  **não é carregável pelo registry** (nunca apareceu porque `run_cpu_analysis` o importa
  direto). Os candidatos da Fase 6 dão default a `view` para contornar. Correção sugerida: 1
  linha no baseline. Documentado em `docs/PLUGIN_CONTRACT.md` seção 6.
- **Fase 6 — `pipeline.toml` ainda não existe**, então "trocar o tracker ativo via
  `pipeline.toml`" (tarefa 11 do plano da fase) NÃO foi cumprido na letra. O que foi provado
  é a forma mais forte que o código atual permite: os candidatos são carregados pelo registry
  e são drop-in por substituição direta do objeto, com teste travando isso. `run_cpu_analysis`
  segue construindo `SingleEntityTracker` hardcoded.
- **Fase 6 — fixture de vídeo (nível-integração) não gerada**: o critério "≥2 `entity_id`s
  estáveis" é atendido pela fixture de nível-unidade (`FrameDetections` sintéticas com oclusão
  real). Gerar o par de vídeos top/side exercitaria Detect+Track juntos; deixado de fora por
  custo de repo/tempo, sem prejuízo do critério de verificação da fase.
- **Fase 6 — candidato 3 (correspondência cross-câmera) não implementado** (era explicitamente
  *time-boxed* no plano). A premissa dele foi medida e confirmada (a view lateral distingue as
  duas entidades durante a oclusão do topo), mas implementá-lo **exigiria mudar a interface
  `Tracker`** — `update()` recebe uma view por vez. Achado arquitetural registrado no handoff A.
