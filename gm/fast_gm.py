import json
import logging
import os
from pathlib import Path
from engine.character import Character
from engine.equipment import build_equipment_check_summary
from dataclasses import dataclass
from typing import Optional

from gm.llm_client import call_chat_json, TIER_FAST
from engine.scene_validator import (
    SceneValidationResult,
    VALIDATOR_SCHEMA,
    build_validator_prompt,
)

PROMPT_PATH = Path(__file__).parent / "prompts" / "check_decision.txt"
ANNOTATION_PROMPT_PATH = Path(__file__).parent / "prompts" / "choice_annotation.txt"

VALID_SKILLS = {
    "astrogation", "athletics", "charm", "coercion", "computers", "cool",
    "coordination", "deception", "discipline", "leadership", "mechanics",
    "medicine", "negotiation", "perception", "piloting_planetary",
    "piloting_space", "resilience", "skulduggery", "stealth", "streetwise",
    "survival", "vigilance", "brawl", "gunnery", "melee", "ranged_light",
    "ranged_heavy", "core_worlds", "education", "lore", "outer_rim",
    "underworld", "warfare", "xenology", "lightsaber",
}

SKILL_ALIASES = {
    "piloting":             "piloting_space",
    "pilot":                "piloting_space",
    "space_piloting":       "piloting_space",
    "spaceship_piloting":   "piloting_space",
    "planetary_piloting":   "piloting_planetary",
    "range_light":          "ranged_light",
    "range_heavy":          "ranged_heavy",
    "light_ranged":         "ranged_light",
    "heavy_ranged":         "ranged_heavy",
    "skullduggery":         "skulduggery",
    "street_wise":          "streetwise",
    "knowledge_underworld": "underworld",
    "knowledge_lore":       "lore",
}

CHECK_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "requires_check": {"type": "boolean"},
        "skill":          {"type": "string"},
        "difficulty": {
            "type": "string",
            "enum": ["simple", "easy", "average", "hard", "daunting", "formidable"],
        },
        "boost_dice":   {"type": "integer", "minimum": 0, "maximum": 2},
        "setback_dice": {"type": "integer", "minimum": 0, "maximum": 2},
        "scene_type": {
            "type": "string",
            "enum": ["combat", "chase", "infiltration", "social",
                     "exploration", "introspection", "space_combat"],
        },
        "moral_weight":        {"type": "integer", "minimum": 0, "maximum": 3},
        "force_use":           {"type": "boolean"},
        "force_power":         {"type": "string"},
        "force_pips_required": {"type": "integer", "minimum": 1, "maximum": 5},
        "reasoning":           {"type": "string"},
    },
    "required": ["requires_check", "scene_type", "reasoning"],
}


@dataclass
class CheckDecision:
    requires_check: bool
    skill:          Optional[str] = None
    difficulty:     Optional[str] = None
    boost_dice:     int = 0
    setback_dice:   int = 0
    scene_type:     str = "social"     # default fallback per Game Mechanics §10
    moral_weight:   int = 0            # 0=none, 1=minor, 2=significant, 3=severe (Game Mechanics §9)
    force_use:      bool = False       # Phase 14: whether this action involves the Force (§16.7)
    force_power:    Optional[str] = None   # Phase 14: which Force power applies (§16.7)
    force_pips_required: int = 0       # Phase 14: minimum pips needed (§16.7)
    reasoning:      str = ""


class LocalGMError(Exception):
    pass


def _normalize_skill(raw: str) -> str:
    normalised = raw.lower().strip().replace(" ", "_").replace("-", "_")
    if normalised in VALID_SKILLS:
        return normalised
    if normalised in SKILL_ALIASES:
        return SKILL_ALIASES[normalised]
    raise ValueError(f"Unknown skill {raw!r}. Valid: {sorted(VALID_SKILLS)}")


