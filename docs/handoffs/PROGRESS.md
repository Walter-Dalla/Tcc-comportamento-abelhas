# PROGRESS — rearquitetura Comportamento Animal

Arquivo mestre de progresso. **Ler primeiro** ao retomar trabalho após perda de
contexto/token, antes de reabrir qualquer código. Referências: `ARCHITECTURE.md` (alvo) e
`docs/plans/fase<N>-detalhado.md` (planos por fase).

## Status por fase

| Fase | Descrição | Status | Handoff |
|---|---|---|---|
| 0 | Ferramental e fundação de pacote | ✅ done | [fase0-pacote-handoff.md](fase0-pacote-handoff.md) |
| 1 | Primitivas core: schema + workspace + store | ⬜ não iniciada | — |
| 2 | Sistema de plugin + esqueleto de orquestração | ⬜ não iniciada | — |
| 3 | Porta pipeline de cálculo pra estágios streaming | ⬜ não iniciada | — |
| 4 | Interface dupla: CLI + GUI na mesma orquestração | ⬜ não iniciada | — |
| 5 | Backends GPU (plugins puros) | ⬜ não iniciada | — |
| 6 | Pesquisa e prontidão de marketplace | ⬜ não iniciada | — |

## Próxima ação

Iniciar **Fase 1** (schema + workspace + store). Ver `ARCHITECTURE.md` seção "Fase 1" e
`docs/plans/fase1-detalhado.md`. Workstreams paralelizáveis desde t0:
`geometry+detection+track+route` / `orientation.py` / `workspace.py`; `profile.py`+`result.py`
(Wave 2) esperam a Wave 1; `store.py` (Wave 3) espera a Wave 2.

## Notas de acompanhamento abertas

- Confirmar com o dono a inclusão de `pillow` na lista oficial de deps do `ARCHITECTURE.md`
  (foi adicionada ao `pyproject.toml` na Fase 0 como correção factual — R4).
- Fase 0 deixou `extend-exclude` (ruff) e `ignore_errors` (mypy) sobre `src/Modules/**`;
  remover entrada a entrada conforme cada módulo legado é reescrito nas Fases 3-4.
- CI roda em Python 3.11 (onde os pins numpy/opencv têm wheel). Máquina local de dev com
  Python 3.13 precisa de versões substitutas dessas duas libs — ver handoff da Fase 0.
