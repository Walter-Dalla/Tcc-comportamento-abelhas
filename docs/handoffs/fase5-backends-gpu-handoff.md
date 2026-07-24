# Handoff: Fase 5 — Backends GPU (plugins puros)
Status: in-progress (código completo e verificado sem CUDA; empacotamento OpenCV+CUDA pendente)
Última atualização: 2026-07-24

Cobre os quatro workstreams do plano num só documento (dev solo): plumbing central
(`array-backend` + `gpu`), `cuda-rectifier`, `cuda-detector` e `packaging`.

## O que foi feito

### Gate GPU + probe (`src/core/gpu.py`)
- `cuda_device_count() -> int`: wrapper NÃO-lançante sobre
  `cv2.cuda.getCudaEnabledDeviceCount()`. Retorna 0 em qualquer indisponibilidade
  (sem cv2, cv2 sem submódulo `cuda`, build sem CUDA que levanta `cv2.error`).
- `require_cuda(min_devices=1) -> int`: GATE obrigatório. Levanta
  `GpuNotAvailableError` (RuntimeError) com mensagem clara incluindo a contagem;
  retorna a contagem em sucesso. NÃO faz `sys.exit`/log-and-continue/UI (core puro).
- `probe_cuda_devices()`/`GpuProbeResult` mantidos (compat Fase 2 + runner). Agora
  delegam a `cuda_device_count()`.

### Ponto de chamada do gate (decisão de produto fechada — NÃO reabrir)
- `src/core/pipeline.py::Pipeline.run`: se `request.gpu`, chama `require_cuda()`
  ANTES de tocar em `Workspace`/`ResultStore` (falha alta e cedo, sem resultado
  parcial). Gate SÓ aqui — nunca no boot da GUI/Tk nem nas telas de config.
- `src/app/runner.py::execute_analysis`: `require_gpu=True` delega a `require_cuda()`
  e re-embrulha em `GpuRequiredError`, que agora é **subclasse de
  `GpuNotAvailableError`** (a CLI já captura `GpuRequiredError` no comando `run`).
  A GUI (`src/app/service.py`) chama `execute_analysis(require_gpu=...)`, então herda
  o gate no mesmo ponto — abrir/configurar telas continua CPU-only.

### `ArrayBackend` (`src/core/array_backend.py`)
- `ArrayBackend` (Protocol runtime_checkable): `upload`/`download`/`warp_perspective`/
  `cvt_color_gray`/`release`. Handle opaco: `np.ndarray` no CPU, `cv2.cuda_GpuMat`
  no CUDA. Frame fica residente na GPU entre Rectify→Detect (sem round-trip RAM).
- `CpuArrayBackend`: upload/download identidade; warp/cvt via `cv2.*` direto. Existe
  para paridade e para exercitar os estágios CUDA SEM hardware.
- `CudaArrayBackend`: construção guardada por `require_cuda()` — falha limpa sem GPU
  (não vira no-op nem estoura AttributeError cru). Operações via `cv2.cuda.*`.
- **Nota de escopo documentada no docstring**: `cv2.cuda` não expõe `findContours`/
  `moments` práticos — só warp/cvtColor/MOG2 rodam na GPU; extração de contorno/
  centroide continua em CPU sobre a máscara baixada. Não é "tudo na GPU".

### `CudaPerspectiveRectifier` (`src/stages/rectify/cuda/{plugin.py,plugin.toml}`)
- MESMA interface do `CpuPerspectiveRectifier`: construtor
  `(frame_points, orientation, role, video_width, video_height, backend=None)`,
  props `role`/`output_shape`, `rectify(frame, frame_index) -> RectifiedFrame`.
  Matriz calculada uma vez no `__init__`. Backend default (`CudaArrayBackend`) só é
  construído no primeiro `rectify()` (gate cai no uso, não na construção).
- `plugin.toml`: `kind="rectify"`, `name="cuda-perspective-rectifier"`.

### `CudaMOG2Detector` (`src/stages/detect/cuda/{plugin.py,plugin.toml}`)
- MESMA interface `Detector`: `detect(frame) -> FrameDetections`, prop `role`,
  `setup()`. Subtractor MOG2 criado no `setup()` (gate CUDA), não no `__init__` —
  construção zero-arg (role default TOP) funciona sem GPU.
- **Algoritmo DIFERENTE do CPU** (decisão de ARCHITECTURE.md): MOG2 vs
  máximo-estático+absdiff. Só o passo final contorno/centroide coincide (replicado,
  `cy_from_bottom = frame_height - cy_from_top`). Por isso "paridade" = equivalência
  comportamental na fixture, não paridade de bit.
- `plugin.toml`: `kind="detector"`, `name="cuda-mog2-detector"`.

### Testes + infra de teste
- Marcador `gpu` registrado em `pyproject.toml` e `tests/conftest.py`
  (`pytest_collection_modifyitems` pula testes `gpu` quando `cuda_device_count()==0`).
