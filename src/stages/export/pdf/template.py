"""Renderização do HTML do relatório PDF (Fase 4), extraída para ser testável
sem tocar IO/pisa.

Acesso defensivo (a mudança-chave vs. `pdfFactory.py` legado): o legado acessava
`data['time_border_x']` etc. por `[]` direto — qualquer chave ausente (plugin de
metadata pulado por erro) derrubava a exportação com `KeyError`. Aqui as métricas
saem por `ctx.get_metric()` com placeholder `"N/D"`.

Mapeamento de eixo (fonte de verdade: `src/core/schema/orientation.py`, convenção
fixada na Fase 1): X = largura (LEFT/RIGHT), Y = altura (TOP/BOTTOM),
Z = profundidade (FRONT/BACK). Portanto Largura=box_cm.x, Altura=box_cm.y,
Profundidade=box_cm.z. (O exemplo do plano trocava y/z para altura/profundidade;
seguimos a convenção real do schema, não o exemplo.) `px_per_cm` vira 3 linhas
por eixo, substituindo a linha única "Razão Pixel para cm" do legado — o schema
da Fase 3 troca a razão-mediana única por um `Point3D` por eixo.
"""

from __future__ import annotations

from src.core.schema.result import AnalysisContext


def metric_value(ctx: AnalysisContext, name: str, default: str = "N/D") -> str:
    metric = ctx.get_metric(name)
    return str(metric.value) if metric is not None else default


def render_html(ctx: AnalysisContext, title: str) -> str:
    result = ctx.result
    calib = result.calibration
    frame_count = str(len(result.routes[0].points)) if result.routes else "N/D"
    rows = [
        ("Quantidade de frames", frame_count),
        ("Largura da Caixa (cm)", str(calib.box_cm.x)),
        ("Altura da Caixa (cm)", str(calib.box_cm.y)),
        ("Profundidade da Caixa (cm)", str(calib.box_cm.z)),
        ("Razão px/cm (X)", str(calib.px_per_cm.x)),
        ("Razão px/cm (Y)", str(calib.px_per_cm.y)),
        ("Razão px/cm (Z)", str(calib.px_per_cm.z)),
        ("FPS", str(calib.fps)),
        ("Tempo Borda X", metric_value(ctx, "time_border_x")),
        ("Tempo Borda Y", metric_value(ctx, "time_border_y")),
        ("Tempo Borda Z", metric_value(ctx, "time_border_z")),
    ]
    rows_html = "\n".join(
        f"                <tr><td>{key}</td><td>{value}</td></tr>" for key, value in rows
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dados do processamento: {title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ width: 50%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 10px; border: 1px solid #ccc; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1>Dados do processamento: {title}</h1>
    <table>
        <tr><th>Propriedade</th><th>Valor</th></tr>
{rows_html}
    </table>
</body>
</html>
"""
