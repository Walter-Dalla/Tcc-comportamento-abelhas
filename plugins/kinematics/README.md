# kinematics — plugin `metadata`

Implementa as seções A-1 a A-4 de
[`docs/research/metadata-extraction-opportunities.md`](../../docs/research/metadata-extraction-opportunities.md):
aceleração/jerk, direção/ângulo de virada, tortuosidade/MSD e bouts de repouso×atividade.
Todas derivam só de `Route3D.points` + `Calibration.fps` — nenhum dado novo é exigido.

## O que ele publica

| Grupo | Métricas | Unidade |
|---|---|---|
| A-1 aceleração/jerk | `acceleration`, `jerk` (séries por frame) | cm/s², cm/s³ |
| | `acceleration_max`, `deceleration_max`, `acceleration_rms` | cm/s² |
| A-2 virada | `turn_angle` (série), `turn_angle_histogram` (10 bins de 18°) | deg |
| | `sharp_turn_count`, `sharp_turn_rate` | count, turns/min |
| A-3 tortuosidade/MSD | `net_displacement`, `straightness_index` | cm, adimensional |
| | `msd_curve` (por lag), `msd_exponent` (omitido se <3 pontos utilizáveis) | cm², adimensional |
| A-4 repouso/atividade | `active_frames`, `rest_frames`, `active_fraction` | frames, adimensional |
| | `bout_count`, `bout_duration_mean_s`, `time_to_first_movement_s` | count, s, s |
| | `rest_bouts` (lista de `[início, fim]`) | — |

## Padrões que vale copiar

- **`[ordering] after = ["speed"]`** no manifest, mas a série de velocidade é
  **recalculada localmente** (mesma fórmula do plugin `speed`) em vez de lida via
  `ctx.get_metric` — mantém o plugin autocontido mesmo se `speed` tiver sido pulado.
- **Guarda de contiguidade em cascata**: toda derivada (velocidade→aceleração→jerk,
  par→trinca de deslocamento) só é calculada entre índices de frame CONSECUTIVOS.
  Um buraco na rota nunca vira um "passo de 1 frame" disfarçado.
- **Defaults não calibrados, documentados como tal**: `SHARP_TURN_THRESHOLD_DEG` (90°)
  e `REST_SPEED_THRESHOLD_CM_S` (0.5 cm/s, sem histerese) são constantes de módulo com
  comentário explícito — não pretendem ser biologicamente validadas.
- **Degrada, não quebra**: métricas escalares caem para `0.0`/`None` em dados
  insuficientes (ex. `msd_exponent` é omitido com <3 pontos); só a ausência total da
  rota levanta `ValueError` (mesma convenção de `SpeedPlugin`/`BorderPlugin`).
