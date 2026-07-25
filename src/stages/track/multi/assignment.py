"""Estratégias de associação detecção→track (Fase 6, workstream A).

Duas estratégias comparadas pelo spike, ambas PURAS (sem `scipy`) para os plugins
`tracker` candidatos não arrastarem dependência nova:

- `greedy`: pega repetidamente o par (track, detecção) de menor custo global,
  fixa-o, remove linha/coluna, repete. Barato; pode trocar identidade quando dois
  tracks disputam a mesma detecção com custos parecidos (cenário do cruzamento).
- `hungarian`: assignment ótimo (minimiza custo total) via algoritmo húngaro
  O(n^3) sobre matriz quadrada (padding com custo 0 para linhas/colunas fictícias,
  que viram "sem-par"). Resolve melhor a disputa simultânea que o greedy.

Ambas recebem uma matriz de custo `cost[i][j]` (track i × detecção j) e um `gate`:
pares com custo `> gate` são proibidos (nunca casados). Retornam
`(matches, unmatched_tracks, unmatched_dets)`.
"""

from __future__ import annotations

import math

Matches = list[tuple[int, int]]
AssignmentResult = tuple[Matches, list[int], list[int]]


def greedy(cost: list[list[float]], gate: float) -> AssignmentResult:
    n_tracks = len(cost)
    n_dets = len(cost[0]) if cost else 0
    used_tracks: set[int] = set()
    used_dets: set[int] = set()
    matches: Matches = []

    # Lista de pares (custo, i, j) ordenada — greedy global.
    pairs = sorted(
        (cost[i][j], i, j)
        for i in range(n_tracks)
        for j in range(n_dets)
        if cost[i][j] <= gate
    )
    for _cost_value, i, j in pairs:
        if i in used_tracks or j in used_dets:
            continue
        matches.append((i, j))
        used_tracks.add(i)
        used_dets.add(j)

    unmatched_tracks = [i for i in range(n_tracks) if i not in used_tracks]
    unmatched_dets = [j for j in range(n_dets) if j not in used_dets]
    return matches, unmatched_tracks, unmatched_dets


def hungarian(cost: list[list[float]], gate: float) -> AssignmentResult:
    n_tracks = len(cost)
    n_dets = len(cost[0]) if cost else 0
    if n_tracks == 0 or n_dets == 0:
        return [], list(range(n_tracks)), list(range(n_dets))

    assignment = _hungarian_square(_pad_to_square(cost))

    matches: Matches = []
    used_tracks: set[int] = set()
    used_dets: set[int] = set()
    for i, j in enumerate(assignment):
        # Ignora linhas/colunas fictícias do padding e pares acima do gate.
        if i < n_tracks and j < n_dets and cost[i][j] <= gate:
            matches.append((i, j))
            used_tracks.add(i)
            used_dets.add(j)

    unmatched_tracks = [i for i in range(n_tracks) if i not in used_tracks]
    unmatched_dets = [j for j in range(n_dets) if j not in used_dets]
    return matches, unmatched_tracks, unmatched_dets


def _pad_to_square(cost: list[list[float]]) -> list[list[float]]:
    n = len(cost)
    m = len(cost[0]) if cost else 0
    size = max(n, m)
    # Padding com 0.0: um par com uma linha/coluna fictícia é "grátis", então o
    # ótimo global corresponde ao assignment parcial ótimo das linhas/colunas reais.
    return [[cost[i][j] if i < n and j < m else 0.0 for j in range(size)] for i in range(size)]


def _hungarian_square(a: list[list[float]]) -> list[int]:
    """Algoritmo húngaro (Kuhn-Munkres) por caminhos aumentantes, O(n^3).

    Implementação clássica com potenciais (u/v); `a` é n×n. Devolve `col_of_row`:
    `result[i] = j` significa linha i atribuída à coluna j. Referência canônica
    (e-maxx / cp-algorithms), adaptada para 0-indexado na saída.
    """
    n = len(a)
    inf = math.inf
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)  # p[j] = linha (1-idx) atribuída à coluna j
    way = [0] * (n + 1)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [inf] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = inf
            j1 = -1
            for j in range(1, n + 1):
                if not used[j]:
                    cur = a[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1

    result = [-1] * n
    for j in range(1, n + 1):
        if p[j] > 0:
            result[p[j] - 1] = j - 1
    return result
