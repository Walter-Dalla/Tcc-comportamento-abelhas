"""Candidato 1 do spike: Kalman + associação greedy (Fase 6, workstream A).

Plugin `tracker` que implementa o contrato `Tracker` (`update`/`tracks`/`reset`)
de `src/core/stages.py`, IDÊNTICO em assinatura ao `SingleEntityTracker` baseline
(mesmo `__init__(view)`), provando que a interface já fixada admite tracking
multi-entidade sem mudar schema/Detect/Fuse.

A lógica mora em `src/stages/track/multi/` (compartilhada com o candidato 2); aqui
só se escolhe a estratégia de associação (greedy). A qualidade do algoritmo NÃO é
o critério de sucesso do spike — provar a interface é. Ver
`docs/handoffs/fase6-tracker-spike-handoff.md`.

`view` tem DEFAULT porque `PluginRegistry.instantiate()` constrói todo plugin com
zero argumentos (`plugin_cls()`); um `tracker` sem default não é carregável pelo
registry. O orquestrador, que precisa de um tracker POR view, constrói explicitamente
`KalmanGreedyTracker("side")`. Ver `docs/PLUGIN_CONTRACT.md` (construtor zero-arg).
"""

from __future__ import annotations

from typing import Literal

from src.stages.track.multi.assignment import greedy
from src.stages.track.multi.base import MultiEntityTracker


class KalmanGreedyTracker(MultiEntityTracker):
    def __init__(self, view: Literal["top", "side"] = "top") -> None:
        super().__init__(view, greedy)
