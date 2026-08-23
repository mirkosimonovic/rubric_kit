"""Labels in long format: one row per (item, grader, dimension, score).

Long format because grading plans are ragged. Not every grader sees
every item, dimensions get added mid-project, and a wide matrix forces
you to decide what an empty cell means before you know.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel

from rubric_kit.spec import Rubric


class Label(BaseModel):
    item_id: str
    grader_id: str
    dimension: str
    score: int
    note: str = ""


class LabelSet:
    def __init__(self, labels: list[Label]):
        self.labels = labels
        self._index: dict[tuple[str, str, str], int] = {
            (label.item_id, label.dimension, label.grader_id): label.score
            for label in labels
        }

    @staticmethod
    def load(path: str | Path) -> LabelSet:
        rows = [
            Label(**json.loads(line))
            for line in Path(path).read_text().splitlines()
            if line.strip()
        ]
        return LabelSet(rows)

    def validate_against(self, rubric: Rubric) -> list[str]:
        """Catches the two mistakes that quietly poison a dataset: a
        score off the scale, and a dimension that no longer exists in
        the rubric because someone renamed it."""
        problems: list[str] = []
        known = {d.key: d for d in rubric.dimensions}
        for label in self.labels:
            dimension = known.get(label.dimension)
            if dimension is None:
                problems.append(
                    f"{label.item_id}/{label.grader_id}: unknown dimension "
                    f"{label.dimension!r}")
            elif label.score not in dimension.scale:
                problems.append(
                    f"{label.item_id}/{label.grader_id}: score {label.score} is "
                    f"off the {label.dimension} scale {dimension.scale}")
        return problems

    def graders(self) -> list[str]:
        return sorted({label.grader_id for label in self.labels})

    def items(self, dimension: str | None = None) -> list[str]:
        return sorted({
            label.item_id for label in self.labels
            if dimension is None or label.dimension == dimension
        })

    def score(self, item_id: str, dimension: str, grader_id: str) -> int | None:
        return self._index.get((item_id, dimension, grader_id))

    def matrix(self, dimension: str, graders: list[str] | None = None
               ) -> list[list[int | None]]:
        """Units by graders, None where a grader didn't score the item."""
        graders = graders or self.graders()
        return [
            [self.score(item, dimension, grader) for grader in graders]
            for item in self.items(dimension)
        ]

    def pairs(self, dimension: str, first: str, second: str) -> list[tuple[int, int]]:
        """Items both graders scored. Anything else can't be a pair."""
        out = []
        for item in self.items(dimension):
            a = self.score(item, dimension, first)
            b = self.score(item, dimension, second)
            if a is not None and b is not None:
                out.append((a, b))
        return out

    def by_item(self, dimension: str) -> dict[str, dict[str, int]]:
        grouped: dict[str, dict[str, int]] = defaultdict(dict)
        for label in self.labels:
            if label.dimension == dimension:
                grouped[label.item_id][label.grader_id] = label.score
        return dict(grouped)
