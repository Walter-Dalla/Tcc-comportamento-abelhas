# Handoff: Fase 4 — Interface dupla (CLI + GUI na mesma orquestração)
Status: done
Última atualização: 2026-07-24

Fase executada por um único agente (não em worktrees paralelos), mas respeitando a
ordem lógica do plano: 4.0 (contrato) primeiro, depois A/B/C/D, depois integração
(launcher + verificação). Todos os 5 checkpoints da seção 10 do plano em `done`.

## O que foi feito

### 4.0 — contrato compartilhado (sequencial, feito 1º)
- `src/app/gui/screen.py` — `Screen` Protocol (`build`/`on_show`/`on_hide`/`teardown`,
  `frame`) + `ScreenBase.run_async(work, on_done, on_error)` que marshalla os callbacks
  pro main thread via `self.frame.after(0, ...)`. Defaults no-op de `on_hide`/`teardown`/
  `on_show` no `ScreenBase` (fix (a) do plano — sem eles o dispatcher quebraria com
  AttributeError).
- `src/app/service.py` — `AppService` (todos os métodos implementados, não stub) +
  `SessionState` (estado de config compartilhado pelas telas, substitui os `StringVar`
  no root Tk). `ProgressEvent`.
- **Decisão de nomenclatura**: o plano fala em `ProfileConfig`; o modelo real da Fase 1
  chama-se `Profile` (`src/core/schema/profile.py`) e **já tinha** o campo
  `orientation: BoxOrientationConfig | None`. Logo a etapa 0.3 do plano ("adicionar campo
  orientation") já estava satisfeita — nenhuma mudança de schema foi necessária.
- `src/app/runner.py` — runner Tk-free compartilhado por CLI e GUI.
- `src/app/orientation_util.py` — `vertices_for_face`, `validate_selection`,
  `validate_orientation` + mensagens PT (fonte única CLI+GUI).
- `src/app/plugins.py` — `default_search_paths(ws)` = `plugins/` (metadata) +
  `src/stages/export/` (exporter) + `<ws>/plugins`.
- `src/core/plugin_registry.py::manifests(kind=None)` — acessor read-only aditivo
  (o plano usava `registry.all()`, inexistente; adicionado sem redesenhar contrato).
- Assinaturas de tela congeladas: `ConfigHubScreen(service, show)`,
  `PerspectiveScreen(service, role, show)`, `BorderScreen(service, role, show)`,
  `RecordWebcamScreen(service, show)`, `OrientationScreen(service, show)`.

### Contrato Fase 3 confirmado (leitura, para B e D)
- `RunRequest(profile: str, workspace: str, plugin_selection, gpu, overrides)`.
- `Pipeline.run(request)` **só roda metadata** sobre um `AnalysisResult` já persistido.
  A análise completa (Capture→Fuse + metadata) é `run_cpu_analysis(profile: Profile) ->
  AnalysisResult` em `src/stages/orchestration.py`. Por isso o runner/serviço delegam a
  `run_cpu_analysis`, não a `Pipeline.run` (reconciliação registrada em `runner.py`).
- `Calibration(box_cm: Point3D, px_per_cm: Point3D, fps: float, orientation)`.
- Convenção de eixo (schema Fase 1, `orientation.py`): **X=largura (LEFT/RIGHT),
  Y=altura (TOP/BOTTOM), Z=profundidade (FRONT/BACK)**.
- `ResultStore.save` grava em `<ws>/outputs/<profile>.json` (arquivo único por perfil).

### A — CLI (`src/app/cli.py`)
- `run --profile [--workspace] [--config] [--gpu]`: roda `execute_analysis` +
  exporters `route-plot`/`pdf-report` headless. `--gpu` sem CUDA → exit 2; erro de
  domínio → exit 1 sem traceback.
- `list-plugins [--workspace] [--kind]`: lista manifests (sem instanciar).
- `validate-config [--workspace] [--profile] [--config]`: valida orientação do perfil.
- **Não importa tkinter** (verificado por teste em subprocesso).

### B — plugins exporter (`src/stages/export/{plot,pdf}/`)
- `pdf-report` e `route-plot` como plugins `exporter` com `plugin.toml`.
- Acesso defensivo (`get_metric`/`N/D`), sem `KeyError` em métrica ausente.
- PDF: linhas `px_per_cm.x/y/z` (fix (d) do plano); `box_cm.x/y/z` =
  largura/altura/profundidade seguindo a convenção do schema (o exemplo do plano
  trocava y/z — segui o schema real, ver "Decisões" abaixo).
- Plot: quebra segmento por buraco de índice no dict (oclusão), não sentinela `-1`;
  salva PNG headless (backend Agg, sem `plt.show`).

### C — GUI (`src/app/gui/`)
- `main_window.py`: dispatcher único `show(name, **kwargs)`.
- `screens/config_hub.py`: "Processar vídeo" → `service.run_pipeline` (mesmo caminho da
  CLI), via `run_async`. Botões de orientação com guarda de pré-condição.
- `screens/perspective.py`: **corrige o bug de thread-safety** — I/O em `run_async`,
  mutação de widget só em `on_done` via `after()`. O `while+sleep` virou "recomputa 1x
  no 4º clique" (equivalente visual — registrado como mudança visualmente idêntica).
- `screens/border.py`, `screens/record_webcam.py` portadas ao protocolo.
  `record_webcam` usa `after(33)` no main thread em vez da thread solta tocando Tk.

### D — OrientationScreen (`src/app/gui/screens/orientation.py`)
- Wireframe isométrico de cubo (Canvas) + 4 dropdowns filtrados pela face +
  validação inline (mensagens PT). Grava `BoxOrientationConfig` via `save_orientation`
  quando as duas câmeras estão completas. Forma técnica mínima da seção 4 do plano +
  UX da seção 2 do `ux-design-detalhado.md` (miniatura de vídeo com pontos deixada como
  próximo incremento — não bloqueante).

### Bugs #4 e #5
- `src/app/gui/preview.py::get_image_from_frame_queue` — função livre (sem `self`),
  `except Empty`. `src/stages/capture/webcam.py::record_webcam_video` — checagem de `ret`
  antes/fora de `start_recording`, seta `error_event`. `start_webcams` retorna dict.

### Integração
- Novo `__init__.py` (launcher: CLI por argv sem importar Tk, senão GUI).
- `pyproject.toml`: `[project.scripts] animaltrack = "src.app.cli:app"` +
  ruff `flake8-bugbear.extend-immutable-calls = ["typer.Option","typer.Argument"]`.

## O que falta
Nada bloqueante para fechar a Fase 4. Incrementos opcionais (não exigidos pelo plano):
- Miniatura de vídeo com os 4 pontos numerados na `OrientationScreen` (UX 2.1) — a
  versão atual já satisfaz o requisito funcional (associar vértice a canto).
- Preview de debug do Detect na GUI (seção 6 do UX, "pergunta em aberto") — fora de escopo.
- `--config pipeline.toml` do CLI é aceito mas ainda não parseado (reservado p/ quando o
  `pipeline.toml` por perfil existir).

## Como verificar o que já foi feito
Do diretório raiz do repo:
- `pytest` → **204 passed** (era 175; +29 novos). Golden-file continua verde.
- `ruff check .` → **All checks passed!**
- `mypy src tests --python-version 3.13` → **Success: no issues found in 115 source files**.
- `python -c "import sys; from src.app import cli; assert 'tkinter' not in sys.modules"` → OK.
- `python __init__.py list-plugins` → lista os 4 plugins (2 metadata + 2 exporter).
- GUI: `python __init__.py` abre a janela sem erro de import (7 telas montadas —
  confirmado com launch auto-fechável).
- Novos testes: `pytest tests/test_cli_e2e.py tests/test_cli_list_plugins.py
  tests/test_cli_validate_config.py tests/test_service.py tests/test_gui_smoke.py
  tests/test_screen_thread_marshalling.py tests/test_orientation_screen.py
  tests/test_export_plugins.py tests/test_capture_bugfixes.py -v`.

Deps novas instaladas neste ambiente: `typer`, `xhtml2pdf` (já pinadas no `pyproject`).

## Como retomar / decisões pendentes de confirmação do dono
- **Mapeamento box_cm→PDF**: o exemplo do plano (seção 2.3) usava `Altura=box_cm.z`,
  `Profundidade=box_cm.y`. Segui a convenção real do schema Fase 1
  (`Altura=box_cm.y`, `Profundidade=box_cm.z`) — o plano marca essa correspondência como
  "consumida, não decidida por B". Confirmar com o dono se a rotulagem PT bate com a
  expectativa experimental.
- **`Pipeline.run` vs `run_cpu_analysis`**: mantive `Pipeline.run` intocado (só metadata,
  como Fase 2/3 deixaram) e fiz CLI/GUI usarem `run_cpu_analysis`. Se no futuro
  `Pipeline.run` passar a orquestrar a pipeline inteira, o runner deve migrar pra ele.
- **`SessionState` no `AppService`**: introduzido para compartilhar estado entre telas sem
  quebrar as assinaturas de construtor congeladas (só `service`/`role`/`show`). É a decisão
  de design mais além do texto literal do plano; funcionalmente equivalente ao "estado
  espalhado entre telas irmãs" do legado, agora centralizado.
- Próxima fase: **Fase 5** (backends GPU) e/ou **Fase 6** (marketplace/tracker multi-animal)
  — podem rodar em paralelo (ARCHITECTURE.md).