def decide_check(
    character:            Character,
    scene_description:    str,
    player_action:        str,
    arc_state:            dict,
    recent_failure_count: int = 0,
    max_retries:          int = 3,
    ship_state=None,
) -> CheckDecision:
    # Failure recovery calibration (Game Mechanics §2)
    if recent_failure_count >= 2:
        failure_calibration = (
            "DIFFICULTY CALIBRATION: The character is under sustained pressure "
            f"({recent_failure_count} failed checks in recent turns). Prefer "
            "average difficulty over hard. Reserve hard/daunting for actions "
            "that are genuinely reckless in context."
        )
    else:
        failure_calibration = ""

    # Phase 11: Talent effects for check decision (§15.4)
    from engine.talents import build_talent_check_effects
    talent_effects = build_talent_check_effects(character)

    # Phase 14/15: Force powers section for Force-sensitive characters (§16.7)
    force_section = ""
    if character.force_rating > 0:
        from engine.force import get_available_force_dice, build_force_choice_guidance
        available = get_available_force_dice(character)
        # Phase 15: include specific Force power list (§16.3)
        power_guidance = build_force_choice_guidance(character)
        force_section = (
            f"\nFORCE POWERS:\n"
            f"This character is Force-sensitive (Force Rating {character.force_rating}, "
            f"{available} dice available after commitments).\n"
            f"\n"
            f"{power_guidance}\n"
            f"\n"
            f"When the player's action involves using the Force:\n"
            f"- Set force_use to true\n"
            f"- Set force_power to the power name (e.g. \"move\", \"sense\")\n"
            f"- Set force_pips_required to the minimum pips needed (see power list)\n"
            f"- The skill field should be the mundane skill being enhanced, or "
            f"omitted for pure Force actions\n"
            f"- Force dice are added automatically by the engine — do not "
            f"include them in boost_dice\n"
            f"- ONLY set force_use for powers the character possesses (listed above)\n"
            f"\n"
            f"When the player's action does NOT involve the Force, even if the "
            f"character is Force-sensitive, set force_use to false. Not every "
            f"action by a Force user involves the Force.\n"
        )

    # Phase 16: Ship status for space_combat scenes (§17)
    ship_status_section = ""
    if ship_state is not None:
        ship_status_section = "\n" + ship_state.to_check_prompt_block() + "\n"

    template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt   = template.format(
        character_summary=character.narrative_status(),
        equipment_section=build_equipment_check_summary(character.loadout),
        talent_effects_section=talent_effects,
        force_section=force_section,
        ship_status_section=ship_status_section,
        current_act=arc_state.get("current_act", 1),
        total_acts=arc_state.get("total_acts", 4),
        act_name=arc_state.get("act_name", "Unknown"),
        tension_level=arc_state.get("tension_level", "rising"),
        failure_calibration=failure_calibration,
        scene_description=scene_description,
        player_action=player_action,
    )

    try:
        data = call_chat_json(
            tier=TIER_FAST,
            purpose="decision",
            user=prompt,
            schema=CHECK_DECISION_SCHEMA,
            temperature=0.1,
            max_tokens=600,
            timeout=30.0,
            retries=max_retries,
        )
        return _validate_decision(data)
    except RuntimeError as e:
        # Rule 5 boundary: garbage JSON after retries must still raise —
        # the model answered and its answer is malformed, which is a bug
        # to surface, not paper over. Only TRANSPORT failure (timeout,
        # connection error, provider outage — the call never produced
        # JSON to judge) falls back to a deterministic decision so a
        # freeform action can't hard-block the turn.
        if _is_json_decode_failure(e):
            raise LocalGMError(
                f"Check decision failed after {max_retries} attempts: {e}"
            )
        logging.warning(
            "decide_check transport failure — deterministic fallback engaged: %s", e
        )
        return _transport_fallback_decision(arc_state, e)
    except (ValueError, KeyError) as e:
        raise LocalGMError(f"Check decision validation failed: {e}")


VALID_SCENE_TYPES = {
    "combat", "chase", "infiltration", "social", "exploration", "introspection",
    "space_combat",
}


# ── Transport-failure fallback for check decisions ───────────────────
# Conservative scene_type → skill mapping used ONLY when the fast tier is
# unreachable. Skill names verified against engine.character.SKILL_CHARACTERISTICS.
# "introspection" is intentionally absent — reflective beats need no dice.

FALLBACK_SCENE_SKILLS = {
    "combat":       "ranged_light",
    "chase":        "coordination",
    "infiltration": "stealth",
    "social":       "charm",
    "exploration":  "perception",
    "space_combat": "piloting_space",
}


