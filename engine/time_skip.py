"""
Time Skip Vignette system — Game Mechanics §19.

Between-act time skips present 1-3 short playable vignettes from the
gap period.  Each vignette is a self-contained narrative moment with
authored passage and 2-3 choices.  NO dice rolls — purely character
decisions that feed behavioral inference, NPC disposition, and Morality.

Duration determines vignette count:
  Short  (1-2 months) → 1 vignette
  Medium (3-6 months) → 2 vignettes
  Long   (6+ months)  → 3 vignettes

Selection considers: behavioral signal matching, NPC relationship
priority, category diversity, and prerequisite filtering.
"""

import logging
import random
from dataclasses import dataclass, field
from typing import Optional


# ── Data models ───────────────────────────────────────────────────────

@dataclass
class VignetteChoice:
    """One authored choice within a vignette."""
    text: str
    skill_tag: str                          # career skill tag for inference
    npc_effects: dict[str, float] = field(default_factory=dict)  # npc_name → disposition delta
    moral_weight: int = 0                   # Conflict accumulation
    morality_bonus: int = 0                 # positive Morality nudge
    aspiration_tags: list[str] = field(default_factory=list)
    narrative_consequence: str = ""         # authored outcome (NOT generated)


@dataclass
class Vignette:
    """One self-contained skip scene from the campaign spine."""
    vignette_id: str
    category: str                           # training, relationship, solitary, crisis, discovery, mundane
    passage: str                            # 3-5 paragraph authored passage
    choices: list[VignetteChoice]
    npc_focus: Optional[str] = None         # NPC name if relationship vignette
    skill_domain: list[str] = field(default_factory=list)
    requires: dict = field(default_factory=dict)   # prerequisite conditions
    excludes: dict = field(default_factory=dict)   # exclusion conditions
    time_stamp: str = ""                    # optional header for long skips


@dataclass
class TimeSkipConfig:
    """Time skip configuration from the campaign spine."""
    duration_months: int
    framing: str                            # brief context for the gap period
    vignettes: list[Vignette] = field(default_factory=list)


@dataclass
class VignetteEffect:
    """Accumulated effects from one vignette choice."""
    vignette_id: str
    choice_index: int
    skill_tag: str
    npc_effects: dict[str, float]
    moral_weight: int
    morality_bonus: int
    aspiration_tags: list[str]
    narrative_consequence: str


@dataclass
class TimeSkipResult:
    """Complete result of a time skip sequence."""
    duration_months: int
    vignettes_presented: list[str]          # vignette IDs in presentation order
    effects: list[VignetteEffect] = field(default_factory=list)
    skill_drift_applied: dict[str, float] = field(default_factory=dict)
    npc_drift_applied: dict[str, float] = field(default_factory=dict)
    total_conflict: int = 0
    total_morality_bonus: int = 0


# ── Constants ─────────────────────────────────────────────────────────

VIGNETTE_CATEGORIES = [
    "training", "relationship", "solitary", "crisis", "discovery", "mundane",
]

# NPC disposition drift per month toward neutral (0.5)
NPC_DRIFT_RATE = 0.02

# Close relationships resist drift
NPC_DRIFT_RESISTANCE_HIGH = 0.8   # disposition > this resists drift
NPC_DRIFT_RESISTANCE_LOW = 0.2    # disposition < this resists drift


# ── Vignette count by duration ────────────────────────────────────────

def vignette_count_for_duration(months: int) -> int:
    """Return how many vignettes to present based on skip duration."""
    if months <= 2:
        return 1
    elif months <= 6:
        return 2
    else:
        return 3


# ── Loading from spine ────────────────────────────────────────────────

