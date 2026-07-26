# Contrato público de plugin — `plugin.toml`

Documento para **autores de plugin de terceiros**. Descreve o formato do manifest,
o que cada `kind` exige, e as regras de instalação/descoberta.

Para o contexto arquitetural interno (decisões, fases, motivação), veja
[`../ARCHITECTURE.md`](../ARCHITECTURE.md). Este documento é a referência do
*contrato*; o `ARCHITECTURE.md` é a referência do *sistema*.

---

> # ⚠️ Aviso de segurança e confiança — leia antes de instalar qualquer plugin
>
> **Não existe sandboxing.** Um plugin instalado roda com **privilégio total do
> processo host**: ele pode ler e escrever qualquer arquivo que o usuário possa,
> abrir rede, e executar qualquer código Python.
>
> **Não há verificação automática de segurança.** A validação feita na instalação é
> de *formato de manifest*, não de intenção do código. Instalar um plugin equivale
> a rodar um script arbitrário que outra pessoa escreveu.
>
> A curadoria é **manual e humana** (modelo "git-tap curado"): não existe registro,
> índice, nem revisão automatizada. **Só instale plugins de fonte que você confia**,
> e leia o código antes.

---

## 1. Campos obrigatórios do `plugin.toml`

Todo plugin é um diretório contendo um `plugin.toml` e o módulo de entrada.

```toml
[plugin]
name        = "fish-body-fat-estimator"
version     = "0.1.0"
kind        = "metadata"
entry       = "plugin:FishBodyFatEstimator"
api_version = "1.0"
schema      = ">=1.0,<2.0"
```

| Campo | Tipo | Regra de validação |
|---|---|---|
| `name` | string | Identificador único do plugin. Convenção **kebab-case** (`meu-plugin`). É o nome usado na instalação, em `[ordering]` e em `plugin remove`. |
| `version` | string | Versão **do plugin em si**, semver (`MAJOR.MINOR.PATCH`). Informativo — o core não a usa para decidir compatibilidade. |
| `kind` | enum fechado | Um de: `capture`, `rectify`, `detector`, `tracker`, `fusion`, `metadata`, `exporter`, `interface`. Valor fora da lista → manifest rejeitado. |
| `entry` | string | Formato `modulo:Classe` (ex. `plugin:MinhaClasse`). O módulo é resolvido **relativo ao diretório do plugin**; a classe precisa ser subclasse da base do `kind` (tabela na seção 6). |
| `api_version` | string | Versão da **API de plugin do core** que este plugin fala. Atualmente suportada: `1.0`. Valor não suportado → plugin rejeitado. |
| `schema` | range PEP 440 | Faixa de `SCHEMA_VERSION` do `AnalysisResult` aceita (ex. `">=1.0,<2.0"`). Fora da faixa do core instalado → plugin rejeitado. |

Campos desconhecidos em `[plugin]` são **rejeitados** (`extra="forbid"`), para que
um erro de digitação falhe cedo em vez de ser ignorado em silêncio.

## 2. `[requires]` — dependências

```toml
[requires]
python   = ">=3.11"          # specifier PEP 440
packages = ["numpy>=1.26"]   # requisitos PEP 508
plugins  = ["speed"]         # nomes de outros plugins necessários
```

| Campo | Default | Semântica |
|---|---|---|
| `python` | `">=3.11"` | Versão de Python exigida. |
| `packages` | `[]` | Pacotes PyPI que o plugin importa. **Declarativo**: o core não instala nada por você — se faltar, o import do plugin falha e ele é pulado com log. |
| `plugins` | `[]` | Outros plugins de que este depende para existir. |

**Resolução**: um plugin cujo `requires.plugins` não está presente é **pulado com
log**, não derruba o run dos demais. Mesma política para qualquer falha de import.

### `[config]` — configuração esperada (opcional, documentação + tipo)

```toml
[config]
fish_length_cm = { type = "float", required = false, description = "Comprimento do peixe em cm, usado na fórmula placeholder de gordura corporal." }
```

