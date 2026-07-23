# 03 — Processamento

Pipeline geral: **BM (vídeo → posição por frame) → Rota 3D → MM (metadados) → EM (exportação)**.

## 1. Módulos Básicos (BM)
Construídos sobre `opencv-python` (CPU) e `NumPy`. Não são de acesso público; não se espera que o pesquisador os manipule no estágio atual.

Executam, por vídeo, frame a frame:

### 1.1 Correção de perspectiva + ROI
Usa `cv2.getPerspectiveTransform` e `cv2.warpPerspective` com os 4 pontos do perfil. Gera a matriz de correção e, como subproduto, **descarta tudo fora dos pontos**, produzindo o ROI a ser analisado.

### 1.2 Remoção de fundo (background)
Abordagem baseada em Chen, Chiang e Tsai (2021), recalibrada dinamicamente:
1. Converte todos os frames para **escala de cinza** (0–255).
2. Divide o vídeo em blocos de **500 frames** e pega o primeiro frame de cada bloco → lista de frames pseudo-aleatórios.
3. Para cada posição de pixel, escolhe o **maior valor** (pixel mais claro) entre esses frames → **máscara de fundo**.
4. Subtrai a máscara de cada frame do vídeo (operação matricial). Onde o fundo coincide, o resultado fica próximo de 0 (escuro); onde o inseto está, próximo do branco.
5. **Remoção de ruído:** zera todos os pixels com valor **menor que 80** (limiar definido empiricamente).

> Motivo da abordagem: insetos comuns (abelhas, moscas, baratas) ficam escuros em grayscale, mas simplesmente pegar "o pixel mais escuro do ROI" gera falsos positivos com bordas, reflexos e a sombra do próprio inseto.

### 1.3 Detecção do inseto
Aplica o algoritmo de contornos do OpenCV sobre a imagem limpa, seleciona o contorno de **maior área** e toma seu **centro** como a posição do inseto naquele frame.

### 1.4 Saída do BM
Extrai também **FPS** e **quantidade de frames**. Grava JSON em `./cache/output/<nome_do_perfil>.json`.

**Detalhe importante de formato:** os pontos **não** são um array — cada ponto fica em um objeto cuja **chave é o número do frame**, porque não é possível garantir a ordem de elementos de array na (des)serialização JSON.

## 2. Rota 3D
Fusão das duas câmeras:
- **Câmera do topo** → `x` (largura) e `z` (profundidade)
- **Câmera lateral** → `y` (altura)

Resultado: chave `"Rota"` no objeto de saída, contendo uma lista de objetos indexados pelo número do frame, cada um com um sub-objeto `{x, y, z}`.

A rota é a **base de todos os MMs seguintes** (velocidade, preferência de local, tempo de voo) e alimenta o módulo de exibição, que reproduz a trajetória frame a frame.

## 3. Módulos de Metadados (MM) — ponto de extensão
Duas estruturas: o **invocador** e os **submódulos invocados**.

### 3.1 Contrato de módulo
- Colocar o script Python na pasta **`./src/MetadataModule`**.
- O arquivo deve expor uma função **`module_call(obj)`** que recebe um objeto genérico com os dados já calculados (BM + MMs anteriores) e **retorna o mesmo objeto**, alterando os valores via ponteiro.
- O invocador descobre e executa arquivos com nomes desconhecidos, encadeando os módulos como uma esteira de processamento — um MM pode depender do resultado de outro.
- **Não há nenhuma proteção**: um módulo pode sobrescrever ou apagar dados de módulos anteriores. Isso é intencional, para não impor travas ao pesquisador.

### 3.2 MMs implementados
- **`BorderModule`** — tempo em voo e tempo em pouso. Um *threshold* em pixels (padrão 100, medido da borda para o centro) cria linhas virtuais: ponto fora do threshold = **voando**; dentro = **pousado** em uma borda. Contabiliza o tempo em cada borda.
- **`SpeedModule`** — calcula a distância entre dois pontos consecutivos e o tempo correspondente a partir do FPS, derivando velocidade média (e permitindo aceleração ao longo do tempo).

## 4. Módulos de Exportação (EM)
- **Persistência:** interface com o disco; carrega e salva JSON nas pastas de cache. Sem criptografia.
- **Gráfico 3D:** Matplotlib renderiza a rota em gráfico tridimensional **interativo**, frame a frame, com rotação do ângulo de visão pelo mouse.
- **Relatório PDF:** submódulo injeta os metadados em um **template HTML** e converte para PDF via biblioteca **Pisa**.

## 5. Limitações conhecidas (observadas nos testes)
- **Perda de detecção** quando o inseto passa por reflexos de luz no vidro, entra em sombras ou fica de costas com as asas refletindo luz (chegou a 13 frames consecutivos sem detecção). Isso gera **quebras de linha** no gráfico de rota.
- **Falso positivo momentâneo:** batidas de asa somadas a ruído de fundo intenso podem fazer o sistema confundir fundo com inseto por 1 frame — sem quebra de linha, interpretado como movimento rápido.
- **Objeto imóvel não é detectado:** a remoção de fundo depende de movimento; se o inseto não se move em um dos eixos, aquele eixo não gera pontos e, como a rota 3D fica incompleta, o gráfico sai vazio.
- **Contagem de frames** para no fim do vídeo mais curto entre os dois.
- **Distorção visual** no gráfico 3D quando há variação de altura — é limitação de renderização do EM, não erro do algoritmo de CV.
