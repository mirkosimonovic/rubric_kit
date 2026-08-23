"""Rubric validation. Every rejection here is a mistake I've watched
sink an annotation round: a scale point nobody wrote anchor text for, a
gate that quietly references a renamed dimension, two dimensions with
the same key so one silently shadows the other."""

import pytest
import yaml

from rubric_kit.spec import Rubric

BASE = {
    "name": "t", "version": "1", "overall_scale": [1, 2, 3],
    "dimensions": [{
        "key": "clarity", "question": "clear?", "scale": [1, 2, 3],
        "anchors": {1: "bad", 2: "ok", 3: "good"},
    }],
}


def test_valid_rubric_loads():
    rubric = Rubric(**BASE)
    assert rubric.dimension("clarity").weight == 1.0


def test_unanchored_scale_point_rejected():
    broken = yaml.safe_load(yaml.safe_dump(BASE))
    del broken["dimensions"][0]["anchors"][2]
    with pytest.raises(ValueError, match="no anchor text"):
        Rubric(**broken)


def test_gate_on_unknown_dimension_rejected():
    broken = dict(BASE, gates=[{"dimension": "truthiness",
                                "at_or_below": 2, "caps_overall_at": 2}])
    with pytest.raises(ValueError, match="unknown dimension"):
        Rubric(**broken)


def test_gate_capping_off_the_overall_scale_rejected():
    broken = dict(BASE, gates=[{"dimension": "clarity",
                                "at_or_below": 2, "caps_overall_at": 9}])
    with pytest.raises(ValueError, match="off the overall scale"):
        Rubric(**broken)


def test_duplicate_dimension_keys_rejected():
    broken = dict(BASE, dimensions=BASE["dimensions"] * 2)
    with pytest.raises(ValueError, match="duplicate dimension"):
        Rubric(**broken)


def test_shipped_rubric_is_valid():
    rubric = Rubric.load("configs/response-quality.yaml")
    assert len(rubric.gates) == 2
    for dimension in rubric.dimensions:
        assert set(dimension.anchors) == set(dimension.scale)
