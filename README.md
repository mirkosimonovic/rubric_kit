# rubric-kit

Measures the people and models doing your grading. Point it at a rubric
and a pile of labels and it tells you which dimension your graders
disagree on, which two anchor texts are causing it, which grader runs
generous, and which one is just guessing.

I've spent a lot of hours on response-rating work across a few
platforms, and the thing that always went unmeasured was the rubric
itself. Everyone tracks throughput and pass rates. Almost nobody checks
whether two careful people reading the same anchor text land on the same
number, which is the assumption every downstream training decision rests
on.

## Quickstart

```bash
pip install -r requirements.txt
python scripts/make_labels.py                         # synthetic graders
python -m rubric_kit.cli validate --rubric configs/response-quality.yaml \
    --labels examples/labels.jsonl
python -m rubric_kit.cli report --rubric configs/response-quality.yaml \
    --labels examples/labels.jsonl --gold examples/gold.jsonl \
    --outdir examples/report
```

A committed run sits in `examples/report/` if you'd rather just read the
output. Here's the part of it that does the work:

```
| dimension               | alpha | exact | reading                          |
| `instruction_following` | 0.378 |  39%  | broken: barely above coin flips  |
| `presentation`          | 0.477 |  43%  | weak                             |
| `truthfulness`          | 0.497 |  44%  | weak                             |

Where to look first: when anchor 3 or 4 was in play on
instruction_following, graders landed on opposite sides 21% of the time
(98 swaps). Those two anchor texts are not separating the cases they
claim to.

  3: Covers the request but misses an explicit constraint like length or format.
  4: Follows the instruction including stated constraints.
```

That last bit is the whole design goal. A number that says agreement is
bad is worth very little. A number that hands you the two sentences to
rewrite is worth an afternoon.

## What it measures

**Agreement, three ways.** Percent agreement is reported because people
ask for it, and it flatters everyone: on a scale where most items are a
4, two graders who always answer 4 agree 70% of the time while knowing
nothing. Cohen's kappa subtracts that chance floor. Krippendorff's alpha
handles what kappa can't, which is more than two graders and graders who
skipped items, and it's what the report leads with.

**Confusable anchors.** For each pair of scale points, how often did two
graders land on opposite sides given that either point was in play. The
conditional part matters. Raw swap counts always crown 4-vs-5, because
4s and 5s are the most common scores on any real dataset, and that tells
you nothing about your anchor text.

**Calibration against gold**, per grader: exact match, within-one,
signed bias in scale points, quadratic-weighted kappa with a bootstrap
interval. Bias is signed on purpose. A grader who is reliably one point
generous has a mediocre exact-match rate, ranks items perfectly well,
and quietly breaks every threshold built on their numbers.

**Adjudication queue** with two triggers: a numeric gap past the
rubric's threshold, and a gate flip, where one grader's scores trip a
hard cap and another's don't. The second is the expensive kind. It can
fire on a one-point disagreement and it moves an item between "train on
this" and "throw it out".

## Rubrics are data here

```yaml
dimensions:
  - key: truthfulness
    question: Is everything asserted actually correct?
    scale: [1, 2, 3, 4, 5]
    weight: 1.5
    anchors:
      1: Contains a confident claim that is plainly false.
      ...
gates:
  - dimension: truthfulness
    at_or_below: 2
    caps_overall_at: 2
    note: False content cannot be rescued by presentation.
```

Validation rejects the mistakes that quietly poison a round: a scale
point with no anchor text (that's where graders invent their own
meaning), a gate pointing at a dimension somebody renamed, duplicate
keys, a cap that sits off the overall scale. Gates get enforced rather
than averaged away, which is the difference between a rubric that says
something and a rubric that computes a mean and hopes.

## How I know the numbers are right

The statistics are hand-rolled from the definitions, so they get checked
three ways.

Alpha and kappa each have a test that works the arithmetic out by hand
in the docstring and asserts the exact fraction. The alpha one is four
units and two graders, small enough to verify on paper in a minute.

Alpha is then fuzzed against the reference `krippendorff` package: 60
random annotation matrices per metric, three graders, a quarter of the
cells missing, asserting agreement to 1e-9. That test is why I trust the
implementation rather than merely believing it. The package is a
test-only dependency and the library imports nothing but the standard
library, pydantic, and pyyaml.

The last check is the interesting one. The synthetic grader generator
plants a specific defect in each simulated grader: one is 0.8 points
generous, one picks at random 70% of the time, one can't tell anchor 3
from anchor 4 on a single dimension. The tests assert that the report
names each defect without being told which grader is which, and CI
re-runs that on a seed nobody tuned against. A measurement tool that
can't recover a known answer has no business reporting an unknown one.

## Design notes

Noise gets diagnosed before bias, and that ordering was a real decision.
A grader who barely tracks gold still produces a bias number, because
random answers drift toward the middle of the scale while real items
don't sit there. Report bias first and someone will subtract half a
point from a random grader's scores and ship it. So a low kappa
short-circuits the verdict and says the bias figure is an artifact.

Bootstrap intervals are on by default and seeded. Kappa on 40 items
swings more than people expect, and two graders whose intervals overlap
have not been shown to differ. Reporting the point estimate alone is how
teams talk themselves into believing 0.61 and 0.52 are different
numbers.

Weighted kappa forgives adjacent confusion by design, which means a
grader who mixes up neighbouring anchors can still score well on it.
That's correct behavior and it's exactly why the confusable-anchor
diagnostic exists separately. The two measures catch different failures
and the report shows both.

## Layout

```
rubric_kit/
  spec.py          rubric schema, anchors, weights, gates, validation
  labels.py        long-format labels, ragged grading plans
  stats.py         percent agreement, cohen + weighted kappa, alpha, bootstrap
  agreement.py     per-dimension analysis and confusable anchors
  calibration.py   grader vs gold: bias, noise, and which is which
  adjudicate.py    dispute queue, numeric gaps and gate flips
  score.py         weighted average with gates actually enforced
  report.py        the markdown a rubric owner reads
  cli.py           validate, report, score
configs/response-quality.yaml   a real 4-dimension rubric with gates
scripts/make_labels.py          simulated graders with planted defects
examples/report/                a committed run
tests/                          31 tests, including the differential fuzz
```

Pairs with my [agent-eval-harness](https://github.com/mirkosimonovic/agent-eval-harness)
and [rlhf-data-pipeline](https://github.com/mirkosimonovic/rlhf-data-pipeline):
the harness produces model outputs to grade, this decides whether the
grading is trustworthy, and the pipeline consumes the labels that
survive.
