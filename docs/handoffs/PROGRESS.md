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
| 5 | Backends GPU (plugins puros) | ⬜ não iniciada | — |
| 6 | Pesquisa e prontidão de marketplace | ⬜ não iniciada | — |

## Próxima ação

Iniciar **Fase 5** (backends GPU) e/ou **Fase 6** (marketplace + tracker multi-animal)
— podem rodar em paralelo (ARCHITECTURE.md: 5 e 6 são plugins aditivos sobre o
esqueleto já estável). Fase 5: `CudaPerspectiveRectifier`/`CudaMOG2Detector` +
`ArrayBackend` + `gpu.py` com gate obrigatório (probe só em `Pipeline.run`, nunca no
boot da GUI). Fase 6: spike de tracker multi-animal atrás da interface `Tracker` já
fixada, plugin de exemplo (peixe), `docs/PLUGIN_CONTRACT.md` + `animaltrack plugin install`.

Fase 4 concluída: CLI Typer (`run`/`list-plugins`/`validate-config`) headless +
GUI refatorada (protocolo `Screen` único, dispatcher, marshalling via `after()` —
bug de thread-safety corrigido), nova `OrientationUi`, plugins exporter
(`route-plot`/`pdf-report`) com acesso defensivo, bugs #4/#5 corrigidos, launcher
fino. Botão "Processar vídeo" religado a `run_cpu_analysis` (mesmo caminho da CLI).
`pytest` 204 passed, `ruff`/`mypy` limpos, GUI abre sem erro de import.

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
