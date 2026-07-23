# Handoff: Fase 0 — pacote + CI

Status: done
Última atualização: 2026-07-23

Cobre os dois workstreams da Fase 0 (A "pacote" T1-T8, B "CI" T9), executados juntos
neste worktree. `ARCHITECTURE.md` seção "Fase 0" + `docs/plans/fase0-detalhado.md` são a
spec autoritativa; este handoff registra o que foi de fato feito e os desvios necessários.

## O que foi feito

Arquivos criados/alterados:
- `pyproject.toml` (novo) — PEP 621, pacote `animaltrack` 0.1.0, `requires-python >=3.11`.
  - `[project.dependencies]` (item (a) da nota de handoff do plano): exatamente
    `numpy==1.26.3`, `opencv-python==4.9.0.80`, `pillow==10.2.0`, `pydantic>=2,<3`,
    `typer>=0.9`, `matplotlib>=3.8`, `xhtml2pdf>=0.2.13`, `pandas>=2.1`.
    `pillow` incluído como correção pontual (R4 — usado em 4 arquivos, faltava no
    ARCHITECTURE.md; sinalizar na próxima revisão do documento). `six`/`setuptools`/`wheel`
    NÃO entram (não importados; setuptools/wheel já em `[build-system]`).
  - `dev = ["pytest>=8", "ruff>=0.4", "mypy>=1.8"]`.
  - `[tool.setuptools.packages.find]`: `where=["."]`, `include=["src","src.*"]`,
    `exclude=[tests..., MetadataModule...]`. **SEM `package-dir` remap** — é a mitigação
    do R1 (o prefixo literal `src.` precisa sobreviver; um src-layout clássico quebraria
    todo import silenciosamente).
  - Config ruff/mypy/pytest no mesmo arquivo (ver desvios abaixo).
  - **Sem `[project.scripts]`** — CLI `animaltrack` é Fase 4; apontar pra `src/app/cli.py`
    inexistente quebraria a instalação.
- `src/**/__init__.py` (9 novos marcadores, T2) — comentário único, zero lógica. NÃO foi
  criado `__init__.py` em `MetadataModule/` da raiz (R2 — dir escaneado dinamicamente em
  runtime, tem de continuar fora do empacotamento).
- `tests/test_smoke.py` (novo, T4) — import de `jsonUtils` (leaf, só json/os) + checagem de
  `importlib.metadata.version("animaltrack")`. Não instancia `tk.Tk()` (R7).
- `.github/workflows/ci.yml` (novo, T9) — checkout, setup-python 3.11, `pip install -e ".[dev]"`,
  `ruff check .`, `mypy src tests`, `pytest`.
- `.gitignore` — adicionado `.ruff_cache/` (T8).
- `requirements.txt` — **removido via `git rm`** (T3, item (d): opção "remover", não stub;
  nada no repo o referenciava).
- `__init__.py` (raiz, launcher) — removido `import ctypes` (genuinamente não usado) e
  ordenado o import restante (auto-fix ruff, behavior-preserving). Único arquivo legado
  tocado; será substituído por launcher fino na Fase 4 de qualquer forma.

Decisões / desvios em relação à spec (todos justificados, nenhum de arquitetura):
- **ruff `extend-exclude = ["src/Modules", "MetadataModule"]`** (item (c)). `ruff check .`
  a frio = **72 violações**, todas em código legado nunca lintado (E501/I001/F541/F401/F841/
  E722/B905/E711/F632/UP015/B007). Seguindo a regra do T6 para contagem grande: excluir os
  dirs legados com TODO de remover conforme Fases 3-4 os reescrevem, mantendo lint ativo em
  `tests/` e código novo (src/core, src/stages, src/app). O resíduo após a exclusão era só o
  launcher raiz (2 issues triviais) → auto-fix seguro (ramo "contagem pequena" do T6).
- **mypy `explicit_package_bases=true` + `mypy_path="."`** e **CI usa `mypy src tests`, não
  `mypy .`**. Motivo: o `__init__.py` do launcher na raiz + nome de diretório com hífen
  (`Tcc-comportamento-abelhas`) fazem o mypy tentar tratar a raiz como um pacote de nome
  inválido e abortar (`... is not a valid Python package name`) — quebraria também no CI.
  `mypy src tests` é o fallback explicitamente previsto no plano (verificação passo 4). O
  override `ignore_errors` para `src.Modules.*` do T7 foi mantido como está.

## O que falta

Nada nesta fase. Fase 0 concluída e verificada. Próximo: Fase 1 (schema + workspace + store).

Itens de acompanhamento (não bloqueiam a Fase 0, registrar na próxima revisão):
- Confirmar com o dono do projeto a inclusão de `pillow` na lista de deps (R4) e refletir no
  `ARCHITECTURE.md`.
- Remover progressivamente as entradas de `extend-exclude` do ruff e o override
  `ignore_errors` do mypy conforme cada módulo de `src/Modules/**` é reescrito (Fases 3-4).

## Como verificar o que já foi feito

Ambiente-alvo: Python 3.11 (o que o CI usa). Comandos, da raiz do repo:
- `pip install -e ".[dev]"` → exit 0; `pip show animaltrack` lista o pacote editável.
- `pytest` → `2 passed`.
- `ruff check .` → `All checks passed!`.
- `mypy src tests` → `Success: no issues found in N source files`.
- `python __init__.py` → abre a janela da GUI sem `ModuleNotFoundError` (prova do R1).

Nota de ambiente (item (b), resultado real desta execução): a máquina local só tem Python
**3.13**, para o qual `numpy==1.26.3`/`opencv-python==4.9.0.80` não têm wheel (build from
source falha sem MSVC) — então `pip install -e ".[dev]"` com os pins **falha em 3.13** e
funciona em 3.11/CI. Verificação local foi feita instalando `-e . --no-deps` (editable OK) +
versões substitutas compatíveis com 3.13 (numpy 2.5.1, opencv 5.0.0.93, pillow 12.3.0, +
demais). Resultados obtidos localmente assim: `pytest` 2 passed; `ruff check .` clean;
`mypy src tests` Success (32 arquivos, com `--python-version 3.13` para contornar um erro de
sintaxe nos stubs da numpy 2.5 sob target 3.11 — artefato exclusivo do substituto, ausente
com numpy 1.26.3 no CI); `python __init__.py` abriu a GUI sem erro de import (R1 confirmado,
com a janela real e via wrapper que constrói `show_main_ui()` e a destrói).

## Como retomar

Fase 0 está fechada. Para começar a Fase 1, ler `docs/handoffs/PROGRESS.md`, depois
`ARCHITECTURE.md` (seção "Fase 1") e `docs/plans/fase1-detalhado.md`. Criar
`src/core/schema/{geometry,detection,track,route,result,orientation}.py`,
`src/core/workspace.py`, `src/core/store.py`. Ao adicionar esses pacotes novos, eles ficam
sob o lint/type-check ativo (não estão em `extend-exclude`/override) — escrever já tipado.
Decisão pendente que só o dono confirma: aceitar `pillow` na lista oficial de deps do
`ARCHITECTURE.md`.
