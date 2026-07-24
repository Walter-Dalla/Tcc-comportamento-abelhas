"""Plugins de export (Fase 4) — refatoração de `ExportModule/{plotRoute,pdfFactory}.py`.

`route-plot` (matplotlib) e `pdf-report` (xhtml2pdf) viram plugins `exporter`
descobertos por `plugin.toml`, consumindo `AnalysisContext.get_metric()` de forma
defensiva (sem mais `KeyError` em métrica ausente). Este diretório é um dos roots
de busca do `PluginRegistry` (ver `src/app/plugins.py`).
"""


class ExportError(Exception):
    """Falha ao gerar um artefato de export (PDF/gráfico)."""
