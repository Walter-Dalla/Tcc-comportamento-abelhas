# Fase 4 — Interface dupla: CLI + GUI na mesma orquestração (plano detalhado)

> Depende de: Fase 2 (`Plugin`, `PluginRegistry`, `Pipeline.run`) e Fase 3 (estágios streaming, `Calibration`
> via `axis_mapping()`, schema `AnalysisResult`/`AnalysisContext` estável) já concluídas e estáveis. Este
> plano trata os tipos abaixo como **contrato fixo, somente leitura** para todos os workstreams desta fase:
> `RunRequest`, `RunResult`, `Pipeline.run`, `AnalysisContext`/`AnalysisResult`/`Calibration`,
> `PluginRegistry`, `ProfileStore`/`ResultStore`, `Workspace`. Nenhum workstream de Fase 4 redesenha esses
> tipos — apenas os consome. Se algum desses contratos ainda não estiver congelado quando a Fase 4 começar,
> **pare e resolva isso primeiro** (não é trabalho desta fase).

## 0. Pré-requisito sequencial — "Fase 4.0": contrato compartilhado

Antes de disparar os 4 workstreams paralelos, um único agente executa, sequencialmente, a fixação das
interfaces que mais de um workstream consome. Isso não é "mais uma feature" — é o motivo pelo qual GUI e
OrientationUi podem rodar em paralelo sem conflito de arquivo/contrato (mesmo raciocínio do
`ARCHITECTURE.md` para a Fase 2: "workstreams que dependem de um tipo/contrato definido em outro lugar
esperam a interface estar fixada, não a implementação completa").

### 0.1 `Screen` protocol — `src/app/gui/screen.py` (arquivo novo)

Substitui o padrão atual inconsistente: `PerspectiveUi`/`BorderUi` implementam `startUp(videoPath)` chamado
via `threading.Thread(target=screen.startUp, args=[videoPath]); .daemon = True; .start()` em
`mainUI.py::run_background_tasks` (linhas 100–103 do arquivo atual) — e essa thread de fundo chama
diretamente métodos Tk (`self.load_image_on_ui_from_cv2`, `self.show_finish_perspective_btn`, mutação de
`Label`/`Canvas`) **sem nenhum marshalling de volta pro main thread**. Isso é o bug de thread-safety latente
citado no `ARCHITECTURE.md`. Além disso, `RecordWebcamVideoUI` (hoje em
`recodWebCamVideo/recordWebcamVideoUI.py`) **não implementa `startUp` nenhum** — `mainUI.py::showRecordWebcamFrame`
chama `self.record_webcam_interface.initial_screen_state()` direto, sem passar por
`run_background_tasks`, quebrando o padrão por completo (não há uniformidade de dispatch entre as 5 telas).

```python
# src/app/gui/screen.py
from __future__ import annotations
import logging
import threading
import tkinter as tk
from typing import Callable, Protocol, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")

class Screen(Protocol):
    """Contrato único para toda tela da GUI. Substitui o startUp(videoPath) ad-hoc."""

    frame: tk.Frame

    def build(self, parent: tk.Widget) -> tk.Frame:
        """Cria e retorna o tk.Frame da tela (chamado 1x, na montagem inicial do MainWindow)."""
        ...

    def on_show(self, **kwargs: object) -> None:
        """Chamado toda vez que a tela é exibida (equivalente ao startUp(videoPath) de hoje, mas
        uniforme: recebe kwargs nomeados, ex: on_show(video_path=...), em vez de posicional único).
        Disparar trabalho pesado via self.run_async — nunca bloquear o main thread aqui."""
        ...

    def on_hide(self) -> None:
        """Chamado ao sair da tela (libera captura de vídeo, cancela threads em andamento, etc)."""
        ...

    def teardown(self) -> None:
        """Chamado 1x no shutdown do app inteiro."""
        ...


class ScreenBase:
    """Mixin concreto com o helper de marshalling. Toda tela concreta herda disso."""

    frame: tk.Frame

    def run_async(
        self,
        work: Callable[[], T],
        on_done: Callable[[T], None],
        on_error: Callable[[Exception], None] | None = None,
    ) -> threading.Thread:
        """Roda `work` em uma thread daemon; `on_done`/`on_error` SEMPRE executam no main thread do Tk,
        via `self.frame.after(0, ...)`. Nenhum código de tela deve chamar métodos Tk fora de on_done/
        on_error/on_show/on_hide (ou seja, fora do main thread)."""

        def _worker() -> None:
            try:
                result = work()
            except Exception as exc:  # intencional: converte em callback marshalled, nunca silencioso
                logger.exception("Falha em run_async de %s", type(self).__name__)
                if on_error is not None:
                    self.frame.after(0, on_error, exc)
                return
            self.frame.after(0, on_done, result)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread

    # Defaults no-op do ciclo de vida: MainWindow.show() (ver 3.2) chama on_hide() em TODA tela a
    # cada troca e teardown() em todas no shutdown. Uma tela concreta que não precise sobrescrever
    # esses ganchos herda estes no-ops de ScreenBase — sem eles, o dispatcher quebraria com
    # AttributeError na 1ª troca de tela (PerspectiveScreen/OrientationScreen/RecordWebcamScreen nas
    # seções 3 e 4 só definem build/on_show). build() continua obrigatório em cada tela (não tem
    # default sensato — precisa retornar o tk.Frame).
    def on_show(self, **kwargs: object) -> None: ...
    def on_hide(self) -> None: ...
    def teardown(self) -> None: ...
```

Regra de revisão para as 4.1: **nenhuma tela migrada pode chamar um método `tk`/`ttk` de dentro de uma
função rodando em thread não-main** — toda mutação de widget passa por `on_done`/`on_error` de
`run_async`. Isso é o que corrige o bug de thread-safety latente descrito no `ARCHITECTURE.md` (item da
Fase 4 "trabalho em background marshalled de volta pro main thread do Tk via `after()`").

### 0.2 `AppService` — assinatura completa (corpo pode ser stub) — `src/app/service.py`

Substitui a montagem de estado hoje pendurada em `root.top_video_path`/`root.side_video_path`
(`tk.StringVar` direto no root Tk, ver `configurationUI.py:41-42` e `mainUI.py:14-15`) e o acesso direto a
`cache/configs.json` via `jsonUtils.import_data_from_file`/`export_data_to_file` espalhado pela GUI
(`configurationUI.py:96-97,156`). CLI **não** depende de `AppService` — CLI monta `RunRequest` direto e
chama `Pipeline.run` (ver seção 2). `AppService` é consumido só pela GUI (workstreams C e D).

```python
# src/app/service.py
from __future__ import annotations
from collections.abc import Callable
from pathlib import Path
from src.core.workspace import Workspace
from src.core.schema.result import AnalysisResult
from src.core.schema.orientation import BoxOrientationConfig
from src.core.plugin_registry import PluginKind, PluginManifest
# ProfileConfig: modelo pydantic da Fase 1 que substitui o dict solto hoje gravado em cache/configs.json
from src.core.schema.profile import ProfileConfig

class ProgressEvent:
    stage: str
    fraction: float | None
    message: str

class AppService:
    """Camada de serviço fina. Toda tela da GUI fala com o mundo através disto — nunca lê/escreve
    arquivo, nunca chama Pipeline.run diretamente."""

    def __init__(self, workspace: Workspace) -> None: ...

    # --- perfis (ProfileStore) ---
    def list_profiles(self) -> list[str]: ...
    def load_profile(self, name: str) -> ProfileConfig: ...
    def save_profile(self, name: str, config: ProfileConfig) -> None: ...
    def new_profile_placeholder_name(self) -> str: ...  # "Novo perfil de analise", ver configurationUI.py:13
    def save_orientation(self, name: str, orientation: BoxOrientationConfig) -> None: ...

    # --- execução (delega 100% pra Pipeline.run; caminho idêntico ao da CLI) ---
    def run_pipeline(
        self, profile: str, on_progress: Callable[[ProgressEvent], None] | None = None
    ) -> AnalysisResult: ...

    # --- plugins (delega pra PluginRegistry) ---
    def list_plugins(self, kind: PluginKind | None = None) -> list[PluginManifest]: ...

    # --- resultados/export (delega pra ResultStore + plugins exporter) ---
    def load_result(self, profile: str) -> AnalysisResult | None: ...
    def export(self, profile: str, exporter_name: str, **kwargs: object) -> Path: ...
```

Tarefa 0.2: escrever este arquivo com corpos reais (não apenas stub) já na etapa sequencial, pois é barato
e desbloqueia C e D sem ambiguidade — só a *assinatura* precisa estar fixa antes de paralelizar, mas como o
custo de implementar já é baixo (delega tudo pra `core/`), fazer completo aqui evita retrabalho.

### 0.3 Campo de orientação no `ProfileConfig` (schema, adição pequena)

`OrientationUi` (workstream D) precisa persistir `BoxOrientationConfig` dentro do mesmo perfil que a GUI
existente (workstream C) lê/grava (vídeo, pontos de perspectiva/borda, dimensões da caixa). Se
`ProfileConfig` (Fase 1) ainda não tiver um campo pra isso, esta etapa sequencial adiciona:

```python
# src/core/schema/profile.py — adição, não redesenho
class ProfileConfig(BaseModel):
    ...  # campos já existentes de Fase 1 (paths, pontos de perspectiva/borda, dimensões cm)
    orientation: BoxOrientationConfig | None = None
```

Motivo de ser sequencial: é o mesmo arquivo/classe que tanto C quanto D vão importar; se cada workstream
adicionasse o campo à sua maneira em paralelo, gera conflito de merge garantido. Faz parte do "contrato
compartilhado" da 4.0, não do trabalho de C nem de D.

### 0.4 Checkpoint de saída da 4.0 (obrigatório antes de abrir os 4 worktrees)

- [ ] `src/app/gui/screen.py` criado, com `Screen` Protocol + `ScreenBase.run_async`.
- [ ] `src/app/service.py` criado, com todos os métodos de `AppService` implementados (não apenas
      assinatura) e testados por `tests/test_service.py` (round-trip perfil, delegação a `Pipeline.run`
      mockado).
- [ ] `ProfileConfig.orientation: BoxOrientationConfig | None` presente e coberto por teste de round-trip
      JSON.
- [ ] Confirmado (leitura, não escrita) que `Calibration`/`AnalysisResult` da Fase 3 estão congelados —
      nomes de campo exatos anotados no handoff da 4.0 para os workstreams B e D usarem sem adivinhar.
- [ ] Assinatura de construtor de cada tela fixada como parte do contrato — em especial
      `OrientationScreen(service, show=...)` (ver 4.1). Motivo: `main_window.py` (workstream C, seção 3.2)
      **importa e instancia** `OrientationScreen` (arquivo do workstream D); C precisa dessa assinatura
      congelada aqui, na 4.0, não descoberta em paralelo com D — senão C escreve o `main_window` contra uma
      interface adivinhada e o merge com D quebra. Anotar as 7 assinaturas de tela no handoff da 4.0.

Só depois disso os 4 workstreams abrem worktree e rodam em paralelo.

---

## 1. Workstream A — `src/app/cli.py` (Typer)

Sem dependência de C/D/da 4.0 (não toca Tkinter, não usa `AppService`) — pode começar antes mesmo da 4.0
terminar, se quiser adiantar. Único ponto de contato: `Pipeline.run`/`Workspace`/`PluginRegistry`
(Fase 2+3, já fixos).

### 1.1 Comandos (exatamente os 3 do `ARCHITECTURE.md`, opções literais + inferidas marcadas)

```python
# src/app/cli.py
from __future__ import annotations
from pathlib import Path
from typing import Optional
import typer

from src.core.workspace import Workspace
from src.core.pipeline import Pipeline, RunRequest
from src.core.plugin_registry import PluginRegistry, PluginKind

app = typer.Typer(name="animaltrack", no_args_is_help=True)


@app.command()
def run(
    workspace: Optional[Path] = typer.Option(
        None, "--workspace", help="Raiz do workspace (default: $ANIMALTRACK_WORKSPACE ou ~/.animaltrack)"
    ),
    profile: str = typer.Option(..., "--profile", help="Nome do perfil de análise"),
    config: Optional[Path] = typer.Option(
        None, "--config", help="Caminho alternativo de pipeline.toml (default: <workspace>/config/<profile>/pipeline.toml)"
    ),
    gpu: bool = typer.Option(False, "--gpu", help="Força backend GPU; falha alto se indisponível (GPU é requisito, não fallback)"),
) -> None:
    """`animaltrack run --workspace ./ws --profile fish01 [--config pipeline.toml] [--gpu]` — literal do ARCHITECTURE.md."""
    ws = Workspace.resolve(workspace)
    request = RunRequest(workspace=ws, profile=profile, config_path=config, require_gpu=gpu)
    result = Pipeline.run(request)
    typer.echo(f"OK: resultado salvo em {ws.outputs / profile}")
    # exit code 0 implícito; falhas de Pipeline.run devem levantar exceção tipada, capturada
    # por um typer.Exit(code=1) em torno da chamada (ver 1.2)


@app.command("list-plugins")
def list_plugins(
    workspace: Optional[Path] = typer.Option(None, "--workspace", help="Raiz do workspace"),
    kind: Optional[str] = typer.Option(
        None, "--kind", help="Filtra por tipo: capture|rectify|detector|tracker|fusion|metadata|exporter"
    ),
) -> None:
    """`animaltrack list-plugins` — opções --workspace/--kind inferidas (não estão em ARCHITECTURE.md
    literalmente, mas list_plugins sem escopo de workspace não tem como descobrir plugins locais)."""
    ws = Workspace.resolve(workspace)
    registry = PluginRegistry()
    registry.discover(ws.plugin_search_paths())
    kind_filter = PluginKind(kind) if kind else None
    manifests = registry.for_kind(kind_filter) if kind_filter else registry.all()
    for m in manifests:
        typer.echo(f"{m.kind:10s} {m.name:30s} v{m.version}")


@app.command("validate-config")
def validate_config(
    workspace: Optional[Path] = typer.Option(None, "--workspace"),
    profile: Optional[str] = typer.Option(None, "--profile", help="Se omitido, valida todos os perfis do workspace"),
    config: Optional[Path] = typer.Option(None, "--config"),
) -> None:
    """`animaltrack validate-config` — opções inferidas (mesma lógica: precisa de escopo). Valida
    pipeline.toml/profile.json contra o schema pydantic sem executar o pipeline."""
    ws = Workspace.resolve(workspace)
    profiles = [profile] if profile else Workspace_list_profiles(ws)  # helper interno, ver 1.3
    exit_code = 0
    for name in profiles:
        errors = validate_profile(ws, name, config)  # helper, ver 1.3 — usa pydantic ValidationError
        if errors:
            exit_code = 1
            for e in errors:
                typer.echo(f"[{name}] {e}", err=True)
        else:
            typer.echo(f"[{name}] OK")
    raise typer.Exit(code=exit_code)
```

Regra dura: **nada em `src/app/cli.py` importa `tkinter` nem `src/app/gui`, direta ou transitivamente.**
Isso é verificado por teste (seção 6) checando `sys.modules` num subprocesso limpo.

### 1.2 Tratamento de erro / exit codes

- Toda exceção de domínio (`CaptureError`, `PluginLoadError`, `ValidationError` do pydantic) capturada em
  volta da chamada de `Pipeline.run`/`registry.discover` dentro de cada comando, convertida em
  `typer.echo(..., err=True)` + `raise typer.Exit(code=1)`. Nunca deixar traceback cru vazar pro usuário
  final da CLI (mas logar via `logging` para depuração).
- `run` retorna código 2 especificamente se `--gpu` foi pedido e a checagem de `src/core/gpu.py` falhar
  (GPU é requisito, não fallback — distinto de erro genérico de pipeline).

### 1.3 Helpers internos (mesmo arquivo ou `src/app/cli_helpers.py`)

- `Workspace_list_profiles(ws) -> list[str]` — lista perfis existentes em `ws.config_path`.
- `validate_profile(ws, name, config_path) -> list[str]` — carrega `ProfileConfig`/`pipeline.toml`,
  roda `.model_validate`, retorna lista de mensagens de erro (vazia se válido).

### 1.4 Testes (ver seção 8 para detalhe) — `tests/test_cli_e2e.py`, `tests/test_cli_list_plugins.py`,
`tests/test_cli_validate_config.py`.

---

## 2. Workstream B — Plugins de Export (`plotRoute.py`/`pdfFactory.py` → `exporter`)

Sem dependência de C/D — só de `Plugin`/`PluginManifest`/`AnalysisContext.get_metric` (Fase 1+2, já
fixos) e dos nomes de campo finais de `Calibration`/`AnalysisResult` (Fase 3, confirmados no checkpoint
0.4). Zero overlap de arquivo com GUI.

### 2.1 Novo layout

```
src/stages/export/
  plot/
    plugin.toml
    plugin.py          # PlotRouteExporter(Plugin)
  pdf/
    plugin.toml
    plugin.py           # PdfReportExporter(Plugin)
    template.py         # render_html(ctx) — extraído p/ ser testável sem tocar IO/pisa
```

### 2.2 `plugin.toml` — pdf

```toml
[plugin]
name        = "pdf-report"
version     = "1.0.0"
kind        = "exporter"
entry       = "plugin:PdfReportExporter"
api_version = "1.0"
schema      = ">=1.0,<2.0"

[requires]
python   = ">=3.11"
packages = ["xhtml2pdf>=2.0"]
plugins  = []

[ordering]
before = []
after  = []
priority = 100
```

`plugin.toml` de `plot` é análogo, `name = "route-plot"`, `packages = ["matplotlib>=3.8", "pandas>=2.0"]`.

### 2.3 Acesso defensivo — o que muda exatamente

Hoje, `pdfFactory.py:42,46,50,54,58,62,66,70,74` acessa `data['frame_count']`, `data['box_width_cm']`,
`data['box_height_cm']`, `data['box_depth_cm']`, `data['pixel_to_cm_ratio']`, `data['fps']`,
`data['time_border_x']`, `data['time_border_y']`, `data['time_border_z']` — todos por `[]` direto, sem
`.get()`; se `execute_metadata_module_calls` não tiver rodado (ou um plugin de metadata tiver sido pulado
por erro), qualquer uma dessas chaves ausente derruba a exportação com `KeyError`.

Novo `template.py`:

```python
# src/stages/export/pdf/template.py
from src.core.schema.result import AnalysisContext

def metric_value(ctx: AnalysisContext, name: str, default: str = "N/D") -> str:
    m = ctx.get_metric(name)
    return str(m.value) if m is not None else default

def render_html(ctx: AnalysisContext, title: str) -> str:
    result = ctx.result
    calib = result.calibration
    rows = [
        ("Quantidade de frames", str(len(result.routes[0].points)) if result.routes else "N/D"),
        ("Largura da Caixa (cm)", str(calib.box_cm.x)),
        ("Altura da Caixa (cm)", str(calib.box_cm.z)),   # ver nota de mapeamento abaixo
        ("Profundidade da Caixa (cm)", str(calib.box_cm.y)),
        ("Razão px/cm (X)", str(calib.px_per_cm.x)),   # substitui a linha única "Razão Pixel para cm" do
        ("Razão px/cm (Y)", str(calib.px_per_cm.y)),   # pdfFactory legado (agora por eixo, pois o schema
        ("Razão px/cm (Z)", str(calib.px_per_cm.z)),   # da Fase 3 troca a razão-mediana única por Point3D)
        ("FPS", str(calib.fps)),
        ("Tempo Borda X", metric_value(ctx, "time_border_x")),
        ("Tempo Borda Y", metric_value(ctx, "time_border_y")),
        ("Tempo Borda Z", metric_value(ctx, "time_border_z")),
    ]
    rows_html = "\n".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    return f"""<!DOCTYPE html>...<table>{rows_html}</table>..."""  # mesmo CSS/estrutura de hoje
```

> **Nota de coordenação (não decisão deste plano)**: o mapeamento exato `box_width_cm/height_cm/depth_cm`
> (nomenclatura legada) → `calib.box_cm.x/y/z` depende de como `axis_mapping()`/`BoxOrientationConfig`
> (Fase 3) definem os eixos (mesma consideração vale para `calib.px_per_cm.x/y/z`) — **não é o workstream B
> quem decide essa correspondência**, ele só a consome
> como fato já fixado. Se ao implementar isso o workstream B achar a correspondência ambígua ou não
> documentada em Fase 3, isso é bloqueio a registrar no handoff (`blocked`), não uma decisão a tomar por
> conta própria.

`plugin.py`:

```python
class PdfReportExporter(Plugin):
    manifest: ClassVar[PluginManifest] = ...  # carregado do plugin.toml
    def export(self, ctx: AnalysisContext, workspace: Workspace, **kwargs) -> Path:
        from xhtml2pdf import pisa
        html = render_html(ctx, title=ctx.result.profile)
        out = workspace.outputs / ctx.result.profile / "report.pdf"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("wb") as f:
            status = pisa.CreatePDF(html, dest=f)
        if status.err:
            raise ExportError(f"xhtml2pdf falhou para {ctx.result.profile}")
        return out
```

`PlotRouteExporter` análogo: `getInsectPositionFromFile` (hoje lendo `data['frame_count']`/`data['route']`
como dict cru, `plotRoute.py:7-15`) vira leitura direta de `route.points: dict[int, Point3D]` (Fase 1) —
segmentação por "gap" deixa de comparar `x == -1` (`plotRoute.py:84`, sentinela legado) e passa a
detectar **buracos de índice** no dict (`frame_index` faltante = oclusão), já que o schema novo não usa
mais sentinela numérica. Isso é uma correção arrastada da migração de schema, registrada aqui porque é o
workstream B quem toca este arquivo.

### 2.4 Testes — `tests/test_export_plugins.py` (detalhe na seção 8).

---

## 3. Workstream C — GUI: refatoração das telas existentes (`src/app/gui/*`)

Depende do checkpoint 0.4 (Screen protocol + AppService prontos). Não depende de D nem de B. Toca
arquivos próprios (novos, sob `src/app/gui/`), não os arquivos legados de `src/Modules/InterfaceModule/*`
(estratégia strangler-fig: legado fica intocado até o momento de apagar, listado na tabela de migração do
`ARCHITECTURE.md`).

### 3.1 Layout novo

```
src/app/gui/
  __init__.py          # def main() -> None: cria root, MainWindow, mainloop
  main_window.py        # MainWindow: monta todas as telas, dict frame_name -> Screen, dispatcher on_show único
  screens/
    config_hub.py        # ex-MainConfigurationInterface
    perspective.py        # ex-PerspectiveUi (parametrizado por role: "top"|"side")
    border.py              # ex-BorderUi (parametrizado por role: "top"|"side")
    record_webcam.py       # ex-RecordWebcamVideoUI
    orientation.py         # NOVO — workstream D
```

### 3.2 `main_window.py` — dispatcher único (substitui `run_background_tasks` + `show*Frame` ad-hoc)

```python
# src/app/gui/main_window.py
import tkinter as tk
from src.app.service import AppService
from src.app.gui.screen import Screen
from src.app.gui.screens.config_hub import ConfigHubScreen
from src.app.gui.screens.perspective import PerspectiveScreen
from src.app.gui.screens.border import BorderScreen
from src.app.gui.screens.record_webcam import RecordWebcamScreen
from src.app.gui.screens.orientation import OrientationScreen

class MainWindow:
    def __init__(self, root: tk.Tk, service: AppService) -> None:
        self.root = root
        self.service = service
        self.screens: dict[str, Screen] = {
            "hub": ConfigHubScreen(service, show=self.show),
            "perspective_top": PerspectiveScreen(service, role="top", show=self.show),
            "perspective_side": PerspectiveScreen(service, role="side", show=self.show),
            "border_top": BorderScreen(service, role="top", show=self.show),
            "border_side": BorderScreen(service, role="side", show=self.show),
            "record_webcam": RecordWebcamScreen(service, show=self.show),
            "orientation": OrientationScreen(service, show=self.show),
        }
        for scr in self.screens.values():
            scr.frame = scr.build(root)
            scr.frame.grid(row=0, column=0, sticky="nsew")
        self.show("hub")

    def show(self, name: str, **kwargs: object) -> None:
        """Dispatcher ÚNICO — substitui showFrameSide/showFrameTop/showConfigBorderTop/... duplicados de
        mainUI.py. Toda tela recebe on_show(**kwargs) da MESMA forma, inclusive record_webcam (que hoje
        é a exceção que quebra o padrão)."""
        for scr in self.screens.values():
            scr.on_hide()
        target = self.screens[name]
        target.frame.tkraise()
        target.on_show(**kwargs)


def main() -> None:
    root = tk.Tk()
    root.title("Ferramenta para a analise comportamental de insetos")
    service = AppService(Workspace.resolve(None))
    MainWindow(root, service)
    root.mainloop()
```

Diferença-chave vs hoje: `showRecordWebcamFrame` (`mainUI.py:96-98`) chamava
`self.record_webcam_interface.initial_screen_state()` **direto**, sem thread, sem `startUp`, quebrando a
uniformidade — no novo desenho `RecordWebcamScreen.on_show()` simplesmente não dispara `run_async` (não
tem vídeo pra carregar), mas ainda assim é chamado por `self.show("record_webcam")` do mesmo jeito que
qualquer outra tela; a assinatura é uniforme mesmo quando o corpo é trivial.

### 3.3 `screens/perspective.py` — correção do bug de thread-safety

Hoje (`perspectiveUi.py:20-48`), `startUp` roda inteiro em thread de fundo, incluindo o loop
`while not finished_perspective: ... self.load_image_on_ui_from_cv2(perspective_frame); self.show_finish_perspective_btn()`
— todas chamadas Tk (criação de `ttk.Label`/`ttk.Button`, `.grid`) feitas **fora do main thread**. Novo
desenho:

```python
class PerspectiveScreen(ScreenBase):
    def __init__(self, service: AppService, role: str, show: Callable) -> None:
        self.service = service
        self.role = role  # "top" | "side"
        self.show = show
        self.frame_perspective_points: list[tuple[int, int]] = []
        self.finished = False

    def build(self, parent: tk.Widget) -> tk.Frame:
        self.frame = tk.Frame(parent)
        self._build_static_widgets()  # placeholders (imagem preta), botão Voltar — só widgets, sem I/O
        return self.frame

    def on_show(self, video_path: str = "", **_: object) -> None:
        if not video_path:
            return
        self.video_path = video_path
        self.run_async(
            work=lambda: self._load_first_frame(video_path),
            on_done=self._apply_first_frame,       # roda no main thread via after()
            on_error=self._show_error,
        )

    def _load_first_frame(self, video_path: str):
        # SOMENTE I/O/CPU (cv2), NENHUMA chamada tk aqui
        success, video = open_video(video_path)
        if not success:
            raise CaptureError(f"Não abriu vídeo {video_path}")
        ok, frame = video.read()
        if not ok:
            raise CaptureError("Vídeo sem frames")
        self._video = video
        return frame

    def _apply_first_frame(self, frame) -> None:
        # AQUI SIM pode mexer em Tk — já estamos no main thread (via after())
        self.load_image_on_ui_from_cv2(frame)
        self._poll_perspective_preview()   # ver abaixo — substitui o while+sleep de hoje

    def _poll_perspective_preview(self) -> None:
        """Substitui o `while not finished_perspective: ... time.sleep(0.01)` de perspectiveUi.py:40-46,
        que hoje roda em thread de fundo tocando Tk a cada iteração. Reimplementado como reagendamento
        via after() no main thread: cada 4 cliques computa o warp 1x e para, sem polling contínuo."""
        if len(self.frame_perspective_points) == 4:
            self.run_async(
                work=lambda: fix_perspective(self._last_frame, self.frame_perspective_points),
                on_done=self._apply_perspective_result,
            )
    # _apply_perspective_result faz o self.load_image_on_ui_from_cv2(...) + show_finish_perspective_btn()
    # sempre a partir de on_done, nunca de dentro de work().
```

Mudança de comportamento pequena e deliberada: o "loop enquanto não configurado" de hoje (`time.sleep(0.01)`
+ recomputar sempre) vira "recomputa uma vez quando o 4º ponto é clicado" — equivalente funcional (o preview
só muda quando `frame_perspective_points` atinge 4), sem custo de polling e sem tocar Tk fora do main
thread. Registrar isso explicitamente no handoff como mudança de comportamento **visualmente idêntica**
(mesmo resultado final, só o "como" de atualização muda) — não uma decisão de UX nova.

`screens/border.py` segue o mesmo padrão (`build` monta canvas placeholder, `on_show(video_path=...)`
carrega o 1º frame via `run_async`); a lógica de arrastar cantos (`start_move`/`move_line`/`stop_move` de
`borderUi.py:72-111`) já roda inteiramente a partir de binds de evento do Tk (main thread) hoje — não
precisa de correção de thread-safety, só de porte pro novo protocolo.

### 3.4 `screens/record_webcam.py` — bug #4 e #5 (ver seção 5) + normalização

`RecordWebcamVideoUI` vira `RecordWebcamScreen(ScreenBase)`. Pontos de mudança:
- `on_show(**_)`: chama `self.initial_screen_state()` direto (sem I/O, sem thread) — comportamento igual
  ao `showRecordWebcamFrame` de hoje, mas agora via protocolo uniforme.
- `show_recoding_video` (hoje `recordWebcamVideoUI.py:52-95`, thread própria que muta `self.labels[...]`
  direto) passa a rodar como `work` de um `run_async`, mas como é um **loop contínuo de preview** (não uma
  tarefa "roda 1x e termina"), o padrão `run_async` de tiro único não serve — usar em vez disso um
  reagendamento leve via `self.frame.after(33, self._poll_preview_frame)` (~30fps), onde
  `_poll_preview_frame` faz `queue.get_nowait()` (não bloqueante) e atualiza os `Label`s **já dentro do
  main thread** (chamado por `after`, nunca por uma thread solta). Isso elimina de vez a thread
  `thread_show_recoding_video` (`recordWebcamVideoUI.py:41-42`) que hoje toca Tk diretamente.
- Remove o `except:` nu de `show_recoding_video` (linha 94) — ver bug #4.

### 3.5 `screens/config_hub.py`

Porta `MainConfigurationInterface` (`configurationUI.py`) trocando:
- `self.root.top_video_path`/`self.root.side_video_path` (StringVar no root Tk) → estado local da tela
  (`self.top_video_path: str`) + `self.service.save_profile(...)`/`load_profile(...)` em vez de
  `import_data_from_file`/`export_data_to_file` direto (`configurationUI.py:96-97,156`).
- `process_video`/`process_metadata_modules`/`process_output_data`/`process_pdf` (chamadas diretas a
  `process_basic_modules`, `execute_metadata_module_calls`, `plot_insect_route_on_graph_*`,
  `pdfFactory.GeneratePdf`) → todas viram `self.service.run_pipeline(profile, on_progress=...)` e
  `self.service.export(profile, "route-plot"|"pdf-report")`. Nenhuma chamada direta a stages/plugins a
  partir da tela.
- Adiciona botão "Configurar orientação" → `self.show("orientation", video_path_top=..., video_path_side=...)`
  (novo, workstream D).

### 3.6 Testes de C — `tests/test_gui_smoke.py`, `tests/test_screen_thread_marshalling.py` (seção 8).

---

## 4. Workstream D — `OrientationScreen` (nova tela)

Depende do checkpoint 0.4 (Screen protocol + `AppService.save_orientation` + `ProfileConfig.orientation`).
Não depende de C além disso — arquivo novo (`src/app/gui/screens/orientation.py`), sem overlap. Coordena
com o plano de UX (`docs/plans/ux-design-detalhado.md`, ainda não escrito) para layout/cores/wording
finais; o que segue é a **forma técnica concreta** mínima pra ter uma primeira versão funcional, não o
polimento visual.

### 4.1 Estado mantido pela tela

```python
class OrientationScreen(ScreenBase):
    def __init__(self, service: AppService, show: Callable) -> None:
        self.service = service
        self.show = show
        self.face_top: BoxFace | None = None
        self.face_side: BoxFace | None = None
        self.corner_vertices_top: list[BoxVertex | None] = [None, None, None, None]
        self.corner_vertices_side: list[BoxVertex | None] = [None, None, None, None]
        # ordem fixa dos 4 índices, igual ao clique do PerspectiveUi:
        # 0 = superior-direito, 1 = superior-esquerdo, 2 = inferior-direito, 3 = inferior-esquerdo
```

### 4.2 Widgets concretos (Tkinter puro, sem lib nova)

- `Canvas` 400x400 (`self.wireframe_canvas`) com wireframe estático da caixa: 8 vértices projetados em
  isométrica com coordenadas 2D pré-calculadas uma vez (constantes de módulo), arestas desenhadas com
  `create_line`, cada vértice com `create_oval` + `create_text` rotulado (`TOP_FRONT_LEFT` etc, tag
  `vertex_<nome>`). Realce: ao selecionar uma face num combobox, `canvas.itemconfig` muda a cor dos 4
  vértices/arestas daquela face (feedback visual imediato de "são estes 4 pontos").
- Por câmera (`ttk.LabelFrame "Câmera Topo"` / `"Câmera Lateral"`):
  - `ttk.Combobox` `face_viewed`, valores = `[f.value for f in BoxFace]`.
  - 4× `ttk.Combobox` rotulados "Canto 1 (superior-direito)" .. "Canto 4 (inferior-esquerdo)" — cada um
    populado dinamicamente via `vertices_for_face(face) -> list[BoxVertex]` (recalculado no callback de
    mudança do combobox de face), com validação: ao selecionar um vértice já usado em outro dos 4 combos
    da mesma câmera, reverte a seleção + `messagebox.showerror` (impede vértice duplicado).
- Botão `"Salvar orientação"`: habilitado só quando `face_top`/`face_side` setados e os 4 vértices de
  cada câmera distintos e pertencentes à face escolhida; ao clicar, monta 2×`CameraOrientation`, monta
  `BoxOrientationConfig(top_camera=..., side_camera=...)`, chama
  `self.service.save_orientation(profile_atual, config)`, `self.show("hub")`.

### 4.3 `vertices_for_face` — mapeamento face→4 vértices (helper puro, testável isoladamente)

```python
def vertices_for_face(face: BoxFace) -> list[BoxVertex]:
    # cada face do cubo tem exatamente 4 dos 8 vértices; nomes combinam TOP/BOTTOM x FRONT/BACK x LEFT/RIGHT
    mapping = {
        BoxFace.TOP:    [v for v in BoxVertex if v.name.startswith("TOP_")],
        BoxFace.BOTTOM: [v for v in BoxVertex if v.name.startswith("BOTTOM_")],
        BoxFace.FRONT:  [v for v in BoxVertex if "_FRONT_" in v.name],
        BoxFace.BACK:   [v for v in BoxVertex if "_BACK_" in v.name],
        BoxFace.LEFT:   [v for v in BoxVertex if v.name.endswith("_LEFT")],
        BoxFace.RIGHT:  [v for v in BoxVertex if v.name.endswith("_RIGHT")],
    }
    return mapping[face]
```

### 4.4 `on_show`

```python
def on_show(self, **_: object) -> None:
    # tela é só formulário sobre wireframe estático — nada de I/O de vídeo, não precisa de run_async
    pass
```

### 4.5 O que fica para o plano de UX Design (não decidido aqui)

Cores exatas, disposição pixel-a-pixel, texto de ajuda/tooltip, se o wireframe usa rotação 3D interativa
(fora de escopo Tkinter puro — se o UX pedir isso, avaliar `matplotlib` embutido via
`FigureCanvasTkAgg`, mas **não assumir isso agora**: o wireframe 2D estático acima já satisfaz o requisito
funcional mínimo "usuário associa vértice a canto clicado"). Este plano fixa apenas: quais widgets existem,
que estado a tela guarda, e o que ela grava de volta (`BoxOrientationConfig` via
`service.save_orientation`).

### 4.6 Testes — `tests/test_orientation_screen.py` (seção 8).

---

## 5. Bugs #4 e #5 — correções exatas (parte do refactor de gravação apoiado em Capture)

Ambos vivem hoje em código que a tabela de migração do `ARCHITECTURE.md` marca como
`ExportModule/{recordVideo,...}.py → Refatora → Capture stage / utils de workspace | Fase 3–4` — a
correção é feita **no novo local**, não remendada no arquivo legado (que será apagado).

### 5.1 Bug #4 — `get_image_from_frame_queue`

Hoje, `recordWebcamController.py:38-46`:
```python
def get_image_from_frame_queue(self, queue, image_size):
    try:
        frame = queue.get(timeout=1)
        image = Image.fromarray(frame)
    except:
        image = Image.new("RGB", image_size, "black")
    imageTk = ImageTk.PhotoImage(image)
    return imageTk
```
Chamada em `recordWebcamVideoUI.py:65,76`: `get_image_from_frame_queue(queueSide, image_size)` — **2
argumentos contra 3 parâmetros** → `TypeError` a cada chamada, hoje mascarado pelo `except:` nu **externo**
de `show_recoding_video` (linha 94), que mata a thread de preview silenciosamente. Este é o achado
confirmado durante a leitura do código: o bug real não é apenas o `self` sobrando na assinatura — é que a
assinatura errada faz o `TypeError` estourar *na chamada*, e esse `TypeError` só não aparece porque um
**segundo** `except:` nu, no laço de `show_recoding_video`, engole tudo e imprime `"erro esperado"`,
encerrando a thread de preview após o primeiro frame.

Novo local: `src/app/gui/screens/record_webcam.py` (ou um `src/stages/capture/preview.py` compartilhável se
outro consumidor precisar), função livre (não método, sem `self` sobrando):

```python
from queue import Queue, Empty

def get_image_from_frame_queue(queue: Queue, image_size: tuple[int, int]) -> ImageTk.PhotoImage:
    try:
        frame = queue.get(timeout=1)
    except Empty:
        image = Image.new("RGB", image_size, "black")
    else:
        image = Image.fromarray(frame)
    return ImageTk.PhotoImage(image)
```
- Remove o `self` sobrando (chamador já passava só 2 argumentos — a assinatura é quem estava errada).
- Troca `except:` nu por `except Empty:` — único caso esperado (fila vazia por timeout); qualquer outra
  exceção (ex: `frame` corrompido em `Image.fromarray`) agora propaga.
- No chamador (`_poll_preview_frame` do novo `record_webcam.py`, ver 3.4), troca o `except:` nu externo
  (hoje `recordWebcamVideoUI.py:94`, `print("erro esperado")`) por captura restrita a
  `tk.TclError` (widget destruído durante shutdown — único caso "esperado" de verdade nesse contexto),
  deixando qualquer outra exceção aparecer/logar via `logger.exception`.

### 5.2 Bug #5 — `record_video()` checagem de falha inalcançável

Hoje, `recordVideo.py:17-29`:
```python
while not stop_event.is_set():
    sync_event.wait()
    started_event.set()

    ret, frame = cap.read()
    queue.put(frame)

    if(start_recording.is_set()):
        if not ret:
            print(f"Erro ao capturar quadro da câmera {camera_index}.")
            break
        out.write(frame)
```
Problema: a checagem `if not ret: break` só é avaliada **dentro** do `if start_recording.is_set()` — antes
do usuário clicar "Iniciar gravação" (fase de preview), uma falha de leitura (`ret=False`, câmera
desconectada) nunca é detectada: o laço continua chamando `cap.read()` indefinidamente (busy loop, 100% de
uma CPU) e ainda faz `queue.put(frame)` com `frame=None` seguidas vezes.

Correção (no novo `WebcamCaptureSource`/gerador de Capture, ou diretamente em `recordVideo.py` se o port
pra Capture stage ainda não estiver pronto quando D/C rodarem — registrar no handoff qual dos dois
aconteceu):
```python
while not stop_event.is_set():
    sync_event.wait()
    started_event.set()

    ret, frame = cap.read()
    if not ret:
        print(f"Erro ao capturar quadro da câmera {camera_index}.")
        error_event.set()
        break

    queue.put(frame)

    if start_recording.is_set():
        out.write(frame)
```
Mudança: checagem de `ret` movida para **fora e antes** de `if start_recording.is_set()`, agora sempre
alcançável; adicionado `error_event.set()` (evento que já existe e é observado pela UI — ver
`recordWebcamVideoUI.py:64,75` — mas hoje nunca é setado a partir de uma falha de leitura *após* abertura
bem-sucedida da câmera, só na abertura inicial em `recordVideo.py:8`); `queue.put(frame)` só acontece com
frame válido.

### 5.3 Testes de ambos — `tests/test_capture_bugfixes.py` (seção 8).

---

## 6. Novo `__init__.py` / launcher — dispatch exato

Único arquivo tocado por último, depois do merge dos 4 worktrees (depende de `src.app.cli:app` e
`src.app.gui:main` existirem com esses nomes — combinar isso já na 4.0 como parte do "contrato
compartilhado", já que tanto A quanto C escrevem essas entry points).

```python
# __init__.py (raiz) — launcher fino, decide GUI vs CLI por argv
from __future__ import annotations
import sys

CLI_COMMANDS = {"run", "list-plugins", "validate-config", "--help", "-h"}


def main() -> int:
    """Se algum argumento de linha de comando reconhecido foi passado, despacha pra CLI (Typer) sem
    NUNCA importar tkinter nesse caminho. Sem argumentos, abre a GUI. `src/app/cli.py` não deve importar
    `src/app/gui` (nem transitivamente) — é isso que garante o caminho headless real."""
    args = sys.argv[1:]
    if args and args[0] in CLI_COMMANDS:
        from src.app.cli import app as cli_app
        cli_app()
        return 0

    from src.app.gui import main as gui_main
    gui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Também adicionar em `pyproject.toml` (Fase 0, já existente a essa altura) o entry point de console:
```toml
[project.scripts]
animaltrack = "src.app.cli:app"
```
(chamada direta `animaltrack run ...` sem passar pelo launcher `__init__.py`, útil pós-`pip install -e .`).

---

## 7. Paralelização — dependências reais entre os 4 workstreams

| Workstream | Depende de (Fase 4) | Não depende de | Arquivos tocados |
|---|---|---|---|
| A — CLI | nada de Fase 4 (só Fase 2+3) | 4.0, C, D | `src/app/cli.py`, `src/app/cli_helpers.py`, testes |
| B — Export plugins | nomes de campo finais de `Calibration` (Fase 3, leitura) | 4.0, C, D | `src/stages/export/**` |
| C — GUI refactor | 4.0 completo (`Screen`, `AppService`, `ProfileConfig.orientation`) | A, B, D | `src/app/gui/main_window.py`, `src/app/gui/screens/{config_hub,perspective,border,record_webcam}.py` |
| D — OrientationUi | 4.0 completo (mesmo motivo de C) + `vertices_for_face` (próprio) | A, B, C (sem overlap de arquivo) | `src/app/gui/screens/orientation.py` |

Conflito real identificado (e como foi neutralizado): **C e D ambos são "telas" que implementam o mesmo
`Screen` Protocol e ambos gravam no mesmo `ProfileConfig`/mesmo `pipeline.toml` de perfil.** Se o contrato
(`Screen`, `AppService`, `ProfileConfig.orientation`) não estivesse fixado *antes* de abrir os dois
worktrees, cada agente inventaria sua própria versão da interface e o merge exigiria retrabalho não
trivial (exatamente o padrão de risco que o `ARCHITECTURE.md` descreve para a Fase 3 com `stages.py`). A
seção 0 (4.0) existe só para eliminar esse risco — depois dela, C e D não compartilham nenhum arquivo de
**escrita** em comum: D só adiciona `orientation.py`, e todo o restante do fio (o `import`/instanciação de
`OrientationScreen` em `main_window.py` e o botão "Configurar orientação" em `config_hub.py`) vive em
arquivos de C. São **dois** pontos de toque conjunto, não um — (a) `main_window.py` importa e instancia
`OrientationScreen`, e (b) `config_hub.py` chama `self.show("orientation", ...)` — mas ambos ficam em
arquivos de C e são escritos por **quem terminar C** contra a assinatura de `OrientationScreen` já congelada
na 4.0 (ver checkpoint 0.4). D não toca nenhum dos dois. É por isso que congelar a assinatura de construtor
das telas na 4.0 (e não só o `Screen` Protocol) é pré-requisito real, não formalidade: sem ela, o `import`
que C faz do módulo de D fica sem contrato e o merge exige retrabalho.

A e B não têm nenhuma dependência de 4.0 nem entre si — podem, na prática, começar antes mesmo do
checkpoint 0.4 fechar, se a ordem de disparo dos agentes permitir.

Integração final (sequencial, depois que os 4 mergeiam): escrever/atualizar `__init__.py` (seção 6) +
rodar suite completa (seção 9) + comparação manual (seção 9).

---

## 8. Plano de testes — arquivos exatos

- `tests/test_cli_e2e.py`
  - `test_run_generates_json_and_pdf_headless(tmp_path)`: usa `typer.testing.CliRunner`, roda
    `["run", "--workspace", str(tmp_path), "--profile", "fixture01"]` sobre um workspace fixture (vídeos
    curtos de Fase 3, `pipeline.toml` já com exporters `route-plot`+`pdf-report` configurados); assert
    `result.exit_code == 0`; assert `(tmp_path / "outputs" / "fixture01" / "result.json").exists()`; assert
    `(tmp_path / "outputs" / "fixture01" / "report.pdf").exists()`.
  - `test_cli_process_never_imports_tkinter()`: **não** roda in-process (risco de outro teste da mesma
    sessão pytest já ter importado `tkinter` e poluir `sys.modules`). Roda via `subprocess.run([sys.executable,
    "-c", script], capture_output=True)` onde `script`, num interpretador **novo**, importa `src.app.cli` e
    então invoca o comando **isolando o resultado do pipeline da checagem de import**: chama
    `app(["run", "--workspace", ws, "--profile", "fixture01"], standalone_mode=False)` dentro de um
    `try/except (SystemExit, Exception)`. O ponto do teste é o grafo de import, **não** o sucesso do `run` —
    então uma falha de pipeline não pode abortar o script antes da checagem. Só depois desse bloco o script
    faz **incondicionalmente** `print("TK_IMPORTED" if "tkinter" in sys.modules else "TK_CLEAN")`; o pai faz
    `assert "TK_CLEAN" in result.stdout`. (Cuidado: com `standalone_mode=True` — o default do Typer — o
    `SystemExit` de qualquer falha/`--help` de `run` mataria o subprocesso antes do `print`, fazendo o teste
    falhar por motivo errado mesmo com o import 100% limpo; daí o `standalone_mode=False` + `try/except`
    obrigatórios.) O `import src.app.cli` sozinho já pega import **estático** de Tk no grafo transitivo; a
    invocação adicional do comando pega import **lazy** de Tk escondido dentro do corpo de `run`. Isso é a
    forma concreta de "assert no Tk import" pedida.
  - `test_run_missing_profile_exits_nonzero()`.
- `tests/test_cli_list_plugins.py` — `test_list_plugins_filters_by_kind()`.
- `tests/test_cli_validate_config.py` — `test_validate_config_reports_errors_without_traceback()`.
- `tests/test_service.py`
  - `test_save_and_load_profile_roundtrip(tmp_path)`.
  - `test_run_pipeline_delegates_to_core_pipeline(monkeypatch)` — monkeypatcha `Pipeline.run`, garante que
    `AppService.run_pipeline` chama exatamente isso e não reimplementa lógica própria.
- `tests/test_gui_smoke.py`
  - `@pytest.mark.skipif(not _has_display(), reason="precisa de display Tk")` no topo do módulo (nota:
    em CI Linux precisa `xvfb-run`; em Windows normalmente há display virtual disponível).
  - `test_main_window_builds_all_screens()`: instancia `tk.Tk()`, `MainWindow(root, fake_service)`, assert
    `set(mw.screens) == {"hub","perspective_top","perspective_side","border_top","border_side","record_webcam","orientation"}`.
  - `test_hub_process_video_calls_same_pipeline_as_cli(monkeypatch)`: monkeypatcha
    `AppService.run_pipeline` com um fake que grava a `RunRequest`/args recebidos; invoca o command do
    botão "Processar vídeo" diretamente (`hub_screen._on_process_video()`); assert o fake foi chamado 1x
    com o profile esperado — prova que GUI não tem caminho de execução paralelo/diferente do da CLI.
- `tests/test_screen_thread_marshalling.py`
  - `test_perspective_screen_never_touches_tk_off_main_thread(monkeypatch)`: substitui
    `PerspectiveScreen.frame` por um objeto dublê cujo `.after(delay, fn, *a)` chama `fn(*a)`
    **imediatamente e registra o nome da thread corrente**; dispara `on_show(video_path=fixture_path)`;
    espera a thread interna (`run_async`) terminar (`thread.join(timeout=2)`); assert que toda mutação de
    widget (rastreada via spies nos métodos `load_image_on_ui_from_cv2`/etc do dublê) só ocorreu durante a
    chamada de `.after`, nunca antes.
- `tests/test_orientation_screen.py`
  - `test_vertices_for_face_returns_4_distinct_vertices_per_face()` — para as 6 faces.
  - `test_save_orientation_rejects_duplicate_vertex_assignment()`.
  - `test_save_orientation_writes_profile_config(monkeypatch)` — monkeypatcha
    `AppService.save_orientation`, aciona o botão "Salvar orientação" com as 2 câmeras completas, assert
    `BoxOrientationConfig` recebido bate com o esperado.
- `tests/test_export_plugins.py`
  - `test_pdf_render_html_missing_border_metrics_shows_placeholder()`: `AnalysisContext` sem métricas
    `time_border_*`; `render_html(ctx, "t")` não lança, contém `"N/D"` 3 vezes.
  - `test_pdf_exporter_writes_file(tmp_path)`.
  - `test_plot_exporter_breaks_segments_on_missing_frame_index()` — regressão da migração de sentinela
    `(-1,-1,-1)` pra buraco de dict.
  - `test_export_plugin_manifests_discovered_as_exporter_kind()`.
- `tests/test_capture_bugfixes.py`
  - `test_get_image_from_frame_queue_signature_has_no_self()` — via `inspect.signature`.
  - `test_get_image_from_frame_queue_unexpected_exception_propagates()` — fila fake cujo `.get()` levanta
    `RuntimeError`; assert `pytest.raises(RuntimeError)` (prova que o `except` deixou de ser genérico).
  - `test_record_loop_read_failure_before_recording_sets_error_and_exits(monkeypatch)`: fake
    `cv2.VideoCapture` cujo `.read()` retorna `(False, None)` já na 1ª chamada, ainda em fase de preview
    (`start_recording` não setado); roda o loop numa thread; `thread.join(timeout=1)`; assert
    `not thread.is_alive()` e `error_event.is_set()` — regressão direta do bug #5 (prova que não há mais
    loop infinito).

---

## 9. Comandos de verificação

```bash
# instalação
pip install -e .[dev]

# suite completa
pytest

# só os novos desta fase
pytest tests/test_cli_e2e.py tests/test_cli_list_plugins.py tests/test_cli_validate_config.py \
       tests/test_service.py tests/test_gui_smoke.py tests/test_screen_thread_marshalling.py \
       tests/test_orientation_screen.py tests/test_export_plugins.py tests/test_capture_bugfixes.py -v

# GUI smoke em CI Linux (precisa de display virtual)
xvfb-run -a pytest tests/test_gui_smoke.py -v

# lint/tipos
ruff check src/app src/stages/export
mypy src/app src/stages/export

# checagem manual rápida de "CLI não importa Tk"
python -c "import sys; from src.app import cli; assert 'tkinter' not in sys.modules; print('OK: CLI headless')"

# rodada manual ponta-a-ponta (headless)
python -m src.app.cli run --workspace ./tmp_ws --profile fixture01
# ou, via launcher raiz:
python __init__.py run --workspace ./tmp_ws --profile fixture01

# rodada manual da GUI (abre janela)
python __init__.py

# comparação visual final (exigida pelo ARCHITECTURE.md a partir da Fase 4)
# — comparar ./tmp_ws/outputs/fixture01/{result.json,report.pdf} e o gráfico 3D
#   contra o output equivalente do pipeline legado, antes de apagar código velho.
```

---

## 10. Handoff — checkpoint seguro por workstream

Cada workstream escreve `docs/handoffs/fase4-<workstream>-handoff.md` seguindo o template do
`ARCHITECTURE.md` (`Status: done | in-progress | blocked`). Definição de "seguro pra entregar mesmo
incompleto" por workstream:

- **4.0 (contrato)**: não é seguro entregar parcialmente — se o agente ficar sem orçamento no meio, o
  handoff **deve** dizer explicitamente "interface ainda não congelada, NÃO abrir C nem D a partir daqui";
  não há meio-termo aceitável aqui porque C e D consomem essa interface por igual.
- **A — CLI**: seguro por comando individual. Ex.: `run` implementado+testado, `list-plugins` e
  `validate-config` ainda não — handoff lista exatamente quais dos 3 comandos estão prontos, quais faltam,
  e aponta pro teste correspondente que prova cada um.
- **B — Export plugins**: seguro por exportador. Ex.: `pdf-report` pronto+testado, `route-plot` não
  começado — handoff diz qual dos 2 arquivos (`plot/plugin.py` vs `pdf/plugin.py`) está pronto.
- **C — GUI refactor**: seguro **por tela**, não por commit genérico. Uma tela só conta como "done" se (a)
  implementa `Screen` por completo, (b) toda mutação de widget passa por `run_async`/`after()`, (c) tem
  teste próprio. Handoff lista as 6 telas (`config_hub`, `perspective_top`, `perspective_side`,
  `border_top`, `border_side`, `record_webcam`) com status individual — nunca "GUI parcialmente feita"
  genérico.
- **D — OrientationUi**: seguro entregar a "primeira versão funcional" (widgets + estado + gravação em
  `ProfileConfig`) mesmo antes do polimento visual do plano de UX estar pronto — handoff deve declarar
  explicitamente se está bloqueado esperando `docs/plans/ux-design-detalhado.md` ou se seguiu com a forma
  técnica mínima definida na seção 4 deste plano.
- **Integração final (seção 7, passo sequencial)**: só é "done" com os 4 workstreams mergeados **e**
  suite completa (seção 9) verde **e** comparação visual manual feita. Uma integração parcial (ex: 3 de 4
  mergeados) é sempre `blocked`, com o handoff apontando exatamente qual workstream falta e linkando pro
  handoff dele.

Ao final da Fase 4 inteira (todos os 5 checkpoints acima em `done`), atualizar `docs/handoffs/PROGRESS.md`
(arquivo mestre) linkando os 5 handoffs desta fase e apontando a Fase 5 como próxima ação.
