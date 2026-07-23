# UX detalhado — Fase 4 (Interface dupla: CLI + GUI)

> Este documento é o desdobramento de UX do `ARCHITECTURE.md` para a Fase 4 (ver tabela de fases e a
> seção "Orientação de câmera/caixa" nele). Não é uma especificação de código — é o desenho de tela,
> fluxo e interação que quem implementar a Fase 4 deve seguir. Escopo: telas Tkinter existentes
> (`mainUI.py`, `configurationUI.py`, `perspectiveUi.py`, `borderUi.py`, `recodWebCamVideo/
> recordWebcamVideoUI.py`), a nova tela `OrientationUi`, e o espelhamento do mesmo conceito no modo
> headless/CLI. Referências de código e de produto usadas: `CLAUDE.md`, `01-visao-produto.md`,
> `02-entrada-de-dados.md`, `03-processamento.md`, e o código-fonte atual das telas listadas acima.

---

## 1. Fluxo completo de telas (atual + novo)

### 1.1 Fluxo atual (hoje)

O hub (`MainConfigurationInterface`) é uma tela única com botões lineares; todas as outras telas são
`tk.Frame`s pré-criados e trocados via `show_frame()` (`tkraise()` + `grid()`), nunca janelas novas.
Fluxo atual, em ASCII:

```
                              ┌─────────────────────────────┐
                              │   Hub (MainConfigurationUI)  │
                              │                              │
                              │  [Capturar videos] ──────────┼──▶ RecordWebcamVideoUI
                              │  [Selecionar perfil]         │      (grava topo+lado, volta ao hub)
                              │  [Selecionar video topo]     │
                              │  [Selecionar video lado]     │
                              │                              │
                              │  [Configurar perspectiva     │
                              │   (topo)]  ───────────────────┼──▶ PerspectiveUi (topo)
                              │  [Configurar bordas (topo)] ──┼──▶ BorderUi (topo)
                              │                              │
                              │  [Configurar perspectiva     │
                              │   (lado)]  ───────────────────┼──▶ PerspectiveUi (lado)
                              │  [Configurar bordas (lado)] ──┼──▶ BorderUi (lado)
                              │                              │
                              │  Largura/Altura/Profund. (cm)│
                              │  [Salvar configurações]      │
                              │  [Processar video]           │
                              │  [Executar módulos metadata]  │
                              │  [Exibir gráfico de rota]     │
                              │  [Exportar para PDF]          │
                              └─────────────────────────────┘
                                     ▲  (show_frame de volta)
                                     │
     PerspectiveUi/BorderUi/RecordWebcamVideoUI ──┘  (Finalizar/Voltar sempre retornam ao hub)
```

Cada tela satélite (perspectiva/borda/gravação) é uma via de mão dupla simples: o hub navega até ela, ela
sempre volta pro hub — não há encadeamento tela→tela sem passar pelo hub.

### 1.2 Fluxo novo, com `OrientationUi` inserida

`OrientationUi` consome os 4 pontos de perspectiva **já clicados de uma câmera específica** (precisa
saber, para cada ponto, "isto é qual vértice da caixa") — portanto ela só faz sentido logicamente **depois
que a perspectiva daquela câmera foi finalizada**, e antes de configurar a perspectiva da outra câmera (o
usuário está com o contexto visual/mental dos 4 pontos ainda fresco). A posição exata no fluxo, por
câmera:

```
PerspectiveUi(topo)  ──finaliza──▶  OrientationUi(topo)  ──finaliza──▶  volta ao hub
PerspectiveUi(lado)  ──finaliza──▶  OrientationUi(lado)  ──finaliza──▶  volta ao hub
```

