"""The rubric as a data structure instead of a paragraph in a doc.

A rubric written in prose can't be validated, diffed, or pointed at by
a report. This one has dimensions with ordered anchors, weights, and
gates, so the tool can say "dimension `instruction_following` has the
worst agreement and graders keep confusing anchors 3 and 4" instead of
"agreement is low, good luck".
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class Dimension(BaseModel):
    key: str
    question: str
    scale: list[int]
    anchors: dict[int, str]            # score -> what that score means
    weight: float = 1.0
    metric: str = "ordinal"            # ordinal | nominal | interval

    @model_validator(mode="after")
    def check(self) -> Dimension:
        if len(self.scale) < 2:
            raise ValueError(f"{self.key}: a scale needs at least two points")
        if sorted(self.scale) != self.scale:
            raise ValueError(f"{self.key}: scale must be ascending")
        missing = [point for point in self.scale if point not in self.anchors]
        if missing:
            raise ValueError(
                f"{self.key}: scale points {missing} have no anchor text. "
                "Unanchored points are where graders invent their own meaning."
            )
        extra = [point for point in self.anchors if point not in self.scale]
        if extra:
            raise ValueError(f"{self.key}: anchors {extra} are off the scale")
        if self.metric not in ("ordinal", "nominal", "interval"):
            raise ValueError(f"{self.key}: unknown metric {self.metric!r}")
        return self


class Gate(BaseModel):
    """A hard cap: fail this dimension and the overall score can't
    exceed the cap no matter how good everything else looks. Real
    rubrics have these, and a weighted average silently ignores them."""

    dimension: str
    at_or_below: int
    caps_overall_at: int
    note: str = ""


class Rubric(BaseModel):
    name: str
    version: str
    overall_scale: list[int]
    dimensions: list[Dimension]
    gates: list[Gate] = Field(default_factory=list)
    adjudicate_when_gap_at_least: int = 2

    @model_validator(mode="after")
    def check(self) -> Rubric:
        keys = [d.key for d in self.dimensions]
        duplicates = {k for k in keys if keys.count(k) > 1}
        if duplicates:
            raise ValueError(f"duplicate dimension keys: {sorted(duplicates)}")
        for gate in self.gates:
            if gate.dimension not in keys:
                raise ValueError(f"gate points at unknown dimension {gate.dimension!r}")
            if gate.caps_overall_at not in self.overall_scale:
                raise ValueError(
                    f"gate on {gate.dimension} caps at {gate.caps_overall_at}, "
                    "which is off the overall scale"
                )
        if not any(d.weight > 0 for d in self.dimensions):
            raise ValueError("every dimension has zero weight, nothing would be scored")
        return self

    def dimension(self, key: str) -> Dimension:
        for dim in self.dimensions:
            if dim.key == key:
                return dim
        raise KeyError(key)

    @staticmethod
    def load(path: str | Path) -> Rubric:
        return Rubric(**yaml.safe_load(Path(path).read_text()))
