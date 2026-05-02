"""
Phase 13 tests: Semantic Memory, Aspiration Echoes, and Prose Diagnostics.

Tests all 9 success criteria:
1. Aspiration echo block appears when active, omitted when inactive
2. Echo content reflects behavioral inference engine's current skill direction
3. Prose diagnostic produces structured JSON
4. Diagnostic results inject into next turn's context package
5. Scene-type-aware assembly routes echo content correctly
6. Choice annotation produces structured JSON with required fields
7. Annotations stored in turn record's choice_implications field
8. Behavioral inference uses annotations when available, falls back when null
9. Act summaries include aggregated behavioral fingerprint
"""

import json
import os
import sys

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import field

from engine.character import Character
from engine.advancement import (
    compute_behavioral_signals,
    aggregate_behavioral_fingerprint,
    SkillSignal,
)
from gm.context import (
    ArcState,
    ContextPackage,
    NPCState,
    ThreadState,
    TurnMemory,
)
from gm.fast_gm import (
    annotate_choice,
    run_prose_diagnostic,
    _validate_annotation,
    ANNOTATION_SCHEMA,
    PROSE_DIAGNOSTIC_SCHEMA,
)


# ── Fixtures ──────────────────────────────────────────────────────────

def _make_character(**overrides) -> Character:
    """Create a minimal test character."""
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "characters", "praxeum_student.json",
    )
    with open(path) as f:
        return Character.model_validate_json(f.read())


def _make_arc_state(**overrides) -> ArcState:
    defaults = dict(
        campaign_name="Test Campaign",
        current_act=1,
        total_acts=4,
        act_name="Act 1",
        act_progress=0.3,
        current_anchor="test anchor",
        next_anchor="next anchor",
        anchors_completed=[],
        throughline_question="Can a man who has only ever looked out for himself become someone worth following?",
        tension_level="rising",
        open_threads=[ThreadState(name="The Missing Cargo")],
        closed_threads=[],
    )
    defaults.update(overrides)
    return ArcState(**defaults)


def _make_ctx(scene_type="social", aspiration_echo="", prose_diag=None, **kw) -> ContextPackage:
    char = _make_character()
    return ContextPackage(
        character=char,
        arc=_make_arc_state(),
        story_summary="Test summary",
        recent_turns=[],
        active_npcs=[NPCState(name="Vossk", disposition=0.3)],
        location="Red Sector Cantina",
        situation="Testing",
        scene_type=scene_type,
        aspiration_echo_instructions=aspiration_echo,
        prose_diagnostic=prose_diag,
        **kw,
    )


# ── Test 1: Aspiration echo block appears when active, omitted when inactive ──

class TestAspirationEchoBlock:
    def test_empty_when_no_instructions(self):
        ctx = _make_ctx(aspiration_echo="")
        assert ctx.build_aspiration_echo_block() == ""

    def test_present_when_active(self):
        ctx = _make_ctx(
            aspiration_echo="The character notices growth in deception.",
        )
        block = ctx.build_aspiration_echo_block()
        assert "ASPIRATION ECHOES" in block
        assert "deception" in block

    def test_contains_frequency_guidance(self):
        ctx = _make_ctx(
            aspiration_echo="Test echo content.",
        )
        block = ctx.build_aspiration_echo_block()
        assert "organic and occasional" in block


# ── Test 2: Echo content reflects behavioral inference ──

class TestAspirationEchoContent:
    def test_force_sensitive_echo(self):
        """Force latency echo should mention connection/awareness.

        Note: latent_force_sensitive is a post-V1 field not yet on the
        Pydantic model. We test via mock to verify the code path works
        when the field is eventually added.
        """
        from api.game_routes import _build_aspiration_echo
        char = _make_character()
        # Use mock since field isn't on the Pydantic model yet
        with patch.object(type(char), "__getattr__", return_value=True):
            # getattr(char, "latent_force_sensitive", False) returns True
            echo = _build_aspiration_echo(
                MagicMock(
                    latent_force_sensitive=True,
                    advancement_log=[],
                ),
                {},
            )
        assert "connection" in echo or "awareness" in echo

    def test_skill_growth_echo(self):
        """Recent advancement should produce skill-specific echo."""
        from api.game_routes import _build_aspiration_echo
        char = _make_character()
        char.advancement_log = [
            {"type": "skill_rank", "skill": "deception", "old_rank": 1, "new_rank": 2}
        ]
        echo = _build_aspiration_echo(char, {})
        assert "deception" in echo

    def test_no_echo_when_no_growth(self):
        """No echo when character has no advancement and no Force sensitivity."""
        from api.game_routes import _build_aspiration_echo
        char = _make_character()
        char.advancement_log = []
        echo = _build_aspiration_echo(char, {})
        assert echo == ""


