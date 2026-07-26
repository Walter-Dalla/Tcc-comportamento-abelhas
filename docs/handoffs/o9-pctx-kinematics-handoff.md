# Handoff — O9 + gap setup(pctx) + plugin kinematics

## Status

Concluído. `pytest -m "not gpu"` 317 passed (311 anteriores + 6 novos de
`kinematics`), `ruff check .` e `mypy src tests --python-version 3.13` limpos.

## O que foi feito

Continuação de `docs/handoffs/otimizacao-bugs-handoff.md` — os 3 itens que
sobraram do handout e não exigiam decisão do dono, executados em 3 subagentes
paralelos (`general-purpose`, cada um em arquivo(s) isolado(s)) + 2 correções
manuais minhas pra fechar efeitos colaterais que os agentes corretamente não
tentaram resolver fora do próprio escopo:

1. **O9** (`src/stages/rectify/plugin.py`): `cvtColor` (BGR→gray) movido pra
   ANTES do `warpPerspective` — warpar 1 canal em vez de 3 é mais barato.
   Achado importante: `tests/fixtures/golden_config.py::golden_profile()` usa
   `perspective_points_top=[]`/`perspective_points_side=[]`, ou seja, o golden
   test sempre cai no fallback de identidade (o short-circuit O10 do PR
   anterior pula o warp de vez) — **o golden-file NÃO precisou de regeneração**,
   confirmado empiricamente rodando os testes, não só por dedução.
   - **Efeito colateral encontrado e corrigido**: a mudança quebrou
     `tests/stages/test_cuda_rectifier.py::test_rectify_matches_cpu_rectifier_bit_for_bit`,
     que compara `CudaPerspectiveRectifier` (rodando com `CpuArrayBackend`
     injetado, sem hardware CUDA) byte-a-byte contra o `CpuPerspectiveRectifier`
     usando PONTOS REAIS de perspectiva (não-identidade) — esse teste não
     passa pelo fallback, então a reordenação passou a divergir por ~±1 nível
     de cinza entre os dois rectifiers. Corrigido eu mesmo (fora do escopo do
     agente, que só tinha permissão pra `src/stages/rectify/plugin.py`):
     mesma troca de ordem espelhada em `src/stages/rectify/cuda/plugin.py`
     (`cvt_color_gray` antes de `warp_perspective`, via `ArrayBackend`).
     `tests/stages/test_cuda_rectifier.py` volta a passar 5/5.
2. **Gap `setup(pctx)`** (`src/stages/orchestration.py`, `src/app/runner.py`,
   `plugins/metadata/fish-body-fat/plugin.py`): `run_cpu_analysis` (caminho
   real CLI/GUI) agora chama `plugin.setup(pctx)` → `plugin.run(ctx)` →
   `plugin.teardown()` pra cada plugin de metadata, com um `PipelineContext`
   real (`RunRequest.overrides` + `Workspace`) — mesmo contrato que
   `Pipeline.run` (Fase 2) já honrava. `run_cpu_analysis`/`execute_analysis`
   ganharam parâmetros opcionais `overrides`/`workspace` (retrocompatíveis,
   default `None`), sem adicionar flag de CLI/UI nova (fora de escopo —
   decisão de produto). Skip de `border` sem `border_region` preservado
   intacto. Sem isolamento de erro novo — exceção de `run()` ainda propaga
   como antes. Docstring do `fish-body-fat` corrigida (a frase sobre
   `run_cpu_analysis` nunca chamar `setup()` ficou factualmente errada).
3. **Plugin novo `kinematics`** (`plugins/kinematics/`): implementa A-1 a A-4
   do doc de pesquisa de metadados (shortlist #1) num único plugin:
   - A-1: `acceleration`, `jerk` (séries cm/s²/cm/s³), `acceleration_max`,
     `deceleration_max`, `acceleration_rms`.
   - A-2: `turn_angle` (série, graus), `turn_angle_histogram` (10 bins de
     18°), `sharp_turn_count`/`sharp_turn_rate` (limiar default 90°, não
     calibrado — documentado).
   - A-3: `net_displacement`, `straightness_index`, `msd_curve` (por lag),
     `msd_exponent` (omitido se <3 pontos utilizáveis).
   - A-4: `active_frames`/`rest_frames`/`active_fraction`, `bout_count`,
     `bout_duration_mean_s`, `time_to_first_movement_s`, `rest_bouts`. Limiar
     `REST_SPEED_THRESHOLD_CM_S=0.5`, sem histerese (simplificação
     deliberada e documentada da sugestão do doc de pesquisa).
   - Mesma regra de buraco do plugin `speed` em cascata (aceleração exige 3
     frames de posição consecutivos, jerk exige 4, ângulo de virada exige 3,
     bouts fecham segmento em qualquer salto de índice). Série de velocidade
     recalculada localmente (não lida de `ctx.get_metric`) pra ficar
     autocontido mesmo se `speed` for pulado.
   - `[ordering] after = ["speed"]` no manifest.
   - **Efeito colateral encontrado e corrigido**:
     `tests/core/test_pipeline_metadata_e2e.py::test_metadata_pipeline_e2e`
     tinha uma asserção de lista EXATA (`ordered == ["speed", "border"]`)
     sobre todos os plugins metadata descobertos em `plugins/` — quebrou ao
     `kinematics` ser descoberto junto. Corrigido eu mesmo (fora do escopo do
     agente, que corretamente não tocou em arquivo existente fora do seu
     mandato): assert relaxado pra checar só a ordem relativa
     (`ordered.index("speed") < ordered.index("border")`), que é o que o
     teste realmente pretende verificar (ordenação topológica), sem travar a
     lista inteira contra a adição de novos plugins metadata no futuro.

## Como verificar

```
pytest -m "not gpu"                    # 317 passed, 3 deselected
pytest tests/stages/test_cuda_rectifier.py -q   # 5 passed (paridade CPU/CUDA restaurada)
pytest tests/plugins/test_kinematics_plugin.py -q  # 6 passed
ruff check .                           # All checks passed!
mypy src tests --python-version 3.13   # Success: no issues found in 142 source files
```

## O que falta

Nada deste escopo. Itens ainda fora (do handout original, seção A —
decisões do dono — e itens de esforço maior não cobertos aqui):
- Validação de CUDA em hardware real (Fase 5, bloqueio de infra, não de
  código).
- Todas as decisões explícitas do dono listadas em `PROGRESS.md`.
- Resto do doc de pesquisa de metadados (grupos B/C/D — exigem mudança de
  schema/estágio, risco médio, fora do critério "PR pequeno" usado aqui).
- Resto do doc de otimização (itens além de O1/O4/O5/O9/O10, se houver).

## Como retomar

`docs/handoffs/next-agent-handout.md` e os dois docs de pesquisa em
`docs/research/` seguem sendo a fonte de itens candidatos. Este handoff +
`docs/handoffs/otimizacao-bugs-handoff.md` fecham a íntegra da seção B do
handout ("trabalho que um agente pode executar sem esperar decisão do dono").