def load_time_skip_config(spine_act_transition: dict) -> Optional[TimeSkipConfig]:
    """
    Load time skip config from the campaign spine.

    The time_skip field lives on the act that the skip leads INTO,
    meaning spine["acts"][next_act_number - 1]["time_skip"].
    Returns None if no time skip is defined for this transition.
    """
    ts = spine_act_transition.get("time_skip")
    if not ts:
        return None

    vignettes = []
    for v in ts.get("vignettes", []):
        choices = []
        for c in v.get("choices", []):
            choices.append(VignetteChoice(
                text=c["text"],
                skill_tag=c.get("skill_tag", ""),
                npc_effects=c.get("npc_effects", {}),
                moral_weight=c.get("moral_weight", 0),
                morality_bonus=c.get("morality_bonus", 0),
                aspiration_tags=c.get("aspiration_tags", []),
                narrative_consequence=c.get("narrative_consequence", ""),
            ))
        vignettes.append(Vignette(
            vignette_id=v["vignette_id"],
            category=v.get("category", "mundane"),
            passage=v.get("passage", ""),
            choices=choices,
            npc_focus=v.get("npc_focus"),
            skill_domain=v.get("skill_domain", []),
            requires=v.get("requires", {}),
            excludes=v.get("excludes", {}),
            time_stamp=v.get("time_stamp", ""),
        ))

    return TimeSkipConfig(
        duration_months=ts.get("duration_months", 1),
        framing=ts.get("framing", ""),
        vignettes=vignettes,
    )


# ── Prerequisite checking ────────────────────────────────────────────

def _check_prerequisites(vignette: Vignette, character, npc_states: list) -> bool:
    """
    Check if a vignette's prerequisites are met.

    Supported conditions:
      - force_sensitive: bool — character.force_rating > 0
      - min_disposition: {npc_name: float} — NPC disposition >= threshold
      - npc_present: str — NPC name exists in npc_states
    """
    reqs = vignette.requires
    if not reqs:
        return True

    # Force sensitivity check
    if reqs.get("force_sensitive") or reqs.get("latent_force_sensitive"):
        if character.force_rating <= 0:
            return False

    # NPC disposition thresholds
    for npc_name, threshold in reqs.get("min_disposition", {}).items():
        npc = next((n for n in npc_states if n.name == npc_name), None)
        if npc is None or npc.disposition < threshold:
            return False

    # NPC presence check
    npc_required = reqs.get("npc_present")
    if npc_required:
        npc_names = [n.name for n in npc_states]
        if npc_required not in npc_names:
            return False

    return True


def _check_exclusions(vignette: Vignette, character, npc_states: list) -> bool:
    """Return True if vignette should be EXCLUDED (not shown)."""
    excl = vignette.excludes
    if not excl:
        return False

    # Same checks but inverted — if condition met, exclude
    if excl.get("force_sensitive") and character.force_rating > 0:
        return True

    return False


# ── Vignette selection ────────────────────────────────────────────────

def select_vignettes(
    config: TimeSkipConfig,
    character,
    npc_states: list,
    behavioral_fingerprint: Optional[dict] = None,
) -> list[Vignette]:
    """
    Select vignettes from the library based on:
    1. Prerequisite filtering
    2. Behavioral signal matching (player's choice patterns)
    3. NPC relationship priority (strongest relationships featured first)
    4. Category diversity (must span at least 2 categories)

    Returns selected vignettes in presentation order.
    """
    target_count = vignette_count_for_duration(config.duration_months)

    # Step 1: Filter by prerequisites and exclusions
    eligible = [
        v for v in config.vignettes
        if _check_prerequisites(v, character, npc_states)
        and not _check_exclusions(v, character, npc_states)
    ]

    if not eligible:
        logging.warning("No eligible vignettes after prerequisite filtering")
        return []

    if len(eligible) <= target_count:
        return eligible[:target_count]

    # Step 2: Score each vignette
    scored = []
    for v in eligible:
        score = _score_vignette(v, character, npc_states, behavioral_fingerprint)
        scored.append((score, v))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Step 3: Select with category diversity constraint
    selected = []
    categories_used = set()

    for score, v in scored:
        if len(selected) >= target_count:
            break
        # Enforce category diversity: if we need 2+ vignettes,
        # second vignette must be a different category
        if len(selected) == 1 and target_count >= 2:
            if v.category in categories_used and len(scored) > 2:
                # Try to find a different category
                continue
        selected.append(v)
        categories_used.add(v.category)

    # If diversity constraint left us short, fill from remaining
    if len(selected) < target_count:
        for score, v in scored:
            if v not in selected:
                selected.append(v)
                if len(selected) >= target_count:
                    break

    return selected[:target_count]