def _is_json_decode_failure(error: BaseException) -> bool:
    """True when the failure is malformed JSON, not transport.

    call_chat_json chains its last attempt's error as __cause__: a
    JSONDecodeError anywhere in the chain means the provider answered
    with garbage (Rule 5 — must raise). Any other chain means the call
    never yielded JSON at all (timeout / connection / provider error).
    """
    seen: set[int] = set()
    current: Optional[BaseException] = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, json.JSONDecodeError):
            return True
        current = current.__cause__ or current.__context__
    return False


def _transport_fallback_decision(arc_state: dict, error: Exception) -> CheckDecision:
    """Deterministic check decision when the fast tier is unreachable.

    Shape-identical to the LLM path (a CheckDecision), conservative on
    every axis: average difficulty, no boost/setback, no moral weight,
    no Force. The reasoning string is tagged DETERMINISTIC_FALLBACK with
    the root error class so telemetry can measure fallback rate.
    """
    scene_state = arc_state.get("scene_state") or {}
    raw_scene = str(
        scene_state.get("scene_type")
        or arc_state.get("last_scene_type")
        or "exploration"
    ).lower().strip()
    scene_type = raw_scene if raw_scene in VALID_SCENE_TYPES else "exploration"

    root: BaseException = error
    seen: set[int] = {id(root)}
    while root.__cause__ is not None and id(root.__cause__) not in seen:
        root = root.__cause__
        seen.add(id(root))
    reasoning = (
        f"DETERMINISTIC_FALLBACK ({type(root).__name__}): fast tier "
        f"unreachable; conservative decision mapped from scene_type={scene_type}"
    )

    skill = FALLBACK_SCENE_SKILLS.get(scene_type)
    if skill is None:
        return CheckDecision(
            requires_check=False,
            scene_type=scene_type,
            moral_weight=0,
            force_use=False,
            reasoning=reasoning,
        )
    return CheckDecision(
        requires_check=True,
        skill=skill,
        difficulty="average",
        scene_type=scene_type,
        moral_weight=0,
        force_use=False,
        reasoning=reasoning,
    )


def _validate_decision(data: dict) -> CheckDecision:
    if "requires_check" not in data:
        raise ValueError("Missing 'requires_check'")

    # scene_type and moral_weight apply to all decisions (check or no-check)
    raw_scene = data.get("scene_type", "social").lower().strip()
    scene_type = raw_scene if raw_scene in VALID_SCENE_TYPES else "social"
    moral_weight = max(0, min(3, int(data.get("moral_weight", 0))))

    # Phase 14: Force fields (§16.7) — apply to all decisions
    force_use = bool(data.get("force_use", False))
    force_power = data.get("force_power") or None
    force_pips_required = max(1, int(data.get("force_pips_required", 1))) if force_use else 0

    if not data["requires_check"]:
        return CheckDecision(
            requires_check=False,
            scene_type=scene_type,
            moral_weight=moral_weight,
            force_use=force_use,
            force_power=force_power,
            force_pips_required=force_pips_required,
            reasoning=data.get("reasoning", ""),
        )
    if "skill" not in data or "difficulty" not in data:
        # Pure Force action (no mundane skill) — still valid if force_use is true
        if force_use:
            return CheckDecision(
                requires_check=True,
                force_use=True,
                force_power=force_power,
                force_pips_required=force_pips_required,
                scene_type=scene_type,
                moral_weight=moral_weight,
                reasoning=data.get("reasoning", "pure Force action"),
            )
        # Model said requires_check but gave incomplete data — fall back to no-check
        return CheckDecision(
            requires_check=False,
            scene_type=scene_type,
            moral_weight=moral_weight,
            reasoning=data.get("reasoning", "incomplete check data, defaulting to no-check"),
        )
    return CheckDecision(
        requires_check=True,
        skill=_normalize_skill(data["skill"]),
        difficulty=data["difficulty"].lower().strip(),
        boost_dice=min(int(data.get("boost_dice", 0)), 2),
        setback_dice=min(int(data.get("setback_dice", 0)), 2),
        scene_type=scene_type,
        moral_weight=moral_weight,
        force_use=force_use,
        force_power=force_power,
        force_pips_required=force_pips_required,
        reasoning=data.get("reasoning", ""),
    )


