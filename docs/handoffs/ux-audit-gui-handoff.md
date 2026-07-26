# Handoff: UX audit — GUI real vs `docs/plans/ux-design-detalhado.md`
Status: done
Última atualização: 2026-07-26

Auditoria da GUI **implementada** na Fase 4 (`src/app/gui/*`) contra o documento de
UX que foi escrito **antes** dela (`docs/plans/ux-design-detalhado.md`), incluindo a
resolução da pergunta deixada em aberto na seção 6. Base: `de67528` (rearquitetura
0-6 completa). Antes de mexer em qualquer coisa, o handoff da Fase 4
(`fase4-integracao-handoff.md`) foi lido para separar **desvio deliberado** de
**lacuna real** — só as lacunas foram corrigidas.

## O que foi feito

### 1. Fluxo e guardas (UX seção 1.2 + tabela da seção 5) — commit `dc5d3ea`
- `src/app/gui/screens/config_hub.py::_processing_error` (novo): "Processar vídeo"
  não tinha **nenhuma** pré-condição além do nome do perfil. Agora espelha o
  `MainConfigurationInterface.is_video_valid()` legado (vídeo → `"Video não
  configurado."`; 4 pontos de perspectiva por câmera → `"Bordas não configuradas."`,
  texto do legado mantido verbatim por causa da seção 5) e **acrescenta** a guarda
  de orientação das duas câmeras exigida pela seção 1.2 (`"Orientação da câmera não
  configurada."`), reusando `orientation_util.validate_orientation` — a mesma fonte
  de verdade do `animaltrack validate-config`.
- `src/app/gui/screens/perspective.py::_finish`: passa a oferecer o auto-avanço
  opcional da seção 1.2 — `messagebox.askyesno("Perspectiva salva", "Perspectiva
  salva. Configurar orientação desta câmera agora?")`; "Sim" navega para
  `orientation` daquela câmera, "Não" volta ao hub como antes. `on_show` guarda o
  `video_path` para repassar. O botão "Voltar"
  (`_finish_without_config`, fallback "sem correção") NÃO oferece nada — a seção
  1.2 amarra a oferta ao "Finalizar perspectiva".
- Botão **"Executar módulos de metadados"** restaurado no hub (existia no legado e
  nos dois diagramas de fluxo do UX; tinha sumido na porta da Fase 4). Backing novo:
  `AppService.run_metadata` → `Pipeline.run` (estágio de metadata isolado da Fase 2)
  sobre o `AnalysisResult` já persistido — exatamente o fluxo "reprocessar sem
  refazer etapas anteriores" da seção 5. `src/app/plugins.py::metadata_search_paths`
  mantém a varredura igual à de `run_cpu_analysis` (built-in `plugins/` + workspace),
  de propósito sem os plugins de *exemplo* (`plugins/metadata/`), para que
  reprocessar metadata não mude o resultado de um run completo.

### 2. `OrientationScreen` conforme a seção 2 — commits `8dbf3a7`, `6ccc28d`
A tela existia, mas a interação central especificada (**escolher a face clicando no
cubo**, 2.2 item 4 / 2.3) não tinha sido implementada — só havia um combobox de face.
Isso não estava registrado como desvio no handoff da Fase 4 (que só documentou a
miniatura como incremento pendente), então foi tratado como lacuna:
- 6 polígonos clicáveis, um por face, com tag própria (`face_top`, `face_bottom`,
  `face_left`, `face_right`, `face_front`, `face_back`), `tag_bind("<Button-1>")`,
  `stipple="gray25"` no estado neutro e preenchimento azul sólido na face escolhida.
  **Decisão de projeto:** numa projeção isométrica de cubo sólido as 6 faces se
  sobrepõem em tela (a de trás ficaria inteiramente coberta e nunca clicável); cada
  face é desenhada como um adesivo encolhido para o próprio centroide
  (`_PATCH_SCALE = 0.45`) + nome PT da face por cima, garantindo área exclusiva de
  clique para as 6. O combobox de face continua como caminho alternativo,
  sincronizado com o clique.
