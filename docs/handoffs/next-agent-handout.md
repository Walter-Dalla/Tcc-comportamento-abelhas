# Handout — próximo agente de implementação

> Prompt pronto pra colar num novo agente (subagente ou sessão nova). Contexto
> auto-contido: não assume que quem lê já viu esta conversa.

---

## Contexto do projeto

Repo: `C:\Projetos\Tcc-comportamento-abelhas`. TCC (tese de graduação brasileira)
que virou plataforma de rastreamento 3D de insetos/animais a partir de 2 câmeras
sincronizadas (topo+lateral). Núcleo **sem IA** — extrai dado estruturado que
alimenta IA/análise **externa**. Rearquitetura completa (Fases 0-6) já está
mesclada em `main`: pipeline em camadas (Capture→Rectify→Detect→Track→Fuse→
Metadata→Export), sistema de plugin genérico (`plugin.toml`), schema Pydantic
v2, CLI+GUI na mesma orquestração, backends GPU (código feito, hardware CUDA
nunca testado), spike de tracker multi-animal, prontidão de marketplace.

Leia primeiro, nesta ordem:
1. `CLAUDE.md` — mapa geral.
2. `ARCHITECTURE.md` — arquitetura alvo completa.
3. `docs/handoffs/PROGRESS.md` — status real de cada fase + toda pendência aberta.
4. `docs/research/metadata-extraction-opportunities.md` — ~30 propostas de metadado
   extraível dos inputs/outputs atuais, com shortlist priorizada no fim.
5. `docs/research/processing-optimization-opportunities.md` — otimizações de
   processamento com medição real (não só leitura de código), shortlist no fim.

Esses dois últimos são pesquisa pura (nenhum código escrito ainda) — é o material
mais provável de virar a próxima rodada de trabalho real.

## Estado atual (confirme antes de agir — pode ter mudado)

`git log -1 main` deve mostrar `02fc13e` ou posterior (commit dos dois docs de
pesquisa). Se `git log -3` do seu worktree não bater com isso, `git merge --ff-only
main` primeiro.

`pytest -m "not gpu"` deve passar 311/311 (3 skip de GPU sem hardware CUDA),
`ruff check .` e `mypy src tests --python-version 3.13` limpos.

## O que fazer

Não existe "próxima fase" no roadmap 0-6 — está tudo mesclado. O trabalho que
resta cai em duas categorias:

### A) Decisões que só o dono do projeto pode confirmar (NÃO tente resolver sozinho)

Listadas em `docs/handoffs/PROGRESS.md`, seção "Notas de acompanhamento abertas".
Resumo: 3 decisões da Fase 1 (todas já implementadas conforme recomendação, só
falta "ok"), 3 da Fase 4, 1 débito de manifest da Fase 5, 2 da Fase 6, e a
escolha do algoritmo de tracking de produção (`kalman-greedy` vs
`kalman-hungarian` vs outro). Se seu prompt de trabalho não menciona
explicitamente uma dessas, **não as resolva** — apenas não as bloqueie.

### B) Trabalho que UM AGENTE PODE executar sem esperar decisão do dono

Estas são as candidatas concretas, extraídas das duas pesquisas — cada uma é
plugin-only ou correção local, baixo risco, não toca esqueleto congelado das
Fases 2/3:

**Do doc de otimização** (shortlist O1+O4+O5+O10 — PR pequeno, não muda o golden-file):
- O1: mover `rectify()` do passe 1 do Detect pra dentro do `if counter % 500` de
  amostragem (hoje retifica os 1200 frames pra montar background de só 3
  amostras — ~20% do tempo total do pipeline desperdiçado).
- O4: trocar `np.max` acumulado por máximo incremental (`np.maximum(..., out=acc)`)
  no background model — evita reter O(duração do vídeo) em memória.
- O5: remover o segundo `cv2.threshold` do detector (é no-op matemática depois
  do primeiro, verificado com `np.array_equal`).
- O10: curto-circuito de warp identidade quando não há correção de perspectiva
  real a aplicar.
- Separado (muda golden, precisa regeneração consciente): O9, inverter ordem
  cvtColor/warp no Rectify (44-68% mais rápido, mas ±1 nível de cinza de
  diferença — regenerar `tests/fixtures/golden/expected_result.json`).

**Bugs reais encontrados** (achados de leitura de código, não hipotéticos):
- `Capture` trunca fps com `int(cap.get(CAP_PROP_FPS))` (29.97→29, viés ~3% em
  toda velocidade calculada) e ignora o fps da câmera lateral sem checar a
  precondição documentada de fps igual entre as duas.
- `plugins/speed/plugin.py` usa `zip(indices, indices[1:])` sem checar
  contiguidade — um gap de N frames é tratado como se fosse 1 frame.
- `src/stages/export/pdf/template.py:31` rotula `len(routes[0].points)` como
  "Quantidade de frames" — na verdade é frames com reconstrução bem-sucedida,
  não o total do vídeo (não existe `frame_count` em lugar nenhum do schema hoje).

**Do doc de metadados, item #1 da shortlist** (zero mudança de pipeline, plugin
`metadata` novo lendo `AnalysisResult`/`Route3D` já existente): plugin único
`kinematics` — aceleração, jerk, ângulos de virada, tortuosidade/MSD, bouts de
repouso, latência ao primeiro movimento. Fecha objetivos do `README.md` nunca
atingidos.

**Achado de gap de configuração** (bloqueia quase toda métrica com limiar):
`run_cpu_analysis` (`src/stages/orchestration.py`) chama só `plugin.run(ctx)`,
nunca `setup(pctx)` — por isso `ctx.request.overrides` é inacessível no caminho
real CLI/GUI e o plugin `fish-body-fat` precisa de env var como workaround. Vale
avaliar corrigir isso já, é pequeno e destrava configuração de plugin de verdade.

## Processo esperado

1. Leia tudo da seção "Contexto" antes de tocar código.
2. Escolha um escopo coerente (não tente fazer as duas pesquisas inteiras de
   uma vez — o dono decide o recorte quando lançar o próximo agente; se você
   está lendo isto como instrução literal de escopo, priorize o PR pequeno de
   otimização O1+O4+O5+O10+bugs de fps/speed/PDF primeiro, é o menor risco e
   maior clareza de valor).
3. Rode `pytest`, `ruff check .`, `mypy src tests --python-version 3.13`
   com frequência (ambiente de dev é Python 3.13; pins de numpy/opencv não têm
   wheel pra 3.13 — usar versões substitutas como as fases anteriores fizeram).
4. Commits incrementais, nunca `--amend`.
5. Escreva `docs/handoffs/<escopo>-handoff.md` seguindo o template já usado em
   todo handoff anterior (Status/O que foi feito/O que falta/Como
   verificar/Como retomar) e atualize `docs/handoffs/PROGRESS.md`.
6. Não mescle em `main` sozinho — isso fica com quem orquestra (o dono ou o
   agente principal que revisa antes do merge).
