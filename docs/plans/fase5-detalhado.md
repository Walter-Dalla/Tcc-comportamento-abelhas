# Fase 5 — Backends GPU (plugins puros, sem mudar esqueleto)

> Plano de execução granular para a Fase 5 descrita em `ARCHITECTURE.md` ("Estratégia GPU" e tabela de
> Fases). Pré-requisito: Fases 0–4 mergeadas — em particular os protocolos `Rectifier`/`Detector` de
> `src/core/stages.py` (ou onde a Fase 3 os fixar) precisam existir e estar estáveis antes de qualquer
> tarefa de código abaixo começar. **Se esse plano for retomado e Fases 0–4 ainda não existirem no repo,
> pare e não escreva código de Fase 5** — o esqueleto que ele estende ainda não existe.

## Decisão de produto já fechada (confirmada pelo dono do projeto)

**O requisito de GPU escopa apenas `Pipeline.run` (execução real de processamento), não o boot da GUI nem
as telas de configuração.** Um pesquisador precisa conseguir abrir a GUI e configurar um perfil
(perspectiva, orientação, pontos de borda) em uma máquina sem GPU — o probe de CUDA só falha alto quando um
run de fato é disparado. Consequências concretas em código:

- `require_cuda()` (seção 1.2) é chamado **dentro de `Pipeline.run()`** (ou no início do comando `run` da
  CLI), nunca no boot do processo Tk/`MainInterface`, nunca na abertura de `PerspectiveUi`/`BorderUi`/
  `OrientationUi`.
- A GUI abre e todas as telas de configuração funcionam normalmente sem GPU. O erro (`GpuNotAvailableError`)
  só aparece no momento em que o usuário aciona "Processar vídeo" (ou equivalente CLI), e é apresentado ali
  (messagebox na GUI / mensagem + `sys.exit(1)` na CLI) — não no startup do app.
- Isso já estava assumido como a opção mais provável neste plano antes da confirmação; o texto abaixo foi
  ajustado para tratar isso como **decidido**, não mais como pendência em aberto.

## 0. Status confirmado no momento em que este plano foi escrito

- Repo 100% legado (`src/Modules/...`), zero código de rearquitetura.
- `requirements.txt` lista `opencv-python==4.9.0.80` — build sem CUDA, sem `opencv_contrib`. Confirmado por
  inspeção direta do arquivo (hoje texto ASCII/UTF-8 puro — a nota do `CLAUDE.md` sobre UTF-16 está
  desatualizada, conforme a auditoria da Fase 0; a versão pinada segue sendo `opencv-python==4.9.0.80`).
- Não existia `docs/`, `pyproject.toml`, `.github/workflows/` no momento em que este plano foi escrito —
  tudo isso é entregável de fases anteriores (0 principalmente), pré-requisito de fato para este plano
  rodar, não só "seria bom que existisse".
- **Ação obrigatória ao retomar este plano para execução real**: antes da Tarefa 1, ler o `Rectifier`/
  `Detector` de fato commitados pela Fase 3 (`src/core/stages.py` e `src/stages/rectify/base.py` ou
  equivalente) e confirmar assinatura exata de métodos. Este documento assume, por inferência do estilo já
  fixado para `Detector`/`Tracker` em `ARCHITECTURE.md`, uma forma provável (seção 1.2) — **mas essa forma
  não está gravada em pedra até a leitura do código real da Fase 3 acontecer**. Se divergir, ajustar as
  assinaturas de `CudaPerspectiveRectifier`/`CudaMOG2Detector` para bater com o que a Fase 3 realmente
  fixou, sem reabrir o contrato.

---

## 1. Lista de tarefas ordenada e concreta

### 1.1 Tarefa 0 (gate, não paralelizável) — confirmar pré-requisitos
- Confirmar que Fases 0–4 estão mergeadas em `main`.
- Ler `src/core/stages.py` (protocolos `Detector`/`Tracker`, e o que a Fase 3 tiver fixado para
  `Rectifier`) e `src/stages/rectify/`, `src/stages/detect/` (implementações CPU já existentes:
  `CpuPerspectiveRectifier`, `BackgroundSubtractionDetector`) para copiar a assinatura exata.
- Ler `src/core/plugin.py`/`plugin_registry.py` para o formato de `PluginManifest`/`plugin.toml` real.
- Confirmar onde `Pipeline.run()` fica de fato (ou o equivalente na CLI) — é ali, e só ali, que
  `require_cuda()` será chamado (ver decisão de produto acima).
- Saída: nenhum arquivo novo — só uma confirmação (ou uma nota curta em
  `docs/handoffs/fase5-prereq-check.md` se algo divergir do assumido aqui, para não perder o raciocínio).

### 1.2 Tarefa 1 (sequencial, bloqueia 1.3 e 1.4) — plumbing central compartilhado
Um único agente/sessão, sem paralelizar — os dois plugins CUDA da tarefa seguinte dependem deste código.

