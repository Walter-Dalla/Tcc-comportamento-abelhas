"""Filtro de Kalman de velocidade constante para um ponto 2D (Fase 6, workstream A).

Estado `x = [px, py, vx, vy]` (posição + velocidade), modelo de transição de
velocidade constante com `dt = 1` frame. Serve a UM propósito no spike: prever
onde uma entidade estará no próximo frame para (a) casar detecções com tracks por
proximidade da PREDIÇÃO (não da última observação crua) e (b) "segurar" a posição
de uma entidade ocluída por alguns frames, para reassociá-la ao MESMO `entity_id`
quando ela reaparece.

Implementação mínima e auto-contida em numpy (sem `filterpy`/`scipy`) — o objetivo
do spike é provar a interface, não entregar um estimador de produção afinado.
"""

from __future__ import annotations

import numpy as np


class KalmanPointTracker:
    """Kalman constante-velocidade para um centróide 2D."""

    def __init__(self, x: float, y: float, *, process_var: float = 1.0, meas_var: float = 1.0) -> None:
        # Estado inicial: posição observada, velocidade zero.
        self._x = np.array([x, y, 0.0, 0.0], dtype=float)
        # Transição (dt=1): posição += velocidade.
        self._F = np.array(
            [
                [1.0, 0.0, 1.0, 0.0],
                [0.0, 1.0, 0.0, 1.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
        # Observação: mede só posição.
        self._H = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])
        # Covariância inicial: posição relativamente certa, velocidade incerta.
        self._P = np.diag([meas_var, meas_var, 1000.0, 1000.0])
        self._Q = np.eye(4) * process_var
        self._R = np.eye(2) * meas_var

    def predict(self) -> tuple[float, float]:
        """Avança um frame e devolve a posição prevista `(x, y)`."""
        self._x = self._F @ self._x
        self._P = self._F @ self._P @ self._F.T + self._Q
        return float(self._x[0]), float(self._x[1])

    def update(self, x: float, y: float) -> None:
        """Corrige o estado com uma observação de posição."""
        z = np.array([x, y], dtype=float)
        y_res = z - self._H @ self._x
        s = self._H @ self._P @ self._H.T + self._R
        k = self._P @ self._H.T @ np.linalg.inv(s)
        self._x = self._x + k @ y_res
        self._P = (np.eye(4) - k @ self._H) @ self._P

    @property
    def position(self) -> tuple[float, float]:
        """Posição atual do estado `(x, y)` (após o último predict/update)."""
        return float(self._x[0]), float(self._x[1])
