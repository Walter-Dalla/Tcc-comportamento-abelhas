"""Plugin `kinematics` (kind=metadata) — aceleração/jerk, virada, tortuosidade/MSD e
bouts de repouso/atividade.

Implementa as seções A-1 a A-4 de `docs/research/metadata-extraction-opportunities.md`
num único plugin novo (o próprio documento sugere agrupá-las em `plugins/kinematics/`,
já que todas derivam de `Route3D.points` + `Calibration.fps` e compartilham a MESMA
regra de buraco). `[ordering] after = ["speed"]` no manifest garante que a métrica
`speed` já exista quando este plugin roda — mas a série de velocidade é RECALCULADA
localmente (mesma fórmula do plugin `speed`) em vez de lida via `ctx.get_metric`, para
manter este plugin autocontido e defensivo caso `speed` tenha sido pulado por algum
motivo (ex. erro isolado pelo `PluginRegistry`).

Regra de buraco (comum às 4 seções, ver docstring do documento de pesquisa): `Route3D.points`
tem buracos (`dict[int, Point3D]` sem índices contíguos — oclusão/falha de detecção). Toda
derivada só é calculada entre índices CONSECUTIVOS (`idx - prev_idx == 1`); um salto nunca é
tratado como passo de 1 frame. Isso se aplica em cascata: aceleração precisa de 2 amostras de
velocidade consecutivas (== 3 frames de posição consecutivos); jerk precisa de 2 amostras de
aceleração consecutivas (== 4 frames de posição consecutivos); ângulo de virada precisa de 2
vetores de deslocamento consecutivos (== 3 frames de posição consecutivos); bouts fecham o
segmento corrente sempre que o índice de frame pula, mesmo que a classificação ativo/parado não
mude.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

from src.core.schema.geometry import Point3D
from src.core.schema.result import AnalysisContext, Metric
from src.core.stages import MetadataPlugin

# --- constantes com default documentado (não calibradas cientificamente) -------------

# A-2: limiar (graus) acima do qual um ângulo de virada é "curva fechada". Default
# arbitrário — o ideal seria configurável por perfil/espécie (fora de escopo aqui).
SHARP_TURN_THRESHOLD_DEG = 90.0

# A-2: histograma de ângulo de virada em 10 bins de 18° cobrindo 0-180°.
TURN_ANGLE_HISTOGRAM_BIN_COUNT = 10
TURN_ANGLE_HISTOGRAM_BIN_WIDTH_DEG = 180.0 / TURN_ANGLE_HISTOGRAM_BIN_COUNT

# A-3: teto de lag da curva de MSD, para limitar custo a O(n * teto) em vez de O(n²).
MSD_MAX_LAG_CAP = 100

# A-4: limiar de velocidade (cm/s) abaixo do qual um frame é classificado "parado".
# Default NÃO validado biologicamente — simples chute relativo à unidade cm/s, sem
# histerese (simplificação deliberada da sugestão do documento de pesquisa, que pede
# histerese; aceitável dado o prazo, mas deixa a classificação sensível a ruído perto
# do limiar).
REST_SPEED_THRESHOLD_CM_S = 0.5


class KinematicsPlugin(MetadataPlugin):
    def run(self, ctx: AnalysisContext) -> None:
        result = ctx.result
        route = next((r for r in result.routes if r.entity_id == 0), None)
        if route is None or not route.points:
            raise ValueError("KinematicsPlugin: nenhuma rota encontrada para entity_id=0")

        fps = result.calibration.fps
        dt = 1.0 / fps
        points = route.points
        indices = sorted(points)

        speed_by_frame = _speed_series(points, indices, dt)

        self._publish_acceleration_jerk(ctx, speed_by_frame, dt)
        self._publish_turn_metrics(ctx, points, indices, fps)
        self._publish_tortuosity(ctx, points, indices)
        self._publish_activity_bouts(ctx, speed_by_frame, indices, dt)

    # -- A-1: aceleração e jerk ----------------------------------------------------
    def _publish_acceleration_jerk(
        self, ctx: AnalysisContext, speed_by_frame: dict[int, float], dt: float
    ) -> None:
        acceleration = _derivative_series(speed_by_frame, dt)
        jerk = _derivative_series(acceleration, dt)

        if acceleration:
            values = list(acceleration.values())
            acceleration_max = max(values)
            # deceleração = magnitude positiva da aceleração mais negativa; clampada em
            # 0 quando não há nenhuma amostra negativa (não houve desaceleração real).
            deceleration_max = max(0.0, -min(values))
            acceleration_rms = math.sqrt(sum(v * v for v in values) / len(values))
        else:
            acceleration_max = 0.0
            deceleration_max = 0.0
            acceleration_rms = 0.0

        ctx.add_metric(
            Metric(
                name="acceleration",
                value=_stringify_keys(acceleration),
                unit="cm/s^2",
                producer="kinematics",
            )
        )
        ctx.add_metric(
            Metric(name="jerk", value=_stringify_keys(jerk), unit="cm/s^3", producer="kinematics")
        )
        ctx.add_metric(
            Metric(
                name="acceleration_max", value=acceleration_max, unit="cm/s^2", producer="kinematics"
            )
        )
        ctx.add_metric(
            Metric(
                name="deceleration_max",
                value=deceleration_max,
                unit="cm/s^2",
                producer="kinematics",
            )
        )
        ctx.add_metric(
            Metric(
                name="acceleration_rms",
                value=acceleration_rms,
                unit="cm/s^2",
                producer="kinematics",
            )
        )

    # -- A-2: direção, ângulo de virada e curvas fechadas ---------------------------
    def _publish_turn_metrics(
        self,
        ctx: AnalysisContext,
        points: dict[int, Point3D],
        indices: list[int],
        fps: float,
    ) -> None:
        turn_angle = _turn_angle_series(points, indices)

        histogram = {
            _histogram_bin_key(i): 0 for i in range(TURN_ANGLE_HISTOGRAM_BIN_COUNT)
        }
        for angle in turn_angle.values():
            bin_idx = min(
                int(angle // TURN_ANGLE_HISTOGRAM_BIN_WIDTH_DEG),
                TURN_ANGLE_HISTOGRAM_BIN_COUNT - 1,
            )
            histogram[_histogram_bin_key(bin_idx)] += 1

        sharp_turn_count = sum(1 for a in turn_angle.values() if a >= SHARP_TURN_THRESHOLD_DEG)

        # taxa por minuto, usando a faixa de índices de frame REALMENTE coberta pela
        # rota (não o nº de amostras de ângulo, que é menor que o nº de frames).
        if len(indices) >= 2 and fps > 0:
            duration_min = (indices[-1] - indices[0]) / fps / 60.0
        else:
            duration_min = 0.0
        sharp_turn_rate = sharp_turn_count / duration_min if duration_min > 0 else 0.0

        ctx.add_metric(
            Metric(
                name="turn_angle",
                value=_stringify_keys(turn_angle),
                unit="deg",
                producer="kinematics",
            )
        )
        ctx.add_metric(
            Metric(
                name="turn_angle_histogram",
                value=histogram,
                unit="count",
                producer="kinematics",
            )
        )
        ctx.add_metric(
            Metric(
                name="sharp_turn_count", value=sharp_turn_count, unit="count", producer="kinematics"
            )
        )
        ctx.add_metric(
            Metric(
                name="sharp_turn_rate",
                value=sharp_turn_rate,
                unit="turns/min",
                producer="kinematics",
            )
        )

    # -- A-3: tortuosidade, índice de retidão e MSD ---------------------------------
    def _publish_tortuosity(
        self, ctx: AnalysisContext, points: dict[int, Point3D], indices: list[int]
    ) -> None:
        if len(indices) < 2:
            net_displacement = 0.0
            straightness_index = 1.0
        else:
            p_first, p_last = points[indices[0]], points[indices[-1]]
            net_displacement = _dist(p_first, p_last)
            path_length = _path_length(points, indices)
            # guarda contra divisão por zero (caminho degenerado, sem passo contíguo
            # algum): reporta retidão máxima em vez de quebrar.
            straightness_index = net_displacement / path_length if path_length > 0 else 1.0

        msd_curve = _msd_curve(points, indices)
        msd_exponent = _msd_exponent(msd_curve)

        ctx.add_metric(
            Metric(
                name="net_displacement", value=net_displacement, unit="cm", producer="kinematics"
            )
        )
        ctx.add_metric(
            Metric(
                name="straightness_index",
                value=straightness_index,
                unit=None,
                producer="kinematics",
            )
        )
        ctx.add_metric(
            Metric(
                name="msd_curve",
                value=_stringify_keys(msd_curve),
                unit="cm^2",
                producer="kinematics",
            )
        )
        if msd_exponent is not None:
            ctx.add_metric(
                Metric(
                    name="msd_exponent", value=msd_exponent, unit=None, producer="kinematics"
                )
            )

    # -- A-4: bouts de repouso/atividade e latência ao primeiro movimento -----------
    def _publish_activity_bouts(
        self,
        ctx: AnalysisContext,
        speed_by_frame: dict[int, float],
        indices: list[int],
        dt: float,
    ) -> None:
        active_frames = sum(1 for s in speed_by_frame.values() if s >= REST_SPEED_THRESHOLD_CM_S)
        rest_frames = len(speed_by_frame) - active_frames
        total = active_frames + rest_frames
        active_fraction = active_frames / total if total > 0 else 0.0

        active_bouts = _bout_segments(speed_by_frame, lambda s: s >= REST_SPEED_THRESHOLD_CM_S)
        rest_bouts = _bout_segments(speed_by_frame, lambda s: s < REST_SPEED_THRESHOLD_CM_S)

        bout_count = len(active_bouts)
        if active_bouts:
            durations = [(end - start + 1) * dt for start, end in active_bouts]
            bout_duration_mean_s = sum(durations) / len(durations)
        else:
            bout_duration_mean_s = 0.0

        time_to_first_movement_s: float | None = None
        if active_bouts and indices:
            first_active_idx = active_bouts[0][0]
            time_to_first_movement_s = (first_active_idx - indices[0]) * dt

        ctx.add_metric(
            Metric(name="active_frames", value=active_frames, unit="frames", producer="kinematics")
        )
        ctx.add_metric(
            Metric(name="rest_frames", value=rest_frames, unit="frames", producer="kinematics")
        )
        ctx.add_metric(
            Metric(
                name="active_fraction", value=active_fraction, unit=None, producer="kinematics"
            )
        )
        ctx.add_metric(
            Metric(name="bout_count", value=bout_count, unit="count", producer="kinematics")
        )
        ctx.add_metric(
            Metric(
                name="bout_duration_mean_s",
                value=bout_duration_mean_s,
                unit="s",
                producer="kinematics",
            )
        )
        ctx.add_metric(
            Metric(
                name="time_to_first_movement_s",
                value=time_to_first_movement_s,
                unit="s",
                producer="kinematics",
            )
        )
        ctx.add_metric(
            Metric(
                name="rest_bouts",
                value=[list(pair) for pair in rest_bouts],
                unit=None,
                producer="kinematics",
            )
        )


# --- helpers puros (sem estado, testáveis isoladamente) -----------------------------


def _dist(p1: Point3D, p2: Point3D) -> float:
    return math.dist((p1.x, p1.y, p1.z), (p2.x, p2.y, p2.z))


def _speed_series(points: dict[int, Point3D], indices: list[int], dt: float) -> dict[int, float]:
    """Mesma fórmula do plugin `speed`: velocidade (cm/s) por par de frames CONSECUTIVOS,
    chaveada pelo frame mais recente do par. Recalculada aqui (não lida de `speed`'s
    métrica) para este plugin não depender de `speed` ter rodado com sucesso."""
    speed: dict[int, float] = {}
    for prev_idx, idx in zip(indices, indices[1:], strict=False):
        if idx - prev_idx != 1:
            continue
        speed[idx] = _dist(points[prev_idx], points[idx]) / dt
    return speed


def _derivative_series(series: dict[int, float], dt: float) -> dict[int, float]:
    """Derivada discreta genérica: usada tanto para velocidade->aceleração quanto para
    aceleração->jerk. Só calcula entre chaves CONSECUTIVAS (`idx - prev_idx == 1`) —
    para `series=speed_by_frame` isso automaticamente exige que os 3 frames de posição
    subjacentes também sejam consecutivos (cada chave de velocidade já representa um
    par contíguo)."""
    keys = sorted(series)
    out: dict[int, float] = {}
    for prev_idx, idx in zip(keys, keys[1:], strict=False):
        if idx - prev_idx != 1:
            continue
        out[idx] = (series[idx] - series[prev_idx]) / dt
    return out


def _turn_angle_series(points: dict[int, Point3D], indices: list[int]) -> dict[int, float]:
    """Ângulo (graus, 0=reta / 180=reversão total) entre os deslocamentos v1=p(i+1)-p(i)
    e v2=p(i+2)-p(i+1), para cada TRINCA de índices consecutivos. Chaveado pelo índice do
    frame do MEIO da trinca. Pula trincas com deslocamento de norma ~0 (direção
    indefinida) em vez de dividir por zero."""
    turn: dict[int, float] = {}
    for a, b, c in zip(indices, indices[1:], indices[2:], strict=False):
        if b - a != 1 or c - b != 1:
            continue
        p_a, p_b, p_c = points[a], points[b], points[c]
        v1 = (p_b.x - p_a.x, p_b.y - p_a.y, p_b.z - p_a.z)
        v2 = (p_c.x - p_b.x, p_c.y - p_b.y, p_c.z - p_b.z)
        n1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2 + v1[2] ** 2)
        n2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2 + v2[2] ** 2)
        if n1 < 1e-9 or n2 < 1e-9:
            continue
        dot = v1[0] * v2[0] + v1[1] * v2[1] + v1[2] * v2[2]
        cos_theta = max(-1.0, min(1.0, dot / (n1 * n2)))
        turn[b] = math.degrees(math.acos(cos_theta))
    return turn


def _histogram_bin_key(bin_idx: int) -> str:
    lo = int(bin_idx * TURN_ANGLE_HISTOGRAM_BIN_WIDTH_DEG)
    hi = int((bin_idx + 1) * TURN_ANGLE_HISTOGRAM_BIN_WIDTH_DEG)
    return f"{lo}-{hi}"


def _path_length(points: dict[int, Point3D], indices: list[int]) -> float:
    total = 0.0
    for prev_idx, idx in zip(indices, indices[1:], strict=False):
        if idx - prev_idx != 1:
            continue
        total += _dist(points[prev_idx], points[idx])
    return total


def _msd_curve(points: dict[int, Point3D], indices: list[int]) -> dict[int, float]:
    """Deslocamento quadrático médio por lag de frame. Para cada lag L, faz a média de
    |p(i+L) - p(i)|^2 sobre TODOS os pares (i, i+L) que existem em `points` — os dois
    índices só precisam existir individualmente, não fazer parte de uma corrida
    contígua (diferente das demais métricas deste plugin)."""
    if len(indices) < 2:
        return {}
    idx_set = set(indices)
    max_lag = min(MSD_MAX_LAG_CAP, (indices[-1] - indices[0]) // 2)
    curve: dict[int, float] = {}
    for lag in range(1, max_lag + 1):
        sq_sum = 0.0
        count = 0
        for i in idx_set:
            j = i + lag
            if j in idx_set:
                p1, p2 = points[i], points[j]
                sq_sum += (p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2 + (p2.z - p1.z) ** 2
                count += 1
        if count > 0:
            curve[lag] = sq_sum / count
    return curve


def _msd_exponent(msd_curve: dict[int, float]) -> float | None:
    """Ajusta log(MSD) ~= expoente*log(lag) + const via regressão linear simples.
    ~1 = difusivo, ~2 = balístico. `None` se houver menos de 3 pontos (lag, msd>0)
    utilizáveis — não força um ajuste sem sentido estatístico."""
    usable = [(lag, msd) for lag, msd in msd_curve.items() if msd > 0]
    if len(usable) < 3:
        return None
    log_lags = np.log(np.array([lag for lag, _ in usable], dtype=float))
    log_values = np.log(np.array([msd for _, msd in usable], dtype=float))
    slope, _intercept = np.polyfit(log_lags, log_values, 1)
    return float(slope)


def _bout_segments(
    speed_by_frame: dict[int, float], is_match: Callable[[float], bool]
) -> list[tuple[int, int]]:
    """Agrupa índices de frame (chaves de `speed_by_frame`, ordenadas) que satisfazem
    `is_match` em segmentos [início, fim] de índices CONSECUTIVOS. Um salto no índice de
    frame sempre fecha o segmento corrente — mesmo que a amostra seguinte também
    satisfaça `is_match` — para não fabricar continuidade sobre um buraco de detecção."""
    segments: list[tuple[int, int]] = []
    start: int | None = None
    end: int | None = None
    prev_key: int | None = None
    for idx in sorted(speed_by_frame):
        matched = is_match(speed_by_frame[idx])
        contiguous = prev_key is not None and idx - prev_key == 1
        if matched:
            if start is not None and contiguous:
                end = idx
            else:
                if start is not None:
                    segments.append((start, end))  # type: ignore[arg-type]
                start, end = idx, idx
        else:
            if start is not None:
                segments.append((start, end))  # type: ignore[arg-type]
                start, end = None, None
        prev_key = idx
    if start is not None:
        segments.append((start, end))  # type: ignore[arg-type]
    return segments


def _stringify_keys(series: dict[int, float]) -> dict[str, float]:
    """`Metric.value` exige `dict[str, Any]` (JsonSafeValue) — as séries internas deste
    módulo usam `int` como chave (mais natural para aritmética de índice de frame)."""
    return {str(k): v for k, v in series.items()}
