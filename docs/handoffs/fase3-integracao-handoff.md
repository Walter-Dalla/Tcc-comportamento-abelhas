# Handoff: Fase 3 — pipeline de cálculo → estágios streaming (consolidado + integração)
Status: done
Última atualização: 2026-07-23

> Integração TENTADA e BEM-SUCEDIDA: o golden-file test
> (`tests/test_golden_pipeline.py`) foi de fato executado e passa (8/8). Os 5
> estágios compõem corretamente. Seguro prosseguir para a Fase 4.

## O que foi feito

### Estágios streaming (`src/stages/`)
Todos implementados como `Plugin`/`Detector`/`Tracker` das bases da Fase 2, com
`plugin.toml` co-localizado (formato marketplace-ready, mas instanciados
diretamente pelo orquestrador nesta fase — precisam de args de construtor que o
registry no-arg não fornece).

- `src/core/frames.py` — `FramePair`/`RectifiedFrame` (dataclasses frozen; carregam
  `np.ndarray`, não são pydantic — só existem em memória durante o run). `stages.py`
  atualizado para apontar o alias `RectifiedFrame` (antes `object`) para o tipo real.
- `src/stages/capture/plugin.py` — `DualVideoFileCapture`. `open()→(fps, Iterator[FramePair])`
  streaming, lockstep no vídeo mais curto; `open_single(role)→Iterator[np.ndarray]`
  (leitura por-view sem lockstep, p/ o passe 1 do Detect); `dimensions(role)`;
  `CaptureError` explícito (torna bug #1 obsoleto). **Desvio do plano**: leitura
  SÍNCRONA (sem threads/filas) — mesmo perfil de memória O(1), determinística,
  mais simples; threading fica como otimização de throughput futura.
- `src/stages/rectify/plugin.py` — `CpuPerspectiveRectifier`. Matriz calculada 1x em
  `__init__` (não por frame como o legado); `rectify(frame, frame_index)→RectifiedFrame`;
  fallback de 4 pontos default idêntico ao `process_perspective`. Orientação entra só
  como metadado anexado (o warp não depende dela).
- `src/stages/detect/plugin.py` — `BackgroundSubtractionDetector`. Modelo de fundo em
  **duas passadas**: passe 1 em `setup()` (amostra a cada `frame_block=500`,
  `np.max(sampled, axis=0)`, lê SÓ a própria view via `open_single` até o fim do seu
  vídeo); passe 2 em `detect()` (absdiff→duplo threshold 80/127→findContours→maior
  contorno→centroide com `cy_from_bottom`). Saída `FrameDetections` (lista vazia, sem
  sentinela `-1,-1`). Modo debug/`waitKey` removido. **Desvio do plano**: Capture+Rectify
  são injetados via construtor (não `ctx.capture_factory`/`rectifier_factory`) — evita
  estender o `PipelineContext` da Fase 2 e mantém o detector testável com fakes.
- `src/stages/track/plugin.py` — `SingleEntityTracker(view)`. `entity_id=0`, 1 ponto/frame,
  buracos = oclusão.
- `src/stages/fuse/plugin.py` — `Fusion.fuse(...)→(routes, Calibration)` + `build_border_region(...)`.
  **Usa o `BoxOrientationConfig.axis_mapping()` do schema (Fase 1)** como fonte de verdade —
  NÃO reimplementa o `_resolve_camera_axis_mapping`/`combine` do rascunho da seção 4.1 do
  plano (ver "Decisões" abaixo). `px_per_cm` por eixo (bug #3); rota já sai em cm (raiz do
  bug #2); interseção explícita de índices (substitui `min(len,len)`).
- `src/stages/orchestration.py` — `run_cpu_analysis(profile)→AnalysisResult`. Compõe os 5
  estágios (2 passes do Detect + passada pareada streaming) e roda os plugins de metadata
  (`speed`/`border`) via `PluginRegistry` (respeita `border after speed`). É o papel que o
  `processVideoModule.py` (apagado) tinha.

### Plugins de metadata (`plugins/`)
- `plugins/speed/plugin.py` — **reescrito** (bugs #2 e #6). Rota já em cm →
  `velocidade = dist_cm/(1/fps)`, sem nenhuma divisão por ratio; `average_speed` divide
  por `n-1` amostras. Métrica mantém o nome `"speed"` (não `"speed_by_frame"` do plano)
  para preservar as chaves do teste e2e da Fase 2; unidade agora `cm/s`.
- `plugins/border/plugin.py` — **inalterado**: já era o contador de containment correto
  (compara cm vs cm sobre `BorderRegion.bounds`). A conversão px→cm dos pontos de borda
  vive em `fuse.build_border_region` (onde `axis_mapping`/`px_per_cm` já existem), não no
  plugin — resolve o bug latente da seção 4.5 sem duplicar lógica.

### Legado apagado / GUI
- Apagados: `processVideoModule.py`, `perspectiveModule.py`, `backgroundRemoveModule.py`,
  `routeAnalizer.py`, `utils/getData.py` (critério 6 da seção 7).
- `configurationUI.py`: removidos os 2 imports legados; `get_perspective_size` inlinado
  (só usado p/ limites do gráfico 3D); botão "Processar vídeo" vira mensagem de migração
  (a ligação real da GUI ao novo pipeline precisa da tela de Orientação = Fase 4).
- `perspectiveUi.py`: `perspective()` inlinado (só usado no preview da tela).
  A GUI (`python __init__.py`) volta a bootar; o processamento de fato migra na Fase 4.

### Testes
- `tests/stages/test_stage_{capture,rectify,detect,track,fuse}.py` — unit tests por estágio
  (Detect contra fakes de Capture/Rectify). Inclui regressão de `px_per_cm` por eixo (bug #3)
  e de `axis_mapping()` reproduzir as fontes do hardcode legado (x←top.U, y←top.V, z←side.V).
- `tests/plugins/test_speed_plugin.py` — atualizado p/ a fórmula corrigida.
- `tests/fixtures/generate_fixture_videos.py` — gerador determinístico (blob escuro em fundo
  claro, 1200 frames 320x240, codec **FFV1 lossless**). Vídeos commitados em
  `tests/fixtures/videos/` (main_top/side 1200; uneven_top 1200 / uneven_side 1600).
- `tests/fixtures/golden_config.py` — orientação + perfil do golden.
- `tests/fixtures/golden/expected_result.json` — `AnalysisResult` de referência (commitado).
- `tests/test_golden_pipeline.py` — golden-file (tolerâncias da seção 5.3), memória limitada
  (`tracemalloc`, teto 50 MB; pico medido ~2.9 MB), validação recuperado≈sintético (<0.5 cm),
  fps-vem-do-topo, truncamento por comprimento diferente.

## O que falta
Nada bloqueante para a Fase 3. Itens de acompanhamento (não bloqueiam):
- **Risco de paridade cross-versão do golden** (importante): o golden foi gerado localmente
  com **cv2 5.0.0 / numpy 2.5.1**; o CI fixa **opencv-python 4.9.0.80 / numpy 1.26.3**. Como
  os vídeos são FFV1 lossless, o DECODE é pixel-exato entre versões, mas `findContours`/
  `moments` podem, em tese, produzir centroides marginalmente diferentes entre OpenCV 4.9 e
  5.0. Se o golden falhar no CI por isso, regenerar `expected_result.json` sob o OpenCV do CI
  (`python -m tests.fixtures.generate_fixture_videos` NÃO é necessário — só reexecutar o
  pipeline e reserializar; os vídeos não mudam). Tolerâncias atuais: 1e-6 (rota/px_per_cm),
  1e-4 (somas), exato (estrutural) — deliberadamente apertadas para pegar regressão real.
- `speed`/`border` mantêm `plugins/*/plugin.toml` com `[ordering]` — ok.
- `videoUtils.py`/`folderUtils.py`/`recordVideo.py` NÃO foram tocados (migração Capture é
  Fase 3–4; ficam p/ a Fase 4 junto com a GUI).

## Como verificar o que já foi feito
```
python -m pytest -q                                  # 175 passed
python -m pytest tests/test_golden_pipeline.py -v     # 8 passed (golden + memória + validações)
python -m pytest tests/stages -q                      # 26 passed (unit por estágio)
python -m ruff check .                                # All checks passed!
python -m mypy src tests --python-version 3.13        # Success: no issues found in 84 source files
```
Regenerar as fixtures (só se precisar): `python -m tests.fixtures.generate_fixture_videos`.

## Como retomar (→ Fase 4)
Próximo passo: **Fase 4** (CLI + GUI na mesma orquestração). Pontos de ancoragem que a Fase 3
já deixou prontos:
- `src.stages.orchestration.run_cpu_analysis(profile)` é o ponto de entrada único da pipeline
  CPU — a CLI (`animaltrack run`) e o botão "Processar vídeo" da GUI devem chamá-lo (a GUI hoje
  só mostra a mensagem de migração). Ele exige `profile.orientation` populado.
- A tela **OrientationUi** (Fase 4) é o pré-requisito que falta para a GUI: sem
  `profile.orientation`, `run_cpu_analysis` levanta `ValueError`. `tests/fixtures/golden_config.py`
  mostra uma orientação válida de exemplo (top vê FRONT, side vê TOP → x←top.U, y←top.V, z←side.V).
- Export (`plotRoute`/`pdfFactory`) ainda consome o dict/JSON antigo — refatorar p/ ler
  `AnalysisResult` novo é tarefa da Fase 4 (acesso defensivo a métrica).

Decisões que só o dono pode confirmar (não bloqueiam a Fase 4):
- Nome da métrica de velocidade mantido `"speed"` (não `"speed_by_frame"` do plano) para não
  quebrar o teste e2e da Fase 2. Trocar depois é 1 linha + 2 testes se preferir o nome do plano.
- A convenção de eixos do schema (Y=altura via TOP/BOTTOM, Z=profundidade via FRONT/BACK)
  diverge da tabela da seção 4.1 do plano (Y=profundidade, Z=altura). Seguiu-se o SCHEMA
  (contrato mergeado da Fase 1). A `OrientationUi` da Fase 4 deve usar a convenção do schema.

## Decisões tomadas e por quê
1. **Usar `BoxOrientationConfig.axis_mapping()` do schema** em vez de reimplementar o
   `_resolve_camera_axis_mapping`/`combine` da seção 4.1: o schema (Fase 1, mergeado, 141 testes)
   já implementa o algoritmo E a política "TOP vence empate", com convenção de vértice própria.
   Reimplementar com a convenção divergente do plano criaria dois algoritmos conflitantes. O
   schema é o contrato.
2. **Capture síncrono** (sem threads): memória O(1) idêntica, determinístico, menos risco.
3. **Detect recebe Capture/Rectify via construtor** (não via `ctx`): não exige mexer no
   `PipelineContext` da Fase 2; mantém o furo de acoplamento da seção 3.4 isolado e testável
   com fakes. O orquestrador reusa o MESMO rectifier no passe 1 e no passe 2 (frames
   byte-idênticos entre passadas).
4. **Conversão px→cm de borda em `build_border_region`** (não no BorderPlugin): o schema
   `BorderRegion.bounds` já é definido em cm e o BorderPlugin da Fase 2 já compara cm vs cm;
   mover a conversão p/ o build evita duplicar `axis_mapping`/`px_per_cm`.
5. **Fixture de 1200 frames + FFV1 lossless**: 1200 > `frame_block`(500) exercita o `np.max`
   multi-amostra (índices 0/500/1000); lossless garante decode pixel-exato p/ o golden.
   Nota: com blob mais escuro que o fundo, `np.max` é invariante às posições amostradas, então
   o teste de comprimento-diferente valida o truncamento pareado (para em 1200, não 1600) e a
   leitura full-length por-view é validada diretamente no unit test do Detect
   (`test_setup_reads_full_length_not_truncated`).
