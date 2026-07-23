"""Vocabulário de exceção compartilhado do subsistema de plugin (Fase 2).

Arquivo novo (não citado literalmente no `ARCHITECTURE.md`, adicionado por
necessidade de implementação, conforme o plano detalhado da Fase 2): `plugin.py`,
`plugin_registry.py` e `pipeline.py` precisam de tipos de exceção próprios sem
risco de import circular — por isso ficam isolados aqui, sem importar nenhum
outro módulo do core.
"""

from __future__ import annotations


class PluginError(Exception):
    """Erro base de todo o subsistema de plugin."""


class PluginManifestError(PluginError):
    """plugin.toml malformado ou faltando campo obrigatório."""


class PluginApiVersionError(PluginError):
    """Plugin declara api_version fora do que o PluginRegistry suporta."""


class PluginSchemaVersionError(PluginError):
    """Plugin declara schema (range) incompatível com SCHEMA_VERSION atual."""


class PluginContractError(PluginError):
    """Classe apontada por `entry` não é subclasse de Plugin, ou não é subclasse
    da classe-base exigida pelo kind declarado (ex.: kind=metadata exige
    MetadataPlugin)."""


class PluginNotFoundError(PluginError):
    """PluginRegistry.get(kind, name) chamado para um (kind, name) não descoberto."""


class PluginOrderingCycleError(PluginError):
    """Ciclo detectado entre before/after de um conjunto de plugins do mesmo kind.

    Erro de configuração — NÃO é isolado por plugin, propaga para fora de
    `for_kind()`/`Pipeline.run()`.
    """


class PluginLoadError(PluginError):
    """Falha ao importar o módulo do entry point ou ao instanciar a classe (cls())."""
