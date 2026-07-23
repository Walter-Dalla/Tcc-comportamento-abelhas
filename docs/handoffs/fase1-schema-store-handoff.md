# Handoff: Fase 1 — schema + workspace + store

Status: done
Última atualização: 2026-07-23

Cobre os 3 workstreams da Fase 1 (Wave 1 A/B/C, Wave 2, Wave 3), executados por
um único agente num worktree isolado. Spec autoritativa: `ARCHITECTURE.md` (seções
"Orientação de câmera/caixa", "Schema de dados", "Persistência", "Fase 1") +
`docs/plans/fase1-detalhado.md`. Este handoff registra o que foi de fato feito, os
desvios necessários e as 3 decisões de projeto pendentes de confirmação do dono.

## O que foi feito

### Base do worktree (nota importante)
O worktree `agent-a2d6970578b4724aa` nasceu de um commit ANTIGO (5710782),
anterior à Fase 0 — não tinha `pyproject.toml`, `src/core`, `tests/`, `docs/`.
Foi feito `git merge --ff-only main` (fast-forward, working tree limpo, sem
commits únicos a perder) para trazer a fundação da Fase 0 (fb0e9e1) antes de
implementar. `git reset --hard` foi tentado primeiro mas bloqueado pelo
classifier; o ff-only é equivalente e não-destrutivo aqui.

### Arquivos criados
- `src/core/__init__.py`, `src/core/schema/__init__.py` — pacotes do core.
- `src/core/schema/geometry.py` — `Point2D`/`Point3D`/`BBox` (`frozen=True`,
  `extra="forbid"`; hasháveis).
- `src/core/schema/detection.py` — `Detection` (`confidence` ge/le, `area` ge),
  `FrameDetections` (lista vazia substitui a sentinela `(-1,-1)`).
- `src/core/schema/track.py` — `Track` (`dict[int, Point2D]`, buracos = oclusão).
- `src/core/schema/route.py` — `Route3D` (`dict[int, Point3D]`).
- `src/core/schema/orientation.py` — `BoxFace`/`BoxVertex`(8)/`CameraRole`/
  `CameraOrientation` (valida 4 cantos distintos), `ImageAxis`/`BoxAxis`/
  `AxisSource`/`AxisMapping` (com `.resolve()` e validador de fontes distintas),
  `BoxOrientationConfig.axis_mapping()` (algoritmo com desempate TOP-vence) e
  `Calibration` (`fps` gt 0).
- `src/core/workspace.py` — `Workspace.resolve()` (precedência cli > env
  `ANIMALTRACK_WORKSPACE` > `~/.animaltrack`), `ensure_dirs()`, `profiles_file()`,
  `result_file()`.
- `src/core/schema/profile.py` — `Profile` (mapeia 1:1 `cache/configs.json`
  legado; validador 4-ou-vazio nos 4 campos de pontos; `orientation` opcional).
- `src/core/schema/result.py` — `Metric`, `BorderRegion` (`threshold_px` +
  `bounds` por eixo, validadores ordenado/completo), `AnalysisResult`
  (`schema_version` default `SCHEMA_VERSION="1.0"`), `AnalysisContext`
  (`add_metric`/`get_metric` defensivo), `JsonSafeValue`.
- `src/core/store.py` — `atomic_write_json` (tmp no mesmo dir + fsync +
  `os.replace`; tmp órfão deliberado em crash), `ProfileStore`, `ResultStore`,
  hierarquia de erros tipados (`StoreError` → `ProfileNotFoundError`,
  `ResultNotFoundError`, `CorruptStoreError` → `SchemaVersionError`,
  `StoreWriteError`).
- Testes: `tests/core/conftest.py` (fixture `tmp_workspace`),
  `tests/core/schema/test_{geometry,detection,track,route,orientation,profile,result,json_schema_export}.py`,
  `tests/core/test_workspace.py`, `tests/core/test_store.py`. Total: **110 testes
  em tests/core**, todos verdes (112 com os 2 smoke da Fase 0).

### Decisões / desvios
- **`str, Enum` mantido (não `StrEnum`)** — o plano (seção 2) e o `ARCHITECTURE.md`
  mandam `class Foo(str, Enum)` para serialização como string simples em JSON. A
  regra `UP042` do ruff (habilitada na Fase 0) pede `StrEnum`; suprimida por
  `# noqa: UP042` em cada enum de `orientation.py`, com comentário explicando o
  motivo deliberado. Alternativa (StrEnum) satisfaria o lint mas divergiria da
  letra da spec.
- **`JsonSafeValue` = union NÃO-recursivo estrito** (ver "decisão (c)" abaixo).

## As 3 decisões de projeto pendentes de confirmação do dono

(a) **Adição de `src/core/schema/profile.py`** — fora da lista literal de arquivos
    da Fase 1 no `ARCHITECTURE.md` (`geometry, detection, track, route, result,
    orientation`). Necessária porque `ProfileStore` não tem tipo para o que
    `cache/configs.json` guarda hoje e nenhum outro lugar o define. Recomendação
    do plano: manter. **Feito conforme recomendado.**

