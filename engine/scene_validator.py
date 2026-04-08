"""
Scene purpose validator — CS-6 Phase 7.

A lightweight local-model call that scores narration against its
dramatic mission. Runs AFTER narration, in parallel with reconciliation.
Quality signal only — does not block delivery.

Pure Python data models. The LLM call is in gm/local_gm.py.
"""

from dataclasses import dataclass
from typing import Optional


VALIDATOR_PROMPT = """You are evaluating a turn's narration for dramatic utility.

DRAMATIC MISSION: {selected_mission}
MISSION SENTENCE: {mission_sentence}
NARRATION: {narration_text}
CHOICES: {choices_text}

Score this turn on five dimensions (1-5 each):

1. MISSION DELIVERY: Did the narration accomplish its stated mission?
   5 = mission clearly delivered; 1 = mission completely absent

2. PRESSURE PROGRESSION: Does the turn increase, maintain, or
   meaningfully shift dramatic pressure?
   5 = pressure clearly advanced; 1 = pressure stagnant or deflated

3. ANTAGONIST RELEVANCE: Is the antagonistic force present or felt?
   5 = directly present; 3 = indirectly referenced; 1 = completely absent

4. CHARACTER-REVEALING CHOICES: Do the choices let the player express
   who their character is, not just what they do?
   5 = choices test character identity; 1 = choices are purely tactical

5. CHANGE: Did something in the story world change because of this turn?
   5 = clear change; 1 = nothing different after this turn"""

VALIDATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "mission_delivery": {"type": "integer", "minimum": 1, "maximum": 5},
        "pressure_progression": {"type": "integer", "minimum": 1, "maximum": 5},
        "antagonist_relevance": {"type": "integer", "minimum": 1, "maximum": 5},
        "character_choices": {"type": "integer", "minimum": 1, "maximum": 5},
        "change": {"type": "integer", "minimum": 1, "maximum": 5},
        "composite": {"type": "number"},
        "concern": {"type": "string"},
    },
    "required": [
        "mission_delivery", "pressure_progression",
        "antagonist_relevance", "character_choices", "change",
    ],
}

# Thresholds
THRESHOLD_OK = 3.0
THRESHOLD_WARNING = 2.0


@dataclass
class SceneValidationResult:
    """Parsed output from scene purpose validation."""
    mission_delivery: int = 3
    pressure_progression: int = 3
    antagonist_relevance: int = 3
    character_choices: int = 3
    change: int = 3
    composite: float = 3.0
    concern: str = ""
    corrective_instruction: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "SceneValidationResult":
        scores = {
            "mission_delivery": _clamp(data.get("mission_delivery", 3)),
            "pressure_progression": _clamp(data.get("pressure_progression", 3)),
            "antagonist_relevance": _clamp(data.get("antagonist_relevance", 3)),
            "character_choices": _clamp(data.get("character_choices", 3)),
            "change": _clamp(data.get("change", 3)),
        }
        values = list(scores.values())
        composite = sum(values) / len(values) if values else 3.0

        corrective = ""
        if composite < THRESHOLD_OK:
            corrective = (
                "The previous turn was low-purpose. This turn should "
                "clearly advance the story."
            )

        return cls(
            **scores,
            composite=round(composite, 2),
            concern=data.get("concern", ""),
            corrective_instruction=corrective,
        )


def _clamp(val, lo=1, hi=5) -> int:
    try:
        return max(lo, min(hi, int(val)))
    except (TypeError, ValueError):
        return 3


def build_validator_prompt(
    selected_mission: str,
    mission_sentence: str,
    narration_text: str,
    choices_text: str,
) -> str:
    """Build the scene validation prompt for the local model."""
    return VALIDATOR_PROMPT.format(
        selected_mission=selected_mission,
        mission_sentence=mission_sentence,
        narration_text=narration_text,
        choices_text=choices_text,
    )