Fluxo completo do hub, com a nova etapa:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          Hub (MainConfigurationUI)                        │
│                                                                            │
│  [Capturar videos] ───────────────────────────────────▶ RecordWebcamVideoUI│
│                                                                            │
│  [Selecionar perfil]  [Selecionar video topo]  [Selecionar video lado]    │
│                                                                            │
│  ── Câmera do topo ──                                                     │
│  [Configurar perspectiva (topo)] ──▶ PerspectiveUi(topo)                  │
│                                         │ finaliza perspectiva             │
│                                         ▼                                 │
│                                    OrientationUi(topo)                     │
│                                         │ finaliza orientação              │
│                                         ▼                                 │
│                                    volta ao hub                           │
│  [Configurar orientação (topo)] ──▶ (mesmo destino acima, acesso direto)  │
│  [Configurar bordas (topo)]     ──▶ BorderUi(topo)                        │
│                                                                            │
│  ── Câmera lateral ──                                                     │
│  [Configurar perspectiva (lado)] ──▶ PerspectiveUi(lado)                  │
│                                         │ finaliza perspectiva             │
│                                         ▼                                 │
│                                    OrientationUi(lado)                     │
│                                         │ finaliza orientação              │
│                                         ▼                                 │
│                                    volta ao hub                           │
│  [Configurar orientação (lado)] ──▶ (mesmo destino acima, acesso direto)  │
│  [Configurar bordas (lado)]     ──▶ BorderUi(lado)                        │
│                                                                            │
│  Largura/Altura/Profundidade (cm)                                         │
│  [Salvar configurações] [Processar video] [Executar módulos de metadata]  │
│  [Exibir gráfico de rota] [Exportar para PDF]                             │
└──────────────────────────────────────────────────────────────────────────┘
```

Decisões de fluxo:

- **Auto-avanço opcional, não obrigatório.** Ao clicar "Finalizar perspectiva" em `PerspectiveUi`, a tela
  pode oferecer diretamente o próximo passo lógico — por exemplo, ao invés de só voltar ao hub, mostrar
  uma confirmação "Perspectiva salva. Configurar orientação desta câmera agora?" com botões "Configurar
  agora" / "Depois" (que apenas volta ao hub, igual hoje). Isso reduz fricção sem forçar uma sequência
  rígida — o pesquisador ainda pode reconfigurar perspectiva e orientação fora de ordem, revisitando pelos
  botões do hub.
- **Botão de orientação no hub sempre visível, mas com guarda de pré-condição.** Os botões "Configurar
  orientação (topo)"/"(lado)" ficam no hub ao lado dos de perspectiva já existentes (mesmo padrão visual:
  `tk.Button`, `pady=5, anchor="center"`). Se o usuário clicar em "Configurar orientação (topo)" antes de
  ter os 4 pontos de perspectiva daquela câmera, a ação deve mostrar
  `messagebox.showerror("Erro!", "Configure a perspectiva desta câmera antes de configurar a orientação.")`
  e não trocar de tela — mesmo padrão de guarda que `is_video_valid()` já usa hoje para bloquear
  processamento sem os 4 pontos.
- **Processar vídeo passa a exigir orientação válida das duas câmeras**, do mesmo jeito que hoje exige os
  4 pontos de perspectiva de cada câmera. Mensagem de erro proposta:
  `messagebox.showerror("Erro!", "Orientação da câmera não configurada.")`, seguindo o tom telegráfico já
  usado em `is_video_valid()` (`"Video não configurado."`, `"Bordas não configuradas."`).
- O hub continua sendo o único roteador (`show_frame`) — não introduzo abas, menu lateral, nem janelas
  novas. Isso é consistente com a diretriz do `ARCHITECTURE.md`: *"Telas antigas mantidas visualmente
  próximas da referência durante a transição, pra não reabrir decisões de UI não relacionadas."*

---

## 2. Design concreto da `OrientationUi`

Esta é a tela nova mais delicada do ponto de vista de usabilidade: o pesquisador (não programador) precisa
declarar corretamente (a) qual face da caixa aquela câmera enxerga de frente e (b) qual vértice da caixa
cada um dos 4 pontos já clicados representa — sem confundir eixo, sem inverter esquerda/direita, sem
duplicar vértice. Erro aqui corrompe silenciosamente o `axis_mapping()` inteiro (ARCHITECTURE.md,
`BoxOrientationConfig`), então a tela precisa **recusar combinações inválidas de forma explícita**, nunca
deixar passar em silêncio.

### 2.1 Layout geral

Divisão em duas colunas dentro do mesmo `tk.Frame`, seguindo o `grid()` já usado pelas telas irmãs:

```
┌───────────────────────────────┬───────────────────────────────────┐
│ Coluna esquerda (grid col 0)   │ Coluna direita (grid col 1)        │
│                                │                                    │
│  Miniatura do frame de vídeo   │  Wireframe da caixa (Canvas)       │
│  com os 4 pontos já marcados,  │  "Qual face da caixa esta câmera   │
│  numerados 1-4 na ordem de     │   enxerga de frente?"              │
│  clique                        │  (clique numa face para escolher) │
│                                │                                    │
│  Ponto 1 (superior-direito)    │                                    │
│  = [dropdown de vértice ▾]     │                                    │
│  Ponto 2 (superior-esquerdo)   │                                    │
│  = [dropdown de vértice ▾]     │                                    │
│  Ponto 3 (inferior-direito)    │                                    │
│  = [dropdown de vértice ▾]     │                                    │
│  Ponto 4 (inferior-esquerdo)   │                                    │
│  = [dropdown de vértice ▾]     │                                    │
│                                │                                    │
│  (mensagem de erro inline,     │                                    │
│   se houver, aparece aqui)     │                                    │
└───────────────────────────────┴───────────────────────────────────┘
        [Resetar orientação]  [Finalizar orientação]  [Voltar]
