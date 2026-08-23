"""Queue the items worth a tiebreak, with the reason attached.

Two triggers. A numeric gap past the rubric's threshold, and a gate
disagreement, where one grader's scores trip a hard cap and another's
don't. The second one is the expensive kind: it flips an item between
"train on this" and "throw it out", so it gets queued even when the
raw scores look close.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from rubric_kit.labels import LabelSet
from rubric_kit.score import score_item
from rubric_kit.spec import Rubric


@dataclass
class Dispute:
    item_id: str
    dimension: str
    graders: tuple[str, str]
    scores: tuple[int, int]
    gap: int
    reason: str


def find_disputes(rubric: Rubric, labels: LabelSet) -> list[Dispute]:
    disputes: list[Dispute] = []
    threshold = rubric.adjudicate_when_gap_at_least

    for dimension in rubric.dimensions:
        for item, scores in labels.by_item(dimension.key).items():
            for (first, a), (second, b) in combinations(sorted(scores.items()), 2):
                gap = abs(a - b)
                if gap >= threshold:
                    disputes.append(Dispute(
                        item_id=item, dimension=dimension.key,
                        graders=(first, second), scores=(a, b), gap=gap,
                        reason=f"{gap}-point gap on a {len(dimension.scale)}-point scale"))

    # gate flips: same item, different sides of a hard cap
    per_grader_scores: dict[str, dict[str, dict[str, int]]] = {}
    for label in labels.labels:
        per_grader_scores.setdefault(label.item_id, {}).setdefault(
            label.grader_id, {})[label.dimension] = label.score

    for item, graders in per_grader_scores.items():
        outcomes = {
            grader: score_item(rubric, scores)
            for grader, scores in graders.items()
        }
        for (first, left), (second, right) in combinations(sorted(outcomes.items()), 2):
            if bool(left.applied_gates) != bool(right.applied_gates):
                tripped = left if left.applied_gates else right
                disputes.append(Dispute(
                    item_id=item, dimension="(gate)",
                    graders=(first, second),
                    scores=(left.final, right.final),
                    gap=abs(left.final - right.final),
                    reason=f"gate disagreement: {tripped.applied_gates[0]}"))

    disputes.sort(key=lambda d: (-d.gap, d.item_id))
    return disputes
