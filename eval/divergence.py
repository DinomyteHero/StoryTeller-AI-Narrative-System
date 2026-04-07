"""Divergence analysis — compare sessions for structural replayability.

Given two or more session telemetry logs from the same campaign with
different policies or seeds, measure how different the narrative outcomes are.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from state.telemetry import read_session_events, NarrativeEvent


@dataclass
class DivergenceReport:
    session_ids: list[str]
    total_turns_compared: int = 0
    scene_divergence: float = 0.0       # % of turns in different scenes
    npc_divergence: float = 0.0         # avg disposition difference at end
    thread_divergence: float = 0.0      # % of threads with different outcomes
    choice_divergence: float = 0.0      # % of turns with different choices
    overall_score: float = 0.0          # weighted average
    details: dict = field(default_factory=dict)


def _group_events_by_type(
    events: list[NarrativeEvent],
) -> dict[str, list[NarrativeEvent]]:
    """Group events by event_type."""
    groups: dict[str, list[NarrativeEvent]] = {}
    for e in events:
        groups.setdefault(e.event_type, []).append(e)
    return groups


def compare_sessions(session_id_a: str, session_id_b: str) -> DivergenceReport:
    """Compare two session telemetry logs for narrative divergence."""
    events_a = read_session_events(session_id_a)
    events_b = read_session_events(session_id_b)

    if not events_a or not events_b:
        return DivergenceReport(
            session_ids=[session_id_a, session_id_b],
            details={"error": "One or both sessions have no telemetry data"},
        )

    groups_a = _group_events_by_type(events_a)
    groups_b = _group_events_by_type(events_b)

    report = DivergenceReport(session_ids=[session_id_a, session_id_b])

    # Choice divergence: compare choice_made events by turn
    choices_a = {e.turn_number: e.event_data for e in groups_a.get("choice_made", [])}
    choices_b = {e.turn_number: e.event_data for e in groups_b.get("choice_made", [])}
    common_turns = set(choices_a.keys()) & set(choices_b.keys())
    report.total_turns_compared = len(common_turns)

    if common_turns:
        different_choices = sum(
            1 for t in common_turns
            if choices_a[t].get("choice_index") != choices_b[t].get("choice_index")
        )
        report.choice_divergence = different_choices / len(common_turns)

    # NPC disposition divergence: compare final disposition shifts
    npc_shifts_a = {}
    npc_shifts_b = {}
    for e in groups_a.get("npc_disposition_shift", []):
        npc_shifts_a[e.event_data.get("npc_name")] = e.event_data.get("new_value", 0.5)
    for e in groups_b.get("npc_disposition_shift", []):
        npc_shifts_b[e.event_data.get("npc_name")] = e.event_data.get("new_value", 0.5)

    common_npcs = set(npc_shifts_a.keys()) & set(npc_shifts_b.keys())
    if common_npcs:
        total_diff = sum(
            abs(npc_shifts_a[n] - npc_shifts_b[n]) for n in common_npcs
        )
        report.npc_divergence = total_diff / len(common_npcs)

    # Thread divergence: compare thread events
    threads_a = {e.event_data.get("thread_name") for e in events_a
                 if e.event_type.startswith("thread_")}
    threads_b = {e.event_data.get("thread_name") for e in events_b
                 if e.event_type.startswith("thread_")}
    all_threads = threads_a | threads_b
    if all_threads:
        resolved_a = {e.event_data.get("thread_name") for e in groups_a.get("thread_resolved", [])}
        resolved_b = {e.event_data.get("thread_name") for e in groups_b.get("thread_resolved", [])}
        different_outcomes = len(resolved_a.symmetric_difference(resolved_b))
        report.thread_divergence = different_outcomes / len(all_threads)

    # Dice outcome divergence
    dice_a = {e.turn_number: e.event_data for e in groups_a.get("dice_resolved", [])}
    dice_b = {e.turn_number: e.event_data for e in groups_b.get("dice_resolved", [])}
    dice_common = set(dice_a.keys()) & set(dice_b.keys())
    if dice_common:
        different_outcomes = sum(
            1 for t in dice_common
            if dice_a[t].get("outcome_quadrant") != dice_b[t].get("outcome_quadrant")
        )
        report.scene_divergence = different_outcomes / len(dice_common)

    # Overall weighted score
    report.overall_score = (
        report.choice_divergence * 0.3 +
        report.npc_divergence * 0.25 +
        report.thread_divergence * 0.25 +
        report.scene_divergence * 0.2
    )

    report.details = {
        "turns_compared": report.total_turns_compared,
        "common_npcs": list(common_npcs) if common_npcs else [],
        "all_threads": list(all_threads) if all_threads else [],
    }

    return report


def format_divergence_report(report: DivergenceReport) -> str:
    """Format a divergence report as human-readable text."""
    lines = [
        f"Divergence Analysis: {report.session_ids[0]} vs {report.session_ids[1]}",
        f"  Turns compared: {report.total_turns_compared}",
        f"  Choice divergence:  {report.choice_divergence:.1%}",
        f"  NPC divergence:     {report.npc_divergence:.3f}",
        f"  Thread divergence:  {report.thread_divergence:.1%}",
        f"  Scene divergence:   {report.scene_divergence:.1%}",
        f"  Overall score:      {report.overall_score:.3f}",
    ]
    return "\n".join(lines)
