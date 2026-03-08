"""
Spine difficulty calibration — pure Python.

Four-signal per-act scoring:
1. Anchor intensity — how dramatically the anchor escalates
2. NPC opposition — hostile NPC disposition and behavioral constraints
3. Mechanical pressure — act-level XP pressure and bonus condition difficulty
4. Pacing pressure — expected turn counts vs tension levels

Produces a SpineDifficultyCurve with composite score, curve shape
classification, and calibration warnings.

Runs as part of Gate 4 validation. No LLM calls required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from studio.schema import CampaignSpine


# ── Constants ─────────────────────────────────────────────────────────

TENSION_SCORES = {
    "rising": 0.3,
    "critical": 0.6,
    "climax": 0.9,
    "falling": 0.2,
    "resolution": 0.1,
}

# Curve shape thresholds
FLAT_VARIANCE_THRESHOLD = 0.02
INVERTED_DROP_THRESHOLD = 0.2


# ── Result types ──────────────────────────────────────────────────────


@dataclass
class ActDifficulty:
    """Per-act difficulty breakdown."""
    act_number: int
    anchor_intensity: float  # 0.0–1.0
    npc_opposition: float    # 0.0–1.0
    mechanical_pressure: float  # 0.0–1.0
    pacing_pressure: float   # 0.0–1.0
    composite: float         # Weighted average

    def to_dict(self) -> dict:
        return {
            "act_number": self.act_number,
            "anchor_intensity": round(self.anchor_intensity, 3),
            "npc_opposition": round(self.npc_opposition, 3),
            "mechanical_pressure": round(self.mechanical_pressure, 3),
            "pacing_pressure": round(self.pacing_pressure, 3),
            "composite": round(self.composite, 3),
        }


@dataclass
class SpineDifficultyCurve:
    """Full campaign difficulty analysis."""
    per_act: list[ActDifficulty]
    overall_composite: float
    curve_shape: str  # "ascending", "descending", "flat", "arc", "inverted_arc"
    calibration_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "per_act": [a.to_dict() for a in self.per_act],
            "overall_composite": round(self.overall_composite, 3),
            "curve_shape": self.curve_shape,
            "calibration_warnings": self.calibration_warnings,
        }


# ── Public API ────────────────────────────────────────────────────────


def compute_difficulty_curve(spine: CampaignSpine) -> SpineDifficultyCurve:
    """Compute the difficulty curve for a campaign spine."""
    act_difficulties: list[ActDifficulty] = []

    for act in spine.acts:
        anchor_score = _score_anchor_intensity(act)
        npc_score = _score_npc_opposition(act, spine)
        mech_score = _score_mechanical_pressure(act)
        pacing_score = _score_pacing_pressure(act)

        # Weighted composite: anchor 30%, NPC 25%, mechanical 25%, pacing 20%
        composite = (
            anchor_score * 0.30
            + npc_score * 0.25
            + mech_score * 0.25
            + pacing_score * 0.20
        )

        act_difficulties.append(ActDifficulty(
            act_number=act.number,
            anchor_intensity=anchor_score,
            npc_opposition=npc_score,
            mechanical_pressure=mech_score,
            pacing_pressure=pacing_score,
            composite=composite,
        ))

    overall = (
        sum(a.composite for a in act_difficulties) / len(act_difficulties)
        if act_difficulties else 0.0
    )

    shape = _classify_curve_shape(act_difficulties)
    warnings = _generate_warnings(act_difficulties, shape, spine)

    return SpineDifficultyCurve(
        per_act=act_difficulties,
        overall_composite=overall,
        curve_shape=shape,
        calibration_warnings=warnings,
    )


# ── Signal scorers ────────────────────────────────────────────────────


def _score_anchor_intensity(act) -> float:
    """Score anchor intensity based on tension level."""
    return TENSION_SCORES.get(act.tension.lower(), 0.5)


def _score_npc_opposition(act, spine: CampaignSpine) -> float:
    """Score NPC opposition based on dispositions and per-act states."""
    hostile_count = 0
    total_relevant = 0

    for npc in spine.npc_roster:
        # Check if NPC has a per_act_state for this act
        act_state = None
        for state in npc.per_act_state:
            if state.act == act.number:
                act_state = state
                break

        if act_state is None:
            continue

        total_relevant += 1

        # Parse disposition — hostile if < 0.4
        disp = _parse_disposition_float(act_state.disposition_expected)
        if disp is not None and disp < 0.4:
            hostile_count += 1
        elif disp is None:
            # String disposition — check for hostile keywords
            if isinstance(act_state.disposition_expected, str):
                hostile_words = ["hostile", "antagonistic", "aggressive", "enemy", "threat"]
                if any(w in act_state.disposition_expected.lower() for w in hostile_words):
                    hostile_count += 1

    if total_relevant == 0:
        # Fall back to starting dispositions
        hostile_start = sum(
            1 for npc in spine.npc_roster if npc.disposition_start < 0.4
        )
        total_start = len(spine.npc_roster)
        return hostile_start / total_start if total_start > 0 else 0.0

    return hostile_count / total_relevant


def _score_mechanical_pressure(act) -> float:
    """Score based on XP pressure and bonus condition count."""
    # More bonus conditions = harder to earn full XP = more pressure
    condition_count = len(act.xp_bonus_conditions)
    condition_pressure = min(condition_count / 5.0, 1.0)

    # Lower base XP relative to typical 15-20 = more pressure
    xp_pressure = max(0.0, 1.0 - (act.xp_base / 30.0))

    return (condition_pressure * 0.6 + xp_pressure * 0.4)


def _score_pacing_pressure(act) -> float:
    """Score pacing based on expected turns vs tension."""
    tension = TENSION_SCORES.get(act.tension.lower(), 0.5)

    # Parse expected_turns — handle both "8-12" string and list formats
    min_turns, max_turns = _parse_expected_turns(act.expected_turns)
    if min_turns is None:
        return tension

    # Fewer turns at higher tension = more pressure
    avg_turns = (min_turns + max_turns) / 2
    turn_pressure = max(0.0, 1.0 - (avg_turns / 15.0))

    return (tension * 0.6 + turn_pressure * 0.4)


# ── Curve classification ──────────────────────────────────────────────


def _classify_curve_shape(acts: list[ActDifficulty]) -> str:
    """Classify the overall difficulty curve shape."""
    if len(acts) < 2:
        return "flat"

    composites = [a.composite for a in acts]
    n = len(composites)

    # Check variance for flat
    mean = sum(composites) / n
    variance = sum((c - mean) ** 2 for c in composites) / n
    if variance < FLAT_VARIANCE_THRESHOLD:
        return "flat"

    # Find peak position
    peak_idx = composites.index(max(composites))
    trough_idx = composites.index(min(composites))

    # Monotonically ascending
    if all(composites[i] <= composites[i + 1] for i in range(n - 1)):
        return "ascending"

    # Monotonically descending
    if all(composites[i] >= composites[i + 1] for i in range(n - 1)):
        return "descending"

    # Arc: peak in middle-ish (not first or last)
    if 0 < peak_idx < n - 1:
        return "arc"

    # Inverted arc: trough in middle
    if 0 < trough_idx < n - 1:
        return "inverted_arc"

    # Default to arc if peak is near end (climax-resolution pattern)
    return "arc"


# ── Warning generation ────────────────────────────────────────────────


def _generate_warnings(
    acts: list[ActDifficulty],
    shape: str,
    spine: CampaignSpine,
) -> list[str]:
    """Generate calibration warnings for the difficulty curve."""
    warnings: list[str] = []

    if not acts:
        return warnings

    composites = [a.composite for a in acts]

    # Flat curve warning
    if shape == "flat":
        warnings.append(
            f"Difficulty curve is flat (all acts near {composites[0]:.2f}). "
            "Consider varying tension across acts for pacing."
        )

    # Inverted arc warning
    if shape == "inverted_arc":
        warnings.append(
            "Difficulty curve dips in the middle. This can feel like a "
            "pacing sag — consider raising mid-campaign tension."
        )

    # Final act harder than climax
    if len(acts) >= 3:
        climax_candidates = [a for a in acts if a.composite == max(composites)]
        if climax_candidates and acts[-1].act_number == climax_candidates[0].act_number:
            # Last act is hardest — might be fine if it's the climax
            pass
        elif acts[-1].composite > acts[-2].composite + INVERTED_DROP_THRESHOLD:
            warnings.append(
                f"Final act (act {acts[-1].act_number}) is significantly harder "
                f"than the preceding act. Consider whether the resolution should "
                f"ease tension."
            )

    # Very high overall difficulty
    overall = sum(composites) / len(composites)
    if overall > 0.75:
        warnings.append(
            f"Overall difficulty is high ({overall:.2f}). "
            "Consider whether this is intentional for the campaign's tone."
        )

    # Very low overall difficulty
    if overall < 0.15:
        warnings.append(
            f"Overall difficulty is low ({overall:.2f}). "
            "The campaign may lack mechanical tension."
        )

    return warnings


# ── Helpers ───────────────────────────────────────────────────────────


def _parse_disposition_float(value) -> Optional[float]:
    """Try to parse a disposition value as a float."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_expected_turns(value) -> tuple[Optional[int], Optional[int]]:
    """Parse expected_turns from various formats.

    Handles: "8-12", "8 to 12", [8, 12], "10"
    """
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return int(value[0]), int(value[1])
        except (ValueError, TypeError):
            return None, None

    if isinstance(value, str):
        # Try "8-12" format
        if "-" in value:
            parts = value.split("-")
            try:
                return int(parts[0].strip()), int(parts[1].strip())
            except (ValueError, IndexError):
                return None, None
        # Try "8 to 12" format
        if " to " in value.lower():
            parts = value.lower().split(" to ")
            try:
                return int(parts[0].strip()), int(parts[1].strip())
            except (ValueError, IndexError):
                return None, None
        # Try single number
        try:
            n = int(value.strip())
            return n, n
        except ValueError:
            return None, None

    if isinstance(value, (int, float)):
        return int(value), int(value)

    return None, None
