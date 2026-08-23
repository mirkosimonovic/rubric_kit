"""Synthetic grading data with known flaws baked in.

The point is testability. Each simulated grader has a defect the tool
is supposed to detect, so the test suite can assert the report actually
finds it instead of just running without crashing:

  gold      the truth
  careful   near-gold, occasional one-point wobble
  generous  correct ordering, roughly +0.8 points on everything
  sloppy    ignores the item 70% of the time and picks at random
  anchor34  fine everywhere except it cannot tell anchor 3 from 4 on
            instruction_following, which is the confusable-pair signal

Seeded, so the numbers in the committed example run are reproducible.
"""

from __future__ import annotations

import argparse
import json
import random

DIMENSIONS = ["instruction_following", "truthfulness", "presentation", "overall_quality"]


def clamp(value: int) -> int:
    return max(1, min(5, value))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="examples/labels.jsonl")
    parser.add_argument("--gold-out", default="examples/gold.jsonl")
    parser.add_argument("--items", type=int, default=120)
    parser.add_argument("--seed", type=int, default=23)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    labels: list[dict] = []
    gold: list[dict] = []

    for index in range(args.items):
        item_id = f"item-{index:04d}"
        truth = {dim: rng.choices([1, 2, 3, 4, 5], weights=[1, 2, 4, 5, 3])[0]
                 for dim in DIMENSIONS}

        for dim, score in truth.items():
            gold.append({"item_id": item_id, "grader_id": "gold",
                         "dimension": dim, "score": score})

        for dim, score in truth.items():
            careful = clamp(score + rng.choice([0, 0, 0, 0, 1, -1]))
            labels.append({"item_id": item_id, "grader_id": "careful",
                           "dimension": dim, "score": careful})

            generous = clamp(score + rng.choices([0, 1, 1, 2], weights=[3, 4, 2, 1])[0])
            labels.append({"item_id": item_id, "grader_id": "generous",
                           "dimension": dim, "score": generous})

            if rng.random() < 0.7:
                sloppy = rng.choice([1, 2, 3, 4, 5])
            else:
                sloppy = score
            labels.append({"item_id": item_id, "grader_id": "sloppy",
                           "dimension": dim, "score": sloppy})

            anchor = score
            if dim == "instruction_following" and score in (3, 4):
                anchor = rng.choice([3, 4])
            elif rng.random() < 0.1:
                anchor = clamp(score + rng.choice([1, -1]))
            labels.append({"item_id": item_id, "grader_id": "anchor34",
                           "dimension": dim, "score": anchor})

    # a realistic ragged plan: the fourth grader skips a slice of items
    labels = [row for row in labels
              if not (row["grader_id"] == "anchor34" and row["item_id"] < "item-0020")]

    with open(args.out, "w") as sink:
        sink.writelines(json.dumps(row) + "\n" for row in labels)
    with open(args.gold_out, "w") as sink:
        sink.writelines(json.dumps(row) + "\n" for row in gold)
    print(f"wrote {len(labels)} labels and {len(gold)} gold rows (seed {args.seed})")


if __name__ == "__main__":
    main()
