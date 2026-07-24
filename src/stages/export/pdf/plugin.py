"""Plugin `pdf-report` (kind=exporter) — porta `ExportModule/pdfFactory.py`.

Renderiza uma tabela-resumo (contagem de frames, dimensões da caixa, razões
px/cm por eixo, fps, tempos de borda) para PDF via xhtml2pdf. Métricas ausentes
viram `"N/D"` em vez de derrubar a exportação com `KeyError` (ver template.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from src.core.plugin import Plugin, PluginManifest
from src.core.schema.result import AnalysisContext
from src.core.workspace import Workspace
from src.stages.export import ExportError
from src.stages.export.pdf.template import render_html


class PdfReportExporter(Plugin):
    manifest: ClassVar[PluginManifest]

    def export(self, ctx: AnalysisContext, workspace: Workspace, **kwargs: object) -> Path:
        from xhtml2pdf import pisa

        title = ctx.result.profile
        html = render_html(ctx, title=title)
        out = workspace.outputs / ctx.result.profile / "report.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("wb") as f:
            status = pisa.CreatePDF(html, dest=f)
        if status.err:
            raise ExportError(f"xhtml2pdf falhou para o perfil '{title}'")
        return out