**`src/core/array_backend.py`** — protocolo `ArrayBackend` que abstrai `numpy.ndarray` (CPU) vs
`cv2.cuda_GpuMat` (GPU). Escopo mínimo necessário para Rectify (warp + grayscale) e para o
upload/download em volta do MOG2 (a extração de contorno/centroide continua em CPU — ver nota abaixo):

```python
# src/core/array_backend.py
from typing import Any, ClassVar, Protocol, runtime_checkable
import numpy as np

@runtime_checkable
class ArrayBackend(Protocol):
    name: ClassVar[str]  # "cpu" | "cuda" — usado em logs/manifests, não em lógica de branch

    def upload(self, frame: np.ndarray) -> Any:
        """CPU: retorna o próprio ndarray (ou cópia defensiva). CUDA: cv2.cuda_GpuMat().upload(frame)."""

    def download(self, handle: Any) -> np.ndarray:
        """Inverso de upload — sempre retorna ndarray em RAM (fronteira de saída do estágio)."""

    def warp_perspective(self, handle: Any, matrix: np.ndarray, dsize: tuple[int, int]) -> Any:
        """CPU: cv2.warpPerspective. CUDA: cv2.cuda.warpPerspective. Mesma assinatura, tipo de handle
        interno diferente."""

    def cvt_color_gray(self, handle: Any) -> Any:
        """CPU: cv2.cvtColor(..., COLOR_BGR2GRAY). CUDA: cv2.cuda.cvtColor."""

    def release(self, handle: Any) -> None:
        """No-op em CPU. Em CUDA, ponto de extensão futuro pra reciclar GpuMat de um pool em vez de
        alocar/desalocar por frame (otimização, não obrigatória na primeira versão)."""
```

- `CpuArrayBackend`: `upload`/`download` são identidade (ou `.copy()` se quisermos isolar side-effects);
  `warp_perspective`/`cvt_color_gray` chamam `cv2.warpPerspective`/`cv2.cvtColor` direto no ndarray. Existe
  principalmente para (a) os testes de paridade terem os dois lados do mesmo protocolo, e (b)
  `CpuPerspectiveRectifier` da Fase 3 poder ser migrado pra usar `ArrayBackend` também, se fizer sentido —
  **decisão explícita**: não é obrigatório reescrever o `CpuPerspectiveRectifier` já existente para usar
  `ArrayBackend` nesta fase (evita mexer em código já validado pelo golden-file test da Fase 3); o backend
  CPU existe para teste/paridade, o rectifier CPU de produção pode continuar como está.
- `CudaArrayBackend`: import de `cv2.cuda` guardado (`try/except AttributeError` — em uma build sem CUDA
  o atributo `cv2.cuda` nem existe), mensagem de erro clara na construção se o módulo não estiver
  disponível (não silenciosamente virar no-op).
- **Nota de escopo importante, documentar explicitamente no docstring do módulo**: `cv2.cuda` não expõe
  `findContours`/`moments` equivalentes utilizáveis diretamente em Python de forma prática — a extração do
  centroide do maior contorno (o que hoje `remove_background`/`BackgroundSubtractionDetector` fazem)
  **continua rodando em CPU** mesmo no caminho GPU: só o warp de perspectiva e a subtração de fundo (MOG2)
  rodam de fato na GPU; a máscara de foreground (pequena, já binarizada) é baixada pra CPU e o resto do
  pipeline de contorno é idêntico ao caminho CPU. Isso é uma limitação real do módulo `cv2.cuda`, não uma
  escolha de design evitável sem sair do OpenCV — deixar isso explícito evita a expectativa de "tudo roda
  na GPU".

**`src/core/gpu.py`** — probe obrigatório, chamado só no início de um `Pipeline.run()`/comando `run` (não no
boot da GUI — ver decisão de produto):

```python
# src/core/gpu.py
class GpuNotAvailableError(RuntimeError):
    """GPU é requisito (ARCHITECTURE.md - Estratégia GPU) para RODAR o pipeline; levantado quando nenhum
    dispositivo CUDA utilizável é encontrado no momento de um Pipeline.run()."""

def cuda_device_count() -> int:
    """Wrapper fino e não-lançante sobre cv2.cuda.getCudaEnabledDeviceCount(). Retorna 0 em qualquer
    cenário de indisponibilidade: sem GPU física, driver ausente, OU build do OpenCV sem módulo cuda
    (nesse caso cv2.cuda nem existe como atributo — AttributeError, capturado)."""
    try:
        import cv2
        return cv2.cuda.getCudaEnabledDeviceCount()
    except AttributeError:
        return 0
    except cv2.error:
        return 0

def require_cuda(min_devices: int = 1) -> int:
    """Probe obrigatório. Levanta GpuNotAvailableError (não faz sys.exit, não faz log-and-continue) se
    cuda_device_count() < min_devices. Retorna a contagem em caso de sucesso (útil pra log).

    Ponto de chamada — DECIDIDO: uma vez, no início de Pipeline.run() (ou do comando `animaltrack run` da
    CLI) — ANTES de instanciar qualquer plugin GPU. NUNCA no boot do processo (GUI ou CLI), nunca na
    abertura de PerspectiveUi/BorderUi/OrientationUi/MainConfigurationInterface. Configurar um perfil
    (perspectiva, orientação, borda) deve funcionar em qualquer máquina, com ou sem GPU; só o disparo real
    de processamento exige CUDA."""
    n = cuda_device_count()
    if n < min_devices:
        raise GpuNotAvailableError(
            f"GPU CUDA obrigatória para processar: {n} dispositivo(s) encontrado(s), esperado >= "
            f"{min_devices}. Ver docs/plans/fase5-detalhado.md, seção 2, para como obter um OpenCV com "
            "suporte CUDA."
        )
    return n
```

