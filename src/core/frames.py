"""Tipos de frame em memória que fluem entre os estágios de streaming (Fase 3).

`FramePair` e `RectifiedFrame` carregam imagens (`numpy.ndarray`) e por isso NÃO
são modelos pydantic (não são serializados, não cruzam fronteira de disco/JSON —
existem só em memória durante um run da pipeline). São `dataclass(frozen=True)`:
imutáveis, baratos, sem overhead de validação por frame.

`ARCHITECTURE.md`/`docs/plans/fase3-detalhado.md` referenciam `FramePair` como
"tipo fixado na Fase 1", mas ele não foi criado lá (o schema da Fase 1 só tem os
modelos serializáveis). Ele nasce aqui, na Fase 3, junto do primeiro estágio que
o produz (Capture). `stages.py` (Fase 2) já reservava o nome `RectifiedFrame` como
alias temporário `object` — agora ele aponta para este tipo real.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.core.schema.orientation import BoxOrientationConfig, CameraRole


@dataclass(frozen=True)
class FramePair:
    """Par de frames crus (BGR) já pareado por índice pelo Capture.

    O pareamento (lockstep) acontece dentro do Capture, não é adiado pro Fuse
    como no código legado — ver `docs/plans/fase3-detalhado.md` seção 2.2.
    """

    frame_index: int
    top: np.ndarray
    side: np.ndarray


@dataclass(frozen=True)
class RectifiedFrame:
    """Um frame retificado (perspectiva aplicada + grayscale) de uma única câmera.

    Carrega `role`/`orientation` como metadado que o Fuse vai precisar depois
    (via `axis_mapping()`); o Detect só usa `image`/`frame_index`/`role`.
    """

    image: np.ndarray
    role: CameraRole
    frame_index: int
    orientation: BoxOrientationConfig | None = None
