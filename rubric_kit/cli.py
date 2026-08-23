"""Command line: validate, report, score.

  python -m rubric_kit.cli validate --rubric configs/response-quality.yaml
  python -m rubric_kit.cli report --rubric ... --labels ... --gold ... --outdir ...
  python -m rubric_kit.cli score --rubric ... --labels ... --grader careful
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from rubric_kit.adjudicate import find_disputes
from rubric_kit.agreement import analyze
from rubric_kit.calibration import calibrate
from rubric_kit.labels import LabelSet
from rubric_kit.report import render
from rubric_kit.score import score_item
from rubric_kit.spec import Rubric


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        rubric = Rubric.load(args.rubric)
    except Exception as error:  # noqa: BLE001 - yaml, io, and pydantic all
        print(f"rubric is invalid: {error}")
        return 1
    print(f"rubric ok: {rubric.name} v{rubric.version}, "
          f"{len(rubric.dimensions)} dimensions, {len(rubric.gates)} gates")

    if args.labels:
        problems = LabelSet.load(args.labels).validate_against(rubric)
        if problems:
            print(f"{len(problems)} label problems:")
            for problem in problems[:20]:
                print(f"  {problem}")
            return 1
        print("labels ok: every score is on a scale the rubric defines")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    rubric = Rubric.load(args.rubric)
    labels = LabelSet.load(args.labels)
    problems = labels.validate_against(rubric)
    if problems:
        print(f"refusing to report on invalid labels ({len(problems)} problems); "
              "run validate")
        return 1

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    agreements = analyze(rubric, labels)
    disputes = find_disputes(rubric, labels)

    calibrations = []
    if args.gold:
        gold = LabelSet.load(args.gold)
        scale = rubric.dimension(args.calibration_dimension).scale
        for grader in labels.graders():
            calibrations.append(
                calibrate(labels, gold, grader, args.calibration_dimension, scale))

    report = render(rubric, agreements, calibrations, disputes,
                    n_items=len(labels.items()))
    (outdir / "report.md").write_text(report)

    with (outdir / "disputes.jsonl").open("w") as sink:
        for dispute in disputes:
            sink.write(json.dumps(asdict(dispute)) + "\n")

    summary = {
        "rubric": f"{rubric.name} v{rubric.version}",
        "items": len(labels.items()),
        "graders": labels.graders(),
        "alpha": {a.dimension: round(a.alpha, 4) for a in agreements},
        "disputes": len(disputes),
        "calibration": {
            c.grader_id: {"n": c.n, "bias": round(c.bias, 3),
                          "kappa": round(c.kappa.value, 3),
                          "verdict": c.verdict()}
            for c in calibrations
        },
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    weakest = min(agreements, key=lambda a: a.alpha)
    print(f"alpha ranges {min(a.alpha for a in agreements):.3f} to "
          f"{max(a.alpha for a in agreements):.3f}; "
          f"weakest is {weakest.dimension} ({weakest.health()})")
    print(f"{len(disputes)} items queued for adjudication")
    print(f"wrote {outdir}/report.md, summary.json, disputes.jsonl")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    rubric = Rubric.load(args.rubric)
    labels = LabelSet.load(args.labels)
    gated = 0
    for item in labels.items():
        scores = {
            dimension.key: labels.score(item, dimension.key, args.grader)
            for dimension in rubric.dimensions
        }
        scores = {k: v for k, v in scores.items() if v is not None}
        if not scores:
            continue
        result = score_item(rubric, scores)
        if result.applied_gates:
            gated += 1
        print(json.dumps({"item_id": item, "raw": round(result.raw, 3),
                          "final": result.final, "gates": result.applied_gates}))
    print(f"# {gated} items were capped by a gate", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="rubric-kit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--rubric", required=True)
    validate.add_argument("--labels")
    validate.set_defaults(func=cmd_validate)

    report = subparsers.add_parser("report")
    report.add_argument("--rubric", required=True)
    report.add_argument("--labels", required=True)
    report.add_argument("--gold")
    report.add_argument("--outdir", required=True)
    report.add_argument("--calibration-dimension", default="instruction_following")
    report.set_defaults(func=cmd_report)

    score = subparsers.add_parser("score")
    score.add_argument("--rubric", required=True)
    score.add_argument("--labels", required=True)
    score.add_argument("--grader", required=True)
    score.set_defaults(func=cmd_score)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