- `src/app/cli.py` (Fase 4) captura `GpuNotAvailableError` no comando `run` → imprime mensagem amigável →
  `sys.exit(1)`. `sys.exit`/apresentação ao usuário fica na camada de app, **nunca** dentro de
  `src/core/gpu.py` (mantém `core/` testável sem side-effect de processo). Comandos que não processam
  (`list-plugins`, `validate-config`) não chamam `require_cuda()` — não precisam de GPU.
- GUI: captura no handler do botão "Processar vídeo" (ou equivalente pós-Fase-4), mostra
  `messagebox.showerror` com a mesma mensagem — **não** no `__init__` de `MainInterface`/boot do Tk. Todas
  as outras telas (`PerspectiveUi`, `BorderUi`, `OrientationUi`, tela de configuração de perfil) continuam
  abrindo e funcionando normalmente sem GPU nenhuma, incluindo em máquina sem CUDA e sem driver NVIDIA.
- Testes desta tarefa (sem marcador `gpu`, rodam sempre): mock de `cv2.cuda.getCudaEnabledDeviceCount`
  retornando 0/1/2; mock simulando `AttributeError` (build sem cuda); `require_cuda()` levanta
  `GpuNotAvailableError` com mensagem contendo a contagem encontrada; teste explícito confirmando que abrir
  `PerspectiveUi`/`BorderUi`/tela de configuração **não** chama `require_cuda()` em nenhum momento (grep de
  chamada, ou teste de integração leve que abre as telas com `cuda_device_count` mockado pra 0 e confirma
  que nenhuma exceção é levantada).

### 1.3 / 1.4 Tarefas paralelas (worktrees separados) — após 1.2 mergeado

**`CudaPerspectiveRectifier`** (`src/stages/rectify/cuda/plugin.py` + `plugin.toml`):

```python
class CudaPerspectiveRectifier(Rectifier):   # mesma interface que CpuPerspectiveRectifier implementa
    manifest = PluginManifest(name="cuda-perspective-rectifier", kind="rectify", ...)

    def __init__(self, backend: ArrayBackend | None = None):
        self._backend = backend or CudaArrayBackend()

    def setup(self, ctx: PipelineContext) -> None:
        require_cuda()  # checagem defensiva de novo; barata, o Pipeline já deve ter chamado antes

    def rectify(self, frame: RawFrame, matrix: np.ndarray, size: tuple[int, int]) -> RectifiedFrame:
        h = self._backend.upload(frame.image)
        h = self._backend.warp_perspective(h, matrix, size)
        h = self._backend.cvt_color_gray(h)
        image = self._backend.download(h)
        return RectifiedFrame(image=image, frame_index=frame.frame_index, view=frame.view)
```
(assinatura de `rectify`/`RawFrame`/`RectifiedFrame` a confirmar contra o real da Fase 3 — Tarefa 0.)

**`CudaMOG2Detector`** (`src/stages/detect/cuda/plugin.py` + `plugin.toml`):

```python
class CudaMOG2Detector(Detector):
    def __init__(self, backend=None, history=500, var_threshold=16, detect_shadows=False):
        self._backend = backend or CudaArrayBackend()
        self._subtractor = cv2.cuda.createBackgroundSubtractorMOG2(history, var_threshold, detect_shadows)

    def detect(self, frame: RectifiedFrame) -> FrameDetections:
        h = self._backend.upload(frame.image)
        fg_gpu = self._subtractor.apply(h, -1, cv2.cuda.Stream_Null())
        fg_mask = self._backend.download(fg_gpu)         # sai da GPU aqui — ver nota de escopo em 1.2
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # maior contorno por área, centroide via cv2.moments — SÓ o passo de contorno/centroide é igual ao
        # de backgroundRemoveModule.py / BackgroundSubtractionDetector da Fase 3; a subtração de fundo em si
        # (MOG2 aqui) é um algoritmo DIFERENTE do máximo-estático+absdiff da CPU — ver nota abaixo e seção 3
        ...
        return FrameDetections(frame_index=frame.frame_index, view=frame.view, detections=[...])
```

