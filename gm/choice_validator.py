"""Choice quality validator — post-generation gate for generic choices.

Calls the fast LLM tier to evaluate choice sets against five rubric
dimensions. Rejects when 2+ dimensions fail.

See docs/CHOICE_QUALITY_VALIDATION_SPEC.md for the full specification.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from gm.llm_client import TIER_FAST, call_chat_json

PROMPT_PATH = Path(__file__).parent / "prompts" / "choice_eval.txt"

CHOICE_EVAL_SCHEMA = {
    "type": "object",
    "properties": {
        "specific":  {"type": "boolean"},
        "identity":  {"type": "boolean"},
        "risk":      {"type": "boolean"},
        "different": {"type": "boolean"},
        "grounded":  {"type": "boolean"},
    },
    "required": ["specific", "identity", "risk", "different", "grounded"],
}

logger = logging.getLogger(__name__)


@dataclass
class ChoiceQualityResult:
    specific: bool
    identity: bool
    risk: bool
    different: bool
    grounded: bool

    @property
    def fail_count(self) -> int:
        return sum(1 for v in [self.specific, self.identity, self.risk,
                               self.different, self.grounded] if not v)

    @property
    def passed(self) -> bool:
        return self.fail_count < 2

    @property
    def rejection_reason(self) -> str:
        failed = []
        if not self.specific:  failed.append("generic")
        if not self.identity:  failed.append("no character expression")
        if not self.risk:      failed.append("uniform risk")
        if not self.different: failed.append("cosmetic variation")
        if not self.grounded:  failed.append("ungrounded")
        return ", ".join(failed)

    def to_dict(self) -> dict:
        return {
            "specific": self.specific,
            "identity": self.identity,
            "risk": self.risk,
            "different": self.different,
            "grounded": self.grounded,
            "fail_count": self.fail_count,
            "passed": self.passed,
            "rejection_reason": self.rejection_reason,
        }


def validate_choice_quality(
    situation: str,
    character_name: str,
    character_career: str,
    passage: str,
    choices: list[str],
) -> ChoiceQualityResult:
    """Evaluate a choice set against the five-dimension quality rubric.

    Calls the fast LLM tier for structured evaluation.
    Returns a ChoiceQualityResult with per-dimension pass/fail.

    On evaluator failure, returns an all-pass result (fail-open)
    to avoid blocking the turn on evaluator issues.
    """
    template = PROMPT_PATH.read_text(encoding="utf-8")

    # Extract last ~100 words of passage for the eval prompt
    words = passage.split()
    last_100 = " ".join(words[-100:]) if len(words) > 100 else passage

    numbered_choices = "\n".join(
        f"{i+1}. {c}" for i, c in enumerate(choices)
    )

    prompt = template.format(
        situation=situation,
        character_name=character_name,
        character_career=character_career,
        last_100_words_of_passage=last_100,
        numbered_choice_list=numbered_choices,
    )

    try:
        data = call_chat_json(
            tier=TIER_FAST,
            purpose="choice_quality",
            user=prompt,
            schema=CHOICE_EVAL_SCHEMA,
            schema_name="choice_quality",
            temperature=0.1,
            max_tokens=100,
            timeout=30.0,
            retries=2,
        )
        return ChoiceQualityResult(
            specific=bool(data.get("specific", True)),
            identity=bool(data.get("identity", True)),
            risk=bool(data.get("risk", True)),
            different=bool(data.get("different", True)),
            grounded=bool(data.get("grounded", True)),
        )

    except Exception as e:
        # Fail-open: if the evaluator breaks, don't block the turn
        logger.warning(f"Choice quality validator failed: {e}. Accepting choices.")
        return ChoiceQualityResult(
            specific=True, identity=True, risk=True,
            different=True, grounded=True,
        )


def build_quality_correction(quality: ChoiceQualityResult) -> str:
    """Build a correction message for the cloud GM based on failed dimensions."""
    parts = ["Your choices were rejected for quality issues:"]
    if not quality.specific:
        parts.append(
            "- Choices are too generic. Include details specific to "
            "this character and this scene."
        )
    if not quality.identity:
        parts.append(
            "- Choices only vary in method, not in what they reveal "
            "about the character. Each choice should say something "
            "different about who the character is."
        )
    if not quality.risk:
        parts.append(
            "- All choices have similar risk levels. Include at least "
            "one lower-risk and one higher-risk option."
        )
    if not quality.different:
        parts.append(
            "- Choices would all lead to similar outcomes. At least "
            "two should produce meaningfully different results."
        )
    if not quality.grounded:
        parts.append(
            "- Choices don't reference specific scene elements. "
            "Reference named NPCs, objects, or threats from the scene."
        )
    parts.append("Rewrite only the choices. Keep the passage unchanged.")
    return "\n".join(parts)
