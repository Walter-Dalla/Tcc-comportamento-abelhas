# Fase 6 — Pesquisa e prontidão de marketplace (plano detalhado)

> Referência: `ARCHITECTURE.md`, seções "Abstração Detector/Tracker" e entrada "Fase 6" em "Fases".
> Pré-requisito confirmado: ao entrar na Fase 6, as interfaces `Plugin`, `Tracker` (`update`/`tracks`/
> `reset`) e `MetadataPlugin`/`Pipeline.run` já estão fixadas e estáveis (entregues nas Fases 2-4). Este
> plano assume isso e **não** redesenha nenhuma dessas interfaces.

## Escopo e enquadramento geral

A Fase 6 tem 3 workstreams **sem dependência entre si** (paralelo total, conforme tabela de
paralelização do `ARCHITECTURE.md`):

- **A. Spike de tracker multi-animal** — prova que a interface `Tracker` já fixada comporta múltiplas
  entidades, sem comprometer qual algoritmo é "o escolhido". Escolha de algoritmo continua pesquisa
  aberta, por decisão explícita do dono do projeto.
- **B. Plugin de exemplo — % de gordura de peixe** — plugin de `metadata` de referência, demonstrando
  generalização de espécie e o contrato de plugin para autores terceiros. A fórmula usada é
  **ilustrativa/placeholder**, não uma fórmula biológica validada.
- **C. Prontidão de marketplace** — documentação do `plugin.toml` como contrato público + comando
  `animaltrack plugin install <path/git-url>`. Sem backend de marketplace definido nesta fase.

Cada workstream abaixo tem: objetivo, tarefas ordenadas, critérios de sucesso e arquivos esperados.

---

## 1. Workstream A — Spike de tracker multi-animal

### 1.1 Objetivo do spike (o que NÃO é, e o que É)

**É**: provar, com um segundo plugin `tracker` real rodando atrás da interface `Tracker` já fixada, que o
esqueleto de arquitetura (schema `Detection`/`FrameDetections`/`Track`, camadas Detect→Track→Fuse) admite
múltiplas entidades simultâneas, incluindo cruzamento de trajetórias e oclusão, **sem alterar** schema,
`Detect`, `Fuse` ou o contrato `Tracker`.

