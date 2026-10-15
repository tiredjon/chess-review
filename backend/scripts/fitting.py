"""Общее для скриптов подбора параметров: симплекс-метод Нелдера — Мида без зависимостей."""

from collections.abc import Callable


def nelder_mead(
    f: Callable[[list[float]], float], x0: list[float], steps: list[float], iterations: int = 400
) -> list[float]:
    """Минимум `f` от начальной точки `x0` с начальными шагами `steps` по координатам."""
    n = len(x0)
    simplex = [x0] + [[x + (steps[i] if i == j else 0) for i, x in enumerate(x0)] for j in range(n)]
    values = [f(x) for x in simplex]
    for _ in range(iterations):
        order = sorted(range(n + 1), key=lambda i: values[i])
        simplex, values = [simplex[i] for i in order], [values[i] for i in order]
        centroid = [sum(p[i] for p in simplex[:-1]) / n for i in range(n)]
        worst = simplex[-1]
        reflected = [c + (c - w) for c, w in zip(centroid, worst, strict=True)]
        fr = f(reflected)
        if fr < values[0]:
            expanded = [c + 2 * (c - w) for c, w in zip(centroid, worst, strict=True)]
            fe = f(expanded)
            simplex[-1], values[-1] = (expanded, fe) if fe < fr else (reflected, fr)
        elif fr < values[-2]:
            simplex[-1], values[-1] = reflected, fr
        else:
            contracted = [c + 0.5 * (w - c) for c, w in zip(centroid, worst, strict=True)]
            fc = f(contracted)
            if fc < values[-1]:
                simplex[-1], values[-1] = contracted, fc
            else:
                best = simplex[0]
                simplex = [best] + [
                    [b + 0.5 * (x - b) for b, x in zip(best, p, strict=True)] for p in simplex[1:]
                ]
                values = [values[0]] + [f(p) for p in simplex[1:]]
    return simplex[min(range(n + 1), key=lambda i: values[i])]
