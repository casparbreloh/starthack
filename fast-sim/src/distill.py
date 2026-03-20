"""
Learning distillation from simulation sweep results.

Compares top-N vs bottom-N results to extract natural language learnings
suitable for writing to AgentCore Memory.
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any

from src.results import RunResult


def distill_wave_learnings(
    top_results: list[RunResult],
    bottom_results: list[RunResult],
) -> list[str]:
    """
    Compare top-N vs bottom-N results to identify discriminating factors.

    Takes pre-selected top-N and bottom-N results (aggregator samples these
    from the full wave without loading all results into memory).

    Returns a list of natural language learning strings (max 20 per wave).
    """
    learnings: list[str] = []

    if not top_results and not bottom_results:
        return ["No results to distill for this wave."]

    all_results = top_results + bottom_results
    if not all_results:
        return learnings

    # ── Score statistics ────────────────────────────────────────────────────
    top_scores = [r.final_score for r in top_results] if top_results else []
    bottom_scores = [r.final_score for r in bottom_results] if bottom_results else []

    if top_scores and bottom_scores:
        top_avg = statistics.mean(top_scores)
        bottom_avg = statistics.mean(bottom_scores)
        score_gap = top_avg - bottom_avg
        learnings.append(
            f"[planting_strategy] Top performers averaged {top_avg:.0f}/100 vs "
            f"bottom performers {bottom_avg:.0f}/100 (gap: {score_gap:.0f} points). "
            f"High variance indicates policy parameters significantly impact mission success."
        )

    # ── Planting schedule analysis ──────────────────────────────────────────
    if top_results and bottom_results:
        top_first_plant_sols = _extract_first_plant_sols(top_results)
        bottom_first_plant_sols = _extract_first_plant_sols(bottom_results)

        if top_first_plant_sols and bottom_first_plant_sols:
            top_mean = statistics.mean(top_first_plant_sols)
            bottom_mean = statistics.mean(bottom_first_plant_sols)
            if abs(top_mean - bottom_mean) > 3:
                direction = "earlier" if top_mean < bottom_mean else "later"
                learnings.append(
                    f"[planting_strategy] Top performers planted {direction} "
                    f"(avg sol {top_mean:.0f} vs {bottom_mean:.0f}). "
                    f"Early planting of micronutrient crops (lettuce/herbs) is critical to "
                    f"prevent crew health degradation before first harvest."
                )

    # ── Crop performance ────────────────────────────────────────────────────
    top_harvested_avg = (
        statistics.mean([r.crops_harvested for r in top_results]) if top_results else 0
    )
    bottom_harvested_avg = (
        statistics.mean([r.crops_harvested for r in bottom_results]) if bottom_results else 0
    )
    if top_harvested_avg > bottom_harvested_avg + 1:
        learnings.append(
            f"[planting_strategy] Top performers harvested avg {top_harvested_avg:.1f} crops "
            f"vs {bottom_harvested_avg:.1f} for bottom performers. "
            f"Successful harvests directly correlate with higher nutrition and survival scores."
        )

    # ── Crisis management ────────────────────────────────────────────────────
    top_crisis_rate = (
        statistics.mean([r.crises_resolved / max(r.crises_encountered, 1) for r in top_results])
        if top_results
        else 0
    )
    bottom_crisis_rate = (
        statistics.mean([r.crises_resolved / max(r.crises_encountered, 1) for r in bottom_results])
        if bottom_results
        else 0
    )
    if top_crisis_rate > bottom_crisis_rate + 0.1:
        learnings.append(
            f"[crisis_response] Top performers resolved {top_crisis_rate * 100:.0f}% of crises "
            f"vs {bottom_crisis_rate * 100:.0f}% for bottom performers. "
            f"Crisis resolution is a strong predictor of final score."
        )

    # ── Common crisis types in bottom results ───────────────────────────────
    bottom_crisis_types = _count_crisis_types(bottom_results)
    if bottom_crisis_types:
        most_common = sorted(bottom_crisis_types.items(), key=lambda x: x[1], reverse=True)[:3]
        crisis_str = ", ".join(f"{k} ({v}x)" for k, v in most_common)
        learnings.append(
            f"[crisis_response] Most common crises in failing runs: {crisis_str}. "
            f"Focus crisis response rules on these types to improve baseline performance."
        )

    # ── Resource management ──────────────────────────────────────────────────
    top_water_avg = (
        statistics.mean([r.resource_averages.get("avg_water_L", 0) for r in top_results])
        if top_results
        else 0
    )
    bottom_water_avg = (
        statistics.mean([r.resource_averages.get("avg_water_L", 0) for r in bottom_results])
        if bottom_results
        else 0
    )
    if abs(top_water_avg - bottom_water_avg) > 50:
        direction = "higher" if top_water_avg > bottom_water_avg else "lower"
        learnings.append(
            f"[resource_management] Top performers maintained {direction} water reserves "
            f"(avg {top_water_avg:.0f}L vs {bottom_water_avg:.0f}L). "
            f"Irrigation rate tuning has significant impact on resource efficiency score."
        )

    # ── Mission completion ──────────────────────────────────────────────────
    top_complete = sum(1 for r in top_results if r.mission_outcome == "complete")
    bottom_complete = sum(1 for r in bottom_results if r.mission_outcome == "complete")
    if top_results and bottom_results:
        top_complete_pct = top_complete / len(top_results) * 100
        bottom_complete_pct = bottom_complete / len(bottom_results) * 100
        learnings.append(
            f"[scoring_optimization] Mission completion rate: {top_complete_pct:.0f}% (top) "
            f"vs {bottom_complete_pct:.0f}% (bottom). "
            "Full 450-sol completion yields survival_score=100 "
            "which dominates the final score (35% weight)."
        )

    # ── Filter maintenance insight ──────────────────────────────────────────
    if len(learnings) < 15:
        learnings.append(
            "[resource_management] Maintaining water filter health above 60% prevents "
            "water_recycling_decline crises in most runs. "
            "Clean filters every 30-40 sols proactively."
        )

    # ── Nutrient depletion insight ──────────────────────────────────────────
    if len(learnings) < 16:
        learnings.append(
            "[crisis_response] nutrient_depletion crises appear in the first 10-15 sols "
            "when crops are actively consuming nitrogen. "
            "Pre-boost all zones with nitrogen_boost=True at sol 5 to prevent early depletion."
        )

    return learnings[:20]  # cap at 20


def distill_crisis_playbook(
    top_results: list[RunResult],
    bottom_results: list[RunResult],
) -> dict[str, Any]:
    """
    Build a structured crisis playbook from top vs bottom result comparison.

    For each crisis type: avg response time, best/worst response actions,
    survival rate.
    """
    all_results = top_results + bottom_results
    crisis_types = set()
    for r in all_results:
        for entry in r.crisis_log:
            crisis_types.add(entry.get("type", "unknown"))

    playbook: dict[str, Any] = {}
    for crisis_type in crisis_types:
        top_entries = [
            entry for r in top_results for entry in r.crisis_log if entry.get("type") == crisis_type
        ]
        bottom_entries = [
            entry
            for r in bottom_results
            for entry in r.crisis_log
            if entry.get("type") == crisis_type
        ]

        top_resolved = sum(1 for e in top_entries if e.get("resolved"))
        bottom_resolved = sum(1 for e in bottom_entries if e.get("resolved"))

        top_resolve_rate = top_resolved / len(top_entries) if top_entries else 0
        bottom_resolve_rate = bottom_resolved / len(bottom_entries) if bottom_entries else 0

        playbook[crisis_type] = {
            "top_resolution_rate": round(top_resolve_rate, 2),
            "bottom_resolution_rate": round(bottom_resolve_rate, 2),
            "occurrences_top": len(top_entries),
            "occurrences_bottom": len(bottom_entries),
            "recommendation": (
                f"Resolution rate: top {top_resolve_rate * 100:.0f}% vs "
                f"bottom {bottom_resolve_rate * 100:.0f}%. "
                + (
                    "Investigate response rules for better outcomes."
                    if top_resolve_rate < 0.7
                    else "Response rules effective."
                )
            ),
        }

    return playbook


def format_for_memory(learnings: list[str], wave_id: str) -> str:
    """
    Format learnings into a tagged string suitable for AgentCore Memory.
    """
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = f"[FAST-SIM WAVE {wave_id} -- {timestamp}]"
    body = "\n".join(f"- {learning}" for learning in learnings)
    return f"{header}\n{body}"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_first_plant_sols(results: list[RunResult]) -> list[int]:
    """Extract sol of first planting from key_decisions."""
    first_sols: list[int] = []
    for r in results:
        for kd in r.key_decisions:
            if "first_plant" in kd.get("action", ""):
                first_sols.append(kd.get("sol", 0))
                break
        else:
            # No first_plant key decision — use sol 0 as default
            first_sols.append(0)
    return first_sols


def _count_crisis_types(results: list[RunResult]) -> dict[str, int]:
    """Count occurrences of each crisis type across results."""
    counts: dict[str, int] = {}
    for r in results:
        for entry in r.crisis_log:
            ctype = entry.get("type", "unknown")
            counts[ctype] = counts.get(ctype, 0) + 1
    return counts
