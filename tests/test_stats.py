"""Agreement statistics, checked three ways: arithmetic small enough to
do on paper, a differential fuzz against the reference implementation,
and behavioral properties that should hold for any correct version."""

import math

import pytest

from rubric_kit.stats import (
    bootstrap,
    cohens_kappa,
    krippendorff_alpha,
    percent_agreement,
)


def test_alpha_matches_hand_computation():
    """Four units, two graders, nominal metric, worked out by hand.

    Coincidences: o[1,1]=4, o[2,2]=2, o[1,2]=o[2,1]=1, so n_1=5, n_2=3,
    n=8. Observed disagreement is 2. Expected is n_1*n_2 twice = 30.
    alpha = 1 - (n-1) * 2/30 = 1 - 14/30 = 0.5333.
    """
    units = [[1, 1], [1, 1], [2, 2], [1, 2]]
    assert math.isclose(krippendorff_alpha(units, "nominal"), 1 - 14 / 30, rel_tol=1e-12)


def test_kappa_matches_hand_computation():
    """Two items on a 1-5 scale: one exact match at 3, one 1-vs-5 miss.

    Unweighted: observed disagreement 0.5, expected 0.75, kappa = 1/3.
    Quadratic: the maximum-distance miss keeps observed at 0.5 while
    shrinking expected to 0.375, so kappa = 1 - 4/3 = -1/3. Weighting
    changes both halves of the ratio, which is the part people get
    wrong when they assume weights can only help.
    """
    pairs = [(3, 3), (1, 5)]
    scale = [1, 2, 3, 4, 5]
    assert math.isclose(cohens_kappa(pairs, "unweighted", scale), 1 / 3, rel_tol=1e-12)
    assert math.isclose(cohens_kappa(pairs, "quadratic", scale), -1 / 3, rel_tol=1e-12)


@pytest.mark.parametrize("metric", ["nominal", "ordinal", "interval"])
def test_alpha_agrees_with_reference_implementation(metric):
    """Differential fuzz against the `krippendorff` package: 60 random
    annotation matrices per metric, three graders, a quarter of the
    cells missing. Any disagreement past floating-point noise is a bug
    in this file, and this is how I know the hand-rolled version is
    right rather than merely plausible."""
    numpy = pytest.importorskip("numpy")
    reference = pytest.importorskip("krippendorff")
    import random

    rng = random.Random(5)
    for _ in range(60):
        units = [
            [rng.choice([1, 2, 3, 4, 5]) if rng.random() > 0.25 else None
             for _ in range(3)]
            for _ in range(rng.randint(8, 25))
        ]
        matrix = numpy.full((3, len(units)), numpy.nan)
        for column, unit in enumerate(units):
            for row, value in enumerate(unit):
                if value is not None:
                    matrix[row, column] = value

        mine = krippendorff_alpha(units, metric)
        theirs = reference.alpha(reliability_data=matrix, level_of_measurement=metric)
        assert abs(mine - theirs) < 1e-9, (metric, mine, theirs)


def test_metrics_order_themselves_as_expected():
    """On ordered data, treating the scale as unordered throws away
    information, so nominal should never beat ordinal or interval."""
    units = [[1, 1, None], [2, 2, 3], [3, 3, 3], [2, 2, 2],
             [1, 2, 3], [4, 4, 4], [1, 1, 2], [None, 5, 5]]
    nominal = krippendorff_alpha(units, "nominal")
    ordinal = krippendorff_alpha(units, "ordinal")
    interval = krippendorff_alpha(units, "interval")
    assert nominal < ordinal
    assert nominal < interval


def test_perfect_agreement():
    perfect = [[3, 3, 3], [1, 1, 1], [5, 5, 5], [2, 2, 2]]
    assert krippendorff_alpha(perfect, "ordinal") == 1.0
    assert cohens_kappa([(a, b) for a, b, _ in perfect]) == 1.0


def test_kappa_punishes_the_lazy_majority_guesser():
    # 8 of 10 items are a 4 and both graders lean on it. Percent
    # agreement looks respectable, kappa does not, because guessing the
    # majority class earns nothing.
    pairs = [(4, 4)] * 8 + [(4, 3), (3, 4)]
    assert percent_agreement(pairs) == 0.8
    assert cohens_kappa(pairs) < 0.05


def test_weighting_rewards_near_misses():
    scale = [1, 2, 3, 4, 5]
    pairs = [(4, 5), (5, 4), (3, 4), (4, 3)] + [(i, i) for i in [1, 2, 3, 5, 1, 2]]
    plain = cohens_kappa(pairs, "unweighted", scale)
    linear = cohens_kappa(pairs, "linear", scale)
    quadratic = cohens_kappa(pairs, "quadratic", scale)
    assert plain < linear < quadratic


def test_bootstrap_interval_brackets_the_point_estimate():
    pairs = [(4, 4)] * 20 + [(3, 4)] * 5 + [(2, 3)] * 5 + [(1, 1)] * 10
    estimate = bootstrap(cohens_kappa, pairs, resamples=400)
    assert estimate.low <= estimate.value <= estimate.high
    assert estimate.n_units == 40
    again = bootstrap(cohens_kappa, pairs, resamples=400)
    assert (again.low, again.high) == (estimate.low, estimate.high)