def _score_vignette(
    vignette: Vignette,
    character,
    npc_states: list,
    fingerprint: Optional[dict],
) -> float:
    """
    Score a vignette for selection priority.

    Factors:
    - Behavioral signal match (dominant_tags overlap with skill_domain)
    - NPC relationship strength (strongest dispositions rank higher)
    - Category variety bonus
    """
    score = 0.0

    # Behavioral signal matching — does this vignette's skill domain
    # match the player's demonstrated interests?
    if fingerprint:
        dominant_tags = set(fingerprint.get("dominant_tags", []))
        dominant_priorities = set(fingerprint.get("dominant_priorities", []))
        domain_set = set(vignette.skill_domain)

        # Direct skill overlap
        overlap = domain_set & dominant_tags
        score += len(overlap) * 0.3

        # Priority overlap with aspiration tags in choices
        for choice in vignette.choices:
            aspiration_overlap = set(choice.aspiration_tags) & dominant_priorities
            score += len(aspiration_overlap) * 0.15

    # NPC relationship priority — vignettes featuring high-relationship NPCs
    if vignette.npc_focus:
        npc = next((n for n in npc_states if n.name == vignette.npc_focus), None)
        if npc:
            # Distance from neutral (0.5) = relationship strength
            relationship_strength = abs(npc.disposition - 0.5) * 2
            score += relationship_strength * 0.4

    # Category scoring — training and relationship slightly preferred
    category_bonus = {
        "relationship": 0.1,
        "training": 0.05,
        "crisis": 0.05,
        "discovery": 0.0,
        "solitary": 0.0,
        "mundane": -0.05,
    }
    score += category_bonus.get(vignette.category, 0.0)

    # Small random factor to prevent deterministic selection
    score += random.uniform(0, 0.1)

    return score


# ── Effect processing ─────────────────────────────────────────────────

def process_vignette_choice(
    vignette: Vignette, choice_index: int,
) -> VignetteEffect:
    """Process a single vignette choice and return its effects."""
    if choice_index < 0 or choice_index >= len(vignette.choices):
        raise ValueError(
            f"Invalid choice_index {choice_index} for vignette "
            f"{vignette.vignette_id} with {len(vignette.choices)} choices"
        )

    choice = vignette.choices[choice_index]
    return VignetteEffect(
        vignette_id=vignette.vignette_id,
        choice_index=choice_index,
        skill_tag=choice.skill_tag,
        npc_effects=dict(choice.npc_effects),
        moral_weight=choice.moral_weight,
        morality_bonus=choice.morality_bonus,
        aspiration_tags=list(choice.aspiration_tags),
        narrative_consequence=choice.narrative_consequence,
    )


def aggregate_vignette_effects(effects: list[VignetteEffect]) -> dict:
    """
    Aggregate effects from all vignette choices into a summary dict.

    Returns:
        skill_tags: list of skill tags (fed to behavioral inference)
        npc_effects: {npc_name: total_disposition_delta}
        total_conflict: sum of moral_weight
        total_morality_bonus: sum of morality_bonus
        aspiration_tags: combined unique tags
    """
    skill_tags = []
    npc_effects: dict[str, float] = {}
    total_conflict = 0
    total_morality_bonus = 0
    aspiration_tags: set[str] = set()

    for effect in effects:
        if effect.skill_tag:
            skill_tags.append(effect.skill_tag)
        for npc_name, delta in effect.npc_effects.items():
            npc_effects[npc_name] = npc_effects.get(npc_name, 0.0) + delta
        total_conflict += effect.moral_weight
        total_morality_bonus += effect.morality_bonus
        aspiration_tags.update(effect.aspiration_tags)

    return {
        "skill_tags": skill_tags,
        "npc_effects": npc_effects,
        "total_conflict": total_conflict,
        "total_morality_bonus": total_morality_bonus,
        "aspiration_tags": sorted(aspiration_tags),
    }