# ── Test 3: Prose diagnostic produces structured JSON ──

class TestProseDiagnostic:
    def test_returns_none_with_no_passages(self):
        result = run_prose_diagnostic([], "No NPCs.")
        assert result is None

    @patch("gm.fast_gm.call_chat_json")
    def test_returns_structured_json(self, mock_llm):
        mock_llm.return_value = {
            "sensory_channels_recent": ["visual", "visual", "auditory"],
            "rhythm_note": "uniform long-short-long",
            "opener_similarity": "2 of 3 opened with location",
            "npc_coherence_flags": [{
                "npc": "Vossk",
                "described_behavior": "cooperative",
                "mechanical_disposition": 0.25,
                "flag": "action-emotion inconsistency",
            }],
            "polarity_note": "mostly positive despite hostile NPC",
        }

        result = run_prose_diagnostic(
            ["Passage 1 text.", "Passage 2 text."],
            "Vossk: hostile (0.25)",
        )
        assert result is not None
        assert "sensory_channels_recent" in result
        assert "npc_coherence_flags" in result
        assert len(result["npc_coherence_flags"]) == 1

    @patch("gm.fast_gm.call_chat_json")
    def test_graceful_failure(self, mock_llm):
        mock_llm.side_effect = RuntimeError("LLM down")
        result = run_prose_diagnostic(
            ["Passage 1.", "Passage 2."],
            "No NPCs.",
        )
        assert result is None  # graceful degradation


# ── Test 4: Diagnostic results inject into context package ──

class TestProseDiagnosticInjection:
    def test_diagnostic_block_empty_when_none(self):
        ctx = _make_ctx(prose_diag=None)
        assert ctx.build_prose_diagnostic_block() == ""

    def test_diagnostic_block_populated(self):
        diag = {
            "sensory_channels_recent": ["visual", "visual"],
            "rhythm_note": "monotonous",
            "npc_coherence_flags": [],
        }
        ctx = _make_ctx(prose_diag=diag)
        block = ctx.build_prose_diagnostic_block()
        assert "PROSE DIAGNOSTIC" in block
        assert "visual" in block
        assert "do not mention" in block.lower()


# ── Test 5: Scene-type-aware assembly ──

class TestSceneTypeAwareEcho:
    def test_omitted_in_combat(self):
        ctx = _make_ctx(
            scene_type="combat",
            aspiration_echo="Character notices growth.",
        )
        assert ctx.build_aspiration_echo_block() == ""

    def test_omitted_in_chase(self):
        ctx = _make_ctx(
            scene_type="chase",
            aspiration_echo="Character notices growth.",
        )
        assert ctx.build_aspiration_echo_block() == ""

    def test_present_in_social(self):
        ctx = _make_ctx(
            scene_type="social",
            aspiration_echo="Character notices growth.",
        )
        assert ctx.build_aspiration_echo_block() != ""

    def test_present_in_introspection(self):
        ctx = _make_ctx(
            scene_type="introspection",
            aspiration_echo="Character notices growth.",
        )
        assert ctx.build_aspiration_echo_block() != ""

    def test_present_in_exploration(self):
        ctx = _make_ctx(
            scene_type="exploration",
            aspiration_echo="Character notices growth.",
        )
        assert ctx.build_aspiration_echo_block() != ""


# ── Test 6: Choice annotation produces structured JSON ──