- Sem GPU (rodam sempre): `tests/core/test_gpu_gate.py`,
  `tests/core/test_array_backend.py`, `tests/core/test_pipeline_gpu_gate.py`,
  `tests/test_runner_gpu.py`, `tests/stages/test_cuda_rectifier.py`,
  `tests/stages/test_cuda_detector.py`.
- Com GPU (`@pytest.mark.gpu`, pulados aqui): `tests/gpu/test_cuda_parity.py`
  (Teste 1 rectifier + placeholder skip rastreável do Teste 2 detector) e o
  round-trip real de `CudaArrayBackend`.
- `ci.yml`: `pytest -m "not gpu"` explícito.
- `# type: ignore[attr-defined]` PONTUAIS e documentados nas chamadas `cv2.cuda.*`
  (stubs do OpenCV não declaram os símbolos contrib+CUDA) — decisão do plano seção 5.

## O que falta

1. **Empacotamento OpenCV+CUDA (item de maior risco, fora de código)** — sem isso
   nada do caminho CUDA foi EXECUTADO, só escrito/verificado estruturalmente:
   - Esta máquina de dev tem `cv2 5.0.0` (build PyPI): `cuda_device_count()==0` e
     `cv2.cuda.warpPerspective`/`createBackgroundSubtractorMOG2` NÃO existem (só
     `cuda_GpuMat`/`Stream` existem). Confirma o risco do plano seção 2.
   - Caminho recomendado (ARCHITECTURE.md + plano seção 2): Docker + build Linux
     dentro do container (WSL2 GPU passthrough no Win11), escopado ao caminho
     headless/CLI. Entregáveis a criar: `Dockerfile.cuda` + `docs/gpu-setup.md`.
   - Registrar tentativas (versão CUDA Toolkit/driver/compute capability/tag OpenCV+
     opencv_contrib/flags cmake) aqui conforme forem feitas — não só o resultado.
2. **Teste 2 (paridade comportamental do detector completo)**: hoje é um `skip`
   rastreável em `tests/gpu/test_cuda_parity.py`. Estruturar a asserção real (rodar a
   fixture de vídeo da Fase 3 pelos dois caminhos, descartar frames de aquecimento do
   MOG2, comparar centroide<=3px / área<=15% / discordância de presença<=2%) quando o
   ambiente CUDA existir.
3. **Wiring de orquestração GPU** (opcional, fora do escopo mínimo desta fase): hoje
   `run_cpu_analysis` constrói só os estágios CPU. Um `run_gpu_analysis` (ou um flag
   que troque as fábricas por `CudaPerspectiveRectifier`/`CudaMOG2Detector`) só faz
   sentido depois do item 1. Os plugins CUDA já satisfazem o contrato para isso.

## Como verificar o que já foi feito

```
pytest -m "not gpu"      # 236 passed (204 pré-existentes + 32 novos)
pytest -m gpu            # 3 skipped (sem device CUDA) — não falha
ruff check src tests     # All checks passed!
mypy src tests --python-version 3.13   # Success: no issues found
```

Verificação manual (só na máquina com OpenCV+CUDA real, após item 1): `pytest -m gpu`
deve rodar (não pular) e passar o Teste 1; `animaltrack run --gpu --profile <p>` deve
acelerar e produzir `AnalysisResult` equivalente ao caminho CPU (golden Fase 3).

## Como retomar

- Próximo passo exato: **workstream de empacotamento** (item 1 acima) — montar
  `Dockerfile.cuda` + `docs/gpu-setup.md`, obter um `cv2` com módulo cuda, então
  `pytest -m gpu` de verdade e estruturar o Teste 2 (item 2). Só depois marcar a
  Fase 5 como `done` no `PROGRESS.md` (o plano seção 6 é explícito: não fechar a fase
  enquanto os testes de paridade reais não puderem rodar).
- Decisão de produto JÁ confirmada, não reabrir: `require_cuda()` gate apenas
  `Pipeline.run`/caminho de análise, nunca boot da GUI/telas de config.
- Débito documentado: o manifest (`PluginRequires`, `extra="forbid"`) não expressa
  "precisa de build com CUDA". Não foi adicionado `requires.capabilities` para não
  mexer no schema/discovery da Fase 2 nesta fase; a exigência está nos comentários dos
  dois `plugin.toml` e aqui. Se/quando adicionar o campo, checar via
  `gpu.cuda_device_count() > 0` no discovery de um run real (não na listagem/GUI).
- Nota de ambiente: máquina de dev roda Python 3.13 com cv2 5.0.0/numpy 2.5.1
  (substitutos dos pins 4.9.0.80/1.26.3 que não têm wheel 3.13); rodar mypy com
  `--python-version 3.13`. CI fixa 3.11.