# ── NPC disposition application ───────────────────────────────────────

def apply_vignette_npc_effects(
    npc_effects: dict[str, float], npc_states: list,
) -> None:
    """Apply vignette-driven NPC disposition changes. Clamps to [0, 1]."""
    npc_map = {n.name: n for n in npc_states}
    for npc_name, delta in npc_effects.items():
        npc = npc_map.get(npc_name)
        if npc:
            npc.disposition = max(0.0, min(1.0, npc.disposition + delta))
            logging.info(
                f"Vignette NPC effect: {npc_name} disposition "
                f"{npc.disposition - delta:.2f} → {npc.disposition:.2f}"
            )


# ── NPC relationship drift ───────────────────────────────────────────

def apply_npc_time_drift(
    npc_states: list, duration_months: int,
) -> dict[str, float]:
    """
    Apply NPC disposition drift during time skip.

    - Dispositions drift toward neutral (0.5) at NPC_DRIFT_RATE per month
    - Close relationships (>0.8 or <0.2) resist drift
    - Returns dict of {npc_name: total_drift_applied}
    """
    drift_applied = {}
    for npc in npc_states:
        if npc.disposition > NPC_DRIFT_RESISTANCE_HIGH:
            # Strong positive — resist drift
            continue
        if npc.disposition < NPC_DRIFT_RESISTANCE_LOW:
            # Strong negative — resist drift
            continue

        total_drift = NPC_DRIFT_RATE * duration_months
        if npc.disposition > 0.5:
            actual_drift = -min(total_drift, npc.disposition - 0.5)
        elif npc.disposition < 0.5:
            actual_drift = min(total_drift, 0.5 - npc.disposition)
        else:
            actual_drift = 0.0

        if actual_drift != 0.0:
            old_disp = npc.disposition
            npc.disposition = round(npc.disposition + actual_drift, 3)
            drift_applied[npc.name] = actual_drift
            logging.info(
                f"NPC time drift: {npc.name} {old_disp:.3f} → "
                f"{npc.disposition:.3f} ({duration_months} months)"
            )

    return drift_applied


# ── Strain/wound recovery during skip ─────────────────────────────────

def apply_time_skip_recovery(character, duration_months: int) -> dict:
    """
    Full recovery after any 1+ week skip.
    Wounds and strain reset to 0.
    """
    old_strain = character.current_strain
    old_wounds = character.current_wounds
    character.current_strain = 0
    character.current_wounds = 0
    return {
        "strain_recovered": old_strain,
        "wounds_recovered": old_wounds,
    }


# ── Build vignette turn rows for inference ────────────────────────────

def build_vignette_inference_rows(effects: list[VignetteEffect]) -> list[dict]:
    """
    Convert vignette effects into pseudo-turn rows for behavioral inference.

    Vignette choices are weighted as if they were the final 2-3 turns
    of the act, giving them appropriate influence on skill inference.
    """
    rows = []
    for effect in effects:
        rows.append({
            "turn_number": 9000 + len(rows),  # high number to sort last
            "check_skill": None,
            "check_difficulty": None,
            "roll_result_json": None,
            "skill_tags_json": json.dumps([effect.skill_tag]) if effect.skill_tag else None,
            "choice_index": effect.choice_index,
            "moral_weight": effect.moral_weight,
            "choice_implications": json.dumps({
                "behavioral_tags": effect.aspiration_tags,
                "priority_revealed": effect.skill_tag,
            }) if effect.skill_tag else None,
        })
    return rows


