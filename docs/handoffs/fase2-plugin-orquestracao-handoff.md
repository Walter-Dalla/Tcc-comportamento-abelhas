# Handoff: Fase 2 — sistema de plugin + esqueleto de orquestração

Status: done
Última atualização: 2026-07-23

Cobre todos os workstreams da Fase 2 (Agente A: `errors`→`plugin`→`stages`→
`plugin_registry`→`pipeline`; Agente B: `gpu`; Agentes C/D: plugins `speed`/
`border`), executados por um único agente num worktree isolado. Spec autoritativa:
`ARCHITECTURE.md` (seções "Contrato de plugin", "Abstração Detector/Tracker",
"Fase 2") + `docs/plans/fase2-detalhado.md` (plano detalhado, já auditado 2x).

## Base do worktree

O worktree nasceu de um commit antigo (5710782, anterior à Fase 0). Foi feito
`git merge --ff-only main` (working tree limpo) para trazer Fases 0+1 (HEAD ficou
em `53e6882 Merge Fase 1`) antes de implementar. Mesma situação/mitigação do
handoff da Fase 1.

## O que foi feito

### Arquivos criados
- `src/core/errors.py` — hierarquia de exceção do subsistema de plugin:
  `PluginError` (base) → `PluginManifestError`, `PluginApiVersionError`,
  `PluginSchemaVersionError`, `PluginContractError`, `PluginNotFoundError`,
  `PluginOrderingCycleError`, `PluginLoadError`. Sem imports do core (evita ciclo).
- `src/core/plugin.py` — `PluginKind` (8 kinds), `PluginRequires`, `PluginOrdering`,
  `PluginManifest` (+ `from_toml()` como única fonte de verdade de disco),
  `PluginSpec` (manifest + `source_dir`), `Plugin(ABC)` (ClassVar `manifest`,
  hooks `setup(ctx)`/`teardown()` no-op). `TYPE_CHECKING` import de
  `PipelineContext` para o mypy resolver a anotação sem ciclo em runtime.
- `src/core/stages.py` — `Detector`, `Tracker`, `MetadataPlugin` (base do
  kind=metadata, método canônico `run(ctx)->None` conforme ARCHITECTURE.md, NÃO
  `compute`). Alias `RectifiedFrame = object` sob `TYPE_CHECKING` (tipo real chega
  na Fase 3).
- `src/core/plugin_registry.py` — `PluginRegistry.discover()` (varre
  `<root>/*/plugin.toml`, valida manifest, registro preguiçoso, manifest inválido
  logado+pulado), `instantiate()` (valida api_version→schema range→importa entry→
  valida subclasse por kind→injeta manifest→instancia), `get()`/`for_kind()` (com
  isolamento de erro), `register_instance()` (registro direto p/ testes),
  `_topological_order()` (Kahn com desempate `(-priority, nome)` + detecção de
  ciclo). `SUPPORTED_API_VERSIONS = {"1.0"}`.
- `src/core/pipeline.py` — `RunRequest`, `PluginFailure`, `RunResult`,
  `PipelineContext` (dataclass, não-pydantic), `Pipeline.run()` (carrega
  `AnalysisResult` via `ResultStore`, roda só o kind `metadata` ordenado, salva).
- `src/core/gpu.py` — `GpuProbeResult` + `probe_cuda_devices()` (nunca lança,
  captura ampla `Exception`).
- `plugins/speed/{plugin.toml,plugin.py}` — `SpeedPlugin(MetadataPlugin)`, adapter
  fino portando `MetadataModule/speedModule.py`.
- `plugins/border/{plugin.toml,plugin.py}` — `BorderPlugin(MetadataPlugin)`,
  `ordering.after=["speed"]`, consome `BorderRegion.bounds`.
- Testes (todos verdes): `tests/conftest.py` (fixtures/fábricas compartilhadas),
  `tests/core/test_plugin_manifest.py`, `test_plugin_registry_discovery.py`,
  `test_plugin_registry_versioning.py`, `test_plugin_registry_ordering.py`,
  `test_pipeline_error_isolation.py`, `test_gpu_probe.py`,
  `test_pipeline_metadata_e2e.py`, `tests/plugins/test_speed_plugin.py`,
  `tests/plugins/test_border_plugin.py`. **+29 testes (112 → 141 no total).**
- `pyproject.toml` — adicionada dependência `packaging>=23` (usada por
  `SpecifierSet` na checagem do range `schema`).

### Bugs legados PRESERVADOS verbatim (correção é da Fase 3, não desta)
- `SpeedPlugin`: bug #2 (dupla divisão por ratio: `speed = distance/ratio` onde
  `distance` já embute o ratio) e bug #6 (`average = speed_total / len(route.points)`
  em vez de `len-1`) mantidos. Marcados com `# BUG #N PRESERVADO` no código e
  travados por `tests/plugins/test_speed_plugin.py` como teste de regressão (diff
  de comparação para quando a Fase 3 corrigir).
- `BorderPlugin`: a mistura de eixos do `borderModule.py` legado NÃO é reproduzida
  aqui — por decisão do próprio plano (seção 0), essa derivação vive upstream de
  quem popula `BorderRegion.bounds` (fixture na Fase 2; `axis_mapping()` na Fase 3).
  O plugin só conta containment por eixo 3D já resolvido.

## Decisões / desvios em relação à letra do plano