# ── Phase 13: Choice Annotation (§24) ────────────────────────────────

ANNOTATION_SCHEMA = {
    "type": "object",
    "properties": {
        "choice_target":        {"type": "string"},
        "choice_method":        {"type": "string"},
        "sacrifice":            {"type": "string"},
        "priority_revealed":    {"type": "string"},
        "npc_impact":           {"type": "object"},
        "throughline_relevance": {
            "type": "string",
            "enum": ["high", "medium", "low"],
        },
        "throughline_direction": {"type": "string"},
        "behavioral_tags": {
            "type": "array",
            "items": {"type": "string"},
        },
        # Brooks/Weiland arc alignment per choice. "neutral" when the
        # protagonist has no narrative_arc populated or when the choice
        # has no clear bearing on the lie this turn.
        "arc_alignment": {
            "type": "string",
            "enum": ["lie", "truth", "neutral"],
        },
        "arc_evidence": {"type": "string"},
    },
    "required": [
        "choice_target", "priority_revealed",
        "throughline_relevance", "behavioral_tags",
    ],
}


def annotate_choice(
    selected_choice: str,
    rejected_choices: list[str],
    scene_context: str,
    npc_summary: str,
    recent_pattern: str,
    throughline_question: str,
    narrative_arc_block: str = "",
) -> Optional[dict]:
    """
    Extract behavioral meaning from the player's choice (§24).

    Runs via local model. Returns structured annotation dict or None on failure.
    Designed to run in parallel with check decision — not on critical path.
    When `narrative_arc_block` is provided, the annotator also classifies
    the choice as `lie | truth | neutral` against the protagonist's arc.
    """
    template = ANNOTATION_PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        selected_choice=selected_choice,
        rejected_choices="\n".join(f"- {c}" for c in rejected_choices) or "None",
        scene_context=scene_context[:500],
        npc_summary=npc_summary[:300],
        recent_pattern=recent_pattern[:400],
        throughline_question=throughline_question,
        narrative_arc_block=narrative_arc_block or "",
    )

    try:
        data = call_chat_json(
            tier=TIER_FAST,
            purpose="annotation",
            user=prompt,
            schema=ANNOTATION_SCHEMA,
            temperature=0.2,
            max_tokens=600,
            timeout=30.0,
            retries=2,
        )
        return _validate_annotation(data)
    except Exception as e:
        logging.warning(f"Choice annotation failed (non-critical): {e}")
        return None


def _validate_annotation(data: dict) -> dict:
    """Validate and normalize the annotation JSON."""
    # Ensure required fields
    if "priority_revealed" not in data or "behavioral_tags" not in data:
        raise ValueError("Missing required annotation fields")

    # Clamp behavioral_tags to 2-5 items
    tags = data.get("behavioral_tags", [])
    if not isinstance(tags, list):
        tags = []
    data["behavioral_tags"] = tags[:5]

    # Normalize throughline_relevance
    relevance = data.get("throughline_relevance", "low")
    if relevance not in ("high", "medium", "low"):
        data["throughline_relevance"] = "low"

    # Ensure npc_impact is a dict
    if not isinstance(data.get("npc_impact"), dict):
        data["npc_impact"] = {}

    # Brooks/Weiland arc alignment — default to neutral if missing or invalid
    arc_alignment = data.get("arc_alignment", "neutral")
    if arc_alignment not in ("lie", "truth", "neutral"):
        arc_alignment = "neutral"
    data["arc_alignment"] = arc_alignment
    if not isinstance(data.get("arc_evidence"), str):
        data["arc_evidence"] = ""

    return data


# ── Ending branch classification (experience shell) ─────────────────

ENDING_BRANCH_SCHEMA = {
    "type": "object",
    "properties": {
        "branch_id":  {"type": "string"},
        "reasoning":  {"type": "string"},
    },
    "required": ["branch_id", "reasoning"],
}


