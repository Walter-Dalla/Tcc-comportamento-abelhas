"""Helpers puros (Tk-free) de orientação de câmera/caixa (Fase 4).

Fonte única de verdade da validação de orientação, compartilhada entre a GUI
(`OrientationScreen`, workstream D) e a CLI (`animaltrack validate-config`,
workstream A) — as mensagens de erro em português são idênticas nos dois modos
(exigência do `ux-design-detalhado.md` seção 4).
"""

from __future__ import annotations

from src.core.schema.orientation import (
    BoxFace,
    BoxOrientationConfig,
    BoxVertex,
    CameraOrientation,
)

# Mensagens exatas (ux-design-detalhado.md seções 1.2 e 2.5) — não reescrever.
MSG_FACE_MISSING = "Selecione qual face da caixa esta câmera enxerga antes de continuar."
MSG_VERTEX_MISSING = "Selecione o vértice correspondente a todos os 4 pontos antes de finalizar."
MSG_VERTEX_DUPLICATE = "Cada ponto precisa apontar para um vértice diferente."
MSG_VERTICES_NOT_FACE = "Os 4 vértices selecionados não formam a face escolhida. Revise a seleção."
MSG_ORIENTATION_MISSING = "Orientação da câmera não configurada."

# Rótulos de face em português (ux-design-detalhado.md seção 2.3), mapeados 1:1 a BoxFace.
FACE_LABELS_PT: dict[BoxFace, str] = {
    BoxFace.TOP: "Topo",
    BoxFace.BOTTOM: "Base",
    BoxFace.LEFT: "Esquerda",
    BoxFace.RIGHT: "Direita",
    BoxFace.FRONT: "Frente",
    BoxFace.BACK: "Fundo",
}

# Rótulos de vértice legíveis para o combobox (ux-design-detalhado.md seção 2.4).
VERTEX_LABELS_PT: dict[BoxVertex, str] = {
    BoxVertex.TOP_FRONT_LEFT: "Topo-Frente-Esquerda",
    BoxVertex.TOP_FRONT_RIGHT: "Topo-Frente-Direita",
    BoxVertex.TOP_BACK_LEFT: "Topo-Fundo-Esquerda",
    BoxVertex.TOP_BACK_RIGHT: "Topo-Fundo-Direita",
    BoxVertex.BOTTOM_FRONT_LEFT: "Base-Frente-Esquerda",
    BoxVertex.BOTTOM_FRONT_RIGHT: "Base-Frente-Direita",
    BoxVertex.BOTTOM_BACK_LEFT: "Base-Fundo-Esquerda",
    BoxVertex.BOTTOM_BACK_RIGHT: "Base-Fundo-Direita",
}


def vertices_for_face(face: BoxFace) -> list[BoxVertex]:
    """Os exatamente 4 (dos 8) vértices que pertencem à face dada."""
    mapping: dict[BoxFace, list[BoxVertex]] = {
        BoxFace.TOP: [v for v in BoxVertex if v.name.startswith("TOP_")],
        BoxFace.BOTTOM: [v for v in BoxVertex if v.name.startswith("BOTTOM_")],
        BoxFace.FRONT: [v for v in BoxVertex if "_FRONT_" in v.name],
        BoxFace.BACK: [v for v in BoxVertex if "_BACK_" in v.name],
        BoxFace.LEFT: [v for v in BoxVertex if v.name.endswith("_LEFT")],
        BoxFace.RIGHT: [v for v in BoxVertex if v.name.endswith("_RIGHT")],
    }
    return mapping[face]


def validate_selection(
    face: BoxFace | None, vertices: list[BoxVertex | None]
) -> str | None:
    """Valida a seleção parcial de uma câmera (usada pela GUI). Retorna a 1ª
    mensagem de erro em português, ou None se a seleção estiver válida."""
    if face is None:
        return MSG_FACE_MISSING
    if any(v is None for v in vertices):
        return MSG_VERTEX_MISSING
    concrete = [v for v in vertices if v is not None]
    if len(set(concrete)) != len(concrete):
        return MSG_VERTEX_DUPLICATE
    if set(concrete) != set(vertices_for_face(face)):
        return MSG_VERTICES_NOT_FACE
    return None


def _validate_camera(camera: CameraOrientation) -> str | None:
    return validate_selection(camera.face_viewed, list(camera.corner_vertices))


def validate_orientation(config: BoxOrientationConfig | None) -> list[str]:
    """Valida uma orientação persistida (usada pela CLI). Lista de mensagens de
    erro em português (vazia se válida)."""
    if config is None:
        return [MSG_ORIENTATION_MISSING]
    errors: list[str] = []
    for role, camera in (("topo", config.top_camera), ("lado", config.side_camera)):
        error = _validate_camera(camera)
        if error is not None:
            errors.append(f"câmera {role}: {error}")
    return errors
