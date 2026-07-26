# Handoff — Decisões do dono (2026-07-26): axis avg + kalman-hungarian + [config]

## Status

Concluído. `pytest -m "not gpu"` 322 passed (317 anteriores + 8 novos de
`tests/core/test_plugin_config.py` - 3 deletados de `test_orientation.py` que
testavam API removida), `ruff check .` e `mypy src tests --python-version 3.13`
limpos.

## Contexto

Continuação de `docs/handoffs/o9-pctx-kinematics-handoff.md`. O dono revisou
todas as "decisões pendentes" acumuladas nos handoffs de Fase 1/4/5/6 e decidiu
caso a caso (via `AskUserQuestion`, registrado nesta conversa). A maioria foi
"aprovar o que já estava implementado" (sem mudança de código); 3 decisões
exigiram trabalho real, executado em 3 subagentes `general-purpose` paralelos
com escopo de arquivo disjunto.

## Decisões só confirmadas (sem mudança de código)

- Fase 1 (a): `profile.py` fora da lista literal do ARCHITECTURE.md — aprovado.
- Fase 1 (c): `Metric.value` restrito a `JsonSafeValue` estrito — aprovado.
- Fase 4: rótulo PDF `Altura=box_cm.y`/`Profundidade=box_cm.z` — aprovado.
- Fase 4: split `Pipeline.run` (só metadata) / `run_cpu_analysis` (pipeline
  inteira) — aprovado, manter.
- Fase 4: `SessionState` no `AppService` — aprovado.
- Fase 6: dar default a `view` no `SingleEntityTracker` — já resolvido num
  commit anterior (`de67528`, antes desta sessão); o handoff da Fase 6 estava
  desatualizado ao dizer que isso ainda faltava. Nada feito agora.

## Trabalho real executado

### 1. Fase 1 (b): política de eixo doblemente observado — TOP-vence → média

**Antes**: quando um eixo 3D (x/y/z) era observável pelas duas câmeras (ex.
ambas veem X), `BoxOrientationConfig.axis_mapping()` escolhia TOP como fonte
única e descartava a leitura da SIDE. **Agora**: as duas leituras são usadas —
convertidas pra cm independentemente (cada câmera com sua própria razão
px/cm) e depois tiradas a MÉDIA aritmética.

Mudanças:
- `src/core/schema/orientation.py`: `axis_mapping() -> AxisMapping` (single
  source) removido inteiramente (classe `AxisMapping`, validador
  `_distinct_sources`, método `.resolve()` — nenhum outro chamador funcional
  existia além de `Fusion`/`build_border_region`, confirmado por grep antes de
  deletar). Substituído por `axis_sources() -> dict[BoxAxis, list[AxisSource]]`
  (retorna 1 ou 2 fontes por eixo, ordenadas TOP-primeiro só por determinismo,
  não mais por prioridade).
- `src/stages/fuse/plugin.py`: `Fusion.fuse()` reescrito — pra cada eixo,
  converte a leitura de CADA fonte pra cm com a razão px/cm PRÓPRIA daquela
  fonte, depois tira a média das leituras (1 ou 2). `Calibration.px_per_cm`
  reportado passa a ser a média das razões por câmera quando o eixo tem 2
  fontes. `build_border_region()`: assinatura mudou (`px_per_cm: Point3D` →
  `box_cm: Point3D`, já que uma razão pré-calculada e já-mediana não serve pra
  converter os pontos de borda de CADA câmera corretamente) — recomputa a razão
  própria de cada fonte internamente; bounds (min,max) calculados
  independentemente por câmera e depois tirada a média elemento a elemento.
- `src/stages/orchestration.py`: único call site de `build_border_region`
  atualizado pra passar `profile.box_cm` em vez de `calibration.px_per_cm`.
- Testes: `tests/core/schema/test_orientation.py` e
  `tests/stages/test_stage_fuse.py` reescritos pra `axis_sources()`. 2 testes
  da API removida (`test_axis_mapping_resolve`,
  `test_axis_mapping_distinct_sources_validator`) foram deletados (testavam
  método/validador que não existem mais). `test_route_is_in_cm` teve reescrita
  conceitual: usava `side.x=999.0` deliberadamente irrelevante pra provar que
  TOP vencia — sob a nova política isso ficaria enganoso (side.x agora
  IMPORTA), trocado por valores que exercitam a média de verdade (top.x=40→2cm,
  side.x=80→4cm, média=3cm).
