# Fase 0 — Ferramental e fundação de pacote (plano detalhado)

> Referência: `ARCHITECTURE.md` (seção "Fase 0"). Este documento é o plano granular e execução-pronto para
> essa fase, com achados verificados no repositório real (não suposições) — inclusive onde eles contradizem
> claims desatualizadas do `CLAUDE.md`.

## 0. Achados de auditoria (base factual deste plano)

Estado real do repositório na data deste plano, confirmado por leitura direta (não por inferência do
`CLAUDE.md`):

- Não existem hoje: `pyproject.toml`, `tests/`, `.github/`, `setup.py`/`setup.cfg`, `mypy.ini`,
  `pytest.ini`, `.ruff.toml`, `docs/` (este documento é o primeiro arquivo em `docs/`).
- `requirements.txt` (135 bytes) é **ASCII/CRLF puro**, não UTF-16 com BOM — a nota do `CLAUDE.md` sobre
  encoding está desatualizada. Conteúdo atual, linha a linha:
  ```
  numpy==1.26.3
  opencv-python==4.9.0.80
  pillow==10.2.0
  setuptools==69.0.3
  six==1.16.0
  wheel==0.42.0
  pandas
  matplotlib
  xhtml2pdf
  ```
  O arquivo já inclui `pandas`/`matplotlib`/`xhtml2pdf` (sem pin de versão) — a nota do `CLAUDE.md` de que
  o arquivo está "incompleto" também está desatualizada.
- **Nenhum `__init__.py` existe em `src/`** (nem `src/__init__.py`, nem em nenhum subdiretório) — busca
  recursiva por `__init__.py` sob `src/` retorna zero resultados. O `__init__.py` da raiz do repo
  (167 bytes) é só o launcher da GUI:
  ```python
  import ctypes
  from src.Modules.InterfaceModule.mainUI import run_loop, show_main_ui
  if __name__ == "__main__":
      screen = show_main_ui()
      run_loop(screen)
  ```
- **Todo import interno do código usa o prefixo literal `src.`** — `from src.Modules.BasicModule...`,
  `from src.utils.interfaceUtils import show_frame`, etc., em praticamente todo arquivo de `src/`
  (`mainUI.py`, `configurationUI.py`, `processVideoModule.py`, `plotRoute.py`, `modulesInvoker.py`, e mais).
  Hoje isso funciona porque `src` é tratado como pacote-namespace implícito (PEP 420) quando o app roda com
  `python __init__.py` a partir da raiz do repo (raiz entra no `sys.path`).
- `PIL` (Pillow) é importado de fato em 4 arquivos: `perspectiveUi.py`, `borderUi.py`,
  `recordWebcamController.py`, `recordWebcamVideoUI.py` (`from PIL import Image, ImageTk, ...`) —
  dependência de runtime real, **ausente** da lista de deps do Fase 0 no `ARCHITECTURE.md` (que cita só
  numpy/opencv-python/pydantic/typer/matplotlib/xhtml2pdf/pandas).
- `six`, `setuptools`, `wheel` (hoje pinados em `requirements.txt`) **não são importados em nenhum lugar do
  código-fonte** (grep de `^import |^from ` em `src/` e `MetadataModule/` não encontra nenhum) — sobra
  provável de um `pip freeze` antigo.
- `MetadataModule/` na raiz (só `borderModule.py` + `speedModule.py`, sem `__init__.py`) é o diretório
  escaneado dinamicamente via `importlib` em runtime por
  `src/Modules/MetadataModule/modulesInvoker.py::execute_metadata_module_calls` (ver `CLAUDE.md`, seção
  "Metadata module system") — **não deve virar pacote instalável, não deve ganhar `__init__.py`, não deve
  ser movido/renomeado** nesta fase (nem em nenhuma até a Fase 2/3 refatorá-lo explicitamente, per tabela de
  migração do `ARCHITECTURE.md`).
- `.gitignore` já cobre `.mypy_cache/`, `.pytest_cache/`, `.venv`/`venv/`, `venv.bak/`, `build/`, `dist/`,
  `.eggs/`, `*.egg-info/`; **falta** `.ruff_cache/`.
- `README.md` não referencia `requirements.txt` em nenhum lugar (sem instrução de instalação a atualizar
  por causa da aposentadoria do arquivo).
- `LICENSE`: MIT, Walter Dalla Torre Neto, 2024 — usar em `[project.license]`.

## 1. Lista ordenada de tarefas