> **Nota de algoritmo (ver seção 3)**: o detector CPU da Fase 3 (`BackgroundSubtractionDetector`) faz
> subtração de fundo por *máximo estático + `cv2.absdiff` + threshold fixo*, **não** MOG2. Este detector GPU
> usa MOG2 por decisão de `ARCHITECTURE.md` ("Estratégia GPU"), logo é um detector *diferente*, não uma
> versão GPU do CPU — só a extração de contorno/centroide coincide. Isso é intencional, mas molda como a
> "paridade" é definida e testada (equivalência comportamental na fixture, não paridade de máscara): quem
> implementar este plugin e o teste de paridade deve ler a assimetria descrita na seção 3 antes de assumir
> "mesmo algoritmo dos dois lados".

- Ambas as tarefas: `plugin.toml` com `kind` correto, `requires.packages` listando o requisito de OpenCV, e
  — como o manifest atual (Fase 2) não tem como expressar "precisa de build com CUDA", registrar essa
  limitação: adicionar campo opcional `requires.capabilities = ["cuda"]` ao schema de manifest (pequeno
  ajuste retroativo em `plugin_registry.py`, avaliar se cabe nesta fase ou vira débito documentado) checado
  via `gpu.cuda_device_count() > 0` no `discover()`/`instantiate()` — plugin que requer `cuda` e não há GPU
  é pulado com log (mesma política de "plugin quebrado não derruba o run" já adotada na Fase 2), não
  crasha a descoberta inteira. **Importante**: essa checagem acontece só no discovery de plugins pra um run
  de fato (mesmo ponto de `Pipeline.run()`), não impede a GUI de listar/abrir telas de configuração.
- Testes unitários de cada um ficam sob `@pytest.mark.gpu` (seção 5) — não rodam sem GPU real.

### 1.5 Tarefa de integração (sequencial, após 1.3+1.4 mergeados e após o milestone de empacotamento da
seção 2 estar pronto o suficiente pra rodar localmente)
- Smoke test de discovery: os dois `plugin.toml` novos aparecem em `PluginRegistry.for_kind(...)`.
- Testes de paridade (seção 3) escritos e rodados manualmente na máquina com GPU real do dev (não em CI).
- Ponto de chamada de `require_cuda()` fixado dentro de `Pipeline.run()`/CLI (decisão de produto já
  confirmada — ver topo do documento), e teste de regressão confirmando que a GUI/telas de configuração
  seguem funcionando sem GPU (mockando `cuda_device_count()` pra 0 no processo inteiro da GUI e navegando
  pelas telas de perspectiva/borda/orientação sem erro).
- Atualizar `.github/workflows/ci.yml` (herdado da Fase 0) pra rodar `pytest -m "not gpu"` explicitamente.

### 1.6 Handoffs
`docs/handoffs/fase5-array-backend-handoff.md`, `fase5-cuda-rectifier-handoff.md`,
`fase5-cuda-detector-handoff.md`, `fase5-packaging-handoff.md` — ver seção 6.

---

## 2. O problema de empacotamento do OpenCV com CUDA (a parte não-trivial de verdade)

**Confirmado neste repo**: `requirements.txt` fixa `opencv-python==4.9.0.80`. As wheels oficiais de
`opencv-python`/`opencv-contrib-python` no PyPI são compiladas **sem** o módulo `cuda` — é política
deliberada do mantenedor do pacote (portabilidade/tamanho/manylinux), não uma omissão acidental. Além
disso, `cudawarping` (onde vive `cv2.cuda.warpPerspective`), `cudaimgproc` (onde vive `cv2.cuda.cvtColor`,
usado por `ArrayBackend.cvt_color_gray`) e `cudabgsegm` (onde vive
`cv2.cuda.createBackgroundSubtractorMOG2`) são módulos de **`opencv_contrib`**, então nem
`opencv-contrib-python` do PyPI resolve — contrib no PyPI também é compilado sem CUDA. Ou seja: **não
existe hoje um `pip install` que entregue isso** — é preciso obter (construir ou baixar) um build
diferente do runtime Python padrão.

### Opções

**A — Build a partir do código-fonte no Windows (`-DWITH_CUDA=ON`, MSVC + CMake)**
- Requer: Visual Studio Build Tools (versão compatível com a versão do CUDA Toolkit escolhida), CUDA
  Toolkit, clonar `opencv` **e** `opencv_contrib` na mesma tag, `cmake` com
  `-DWITH_CUDA=ON -DOPENCV_EXTRA_MODULES_PATH=<path>/opencv_contrib/modules -DBUILD_opencv_python3=ON
  -DCUDA_ARCH_BIN=<compute capability da GPU do dev>` (restringir a arquitetura reduz tempo de build e
  tamanho do binário — evitar `ALL` archs).
- **Risco a marcar explicitamente, não maquiar**: builds de OpenCV+CUDA no Windows são um problema
  conhecido e mal documentado — combinação exata de versão do MSVC / CUDA Toolkit / CMake / OpenCV que
  compila com sucesso muda a cada poucos meses, builds levam 1–3h, falhas de linkagem/versão são comuns e
  pouco googláveis, e não há wheel oficial pra comparar contra. Este é o caminho de **maior esforço e
  maior fragilidade** apesar de parecer o mais "correto"/oficial.

