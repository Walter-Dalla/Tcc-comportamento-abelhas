# Handoff: Fase 6 — Workstream C (prontidão de marketplace)
Status: done
Última atualização: 2026-07-25

## O que foi feito

### `docs/PLUGIN_CONTRACT.md` — contrato público
Documento dedicado para **autores de plugin terceiros** (audiência diferente do
`ARCHITECTURE.md`, que serve a quem trabalha dentro do repo). Conteúdo, seguindo a
seção 3.2 do plano:

1. Tabela de campos obrigatórios do `plugin.toml` com regras de validação.
2. Semântica de `[requires]` (`python`/`packages`/`plugins`) e como o registry
   resolve/pula.
3. Semântica de `[ordering]` — incluindo a regra real implementada: **maior
   `priority` roda mais cedo**, desempate alfabético, ciclo é fatal.
4. Convenção de diretório, incl. plugin multi-arquivo e a **pegadinha de que
   `discover()` varre um nível só**.
5. Política de versionamento — `version` × `api_version` × `schema`, e o que o
   autor faz em cada caso.
6. Tabela `kind` → classe-base → assinaturas, mais a **restrição de construtor
   zero-arg** (achado do workstream A).
7. Contrato de isolamento de erro, por estágio (`setup`/`run`/`teardown`), com o
   comportamento real do `Pipeline`.
8. **Aviso de segurança em destaque no topo**: não há sandboxing, um plugin roda
   com privilégio total do processo; curadoria é manual/humana.
9. Esqueleto mínimo copy-paste (manifest + classe).
10. Tabela de rastreabilidade fase → contrato + seção honesta de limitações
    conhecidas.

`ARCHITECTURE.md` ganhou o link cruzado na seção "Contrato de plugin".

### `animaltrack plugin install|list|remove`
- `src/app/plugin_install.py` — miolo testável, separado do Typer.
- `src/app/cli.py` — grupo `plugin` com os três subcomandos.

Fluxo do `install`, conforme seção 3.3 do plano:
1. Detecta origem: path local existente ⇒ cópia; senão ⇒ `git clone --depth 1`.
2. **Staging temporário sempre** — nunca valida no destino final.
3. Remove `.git` do staging (instalação é snapshot pontual, não tracking; sem
   auto-update).
4. Valida o manifest **antes de aceitar**: parse, campos obrigatórios, `kind` no
   enum, `entry` no formato `modulo:Classe`, módulo existe, classe importa e é
   subclasse da base do kind, `api_version`/`schema` compatíveis com o core.
5. Qualquer falha ⇒ imprime **todas** as falhas, descarta staging, **nada escrito**.
6. Nome final vem do **manifest**, não do path/URL.
7. Colisão ⇒ recusa mostrando versão instalada vs. nova, sugere `--force`; com
   `--force`, substitui o diretório inteiro. Sem aliasing.
8. Exit codes scriptáveis: `0` com nome+versão; `≠0` com erros em `stderr`.
9. **Sem backend** — reforçado no código e na doc: `install` só aceita path ou URL
   git literal.

## O que falta

- **Descoberta pós-instalação sem reiniciar processo** (item 7 do plano, seção
  3.3): não implementada como re-`discover()` in-process. Na prática não faz
  diferença hoje — cada comando da CLI é um processo novo que descobre do zero, e
  o plugin instalado já aparece no comando seguinte (coberto por teste). Só vira
  necessário se um dia a GUI instalar plugins sem reiniciar.
- **Sem sandboxing** — é a limitação mais séria da superfície de marketplace, e
  está documentada em destaque, não escondida. Qualquer backend futuro precisa
  resolver isso antes de distribuição ampla.
- **Sem índice/registro, sem aliasing, sem auto-update** — todos fora de escopo por
  decisão do plano ("sem backend definido ainda"), documentados como limitações.
- `[requires].packages` continua **declarativo** (nada é instalado
  automaticamente), e `[requires].plugins` não é verificado na instalação — um
  plugin cuja dependência falta instala normalmente e é pulado com log em tempo de
  run. Aceitável, mas é uma aspereza a confirmar com o dono.

## Como verificar o que já foi feito

```bash
pytest tests/test_cli_plugin_install.py -q   # 14 passed
ruff check . && mypy src tests --python-version 3.13

# fim a fim manual
animaltrack plugin install ./plugins/metadata/fish-body-fat --workspace ./ws
animaltrack plugin list --workspace ./ws
animaltrack list-plugins --workspace ./ws    # built-in + instalados
animaltrack plugin remove fish-body-fat-estimator --workspace ./ws --yes
```

Testes cobrem o caminho feliz completo (**instala um plugin criado fora de
qualquer raiz de busca built-in → registry descobre → roda dentro de um
`Pipeline.run` real e sua métrica aparece no `AnalysisResult`**) e os negativos:
campo obrigatório ausente, classe-base errada, módulo de entry ausente,
`api_version`/`schema`/`kind` incompatíveis, colisão sem e com `--force`, origem
inexistente, e `remove` de plugin não instalado. Todos os negativos asseguram que
**nada** foi escrito no workspace.

## Como retomar

O ponto de extensão natural é `_validate_staging` em `src/app/plugin_install.py`:
qualquer regra nova de contrato (ex. validar `[requires].plugins`, ou uma seção
`[config]` se for formalizada) entra ali, acumulando na lista `errors` para manter
a propriedade de "reporta todas as falhas de uma vez". Ao mudar qualquer regra,
atualize `docs/PLUGIN_CONTRACT.md` **no mesmo commit** — ele é o contrato público,
não documentação derivada.