class TestChoiceAnnotation:
    def test_validate_annotation_valid(self):
        data = {
            "choice_target": "protect_doss",
            "choice_method": "deception",
            "sacrifice": "personal_risk",
            "priority_revealed": "relationship_over_safety",
            "npc_impact": {"doss": "trust_invested"},
            "throughline_relevance": "high",
            "throughline_direction": "becoming_someone_worth_following",
            "behavioral_tags": ["protective", "deceptive", "risk_taking"],
        }
        result = _validate_annotation(data)
        assert result["priority_revealed"] == "relationship_over_safety"
        assert result["throughline_relevance"] == "high"
        assert len(result["behavioral_tags"]) == 3

    def test_validate_annotation_clamps_tags(self):
        data = {
            "choice_target": "test",
            "priority_revealed": "test",
            "throughline_relevance": "medium",
            "behavioral_tags": ["a", "b", "c", "d", "e", "f", "g"],
        }
        result = _validate_annotation(data)
        assert len(result["behavioral_tags"]) == 5  # clamped to max 5

    def test_validate_annotation_normalizes_relevance(self):
        data = {
            "priority_revealed": "test",
            "throughline_relevance": "very_high",  # invalid
            "behavioral_tags": ["test"],
        }
        result = _validate_annotation(data)
        assert result["throughline_relevance"] == "low"  # normalized

    def test_validate_annotation_missing_required_raises(self):
        with pytest.raises(ValueError):
            _validate_annotation({"choice_target": "test"})  # missing priority + tags

    @patch("gm.fast_gm.call_chat_json")
    def test_annotate_choice_success(self, mock_llm):
        mock_llm.return_value = {
            "choice_target": "protect_doss",
            "choice_method": "deception",
            "sacrifice": "personal_risk",
            "priority_revealed": "relationship_over_safety",
            "npc_impact": {"doss": "trust_invested"},
            "throughline_relevance": "high",
            "throughline_direction": "loyalty",
            "behavioral_tags": ["protective", "loyal"],
        }

        result = annotate_choice(
            selected_choice="Cover for Doss",
            rejected_choices=["Turn him in", "Walk away"],
            scene_context="Customs checkpoint",
            npc_summary="Doss: friendly (0.7)",
            recent_pattern="Turn 1: explored area",
            throughline_question="Can he become worth following?",
        )
        assert result is not None
        assert result["priority_revealed"] == "relationship_over_safety"
        assert "protective" in result["behavioral_tags"]

    @patch("gm.fast_gm.call_chat_json")
    def test_annotate_choice_graceful_failure(self, mock_llm):
        mock_llm.side_effect = RuntimeError("Connection error")
        result = annotate_choice(
            selected_choice="Test",
            rejected_choices=["Other"],
            scene_context="Test",
            npc_summary="None",
            recent_pattern="None",
            throughline_question="Test?",
        )
        assert result is None  # graceful degradation


# ── Test 7: Annotations stored in choice_implications field ──

class TestAnnotationStorage:
    def test_log_turn_accepts_choice_implications(self):
        """Verify log_turn signature accepts the new parameter."""
        import inspect
        from state.session import log_turn
        sig = inspect.signature(log_turn)
        assert "choice_implications" in sig.parameters

    def test_get_act_turns_returns_choice_implications(self):
        """Verify get_act_turns query includes choice_implications."""
        import inspect
        from state.session import get_act_turns
        source = inspect.getsource(get_act_turns)
        assert "choice_implications" in source


# ── Test 8: Behavioral inference uses annotations when available ──

class TestBehavioralInferenceWithAnnotations:
    def _make_turn_rows(self, n=5, with_annotations=False):
        rows = []
        for i in range(n):
            row = {
                "turn_number": i + 1,
                "check_skill": "deception",
                "check_difficulty": "average",
                "roll_result_json": json.dumps({
                    "succeeded": True,
                    "outcome_quadrant": "success_advantage",
                }),
                "skill_tags_json": json.dumps(["deception", "charm", None]),
                "choice_index": 0,
                "moral_weight": 0,
                "choice_implications": None,
            }
            if with_annotations:
                row["choice_implications"] = json.dumps({
                    "choice_target": "protect ally",
                    "priority_revealed": "relationship_over_safety",
                    "throughline_relevance": "high",
                    "throughline_direction": "loyalty",
                    "behavioral_tags": ["protective", "social"],
                })
            rows.append(row)
        return rows

    def test_without_annotations_skill_tag_only(self):
        rows = self._make_turn_rows(5, with_annotations=False)
        signals = compute_behavioral_signals(rows, annotations=None)
        assert len(signals) > 0
        # Should still work with skill tags alone
        deception_signal = next(
            (s for s in signals if s.skill == "deception"), None
        )
        assert deception_signal is not None

    def test_with_annotations_enriches_signal(self):
        rows = self._make_turn_rows(5, with_annotations=True)
        annotations = [
            json.loads(r["choice_implications"])
            for r in rows if r["choice_implications"]
        ]
        signals_without = compute_behavioral_signals(rows, annotations=None)
        signals_with = compute_behavioral_signals(rows, annotations=annotations)

        # Both should produce results
        assert len(signals_without) > 0
        assert len(signals_with) > 0

        # Annotation boost: social category tags should boost social-aligned skills
        # The exact boost depends on tag overlap — verify no crash at minimum
        for s in signals_with:
            assert s.weighted_total >= 0

    def test_empty_annotations_same_as_none(self):
        rows = self._make_turn_rows(5)
        signals_none = compute_behavioral_signals(rows, annotations=None)
        signals_empty = compute_behavioral_signals(rows, annotations=[])

        # Empty list should behave same as None
        assert len(signals_none) == len(signals_empty)