Cada chave declara um campo que o plugin espera encontrar em
`ctx.request.overrides` (seção 6): `type` (`"str"`/`"int"`/`"float"`/`"bool"`),
`required` (default `false`), `default` e `description`. **Isto é documentação e
checagem de tipo opcional, não uma allowlist nem um gate de execução** — nenhum
override não declarado em `[config]` é rejeitado, e nada em `Pipeline.run`/
`run_cpu_analysis` valida `[config]` automaticamente. Um plugin que quer checar
seus próprios overrides pode chamar, do próprio `setup()`:

```python
errors = self.manifest.validate_overrides(ctx.request.overrides)
if errors:
    log.warning("config inválida: %s", "; ".join(errors))
```

Ver `plugins/metadata/fish-body-fat/plugin.toml` para um exemplo real em uso.

## 3. `[ordering]` — ordem de execução

```toml
[ordering]
before   = []
after    = ["speed"]
priority = 200
```

- `before` / `after` referenciam o **`name`** de outros plugins **do mesmo `kind`**.
  Referência a um nome não descoberto é **ignorada com warning** (não é fatal).
- `priority`: inteiro, default `0`. **Número maior roda mais cedo.**
- **Desempate**: quando não há relação `before`/`after` explícita, a ordem é
  `(-priority, name)` — ou seja, maior prioridade primeiro, empate resolvido em
  **ordem alfabética do `name`** (determinístico entre execuções).
- Um ciclo em `before`/`after` é **erro fatal de configuração** (`PluginOrderingCycleError`)
  — ao contrário de falhas de plugin individuais, ele derruba o run inteiro, porque
  não existe ordem correta a escolher.

## 4. Convenção de diretório

O `plugin.toml` fica **sempre ao lado** do módulo de entrada:

```
meu-plugin/
├── plugin.toml
├── plugin.py          # entry = "plugin:MinhaClasse"
└── README.md          # opcional, recomendado
```

Plugin multi-arquivo é um pacote Python normal dentro da pasta; `entry` aponta para
o módulo público:

```
meu-plugin/
├── plugin.toml        # entry = "plugin:MinhaClasse"
├── plugin.py          # importa de _interno/
└── _interno/
    ├── __init__.py
    └── algoritmo.py
```

> **Descoberta varre UM nível.** O registry procura `<raiz_de_busca>/<pasta>/plugin.toml`.
> Um plugin em `<raiz>/grupo/meu-plugin/plugin.toml` **não** é encontrado ao varrer
> `<raiz>` — a pasta de agrupamento precisa ser registrada como raiz de busca própria
> (é o que `src/app/plugins.py` faz com `plugins/tracker/` e `plugins/metadata/`).

**Raízes de busca padrão**, na ordem:

1. `plugins/` (repo) — plugins `metadata` built-in
2. `src/stages/export/` (repo) — plugins `exporter` built-in
3. `plugins/tracker/`, `plugins/metadata/` (repo) — plugins de exemplo/spike
4. `<workspace>/plugins/` — **onde `animaltrack plugin install` escreve**

Em caso de nome duplicado, **o primeiro descoberto vence** e os seguintes são
pulados com warning.

## 5. Versionamento — três coisas diferentes

| Campo | O que versiona | Quando um autor mexe |
|---|---|---|
| `version` | O plugin em si | A cada release do seu plugin. Semver comum. Não afeta compatibilidade. |
| `api_version` | O contrato do **core** (classes-base, assinaturas) | Só quando o core sobe. Bump **maior** = plugins com a versão antiga passam a ser **rejeitados** pelo registry. |
| `schema` | A faixa de `AnalysisResult`/schema de dados aceita | Ao verificar que seu plugin funciona com um novo schema, amplie a faixa. Bump maior do schema é quebra de contrato de dados. |

Regra prática para o autor: **ao atualizar seu plugin**, suba `version`. Só mexa em
`api_version`/`schema` quando testar contra uma versão nova do core e confirmar que
funciona.

## 6. Classe-base por `kind`

O `entry` precisa apontar para uma subclasse da base correspondente, senão a
instalação/carga é rejeitada.

