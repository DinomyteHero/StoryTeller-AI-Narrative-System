import json
import os
import httpx
from pathlib import Path
from engine.character import Character
from engine.equipment import build_equipment_check_summary
from dataclasses import dataclass
from typing import Optional

PROMPT_PATH = Path(__file__).parent / "prompts" / "check_decision.txt"
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
                     "exploration", "introspection"],
        },
        "moral_weight": {"type": "integer", "minimum": 0, "maximum": 3},
        "reasoning":    {"type": "string"},
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

    template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt   = template.format(
        character_summary=character.narrative_status(),
        equipment_section=build_equipment_check_summary(character.loadout),
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
}


def _validate_decision(data: dict) -> CheckDecision:
    if "requires_check" not in data:
        raise ValueError("Missing 'requires_check'")

    # scene_type and moral_weight apply to all decisions (check or no-check)
    raw_scene = data.get("scene_type", "social").lower().strip()
    scene_type = raw_scene if raw_scene in VALID_SCENE_TYPES else "social"
    moral_weight = max(0, min(3, int(data.get("moral_weight", 0))))

    if not data["requires_check"]:
        return CheckDecision(
            requires_check=False,
            scene_type=scene_type,
            moral_weight=moral_weight,
            reasoning=data.get("reasoning", ""),
        )
    if "skill" not in data or "difficulty" not in data:
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
        reasoning=data.get("reasoning", ""),
    )
