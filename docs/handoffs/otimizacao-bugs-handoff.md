# Handoff — otimização de processamento + bugs pontuais (O1/O4/O5/O10 + fps/speed/PDF)

## Status

Concluído. `pytest -m "not gpu"` 311 passed (mesmo total de antes — golden-file
intocado), `ruff check .` e `mypy src tests --python-version 3.13` limpos.

## O que foi feito

Escopo extraído de `docs/handoffs/next-agent-handout.md` (seção B), priorizado
como PR pequeno de baixo risco — nenhuma mudança toca esqueleto das Fases 2/3
nem golden-file:

1. **O1** (`src/stages/detect/plugin.py`, `setup()`): `rectify()` só roda nos
   frames de fato amostrados (`counter % frame_block == 0`), não nos 1200 frames
   inteiros pra extrair 3 amostras.
2. **O4** (mesmo método): lista `sampled` + `np.max(sampled, axis=0)` no final
   virou acumulador incremental (`np.maximum(acc, novo, out=acc)`) — não retém
   mais O(duração/frame_block) frames em memória simultaneamente. Resultado
   numérico idêntico.
3. **O5** (`detect()`): removido o 2º `cv2.threshold` (era no-op matemática
   depois do 1º, já confirmado por investigação anterior via
   `np.array_equal`). Constante `_BINARY_THRESHOLD` removida por ficar sem uso.
4. **O10** (`src/stages/rectify/plugin.py`): `__init__` calcula
   `self._is_identity` (matriz ≈ `np.eye(3)` E mesmas dimensões do vídeo de
   entrada); `rectify()` pula `cv2.warpPerspective` nesse caso, usa o frame
   direto antes do `cvtColor`. Caso não-identidade inalterado byte a byte.
5. **Bug fps** (`src/stages/capture/plugin.py`, `open()`): trocado
   `int(cap.get(CAP_PROP_FPS))` por `cap.get(CAP_PROP_FPS)` sem truncar
   (29.97→29 era viés ~3% em toda velocidade calculada a jusante). Retorno de
   `open()` mudou de `tuple[int, ...]` pra `tuple[float, ...]`.
   - **Não** foi adicionada checagem de fps-igual entre top/side: as fixtures
     de teste reais (`main_top.avi`/`main_side.avi`... na verdade
     `uneven_top.avi`/`uneven_side.avi`) têm fps DIFERENTES por design (30 vs
     15) e dependem disso pra truncar no vídeo mais curto continuar
     funcionando. Adicionar a checagem quebrou 2 testes existentes — reverti.
     Se essa precondição de fps-igual é de fato desejada, é uma decisão do
     dono (mudaria comportamento hoje suportado), não algo pra resolver
     unilateralmente aqui.
6. **Bug speed** (`plugins/speed/plugin.py`): loop `zip(indices, indices[1:])`
   ganhou guarda de contiguidade (`if idx - prev_idx != 1: continue`) — gap de
   N frames por falha de detecção não é mais tratado como passo de 1 frame
   (o que inflava `speed`/`distance_total`/`average_speed`).
7. **Bug PDF** (`src/stages/export/pdf/template.py:33`): rótulo "Quantidade de
   frames" → "Quadros com posição reconstruída" — o valor sempre foi
   `len(routes[0].points)` (frames com reconstrução 3D bem-sucedida), nunca o
   total de frames do vídeo. Não foi adicionado campo `frame_count` novo ao
   schema (não existe hoje, fora de escopo).

Execução: 4 agentes `cavecrew-builder` em paralelo, um por arquivo isolado
(detect, rectify, speed, pdf), pra evitar colisão de edição no mesmo arquivo;
capture/fps foi feito diretamente por mim (única mudança em decisão preso a
teste, precisou de ajuste manual).

## O que falta

Nada deste escopo. Itens fora de escopo (não tocados, ver handout):
- O9 (inverter ordem cvtColor/warp no Rectify) — muda golden-file, precisa
  regeneração consciente, deixado pra rodada separada.
- Gap de configuração `setup(pctx)` nunca chamado em `run_cpu_analysis`
  (`src/stages/orchestration.py`) — mencionado no handout como "vale avaliar",
  mas é mudança de comportamento de orquestração, não bug/otimização local;
  não entrou neste PR pra manter o escopo pequeno e de baixo risco.
- Todas as "Decisões que só o dono pode confirmar" (seção A do handout) —
  não tocadas, conforme instrução.
- Decisão sobre precondição fps-igual entre câmeras (ver item 5 acima) — acaba
  virando mais uma decisão de dono, registrada aqui.

## Como verificar

```
pytest -m "not gpu"          # 311 passed, 3 deselected
ruff check .                 # All checks passed!
mypy src tests --python-version 3.13   # Success: no issues found
git diff --stat              # 5 arquivos, +27/-13
```

## Como retomar

Se for atacar o próximo item, `docs/handoffs/next-agent-handout.md` ainda tem
a lista completa (O9, gap de `setup(pctx)`, plugin `kinematics` de metadados,
decisões do dono). Este handoff cobre só o recorte O1+O4+O5+O10+bugs.
