# Rubric report: response-quality v1.2

120 items, 4 graders, 4 dimensions.

## Agreement by dimension

| dimension | alpha | exact match | reading |
|---|---|---|---|
| `instruction_following` | 0.378 | 39% | broken: graders are barely above coin flips on this dimension |
| `presentation` | 0.477 | 43% | weak: the rubric is doing less work than the graders' instincts |
| `truthfulness` | 0.497 | 44% | weak: the rubric is doing less work than the graders' instincts |
| `overall_quality` | 0.523 | 41% | weak: the rubric is doing less work than the graders' instincts |

Alpha is Krippendorff's, ordinal unless the dimension says otherwise. It reads on the usual scale: 0.8 solid, 0.667 the conventional floor for tentative conclusions, 0 means the graders are independent of each other.

### Where to look first

`instruction_following` has the weakest agreement. When anchor 3 or 4 was in play, graders landed on opposite sides 21% of the time (98 swaps). Those two anchor texts are not separating the cases they claim to.

> **3**: Covers the request but misses an explicit constraint like length or format.
> **4**: Follows the instruction including stated constraints.

## Graders against gold

| grader | n | exact | within 1 | bias | weighted kappa | reading |
|---|---|---|---|---|---|---|
| `sloppy` | 120 | 41% | 66% | -0.51 | 0.229 [0.056, 0.394] | noise: barely tracks gold, so the bias figure is an artifact rather than something to correct for |
| `generous` | 120 | 48% | 98% | +0.54 | 0.772 [0.687, 0.835] | systematically generous by 0.54 points, but ranks items sensibly |
| `anchor34` | 100 | 61% | 100% | -0.17 | 0.825 [0.730, 0.886] | well calibrated |
| `careful` | 120 | 72% | 100% | -0.01 | 0.889 [0.839, 0.928] | well calibrated |

Bias is signed and in scale points: positive means the grader scores above gold. Kappa intervals are a seeded percentile bootstrap over items, so two graders whose intervals overlap have not been shown to differ.

## Adjudication queue

721 disputes, 187 of them gate flips where one grader's scores trip a hard cap and another's do not. Gate flips are the expensive kind: they move an item between usable and discard.

| item | dimension | graders | scores | why |
|---|---|---|---|---|
| `item-0003` | `truthfulness` | careful vs sloppy | 5 vs 1 | 4-point gap on a 5-point scale |
| `item-0003` | `truthfulness` | generous vs sloppy | 5 vs 1 | 4-point gap on a 5-point scale |
| `item-0005` | `presentation` | generous vs sloppy | 5 vs 1 | 4-point gap on a 5-point scale |
| `item-0008` | `truthfulness` | careful vs sloppy | 5 vs 1 | 4-point gap on a 5-point scale |
| `item-0008` | `truthfulness` | generous vs sloppy | 5 vs 1 | 4-point gap on a 5-point scale |
| `item-0009` | `truthfulness` | generous vs sloppy | 5 vs 1 | 4-point gap on a 5-point scale |
| `item-0023` | `instruction_following` | anchor34 vs sloppy | 5 vs 1 | 4-point gap on a 5-point scale |
| `item-0023` | `instruction_following` | generous vs sloppy | 5 vs 1 | 4-point gap on a 5-point scale |
| `item-0032` | `truthfulness` | anchor34 vs sloppy | 5 vs 1 | 4-point gap on a 5-point scale |
| `item-0032` | `truthfulness` | careful vs sloppy | 5 vs 1 | 4-point gap on a 5-point scale |
| ... | | | | 711 more in `disputes.jsonl` |