**B — Wheel pré-compilada de terceiros**
- Existem builds de terceiros na comunidade (ex.: releases no GitHub de mantenedores independentes que
  publicam `opencv-python`-style wheels com CUDA para Windows). Risco: proveniência/confiança (rodar
  binário compilado por terceiro com acesso a GPU/driver), desatualização em relação à versão de OpenCV
  usada no resto do projeto, e a wheel é compilada para uma combinação específica de CUDA Toolkit/driver/
  compute capability que precisa bater com a máquina do dev — sem garantia de manutenção contínua pelo
  autor terceiro.
- Se usada, documentar de forma explícita e rastreável: URL exata da release, hash SHA256 verificado antes
  de instalar, versão exata pinada (não "latest"), e nota de que é uma conveniência de desenvolvimento, não
  o caminho suportado oficialmente do projeto.

**C — Docker com imagem base CUDA**
- Ex.: `FROM nvidia/cuda:12.x-devel-ubuntu22.04`, clonar `opencv`+`opencv_contrib`, buildar dentro do
  container (mesma complexidade de CMake da opção A, mas em Linux — ecossistema de build Linux+CUDA é
  muito mais maduro/documentado que o Windows equivalente: mais exemplos de Dockerfile funcionando,
  matriz de compatibilidade CUDA/GCC bem mais estável).
- Exige, no host Windows: Docker Desktop com backend WSL2 + NVIDIA Container Toolkit (ou suporte nativo de
  GPU do Docker Desktop via WSL2) — **Windows 11 (ambiente confirmado deste projeto) suporta passthrough
  de GPU pra WSL2 nativamente com driver NVIDIA atualizado no host**, sem precisar de driver duplicado
  dentro do WSL2. Isso é um caminho relativamente bem pavimentado hoje.
- Fricção arquitetural real a não esconder: a GUI Tkinter (que continua existindo por decisão já fechada
  em `ARCHITECTURE.md`) não roda de forma trivial dentro de um container Linux headless — exigiria
  forwarding de X11 (ex. VcXsrv no Windows) se quisermos rodar o app inteiro dentro do container. **Opção
  mais simples, e agora reforçada pela decisão de produto confirmada** (GPU só é exigida no `Pipeline.run`,
  não no boot da GUI): usar o container/WSL2 apenas para rodar o caminho **headless/CLI**
  (`animaltrack run --gpu`, já entregue na Fase 4) — que é justamente onde o requisito de GPU faz sentido —
  e manter a GUI Tkinter nativa no Windows, sem GPU, para as telas de configuração
  (`PerspectiveUi`/`BorderUi`/`OrientationUi`). A decisão de escopo do probe (seção "Decisão de produto"
  acima) foi tomada exatamente pensando nesse encaixe: o pesquisador configura o perfil na GUI em qualquer
  máquina, e roda o processamento pesado via CLI dentro do ambiente com GPU (container ou máquina com CUDA
  nativo) quando quiser.

### Recomendação (dado: dev solo, Windows, projeto sem infraestrutura de Docker/CI-GPU hoje)

1. **Caminho primário recomendado: Opção C (Docker + build Linux dentro do container)**, apesar de exigir
   introduzir Docker como dependência operacional nova neste projeto — porque o build Linux+CUDA é
   comprovadamente mais tratável que o build Windows nativo (Opção A), e o Windows 11 do ambiente já
   suporta GPU passthrough via WSL2 sem trabalho adicional de driver. Escopo do container: só o caminho
   headless/CLI GPU-acelerado; GUI continua nativa e CPU-only para as telas de configuração (consistente
   com a decisão de produto confirmada).
2. Entregável concreto desta escolha: um `Dockerfile.cuda` no repo (fora do escopo de código deste plano —
   é infraestrutura, documentado aqui como decisão, criado como parte da tarefa de empacotamento, não como
   "plugin puro" de código de estágio) + um `docs/gpu-setup.md` com o passo a passo exato (versão do CUDA
   Toolkit, tag do OpenCV/opencv_contrib usada, comando `cmake` completo, comando `docker build`/`docker
   run --gpus all`).
3. **Opção B (wheel de terceiro) como fallback tático apenas**, só para destravar iteração local rápida se
   o Docker+WSL2 der problema nesta máquina específica — nunca como o caminho documentado/suportado
   oficialmente do projeto, pelo risco de proveniência/manutenção.
4. **Opção A (build nativo Windows) não recomendada como caminho principal** — maior esforço, maior
   fragilidade, pior tempo-até-primeiro-sucesso para um dev solo, mesmo sendo a opção que "parece" mais
   direta por não introduzir Docker. Só considerar se Docker for uma restrição dura e inegociável do
   usuário.

### Risco/bloqueio a declarar explicitamente (não maquiar)

