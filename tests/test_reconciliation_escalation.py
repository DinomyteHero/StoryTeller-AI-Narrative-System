"""Selective reconciliation escalation — Tier 1 audit closure.

Verifies the two-strike escalation pattern:
1. First zero-delta turn → no escalation, counter increments to 1.
2. Second consecutive zero-delta turn → escalation to TIER_QUALITY, telemetry
   event emitted, counter resets to 0.
3. Non-zero-delta turn → counter resets to 0.
4. Quality run finds something the fast run missed → quality result wins.
5. Quality run also empty → fast result preserved (genuine quiet streak).
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.reconciliation import (
    ReconciliationResult,
    count_state_deltas,
    is_silent_reconciliation,
    reconcile_turn_with_escalation,
)
from gm.context import ArcState


@pytest.fixture
def empty_arc():
    return ArcState(
        campaign_name="Test",
        current_act=1,
        total_acts=4,
        act_name="Act I",
        act_progress=0.0,
        current_anchor="anchor",
        next_anchor="next",
        anchors_completed=[],
        throughline_question="?",
        tension_level=1,
        open_threads=[],
        closed_threads=[],
    )


@pytest.fixture
def telemetry_dir(tmp_path, monkeypatch):
    # The TELEMETRY_DIR module constant is read at import time, so we patch
    # the resolved attribute rather than the env var.
    import state.telemetry
    monkeypatch.setattr(state.telemetry, "TELEMETRY_DIR", tmp_path)
    return tmp_path


def _empty_result() -> ReconciliationResult:
    return ReconciliationResult()


def _result_with_thread() -> ReconciliationResult:
    r = ReconciliationResult()
    r.thread_updates = {
        "threads_advanced": ["a thread"],
        "threads_resolved": [],
        "threads_opened": [],
    }
    return r


def test_zero_delta_count_increments_without_escalation(empty_arc, telemetry_dir):
    with patch("engine.reconciliation.reconcile_turn", return_value=_empty_result()) as mock_recon:
        result, new_count, escalated = reconcile_turn_with_escalation(
            session_id="s1",
            turn_number=5,
            prior_zero_delta_count=0,
            narration="quiet turn",
            player_action="wait",
            check_result="",
            active_npcs=[],
            arc=empty_arc,
            spine_act={"anchor": "x", "expected_turns": [8, 12]},
            spine={"total_acts": 4},
        )
    assert new_count == 1
    assert escalated is False
    assert mock_recon.call_count == 1


def test_two_consecutive_zero_deltas_triggers_escalation(empty_arc, telemetry_dir):
    with patch("engine.reconciliation.reconcile_turn", return_value=_empty_result()) as mock_recon:
        result, new_count, escalated = reconcile_turn_with_escalation(
            session_id="s2",
            turn_number=6,
            prior_zero_delta_count=1,
            narration="quiet turn 2",
            player_action="wait",
            check_result="",
            active_npcs=[],
            arc=empty_arc,
            spine_act={"anchor": "x", "expected_turns": [8, 12]},
            spine={"total_acts": 4},
        )
    assert escalated is True
    assert new_count == 0
    assert mock_recon.call_count == 2  # fast + quality

    log_files = list(Path(telemetry_dir).glob("*.jsonl"))
    assert len(log_files) == 1
    contents = log_files[0].read_text(encoding="utf-8")
    assert "reconciliation_escalated" in contents


def test_quality_recovery_replaces_fast_result(empty_arc, telemetry_dir):
    """When fast returns empty but quality finds something, quality wins."""
    side = [_empty_result(), _result_with_thread()]

    def fake_recon(*args, **kwargs):
        return side.pop(0)

    with patch("engine.reconciliation.reconcile_turn", side_effect=fake_recon):
        result, new_count, escalated = reconcile_turn_with_escalation(
            session_id="s3",
            turn_number=7,
            prior_zero_delta_count=1,
            narration="actually busy turn",
            player_action="confront",
            check_result="",
            active_npcs=[],
            arc=empty_arc,
            spine_act={"anchor": "x", "expected_turns": [8, 12]},
            spine={"total_acts": 4},
        )
    assert escalated is True
    assert new_count == 0
    assert is_silent_reconciliation(result) is False
    assert result.thread_updates["threads_advanced"] == ["a thread"]


def test_non_zero_delta_resets_counter(empty_arc, telemetry_dir):
    with patch("engine.reconciliation.reconcile_turn", return_value=_result_with_thread()):
        result, new_count, escalated = reconcile_turn_with_escalation(
            session_id="s4",
            turn_number=8,
            prior_zero_delta_count=1,
            narration="busy turn",
            player_action="act",
            check_result="",
            active_npcs=[],
            arc=empty_arc,
            spine_act={"anchor": "x", "expected_turns": [8, 12]},
            spine={"total_acts": 4},
        )
    assert escalated is False
    assert new_count == 0


def test_both_tiers_empty_resets_counter(empty_arc, telemetry_dir):
    """Two-strike followed by quality-also-empty: streak is real, reset."""
    with patch("engine.reconciliation.reconcile_turn", return_value=_empty_result()):
        result, new_count, escalated = reconcile_turn_with_escalation(
            session_id="s5",
            turn_number=9,
            prior_zero_delta_count=1,
            narration="genuinely quiet",
            player_action="rest",
            check_result="",
            active_npcs=[],
            arc=empty_arc,
            spine_act={"anchor": "x", "expected_turns": [8, 12]},
            spine={"total_acts": 4},
        )
    assert escalated is True
    assert new_count == 0
    assert is_silent_reconciliation(result) is True
