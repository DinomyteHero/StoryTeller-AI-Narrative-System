"""
Physics guardrail tests — the validation gate between LLM output and
persistent narrative state, plus the cost-path changes that shipped with it.

Covers:
1. World registry — location validation against spine/ledger/passage
2. Visited-location ledger — provenance, dedupe, vocabulary growth
3. Fact grounding — ungrounded facts never reach persistent state
4. Reconciliation grounding — knowledge_gained filtered, knowledge_lost
   restricted to facts the NPC actually knew
5. Scene-state patch gate — _apply_narration_scene_state rejects invented
   locations and hallucinated known_facts
6. Dice-polarity post-check — Rule 4 enforcement wiring in the narration loop
7. Choices-only quality repair — quality failures no longer re-run narration
8. Prompt split — static system prompt, dynamic user prompt
9. Token usage accounting
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from engine.character import Character
from engine.dice import RollResult
from engine.world_registry import (
    ground_facts,
    location_vocabulary,
    record_location,
    significant_tokens,
    validate_proposed_location,
)
from gm.context import ArcState, ContextPackage, NPCState, ThreadState


# ── Fixtures ──────────────────────────────────────────────────────────

SPINE = {
    "acts": [
        {
            "number": 1,
            "name": "Arrivals",
            "opening_location": "Jedi Praxeum, dormitory wing, Yavin 4",
        },
    ],
}

PASSAGE_TAPPING = (
    "You follow Kira down past the archway. A light metallic tapping "
    "comes from below the sealed stairs, and Kira goes still beside you. "
    "The pull from the lower Massassi levels is stronger here."
)


def _make_character() -> Character:
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
        throughline_question="Can the student face what calls from below?",
        tension_level="rising",
        open_threads=[ThreadState(name="The Sealed Stairs")],
        closed_threads=[],
    )
    defaults.update(overrides)
    return ArcState(**defaults)


def _make_ctx(**kw) -> ContextPackage:
    defaults = dict(
        character=_make_character(),
        arc=_make_arc_state(),
        story_summary="Test summary",
        recent_turns=[],
        active_npcs=[NPCState(name="Kira Denn", disposition=0.5)],
        location="Jedi Praxeum, dormitory wing",
        situation="THE PLAYER CHOSE: pick the lock on the sealed stairs",
        scene_type="exploration",
    )
    defaults.update(kw)
    return ContextPackage(**defaults)


def _failed_roll() -> RollResult:
    return RollResult(
        net_successes=-2, succeeded=False, outcome_quadrant="failure_threat",
    )


VALID_NARRATION = (
    "The corridor narrows as you work the pick into the old lock. " * 25
    + "\n---CHOICES---\n"
    "1. Work the mechanism again, slower this time [Skulduggery]\n"
    "2. Step back and watch the stairwell from the archway\n"
)


# ── 1. Location validation ───────────────────────────────────────────

class TestLocationValidation:
    def test_canon_location_accepted(self):
        ok, source = validate_proposed_location(
            "the meditation hall of the Jedi Praxeum",
            spine=SPINE, arc_state={},
        )
        assert ok and source == "canon"

    def test_prior_location_refinement_accepted(self):
        ok, source = validate_proposed_location(
            "archway above the sealed stairs",
            spine=SPINE, arc_state={},
            prior_location="sealed stairs beneath the lower levels",
        )
        assert ok and source == "prior"

    def test_passage_grounded_new_location_accepted(self):
        ok, source = validate_proposed_location(
            "the Glass Wake's cargo hold",
            spine=SPINE, arc_state={},
            passage_text="You climb into the cargo hold of the Glass Wake.",
        )
        assert ok and source == "narration"

    def test_invented_location_rejected(self):
        ok, source = validate_proposed_location(
            "the lost city of Atlantis",
            spine=SPINE, arc_state={},
            prior_location="Jedi Praxeum dormitory",
            passage_text=PASSAGE_TAPPING,
        )
        assert not ok and source == ""

    def test_partial_passage_overlap_not_enough_for_new_ground(self):
        # One token grounded ("cargo"), the rest invented — must reject.
        ok, _ = validate_proposed_location(
            "the cargo vaults of Coruscant",
            spine=SPINE, arc_state={},
            passage_text="You drop the crate in the cargo bay.",
        )
        assert not ok


# ── 2. Visited-location ledger ───────────────────────────────────────

class TestVisitedLedger:
    def test_record_location_provenance(self):
        arc_state = {}
        record_location(arc_state, "Glass Wake cargo hold",
                        turn_number=3, source="narration")
        ledger = arc_state["visited_locations"]
        assert ledger == [
            {"name": "Glass Wake cargo hold", "turn": 3, "source": "narration"}
        ]

    def test_record_location_dedupes(self):
        arc_state = {}
        record_location(arc_state, "Glass Wake cargo hold",
                        turn_number=3, source="narration")
        record_location(arc_state, "glass wake CARGO hold",
                        turn_number=5, source="canon")
        assert len(arc_state["visited_locations"]) == 1

    def test_ledger_extends_vocabulary(self):
        """A location established once becomes canon for later turns."""
        arc_state = {}
        record_location(arc_state, "Glass Wake cargo hold",
                        turn_number=3, source="narration")
        ok, source = validate_proposed_location(
            "the Glass Wake's bridge",
            spine=SPINE, arc_state=arc_state,
        )
        assert ok and source == "canon"

    def test_vocabulary_includes_spine_and_ledger(self):
        arc_state = {"visited_locations": [{"name": "Tion shadowport"}]}
        vocab = location_vocabulary(SPINE, arc_state)
        assert "praxeum" in vocab
        assert "shadowport" in vocab


# ── 3. Fact grounding ────────────────────────────────────────────────

class TestFactGrounding:
    def test_grounded_fact_kept(self):
        grounded, dropped = ground_facts(
            ["Kira feels a pull from the lower Massassi levels"],
            PASSAGE_TAPPING,
        )
        assert len(grounded) == 1 and not dropped

    def test_hallucinated_fact_dropped(self):
        grounded, dropped = ground_facts(
            ["The Emperor is alive and hiding on Jakku"],
            PASSAGE_TAPPING,
        )
        assert not grounded and len(dropped) == 1

    def test_morphology_tolerance(self):
        # "tapping" in passage grounds "taps"; "sealed" grounds "seal"
        grounded, _ = ground_facts(
            ["Something taps behind the seal under the stairs"],
            PASSAGE_TAPPING,
        )
        assert len(grounded) == 1

    def test_unverifiable_fact_dropped(self):
        grounded, dropped = ground_facts(["It is."], PASSAGE_TAPPING)
        assert not grounded and dropped == ["It is."]

    def test_significant_tokens_filter_stopwords(self):
        tokens = significant_tokens("The pull from the lower levels")
        assert "the" not in tokens and "from" not in tokens
        assert "pull" in tokens and "lower" in tokens


# ── 4. Reconciliation grounding ──────────────────────────────────────

class TestReconciliationGrounding:
    def test_validate_result_drops_ungrounded_knowledge(self):
        from engine.reconciliation import _validate_result
        data = {
            "npc_updates": [{
                "npc_name": "Kira Denn",
                "knowledge_gained": [
                    "The player heard tapping below the sealed stairs",
                    "The Emperor is hiding on Jakku",
                ],
                "disposition_shift": 0.05,
            }],
            "thread_updates": {},
            "story_progress": {"anchor_proximity": "distant",
                               "progress_delta": 0.05},
        }
        result = _validate_result(data, narration=PASSAGE_TAPPING)
        gained = result.npc_updates[0]["knowledge_gained"]
        assert len(gained) == 1
        assert "tapping" in gained[0]

    def test_validate_result_without_narration_keeps_all(self):
        from engine.reconciliation import _validate_result
        data = {
            "npc_updates": [{
                "npc_name": "Kira Denn",
                "knowledge_gained": ["Anything at all"],
            }],
            "thread_updates": {},
            "story_progress": {"anchor_proximity": "distant",
                               "progress_delta": 0.05},
        }
        result = _validate_result(data)
        assert result.npc_updates[0]["knowledge_gained"] == ["Anything at all"]

    def test_knowledge_lost_only_removes_known_facts(self):
        from engine.reconciliation import apply_npc_updates
        npc = NPCState(name="Kira Denn", disposition=0.5)
        npc.knows = ["The stairs are sealed"]
        npc.doesnt_know = []
        apply_npc_updates(
            [{
                "npc_name": "Kira Denn",
                "knowledge_gained": [],
                "knowledge_lost": [
                    "The stairs are sealed",          # actually known
                    "The Custodian's true name",      # invented
                ],
                "disposition_shift": 0.0,
            }],
            [npc],
        )
        assert npc.knows == []
        assert npc.doesnt_know == ["The stairs are sealed"]


# ── 5. Scene-state patch gate ────────────────────────────────────────

class TestScenePatchGate:
    def _apply(self, state_patch, passage=PASSAGE_TAPPING):
        from api.game_routes import _apply_narration_scene_state
        from gm.cloud_gm import NarrationResult
        arc_state = {"current_location": "Jedi Praxeum, dormitory wing, Yavin 4"}
        current_act = {
            "opening_location": "Jedi Praxeum, dormitory wing, Yavin 4",
            "anchor": "arrivals",
            "anchor_description": "Reach the sealed stairs",
        }
        nr = NarrationResult(
            passage=passage,
            choices=["Go on", "Hold back"],
            skill_tags=[None, None],
            state_patch=state_patch,
        )
        _apply_narration_scene_state(
            arc_state=arc_state,
            current_act=current_act,
            npc_states=[],
            narration_result=nr,
            player_action="follow Kira down",
            scene_type="exploration",
            recent_turns=[],
            turn_number=2,
            spine=SPINE,
        )
        return arc_state

    def test_invented_location_rejected_falls_back(self):
        arc_state = self._apply({"current_location": "the lost city of Atlantis"})
        assert "atlantis" not in arc_state["scene_state"]["current_location"].lower()
        ledger = arc_state.get("visited_locations", [])
        assert not any("atlantis" in e["name"].lower() for e in ledger)

    def test_grounded_location_accepted_and_recorded(self):
        arc_state = self._apply(
            {"current_location": "archway above the sealed Massassi stairs"}
        )
        assert arc_state["scene_state"]["current_location"] == (
            "archway above the sealed Massassi stairs"
        )
        ledger = arc_state["visited_locations"]
        assert ledger[0]["name"] == "archway above the sealed Massassi stairs"
        assert ledger[0]["turn"] == 2

    def test_hallucinated_known_fact_dropped(self):
        arc_state = self._apply({
            "known_facts": [
                "A metallic tapping comes from below the sealed stairs",
                "The Emperor is hiding on Jakku",
            ],
        })
        facts = arc_state["scene_state"]["known_facts"]
        assert any("tapping" in f.lower() for f in facts)
        assert not any("emperor" in f.lower() for f in facts)


# ── 6. Dice-polarity post-check ──────────────────────────────────────

class TestNarrationPolarityUnit:
    @patch("gm.fast_gm.call_chat_json")
    def test_returns_verdict(self, mock_llm):
        from gm.fast_gm import check_narration_polarity
        mock_llm.return_value = {"depicted_outcome": "success"}
        verdict = check_narration_polarity(
            "You pick the lock and the door swings open.",
            "THE PLAYER CHOSE: pick the lock",
            outcome_label="FAILED (2 net failures)",
        )
        assert verdict == "success"

    @patch("gm.fast_gm.call_chat_json")
    def test_fail_open_on_error(self, mock_llm):
        from gm.fast_gm import check_narration_polarity
        mock_llm.side_effect = RuntimeError("LLM down")
        verdict = check_narration_polarity(
            "Passage.", "Situation.", outcome_label="FAILED",
        )
        assert verdict == "unclear"


class TestPolarityRetryWiring:
    def test_mismatch_triggers_narration_retry(self, monkeypatch):
        import gm.cloud_gm as cloud_gm

        monkeypatch.setattr(cloud_gm, "DICE_POLARITY_CHECK", True)
        monkeypatch.setattr(cloud_gm, "CHOICE_QUALITY_INLINE", False)

        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = VALID_NARRATION
        response.choices[0].finish_reason = "stop"
        response.usage = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response

        ctx = _make_ctx(roll_result=_failed_roll())

        with patch.object(cloud_gm, "_make_client",
                          return_value=(mock_client, "test-model")), \
             patch("gm.fast_gm.check_narration_polarity",
                   side_effect=["success", "failure"]) as mock_polarity:
            result = cloud_gm.narrate_turn(ctx, max_retries=1)

        assert mock_client.chat.completions.create.call_count == 2
        assert mock_polarity.call_count == 2
        assert len(result.choices) == 2

    def test_no_polarity_call_on_success(self, monkeypatch):
        import gm.cloud_gm as cloud_gm

        monkeypatch.setattr(cloud_gm, "DICE_POLARITY_CHECK", True)
        monkeypatch.setattr(cloud_gm, "CHOICE_QUALITY_INLINE", False)

        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = VALID_NARRATION
        response.choices[0].finish_reason = "stop"
        response.usage = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response

        succeeded = RollResult(net_successes=2, succeeded=True,
                               outcome_quadrant="success_advantage")
        ctx = _make_ctx(roll_result=succeeded)

        with patch.object(cloud_gm, "_make_client",
                          return_value=(mock_client, "test-model")), \
             patch("gm.fast_gm.check_narration_polarity") as mock_polarity:
            cloud_gm.narrate_turn(ctx, max_retries=1)

        mock_polarity.assert_not_called()


# ── 7. Choices-only quality repair ───────────────────────────────────

class TestChoiceRepair:
    @patch("gm.llm_client.call_chat")
    def test_regenerate_choices_unit(self, mock_chat):
        from gm.choice_validator import ChoiceQualityResult
        from gm.cloud_gm import NarrationResult, regenerate_choices

        mock_chat.return_value = (
            "1. Work the lock yourself — patience is cheaper than favors [Skulduggery]\n"
            "2. Buy a drink next door and watch who comes and goes\n"
        )
        original = NarrationResult(
            passage="A long passage. " * 40,
            choices=["Attack", "Defend"],
            skill_tags=[None, None],
        )
        quality = ChoiceQualityResult(
            specific=False, identity=False, risk=True,
            different=True, grounded=True,
        )
        repaired = regenerate_choices(_make_ctx(), original, quality)

        assert repaired is not None
        assert repaired.passage == original.passage
        assert len(repaired.choices) == 2
        assert repaired.skill_tags[0] is not None
        assert repaired.skill_tags[1] is None

    @patch("gm.llm_client.call_chat")
    def test_repair_failure_returns_none(self, mock_chat):
        from gm.choice_validator import ChoiceQualityResult
        from gm.cloud_gm import NarrationResult, regenerate_choices

        mock_chat.side_effect = RuntimeError("LLM down")
        original = NarrationResult(
            passage="A passage.", choices=["A", "B"], skill_tags=[None, None],
        )
        quality = ChoiceQualityResult(
            specific=False, identity=False, risk=True,
            different=True, grounded=True,
        )
        assert regenerate_choices(_make_ctx(), original, quality) is None

    def test_quality_failure_repairs_choices_not_narration(self, monkeypatch):
        import gm.cloud_gm as cloud_gm
        from gm.choice_validator import ChoiceQualityResult
        from gm.cloud_gm import NarrationResult

        monkeypatch.setattr(cloud_gm, "DICE_POLARITY_CHECK", False)
        monkeypatch.setattr(cloud_gm, "CHOICE_QUALITY_INLINE", True)

        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = VALID_NARRATION
        response.choices[0].finish_reason = "stop"
        response.usage = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = response

        failing = ChoiceQualityResult(
            specific=False, identity=False, risk=True,
            different=True, grounded=True,
        )
        passing = ChoiceQualityResult(
            specific=True, identity=True, risk=True,
            different=True, grounded=True,
        )
        repaired = NarrationResult(
            passage="kept passage",
            choices=["Better choice one", "Better choice two"],
            skill_tags=[None, None],
        )

        with patch.object(cloud_gm, "_make_client",
                          return_value=(mock_client, "test-model")), \
             patch("gm.choice_validator.validate_choice_quality",
                   side_effect=[failing, passing]), \
             patch.object(cloud_gm, "regenerate_choices",
                          return_value=repaired) as mock_repair:
            result = cloud_gm.narrate_turn(_make_ctx(), max_retries=2)

        # Narration generated exactly once — the repair handled quality.
        assert mock_client.chat.completions.create.call_count == 1
        mock_repair.assert_called_once()
        assert result.choices == ["Better choice one", "Better choice two"]


# ── 8. Prompt split for prefix caching ───────────────────────────────

class TestPromptSplit:
    def test_system_prompt_static_across_contexts(self):
        from gm.cloud_gm import _build_prompts
        sys1, _ = _build_prompts(_make_ctx())
        sys2, _ = _build_prompts(_make_ctx(
            situation="THE PLAYER CHOSE: something entirely different",
            location="Tion shadowport",
        ))
        assert sys1 == sys2
        assert "DICE RESULT INTERPRETATION GUIDE" in sys1
        assert "---CHOICES---" in sys1

    def test_user_prompt_holds_context_not_rules(self):
        from gm.cloud_gm import _build_prompts
        _, user = _build_prompts(_make_ctx())
        assert "DICE RESULT INTERPRETATION GUIDE" not in user
        assert "CURRENT SCENE" in user
        assert "Kira Denn" in user

    def test_user_prompt_fully_formatted(self):
        from gm.cloud_gm import _build_prompts
        _, user = _build_prompts(_make_ctx())
        for placeholder in ("{character_summary}", "{npc_states}",
                            "{dice_result_block}", "{tone_instruction}"):
            assert placeholder not in user

    def test_system_prompt_read_verbatim(self):
        # The system file is read verbatim (never .format()ed), so the
        # escaped braces from the old single-template era must not appear,
        # and no format-style placeholder may remain.
        from gm.cloud_gm import PROMPT_PATH_SYSTEM
        text = PROMPT_PATH_SYSTEM.read_text(encoding="utf-8")
        assert "{{" not in text and "}}" not in text
        import re
        assert not re.search(r"\{[a-z_]+_block\}", text)


# ── 9. Token usage accounting ────────────────────────────────────────

class TestUsageAccounting:
    def test_records_and_totals(self):
        from gm.llm_client import log_llm_usage, usage_totals
        response = SimpleNamespace(
            usage=SimpleNamespace(
                prompt_tokens=1000,
                completion_tokens=200,
                total_tokens=1200,
                prompt_tokens_details=SimpleNamespace(cached_tokens=800),
            ),
        )
        log_llm_usage(purpose="test_purpose_unique", tier="fast",
                      model="test-model", response=response)
        totals = usage_totals()["test_purpose_unique"]
        assert totals["calls"] == 1
        assert totals["prompt_tokens"] == 1000
        assert totals["cached_prompt_tokens"] == 800

    def test_deepseek_native_cache_field(self):
        from gm.llm_client import _extract_usage
        response = SimpleNamespace(
            usage=SimpleNamespace(
                prompt_tokens=500, completion_tokens=100, total_tokens=600,
                prompt_tokens_details=None,
                prompt_cache_hit_tokens=300,
            ),
        )
        usage = _extract_usage(response)
        assert usage["cached_prompt_tokens"] == 300

    def test_missing_usage_is_safe(self):
        from gm.llm_client import log_llm_usage
        log_llm_usage(purpose="x", tier="fast", model="m",
                      response=SimpleNamespace())  # no usage attr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
