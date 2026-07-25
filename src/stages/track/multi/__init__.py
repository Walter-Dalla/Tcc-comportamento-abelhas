"""Biblioteca compartilhada do spike de tracker multi-animal (Fase 6, workstream A).

Contém as peças reutilizadas pelos dois plugins `tracker` candidatos
(`plugins/tracker/kalman-greedy`, `plugins/tracker/kalman-hungarian`):

- `kalman.KalmanPointTracker` — filtro de Kalman de velocidade constante para um
  ponto 2D (estado `[x, y, vx, vy]`), usado para PREDIZER a posição de cada
  entidade durante oclusão (o que permite reassociar o mesmo `entity_id` quando a
  entidade reaparece).
- `assignment.greedy` / `assignment.hungarian` — as duas estratégias de associação
  detecção→track comparadas pelo spike. Ambas puras (sem `scipy`) para o plugin não
  arrastar dependência nova (ver handoff `fase6-tracker-spike`).
- `base.MultiEntityTracker` — implementa o contrato `Tracker` (`update`/`tracks`/
  `reset`) do `src/core/stages.py` EXATAMENTE como o `SingleEntityTracker` baseline,
  parametrizado pela estratégia de associação. É a prova de que a interface já
  fixada admite múltiplas entidades sem tocar em schema/Detect/Fuse.

IMPORTANTE (enquadramento do spike): a QUALIDADE do algoritmo não é o ponto — o
ponto é provar drop-in-extensibilidade da interface. Ver `docs/plans/fase6-detalhado.md`
seção 1.1 e o handoff do workstream.
"""