def classify_ending_branch(spine: dict, story_summary: str) -> Optional[str]:
    """Identify which authored climax branch the played story took.

    Runs once, at epilogue time. The spine's climactic variation point
    options are the authored branches (each ending path's branch_id must
    resolve to one — Gate 4b); this classifies the actually-played story
    against them so the ENGINE selects the ending deterministically and
    the epilogue model writes it, rather than choosing it.

    Fail-open: returns None when the spine has no branch structure or
    the model's answer doesn't resolve to a known option id — the
    epilogue then falls back to LLM ending-matching (legacy behavior).
    """
    sa = spine.get("story_architecture") or {}
    ending_branch_ids = {
        ep.get("branch_id") for ep in sa.get("ending_paths", [])
        if isinstance(ep, dict) and ep.get("branch_id")
    }
    if not ending_branch_ids:
        return None

    options = []
    for vp in spine.get("variation_points", []) or []:
        for opt in vp.get("options", []) or []:
            if isinstance(opt, dict) and opt.get("id") in ending_branch_ids:
                options.append(opt)
    if not options:
        return None

    option_block = "\n".join(
        f"- {opt['id']}: {opt.get('description', '')}" for opt in options
    )
    prompt = (
        "A narrative RPG campaign has just been completed. Below are the "
        "authored climactic branches, then a summary of the story that was "
        "actually played.\n\n"
        f"AUTHORED BRANCHES:\n{option_block}\n\n"
        f"THE STORY THAT WAS PLAYED:\n{story_summary[:6000]}\n\n"
        "Which branch did the played story actually take? Judge by what the "
        "protagonist DID in the final stretch — not by which branch is most "
        "dramatic. Respond ONLY with JSON: "
        '{"branch_id": "<exact id from the list>", '
        '"reasoning": "<one sentence>"}'
    )

    try:
        data = call_chat_json(
            tier=TIER_FAST,
            purpose="ending_branch",
            user=prompt,
            schema=ENDING_BRANCH_SCHEMA,
            temperature=0.0,
            max_tokens=300,
            timeout=30.0,
            retries=2,
        )
        branch_id = str(data.get("branch_id", "")).strip()
        if branch_id in ending_branch_ids:
            logging.info("ending_branch classified: %s (%s)",
                         branch_id, str(data.get("reasoning", ""))[:120])
            return branch_id
        logging.warning("ending_branch %r not in authored set; falling back",
                        branch_id)
        return None
    except Exception as e:
        logging.warning(f"Ending branch classification failed (non-critical): {e}")
        return None


# ── Phase 13: Prose Diagnostic Signal (§13) ──────────────────────────

PROSE_DIAGNOSTIC_SCHEMA = {
    "type": "object",
    "properties": {
        "sensory_channels_recent": {
            "type": "array",
            "items": {"type": "string"},
        },
        "rhythm_note":        {"type": "string"},
        "opener_similarity":  {"type": "string"},
        "npc_coherence_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "npc":                   {"type": "string"},
                    "described_behavior":     {"type": "string"},
                    "mechanical_disposition": {"type": "number"},
                    "flag":                  {"type": "string"},
                },
            },
        },
        "polarity_note": {"type": "string"},
    },
    "required": ["sensory_channels_recent", "npc_coherence_flags"],
}


def run_prose_diagnostic(
    recent_passages: list[str],
    npc_states_block: str,
) -> Optional[dict]:
    """
    Prose diagnostic signal — detects repetition, sensory monotony,
    and NPC action-emotion coherence issues (§13).

    Runs via local model. Returns diagnostic dict or None on failure.
    Designed to run in parallel with check decision — not on critical path.
    """
    if not recent_passages:
        return None

    passages_text = "\n\n---\n\n".join(
        f"Passage {i+1}:\n{p[:400]}" for i, p in enumerate(recent_passages[-4:])
    )

    prompt = (
        "You are a narrative quality auditor. Analyze these recent passages "
        "and NPC states for patterns that reduce prose quality.\n\n"
        f"RECENT PASSAGES:\n{passages_text}\n\n"
        f"NPC STATES:\n{npc_states_block}\n\n"
        "Identify:\n"
        "1. sensory_channels_recent: Which sensory channels dominate "
        "(visual, auditory, tactile, olfactory, kinesthetic) — list one per passage\n"
        "2. rhythm_note: Any paragraph rhythm monotony or repetitive structures\n"
        "3. opener_similarity: Whether passage openings are too similar\n"
        "4. npc_coherence_flags: Any NPC described in prose as behaving "
        "inconsistently with their mechanical disposition. Include the NPC name, "
        "described behavior, mechanical disposition value, and flag description\n"
        "5. polarity_note: Whether NPC interactions are uniformly positive "
        "despite hostile/conflicted NPC states\n\n"
        "Return ONLY valid JSON."
    )

    try:
        return call_chat_json(
            tier=TIER_FAST,
            purpose="diagnostic",
            user=prompt,
            schema=PROSE_DIAGNOSTIC_SCHEMA,
            temperature=0.1,
            max_tokens=800,
            timeout=30.0,
            retries=2,
        )
    except Exception as e:
        logging.warning(f"Prose diagnostic failed (non-critical): {e}")
        return None


