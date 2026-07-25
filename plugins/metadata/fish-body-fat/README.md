# fish-body-fat-estimator — plugin `metadata` de exemplo

> ## ⚠️ Aviso: a fórmula deste plugin é ilustrativa, não científica
>
> A estimativa de % de gordura corporal aqui **não é uma fórmula biológica
> validada**. Ela implementa apenas a ideia informal "gordura corporal em função de
> velocidade de natação, duração de natação e tamanho do peixe", com constantes
> arbitrárias. **Nenhum dado de domínio real foi usado.** Não tire conclusões
> biológicas dos números que ela produz sem validação por um especialista em
> biologia/fisiologia de peixes.

## Para que este plugin existe

É uma **referência/template para autores de plugin de terceiros** (Fase 6,
workstream B da rearquitetura). Ele demonstra duas coisas:

1. **Generalização de espécie** — o contrato de plugin não tem nada de específico
   de abelha: o mesmo `AnalysisResult` (rota 3D + calibração + métricas) descreve
   um peixe num aquário tão bem quanto uma abelha numa caixa.
2. **O formato completo de um plugin real** — `plugin.toml` + classe + testes +
   este README, exatamente o que um módulo de marketplace conteria.

O contrato público completo está em [`docs/PLUGIN_CONTRACT.md`](../../../docs/PLUGIN_CONTRACT.md).

## O que ele faz

| | |
|---|---|
| **Lê** | `average_speed` (cm/s), métrica produzida pelo plugin `speed` |
| **Lê** | `fish_length_cm`, configuração fornecida pelo usuário (ver abaixo) |
| **Deriva** | duração de natação = frames com posição ÷ fps ÷ 60 |
| **Escreve** | `fish_body_fat_pct` (%), limitada a `[0, 100]` |

Fórmula (placeholder):

```
gordura% = 25.0 − 0.8·velocidade_média + 0.15·duração_min + 0.05·comprimento_cm
```

## Padrões que vale copiar

- **`[ordering] after = ["speed"]`** no manifest: garante que a métrica de entrada
  já exista quando este plugin roda.
- **Acesso defensivo**: se `average_speed` não estiver presente, o plugin registra
  um aviso e **pula** — não levanta exceção. Um plugin que não consegue calcular
  sua métrica nunca deve derrubar o run dos outros.
- **Nunca inventar default para dado medido**: sem `fish_length_cm`, o plugin pula
  em vez de assumir um valor — um default silencioso falsearia um dado biológico.

## Como fornecer `fish_length_cm`

O comprimento do peixe é medido manualmente antes da gravação e não é derivável da
rota. Duas formas, nesta ordem de precedência:

1. **`overrides` do run** (preferido) — `RunRequest(overrides={"fish_length_cm": 12.5})`;
   o plugin lê em `setup(PipelineContext)`.
2. **Variável de ambiente** `ANIMALTRACK_FISH_LENGTH_CM` — fallback que cobre o
   caminho `run_cpu_analysis`, que executa plugins de metadata sem chamar `setup()`.

```bash
ANIMALTRACK_FISH_LENGTH_CM=12.5 animaltrack run --profile meu-aquario
```

> **Decisão em aberto**: o plano da Fase 6 propunha uma seção `[config]` no
> `plugin.toml` para declarar configuração tipada por plugin. Ela **não** foi
> implementada nesta fase para não mexer no schema/discovery de manifest da Fase 2
> (mesmo critério que a Fase 5 aplicou ao seu "débito de manifest"). Formalizar
> `[config]` segue sendo a opção recomendada a prazo — decisão do dono do contrato.

## Instalação

```bash
animaltrack plugin install ./plugins/metadata/fish-body-fat
animaltrack plugin list        # confirma que apareceu
```