**NÃO é**: escolher o algoritmo de tracking definitivo do produto. Por decisão explícita do dono do
projeto (registrada no `ARCHITECTURE.md`: *"Algoritmo continua em aberto — o ponto é provar que a
interface admite"*), este plano **não** recomienda Kalman, Hungarian, correspondência cross-câmera nem
nenhuma outra abordagem como resposta final. O resultado do spike é um **relatório comparativo** que
alimenta uma decisão futura, não a decisão em si.

### 1.2 Harness de avaliação — fixture multi-entidade concreta

Duas variantes de fixture, complementares:

**(a) Fixture de nível-unidade — `FrameDetections` sintéticas diretas** (ciclo rápido de avaliação de
algoritmo, sem depender de Detect nem de codificação de vídeo):

- Script `tests/fixtures/tracker/gen_synthetic_detections.py` gera, para N frames (ex. 150), uma lista de
  `FrameDetections` por frame, view fixa (`"top"`), com 2+ `Detection`s por frame seguindo trajetórias
  paramétricas conhecidas.
- Trajetórias concretas (parametrização exata, para ser reprodutível):
  - Entidade A: `x_A(t) = 40 + 4.0*t`, `y_A(t) = 100 + 15*sin(2*pi*t/60)` (esquerda→direita, oscilação
    vertical leve), `t` = índice do frame, 0..149.
  - Entidade B: `x_B(t) = 560 - 4.0*t`, `y_B(t) = 100 - 15*sin(2*pi*t/60)` (direita→esquerda). Nota: B usa
    a **mesma baseline vertical de A (100) com fase oposta** de propósito — com baselines distantes (ex. A
    em 100 e B em 200, amplitude 15), os centróides nunca chegariam à distância de oclusão (`< soma dos
    raios = 24px`): a separação vertical mínima seria ~70px e as duas nunca colapsariam em um único blob,
    esvaziando a janela de cruzamento. Mantendo A e B na mesma faixa vertical, elas ficam separadas só em
    x até convergirem perto do cruzamento.
  - As duas trajetórias se cruzam (distância entre centróides < soma dos raios, raio fixo 12px) por volta
    do frame 65 (onde `x_A = x_B`, isto é `40 + 4t = 560 - 4t`) — a janela exata de cruzamento é calculada
    e registrada no arquivo de ground truth (não hardcoded "no olho").
  - Durante a janela de cruzamento, o gerador simula oclusão real: por 5-10 frames consecutivos as duas
    detecções colapsam em **uma única** `Detection` (centróide médio, bbox união) — replicando o que o
    `BackgroundSubtractionDetector` real faria ao ver um único contorno de dois blobs sobrepostos. Fora
    da janela, 2 detecções normais por frame.
  - Fixture parametrizável para 3+ entidades (adicionar entidade C com trajetória vertical
    `y_C(t) = 40 + 3.2*t`, cruzando A e B em pontos diferentes) para testar cenários de oclusão múltipla,
    mas o caso mínimo obrigatório é 2 entidades cruzando.
- Ground truth: `tests/fixtures/tracker/ground_truth.json` — por frame, posição real de cada entidade
  nomeada (`entity_A`, `entity_B`, ...) e flag `occluded: bool` quando colapsada. Esse arquivo é o que
  permite calcular métricas objetivamente (só é possível porque a fixture é sintética e a "verdade" é
  conhecida por construção).

**(b) Fixture de nível-integração — vídeo golden** (exercita Detect+Track juntos, é o que o critério de
verificação da Fase 6 do `ARCHITECTURE.md` pede: *"fixture multi-entidade gera ≥2 `entity_id`s
estáveis"*):

- Script `tests/fixtures/tracker/gen_synthetic_video.py` renderiza (via `cv2`/`numpy`, círculos sólidos
  sobre fundo uniforme) as mesmas trajetórias acima em um vídeo real (`.mp4`/`.avi`, 640x480, 30fps, 5s ≈
  150 frames), gravado como par top/side (side pode ser uma projeção trivial, ex. só eixo y variando, já
  que o foco do spike é o comportamento do `Tracker`, não o `Fuse`).
- Vídeo + ground truth commitados como fixture de teste (arquivo pequeno, poucos segundos, resolução
  baixa — manter no orçamento de repo).
- **Limitação conhecida para o candidato 3 (correspondência cross-câmera)**: com a view lateral reduzida a
  uma projeção trivial, ela **não** carrega informação independente capaz de desambiguar identidades
  durante a oclusão na view de topo — que é exatamente o mecanismo que o candidato 3 (seção 1.4.3) alega
  explorar. Avaliar o candidato 3 de forma significativa exigiria uma fixture cuja view lateral **mantenha
  as duas entidades separáveis durante a janela de oclusão da view de topo** (ex. entidades que se sobrepõem
  no topo mas continuam distintas na lateral). Com a projeção trivial aqui, a medição do candidato 3 fica
  necessariamente limitada — coerente com seu caráter *time-boxed*/"medir o que der" (tarefa 9), mas a ser
  registrado explicitamente no relatório para não superinterpretar o resultado dele.

### 1.3 Métricas de sucesso — separar critério de interface (obrigatório) de critério de algoritmo (pesquisa)

**Critério de interface (obrigatório, é o que decide se o spike "funcionou" arquiteturalmente):**
- O pipeline roda ponta-a-ponta com o novo plugin `tracker` selecionado via `pipeline.toml`, **sem**
  nenhuma alteração em `Detect`, `Fuse`, schema (`Detection`/`Track`/`Route3D`) ou no contrato abstrato
  `Tracker`.
- Rodar a fixture (b) produz `AnalysisResult` com ≥2 `entity_id`s distintos e estáveis (não um único
  `entity_id=0` como o `SingleEntityTracker` atual produziria).

**Métricas de qualidade de algoritmo (informativas, alimentam o relatório comparativo, NÃO são gate de
aceite da fase — são o *resultado da pesquisa*, cujo bar aceitável fica em aberto para decisão futura):**

- **Taxa de ID-switch**: para cada frame onde a atribuição ground-truth-para-track mais próxima (por
  distância de centróide) muda de `entity_id` em relação ao frame anterior — sem que a entidade física
  correspondente tenha reaparecido de uma oclusão longa — conta como 1 switch. Métrica final =
  `total_switches / total_frames_com_2+_entidades`.
- **Contagem de fragmentação de track**: número de segmentos de `Track.points` distintos (interrompidos
  por buraco) produzidos por entidade-verdade. Ideal = 1 segmento por entidade ground-truth; fragmentação
  = `num_segmentos_produzidos - num_entidades_ground_truth` (0 = perfeito).
- **Recuperação pós-oclusão**: booleano por evento de oclusão — o `entity_id` de cada entidade antes da
  oclusão é o mesmo depois (recuperação correta) ou trocou/apareceu como novo id (recuperação falha).
- **Nota secundária de performance** (não bloqueante, apenas registrada): frames/segundo do candidato na
  fixture — relevante para viabilidade futura de tempo real, mas não decide sucesso do spike.

Uma barra de partida sugerida (ajustável, não é um gate rígido de fase, é só para orientar o relatório):
pelo menos um candidato deve alcançar ID-switch = 0 no evento de cruzamento da fixture mínima (2
entidades) e fragmentação ≤ 1 por entidade. Se **nenhum** candidato alcançar isso, o spike ainda é
considerado bem-sucedido do ponto de vista de **interface** (critério obrigatório acima) — o relatório
apenas documenta que nenhum candidato testado está pronto para produção e recomenda investigação
adicional.

### 1.4 Candidatos a avaliar (2-3 — explicitamente candidatos, não decisão)

Os três candidatos abaixo são os já citados no `ARCHITECTURE.md` (seção "Abstração Detector/Tracker" e
Fase 6). Cada um recebe um parágrafo de trade-off. Nenhum é apresentado como "a escolha" — o objetivo do
spike é gerar dados comparativos, a escolha final é uma decisão de produto posterior do dono do projeto.

1. **Kalman filter (predição de movimento por entidade) + associação greedy por proximidade.**
   Trade-off: é barato computacionalmente e modela bem movimento suave/linear através de oclusões breves
   (a predição do filtro "segura" a posição da entidade enquanto ela está ocluída, permitindo
   reassociação quando reaparece). Fraqueza: a etapa de associação greedy (pega o vizinho mais próximo,
   sem considerar o conjunto completo de candidatos) pode trocar identidades quando duas entidades têm
   velocidades/posições preditas muito parecidas no momento do cruzamento — é justamente o cenário da
   fixture de teste. Na prática, Kalman costuma ser combinado com uma etapa de associação melhor (ver
   candidato 2) em vez de usado sozinho com greedy.

2. **Hungarian algorithm (assignment ótimo via matriz de custo, ex. `scipy.optimize.linear_sum_assignment`)
   para associar detecção→track por frame.** Trade-off: resolve a associação de forma globalmente ótima
   (minimiza custo total, ex. soma de distâncias), lidando melhor que greedy com múltiplos candidatos
   simultâneos competindo pela mesma detecção — reduz ID-switch em cruzamentos comparado ao greedy puro.
   Fraqueza: por si só não tem modelo de movimento/predição — normalmente precisa ser combinado com uma
   posição predita (ex. do Kalman) como ponto de referência para o custo, e sozinho não resolve
   reidentificação após oclusão longa (detecção "sumida" não tem custo contra o quê comparar). Custo
   computacional cresce com o número de detecções, mas irrelevante na escala esperada deste projeto
   (poucos blobs por frame).

3. **Correspondência cross-câmera** (usa as duas `FrameDetections` — topo e lateral — em conjunto,
   explorando consistência geométrica/epipolar entre as views para desambiguar identidade). Trade-off:
   é o único candidato que aproveita de forma nativa o setup dual-câmera já existente no projeto — em
   teoria pode recuperar identidade através de uma oclusão em uma view usando a detecção ainda clara da
   outra view (ex. os dois blobs se sobrepõem na câmera de topo mas continuam separados na lateral).
   Fraqueza: é a abordagem mais custom e menos testada das três (não é um algoritmo de prateleira como os
   dois anteriores), exige acesso à calibração/`axis_mapping()` já no momento do tracking (acoplamento
   maior entre Track e Fuse do que a interface `Tracker` hoje assume) e sincronização exata entre as duas
   streams de detecção — complexidade de implementação bem maior. Deve ser tratado como o candidato mais
   caro e ser explicitamente *time-boxed* no spike (ver tarefa 8 abaixo) em vez de levado a uma
   implementação completa de plugin.

*(Nota: uma quarta via — tracking por aparência/re-identificação visual, ex. embeddings de rede neural —
foi deliberadamente deixada de fora da lista de candidatos porque contraria a decisão de arquitetura de
manter o núcleo "sem IA embutida"; mencionar apenas como nota de rodapé no relatório final, não como
candidato a spikar.)*

### 1.5 Lista de tarefas ordenada e concreta

1. Implementar gerador de fixture nível-unidade (`gen_synthetic_detections.py`) + arquivo de ground truth
   (`ground_truth.json`), com a parametrização de trajetórias da seção 1.2(a).
2. Implementar gerador de fixture nível-integração (`gen_synthetic_video.py`), reaproveitando as mesmas
   trajetórias, produzindo par de vídeos top/side + ground truth.
3. Implementar o harness de métricas (`tests/fixtures/tracker/metrics.py` ou módulo equivalente): recebe
   `list[Track]` produzido por um `Tracker` + `ground_truth.json`, calcula taxa de ID-switch,
   fragmentação e recuperação pós-oclusão (fórmulas da seção 1.3).
4. Rodar o `SingleEntityTracker` (já existente da Fase 3) contra a fixture como **controle/baseline** —
   esperado: colapsa tudo em `entity_id=0`, útil para evidenciar por que o spike importa (métrica de
   fragmentação/ID-switch não se aplica pois não há distinção de entidade nenhuma — documentar isso
   explicitamente no relatório como "baseline sem capacidade multi-entidade").
5. Implementar candidato 1 (Kalman + greedy) como plugin `tracker` completo em
   `plugins/tracker/kalman-greedy/{plugin.toml, plugin.py}`, seguindo o contrato `Tracker`
   (`update`/`tracks`/`reset`).
6. Rodar o harness (passo 3) contra o candidato 1 na fixture (a), registrar métricas.
7. Implementar candidato 2 (Hungarian, com posição predita do Kalman como referência de custo) como
   segundo plugin `tracker` em `plugins/tracker/kalman-hungarian/{plugin.toml, plugin.py}`.
8. Rodar o harness contra o candidato 2, registrar métricas.
9. Prototipar candidato 3 (correspondência cross-câmera) em nível de **script de spike** (não
   necessariamente um plugin completo/produção), explicitamente time-boxed (ex. orçamento fixo de tempo
   definido antes de começar — se estourar, documentar o estado parcial e parar, não é obrigatório
   terminar); medir o que der para medir com o harness.
10. Escrever o relatório de achados em `docs/handoffs/fase6-tracker-spike-handoff.md`: tabela comparativa
    de métricas por candidato, recomendação de continuidade (ou não) de cada abordagem, reafirmando que a
    escolha final do algoritmo de produção é decisão pendente do dono do projeto.
11. Teste de integração final: confirmar que trocar o plugin `tracker` ativo apenas via `pipeline.toml`
    (sem tocar código de `Detect`/`Fuse`/schema) faz o pipeline rodar de ponta a ponta na fixture (b) e
    produzir ≥2 `entity_id`s estáveis no `AnalysisResult` — este é o critério de verificação obrigatório
    da fase.

---

## 2. Workstream B — Plugin de exemplo: % de gordura de peixe

### 2.1 Enquadramento (aviso explícito)

Este plugin é uma **referência/exemplo de terceiro** — seu propósito é demonstrar (a) que o contrato de
plugin `metadata` generaliza para uma espécie diferente (peixe, não abelha) e (b) o formato completo de
um plugin real (manifest + lógica + testes) que um autor externo replicaria.

> **A fórmula de gordura corporal usada abaixo é ilustrativa/placeholder.** Ela segue a ideia informal
> dada pelo dono do projeto (gordura corporal em função de velocidade de natação + duração de natação +
> tamanho do peixe), mas **não é uma fórmula biológica validada** — ninguém especificou a ciência de
> domínio real para isso ainda. Qualquer uso além de demonstração de arquitetura exige validação com um
> especialista em biologia/fisiologia de peixes antes de qualquer conclusão real ser tirada dos números
> que ela produz. Este aviso deve aparecer também no código (docstring/comentário) e num `README.md` do
> próprio diretório do plugin.

### 2.2 `plugin.toml` (kind = metadata)

```toml
[plugin]
name        = "fish-body-fat-estimator"
version     = "0.1.0"
kind        = "metadata"
entry       = "plugin:FishBodyFatEstimator"
api_version = "1.0"
schema      = ">=1.0,<2.0"

[requires]
python   = ">=3.11"
packages = []
plugins  = []          # não depende de outro plugin para existir, mas depende de uma métrica (ver ordering)

[ordering]
before   = []
after    = ["speed"]   # precisa que average_speed já esteja calculado por speedModule/plugin "speed"
priority = 200

[config]
# Extensão proposta ao manifesto (ver nota de decisão em aberto abaixo): valor default e obrigatoriedade
# de um dado que não é derivável da rota — tamanho do peixe.
fish_length_cm = { required = true, type = "float", description = "Comprimento do peixe em cm, medido manualmente antes da gravação." }
```

### 2.3 Lógica de `module_call`/`run` (pseudocódigo comentado)

```python
"""
fish-body-fat-estimator — plugin de METADATA de referência (espécie: peixe).

AVISO: a fórmula abaixo é ILUSTRATIVA/PLACEHOLDER. Não é uma fórmula biológica validada.
Baseia-se apenas na ideia informal "gordura corporal em função de velocidade de natação,
duração de natação e tamanho do peixe" — nenhum dado de domínio real foi fornecido até o
momento. Não usar os valores produzidos por este plugin para qualquer conclusão biológica
real sem validação por um especialista.
"""

class FishBodyFatEstimator(MetadataPlugin):
    manifest = ...  # carregado de plugin.toml

    def run(self, ctx: AnalysisContext) -> None:
        avg_speed = ctx.get_metric("average_speed")   # produzido pelo plugin "speed" (ordering: after)
        if avg_speed is None:
            # acesso defensivo — schema versionado permite recusar/pular sem KeyError (ver ARCHITECTURE.md,
            # seção "Schema de dados")
            log.warning("fish-body-fat-estimator: métrica 'average_speed' ausente, pulando.")
            return

        fps = ctx.result.calibration.fps
        total_frames = _count_frames_with_position(ctx.result.routes)
        swim_duration_min = (total_frames / fps) / 60.0

        fish_length_cm = self.config.fish_length_cm  # vindo da seção [config] do manifesto (ver 2.4)

        # --- FÓRMULA PLACEHOLDER (não validada) ---
        # Ideia informal: gordura corporal cai com velocidade média alta e sobe com duração de natação
        # e tamanho do peixe, dentro de faixas arbitrárias de calibração de constantes.
        BASE = 25.0   # % baseline arbitrário
        K_SPEED = 0.8
        K_DURATION = 0.15
        K_SIZE = 0.05

        body_fat_pct = BASE \
            - K_SPEED * avg_speed.value \
            + K_DURATION * swim_duration_min \
            + K_SIZE * fish_length_cm
        body_fat_pct = max(0.0, min(100.0, body_fat_pct))  # clamp em faixa fisicamente plausível

        ctx.add_metric(Metric(
            name="fish_body_fat_pct",
            value=body_fat_pct,
            unit="%",
            producer="fish-body-fat-estimator",
        ))
```

### 2.4 Item em aberto: config por plugin (decisão a confirmar)

O contrato de plugin atual (Fases 2-4) não previa um mecanismo de **configuração customizada por
plugin** vinda do usuário (os plugins `speed`/`border` hoje só leem dados já presentes no
`AnalysisContext`). Este plugin precisa de um dado novo — `fish_length_cm` — que não é derivável da rota
nem de nenhuma métrica já calculada.

Proposta mínima (a confirmar com quem mantém `plugin.py`/`plugin_registry.py`):
- Seção `[config]` opcional no `plugin.toml`, com schema simples (nome, tipo, obrigatório, descrição,
  default opcional).
- Se o dado obrigatório não for fornecido no perfil do usuário: falhar de forma clara e localizada (log +
  métrica pulada, não crash do run inteiro — consistente com o isolamento de erro já definido no
  `ARCHITECTURE.md`) em vez de silenciosamente assumir um default enganoso para um dado biológico.
- Alternativa mais simples de curto prazo, se estender o manifesto for indesejado nesta fase: ler
  `fish_length_cm` de um campo genérico já existente no perfil (se houver) ou aceitar via variável de
  ambiente/arquivo de config lateral — citado aqui apenas como fallback, a extensão de manifesto é a opção
  recomendada por ser consistente com o resto do contrato.

### 2.5 Layout de diretório

```
plugins/metadata/fish-body-fat/
├── plugin.toml
├── plugin.py
└── README.md   # repete o aviso de fórmula placeholder, explica o propósito de exemplo/referência
```

### 2.6 Teste

- Teste unitário com `AnalysisResult` sintético (rota fixa, `average_speed` conhecido, `fish_length_cm`
  fornecido) verificando que `fish_body_fat_pct` é calculado com a fórmula esperada e clampado em
  `[0, 100]`.
- Teste de ausência de `average_speed`: plugin pula sem lançar exceção, não adiciona métrica.
- Teste de ausência de `fish_length_cm` no config: falha localizada e documentada (não crash do run).

---

## 3. Workstream C — Prontidão de marketplace

### 3.1 Onde documentar o contrato público — decisão

**Decisão**: criar `docs/PLUGIN_CONTRACT.md` como documento dedicado (não embutir em
`ARCHITECTURE.md`). Justificativa: `ARCHITECTURE.md` é a referência viva de arquitetura para quem
trabalha *dentro* do repositório (contexto, decisões, fases); `PLUGIN_CONTRACT.md` tem audiência
diferente — autores de plugin terceiros que só precisam saber o formato do `plugin.toml`, o que cada
`kind` exige, e as regras de instalação. Misturar os dois deixaria `ARCHITECTURE.md` inchado e o contrato
público mais difícil de achar. `ARCHITECTURE.md` ganha um link cruzado apontando para
`docs/PLUGIN_CONTRACT.md` na seção "Contrato de plugin".

### 3.2 Conteúdo exato do `docs/PLUGIN_CONTRACT.md`

1. **Tabela de campos obrigatórios do `plugin.toml`**: `name` (string, único, kebab-case), `version`
   (semver), `kind` (enum: `capture|rectify|detector|tracker|fusion|metadata|exporter|interface`),
   `entry` (formato `modulo:Classe`), `api_version` (semver da API de plugin do core), `schema` (range
   semver do `AnalysisResult`/schema de dados aceito) — com regras de validação (regex de `name`, enum
   fechado de `kind`, `entry` deve resolver e a classe deve ser subclasse do tipo base correto).
2. **Semântica de `[requires]`**: `python` (specifier PEP 440), `packages` (lista PEP 508), `plugins`
   (nomes de outros plugins dos quais este depende, opcionalmente com version range) — e como o registry
   resolve/rejeita (plugin cujo `requires.plugins` não está presente é pulado com log, não derruba o
   run).
3. **Semântica de `[ordering]`**: `before`/`after` referenciam `name` de outros plugins do mesmo `kind`;
   `priority` (inteiro, **maior número roda mais cedo**, default `0` — alinhado ao `_topological_order` da
   Fase 2, que ordena por `(-priority, nome)`); regra de desempate (ordem alfabética do `name`) quando não
   há relação explícita `before`/`after`.
4. **Convenção de diretório/co-localização**: `plugin.toml` sempre ao lado do arquivo de entrada;
   layout para plugins multi-arquivo (pacote Python normal dentro da pasta do plugin, `entry` aponta para
   o módulo público).
5. **Política de versionamento**: diferença entre `version` (do plugin em si, informativo), `api_version`
   (contrato do core — bump maior = plugins antigos passam a ser rejeitados pelo registry) e `schema`
   (range do schema de dados aceito) — regras de semver para cada um e o que um autor de plugin deve
   fazer ao atualizar.
6. **Contrato de classe-base por `kind`**: tabela linkando cada `kind` à classe abstrata correspondente
   em `src/core/stages.py`/`src/core/plugin.py` (`Detector.detect`, `Tracker.update`/`tracks`/`reset`,
   `MetadataPlugin.run`, etc.), com assinatura mínima esperada.
7. **Contrato de isolamento de erro**: o que acontece se `setup()`/método principal do plugin lança
   exceção — plugin é pulado, log estruturado (formato esperado do log: nível, nome do plugin, exceção),
   run continua para os demais plugins do mesmo `kind`.
8. **Aviso de segurança/confiança**: nenhum sandboxing existe ainda — um plugin instalado roda com
   privilégio total do processo host. Curadoria é manual/humana por ora (modelo "git-tap curado"), não há
   verificação automática de segurança de código de terceiro. Este aviso deve ser bem visível (bloco de
   destaque no topo do documento, não rodapé).
9. **Esqueleto mínimo copy-paste**: exemplo completo de um plugin `metadata` trivial (manifest + classe)
   pronto para copiar/adaptar.
10. **Tabela de rastreabilidade fase→versão de contrato**: qual fase da arquitetura introduziu/alterou o
    formato atual do `plugin.toml` (ex. Fase 2 = contrato inicial, Fase 6 = extensão `[config]` proposta
    no Workstream B) — para quem consome o contrato entender o histórico sem precisar ler todo o
    `ARCHITECTURE.md`.

### 3.3 `animaltrack plugin install <path/git-url>` — comportamento exato

Novo grupo de subcomando Typer em `src/app/cli.py`: `animaltrack plugin install|list|remove`.

**Fluxo `install <path/git-url>`:**

1. **Detectar origem**: se o argumento resolve para um path local existente (`Path(arg).exists()`), usa
   fluxo de cópia local; senão, trata como git URL.
2. **Path local**: copia (não symlink) a árvore de diretório inteira para um diretório temporário de
   staging antes de validar (nunca valida direto no destino final).
3. **Git URL**: `git clone --depth 1 <url> <tmp-dir>`; após clone, remove metadados `.git` do staging
   (instalação não é "tracking" de upstream — não há responsabilidade de auto-update nesta fase, é uma
   cópia pontual).
4. **Validação do manifesto ANTES de aceitar** (sobre o staging, não sobre o destino):
   - `plugin.toml` existe e parseia.
   - Todos os campos obrigatórios presentes (seção 3.2, item 1).
   - `kind` é um dos valores do enum permitido.
   - `entry` resolve (import) e a classe é subclasse do tipo base correto para o `kind` declarado.
   - `api_version`/`schema` estão dentro do range que o core instalado suporta.
   - **Se qualquer verificação falhar**: comando aborta, imprime **todas** as falhas encontradas (não só
     a primeira), staging é descartado, **nada é escrito** em `workspace/plugins/`.
5. **Nome final vem do manifesto** (`[plugin].name`), não do nome do diretório/path/URL fornecido.
6. **Colisão de nome**: se `workspace/plugins/<name>/` já existir:
   - Comportamento padrão: **recusa**, mensagem mostra versão já instalada vs. versão nova (do
     `plugin.toml` incoming), sugere `--force` para sobrescrever.
   - Com `--force`: substitui o diretório existente inteiro pelo conteúdo validado do staging.
   - **Sem aliasing nesta fase** — instalar duas versões lado a lado sob nomes locais diferentes fica
     fora de escopo (seria feature de um backend de marketplace futuro, citado apenas como possibilidade
     futura no documento de contrato, não implementado agora).
7. **Pós-instalação**: dispara `PluginRegistry.discover([workspace.plugins])` para o plugin ficar
   visível imediatamente, sem precisar reiniciar processo/CLI.
8. **Saída/exit codes**: sucesso → exit 0, imprime nome+versão instalada; falha de validação → exit ≠0,
   lista de erros; colisão sem `--force` → exit ≠0, mensagem de conflito — formato pensado para ser
   scriptável (parseável por CI, se necessário no futuro).
9. **Sem backend**: reforçar explicitamente no comportamento e na documentação — não há índice/servidor
   de resolução por nome. `install` sempre recebe um path ou URL git **literal** fornecido pelo usuário;
   "marketplace" aqui é só o formato de contrato + curadoria manual (estilo "git-tap"), não um serviço.

**Subcomandos irmãos** (mencionar, não é o foco desta fase, mas completa a superfície do CLI):
`animaltrack plugin list` (lista plugins descobertos com nome/versão/kind/origem), `animaltrack plugin
remove <name>` (remove diretório de `workspace/plugins/<name>/`, com confirmação).

### 3.4 Arquivos esperados deste workstream

`docs/PLUGIN_CONTRACT.md` (novo), `src/app/cli.py` (subcomando `plugin install/list/remove`), link
cruzado adicionado em `ARCHITECTURE.md` (seção "Contrato de plugin") apontando para o novo documento.

---

## 4. Paralelização

Confirmado, alinhado à tabela de paralelização do `ARCHITECTURE.md` (linha "Fase 6"): os workstreams A
(spike de tracker), B (plugin de peixe) e C (marketplace) **não têm dependência entre si** — nenhum lê ou
escreve arquivo que outro também toca, e nenhum contrato definido por um é consumido pelos outros.

Cada workstream depende apenas de infraestrutura que já deve estar estável **antes** de começar a Fase 6:
- A depende de: `Tracker` (interface abstrata), `SingleEntityTracker` (baseline, Fase 3), `Pipeline.run`,
  schema `Detection`/`FrameDetections`/`Track` (Fase 1).
- B depende de: `MetadataPlugin`/`Plugin` (interface), `PluginRegistry`, `AnalysisContext.get_metric`/
  `add_metric`, plugin `speed` já existente (Fase 2/3) produzindo `average_speed`.
- C depende de: formato de `plugin.toml` e `PluginRegistry.discover` (Fase 2), `Workspace` (Fase 1/4),
  `src/app/cli.py` já existente como base Typer (Fase 4).

Nenhuma dessas dependências é *nova* — todas já deveriam estar entregues e estáveis ao final da Fase 4/5,
conforme a ordem de fases do `ARCHITECTURE.md`. Portanto os 3 workstreams podem começar **em paralelo
total, dia 1 da fase**, sem espera por interface.

**Isolamento (worktree)**: seguindo a regra geral do `ARCHITECTURE.md` ("workstreams só de leitura/
pesquisa (spikes, docs) não precisam de worktree; todo workstream que escreve código usa worktree
separado"):
- A escreve código (2-3 plugins `tracker` + scripts de fixture/harness) → worktree próprio.
- B escreve código (plugin `metadata` completo) → worktree próprio.
- C é misto: a parte de documentação (`PLUGIN_CONTRACT.md`) é só-leitura/escrita de doc, pode dispensar
  worktree; a parte de CLI (`plugin install/list/remove` em `src/app/cli.py`) escreve código → usar
  worktree para essa parte, ou tratar C como um único worktree cobrindo doc+CLI (mais simples de
  coordenar do que fatiar um workstream pequeno em dois).

Integração final: após os 3 workstreams terminarem, merge sequencial dos worktrees (nenhum conflito de
arquivo esperado, já que não compartilham arquivo algum), roda a suíte de verificação da fase inteira, só
então grava o handoff consolidado em `docs/handoffs/PROGRESS.md`.

---

## 5. Plano de teste

- **Teste de fixture multi-entidade** (`tests/test_tracker_multi_entity.py`): roda um `Tracker` candidato
  (ou o pipeline completo) contra a fixture de integração (seção 1.2b), asserta que o `AnalysisResult`
  produzido contém **≥2 `entity_id`s estáveis** ao longo do tempo (mesmo `entity_id` associado à mesma
  entidade física do início ao fim, exceto durante a janela de oclusão documentada), e que não há
  `entity_id`s "fantasma" além do número de entidades do ground truth mais uma tolerância pequena (ex.
  no máximo +1, para acomodar um id descartado rapidamente por ruído).
- **Teste de instalação de plugin externo, descoberta e execução**
  (`tests/test_cli_plugin_install.py`):
  1. Cria um plugin de teste válido (manifest + `plugin.py` trivial) em diretório temporário.
  2. Invoca `animaltrack plugin install <tmp-dir>` via runner de CLI (Typer `CliRunner` ou subprocess).
  3. Asserta que `workspace/plugins/<name>/` foi criado com o conteúdo esperado.
  4. Asserta que `PluginRegistry.discover` encontra o plugin recém-instalado.
  5. Roda um `Pipeline.run` mínimo que inclui esse plugin na cadeia e confirma que sua métrica/efeito
     esperado aparece no `AnalysisResult`.
  6. **Teste negativo — manifesto inválido**: instala um plugin com `plugin.toml` faltando campo
     obrigatório; asserta exit code ≠0, mensagem lista o(s) erro(s), e que **nada** foi escrito em
     `workspace/plugins/`.
  7. **Teste negativo — colisão de nome sem `--force`**: instala o mesmo plugin duas vezes; segunda
     chamada é recusada, diretório original permanece intacto (verificar conteúdo/versão inalterados);
     repetir com `--force` e confirmar que aí sim substitui.
- **Teste unitário do plugin de peixe** (seção 2.6, já detalhado acima): fórmula, clamp, ausência de
  métrica de entrada, ausência de config obrigatório.
- **Smoke tests dos candidatos de tracker** (um por candidato implementado como plugin completo — 1 e
  2): teste leve rodando o harness (seção 1.3) contra a fixture (a) e asserindo que os `entity_id`
  batem com o ground truth **dentro de um limiar tolerante** (não um bar de qualidade de produção — só
  para impedir que o código do spike apodreça silenciosamente/quebre em refactors futuros sem que
  ninguém perceba).

---

## 6. Comandos de verificação

```
# suíte de testes da fase (ajustar marker/path conforme convenção de teste do projeto)
pytest -k "tracker_multi_entity or cli_plugin_install or fish_body_fat or tracker_spike"

# qualidade de código
ruff check .
mypy src

# CLI de instalação de plugin, fim a fim manual
animaltrack plugin install ./plugins/metadata/fish-body-fat
animaltrack list-plugins            # confirma fish-body-fat-estimator descoberto
animaltrack plugin install <tmp-dir-com-plugin-de-teste>
animaltrack plugin list             # confirma plugin externo aparece

# pipeline fim a fim na fixture multi-entidade, inspeção manual do resultado
animaltrack run --workspace ./ws --profile fixture-multi-entity
#   -> inspecionar outputs/*.json: contar entity_id distintos (esperado >= 2)
```

---

## 7. Nota de prontidão para handoff

Esta fase é classificada como **menor risco de perda de handoff** em relação às fases anteriores (ex.
Fase 3): os 3 workstreams são pequenos, independentes e não compartilham arquivo — mesmo que uma sessão
perca contexto no meio de um workstream, o dano fica contido a esse workstream isolado (worktree
próprio), sem risco de deixar os outros dois workstreams num estado inconsistente.

Ainda assim, seguindo o protocolo obrigatório de handoff do `ARCHITECTURE.md`, cada workstream deve
gravar/atualizar seu `docs/handoffs/fase6-<workstream>-handoff.md` nos seguintes checkpoints (não só ao
final):

- **Workstream A (tracker spike)**:
  1. Checkpoint após fixture (a)+(b) e harness de métricas prontos (antes de implementar qualquer
     candidato) — é o ponto mais caro de refazer do zero se perdido.
  2. Checkpoint após cada candidato avaliado (1, depois 2, depois o time-boxed 3) — cada um é uma unidade
     independente de progresso.
  3. Checkpoint final com o relatório comparativo consolidado.
- **Workstream B (plugin de peixe)**:
  1. Checkpoint após `plugin.toml` + esqueleto de classe (antes de plugar a fórmula) — decisão do
     mecanismo de `[config]` (seção 2.4) deve ficar registrada aqui explicitamente, é o único ponto do
     plano que depende de confirmação externa (quem mantém o contrato de plugin).
  2. Checkpoint final com testes passando.
- **Workstream C (marketplace)**:
  1. Checkpoint após rascunho do `PLUGIN_CONTRACT.md` (antes de implementar a CLI) — permite revisão do
     conteúdo do contrato antes de código depender dele.
  2. Checkpoint final com `plugin install/list/remove` implementado e testado.

Ao final dos 3 workstreams, gravar handoff consolidado em `docs/handoffs/PROGRESS.md` marcando Fase 6
como concluída, com link para os 3 handoffs individuais e para o relatório de spike do tracker (que é o
único artefato desta fase com uma decisão pendente explícita — a escolha de algoritmo de produção — a ser
resolvida pelo dono do projeto em uma iteração futura, fora do escopo desta fase).
