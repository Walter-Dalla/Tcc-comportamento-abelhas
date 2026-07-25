"""Candidato 2 do spike: Kalman + assignment húngaro (Fase 6, workstream A).

Plugin `tracker` que implementa o contrato `Tracker` (`update`/`tracks`/`reset`)
de `src/core/stages.py`, IDÊNTICO em assinatura ao `SingleEntityTracker` baseline
(mesmo `__init__(view)`). Difere do candidato 1 SÓ na estratégia de associação:
usa o algoritmo húngaro (assignment globalmente ótimo) em vez do greedy, com a
posição prevista pelo Kalman como referência de custo.

A lógica mora em `src/stages/track/multi/` (compartilhada com o candidato 1). A
qualidade do algoritmo NÃO é o critério de sucesso do spike — provar a interface
é. Ver `docs/handoffs/fase6-tracker-spike-handoff.md`.

`view` tem DEFAULT porque `PluginRegistry.instantiate()` constrói todo plugin com
zero argumentos (`plugin_cls()`); um `tracker` sem default não é carregável pelo
registry. O orquestrador, que precisa de um tracker POR view, constrói explicitamente
`KalmanHungarianTracker("side")`. Ver `docs/PLUGIN_CONTRACT.md` (construtor zero-arg).
"""

from __future__ import annotations

from typing import Literal

from src.stages.track.multi.assignment import hungarian
from src.stages.track.multi.base import MultiEntityTracker


class KalmanHungarianTracker(MultiEntityTracker):
    def __init__(self, view: Literal["top", "side"] = "top") -> None:
        super().__init__(view, hungarian)