Este é um problema de infraestrutura real, não só "mais um pacote pip". Pode consumir dias inteiros de
tentativa-e-erro de versão de toolkit/driver/compilador — é um ponto de dor conhecido e recorrente na
comunidade OpenCV+CUDA, independente de sistema operacional, e pior no Windows. **Não é paralelizável com
a verificação de código** no sentido de que nenhum teste de paridade real ou execução `--gpu` de fato pode
rodar antes desse ambiente existir — mas *é* paralelizável com a *escrita* das Tarefas 1.2–1.4 (o código
dos plugins pode ser escrito e revisado contra a superfície documentada da API `cv2.cuda` sem um ambiente
funcional; só não pode ser *executado/validado* sem ele). Tratar "obter um `cv2` com CUDA funcionando" como
milestone próprio, com go/no-go separado, bloqueante apenas para a Tarefa 1.5 (integração/paridade), não
para 1.2–1.4.

---

## 3. Desenho dos testes de paridade CUDA vs CPU

**Assimetria de algoritmo — registrar antes de tudo (achado de verificação contra o código real da Fase
3)**: o detector CPU (`BackgroundSubtractionDetector`, porte de `backgroundRemoveModule.py`) **não usa
MOG2**. É subtração de fundo por *imagem de máximo estático* (`np.max` das amostras a cada 500 frames) +
`cv2.absdiff` + threshold fixo (80, depois 127), em duas passadas não-causais (ver Fase 3, seção 3). O
detector GPU (`CudaMOG2Detector`) usa MOG2 (`cv2.cuda.createBackgroundSubtractorMOG2`) — primitiva de GPU
escolhida em `ARCHITECTURE.md` (seção "Estratégia GPU"). São **dois algoritmos diferentes de subtração de
fundo**, não a mesma lógica com backend trocado; só o passo final de contorno/centroide
(`findContours`/`moments`/maior área) é idêntico entre os dois. Consequências concretas para o teste:
- **Não existem "parâmetros de MOG2 idênticos nos dois lados"**: só o lado GPU tem
  `history`/`varThreshold`/`detectShadows`; o lado CPU tem os thresholds fixos 80/127 e a imagem de máximo.
- **"Frames de aquecimento" aplica-se só ao MOG2 (GPU)**, que é stateful e precisa convergir; o lado CPU é
  estático/duas-passadas e não tem aquecimento — a comparação deve alinhar as séries descartando, nos dois
  lados, os mesmos frames iniciais em que o MOG2 ainda não convergiu.
- Portanto o **Teste 2 abaixo é uma equivalência comportamental ponta-a-ponta na fixture** (os dois
  caminhos localizam o mesmo alvo aproximadamente no mesmo lugar), **não** uma paridade de máscara/bit entre
  duas implementações do mesmo algoritmo. Isso é viável na fixture sintética justamente porque o alvo (um
  círculo escuro sólido sobre fundo uniforme) é forte e não-ambíguo — ambos os algoritmos convergem pra
  quase o mesmo centroide; não seria garantido em vídeo real com fundo complexo.

**Nota pro dono do projeto (confirmar, não reabrir aqui)**: essa combinação — MOG2 na GPU vs. máximo-estático
na CPU, ambos sob um teste chamado "paridade" — é uma tensão herdada de `ARCHITECTURE.md`, não introduzida
por este plano. Se a intenção for paridade *de algoritmo* de verdade, o detector GPU teria que replicar o
máximo-estático via `cv2.cuda.absdiff`/`cv2.cuda.threshold` (o que exigiria estender `ArrayBackend` com
essas duas operações, que hoje não constam da seção 1.2) em vez de MOG2. Este plano segue a decisão atual de
`ARCHITECTURE.md` (MOG2 na GPU) e trata "paridade" como equivalência comportamental.

Fixture: o mesmo vídeo curto de referência usado no golden-file test da Fase 3 (mesmos frames, mesma
homografia). Para o lado GPU, fixar `history`/`varThreshold`/`detectShadows` explicitamente e descartar os
primeiros N frames de aquecimento do MOG2 antes de comparar (MOG2 é stateful e precisa convergir); o lado
CPU não tem estado a aquecer, mas só entra na comparação nos mesmos frames pós-aquecimento, pra alinhar as
duas séries frame a frame.

**Teste 1 — paridade do rectifier isolado** (isola do ruído estocástico do MOG2):
- Mesmo frame de entrada + mesma matriz de homografia, warp via `CpuArrayBackend` e via
  `CudaArrayBackend`.
- Métrica: diferença absoluta por pixel (`cv2.absdiff`) entre as duas imagens de saída — critério de
  aprovação: média da diferença ≤ 1–2 níveis de cinza (8 bits) e diferença máxima ≤ ~5 (folga para
  arredondamento de interpolação subpixel, que pode diferir levemente entre implementação CPU e CUDA do
  `warpPerspective`).

**Teste 2 — paridade do detector completo (rectify+MOG2 encadeados)**:
- Roda a fixture inteira pelos dois caminhos completos (CPU: `CpuPerspectiveRectifier` +
  `BackgroundSubtractionDetector`; GPU: `CudaPerspectiveRectifier` + `CudaMOG2Detector`).
