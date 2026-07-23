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
| 4 | Interface dupla: CLI + GUI na mesma orquestração | ⬜ não iniciada | — |
| 5 | Backends GPU (plugins puros) | ⬜ não iniciada | — |
| 6 | Pesquisa e prontidão de marketplace | ⬜ não iniciada | — |

## Próxima ação

Iniciar **Fase 4** (Interface dupla: CLI + GUI na mesma orquestração). Ver
`ARCHITECTURE.md` seção "Fase 4" e `docs/plans/fase4-detalhado.md`. Ponto de entrada
único já pronto: `src.stages.orchestration.run_cpu_analysis(profile)` — a CLI
(`animaltrack run`) e o botão "Processar vídeo" da GUI devem chamá-lo. Pré-requisito
que falta e é o cerne da Fase 4: a tela **OrientationUi** que popula
`profile.orientation` (sem ela `run_cpu_analysis` levanta `ValueError`). Também na
Fase 4: refatorar `plotRoute`/`pdfFactory` p/ ler `AnalysisResult` novo, corrigir
bugs #4/#5, novo launcher `__init__.py`. Ver detalhes em
[fase3-integracao-handoff.md](fase3-integracao-handoff.md) → "Como retomar".

Fase 3 concluída: 5 estágios streaming (Capture/Rectify/Detect/Track/Fuse) +
orquestração, bugs #2/#3/#6 corrigidos, #1 obsoleto. Guard-rail golden-file
executado e verde (`tests/test_golden_pipeline.py`, 8/8). Legado de cálculo apagado.
`pytest` 175 passed, `ruff`/`mypy` limpos.

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
