"""Agreement statistics, written out from the definitions.

Three measures live here and they answer different questions. Percent
agreement answers "how often did two graders type the same number", and
it flatters everyone: on a 5-point scale where 70% of items are a 4,
two graders who always guess 4 agree 70% of the time while knowing
nothing. Cohen's kappa subtracts that chance floor. Weighted kappa goes
further and admits that on an ordinal scale a 4-vs-5 disagreement is
smaller than a 1-vs-5, which is the whole reason rubrics have ordered
anchors. Krippendorff's alpha handles what the kappas can't: more than
two graders, graders who skipped items, and any of the three metrics.

No numpy. These run on annotation-sized data, the formulas are short,
and a reader can check them against the papers line by line.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass


@dataclass
class Estimate:
    """A point estimate with an optional bootstrap interval. Reporting
    kappa on 40 items without an interval is how teams talk themselves
    into believing a 0.61 and a 0.52 are different numbers."""

    value: float
    low: float | None = None
    high: float | None = None
    n_units: int = 0

    def __str__(self) -> str:
        if self.low is None:
            return f"{self.value:.3f}"
        return f"{self.value:.3f} [{self.low:.3f}, {self.high:.3f}]"


def percent_agreement(pairs: Sequence[tuple[int, int]]) -> float:
    if not pairs:
        return float("nan")
    return sum(1 for a, b in pairs if a == b) / len(pairs)


def _weight(i: int, j: int, categories: Sequence[int], scheme: str) -> float:
    """Disagreement weight: 0 when the graders match, 1 at opposite ends."""
    if scheme == "unweighted":
        return 0.0 if i == j else 1.0
    span = max(categories) - min(categories)
    if span == 0:
        return 0.0
    distance = abs(i - j) / span
    return distance if scheme == "linear" else distance ** 2


def cohens_kappa(pairs: Sequence[tuple[int, int]], scheme: str = "unweighted",
                 categories: Sequence[int] | None = None) -> float:
    """Cohen's kappa for two graders. scheme is unweighted, linear, or
    quadratic; the weighted forms only make sense on an ordinal scale."""
    if not pairs:
        return float("nan")
    if categories is None:
        categories = sorted({v for pair in pairs for v in pair})
    if len(categories) < 2:
        return float("nan")

    n = len(pairs)
    observed = Counter(pairs)
    rows = Counter(a for a, _ in pairs)
    cols = Counter(b for _, b in pairs)

    disagreement_observed = 0.0
    disagreement_expected = 0.0
    for i in categories:
        for j in categories:
            w = _weight(i, j, categories, scheme)
            if w == 0.0:
                continue
            disagreement_observed += w * observed.get((i, j), 0) / n
            disagreement_expected += w * (rows.get(i, 0) / n) * (cols.get(j, 0) / n)

    if disagreement_expected == 0:
        return float("nan")
    return 1 - disagreement_observed / disagreement_expected


def _ordinal_delta(values: Sequence[int], counts: dict[int, float]) -> Callable[[int, int], float]:
    """Krippendorff's ordinal difference: the squared mass of categories
    lying between the two ranks, so how far apart two scores are depends
    on how the data actually spread across the scale."""

    def delta(c: int, k: int) -> float:
        if c == k:
            return 0.0
        low, high = (c, k) if c < k else (k, c)
        between = sum(counts[g] for g in values if low <= g <= high)
        return (between - (counts[c] + counts[k]) / 2) ** 2

    return delta


def krippendorff_alpha(units: Iterable[Sequence[int | None]],
                       metric: str = "ordinal") -> float:
    """Alpha across any number of graders, missing values allowed.

    units is one row per item, one slot per grader, None where a grader
    didn't score that item. Rows with fewer than two scores carry no
    information about agreement and are skipped, which is the standard
    treatment and the reason alpha survives sparse annotation plans.
    """
    rows = [[v for v in unit if v is not None] for unit in units]
    rows = [row for row in rows if len(row) >= 2]
    if not rows:
        return float("nan")

    coincidence: dict[tuple[int, int], float] = {}
    for row in rows:
        weight = 1 / (len(row) - 1)
        for i, c in enumerate(row):
            for j, k in enumerate(row):
                if i == j:
                    continue
                coincidence[(c, k)] = coincidence.get((c, k), 0.0) + weight

    marginals: dict[int, float] = {}
    for (c, _), mass in coincidence.items():
        marginals[c] = marginals.get(c, 0.0) + mass
    total = sum(marginals.values())
    if total <= 1:
        return float("nan")

    values = sorted(marginals)
    if metric == "nominal":
        def delta(c: int, k: int) -> float:
            return 0.0 if c == k else 1.0
    elif metric == "interval":
        def delta(c: int, k: int) -> float:
            return float((c - k) ** 2)
    elif metric == "ordinal":
        delta = _ordinal_delta(values, marginals)
    else:
        raise ValueError(f"unknown metric {metric!r}")

    observed = sum(mass * delta(c, k) for (c, k), mass in coincidence.items())
    expected = sum(
        marginals[c] * marginals[k] * delta(c, k)
        for c in values for k in values
    )
    if expected == 0:
        return float("nan")
    return 1 - (total - 1) * observed / expected


def bootstrap(statistic: Callable[[Sequence], float], data: Sequence,
              resamples: int = 1000, seed: int = 17,
              confidence: float = 0.95) -> Estimate:
    """Percentile bootstrap over units. Seeded, so a report regenerated
    tomorrow shows the same interval as the one in yesterday's PR."""
    point = statistic(data)
    if not data or len(data) < 3:
        return Estimate(value=point, n_units=len(data))

    rng = random.Random(seed)
    draws: list[float] = []
    size = len(data)
    for _ in range(resamples):
        sample = [data[rng.randrange(size)] for _ in range(size)]
        value = statistic(sample)
        if not math.isnan(value):  # a resample can land on one category
            draws.append(value)
    if len(draws) < resamples // 10:
        return Estimate(value=point, n_units=size)

    draws.sort()
    tail = (1 - confidence) / 2
    low = draws[int(tail * len(draws))]
    high = draws[min(len(draws) - 1, int((1 - tail) * len(draws)))]
    return Estimate(value=point, low=low, high=high, n_units=size)