NARRATION_POLARITY_SCHEMA = {
    "type": "object",
    "properties": {
        "depicted_outcome": {
            "type": "string",
            "enum": ["success", "failure", "mixed", "unclear"],
        },
    },
    "required": ["depicted_outcome"],
}


def check_narration_polarity(
    passage: str,
    situation: str,
    *,
    outcome_label: str,
) -> str:
    """Rule 4 enforcement — the dice are the truth.

    Asks the fast tier whether the passage, as written, depicts the
    attempted action succeeding or failing. Called only on failed checks
    (the case the narrator is tempted to soften). Returns one of
    "success" / "failure" / "mixed" / "unclear".

    Fail-open: any evaluator problem returns "unclear" so the turn is
    never blocked by the validator itself.
    """
    prompt = (
        "A player attempted an action in an interactive story. The game's "
        f"dice ruled the attempt: {outcome_label}.\n\n"
        f"SCENE AND ATTEMPTED ACTION:\n{situation[:600]}\n\n"
        f"STORY PASSAGE:\n{passage[:4000]}\n\n"
        "Question: judged only by what the passage shows, did the player's "
        "attempted action achieve its goal?\n"
        '- "success": the passage gives the player what the attempt sought\n'
        '- "failure": the goal is denied, even if something peripheral was gained\n'
        '- "mixed": genuinely ambiguous — partial achievement of the core goal\n'
        '- "unclear": the passage does not show the outcome\n'
        "Judge the attempted action's core goal only, not side effects."
    )

    try:
        data = call_chat_json(
            tier=TIER_FAST,
            purpose="polarity",
            user=prompt,
            schema=NARRATION_POLARITY_SCHEMA,
            schema_name="narration_polarity",
            temperature=0.0,
            max_tokens=60,
            timeout=15.0,
            retries=1,
        )
        verdict = str(data.get("depicted_outcome", "unclear")).strip().lower()
        if verdict in {"success", "failure", "mixed", "unclear"}:
            return verdict
        return "unclear"
    except Exception as e:
        logging.warning(f"Narration polarity check failed (fail-open): {e}")
        return "unclear"


def validate_scene_purpose(
    *,
    selected_mission: str,
    mission_sentence: str,
    narration_text: str,
    choices: Optional[list] = None,
) -> SceneValidationResult:
    """CS-6 post-narration scene purpose validation.

    Scores the just-completed turn's narration against its dramatic mission
    on five dimensions (mission_delivery, pressure_progression,
    antagonist_relevance, character_choices, change). Quality signal only —
    callers should never use the result to gate or rewrite narration.

    Returns a neutral SceneValidationResult (composite=3.0) when the mission
    is missing or the LLM call fails, so callers can treat the result as
    always-present and never block on validation problems.
    """
    if not selected_mission or not mission_sentence:
        return SceneValidationResult()

    choices_text = "\n".join(f"- {c}" for c in (choices or [])[:6])
    prompt = build_validator_prompt(
        selected_mission=selected_mission,
        mission_sentence=mission_sentence,
        narration_text=narration_text or "",
        choices_text=choices_text,
    )

    try:
        data = call_chat_json(
            tier=TIER_FAST,
            purpose="diagnostic",
            user=prompt,
            schema=VALIDATOR_SCHEMA,
            schema_name="scene_validation",
            temperature=0.2,
            max_tokens=400,
            timeout=20.0,
            retries=2,
        )
    except Exception as e:
        logging.warning(f"scene_validator failed (non-critical): {e}")
        return SceneValidationResult()

    return SceneValidationResult.from_dict(data)