| `kind` | Classe-base | Métodos que você implementa |
|---|---|---|
| `detector` | `src.core.stages.Detector` | `detect(frame: RectifiedFrame) -> FrameDetections` |
| `tracker` | `src.core.stages.Tracker` | `update(dets: FrameDetections) -> None`, `tracks() -> list[Track]`, `reset() -> None` (opcional) |
| `metadata` | `src.core.stages.MetadataPlugin` | `run(ctx: AnalysisContext) -> None` — muta `ctx` via `add_metric()`, sem retorno |
| `capture`, `rectify`, `fusion`, `exporter`, `interface` | `src.core.plugin.Plugin` | Ainda sem base específica; exigem apenas `Plugin`. |

Todo plugin herda de `Plugin` e ganha dois hooks opcionais:

```python
def setup(self, ctx: PipelineContext) -> None: ...   # antes da execução
def teardown(self) -> None: ...                      # depois, sempre que setup passou
```

> **Restrição importante: o construtor precisa aceitar zero argumentos.**
> O registry instancia com `plugin_cls()`. Se seu plugin precisa de parâmetros
> (ex. um `tracker` por view), dê **default** a todos eles e permita configuração
> por `setup()`. Configuração vinda do usuário chega em `ctx.request.overrides`
> (`dict[str, Any]`) — veja `plugins/metadata/fish-body-fat/` como exemplo.

## 7. Isolamento de erro

O contrato garante que **um plugin quebrado não derruba o run**:

| Onde falha | O que acontece |
|---|---|
| Manifest inválido (descoberta) | Plugin pulado, warning logado, descoberta continua. |
| Import do `entry` / `api_version` / `schema` incompatível | Plugin pulado, warning com o tipo da exceção, demais plugins do mesmo kind seguem. |
| `setup()` levanta | Falha registrada; `run()` e `teardown()` **não** rodam para esse plugin. |
| `run()` levanta | Falha registrada; `teardown()` **ainda roda** (try/finally); próximo plugin segue. |
| `teardown()` levanta | Falha registrada; run continua. |
| Ciclo em `[ordering]` | **Fatal** — propaga e derruba o run (não há ordem válida). |

Cada falha isolada vira um `PluginFailure` (kind, name, stage, tipo de erro,
mensagem, traceback) na lista `RunResult.plugin_failures`. O log estruturado sai
em nível `ERROR` com o nome do plugin e o estágio.

**Recomendação ao autor**: prefira **pular com log** a levantar exceção quando um
insumo opcional falta (ex. uma métrica que outro plugin não produziu). Acesso
defensivo via `ctx.get_metric(...) is None` é o padrão esperado.

## 8. Esqueleto mínimo copy-paste

`meu-plugin/plugin.toml`:

```toml
[plugin]
name        = "meu-plugin"
version     = "0.1.0"
kind        = "metadata"
entry       = "plugin:MeuPlugin"
api_version = "1.0"
schema      = ">=1.0,<2.0"

[requires]
python   = ">=3.11"
packages = []
plugins  = []

[ordering]
before   = []
after    = ["speed"]
priority = 100
```

`meu-plugin/plugin.py`:

```python
import logging

from src.core.schema.result import AnalysisContext, Metric
from src.core.stages import MetadataPlugin

log = logging.getLogger("animaltrack.plugin.meu-plugin")


class MeuPlugin(MetadataPlugin):
    def run(self, ctx: AnalysisContext) -> None:
        entrada = ctx.get_metric("average_speed")
        if entrada is None:
            log.warning("meu-plugin: 'average_speed' ausente, pulando.")
            return  # acesso defensivo: pula, não levanta

        ctx.add_metric(
            Metric(
                name="minha_metrica",
                value=float(entrada.value) * 2.0,
                unit="cm/s",
                producer="meu-plugin",
            )
        )
```

Instale e confirme:

```bash
animaltrack plugin install ./meu-plugin
animaltrack plugin list
```

> `Metric.value` aceita apenas valores seguros para JSON: `str`, `int`, `float`,
> `bool`, `None`, `list` ou `dict`. Um `numpy.ndarray` (ou objeto arbitrário) é
> **rejeitado na construção do `Metric`** — falha cedo, no seu código, em vez de
> quebrar obscuramente na serialização.

## 9. Instalação — `animaltrack plugin`

