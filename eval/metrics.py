"""Quality metrics for evaluating narrative sessions.

Each metric takes a SessionRecord and returns a MetricResult with a
normalized score, pass/fail, and human-readable details.

Metrics are split into two tiers:
  - Tier 1 (no LLM): slop rate, word count, choice distinctness, thread tracking
  - Tier 2 (LLM-assisted): dice fidelity, NPC consistency, passage specificity
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eval.harness import SessionRecord


@dataclass
class MetricResult:
    name: str
    score: float        # 0.0-1.0 normalized
    passed: bool
    details: str        # human-readable explanation
    raw_data: dict = field(default_factory=dict)


# ── Banned slop phrases ──────────────────────────────────────────────────

SLOP_PHRASES = [
    "tapestry", "delve", "testament to", "couldn't help but notice",
    "settled over", "hung in the air", "seemed to",
    "the weight of", "a flicker of", "something shifted",
    "In that moment", "It was then that", "And yet, despite everything",
    "sent a shiver", "washed over", "pierced the silence",
    "a sense of", "couldn't help but", "the air crackled",
    "a knowing smile", "eyes that held",
]

# ── Scene type word count ranges ─────────────────────────────────────────

WORD_COUNT_RANGES = {
    "combat":        (250, 350),
    "chase":         (250, 400),
    "infiltration":  (300, 450),
    "social":        (350, 500),
    "exploration":   (350, 500),
    "introspection": (300, 450),
    "space_combat":  (250, 400),
}

# Default range for unknown scene types
DEFAULT_WORD_RANGE = (250, 600)


# ── Tier 1 Metrics (no LLM required) ────────────────────────────────────

def measure_slop_rate(session: SessionRecord) -> MetricResult:
    """Count banned AI-slop phrases across all passages."""
    total_passages = len(session.turns)
    if total_passages == 0:
        return MetricResult("slop_rate", 1.0, True, "No passages to evaluate", {})

    slop_turns = 0
    slop_instances: list[tuple[int, list[str]]] = []
    for turn in session.turns:
        passage_lower = turn.passage.lower()
        found = [p for p in SLOP_PHRASES if p.lower() in passage_lower]
        if found:
            slop_turns += 1
            slop_instances.append((turn.turn_number, found))

    rate = slop_turns / total_passages
    return MetricResult(
        name="slop_rate",
        score=1.0 - rate,
        passed=rate < 0.05,  # <5% of turns contain slop
        details=f"{slop_turns}/{total_passages} turns contain slop phrases",
        raw_data={"instances": slop_instances, "rate": rate},
    )


def measure_word_count_compliance(session: SessionRecord) -> MetricResult:
    """Check passage word counts against scene-type targets."""
    total = len(session.turns)
    if total == 0:
        return MetricResult("word_count", 1.0, True, "No passages to evaluate", {})

    compliant = 0
    violations: list[dict] = []
    for turn in session.turns:
        wc = len(turn.passage.split())
        lo, hi = WORD_COUNT_RANGES.get(turn.scene_type, DEFAULT_WORD_RANGE)
        # Allow 20% tolerance on boundaries (LLMs aren't exact)
        lo_flex = int(lo * 0.8)
        hi_flex = int(hi * 1.2)
        if lo_flex <= wc <= hi_flex:
            compliant += 1
        else:
            violations.append({
                "turn": turn.turn_number,
                "word_count": wc,
                "scene_type": turn.scene_type,
                "expected": f"{lo}-{hi}",
            })

    rate = compliant / total
    return MetricResult(
        name="word_count",
        score=rate,
        passed=rate >= 0.80,  # 80% of turns within range
        details=f"{compliant}/{total} turns within word count targets ({len(violations)} violations)",
        raw_data={"violations": violations, "compliance_rate": rate},
    )


def measure_choice_distinctness(session: SessionRecord) -> MetricResult:
    """Measure pairwise distinctness of choices using word overlap.

    For each turn's choice set, compute pairwise Jaccard similarity on
    word sets. Flag turns where any pair exceeds 0.6 similarity (very
    similar wording).
    """
    total = len(session.turns)
    if total == 0:
        return MetricResult("choice_distinctness", 1.0, True, "No turns", {})

    distinct_turns = 0
    similar_pairs: list[dict] = []
    for turn in session.turns:
        choices = turn.choices
        if len(choices) < 2:
            distinct_turns += 1
            continue
        # Compute pairwise Jaccard on word sets
        word_sets = [set(c.lower().split()) for c in choices]
        max_sim = 0.0
        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                intersection = len(word_sets[i] & word_sets[j])
                union = len(word_sets[i] | word_sets[j])
                sim = intersection / union if union > 0 else 0.0
                max_sim = max(max_sim, sim)
                if sim > 0.6:
                    similar_pairs.append({
                        "turn": turn.turn_number,
                        "choice_a": choices[i][:60],
                        "choice_b": choices[j][:60],
                        "similarity": round(sim, 3),
                    })
        if max_sim <= 0.6:
            distinct_turns += 1

    rate = distinct_turns / total
    return MetricResult(
        name="choice_distinctness",
        score=rate,
        passed=rate >= 0.85,  # 85% of turns have distinct choices
        details=f"{distinct_turns}/{total} turns have distinct choices",
        raw_data={"similar_pairs": similar_pairs, "distinctness_rate": rate},
    )


def measure_opening_reflects_choice(session: SessionRecord) -> MetricResult:
    """Check that each passage's opening references the player's prior choice.

    Looks for word overlap between the player action and the first 2
    sentences of the passage. Not a perfect heuristic but catches the
    worst cases where narration ignores the choice entirely.
    """
    # Skip turn 0 (opening, no prior choice)
    scoreable = [t for t in session.turns if t.turn_number > 0]
    if not scoreable:
        return MetricResult("opening_choice", 1.0, True, "No turns to evaluate", {})

    reflected = 0
    misses: list[dict] = []
    for turn in scoreable:
        # Get first 2 sentences of passage
        sentences = re.split(r'[.!?]+', turn.passage)
        opening = " ".join(sentences[:2]).lower()
        # Get key content words from player action (>3 chars)
        action = turn.player_action or ""
        action_words = {w.lower() for w in action.split() if len(w) > 3}
        # Check overlap
        overlap = sum(1 for w in action_words if w in opening)
        if overlap >= 1 or len(action_words) == 0:
            reflected += 1
        else:
            misses.append({
                "turn": turn.turn_number,
                "action": action[:80],
                "opening": opening[:120],
            })

    rate = reflected / len(scoreable) if scoreable else 1.0
    return MetricResult(
        name="opening_choice",
        score=rate,
        passed=rate >= 0.70,
        details=f"{reflected}/{len(scoreable)} turns reflect the player's choice in the opening",
        raw_data={"misses": misses, "reflection_rate": rate},
    )


def measure_passage_specificity(session: SessionRecord) -> MetricResult:
    """Count concrete nouns, proper names, and sensory details per passage.

    Uses a heuristic: count capitalized words (proper nouns), sensory
    adjective stems, and Star Wars-specific terms. Flag passages with
    fewer than 2 specific details.
    """
    SENSORY_STEMS = [
        "smell", "stink", "stench", "reek", "aroma", "scent",
        "cold", "warm", "hot", "cool", "damp", "wet", "dry",
        "loud", "quiet", "hum", "buzz", "crack", "hiss", "groan",
        "bright", "dim", "dark", "glow", "flash", "shadow",
        "rough", "smooth", "sharp", "soft", "grit", "rust",
        "bitter", "sweet", "sour", "metallic", "acrid",
    ]
    SW_TERMS = [
        "blaster", "lightsaber", "hyperspace", "durasteel", "ferrocrete",
        "transparisteel", "turbolaser", "repulsor", "bacta", "credits",
        "cantina", "docking", "datapad", "holocron", "carbonite",
    ]

    total = len(session.turns)
    if total == 0:
        return MetricResult("specificity", 1.0, True, "No passages", {})

    specific_turns = 0
    sparse: list[dict] = []
    for turn in session.turns:
        words = turn.passage.split()
        # Proper nouns: capitalized words not at sentence start
        proper_nouns = 0
        for i, w in enumerate(words):
            if i > 0 and w[0:1].isupper() and not words[i-1].endswith(('.', '!', '?', '"')):
                proper_nouns += 1
        # Sensory details
        passage_lower = turn.passage.lower()
        sensory = sum(1 for s in SENSORY_STEMS if s in passage_lower)
        # Star Wars terms
        sw = sum(1 for t in SW_TERMS if t in passage_lower)
        detail_score = proper_nouns + sensory + sw
        if detail_score >= 2:
            specific_turns += 1
        else:
            sparse.append({
                "turn": turn.turn_number,
                "detail_score": detail_score,
                "proper_nouns": proper_nouns,
                "sensory": sensory,
                "sw_terms": sw,
            })

    rate = specific_turns / total
    return MetricResult(
        name="specificity",
        score=rate,
        passed=rate >= 0.80,
        details=f"{specific_turns}/{total} passages have 2+ specific details",
        raw_data={"sparse_passages": sparse, "specificity_rate": rate},
    )


def measure_thread_tracking(session: SessionRecord) -> MetricResult:
    """Track state changes across turns. Flag sessions with long runs
    of zero state deltas (consequence gaps)."""
    total = len(session.turns)
    if total == 0:
        return MetricResult("thread_tracking", 1.0, True, "No turns", {})

    gap_count = 0
    consecutive_gaps = 0
    max_consecutive = 0
    gap_turns: list[int] = []
    for turn in session.turns:
        deltas = turn.state_deltas or {}
        has_change = any(
            v for k, v in deltas.items()
            if k not in ("reasoning",) and v
        )
        if not has_change:
            gap_count += 1
            consecutive_gaps += 1
            max_consecutive = max(max_consecutive, consecutive_gaps)
            gap_turns.append(turn.turn_number)
        else:
            consecutive_gaps = 0

    gap_rate = gap_count / total
    return MetricResult(
        name="thread_tracking",
        score=1.0 - gap_rate,
        passed=gap_rate < 0.20 and max_consecutive < 4,
        details=(
            f"{gap_count}/{total} turns have zero state deltas "
            f"(max consecutive: {max_consecutive})"
        ),
        raw_data={
            "gap_turns": gap_turns,
            "gap_rate": gap_rate,
            "max_consecutive_gaps": max_consecutive,
        },
    )


# ── Metric Registry ─────────────────────────────────────────────────────

def measure_choice_quality(session: SessionRecord) -> MetricResult:
    """Aggregate choice quality validator results from turn records.

    Only meaningful when the harness ran with real LLMs and the validator
    was active. If no choice_quality data is present, returns a neutral result.
    """
    turns_with_quality = [t for t in session.turns if t.choice_quality]
    if not turns_with_quality:
        return MetricResult(
            "choice_quality", 1.0, True,
            "No choice quality data (validator not active)", {},
        )

    passed = sum(1 for t in turns_with_quality if t.choice_quality.get("passed", True))
    total = len(turns_with_quality)
    rate = passed / total

    # Collect failure dimension frequencies
    dim_fails: Counter = Counter()
    for t in turns_with_quality:
        q = t.choice_quality
        for dim in ("specific", "identity", "risk", "different", "grounded"):
            if not q.get(dim, True):
                dim_fails[dim] += 1

    return MetricResult(
        name="choice_quality",
        score=rate,
        passed=rate >= 0.80,
        details=f"{passed}/{total} turns passed choice quality ({rate:.0%})",
        raw_data={
            "pass_rate": rate,
            "dimension_failures": dict(dim_fails),
            "retry_count": sum(
                1 for t in turns_with_quality
                if t.choice_quality.get("fail_count", 0) >= 2
            ),
        },
    )


def measure_consequence_rate(session: SessionRecord) -> MetricResult:
    """Check what percentage of turns produced meaningful state changes.

    Uses state_deltas from the reconciliation system. A turn with
    zero total_changes is a consequence gap.
    """
    total = len(session.turns)
    if total == 0:
        return MetricResult("consequence_rate", 1.0, True, "No turns", {})

    turns_with_changes = 0
    gaps: list[int] = []
    for turn in session.turns:
        deltas = turn.state_deltas or {}
        if deltas.get("total_changes", 0) > 0:
            turns_with_changes += 1
        else:
            gaps.append(turn.turn_number)

    rate = turns_with_changes / total
    return MetricResult(
        name="consequence_rate",
        score=rate,
        passed=rate >= 0.80,  # 80% of turns should produce state changes
        details=f"{turns_with_changes}/{total} turns produced state changes ({len(gaps)} gaps)",
        raw_data={"gap_turns": gaps, "consequence_rate": rate},
    )


TIER1_METRICS = [
    measure_slop_rate,
    measure_word_count_compliance,
    measure_choice_distinctness,
    measure_opening_reflects_choice,
    measure_passage_specificity,
    measure_thread_tracking,
    measure_choice_quality,
    measure_consequence_rate,
]

# Tier 2 metrics would go here when implemented (require LLM calls)
TIER2_METRICS: list = []


def run_all_metrics(
    session: SessionRecord,
    include_tier2: bool = False,
) -> list[MetricResult]:
    """Run all applicable metrics and return results."""
    metrics = list(TIER1_METRICS)
    if include_tier2:
        metrics.extend(TIER2_METRICS)
    return [m(session) for m in metrics]