```

- A miniatura reaproveita o padrão já existente de `PerspectiveUi.load_image_on_ui_from_array` /
  `BorderUi.load_image_on_ui_from_array`: a mesma imagem do primeiro frame, redimensionada
  (`Image.thumbnail`), com os 4 pontos desenhados por cima (`ImageDraw` ou marcadores de `Canvas`, igual
  ao estilo de círculo azul (`fill="blue"`) já usado em `BorderUi.draw_lines`). Cada ponto ganha um rótulo
  numérico "1", "2", "3", "4" ao lado do marcador, na ordem em que foi clicado em `PerspectiveUi`
  (superior-direito, superior-esquerdo, inferior-direito, inferior-esquerdo — mesma ordem do
  `02-entrada-de-dados.md` item 4).
- Não é necessário reabrir o vídeo/clicar de novo — os 4 pontos já existem em
  `perspective_top_interface.frame_perspective_points` / `..._side_interface...`; a tela só precisa
  desenhar por cima, não capturar novos cliques na imagem.

### 2.2 O wireframe do cubo (Canvas)

Desenho via `tkinter.Canvas`, projeção isométrica simples (a mesma técnica usada em diagramas técnicos
2D de caixas 3D), sem biblioteca externa:

1. **Face frontal**: um quadrado sólido desenhado com `canvas.create_polygon` (ex.: cantos em
   `(100,150)`, `(220,150)`, `(220,270)`, `(100,270)`), tag `"face_front"`.
2. **Face de trás (deslocada)**: o mesmo quadrado, deslocado por um offset isométrico fixo, por exemplo
   `(+60,-60)` em cada canto — cantos em `(160,90)`, `(280,90)`, `(280,210)`, `(160,210)`, tag
   `"face_back"`. Este quadrado fica visualmente "atrás e acima" do frontal, dando a ilusão de
   profundidade.
3. **4 linhas de conexão** (`canvas.create_line`) ligando cada canto da face frontal ao canto
   correspondente da face de trás — essas 4 linhas, junto das arestas das duas faces, formam o wireframe
   completo das 12 arestas do cubo.
4. **6 polígonos clicáveis, um por face**, cada um com sua própria `tag` (`"face_top"`, `"face_bottom"`,
   `"face_left"`, `"face_right"`, `"face_front"`, `"face_back"`), desenhados como polígonos semi-
   transparentes (usar uma cor de preenchimento clara/neutra, ex. `stipple="gray25"` do Tkinter, para não
   esconder as linhas do wireframe) sobre a região correspondente:
   - `face_front` / `face_back`: os dois quadrados já descritos.
   - `face_top`: o paralelogramo formado pelos dois cantos superiores da face frontal + os dois cantos
     superiores da face de trás.
   - `face_bottom`: o paralelogramo equivalente na base.
   - `face_left`: o paralelogramo formado pelos dois cantos esquerdos de frente/trás.
   - `face_right`: o paralelogramo formado pelos dois cantos direitos de frente/trás.
5. **8 rótulos de vértice** (`canvas.create_text`, fonte pequena), um em cada canto do wireframe, com
   abreviação de 3 letras espelhando o enum `BoxVertex` do ARCHITECTURE.md (`TOP_FRONT_LEFT` →
   `"TFL"`, etc.): `TFL`, `TFR`, `TBL`, `TBR` (canto do topo: frente-esquerda, frente-direita, trás-
   esquerda, trás-direita) e `BFL`, `BFR`, `BBL`, `BBR` (mesma lógica na base). Um rótulo textual maior
   abaixo do desenho traduz a legenda: *"T = topo/B = base, F = frente/B = trás, L = esquerda/R =
   direita"*.
6. **Clique numa face**: `canvas.tag_bind("face_top", "<Button-1>", ...)` (um bind por tag/face) chama
   `self.select_face(BoxFace.TOP)`; a face escolhida recebe destaque visual (preenchimento sólido colorido
   em vez do `stipple` neutro, ex. azul), as demais voltam ao estado neutro.

### 2.3 Passo 1 — escolher a face vista pela câmera

Rótulo fixo acima do canvas: **"Qual face da caixa esta câmera enxerga de frente?"**

Nomes de face em português, mapeados 1:1 para `BoxFace`:

| Rótulo em português | `BoxFace` |
|---|---|
| Topo | `TOP` |
| Base | `BOTTOM` |
| Esquerda | `LEFT` |
| Direita | `RIGHT` |
| Frente | `FRONT` |
| Fundo | `BACK` |

Ao clicar numa face do wireframe, um `ttk.Label` abaixo do canvas confirma em texto a escolha: **"Face
selecionada: Topo"** (atualiza dinamicamente). Isso existe porque o wireframe sozinho, sendo uma
projeção 2D de um cubo, pode ser ambíguo para leitura rápida — o texto de confirmação remove a dúvida.

### 2.4 Passo 2 — associar cada um dos 4 pontos clicados a um vértice

Para cada um dos 4 pontos (na ordem fixa de clique), uma linha com rótulo + `ttk.Combobox`:

```
Ponto 1 (superior-direito) = [▾ selecione o vértice]
Ponto 2 (superior-esquerdo) = [▾ selecione o vértice]
Ponto 3 (inferior-direito) = [▾ selecione o vértice]
Ponto 4 (inferior-esquerdo) = [▾ selecione o vértice]
```

- **O combobox só lista os 4 vértices que pertencem à face escolhida no Passo 1** (filtro dinâmico —
  nunca lista os 8 vértices possíveis). Isso elimina por construção a maior classe de erro (associar um
  ponto a um vértice de outra face). Exemplo: se a face escolhida é `TOP`, os 4 vértices disponíveis nos
  4 comboboxes são `TFL`, `TFR`, `TBL`, `TBR` (traduzidos na exibição do combobox como texto completo,
  ex. `"Topo-Frente-Esquerda"`, não a sigla).
- **Os comboboxes ficam desabilitados até uma face ser escolhida** (Passo 1), com um rótulo cinza
  placeholder "Escolha a face primeiro" — evita preencher os pontos numa ordem que depois vira inválida.
- **Trocar de face depois de já ter escolhido vértices reseta as 4 seleções**, com aviso inline: *"Face
  alterada — selecione novamente os vértices dos 4 pontos."* (evita o estado inconsistente de "vértice
  escolhido pertence à face antiga").

### 2.5 Validação e mensagens de erro (exatas, em português)

Regras de validação, verificadas ao clicar em **"Finalizar orientação"**:

1. **Face não escolhida.**
   Erro: `"Selecione qual face da caixa esta câmera enxerga antes de continuar."`
2. **Algum dos 4 pontos sem vértice selecionado.**
   Erro: `"Selecione o vértice correspondente a todos os 4 pontos antes de finalizar."`
3. **Vértice repetido entre os 4 pontos** (dois pontos apontando para o mesmo vértice).
   Erro: `"Cada ponto precisa apontar para um vértice diferente."`
4. **Conjunto dos 4 vértices escolhidos não é exatamente o conjunto dos 4 vértices da face** — na
   prática esta regra já é garantida de graça pelo filtro do combobox (2.4), mas a validação final
   revalida mesmo assim (defesa em profundidade, e cobre qualquer futuro caminho de código que preencha
   os campos programaticamente, ex. ao carregar um perfil salvo com dados inconsistentes).
   Erro: `"Os 4 vértices selecionados não formam a face escolhida. Revise a seleção."`

Todas as mensagens aparecem como `ttk.Label` vermelho inline logo abaixo dos 4 comboboxes (não como
`messagebox` modal) — diferente do padrão de erro do hub (`messagebox.showerror`), porque aqui o erro é
de preenchimento de formulário em andamento, não uma ação disparada; um popup modal a cada tentativa de
ajuste seria mais fricção do que ajuda. `messagebox.showerror` continua reservado para erros de
transição de tela (ex. tentar abrir `OrientationUi` sem perspectiva configurada, seção 1.2).

Somente com as 4 regras satisfeitas o botão some o erro inline e a tela navega de volta ao hub
(`show_frame(self.main_frame)`), persistindo `face_viewed` e a lista ordenada `corner_vertices` (mesma
ordem de clique) equivalente ao `CameraOrientation` do `orientation.py`.

### 2.6 Botões — trio consistente com as telas existentes

Seguindo o padrão de `PerspectiveUi`/`BorderUi`:

- **"Resetar orientação"** — limpa a face escolhida (volta o wireframe ao estado neutro) e as 4 seleções
  de vértice (equivalente a `PerspectiveUi.reset_perspective`/`BorderUi.reset_border_config`).
- **"Finalizar orientação"** — roda as validações da seção 2.5; só navega de volta ao hub se todas
  passarem (equivalente a `PerspectiveUi.finish_perspective`/`BorderUi.finish_border_config`).
- **"Voltar"** — sai sem salvar. Diferente de `PerspectiveUi.finish_perspective_without_config` (que
  auto-preenche os 4 cantos da imagem inteira como *default* de "sem correção de perspectiva"), **não
  existe default sensato para orientação** — não há como inferir "qual face a câmera vê" automaticamente.
  Por isso "Voltar" aqui simplesmente descarta qualquer seleção parcial e retorna ao hub deixando a
  orientação daquela câmera como não configurada (`None`), e o hub passa a bloquear "Processar vídeo"
  nesse caso (ver 1.2), do mesmo jeito que já bloqueia hoje por perspectiva/borda ausente.

### 2.7 Reaproveitamento do magnifier (mira + zoom de 100×100px)

**Decisão: não reaproveitar o magnifier nesta tela.** O magnifier de `PerspectiveUi.on_motion` (recorte
de 100×100px com mira vermelha central, seguindo o cursor) existe para permitir clique **sub-pixel
preciso** sobre a imagem do vídeo — ali, um erro de poucos pixels na escolha do canto distorce a
homografia inteira. Em `OrientationUi`, a interação do usuário é inteiramente **discreta** (clicar uma
região de face num wireframe estilizado; escolher um item de uma lista de 4 opções em um combobox) — não
há coordenada de pixel sendo registrada, então não existe "precisão de clique" a ganhar. Reaproveitar o
magnifier aqui seria complexidade acidental sem benefício de usabilidade real; a miniatura com os 4 pontos
numerados (2.1) já é suficiente para o usuário relacionar visualmente "ponto 1 é aquele canto ali".

---

## 3. Consistência com padrões existentes

O que `OrientationUi` **mantém** dos padrões já estabelecidos por `PerspectiveUi`/`BorderUi`:

- Trio de botões resetar/finalizar/voltar, com os mesmos verbos ("Resetar", "Finalizar", "Voltar") só
  trocando o substantivo ("orientação" em vez de "perspectiva"/"borda"/nada).
- Widget de botão: `ttk.Button` (não `tk.Button`) — `OrientationUi` está mais próxima de `PerspectiveUi`/
  `BorderUi` (que já usam `ttk.Button` para o trio de ação) do que do hub (que usa `tk.Button` simples
  para navegação linear).
- Layout via `grid()` com `padx=10, pady=10`, mesma convenção de espaçamento visual das telas irmãs.
- Roteamento por `show_frame()` — nenhuma janela nova, nenhum `Toplevel`.
- Reaproveita a miniatura de frame de vídeo com marcadores desenhados por cima, no mesmo estilo visual de
  `BorderUi.draw_lines` (círculos azuis nos vértices).

Onde `OrientationUi` **diverge** deliberadamente (e por quê):

- O botão "Voltar" aqui tem semântica de "não fazer nada por padrão / descarta seleção parcial", herdando
  o espírito do "Voltar" de `PerspectiveUi` (que tem 3 botões, incluindo um "Voltar" com comportamento
  próprio de fallback) mais do que o de `BorderUi` (que só tem 2 botões — "Finalizar"/"Resetar" — sem
  "Voltar" explícito, porque o retângulo de borda sempre tem um estado válido por padrão, `[[50,50],
  [450,50], [50,450], [450,450]]`). A diferença é que o fallback de `PerspectiveUi` é "sem correção" (um
  default geometricamente válido), enquanto orientação não tem equivalente — por isso o "Voltar" de
  `OrientationUi` deixa o estado como "não configurado" em vez de aplicar um default arbitrário.

---

## 4. Paridade headless/CLI — schema de configuração

Por decisão do `ARCHITECTURE.md` ("GUI (Tkinter) continua existindo, ganha modo headless/CLI"), um
pesquisador rodando `animaltrack run --config pipeline.toml` em lote não pode clicar num wireframe — a
mesma informação de orientação precisa ser editável à mão em texto plano, usando os mesmos nomes de enum
que `BoxFace`/`BoxVertex`/`CameraRole` (`src/core/schema/orientation.py`) definem.

Proposta de seção em `pipeline.toml` (ou arquivo de config equivalente por perfil):

```toml
# Orientação de câmera/caixa — ver src/core/schema/orientation.py (BoxFace, BoxVertex, CameraRole)
#
# corner_vertices preserva a MESMA ordem de clique usada no PerspectiveUi / na etapa de perspectiva:
#   [superior-direito, superior-esquerdo, inferior-direito, inferior-esquerdo]
# Os 4 vértices listados devem ser exatamente os 4 vértices da face indicada em face_viewed —
# `animaltrack validate-config` recusa a configuração caso contrário (mesma regra de validação da
# tela OrientationUi, seção 2.5 do ux-design-detalhado.md).

