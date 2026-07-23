# 02 — Entrada de Dados

## 1. Ambiente controlado (pré-condição física)
- **Caixa** retangular transparente (vidro ou acrílico) que confina o inseto; tamanho livre, desde que o inseto possa voar e pousar.
- **Fundo branco** e sem distorções que gerem sombra (laterais opacas brancas, plano branco ou tecido).
- **Iluminação** uniforme, idealmente sem gradientes; gradientes são tolerados pelo algoritmo de extração de fundo, mas a luz **não pode variar durante o experimento**.
- **Duas câmeras** a 90° entre si, em lados adjacentes — idealmente uma no **topo** e uma na **lateral**.
  - Devem ser acionadas simultaneamente por meio externo.
  - Devem gravar no **mesmo FPS** (obrigatório).
  - Resolução pode variar entre elas; quanto maior, melhor a precisão.
  - Enquadramento ideal captura as bordas da caixa.

## 2. Entradas do sistema
- **Vídeo do topo** (`.mp4`) — define largura (x) e profundidade (z).
- **Vídeo da lateral** (`.mp4`) — define altura (y).
- **Dimensões da caixa** em centímetros: largura, profundidade e altura.
- **Pontos de perspectiva** (4 por vídeo), definidos visualmente pelo usuário.

Os vídeos **não são copiados nem duplicados**; o sistema guarda apenas o caminho e só interage com o arquivo durante o processamento.

## 3. Fluxo de entrada na interface (Tkinter)
1. **Selecionar perfil** — ao abrir, o perfil "Novo perfil de análise" vem selecionado. É possível trocar de perfil ou analisar sem salvar.
2. **"Selecione o local do arquivo de vídeo topo"** e **"…vídeo lado"** — abrem o seletor de arquivos do SO.
3. **Preencher medidas da caixa** (cm).
4. **"Configurar bordas"** (topo e lado) — abre uma tela com o **primeiro frame** do vídeo:
   - O usuário clica 4 pontos, **nesta ordem**: superior direito, superior esquerdo, inferior direito, inferior esquerdo.
   - Ao mover o cursor, um recorte de 50 px com uma cruz central é exibido no canto, para clique preciso.
   - Botões: **"resetar perspectiva"** (zera os pontos), **"finalizar perspectiva"** (salva e sai), **"voltar"** (sai sem alterar → os pontos assumem os extremos da imagem, ou seja, nenhuma correção).
   - Isso define o **ROI**, reduzindo o custo computacional do processamento.
5. **"Salvar Configurações"** — cria/atualiza o perfil de análise.

A interface também permite **reprocessar** os dados, **exibir o gráfico de rota** e **exportar o PDF** sem refazer as etapas anteriores — isso é intencional, para acelerar o desenvolvimento e teste de novos MMs sem reexecutar os BMs.

## 4. Persistência do perfil de análise
Arquivo: `./cache/configs.json` — um objeto por perfil, contendo:

| Campo | Significado |
|---|---|
| `top_video_path` | caminho do vídeo do topo |
| `side_video_path` | caminho do vídeo lateral |
| `frame_perspective_points_top` | 4 pontos 2D de correção de perspectiva (topo) |
| `frame_perspective_points_side` | 4 pontos 2D de correção de perspectiva (lateral) |
| `width_box_cm` | largura da caixa em cm |
| `depth_box_cm` | profundidade da caixa em cm |
| `height_box_cm` | altura da caixa em cm |

Esses dados são carregados na abertura do sistema e na troca de perfil, e são repassados aos BMs e MMs no início do processamento. Os perfis são reutilizáveis e compartilháveis entre pesquisadores.

## 5. Parâmetros de módulo
- **Threshold de borda** (`BorderModule`): distância em pixels da borda para o centro que separa "pousado" de "voando". **Padrão: 100 px**, configurável pelo pesquisador.

## 6. Sem proteção de dados (decisão de projeto)
Não há senha, criptografia ou ofuscamento. Todos os dados ficam em JSON legível em pastas de cache, para facilitar inspeção, exportação e criação de novos módulos.