- Rótulos de vértice deslocados para fora e nomes de face para dentro
  (`_offset_from_center`) — na isométrica o centro de uma face cai sobre um vértice
  da face oposta (centro de "Fundo" sobre `TFR`, de "Frente" sobre `BBL`).
- **Miniatura do 1º frame com os 4 pontos numerados** (2.1, o incremento que a Fase 4
  deixou pendente): `build_thumbnail` (função pura, testável) desenha círculos azuis
  + números 1-4 na ordem de clique; carregada via `run_async` (I/O fora do main
  thread, `ImageTk.PhotoImage` só em `on_done`). Falha de vídeo não vira modal — só
  troca o texto do label (é auxílio visual, não bloqueia a tarefa). Sem bind de
  clique/magnifier na miniatura (seção 2.7 preservada).
- Placeholder `"Escolha a face primeiro"` nos comboboxes desabilitados (2.4).
- Aviso `"Face alterada — selecione novamente os vértices dos 4 pontos."` só quando
  algo foi de fato resetado; antes aparecia já na 1ª escolha de face.
- **Bug de layout**: rótulo do ponto e combobox estavam na MESMA célula do grid
  (`row=i, column=0`, um com `sticky="e"` e outro `"w"`). Agora há as duas colunas do
  desenho de 2.1 (miniatura + 4 pontos + erro inline à esquerda; wireframe +
  confirmação de face à direita) e o trio de botões centralizado embaixo.

### 3. Seção 6 — pergunta em aberto RESOLVIDA (Opção 2) — commit `95a41c2`
Implementada a Opção 2 (recomendação implícita do próprio documento): sem preview ao
vivo, export de frames para inspeção pós-hoc.
- `src/stages/detect/debug.py::DebugFrameWriter`: grava
  `<workspace>/debug/<perfil>/<view>/frame_NNNNNN_{det,nodet}.png` a partir de uma
  **thread daemon própria**, alimentada por fila **limitada** com `put_nowait`. Se a
  gravação não acompanha o processamento, o frame é **descartado** (contado em
  `dropped`) em vez de segurar o pipeline. Nem a thread do pipeline nem a main thread
  do Tk bloqueiam em nenhum momento. Amostragem: 1 a cada N frames **+ todo frame em
  que a detecção falhou** (o caso que o pesquisador quer inspecionar).
- `BackgroundSubtractionDetector(..., debug=...)` opcional; sem writer o custo é um
  `if`. Teste trava que o `FrameDetections` é idêntico com e sem debug.
- Mesma pasta pelos dois pontos de entrada: `animaltrack run --debug-frames` (CLI,
  ecoa o caminho no fim) e, na GUI, a caixa "Exportar frames de debug" + o botão
  **"Abrir pasta de debug"** (`src/app/open_folder.py`, `os.startfile`/`Popen` — abre
  o explorador do SO sem bloquear). `Workspace.debug`/`debug_dir(profile)` é a fonte
  única do caminho.
- **Por que não a Opção 1**: exigiria um segundo consumidor do stream de frames + uma
  tela nova de "processamento com preview"; o próprio UX a coloca como alvo de médio
  prazo, não como mínimo viável. Nada do que foi feito aqui atrapalha a Opção 1
  depois — o writer é só mais um consumidor plugável no mesmo ponto do Detect.

### Conformidades verificadas (auditadas, nada mudado)
- Seção 2.5: as 4 mensagens PT exatas vivem em `src/app/orientation_util.py`,
  verbatim, e são exibidas **inline** (`ttk.Label` vermelho), não em modal.
- Seção 2.7: magnifier NÃO reaproveitado na `OrientationScreen` (deliberado).
- Seção 3: trio Resetar/Finalizar/Voltar, `ttk.Button` nas telas satélite,
  `tk.Button` no hub, `grid(padx=10, pady=10)`.
- Seção 4: `animaltrack validate-config` chama `validate_orientation` — mesmas 4
  regras e mesmo texto PT que a GUI (fonte única, sem duplicação de linguagem).
- Seção 5, item a item: sentinela `"Novo perfil de analise"` sempre no topo do
  combobox; ordem fixa dos 4 cliques de perspectiva; drag por vértice do `BorderUi`
  (retângulo axis-aligned) intacto; hub único sem abas; magnifier preservado no
  `PerspectiveScreen`; rótulos PT-BR existentes não retrabalhados; exportar
  gráfico/PDF sem reprocessar vídeo.

