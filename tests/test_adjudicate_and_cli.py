"""Adjudication triggers and the CLI wired end to end."""

import json
import subprocess
import sys
from pathlib import Path

from rubric_kit.adjudicate import find_disputes
from rubric_kit.labels import Label, LabelSet
from rubric_kit.spec import Rubric

RUBRIC = Rubric.load("configs/response-quality.yaml")


def labels_for(item: str, grader: str, scores: dict[str, int]) -> list[Label]:
    return [Label(item_id=item, grader_id=grader, dimension=k, score=v)
            for k, v in scores.items()]


def test_gate_flip_is_queued_even_when_scores_look_close():
    """Both graders call it a 4 on everything except truthfulness, where
    one says 3 and the other says 2. One point apart, under the numeric
    threshold, and yet the item flips from usable to capped. That is the
    dispute worth a human's time."""
    rows = labels_for("i1", "a", {"instruction_following": 4, "truthfulness": 3,
                                  "presentation": 4, "overall_quality": 4})
    rows += labels_for("i1", "b", {"instruction_following": 4, "truthfulness": 2,
                                   "presentation": 4, "overall_quality": 4})
    disputes = find_disputes(RUBRIC, LabelSet(rows))
    gate_flips = [d for d in disputes if d.dimension == "(gate)"]
    assert len(gate_flips) == 1
    assert "truthfulness=2" in gate_flips[0].reason
    assert not [d for d in disputes if d.dimension == "truthfulness"]


def test_wide_numeric_gap_is_queued():
    rows = labels_for("i2", "a", {"presentation": 5})
    rows += labels_for("i2", "b", {"presentation": 2})
    disputes = find_disputes(RUBRIC, LabelSet(rows))
    assert any(d.dimension == "presentation" and d.gap == 3 for d in disputes)


def test_agreeing_graders_produce_no_disputes():
    rows = labels_for("i3", "a", {"instruction_following": 4, "truthfulness": 4,
                                  "presentation": 4, "overall_quality": 4})
    rows += labels_for("i3", "b", {"instruction_following": 4, "truthfulness": 5,
                                   "presentation": 4, "overall_quality": 4})
    assert find_disputes(RUBRIC, LabelSet(rows)) == []


def test_cli_validate_rejects_off_scale_scores(tmp_path: Path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"item_id": "i", "grader_id": "g",
                               "dimension": "truthfulness", "score": 9}) + "\n")
    result = subprocess.run(
        [sys.executable, "-m", "rubric_kit.cli", "validate",
         "--rubric", "configs/response-quality.yaml", "--labels", str(bad)],
        capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "off the truthfulness scale" in result.stdout


def test_cli_report_end_to_end(tmp_path: Path):
    labels, gold = tmp_path / "l.jsonl", tmp_path / "g.jsonl"
    subprocess.run([sys.executable, "scripts/make_labels.py",
                    "--out", str(labels), "--gold-out", str(gold),
                    "--items", "60", "--seed", "5"], check=True)
    outdir = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "rubric_kit.cli", "report",
         "--rubric", "configs/response-quality.yaml",
         "--labels", str(labels), "--gold", str(gold), "--outdir", str(outdir)],
        capture_output=True, text=True, check=True)
    assert "queued for adjudication" in result.stdout

    summary = json.loads((outdir / "summary.json").read_text())
    assert set(summary["alpha"]) == {d.key for d in RUBRIC.dimensions}
    assert summary["calibration"]["sloppy"]["kappa"] < \
        summary["calibration"]["careful"]["kappa"]

    report = (outdir / "report.md").read_text()
    assert "Agreement by dimension" in report
    assert "Where to look first" in report
    disputes = (outdir / "disputes.jsonl").read_text().splitlines()
    assert len(disputes) == summary["disputes"]
