import json
import logging
import os
import httpx
from pathlib import Path
from engine.character import Character
from engine.equipment import build_equipment_check_summary
from dataclasses import dataclass
from typing import Optional

PROMPT_PATH = Path(__file__).parent / "prompts" / "check_decision.txt"
ANNOTATION_PROMPT_PATH = Path(__file__).parent / "prompts" / "choice_annotation.txt"
OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen3.5:9b")

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

    last_error = None
    for _ in range(max_retries):
        try:
            response = httpx.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model":  LOCAL_MODEL,
                    "prompt": f"/no_think\n{prompt}",
                    "stream": False,
                    "format": CHECK_DECISION_SCHEMA,
                    "options": {"temperature": 0.1, "num_predict": 200},
                },
                timeout=30.0,
            )
            response.raise_for_status()
            resp_json = response.json()
            raw_text = resp_json["response"].strip()
            if not raw_text and resp_json.get("thinking", "").strip():
                raw_text = resp_json["thinking"].strip()

            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            return _validate_decision(json.loads(raw_text))

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            last_error = e
        except httpx.HTTPError as e:
            raise LocalGMError(f"Ollama connection error: {e}")

    raise LocalGMError(
        f"Local model failed after {max_retries} attempts. Last error: {last_error}"
    )


VALID_SCENE_TYPES = {
    "combat", "chase", "infiltration", "social", "exploration", "introspection",
    "space_combat",
}


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
) -> Optional[dict]:
    """
    Extract behavioral meaning from the player's choice (§24).

    Runs via local model. Returns structured annotation dict or None on failure.
    Designed to run in parallel with check decision — not on critical path.
    """
    template = ANNOTATION_PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        selected_choice=selected_choice,
        rejected_choices="\n".join(f"- {c}" for c in rejected_choices) or "None",
        scene_context=scene_context[:500],
        npc_summary=npc_summary[:300],
        recent_pattern=recent_pattern[:400],
        throughline_question=throughline_question,
    )

    is_qwen = "qwen" in LOCAL_MODEL.lower()
    msg = f"/no_think\n{prompt}" if is_qwen else prompt

    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": LOCAL_MODEL,
                "prompt": msg,
                "stream": False,
                "format": ANNOTATION_SCHEMA,
                "options": {"temperature": 0.2, "num_predict": 300},
            },
            timeout=30.0,
        )
        response.raise_for_status()
        resp_json = response.json()
        raw_text = resp_json["response"].strip()

        if not raw_text and resp_json.get("thinking", "").strip():
            raw_text = resp_json["thinking"].strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        return _validate_annotation(json.loads(raw_text))

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

    return data


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

    is_qwen = "qwen" in LOCAL_MODEL.lower()
    msg = f"/no_think\n{prompt}" if is_qwen else prompt

    try:
        response = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": LOCAL_MODEL,
                "prompt": msg,
                "stream": False,
                "format": PROSE_DIAGNOSTIC_SCHEMA,
                "options": {"temperature": 0.1, "num_predict": 400},
            },
            timeout=30.0,
        )
        response.raise_for_status()
        resp_json = response.json()
        raw_text = resp_json["response"].strip()

        if not raw_text and resp_json.get("thinking", "").strip():
            raw_text = resp_json["thinking"].strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        return json.loads(raw_text)

    except Exception as e:
        logging.warning(f"Prose diagnostic failed (non-critical): {e}")
        return None