## O que falta
Nada bloqueante. Itens conscientemente fora de escopo:
1. **Opção 1 da seção 6** (preview embutido ao vivo) — alvo de médio prazo, como o
   próprio UX diz. Só faz sentido quando/se houver custo zero de I/O para um 2º
   consumidor do stream.
2. **`CudaMOG2Detector` não exporta frames de debug** — só o detector CPU foi
   instrumentado. Quando o caminho CUDA for executável de verdade (bloqueio de
   packaging da Fase 5), replicar o mesmo `debug=` lá.
3. **`--config pipeline.toml` continua aceito e não parseado** (débito herdado da
   Fase 4, registrado no PROGRESS). O schema TOML de orientação proposto na seção 4
   do UX só vira código quando o `pipeline.toml` por perfil existir.
4. `"Bordas não configuradas."` como mensagem para **pontos de perspectiva** faltando
   é um texto enganoso do legado, preservado verbatim por causa da regra "não
   retrabalhar copy existente" (seção 5). Se o dono quiser corrigir a copy, é uma
   linha em `config_hub._processing_error`.

## Como verificar o que já foi feito
Da raiz do worktree:
- `pytest` → **311 passed, 3 skipped** (era 279/3; +32 testes). Os 3 skips são os de
  CUDA, pré-existentes.
- `ruff check .` → All checks passed!
- `mypy src tests --python-version 3.13` → Success (141 arquivos).
- Testes novos: `pytest tests/test_gui_flow_guards.py tests/test_debug_frames.py
  tests/test_orientation_screen.py -v`.
- Paridade CLI da seção 6: `pytest tests/test_cli_e2e.py -k debug_frames` (roda
  `animaltrack run --debug-frames` de verdade na fixture e confere os PNGs).
- **Smoke manual de GUI: FEITO neste ambiente** (há display Tk). Um script temporário
  abriu a janela real (`MainWindow` + `AppService` em workspace temporário), tentou
  "Configurar orientação" sem perspectiva (guarda barrou, sem troca de tela), navegou
  para a `OrientationUi` com um vídeo de fixture, clicou numa face pelo mesmo callback
  do polígono e voltou ao hub. Resultado: `guard-ok`, `orientation-shown`,
  `face=Face selecionada: Topo`, `combo_state=readonly`, `thumb=img` (miniatura
  carregada), `back-to-hub` — sem exceção. A geometria do wireframe também foi
  inspecionada visualmente (render PIL da mesma geometria) para confirmar que as 6
  faces têm área de clique exclusiva e os rótulos não se sobrepõem.

Nota de ambiente (pré-existente, não introduzida aqui): rodar **um único** arquivo de
teste de GUI isolado com captura de saída ligada pode falhar ao criar o `tk.Tk()` da
fixture de sessão e **pular** os testes silenciosamente; na suíte completa (ou com
`-s`) eles rodam normalmente. Vale conferir o total de `passed` ao rodar arquivos de
GUI avulsos.

## Como retomar
- Próximo passo natural: nada nesta frente. Se o dono quiser evoluir a seção 6, o
  caminho é a Opção 1 (item 1 acima), reusando `DebugFrameWriter` como referência de
  ponto de extensão no Detect.
- **Decisões que só o dono confirma** (todas implementadas conforme a recomendação do
  próprio UX; nenhuma bloqueia):
  1. Restauração do botão "Executar módulos de metadados" ligado a `Pipeline.run`
     (metadata sobre resultado persistido) — confirmar que é o comportamento
     esperado, e se plugins de metadata *instalados no workspace* devem rodar aí
     (hoje rodam) enquanto os de exemplo do repo não.
  2. Adesivos encolhidos por face no wireframe (em vez de faces inteiras clicáveis) —
     é o único jeito de deixar a face de trás alcançável na projeção isométrica.
  3. Amostragem padrão do debug (`every=100` + toda falha de detecção) e o descarte
     silencioso quando a fila enche.
  4. Manter a copy enganosa `"Bordas não configuradas."` para perspectiva ausente.