1. **`ResultStore.save(result)` — assinatura real difere do plano.** O
   `pipeline.py` do plano chamava `store.save(request.profile, ctx.result)`, mas a
   API real da Fase 1 é `ResultStore.save(result: AnalysisResult)` (o profile vem
   de `result.profile`). Adaptado para `store.save(ctx.result)`. Sem impacto de
   comportamento.
2. **`teardown()` via try/finally (não `break`).** O plano deixava um `break` que
   pularia `teardown` quando `run` falha; a própria seção 3 do plano recomendava
   trocar por try/finally para plugins com estado. Implementado
   `_execute_metadata_plugin()` com `setup` isolado + `run`/`teardown` num
   try/finally: se `setup` falha, run/teardown não rodam; se `setup` teve sucesso,
   `teardown` roda SEMPRE, mesmo com `run` falho. Cada estágio falho vira um
   `PluginFailure` independente.
3. **`Workspace(root=Path(request.workspace))`** — `request.workspace` é `str`;
   pydantic coage em runtime, mas o mypy exige `Path` explícito. Convertido.
4. **Campo `PluginManifest.schema`** — mantido o nome `schema` (fiel ao contrato do
   `plugin.toml` do ARCHITECTURE.md), apesar de pydantic emitir um `UserWarning`
   benigno ("Field name 'schema' shadows an attribute in parent BaseModel") e do
   mypy exigir `# type: ignore[assignment]`. Renomear com alias mudaria os sites de
   acesso `spec.manifest.schema` do plano — preferiu-se fidelidade ao plano. O
   warning aparece 1x na coleta do pytest; é inofensivo.
5. **`register_instance()`** — método adicionado ao registry (não no plano) para o
   teste de isolamento de erro registrar plugins dummy sem passar por disco. Puro
   aditivo, não altera os caminhos de discovery/instantiate.
6. **Chaves de `speed` como `str(frame_index)`** — obrigatório: `Metric.value`
   (union estrito da Fase 1) rejeita `dict` com chave `int` (JSON não tem chave
   inteira). Já antecipado na nota de forward-compat do handoff da Fase 1.
7. **`px_per_cm` escalar** — `Calibration.px_per_cm` é `Point3D` (por eixo); o
   escalar legado é aproximado pela média dos 3 componentes, documentado inline no
   `SpeedPlugin`. Correção de raiz (bug #3, via `axis_mapping()`) é da Fase 3.

## Como verificar o que já foi feito

Comandos (da raiz do worktree), todos passando nesta entrega:
- `pytest` → **141 passed, 1 warning** (o warning `schema` benigno acima).
- `pytest tests/core tests/plugins -q` → 29 testes da Fase 2 verdes.
- `ruff check src plugins tests` → **All checks passed!**
- `mypy src tests --python-version 3.13` → **Success: no issues found in 67 source
  files** (fallback local; CI usa 3.11 + pins).
- Smoke de discovery/ordenação:
  ```
  python -c "from pathlib import Path; from src.core.plugin_registry import PluginRegistry; from src.core.plugin import PluginKind; r=PluginRegistry(); r.discover([Path('plugins')]); print([p.manifest.name for p in r.for_kind(PluginKind.METADATA)])"
  ```
  → saída esperada `['speed', 'border']`.

Ambiente local em Python 3.13: mesma estratégia dos handoffs 0/1 (pins numpy/opencv
não têm wheel 3.13; usar substitutos + `mypy ... --python-version 3.13`).

## Como retomar

Fase 2 concluída e verificada. Próxima é a **Fase 3** (a grande refatoração:
Capture/Rectify/Detect/Track/Fuse streaming). O que a Fase 3 consome desta fase:
- `from src.core.stages import Detector, Tracker, MetadataPlugin` — bases fixadas.
  Trocar o alias `RectifiedFrame = object` (em `stages.py`, sob `TYPE_CHECKING`)
  pelo tipo real quando o estágio Rectify existir.
- `from src.core.plugin import Plugin, PluginKind, PluginManifest, PluginSpec`.
- `PluginRegistry.discover()/for_kind()` já servem qualquer kind; basta adicionar a
  classe-base do kind em `_KIND_BASE_CLASS` (`plugin_registry.py`) quando
  Capture/Rectify/Fusion ganharem base própria.
- `Pipeline.run()` hoje só roda o kind `metadata`; a Fase 3 estende o corpo de
  `run()` para sequenciar Capture→Rectify→Detect→Track→Fuse antes do metadata.
- **Corrigir aqui na Fase 3**: bug #2 e #6 no `plugins/speed/plugin.py` (fórmula de
  velocidade), bug #3 via `Calibration.px_per_cm` por eixo (`axis_mapping()`), e
  popular `BorderRegion.bounds` via `axis_mapping()` em vez da fixture de teste. Os
  testes de regressão de `speed` vão precisar dos valores atualizados.

### Decisões pendentes de confirmação do dono (herdadas + novas)
- Herdadas da Fase 1 (a/b/c) — ainda abertas, ver handoff da Fase 1.
- Novas desta fase: item 4 acima (manter nome de campo `schema` com warning
  benigno) e item 2 (try/finally em vez do `break` do plano — melhoria fiel à
  própria recomendação da seção 3 do plano). Ambas implementadas conforme
  julgamento técnico; só falta o "ok" do dono.
