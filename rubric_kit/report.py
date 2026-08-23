"""Markdown report. The audience is whoever owns the rubric, so every
section ends in something they can act on: rewrite this anchor, retrain
this grader, label more items before trusting this number."""

from __future__ import annotations

from rubric_kit.adjudicate import Dispute
from rubric_kit.agreement import DimensionAgreement
from rubric_kit.calibration import Calibration
from rubric_kit.spec import Rubric


def render(rubric: Rubric, agreements: list[DimensionAgreement],
           calibrations: list[Calibration], disputes: list[Dispute],
           n_items: int) -> str:
    lines: list[str] = []
    push = lines.append

    push(f"# Rubric report: {rubric.name} v{rubric.version}")
    push("")
    push(f"{n_items} items, {agreements[0].n_graders if agreements else 0} graders, "
         f"{len(rubric.dimensions)} dimensions.")
    push("")

    push("## Agreement by dimension")
    push("")
    push("| dimension | alpha | exact match | reading |")
    push("|---|---|---|---|")
    for row in sorted(agreements, key=lambda a: a.alpha):
        push(f"| `{row.dimension}` | {row.alpha:.3f} | {row.percent:.0%} | {row.health()} |")
    push("")
    push("Alpha is Krippendorff's, ordinal unless the dimension says "
         "otherwise. It reads on the usual scale: 0.8 solid, 0.667 the "
         "conventional floor for tentative conclusions, 0 means the "
         "graders are independent of each other.")
    push("")

    worst = min(agreements, key=lambda a: a.alpha) if agreements else None
    if worst and worst.confusable_anchors:
        low, high, rate, count = worst.confusable_anchors[0]
        push("### Where to look first")
        push("")
        push(f"`{worst.dimension}` has the weakest agreement. When anchor "
             f"{low} or {high} was in play, graders landed on opposite "
             f"sides {rate:.0%} of the time ({count} swaps). Those two "
             "anchor texts are not separating the cases they claim to.")
        push("")
        push(f"> **{low}**: {rubric.dimension(worst.dimension).anchors[low]}")
        push(f"> **{high}**: {rubric.dimension(worst.dimension).anchors[high]}")
        push("")

    if calibrations:
        push("## Graders against gold")
        push("")
        push("| grader | n | exact | within 1 | bias | weighted kappa | reading |")
        push("|---|---|---|---|---|---|---|")
        for cal in sorted(calibrations, key=lambda c: c.kappa.value):
            push(f"| `{cal.grader_id}` | {cal.n} | {cal.exact:.0%} | "
                 f"{cal.adjacent:.0%} | {cal.bias:+.2f} | {cal.kappa} | "
                 f"{cal.verdict()} |")
        push("")
        push("Bias is signed and in scale points: positive means the "
             "grader scores above gold. Kappa intervals are a seeded "
             "percentile bootstrap over items, so two graders whose "
             "intervals overlap have not been shown to differ.")
        push("")

    if disputes:
        push("## Adjudication queue")
        push("")
        gate_flips = [d for d in disputes if d.dimension == "(gate)"]
        push(f"{len(disputes)} disputes, {len(gate_flips)} of them gate flips "
             "where one grader's scores trip a hard cap and another's do not. "
             "Gate flips are the expensive kind: they move an item between "
             "usable and discard.")
        push("")
        push("| item | dimension | graders | scores | why |")
        push("|---|---|---|---|---|")
        for dispute in disputes[:10]:
            push(f"| `{dispute.item_id}` | `{dispute.dimension}` | "
                 f"{dispute.graders[0]} vs {dispute.graders[1]} | "
                 f"{dispute.scores[0]} vs {dispute.scores[1]} | {dispute.reason} |")
        if len(disputes) > 10:
            push(f"| ... | | | | {len(disputes) - 10} more in `disputes.jsonl` |")
        push("")

    return "\n".join(lines) + "\n"
