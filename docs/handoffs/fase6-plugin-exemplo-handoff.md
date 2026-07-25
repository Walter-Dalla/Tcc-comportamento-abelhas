# Handoff: Fase 6 — Workstream B (plugin de exemplo: % de gordura de peixe)
Status: done
Última atualização: 2026-07-25

## O que foi feito

`plugins/metadata/fish-body-fat/{plugin.toml, plugin.py, README.md}` — plugin
`metadata` de **referência/template para autores terceiros**, demonstrando que o
contrato de plugin generaliza para outra espécie (peixe, não a abelha do TCC
original): o mesmo `AnalysisResult` (rota 3D + calibração + métricas) descreve um
peixe num aquário sem nenhuma mudança de schema.

### O que o plugin demonstra (é o ponto dele)
1. **Consumir métrica de outro plugin** — lê `average_speed` (produzida pelo plugin
   `speed`) via `ctx.get_metric(...)`, com `[ordering] after = ["speed"]` no
   manifest garantindo a ordem.
2. **Acesso defensivo** — métrica ausente ⇒ log + `return`, nunca exceção.
3. **Receber configuração do usuário** que não é derivável da rota
   (`fish_length_cm`).
4. **Publicar métrica própria** — `fish_body_fat_pct` (%), clampada em `[0, 100]`.

### Aviso propagado em três lugares
A fórmula é **ilustrativa/placeholder, não validada cientificamente**. O aviso
aparece no docstring do módulo, num comentário do `plugin.toml` e num bloco de
destaque no topo do `README.md` — como o plano exige.

```
gordura% = 25.0 − 0.8·velocidade_média + 0.15·duração_min + 0.05·comprimento_cm
```

### DECISÃO REGISTRADA: de onde vem `fish_length_cm` (seção 2.4 do plano)

O plano propunha estender o `plugin.toml` com uma seção `[config]`. **Não foi
implementado, deliberadamente.** Motivo: `PluginManifest` é `extra="forbid"` e
`from_toml` só lê `[plugin]`/`[requires]`/`[ordering]` — adicionar `[config]`
exigiria mexer no schema e no discovery da Fase 2, exatamente o tipo de mudança
que a Fase 5 evitou ao registrar seu "débito de manifest" em vez de alterar o
contrato.

**Solução adotada, usando só mecanismo já existente:**
- `Plugin.setup(PipelineContext)` → `ctx.request.overrides` (um `dict[str, Any]`
  livre já presente no `RunRequest`). É o caminho preferido.
- Fallback por variável de ambiente `ANIMALTRACK_FISH_LENGTH_CM`, que cobre o
  caminho `run_cpu_analysis` (orquestração da Fase 3), o qual executa plugins de
  metadata **sem chamar `setup()`**.
- Sem o dado, o plugin **pula com log** em vez de assumir default — um default
  silencioso falsearia um dado biológico medido.

**Pendente de confirmação do dono**: formalizar `[config]` no manifest continua
sendo a opção recomendada a prazo (declaração tipada, validável, autodocumentada).

### Integração
`src/app/plugins.py` ganhou `plugins/metadata/` e `plugins/tracker/` como raízes de
busca próprias — `PluginRegistry.discover()` varre **um nível só**, então pastas de
agrupamento não são alcançadas pela varredura de `plugins/`.

## O que falta

- Confirmação do dono sobre `[config]` (acima).
- **A fórmula precisa de validação por um especialista** antes de qualquer uso real
  — é placeholder por construção, não um débito de implementação.
- O plugin **não roda** no caminho `run_cpu_analysis` por padrão: aquele
  orquestrador descobre apenas `plugins/` (um nível), então só `speed` e `border`
  entram. É intencional — é um exemplo, não um plugin de produção. Para exercitá-lo
  num run real, instale-o (`animaltrack plugin install ./plugins/metadata/fish-body-fat`),
  o que o coloca em `<workspace>/plugins/`.

## Como verificar o que já foi feito

```bash
pytest tests/plugins/test_fish_body_fat_plugin.py -q   # 11 passed
ruff check . && mypy src tests --python-version 3.13   # limpos

animaltrack plugin install ./plugins/metadata/fish-body-fat --workspace ./ws
animaltrack plugin list --workspace ./ws               # confirma descoberto
```

Testes cobrem: valor exato da fórmula, clamp nos dois extremos, ausência de
`average_speed` (pula), ausência de `fish_length_cm` (pula, não inventa default),
uso da env var quando `setup()` não rodou, valores inválidos de comprimento
(`não-numérico`, negativo, zero) rejeitados sem default, `average_speed`
não-numérico, e descoberta com `ordering.after == ["speed"]`.

## Como retomar

O plugin é o template canônico: para escrever outro plugin `metadata`, copie o
diretório inteiro e siga a seção 8 ("Esqueleto mínimo copy-paste") de
`docs/PLUGIN_CONTRACT.md`. Se `[config]` for formalizado, o ponto de mudança é
`PluginManifest` (`src/core/plugin.py`) + `_validate_staging`
(`src/app/plugin_install.py`), e este plugin é o primeiro consumidor natural.