[orientation.top_camera]
role             = "top"
face_viewed      = "top"
corner_vertices  = ["TOP_FRONT_RIGHT", "TOP_FRONT_LEFT", "TOP_BACK_RIGHT", "TOP_BACK_LEFT"]

[orientation.side_camera]
role             = "side"
face_viewed      = "front"
corner_vertices  = ["TOP_FRONT_RIGHT", "TOP_FRONT_LEFT", "BOTTOM_FRONT_RIGHT", "BOTTOM_FRONT_LEFT"]
```

Notas de design deste schema:

- Os valores são strings simples (`"top"`, `"front"`, `"TOP_FRONT_RIGHT"`) — legíveis e editáveis à mão
  por um pesquisador sem conhecimento de Python, sem precisar entender o `Enum` do Pydantic por trás.
  Os valores devem bater literalmente com `BoxFace`/`BoxVertex` (mesma grafia, mesmo case) para que o
  parsing do `pipeline.toml` construa o `BoxOrientationConfig` diretamente, sem tabela de tradução
  adicional entre TOML e schema.
- `corner_vertices` é uma lista ordenada (não um set/dict) exatamente porque a ordem carrega significado
  — precisa alinhar com a ordem de clique da perspectiva daquela câmera. Isso é comentado explicitamente
  no próprio TOML (comentário acima da seção) para reduzir o risco de quem edita à mão inverter a ordem
  sem perceber.
- **`animaltrack validate-config`** (já citado no `ARCHITECTURE.md` como comando CLI) deve rodar a mesma
  validação descrita na seção 2.5 deste documento (face escolhida existe, os 4 vértices batem com a face,
  sem vértice repetido, todos os 4 pontos presentes) **antes** de disparar o pipeline inteiro — dando o
  mesmo feedback de erro rápido que a GUI dá inline, só que via saída de terminal. Mensagens de erro no
  CLI devem usar o mesmo texto em português das mensagens da GUI (seção 2.5), para manter uma única fonte
  de verdade de linguagem entre os dois modos de entrada.

---

## 5. O que manter inalterado (não mexer nesta rearquitetura)

Lista explícita de decisões de UX que devem ser preservadas como estão, para não reabrir debates de
interface não relacionados à mudança de arquitetura (princípio do `ARCHITECTURE.md`: *"Telas antigas
mantidas visualmente próximas da referência durante a transição"*):

| Decisão a manter | Onde vive hoje | Por quê manter |
|---|---|---|
| Combobox de perfil com sentinela `"Novo perfil de analise"` sempre no topo da lista | `MainConfigurationInterface.new_analises_profile` / `config_combobox` | Comportamento já compreendido pelos pesquisadores atuais; trocar o texto/posição do sentinela não tem relação com a rearquitetura de camadas |
| Ordem fixa de clique dos 4 pontos de perspectiva (superior-direito, superior-esquerdo, inferior-direito, inferior-esquerdo) | `PerspectiveUi` / `02-entrada-de-dados.md` item 4 | É a convenção que `corner_vertices` do `orientation.py` explicitamente referencia ("mesma ordem de clique do PerspectiveUi") — mudar a ordem quebraria a suposição documentada no próprio ARCHITECTURE.md |
| Interação de arraste por vértice do `BorderUi` (retângulo axis-aligned com 4 cantos arrastáveis, onde arrastar um canto move-o em x e y e reposiciona as duas arestas adjacentes para o retângulo continuar alinhado aos eixos) | `BorderUi.move_line`/`start_move`/`stop_move` | Já funcional e não tem nenhuma relação com orientação/schema — é puramente sobre a região de borda/vidro |
| Hub único com botões lineares, sem abas/menu lateral | `MainConfigurationInterface` | Rearquitetura é de camadas de processamento, não de navegação; introduzir um novo paradigma de navegação é decisão de UX independente, fora de escopo aqui |
| Magnifier com mira (zoom 100×100 seguindo cursor) nas telas que exigem clique de precisão | `PerspectiveUi.on_motion` | Continua sendo a ferramenta certa para clique de homografia; não deve ser removido nem generalizado para telas que não precisam dele (ver 2.7) |
| Textos/rótulos em português já existentes ("Configurar bordas", "Salvar configurações", "Processar video (Módulos Basicos)", etc.) | Todas as telas atuais | Só adicionar rótulos novos no mesmo tom/idioma; não é objetivo desta fase retrabalhar copy já existente |
| Fluxo de "reprocessar sem refazer etapas anteriores" (exibir gráfico/exportar PDF sem reprocessar vídeo) | `MainConfigurationInterface.process_output_data`/`process_pdf` | Citado explicitamente em `02-entrada-de-dados.md` como comportamento intencional para acelerar teste de novos MMs |

---

## 6. Risco de acessibilidade/usabilidade em aberto — preview de processamento sem bloquear a GUI

**O problema hoje:** o modo debug de `backgroundRemoveModule.py` (branch `if debug_mode`) usa
`cv2.imshow(...)` para três janelas nativas do OpenCV (`_dif_frame`, `_diff`, `_frame`) e
`cv2.waitKey(0)` **bloqueante** — navegação frame a frame por tecla (`n` avança, `ESC` sai do modo debug).
Isso é incompatível com a arquitetura-alvo de Fase 3/4: pipeline em streaming (`Iterator[FramePair]`), GUI
não bloqueante com lifecycle de tela normalizado (`after()` para marshalling de volta à main thread do
Tk, conforme a correção de thread-safety prevista na Fase 4). Uma janela `cv2.imshow` com `waitKey(0)`
trava a thread onde roda — se rodar na mesma thread do pipeline (que hoje já roda em thread de background
separada da UI, `run_background_tasks`), trava aquele processamento até o usuário apertar uma tecla; se
alguém tentar chamar isso a partir da main thread do Tk por engano, trava a UI inteira.

**Pergunta em aberto para quem implementar as telas da Fase 4** (não resolvida por este documento,
propositalmente — é uma decisão de trade-off entre esforço de implementação e fidelidade de preview):

- **Opção 1 — painel de preview embutido na própria janela Tk.** Reaproveitar o padrão que
  `RecordWebcamVideoUI.show_recoding_video`/`get_image_from_frame_queue` já usa: uma `Queue` alimentada
  pelo estágio de Detect/Rectify a cada frame processado, consumida por um `ttk.Label` de imagem dentro da
  própria tela de processamento, com botões não bloqueantes "Próximo frame" / "Continuar automaticamente"
  em vez de `waitKey`. Vantagem: preview ao vivo, mesma UX unificada da GUI. Custo: precisa desenhar uma
  tela nova de "processamento com preview" e um contrato de streaming de frames de debug saindo do
  pipeline até a UI.
- **Opção 2 — exportar frames de debug para pasta temporária, sem preview ao vivo na v1.** O estágio de
  Detect grava as imagens de diff/contorno relevantes (ex. 1 a cada N frames, ou só os frames onde a
  detecção falhou) em `workspace/.../debug/`, e a GUI só oferece um botão "Abrir pasta de debug" que chama
  o explorador de arquivos do SO. Vantagem: zero código de streaming de preview, zero risco de travar
  qualquer thread. Custo: não é "ao vivo" — só útil para inspeção pós-hoc.

Recomendação implícita (não normativa): a Opção 2 é o caminho mínimo viável compatível com a Fase 4 tal
como escopada (sem introduzir um novo tipo de tela de streaming); a Opção 1 é o alvo desejável de médio
prazo, quando/se o `ArrayBackend`/streaming de Detect (Fase 3) já estiver estável o suficiente para expor
um segundo consumidor (debug) do mesmo stream de frames sem custo extra de I/O relevante.
