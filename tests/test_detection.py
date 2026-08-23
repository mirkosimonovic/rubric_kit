"""The test that justifies the whole repo.

Each simulated grader carries one planted defect. If the tool is
measuring what it claims to measure, the report names each of them
without being told which grader is which.
"""

import subprocess
import sys

import pytest

from rubric_kit.agreement import analyze_dimension
from rubric_kit.calibration import calibrate
from rubric_kit.labels import LabelSet
from rubric_kit.spec import Rubric

RUBRIC = Rubric.load("configs/response-quality.yaml")


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    out = tmp_path_factory.mktemp("labels")
    labels_path, gold_path = out / "labels.jsonl", out / "gold.jsonl"
    subprocess.run([sys.executable, "scripts/make_labels.py",
                    "--out", str(labels_path), "--gold-out", str(gold_path),
                    "--items", "150", "--seed", "91"], check=True)
    return LabelSet.load(labels_path), LabelSet.load(gold_path)


def calibration_for(data, grader):
    labels, gold = data
    return calibrate(labels, gold, grader, "instruction_following", [1, 2, 3, 4, 5])


def test_generous_grader_is_caught_as_biased_not_noisy(data):
    result = calibration_for(data, "generous")
    assert result.bias > 0.3, "planted upward bias went undetected"
    assert result.kappa.value > 0.6, "a biased grader still ranks items well"
    assert "generous" in result.verdict()


def test_sloppy_grader_is_caught_as_noise(data):
    result = calibration_for(data, "sloppy")
    assert result.kappa.value < 0.4
    assert "noise" in result.verdict()
    # and the interval is wide enough to be honest about it
    assert result.kappa.high - result.kappa.low > 0.1


def test_careful_grader_passes(data):
    result = calibration_for(data, "careful")
    assert abs(result.bias) < 0.25
    assert result.kappa.value > 0.75
    assert result.verdict() == "well calibrated"


def test_anchor_confusion_surfaces_on_the_right_dimension(data):
    """The planted defect is one grader who cannot tell anchor 3 from 4
    on instruction_following. The conditional swap rate should rank that
    pair first, even though 4-vs-5 disagreements are more numerous in
    raw count because 4s and 5s are simply more common scores."""
    labels, _ = data
    result = analyze_dimension(RUBRIC, labels, "instruction_following")
    top_low, top_high, rate, count = result.confusable_anchors[0]
    assert (top_low, top_high) == (3, 4), result.confusable_anchors
    assert rate > 0.1 and count > 20


def test_one_random_grader_drags_the_pool_alpha_down(data):
    """Four graders, one of them noise: alpha should land well under the
    0.667 line even though three of the four are fine. This is why pool
    alpha alone is a blunt instrument and the per-grader table exists."""
    labels, _ = data
    result = analyze_dimension(RUBRIC, labels, "instruction_following")
    assert result.alpha < 0.667
    assert "broken" in result.health() or "weak" in result.health()


def test_gold_labels_agree_with_themselves(data):
    """Sanity check on the harness itself: gold scored against gold must
    come out perfect, or the plumbing is wrong and every other number
    here is suspect."""
    _, gold = data
    result = calibrate(gold, gold, "gold", "truthfulness", [1, 2, 3, 4, 5])
    assert result.exact == 1.0
    assert result.bias == 0.0
    assert result.kappa.value == 1.0