```bash
animaltrack plugin install <path|git-url> [--workspace DIR] [--force]
animaltrack plugin list [--workspace DIR]
animaltrack plugin remove <name> [--workspace DIR] [--yes]
```

**Não existe backend de marketplace.** Não há índice nem servidor que resolva
*nome → pacote*: `install` sempre recebe um **path local ou URL git literal** que
você fornece. "Marketplace" aqui é o formato de contrato + curadoria manual.

Fluxo do `install`:

1. **Detecta a origem** — se o argumento é um diretório existente, é instalação
   local; senão, é tratado como URL git.
2. **Staging** — o conteúdo é **copiado** (nunca symlink) ou clonado
   (`git clone --depth 1`) para um diretório temporário. A validação acontece
   **sempre no staging**, nunca no destino final.
3. **Metadados `.git` são removidos** — a instalação é um *snapshot pontual*, não
   um rastreamento de upstream. Não há auto-update.
4. **Valida o manifest** — existência e parse do `plugin.toml`, campos obrigatórios,
   `kind` no enum, `entry` resolve e a classe é subclasse da base correta,
   `api_version`/`schema` compatíveis com o core instalado.
5. **Se qualquer verificação falhar** → aborta imprimindo **todas** as falhas
   encontradas (não só a primeira), descarta o staging, e **nada é escrito** em
   `<workspace>/plugins/`.
6. **O nome final vem do manifest** (`[plugin].name`) — não do nome da pasta nem
   da URL.
7. **Colisão de nome** → recusa por padrão, mostrando versão instalada vs. versão
   nova, e sugere `--force`. Com `--force`, o diretório existente é substituído
   inteiro. *Não há aliasing*: instalar duas versões lado a lado está fora de
   escopo por ora.

**Exit codes** (pensados para script/CI): sucesso → `0`, imprime nome e versão
instalada; falha de validação ou colisão sem `--force` → `≠0`, com a lista de
erros em `stderr`.

## 10. Histórico do contrato

| Fase | O que mudou no contrato |
|---|---|
| **2** | Contrato inicial: `plugin.toml` (`[plugin]`/`[requires]`/`[ordering]`), classes-base tipadas, `PluginRegistry` com descoberta, versionamento e isolamento de erro — substituindo o `module_call(data)->data` duck-typed. |
| **3** | Bases `Detector`/`Tracker` ganham implementações reais (streaming); `MetadataPlugin.run(ctx)` passa a receber rota já em cm. |
| **4** | Kind `exporter` em uso real (`route-plot`, `pdf-report`); `<workspace>/plugins/` entra nas raízes de busca. |
| **5** | Backends GPU como plugins puros. **Débito conhecido**: `[requires]` não expressa "precisa de build com CUDA" — a exigência está em comentário no manifest, não em campo. |
| **6** | `docs/PLUGIN_CONTRACT.md` (este documento) + `animaltrack plugin install/list/remove`. Seção `[config]` para configuração tipada por plugin, **implementada de forma aditiva** — documentação + checagem de tipo opcional via `PluginManifest.validate_overrides()`, sem gate automático em `Pipeline.run`/`run_cpu_analysis`; a configuração do usuário continua chegando por `ctx.request.overrides`. |

### Limitações conhecidas (estado atual, honesto)

- **Sem sandboxing** — ver aviso no topo.
- **`[config]` no manifest é documentação + checagem de tipo opcional, não um
  gate de execução** — um plugin declara os campos que espera em `overrides`
  (nome, tipo, `required`, `default`, `description`); nada em `Pipeline.run`/
  `run_cpu_analysis` valida isso automaticamente. Um plugin pode chamar
  `PluginManifest.validate_overrides(overrides) -> list[str]` a partir do
  próprio `setup()` se quiser essa checagem — a configuração em si continua
  chegando como `dict[str, Any]` livre em `ctx.request.overrides`. Ver exemplo
  na seção 2 abaixo.
- **`[requires].packages` é declarativo** — nada é instalado automaticamente.
- **Sem aliasing / múltiplas versões** — um nome, uma instalação.
- **Sem auto-update** — instalar de uma URL git é uma cópia pontual.
- **Construtores precisam ser zero-arg** — ver seção 6.
