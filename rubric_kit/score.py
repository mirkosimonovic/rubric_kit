"""Turn per-dimension scores into one number, gates included.

The weighted average is the easy half. The gates are the half that
matters: a rubric that says "a false claim caps the item at 2" and then
computes a mean anyway isn't enforcing anything.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from rubric_kit.spec import Rubric


@dataclass
class Scored:
    raw: float                       # weighted average before gates
    final: int                       # after gates, rounded to the scale
    applied_gates: list[str] = field(default_factory=list)
    missing_dimensions: list[str] = field(default_factory=list)


def score_item(rubric: Rubric, scores: dict[str, int]) -> Scored:
    weighted_sum = 0.0
    total_weight = 0.0
    missing = []
    for dimension in rubric.dimensions:
        value = scores.get(dimension.key)
        if value is None:
            missing.append(dimension.key)
            continue
        if dimension.weight > 0:
            weighted_sum += value * dimension.weight
            total_weight += dimension.weight

    raw = weighted_sum / total_weight if total_weight else float("nan")
    if math.isnan(raw):  # nothing scorable was submitted for this item
        return Scored(raw=raw, final=min(rubric.overall_scale), missing_dimensions=missing)

    final = round(raw)
    applied = []
    for gate in rubric.gates:
        value = scores.get(gate.dimension)
        if value is not None and value <= gate.at_or_below and final > gate.caps_overall_at:
            final = gate.caps_overall_at
            applied.append(
                f"{gate.dimension}={value} caps overall at {gate.caps_overall_at}")

    low, high = min(rubric.overall_scale), max(rubric.overall_scale)
    final = max(low, min(high, final))
    return Scored(raw=raw, final=final, applied_gates=applied, missing_dimensions=missing)