- **Golden-file não mudou**: verificado empiricamente. A fixture sintética
  (`tests/fixtures/generate_fixture_videos.py`) renderiza o MESMO
  `x_cm * PX_PER_CM` nas duas câmeras (X é o eixo com empate na orientação do
  golden) — média de dois valores idênticos é o próprio valor, sem drift.
- **Achado fora do escopo original dos agentes, corrigido por mim**:
  `tests/core/schema/test_json_schema_export.py` importava `AxisMapping`
  diretamente (não estava na lista de arquivos autorizados pro agente) —
  quebrava a coleta de teste. Removido da lista de imports/`MODELS`.

### 2. Fase 6: escolha do algoritmo de tracking de produção — `kalman-hungarian`

`src/stages/orchestration.py::run_cpu_analysis` trocou
`SingleEntityTracker("top"/"side")` por
`MultiEntityTracker("top"/"side", hungarian)` (construído inline, não via
import do módulo `plugins/tracker/kalman-hungarian/` — hifenizado, não é um
caminho de import Python válido; `KalmanHungarianTracker` é só
`MultiEntityTracker` + `hungarian` injetado, então construir direto é
equivalente e evita inventar um mecanismo de import pra um diretório que só é
carregado dinamicamente pelo `PluginRegistry`).

Verificado empiricamente (não só por dedução): `MultiEntityTracker` grava o
centróide BRUTO da detecção no ponto da track (Kalman só influencia a predição
usada na associação, nunca sobrescreve o ponto gravado), e a fixture golden se
move devagar demais (~0.3px/frame) pra disparar o gating de associação
(`max_distance=60px`) — logo nenhuma fragmentação de `entity_id`, golden
idêntico, nenhum parâmetro de tuning precisou mudar.

### 3. Fase 5/6: formalizar seção `[config]` no `plugin.toml`

Aditivo, não-forçado (documentação + tipagem opcional, não um novo gate de
execução — nenhum plugin existente muda de comportamento):
- `src/core/plugin.py`: novo `PluginConfigField` (`type`, `required`,
  `default`, `description`) e `PluginManifest.config: dict[str,
  PluginConfigField]`, parseado de `[config]` no `plugin.toml` via
  `from_toml`. Novo `PluginManifest.validate_overrides(overrides) -> list[str]`
  (retorna mensagens de erro, não levanta — quem chama decide o que fazer;
  nada chama isso automaticamente hoje, é uma ferramenta que um plugin PODE
  usar no próprio `setup()`). Leniência de tipo: `"float"` aceita `int` também
  (comum em JSON/TOML); `bool` NUNCA satisfaz `"int"`/`"float"` apesar de
  `bool` ser subclasse de `int` em Python (guarda explícita).
- `plugins/metadata/fish-body-fat/plugin.toml`: declara `fish_length_cm` (tipo
  `float`, `required=false` — o fallback de env var continua um caminho válido,
  então não faz sentido marcar como obrigatório só na manifest).
- `plugins/metadata/fish-body-fat/plugin.py`: só docstring atualizada (a nota
  de decisão dizia que formalizar `[config]` era recomendação pendente —
  agora está feito).
- `docs/PLUGIN_CONTRACT.md`/`ARCHITECTURE.md`: limitação "sem `[config]`"
  atualizada pra refletir que agora existe (opcional, aditivo).
- Novo `tests/core/test_plugin_config.py` (8 testes): parsing com/sem
  `[config]`, `validate_overrides()` (obrigatório ausente, satisfeito, tipo
  incompatível, leniência int→float, bool rejeitado, chave extra ignorada).

## Como verificar

```
pytest -m "not gpu"                              # 322 passed, 3 deselected
pytest tests/core/schema/test_orientation.py tests/stages/test_stage_fuse.py tests/test_golden_pipeline.py -q
pytest tests/test_golden_pipeline.py tests/test_debug_frames.py -q   # tracker swap, golden idêntico
pytest tests/core/test_plugin_config.py -q
ruff check .                                      # All checks passed!
mypy src tests --python-version 3.13              # Success: no issues found
```

## O que falta

Nada deste escopo. Segue faltando (ver `docs/handoffs/PROGRESS.md`): validação
de CUDA em hardware real (Fase 5, bloqueio de infra), resto dos grupos B/C/D
do doc de pesquisa de metadados (mudam schema/estágio, risco médio).

## Como retomar

Se algo tocar `src/core/schema/orientation.py`/`src/stages/fuse/plugin.py`
no futuro, `axis_mapping()`/`AxisMapping`/`.resolve()` NÃO EXISTEM MAIS —
qualquer código legado/exemplo em docs que ainda os mencione está
desatualizado, usar `axis_sources()`.