- Por frame onde **ambos** os lados produzem detecção, comparar:
  - **Distância de centroide**: `euclidean(centroide_cpu, centroide_gpu) <= 3.0 px` (constante nomeada
    `PARITY_CENTROID_TOLERANCE_PX`, ajustável por fixture/resolução).
  - **Área do contorno**: `abs(area_cpu - area_gpu) / max(area_cpu, area_gpu) <= 0.15` (15% de tolerância
    relativa — os dois lados usam algoritmos de subtração de fundo diferentes, MOG2 na GPU vs.
    máximo-estático+`absdiff` na CPU, então as máscaras diferem no contorno mesmo detectando o mesmo alvo; a
    folga absorve essa diferença de algoritmo, não só ruído de arredondamento).
- **Taxa de concordância de presença/ausência de detecção**: fração de frames em que um lado detecta e o
  outro não deve ser ≤ 2% dos frames da fixture (tolera flicker de 1 frame perto do início/fim de
  movimento, causado por diferenças de limiar entre os dois algoritmos de subtração de fundo — MOG2 vs.
  máximo-estático — sem mascarar uma divergência sistemática).
- Falha do teste se: p95 da distância de centroide exceder a tolerância, OU a taxa de discordância de
  presença exceder o limite acima. Reporta por-frame no output do teste pra facilitar debug (não só
  pass/fail agregado).

Local: `tests/gpu/test_cuda_rectifier_parity.py`, `tests/gpu/test_cuda_mog2_parity.py` — ambos marcados
`@pytest.mark.gpu`.

---

## 4. Paralelização

