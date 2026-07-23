"""Fixtures compartilhadas dos testes do core (Fase 1)."""

import pytest

from src.core.workspace import Workspace


@pytest.fixture
def tmp_workspace(tmp_path) -> Workspace:
    """Workspace apontando para um diretório temporário ainda inexistente.

    Os diretórios não são criados aqui — cada teste decide se chama
    `ensure_dirs()` (ou deixa as stores criarem sob demanda via atomic_write).
    """
    return Workspace(root=tmp_path / "ws")
