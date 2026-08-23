"""Measure one grader against gold labels.

Accuracy alone hides the failure mode that actually costs you: a grader
who is consistently one point generous. Their exact-match rate looks
mediocre, their ordering of items is fine, and every threshold built on
their numbers is wrong. Bias is the number to look at, and it's signed
on purpose.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from rubric_kit.labels import LabelSet
from rubric_kit.stats import Estimate, bootstrap, cohens_kappa


@dataclass
class Calibration:
    grader_id: str
    dimension: str
    n: int
    exact: float                   # scored the same as gold
    adjacent: float                # within one point
    bias: float                    # mean signed error, + means generous
    mean_absolute_error: float
    kappa: Estimate
    confusion: dict[tuple[int, int], int] = field(default_factory=dict)

    def verdict(self, bias_tolerance: float = 0.4) -> str:
        """Noise gets checked before bias, and the order is the whole
        point. A grader who barely tracks gold will still show a bias
        number, because random answers drift toward the middle of the
        scale while real items don't sit there. That number is an
        artifact. Calling such a grader "harsh" invites someone to
        subtract half a point from their scores and ship the result,
        when the honest reading is that their scores carry almost no
        signal to correct.
        """
        if self.n < 20:
            return "too few gold items to judge"
        if self.kappa.value < 0.4:
            return ("noise: barely tracks gold, so the bias figure is an "
                    "artifact rather than something to correct for")
        if abs(self.bias) > bias_tolerance:
            direction = "generous" if self.bias > 0 else "harsh"
            return (f"systematically {direction} by {abs(self.bias):.2f} points, "
                    "but ranks items sensibly")
        if self.kappa.value < 0.6:
            return "moderate agreement with gold"
        return "well calibrated"


def calibrate(labels: LabelSet, gold: LabelSet, grader_id: str,
              dimension: str, scale: list[int] | None = None) -> Calibration:
    pairs: list[tuple[int, int]] = []
    for item in gold.items(dimension):
        truth = gold.score(item, dimension, gold.graders()[0]) \
            if len(gold.graders()) == 1 else None
        if truth is None:
            for grader in gold.graders():
                found = gold.score(item, dimension, grader)
                if found is not None:
                    truth = found
                    break
        given = labels.score(item, dimension, grader_id)
        if truth is not None and given is not None:
            pairs.append((truth, given))

    n = len(pairs)
    if n == 0:
        return Calibration(grader_id, dimension, 0, float("nan"), float("nan"),
                           float("nan"), float("nan"), Estimate(float("nan")))

    exact = sum(1 for truth, given in pairs if truth == given) / n
    adjacent = sum(1 for truth, given in pairs if abs(truth - given) <= 1) / n
    bias = sum(given - truth for truth, given in pairs) / n
    mae = sum(abs(given - truth) for truth, given in pairs) / n
    kappa = bootstrap(
        lambda data: cohens_kappa(data, "quadratic", scale), pairs, resamples=500)

    return Calibration(
        grader_id=grader_id, dimension=dimension, n=n, exact=exact,
        adjacent=adjacent, bias=bias, mean_absolute_error=mae, kappa=kappa,
        confusion=dict(Counter(pairs)),
    )