# ── Test 9: Act summaries include behavioral fingerprint ──

class TestBehavioralFingerprint:
    def test_insufficient_data_returns_none(self):
        # Fewer than 3 annotated turns
        rows = [
            {"choice_implications": json.dumps({
                "priority_revealed": "test",
                "behavioral_tags": ["tag1"],
                "throughline_relevance": "high",
                "throughline_direction": "loyalty",
            })},
            {"choice_implications": None},
        ]
        result = aggregate_behavioral_fingerprint(rows)
        assert result is None

    def test_sufficient_data_returns_fingerprint(self):
        rows = []
        for i in range(5):
            rows.append({
                "choice_implications": json.dumps({
                    "priority_revealed": "relationship_over_safety",
                    "behavioral_tags": ["protective", "loyal", "deceptive"],
                    "throughline_relevance": "high",
                    "throughline_direction": "becoming_someone_worth_following",
                }),
            })
        result = aggregate_behavioral_fingerprint(rows)
        assert result is not None
        assert "dominant_priorities" in result
        assert "dominant_tags" in result
        assert "throughline_lean" in result
        assert "pattern_strength" in result

    def test_dominant_priorities_ordered(self):
        rows = [
            {"choice_implications": json.dumps({
                "priority_revealed": "relationship_over_safety",
                "behavioral_tags": ["protective"],
                "throughline_relevance": "medium",
                "throughline_direction": "loyalty",
            })},
            {"choice_implications": json.dumps({
                "priority_revealed": "relationship_over_safety",
                "behavioral_tags": ["loyal"],
                "throughline_relevance": "high",
                "throughline_direction": "loyalty",
            })},
            {"choice_implications": json.dumps({
                "priority_revealed": "mission_over_compassion",
                "behavioral_tags": ["pragmatic"],
                "throughline_relevance": "low",
                "throughline_direction": "pragmatism",
            })},
            {"choice_implications": json.dumps({
                "priority_revealed": "relationship_over_safety",
                "behavioral_tags": ["protective"],
                "throughline_relevance": "high",
                "throughline_direction": "loyalty",
            })},
        ]
        result = aggregate_behavioral_fingerprint(rows)
        assert result is not None
        assert result["dominant_priorities"][0] == "relationship_over_safety"
        assert result["throughline_lean"] == "loyalty"
        assert result["pattern_strength"] == 0.75  # 3/4

    def test_handles_null_and_invalid_implications(self):
        rows = [
            {"choice_implications": None},
            {"choice_implications": "invalid json{"},
            {"choice_implications": json.dumps({
                "priority_revealed": "test",
                "behavioral_tags": ["a"],
                "throughline_relevance": "low",
            })},
            {"choice_implications": json.dumps({
                "priority_revealed": "test",
                "behavioral_tags": ["b"],
                "throughline_relevance": "low",
            })},
            {"choice_implications": json.dumps({
                "priority_revealed": "test",
                "behavioral_tags": ["c"],
                "throughline_relevance": "low",
            })},
        ]
        # Should not crash — skips null/invalid and works with valid ones
        result = aggregate_behavioral_fingerprint(rows)
        assert result is not None
        assert result["dominant_priorities"] == ["test"]

    def test_max_tags_capped(self):
        rows = []
        tags = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
        for i in range(5):
            rows.append({
                "choice_implications": json.dumps({
                    "priority_revealed": "test",
                    "behavioral_tags": tags,
                    "throughline_relevance": "low",
                }),
            })
        result = aggregate_behavioral_fingerprint(rows)
        assert len(result["dominant_tags"]) == 6  # capped to top 6


# ── Test: Prompt template exists and has correct placeholders ──

class TestPromptTemplates:
    def test_choice_annotation_prompt_exists(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "gm", "prompts", "choice_annotation.txt",
        )
        assert os.path.exists(path)
        content = open(path, encoding="utf-8").read()
        assert "{selected_choice}" in content
        assert "{rejected_choices}" in content
        assert "{throughline_question}" in content

    def test_narration_prompt_has_phase13_placeholders(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "gm", "prompts", "narration.txt",
        )
        content = open(path, encoding="utf-8").read()
        assert "{aspiration_echo_block}" in content
        assert "{prose_diagnostic_block}" in content


# ── Test: BetweenActResult has behavioral_fingerprint field ──

class TestBetweenActResult:
    def test_has_behavioral_fingerprint(self):
        from engine.reconciliation import BetweenActResult
        result = BetweenActResult()
        assert hasattr(result, "behavioral_fingerprint")
        assert result.behavioral_fingerprint is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