**T1 — Criar `pyproject.toml` (raiz do repo)**

- `[build-system]`:
  ```toml
  [build-system]
  requires = ["setuptools>=68", "wheel"]
  build-backend = "setuptools.build_meta"
  ```
- `[project]`:
  ```toml
  [project]
  name = "animaltrack"
  version = "0.1.0"
  requires-python = ">=3.11"
  readme = "README.md"
  license = { file = "LICENSE" }
  authors = [{ name = "Walter Dalla Torre Neto" }]
  dependencies = [
      "numpy==1.26.3",
      "opencv-python==4.9.0.80",
      "pillow==10.2.0",
      "pydantic>=2,<3",
      "typer>=0.9",
      "matplotlib>=3.8",
      "xhtml2pdf>=0.2.13",
      "pandas>=2.1",
  ]

  [project.optional-dependencies]
  dev = ["pytest>=8", "ruff>=0.4", "mypy>=1.8"]
  ```
  Notas de decisão:
  - `name = "animaltrack"`: nome já fixado pelo `ARCHITECTURE.md` para o futuro CLI (Fase 4, `animaltrack
    run ...`) — adotar agora evita rename de pacote mais tarde.
  - `pillow==10.2.0` **incluído mesmo não estando na lista de deps do `ARCHITECTURE.md`** — é dependência
    de runtime real hoje (ver achado acima); omitir quebraria a GUI. Tratar como correção pontual à lista
    do `ARCHITECTURE.md`, não como decisão unilateral de arquitetura — vale confirmar com o dono do projeto
    na próxima revisão do documento.
  - `six`, `setuptools`, `wheel` **não entram** em `dependencies` (não são importados; `setuptools`/`wheel`
    já cobertos em `[build-system]`).
  - **Não adicionar `[project.scripts]` ainda** — o CLI `animaltrack` é escopo da Fase 4;
    `src/app/cli.py` não existe nesta fase, então um entry point apontando pra lá quebraria a instalação.
- `[tool.setuptools.packages.find]` — **decisão crítica, ver Risco R1 abaixo**:
  ```toml
  [tool.setuptools.packages.find]
  where = ["."]
  include = ["src", "src.*"]
  exclude = ["tests", "tests.*", "MetadataModule", "MetadataModule.*"]
  ```
  Sem `[tool.setuptools.package-dir]` (o default `"" -> "."` é o correto aqui — ver Risco R1 para o porquê
  de **não** usar o mapeamento clássico de "src layout").