Confirmado, em linha com a tabela de paralelização de `ARCHITECTURE.md` ("Fase 5 |
`CudaPerspectiveRectifier` / `CudaMOG2Detector` | espera interfaces `Rectifier`/`Detector` (Fase 3);
paralelo total"), **com uma ressalva que a tabela do documento-mãe não deixa explícita e este plano
adiciona**: os dois plugins não são de fato "paralelo total" desde o primeiro instante — ambos consomem o
mesmo `ArrayBackend` (Tarefa 1.2), que precisa existir primeiro. Ordem real:

1. Sequencial (1 agente): `src/core/array_backend.py` + `src/core/gpu.py` (Tarefa 1.2). Isso é
   pré-requisito **compartilhado**, não específico de rectify nem de detect — ambos os plugins importam e
   recebem uma instância de `ArrayBackend` no construtor.
2. Só depois, fork em paralelo (worktrees separados, arquivos disjuntos — `src/stages/rectify/cuda/*` vs
   `src/stages/detect/cuda/*`, sem dependência de contrato um do outro): Tarefa 1.3
   (`CudaPerspectiveRectifier`) e Tarefa 1.4 (`CudaMOG2Detector`) simultaneamente.
3. A tarefa de empacotamento (seção 2) é ortogonal a 1 e 2 — não toca arquivo de código nenhum, corre em
   paralelo com tudo — mas é pré-requisito bloqueante só da Tarefa 1.5 (integração/paridade), não das
   tarefas 1.2–1.4 (que podem ser escritas e revisadas sem ambiente CUDA real, só não executadas).

---

## 5. Plano de teste e comandos de verificação

**Sem GPU / sempre rodam (CI e local)**:
- `pytest -m "not gpu"` — suíte principal, roda em qualquer máquina/CI sem GPU.
- Testes incluídos aqui: `cuda_device_count()`/`require_cuda()` com `cv2.cuda` mockado (0/1/2 dispositivos,
  e caso `AttributeError` simulando build sem módulo cuda); `CpuArrayBackend` round-trip
  upload/download identidade e `warp_perspective` batendo com chamada direta a `cv2.warpPerspective`;
  discovery dos dois `plugin.toml` novos no `PluginRegistry` (manifest válido, `kind` correto); teste de
  "falha limpa sem device CUDA" — mocka `cuda_device_count()` pra 0 e confirma que
  `Pipeline.run(...)`/comando CLI levanta `GpuNotAvailableError` de forma limpa (sem traceback solto, sem
  arquivo parcial escrito) — **este teste não precisa de GPU real e não é marcado `gpu`**, valida
  exatamente a linha de verificação da Fase 5 em `ARCHITECTURE.md`: "startup falha limpo sem device CUDA";
  teste complementar (também sem GPU) confirmando que a GUI/telas de configuração
  (`PerspectiveUi`/`BorderUi`/`OrientationUi`) abrem e funcionam com `cuda_device_count()` mockado pra 0,
  sem levantar `GpuNotAvailableError` em nenhum momento — valida a decisão de produto confirmada (GPU só
  gate no `Pipeline.run`, não no boot).

**Com GPU (marcados `@pytest.mark.gpu`, só rodam manualmente na máquina do dev com CUDA real)**:
- `pytest -m gpu` — roda só na máquina com GPU/OpenCV-CUDA funcionando.
- Inclui: `CudaArrayBackend` round-trip real, paridade de rectifier isolado, paridade de detector completo
  (seção 3).

**Marcação e skip automático (`tests/conftest.py`)**:
```python
import pytest

def _cuda_available() -> bool:
    try:
        import cv2
        return cv2.cuda.getCudaEnabledDeviceCount() > 0
    except Exception:
        return False

def pytest_configure(config):
    config.addinivalue_line("markers", "gpu: requer build de OpenCV com CUDA e GPU física disponível")

def pytest_collection_modifyitems(config, items):
    if _cuda_available():
        return
    skip_gpu = pytest.mark.skip(reason="Nenhum dispositivo CUDA disponível / OpenCV sem módulo cuda")
    for item in items:
        if "gpu" in item.keywords:
            item.add_marker(skip_gpu)
```
Registrar o marcador também em `pyproject.toml` (`[tool.pytest.ini_options] markers = [...]`, herdado da
Fase 0).

**Comportamento em CI**: runners padrão do GitHub Actions (`ubuntu-latest`/`windows-latest`) não têm GPU —
`cv2.cuda` nem existe como atributo na wheel padrão instalada em CI, então `_cuda_available()` retorna
`False` e todo teste `gpu` é automaticamente pulado (skip, não falha) pela lógica acima, mesmo sem
configuração extra no workflow. Ainda assim, o `ci.yml` (Fase 0) deve rodar `pytest -m "not gpu"`
explicitamente — reforço redundante intencional, documenta a intenção no próprio workflow em vez de
depender só do skip automático silencioso. Runner self-hosted com GPU pra rodar `pytest -m gpu` em CI de
verdade é citado como possibilidade futura, fora de escopo desta fase (dev solo, sem orçamento de infra de
CI com GPU agora).

**Verificação manual (não scriptável em CI, só na máquina real do dev)**: depois que o ambiente da seção 2
estiver pronto, rodar `animaltrack run --gpu` na fixture e comparar tempo de parede e saída
(`AnalysisResult`) contra o resultado do golden-file test da Fase 3 (caminho CPU) — confirma que a
aceleração de fato acontece e que o resultado é equivalente, não só que os testes automatizados passam.
Além disso, abrir a GUI numa sessão/máquina sem GPU (ou com `cuda_device_count` forçado a 0 via variável de
ambiente de teste, se essa via existir) e confirmar visualmente que `PerspectiveUi`/`BorderUi`/
`OrientationUi` funcionam normalmente até o ponto de clicar em "Processar vídeo", onde então o erro amigável
aparece.

**Lint/tipos**: `ruff check src/stages/rectify/cuda src/stages/detect/cuda src/core/array_backend.py
src/core/gpu.py`; `mypy` nos mesmos arquivos — **fricção conhecida a documentar, não ignorar**: stubs de
tipo pra `cv2.cuda`/`cv2.cuda_GpuMat` são incompletos ou inexistentes nos stubs não-oficiais de OpenCV
disponíveis hoje; esperar necessidade de `# type: ignore[attr-defined]` pontual nas chamadas de `cv2.cuda.*`
— decisão de time: aceitar os `ignore` pontuais documentados (não silenciar mypy globalmente pro módulo).

---

## 6. Prontidão de handoff

Fase 5 depende de Fases 0–4 completas e tem o item de maior risco de todo o roadmap fora do código
(empacotamento CUDA, seção 2), que pode span múltiplas sessões/dias. Seguir o protocolo obrigatório de
`ARCHITECTURE.md` à risca, com ênfase especial no workstream de empacotamento:

- `docs/handoffs/fase5-array-backend-handoff.md`, `fase5-cuda-rectifier-handoff.md`,
  `fase5-cuda-detector-handoff.md` — formato padrão do protocolo (status, o que foi feito, o que falta,
  como verificar, como retomar).
- `docs/handoffs/fase5-packaging-handoff.md` — **deve registrar tentativas falhas, não só o resultado
  final**: versão exata de CUDA Toolkit/driver/GPU (compute capability)/tag de OpenCV+opencv_contrib/flags
  de `cmake` testadas, o que funcionou e o que não funcionou e por quê. Este é o workstream com maior risco
  de perda de raciocínio entre sessões — um handoff que só diz "em progresso" sem essas notas força a
  próxima sessão a repetir toda a matriz de tentativa-e-erro do zero.
- Consolidar em `docs/handoffs/PROGRESS.md` só depois que os quatro workstreams (array-backend + 2 plugins
  + packaging) convergirem na Tarefa de integração (1.5) — não marcar Fase 5 como concluída em
  `PROGRESS.md` enquanto o milestone de empacotamento não estiver "pronto o suficiente pra rodar os testes
  de paridade reais", já que sem isso a fase não foi de fato verificada, só escrita.
- Decisão de produto que já foi confirmada e não precisa ser reaberta em nenhum handoff futuro:
  `require_cuda()` gate apenas `Pipeline.run`/comando `run` da CLI, nunca o boot da GUI ou as telas de
  configuração (ver seção "Decisão de produto já fechada" no topo deste documento). Qualquer handoff ou
  implementação que gate a GUI inteira atrás do probe de CUDA está em desacordo com esta decisão e deve ser
  corrigida.
