from __future__ import annotations


def cooperation_rate_per_round(history) -> list[float]:
    """
    Compute cooperation rate per round.

    We treat each directed action i->j as one decision.
    cooperation_rate = (# of "C") / (total actions) for that round.
    """
    rates: list[float] = []
    for tick in history:
        total = 0
        coop = 0
        for _, per_neighbor in tick.actions.items():
            for a in per_neighbor.values():
                total += 1
                if a == "C":
                    coop += 1
        rates.append(coop / total if total else 0.0)
    return rates


def final_wealth(history) -> dict[int, int]:
    """Convenience helper: wealth snapshot from the last tick."""
    if not history:
        return {}
    return dict(history[-1].wealth)


def resource_series(ticks) -> list[float]:
    """Extract post-step resource level series for Open Resources ticks."""
    return [float(tick.R_after) for tick in ticks]


def pool_series(ticks) -> list[float]:
    """Extract post-step governance pool level series for Open Resources ticks."""
    return [float(tick.P_after) for tick in ticks]


def collapse_time(ticks) -> int | None:
    """Return first tick.t where collapse flag is true, else None."""
    for tick in ticks:
        if bool(getattr(tick, "info", {}).get("collapsed")):
            return int(tick.t)
    return None


def gini(values: list[float]) -> float:
    """Compute Gini coefficient for non-negative values in pure Python."""
    if not values:
        return 0.0

    xs = [float(v) for v in values]
    n = len(xs)
    total = sum(xs)
    if n == 0 or total == 0.0:
        return 0.0

    xs_sorted = sorted(xs)
    weighted_sum = 0.0
    for i, x in enumerate(xs_sorted, start=1):
        weighted_sum += i * x

    g = (2.0 * weighted_sum) / (n * total) - (n + 1) / n
    return max(0.0, min(1.0, g))


def gini_final_wealth(ticks) -> float:
    """Gini coefficient over final wealth snapshot from Open Resources ticks."""
    if not ticks:
        return 0.0
    return gini([float(v) for v in ticks[-1].wealth.values()])