- `[tool.pytest.ini_options]`:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  addopts = "-ra"
  ```
- `[tool.ruff]` e `[tool.mypy]`: especificados em T6/T7 abaixo (mesmo arquivo `pyproject.toml`, seções
  adicionais).

**T2 — Criar marcadores de pacote `__init__.py` (vazios) em `src/`**

Arquivos novos, cada um vazio ou com um único comentário (`# marcador de pacote — packaging Fase 0, sem
lógica`):
- `src/__init__.py`
- `src/Modules/__init__.py`
- `src/Modules/BasicModule/__init__.py`
- `src/Modules/BasicModule/utils/__init__.py`
- `src/Modules/ExportModule/__init__.py`
- `src/Modules/InterfaceModule/__init__.py`
- `src/Modules/InterfaceModule/recodWebCamVideo/__init__.py`
- `src/Modules/MetadataModule/__init__.py`
- `src/utils/__init__.py`

Motivo: `packages.find` em modo não-namespace precisa de `__init__.py` por diretório para reconhecer
subpacotes de forma confiável entre versões do setuptools. Zero mudança de comportamento: esses diretórios
já se comportam como pacotes hoje (namespace implícito PEP 420); isso só torna explícito o que já
acontecia. **Não** adicionar `__init__.py` em `MetadataModule/` (raiz) — fica de fora de propósito
(Risco R2).

**T3 — Aposentar `requirements.txt`**

Recomendação primária: `git rm requirements.txt` — nada no repo o referencia (`README.md` confirmado sem
menção a `pip install -r requirements.txt`). Alternativa, caso se prefira manter rastro histórico:
substituir o conteúdo por uma única linha (`# Dependências migradas para pyproject.toml — ver
[project.dependencies]`). Registrar no commit qual das duas opções foi tomada.

**T4 — Criar `tests/test_smoke.py`**

Sem `tests/__init__.py` (não necessário para descoberta do pytest). Conteúdo do smoke test:
- Importa um módulo folha sem efeito colateral pesado no import, por exemplo:
  ```python
  from src.Modules.ExportModule.jsonUtils import export_data_to_file, import_data_from_file

  def test_json_utils_importable():
      assert callable(export_data_to_file)
      assert callable(import_data_from_file)
  ```
- Confirma que o pacote instalado responde por metadado:
  ```python
  import importlib.metadata

  def test_package_metadata():
      assert importlib.metadata.version("animaltrack")
  ```
- **Não** instanciar `tk.Tk()` nem abrir vídeo/webcam real (Risco R7) — o runner de CI roda sem display
  gráfico.

**T5 — `[tool.pytest.ini_options]`**

Já descrito em T1 — mesma edição de `pyproject.toml`, listado aqui só por completude do range de seções
tocadas nesse arquivo.

**T6 — `[tool.ruff]` em `pyproject.toml`**

```toml
[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```
- `line-length = 120`: código legado tem linhas longas de Tk/OpenCV.
- Ruleset propositalmente enxuto (pyflakes + pycodestyle erros + isort + pyupgrade + bugbear básico) para
  não inundar a Fase 0 de achados de estilo em código nunca lintado antes.
- **Decisão a confirmar durante a execução, com dado real na mão** (não é possível saber a contagem de
  violações sem rodar `ruff` de fato, o que está fora do escopo deste documento de planejamento): rodar
  `ruff check .` logo após configurar; se a contagem de violações for pequena (dezenas), aplicar
  `ruff check --fix` (auto-fix é comportamento-preservando: imports não usados, espaçamento); se for
  grande, adicionar `extend-exclude` temporário para os diretórios legados (`src/Modules/**`) com um TODO
  explícito de remover ao longo das Fases 3–4 (quando esses módulos são reescritos), e aplicar o lint só em
  `tests/` e arquivos novos por ora.

**T7 — `[tool.mypy]` em `pyproject.toml`**

Código legado não tem nenhuma anotação de tipo hoje. Config inicial deliberadamente permissiva, para não
transformar a Fase 0 em retrofit de tipos (isso é papel das Fases 1+, quando o código é reescrito em
`src/core`/`src/stages`/`src/app`):
```toml
[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["src.Modules.*"]
ignore_errors = true
```
Isso deixa `mypy .` (ou `mypy src tests`) checando de verdade só `tests/` (e qualquer coisa nova fora de
`src.Modules.*`); a exclusão de `src.Modules.*` é removida fase a fase à medida que cada módulo legado é
reescrito/tipado, nunca retirada de uma vez.

**T8 — Atualizar `.gitignore`**

Adicionar a entrada `.ruff_cache/` (única lacuna encontrada; `.mypy_cache/`, `.pytest_cache/`, `venv/`,
`build/`, `dist/`, `*.egg-info/` já estão cobertos).

**T9 — Criar `.github/workflows/ci.yml`**

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: mypy .
      - run: pytest
```
`ubuntu-latest` sem servidor gráfico é seguro aqui porque T4 explicitamente não instancia um `tk.Tk()` real
(Risco R7); se uma fase futura adicionar smoke test de GUI de verdade, será necessário Xvfb — fora do
escopo da Fase 0.

## 2. Paralelização

Conforme `ARCHITECTURE.md` (tabela "Paralelização por fase", linha da Fase 0) — já descontando
`ARCHITECTURE.md` da lista de deliverables paralelizáveis, porque o documento já existe (foi criado antes
deste plano): restam **2 workstreams paralelizáveis desde já, sem esperar nenhuma interface**:

- **Workstream A — "pacote"**: T1 (`pyproject.toml`), T2 (marcadores `__init__.py`), T3 (aposentar
  `requirements.txt`), T4 (`tests/test_smoke.py`), T5/T6/T7 (seções pytest/ruff/mypy do mesmo
  `pyproject.toml` de T1), T8 (`.gitignore`).
- **Workstream B — "CI"**: T9 (`.github/workflows/ci.yml`).

**Por que dá para paralelizar**: os conjuntos de arquivos tocados são disjuntos — A nunca toca `.github/`;
B só toca `.github/workflows/ci.yml`. O "contrato" do qual B depende (quais comandos rodar —
`pip install -e ".[dev]"`, `ruff check .`, `mypy .`, `pytest`; nome do pacote `animaltrack`; nome do extra
`dev`) já está fixado por este próprio plano (e pelo `ARCHITECTURE.md`), não pela implementação real de A —
isso é exatamente o caso de "workstream que não depende de tipo/contrato definido em outro lugar" que a
regra geral de paralelização do `ARCHITECTURE.md` exige antes de liberar paralelismo. B pode escrever o
workflow especulativamente usando os nomes já decididos aqui.

**Sequencial obrigatório**: um passo curto de integração **depois** que A e B terminam — conferir que
`ci.yml` (B) bate de fato com os nomes finais escolhidos em `pyproject.toml` (A), caso T6/T7 tenham mudado
de plano durante a execução (por exemplo, se o ruleset de ruff precisou de `extend-exclude` que muda o
comando). É revisão, não codificação nova; só depois disso a Fase 0 é considerada concluída e o handoff
consolidado é escrito em `docs/handoffs/PROGRESS.md`.

## 3. Riscos específicos deste repositório

**R1 (crítico) — colisão de prefixo de import: "`src`" é namespace literal em uso, não só convenção de
layout.** Todo import interno hoje é `from src.Modules...` / `from src.utils...`. Se o packaging usar o
mapeamento clássico de "src layout" (`[tool.setuptools] package-dir = {"" = "src"}`), o `pip install -e .`
**parece** funcionar (instala sem erro) mas **todo import existente quebra em runtime**
(`ModuleNotFoundError: No module named 'src'`), porque o pacote instalado passaria a se chamar `Modules`,
não `src.Modules` — o prefixo `src.` desapareceria do caminho de import exatamente como o layout clássico
pretende (isso é intencional na convenção padrão, só que aqui o código já depende do prefixo ficar). Isso
violaria diretamente o "sem mudança de comportamento" que define a Fase 0, e **não seria pego pelos testes
automatizados** — só rodando o app de verdade (`python __init__.py`). Mitigação já embutida em T1: usar
`packages.find` com `where=["."]`, `include=["src","src.*"]`, **sem** `package-dir`; T2 adiciona
`__init__.py` reais para tornar isso robusto entre versões do setuptools. **Verificação manual
obrigatória**, não substituível por `pytest`: depois de `pip install -e .`, rodar `python __init__.py` e
confirmar que a janela da GUI abre sem erro de import.

**R2 — `MetadataModule/` (raiz) não pode virar pacote nem ser tocado.** É o diretório escaneado
dinamicamente por `importlib` em runtime (`src/Modules/MetadataModule/modulesInvoker.py`), quirk
documentada em `CLAUDE.md`. T1 exclui explicitamente (`exclude = ["MetadataModule", "MetadataModule.*"]`)
por segurança, mesmo sem `__init__.py` lá hoje — protege contra descoberta acidental futura se alguém ligar
modo namespace no `packages.find` ou adicionar `__init__.py` lá por engano em fase posterior.

**R3 — claims desatualizadas do `CLAUDE.md` sobre `requirements.txt`.** O arquivo hoje é ASCII/CRLF puro
(não UTF-16 com BOM como o `CLAUDE.md` descreve) e já lista `pandas`/`matplotlib`/`xhtml2pdf` (sem pin) —
a segunda claim do `CLAUDE.md` ("incompleto") também está desatualizada. Não confiar cegamente na
descrição do `CLAUDE.md` ao migrar valores; os valores reais a levar para `pyproject.toml` são os
verificados na seção 0 deste documento (leitura direta do arquivo).

**R4 — Pillow ausente da lista de deps do `ARCHITECTURE.md`, mas usado de verdade.** 4 arquivos
(`perspectiveUi.py`, `borderUi.py`, `recordWebcamController.py`, `recordWebcamVideoUI.py`) importam `PIL`
diretamente. Omitir `pillow` do `pyproject.toml` quebraria a GUI por omissão, violando "sem mudança de
comportamento" da Fase 0. T1 inclui `pillow==10.2.0` como correção pontual à lista do `ARCHITECTURE.md` —
vale avisar o dono do projeto de que isso é um acréscimo factual, não uma decisão unilateral de
arquitetura, e sinalizar isso na próxima revisão do `ARCHITECTURE.md`.

**R5 — zero `__init__.py` em `src/` hoje.** T2 é a única tarefa desta fase que cria arquivos fora de
`pyproject.toml`/`tests/`/CI/`.gitignore`/`requirements.txt`. Risco individual baixo (arquivo vazio), mas
por estar diretamente acoplado ao Risco R1, T2 deve terminar com a mesma checagem manual
(`python __init__.py`) e não só com testes automatizados.

**R6 — lint/type-check "a frio" em código legado nunca lintado/tipado.** Não é possível saber a contagem
real de violações de `ruff`/`mypy` sem rodar as ferramentas de fato — fora do escopo deste documento, que
é produto de uma etapa somente-leitura. T6/T7 documentam a regra de decisão (auto-fix se poucas violações;
`extend-exclude`/`ignore_errors` temporário se muitas) para quem executar a fase resolver com dado real em
mãos, em vez de adivinhar aqui um número.

**R7 — CI sem display gráfico.** `ubuntu-latest` não tem servidor Tk/X11. `tests/test_smoke.py` não pode
instanciar `tk.Tk()` real nem abrir vídeo/webcam de verdade — só checagens de import/metadado (ver T4).

**R8 — `docs/plans/` e `docs/handoffs/` não existiam antes deste documento.** Este plano já criou
`docs/plans/` (continha só este arquivo até agora). O primeiro subagente a escrever um handoff da Fase 0
ainda precisa criar `docs/handoffs/` (não existe até este ponto).

## 4. Passos de verificação (comandos exatos)

1. `pip install -e ".[dev]"` — sucesso = exit code 0; `pip show animaltrack` lista o pacote instalado em
   modo editável.
   - Checagem manual adicional (não é um dos 4 comandos formais pedidos pelo `ARCHITECTURE.md`, mas cobre
     diretamente o Risco R1 e é obrigatória antes de considerar T1/T2 concluídas): `python __init__.py`
     deve abrir a janela da GUI normalmente, sem `ModuleNotFoundError`.
2. `pytest` — sucesso = todos os testes coletados (incluindo `tests/test_smoke.py`) passam, 0 falhas/erros.
3. `ruff check .` — sucesso = saída `All checks passed!`, dado o ruleset/excludes finalizado em T6.
4. `mypy .` (ou `mypy src tests`, se `.` pegar diretórios indesejados como `.venv`) — sucesso =
   `Success: no issues found in N source files`, dado o override de T7 que ignora `src.Modules.*` por ora.
5. CI (`.github/workflows/ci.yml`) — sucesso = job verde no GitHub Actions, rodando os mesmos 4 comandos
   acima em push/PR para `main`.

"Comportamento de runtime não tocado" (exigência explícita da Fase 0 no `ARCHITECTURE.md`) é considerado
verificado apenas quando o passo 1 (incluindo a checagem manual do `python __init__.py`) passa — os passos
2–5 verificam ferramental, não comportamento do app.

## 5. Nota de prontidão para handoff

O trabalho de codificação real desta fase será feito por subagente(s) seguindo o protocolo de handoff
descrito em `ARCHITECTURE.md` ("Execução: subagentes paralelos e handoff"). Se esse agente futuro ficar
com o orçamento de contexto/token baixo no meio da fase, o **primeiro checkpoint de handoff** deve ser
logo após:

- Workstream A ter `pyproject.toml` (T1) + marcadores `__init__.py` (T2) no lugar, **e**
- `pip install -e .` + `python __init__.py` (smoke manual) terem sido confirmados verdes —

ou seja, assim que o Risco R1 (o item de maior risco da fase, o único capaz de quebrar a GUI silenciosamente
sem pytest detectar) estiver provadamente resolvido. Tudo depois disso — afinar ruleset de ruff/mypy (T6/
T7), aposentar `requirements.txt` (T3), escrever `tests/test_smoke.py` (T4), escrever CI (T9) — é mecânico
e independentemente retomável por um agente novo lendo o `pyproject.toml` já commitado como fonte da
verdade, sem precisar re-explorar o raciocínio do R1 do zero.

O arquivo de handoff nesse ponto (`docs/handoffs/fase0-pacote-handoff.md`, formato definido em
`ARCHITECTURE.md`) deve registrar no mínimo:
- (a) lista exata de dependências/versões escolhidas em `[project.dependencies]`;
- (b) confirmação explícita de que os imports `from src.Modules...` seguem resolvendo pós-instalação
  (resultado do `python __init__.py`, não só do `pytest`);
- (c) contagem de violações do primeiro `ruff check .`/`mypy .` rodado a frio, e a decisão de escopo
  tomada a partir disso (Risco R6) — auto-fix vs. exclude temporário;
- (d) qual destino foi dado ao `requirements.txt` (removido via `git rm` vs. substituído por stub — T3).
