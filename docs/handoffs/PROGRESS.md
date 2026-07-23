# PROGRESS — rearquitetura Comportamento Animal

Arquivo mestre de progresso. **Ler primeiro** ao retomar trabalho após perda de
contexto/token, antes de reabrir qualquer código. Referências: `ARCHITECTURE.md` (alvo) e
`docs/plans/fase<N>-detalhado.md` (planos por fase).

## Status por fase

| Fase | Descrição | Status | Handoff |
|---|---|---|---|
| 0 | Ferramental e fundação de pacote | ✅ done | [fase0-pacote-handoff.md](fase0-pacote-handoff.md) |
| 1 | Primitivas core: schema + workspace + store | ✅ done | [fase1-schema-store-handoff.md](fase1-schema-store-handoff.md) |
| 2 | Sistema de plugin + esqueleto de orquestração | ⬜ não iniciada | — |
| 3 | Porta pipeline de cálculo pra estágios streaming | ⬜ não iniciada | — |
| 4 | Interface dupla: CLI + GUI na mesma orquestração | ⬜ não iniciada | — |
| 5 | Backends GPU (plugins puros) | ⬜ não iniciada | — |
| 6 | Pesquisa e prontidão de marketplace | ⬜ não iniciada | — |

## Próxima ação

Iniciar **Fase 2** (sistema de plugin + esqueleto de orquestração): `src/core/plugin.py`,
`plugin_registry.py`, `pipeline.py`, `stages.py`, `errors.py`, + plugins `speed`/`border`
(adapters finos) e `gpu.py` (stub, paralelo). Ver `ARCHITECTURE.md` seção "Fase 2" e
`docs/plans/fase2-detalhado.md`. O schema da Fase 1 (`AnalysisContext`, `AnalysisResult`,
`Metric`, `BorderRegion`, `Calibration`, `Route3D`, `Workspace`, `ResultStore`,
`SCHEMA_VERSION`) já está exposto e consumível — ver handoff da Fase 1.

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