# ── Serialization helpers ─────────────────────────────────────────────

def serialize_vignette(v: Vignette) -> dict:
    """Serialize a Vignette for API response / arc_state storage."""
    return {
        "vignette_id": v.vignette_id,
        "category": v.category,
        "passage": v.passage,
        "time_stamp": v.time_stamp,
        "npc_focus": v.npc_focus,
        "choices": [
            {"text": c.text, "index": i}
            for i, c in enumerate(v.choices)
        ],
    }


def serialize_time_skip_state(
    config: TimeSkipConfig,
    selected: list[Vignette],
    effects: list[VignetteEffect],
    current_index: int,
) -> dict:
    """Serialize the time skip state for storage in arc_state_json."""
    return {
        "duration_months": config.duration_months,
        "framing": config.framing,
        "selected_ids": [v.vignette_id for v in selected],
        "current_vignette_index": current_index,
        "effects": [
            {
                "vignette_id": e.vignette_id,
                "choice_index": e.choice_index,
                "skill_tag": e.skill_tag,
                "npc_effects": e.npc_effects,
                "moral_weight": e.moral_weight,
                "morality_bonus": e.morality_bonus,
                "aspiration_tags": e.aspiration_tags,
                "narrative_consequence": e.narrative_consequence,
            }
            for e in effects
        ],
        "all_vignettes": [
            _serialize_full_vignette(v) for v in selected
        ],
    }


def deserialize_time_skip_state(data: dict) -> tuple:
    """
    Restore time skip state from arc_state_json.
    Returns (selected_vignettes, effects, current_index).
    """
    vignettes = []
    for v_data in data.get("all_vignettes", []):
        choices = []
        for c in v_data.get("choices", []):
            choices.append(VignetteChoice(
                text=c["text"],
                skill_tag=c.get("skill_tag", ""),
                npc_effects=c.get("npc_effects", {}),
                moral_weight=c.get("moral_weight", 0),
                morality_bonus=c.get("morality_bonus", 0),
                aspiration_tags=c.get("aspiration_tags", []),
                narrative_consequence=c.get("narrative_consequence", ""),
            ))
        vignettes.append(Vignette(
            vignette_id=v_data["vignette_id"],
            category=v_data.get("category", "mundane"),
            passage=v_data.get("passage", ""),
            choices=choices,
            npc_focus=v_data.get("npc_focus"),
            skill_domain=v_data.get("skill_domain", []),
            time_stamp=v_data.get("time_stamp", ""),
        ))

    effects = []
    for e_data in data.get("effects", []):
        effects.append(VignetteEffect(
            vignette_id=e_data["vignette_id"],
            choice_index=e_data["choice_index"],
            skill_tag=e_data["skill_tag"],
            npc_effects=e_data.get("npc_effects", {}),
            moral_weight=e_data.get("moral_weight", 0),
            morality_bonus=e_data.get("morality_bonus", 0),
            aspiration_tags=e_data.get("aspiration_tags", []),
            narrative_consequence=e_data.get("narrative_consequence", ""),
        ))

    return vignettes, effects, data.get("current_vignette_index", 0)


def _serialize_full_vignette(v: Vignette) -> dict:
    """Full serialization of a vignette including choice details."""
    return {
        "vignette_id": v.vignette_id,
        "category": v.category,
        "passage": v.passage,
        "time_stamp": v.time_stamp,
        "npc_focus": v.npc_focus,
        "skill_domain": v.skill_domain,
        "choices": [
            {
                "text": c.text,
                "skill_tag": c.skill_tag,
                "npc_effects": c.npc_effects,
                "moral_weight": c.moral_weight,
                "morality_bonus": c.morality_bonus,
                "aspiration_tags": c.aspiration_tags,
                "narrative_consequence": c.narrative_consequence,
            }
            for c in v.choices
        ],
    }


# Need json for build_vignette_inference_rows
import json