(b) **Política "TOP-camera-vence-empate" em `axis_mapping()`** — quando um eixo 3D
    é observável pelas duas câmeras, a leitura da câmera TOP é a fonte canônica.
    Reproduz o comportamento do `routeAnalizer.py` legado (top sempre vence, side
    só contribui o eixo exclusivo). Alternativa (média das duas leituras) seria
    mais robusta a ruído mas mudaria o comportamento numérico. **Feito conforme
    recomendado (TOP-vence).**

(c) **`Metric.value` restrito a `JsonSafeValue`, não `Any`** — implementado como
    union ESTRITO não-recursivo:
    `StrictStr | StrictInt | StrictFloat | StrictBool | None |
    Annotated[list[Any], Strict()] | Annotated[dict[str, Any], Strict()]`.
    Rejeita `set`/`tuple`/`numpy.ndarray`/objeto arbitrário na CONSTRUÇÃO do
    `Metric` (falha cedo, no ponto onde o plugin errou), em vez de tardiamente na
    serialização. **Nota: mais estrito que a letra do plano** — o plano escreveu
    `list[Any] | dict[str, Any]` (sem `Strict()`), forma que em modo lax coage
    numpy/set/tuple para list e depois quebra `model_dump_json()` (verificado
    empiricamente: `np.array` vira `[np.int64(...)]` e falha na serialização) —
    ou seja, a letra do plano NÃO cumpre a intenção declarada no próprio plano. A
    variante recursiva (validar itens aninhados) foi avaliada e descartada:
    `TypeAliasType` recursivo quebra o mypy ("cyclic definition") e `TypeAlias`
    recursivo entra em `RecursionError` no pydantic. O único buraco remanescente é
    um valor não-safe ANINHADO dentro de uma list/dict (ex. `[{1,2}]`) — raro e não
    pior que a forma original do plano. Confirmar se aceita a forma estrita.

## Como verificar o que já foi feito

Ambiente: a Fase 0 pinou `numpy==1.26.3`/`opencv-python==4.9.0.80`/`pillow==10.2.0`
(sem wheel para Python 3.13, só 3.11/CI). Como o `pytest` deste repo importa o
launcher raiz `__init__.py` durante a coleta (que puxa PIL/cv2/numpy), a
verificação LOCAL em 3.13 exigiu instalar substitutos: `pydantic`, `pytest`,
`ruff`, `mypy` (via `-e .[dev]` equivalente) + `pillow numpy opencv-python
matplotlib pandas` (versões 3.13, com o warning esperado de incompatibilidade com
os pins). Mesma estratégia documentada no handoff da Fase 0. Em CI (3.11 + pins) o
launcher importa limpo e nenhum substituto é necessário.

Comandos (da raiz do worktree):
- `pytest tests/core -v` → **110 passed**.
- `pytest` (suíte inteira) → **112 passed** (110 core + 2 smoke Fase 0).
- `ruff check .` → **All checks passed!**.
- `mypy src tests` → em CI (3.11 + numpy 1.26.3): **Success**. LOCAL em 3.13 com
  numpy 2.5 substituto: rodar `mypy src tests --python-version 3.13` (contorna um
  erro de sintaxe nos stubs da numpy 2.5 sob target 3.11 — artefato exclusivo do
  substituto, idêntico ao já registrado na Fase 0) → **Success: no issues found in
  51 source files**.
- Smoke manual: `python -c "from src.core.schema.result import AnalysisResult;
  print(AnalysisResult.model_json_schema())"` → não lança.

## Como retomar

Fase 1 está concluída e verificada. A próxima fase é a **Fase 2** (`plugin.py`,
`plugin_registry.py`, `pipeline.py`, `stages.py`, `errors.py`, + plugins
`speed`/`border`). Ver `docs/plans/fase2-detalhado.md`.

Consumo do schema pela Fase 2 (confirmado por leitura cruzada do plano da Fase 2):
- `from src.core.schema.result import AnalysisContext, AnalysisResult, Metric,
  BorderRegion, SCHEMA_VERSION` — todos expostos.
- `from src.core.schema.orientation import Calibration` — exposto.
- `from src.core.store import ResultStore`; `from src.core.workspace import
  Workspace` — expostos.
- `BorderRegion.bounds["x"|"y"|"z"] -> (min, max)` — forma consumida pelo
  `BorderPlugin` da Fase 2, batendo 1:1.
- **Nota de forward-compat para a Fase 2**: `Metric.value` (union estrito) aceita
  `dict[str, Any]` mas, por ser `Strict()`, um `dict` com CHAVES `int` é rejeitado
  (chave JSON tem de ser string). Se um plugin quiser guardar
  `dict[frame_index:int, valor]` como métrica (ex. `speed_by_frame`), converter as
  chaves para `str` ou usar `list` indexada por frame. Não é bug do schema (JSON
  não tem chave inteira); é só um ponto a lembrar ao portar `speedModule`.

Decisões pendentes que só o dono confirma: as 3 listadas acima (a/b/c). A
divergência histórica de forma do `BorderRegion` (6 floats planos vs
`threshold_px`+`bounds`) JÁ foi reconciliada no plano — foi implementada a forma
`threshold_px`+`bounds` (alinhada a `ARCHITECTURE.md`), sem pendência.
