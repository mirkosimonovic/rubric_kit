"""Scoring with gates. The gate tests matter more than the average:
getting a weighted mean right is arithmetic, while a gate that fails to
fire is a rubric that lies about what it enforces."""

from rubric_kit.score import score_item
from rubric_kit.spec import Rubric

RUBRIC = Rubric.load("configs/response-quality.yaml")


def test_gate_caps_an_otherwise_excellent_item():
    scores = {"instruction_following": 5, "truthfulness": 2,
              "presentation": 5, "overall_quality": 4}
    result = score_item(RUBRIC, scores)
    assert result.raw > 3.5           # the average says this is good
    assert result.final == 2          # the gate says otherwise
    assert "truthfulness=2" in result.applied_gates[0]


def test_no_gate_means_plain_weighted_average():
    scores = {"instruction_following": 4, "truthfulness": 4,
              "presentation": 5, "overall_quality": 4}
    result = score_item(RUBRIC, scores)
    assert result.applied_gates == []
    # weights 1.5, 1.5, 1.0, and overall_quality is weight 0 so it
    # is reported but never averaged in
    assert abs(result.raw - (4 * 1.5 + 4 * 1.5 + 5 * 1.0) / 4.0) < 1e-9
    assert result.final == 4


def test_gate_never_raises_a_score():
    scores = {"instruction_following": 1, "truthfulness": 1,
              "presentation": 1, "overall_quality": 1}
    result = score_item(RUBRIC, scores)
    assert result.final == 1          # already below the cap, stays there


def test_missing_dimensions_are_reported_not_guessed():
    result = score_item(RUBRIC, {"instruction_following": 4})
    assert "truthfulness" in result.missing_dimensions
    assert result.final == 4
