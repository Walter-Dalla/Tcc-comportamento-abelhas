"""fish-body-fat-estimator — plugin de METADATA de referência (espécie: peixe).

=============================== AVISO IMPORTANTE ===============================
A FÓRMULA ABAIXO É ILUSTRATIVA/PLACEHOLDER. **NÃO** é uma fórmula biológica
validada. Baseia-se apenas na ideia informal "gordura corporal em função de
velocidade de natação, duração de natação e tamanho do peixe" — nenhum dado de
domínio real foi fornecido. NÃO usar os valores produzidos por este plugin para
qualquer conclusão biológica real sem validação por um especialista em
biologia/fisiologia de peixes.
================================================================================

PROPÓSITO (Fase 6, workstream B): demonstrar (a) que o contrato `metadata`
generaliza para uma espécie diferente da abelha do TCC original e (b) o formato
completo de um plugin de terceiro (manifest + lógica + testes + README), servindo
de template copiável. Ver `docs/PLUGIN_CONTRACT.md`.

Demonstra três coisas que um autor de plugin precisa saber fazer:

1. **Consumir métrica de OUTRO plugin**: lê `average_speed` (produzida pelo plugin
   `speed`) via `ctx.get_metric(...)`, com `[ordering] after = ["speed"]` no
   manifest garantindo a ordem. O acesso é DEFENSIVO — métrica ausente faz o
   plugin pular com log, nunca levantar (schema versionado permite recusar).
2. **Receber configuração do usuário** que não é derivável da rota
   (`fish_length_cm`) — ver nota de decisão abaixo.
3. **Publicar métrica própria** via `ctx.add_metric(...)`.

--- NOTA DE DECISÃO: de onde vem `fish_length_cm` -----------------------------
A seção 2.4 do plano da Fase 6 propunha estender o `plugin.toml` com uma seção
`[config]`. **Não foi feito nesta fase, deliberadamente**: `PluginManifest` é
`extra="forbid"` e `from_toml` só lê as tabelas `[plugin]/[requires]/[ordering]` —
adicionar `[config]` exigiria mexer no schema e no discovery da Fase 2, o mesmo
tipo de mudança que a Fase 5 evitou (ver "débito de manifest" no PROGRESS.md).

Em vez disso o plugin usa o mecanismo que JÁ existe no contrato:
`Plugin.setup(PipelineContext)` dá acesso a `request.overrides`, um `dict[str, Any]`
livre carregado pelo `RunRequest`. Fallback para a variável de ambiente
`ANIMALTRACK_FISH_LENGTH_CM` cobre o caminho `run_cpu_analysis` (orquestração da
Fase 3), que roda plugins de metadata sem chamar `setup()`.

Formalizar `[config]` no manifest continua sendo a opção recomendada a prazo —
decisão pendente do dono do contrato de plugin, registrada no handoff.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from src.core.schema.result import AnalysisContext, AnalysisResult, Metric
from src.core.stages import MetadataPlugin

if TYPE_CHECKING:
    from src.core.pipeline import PipelineContext

log = logging.getLogger("animaltrack.plugin.fish-body-fat")

CONFIG_KEY = "fish_length_cm"
ENV_VAR = "ANIMALTRACK_FISH_LENGTH_CM"

# --- CONSTANTES DA FÓRMULA PLACEHOLDER (arbitrárias, não calibradas) ---------
BASE_PCT = 25.0
K_SPEED = 0.8
K_DURATION = 0.15
K_SIZE = 0.05


def _count_frames_with_position(result: AnalysisResult) -> int:
    """Nº de frames distintos com posição reconstruída em qualquer rota."""
    frames: set[int] = set()
    for route in result.routes:
        frames.update(route.points)
    return len(frames)


class FishBodyFatEstimator(MetadataPlugin):
    def __init__(self) -> None:
        self._fish_length_cm: float | None = None

    def setup(self, ctx: PipelineContext) -> None:
        """Lê `fish_length_cm` dos overrides do run (ver nota de decisão no módulo)."""
        raw = ctx.request.overrides.get(CONFIG_KEY)
        if raw is not None:
            self._fish_length_cm = self._coerce_length(raw)

    def run(self, ctx: AnalysisContext) -> None:
        # 1. métrica de entrada, produzida por outro plugin (`speed`).
        avg_speed = ctx.get_metric("average_speed")
        if avg_speed is None:
            # Acesso defensivo: pula com log, NÃO levanta — um plugin que não pode
            # calcular sua métrica não derruba o run dos demais.
            log.warning("fish-body-fat-estimator: métrica 'average_speed' ausente, pulando.")
            return
        if not isinstance(avg_speed.value, (int, float)) or isinstance(avg_speed.value, bool):
            log.warning(
                "fish-body-fat-estimator: 'average_speed' com valor não numérico (%r), pulando.",
                avg_speed.value,
            )
            return

        # 2. configuração obrigatória do usuário.
        fish_length_cm = self._resolve_fish_length()
        if fish_length_cm is None:
            # Falha LOCALIZADA e documentada: sem assumir um default enganoso para
            # um dado biológico. Sem métrica, sem exceção.
            log.warning(
                "fish-body-fat-estimator: '%s' não fornecido (nem em overrides do run, nem em %s), "
                "pulando — um default silencioso falsearia um dado medido.",
                CONFIG_KEY,
                ENV_VAR,
            )
            return

        fps = ctx.result.calibration.fps
        total_frames = _count_frames_with_position(ctx.result)
        swim_duration_min = (total_frames / fps) / 60.0 if fps > 0 else 0.0

        body_fat_pct = estimate_body_fat_pct(
            average_speed_cm_s=float(avg_speed.value),
            swim_duration_min=swim_duration_min,
            fish_length_cm=fish_length_cm,
        )

        ctx.add_metric(
            Metric(
                name="fish_body_fat_pct",
                value=body_fat_pct,
                unit="%",
                producer="fish-body-fat-estimator",
            )
        )

    # -- helpers -------------------------------------------------------------
    def _resolve_fish_length(self) -> float | None:
        if self._fish_length_cm is not None:
            return self._fish_length_cm
        return self._coerce_length(os.environ.get(ENV_VAR))

    @staticmethod
    def _coerce_length(raw: object) -> float | None:
        if raw is None:
            return None
        try:
            value = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            log.warning("fish-body-fat-estimator: '%s' inválido (%r), ignorado.", CONFIG_KEY, raw)
            return None
        if value <= 0:
            log.warning("fish-body-fat-estimator: '%s' deve ser > 0, recebeu %r.", CONFIG_KEY, value)
            return None
        return value


def estimate_body_fat_pct(
    *, average_speed_cm_s: float, swim_duration_min: float, fish_length_cm: float
) -> float:
    """FÓRMULA PLACEHOLDER — NÃO VALIDADA CIENTIFICAMENTE (ver aviso do módulo).

    Ideia informal: a gordura corporal cai com velocidade média alta (peixe ativo)
    e sobe com duração de natação e tamanho do peixe, dentro de faixas arbitrárias
    de calibração. Resultado é limitado (clamp) a [0, 100] por ser uma porcentagem.
    """
    raw = (
        BASE_PCT
        - K_SPEED * average_speed_cm_s
        + K_DURATION * swim_duration_min
        + K_SIZE * fish_length_cm
    )
    return max(0.0, min(100.0, raw))
