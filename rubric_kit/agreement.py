"""Agreement per dimension, plus the diagnostics that make it useful.

A single alpha for the whole rubric tells you there's a problem. The
per-dimension breakdown tells you where, the confusable anchor pairs
tell you which two anchor texts read the same to graders, and that's a
rubric edit you can actually make on Monday.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations

from rubric_kit.labels import LabelSet
from rubric_kit.spec import Rubric
from rubric_kit.stats import (
    Estimate,
    bootstrap,
    cohens_kappa,
    krippendorff_alpha,
    percent_agreement,
)


@dataclass
class DimensionAgreement:
    dimension: str
    n_items: int
    n_graders: int
    alpha: float
    percent: float
    pairwise_kappa: dict[tuple[str, str], Estimate] = field(default_factory=dict)
    confusable_anchors: list[tuple[int, int, float, int]] = field(default_factory=list)

    def health(self) -> str:
        if self.alpha != self.alpha:
            return "not enough overlapping labels"
        if self.alpha >= 0.8:
            return "solid"
        if self.alpha >= 0.667:
            return "usable, treat conclusions as tentative"
        if self.alpha >= 0.4:
            return "weak: the rubric is doing less work than the graders' instincts"
        return "broken: graders are barely above coin flips on this dimension"


def analyze_dimension(rubric: Rubric, labels: LabelSet, dimension: str
                      ) -> DimensionAgreement:
    spec = rubric.dimension(dimension)
    graders = labels.graders()
    matrix = labels.matrix(dimension, graders)

    alpha = krippendorff_alpha(matrix, spec.metric)

    all_pairs: list[tuple[int, int]] = []
    pairwise: dict[tuple[str, str], Estimate] = {}
    for first, second in combinations(graders, 2):
        pairs = labels.pairs(dimension, first, second)
        if len(pairs) >= 5:
            pairwise[(first, second)] = bootstrap(
                lambda data: cohens_kappa(data, "quadratic", spec.scale),
                pairs, resamples=400)
            all_pairs.extend(pairs)

    confusable = _confusable_anchors(all_pairs, spec.scale)

    return DimensionAgreement(
        dimension=dimension,
        n_items=len(labels.items(dimension)),
        n_graders=len(graders),
        alpha=alpha,
        percent=percent_agreement(all_pairs),
        pairwise_kappa=pairwise,
        confusable_anchors=confusable,
    )


def _confusable_anchors(pairs: list[tuple[int, int]], scale: list[int],
                        min_swaps: int = 8) -> list[tuple[int, int, float, int]]:
    """Which two anchor texts read the same to graders.

    Raw swap counts answer the wrong question: 4-vs-5 tops that list on
    almost any real dataset because 4s and 5s are simply the most common
    scores. The useful number is conditional. Out of the times either
    anchor was in play, how often did the two graders land on opposite
    sides? That ratio finds the anchor pair whose wording is genuinely
    doing no work, which is the one to rewrite.
    """
    swaps: Counter[tuple[int, int]] = Counter()
    opportunities: Counter[tuple[int, int]] = Counter()
    for low in scale:
        for high in scale:
            if low >= high:
                continue
            for a, b in pairs:
                touches = a in (low, high) or b in (low, high)
                if not touches:
                    continue
                opportunities[(low, high)] += 1
                if {a, b} == {low, high}:
                    swaps[(low, high)] += 1

    scored = [
        (low, high, swaps[(low, high)] / opportunities[(low, high)], swaps[(low, high)])
        for (low, high) in opportunities
        if swaps[(low, high)] >= min_swaps
    ]
    scored.sort(key=lambda row: -row[2])
    return scored[:3]


def analyze(rubric: Rubric, labels: LabelSet) -> list[DimensionAgreement]:
    return [analyze_dimension(rubric, labels, d.key) for d in rubric.dimensions]
