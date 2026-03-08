"""
Talent tree engine (Game Mechanics §15).

Loads talent library and specialization trees. Applies Type 1 (passive)
and Type 2 (conditional) talents to the dice pool pipeline. Provides
context for Type 3 (substitution) and Type 4 (narrative enabler) talents
to the GM prompts.

This module is pure Python — no LLM dependencies, no API keys.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Paths ─────────────────────────────────────────────────────────────

TALENT_TREES_DIR = Path(__file__).parent.parent / "data" / "talent_trees"


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class TalentActivation:
    """Record of a talent firing during pool modification or intervention."""
    talent_name:       str
    talent_type:       str       # "passive", "conditional", "intervention"
    effect_description: str = ""
    strain_charged:    int = 0
    narrative_hint:    str = ""  # from narrative_identity / prose_tags


@dataclass
class TreeEntry:
    """One node in a specialization tree."""
    id:            str
    talent_ref:    str
    tier:          int
    position:      int
    xp_cost:       int
    prerequisites: list[str] = field(default_factory=list)


@dataclass
class TreePath:
    """Named thematic branch within a tree."""
    theme:       str
    description: str
    talent_ids:  list[str] = field(default_factory=list)


@dataclass
class SpecializationTree:
    """A complete specialization talent tree."""
    specialization: str
    career:         str
    game_line:      str
    entries:        list[TreeEntry]   = field(default_factory=list)
    tree_paths:     dict[str, TreePath] = field(default_factory=dict)


# ── Talent library cache ──────────────────────────────────────────────

_library_cache: Optional[dict] = None


def load_talent_library() -> dict:
    """
    Load the central talent library from JSON.
    Returns dict keyed by talent_ref with full talent definitions.
    """
    path = TALENT_TREES_DIR / "talent_library.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["talents"]


def _get_library() -> dict:
    """Cached talent library access."""
    global _library_cache
    if _library_cache is None:
        _library_cache = load_talent_library()
    return _library_cache


def load_specialization_tree(name: str) -> SpecializationTree:
    """
    Load a specialization tree from JSON.
    name: filename without extension, e.g. "smuggler_pilot"
    """
    path = TALENT_TREES_DIR / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    entries = [
        TreeEntry(
            id=e["id"],
            talent_ref=e["talent_ref"],
            tier=e["tier"],
            position=e["position"],
            xp_cost=e["xp_cost"],
            prerequisites=e.get("prerequisites", []),
        )
        for e in data["talents"]
    ]

    paths = {}
    for key, p in data.get("tree_paths", {}).items():
        paths[key] = TreePath(
            theme=p["theme"],
            description=p["description"],
            talent_ids=p.get("talent_ids", []),
        )

    return SpecializationTree(
        specialization=data["specialization"],
        career=data["career"],
        game_line=data["game_line"],
        entries=entries,
        tree_paths=paths,
    )


# ── Talent rank computation ──────────────────────────────────────────

def get_talent_rank(character, talent_ref: str) -> int:
    """
    Get the effective rank of a talent across all acquisitions.
    Each entry in acquired_talents with this talent_ref contributes 1 rank.
    """
    return sum(
        1 for t in getattr(character, "acquired_talents", [])
        if t.get("talent_ref") == talent_ref
    )


def get_acquired_refs(character) -> set[str]:
    """Return the set of talent_refs the character has acquired."""
    return {
        t.get("talent_ref")
        for t in getattr(character, "acquired_talents", [])
        if t.get("talent_ref")
    }


# ── Pipeline Stage 2: Passive talent modifiers (§15.3) ───────────────

def apply_passive_modifiers(pool, character, skill: str) -> list[TalentActivation]:
    """
    Stage 2 of pool modification pipeline.
    Applies Type 1 passive pool modifiers for acquired talents.
    Returns list of activations for narration context.
    Does NOT modify thresholds (those are applied at acquisition time).
    """
    library = _get_library()
    activations = []

    acquired_refs = get_acquired_refs(character)
    if not acquired_refs:
        return activations

    # Group by talent_ref and count ranks
    ref_ranks: dict[str, int] = {}
    for t in character.acquired_talents:
        ref = t.get("talent_ref")
        if ref:
            ref_ranks[ref] = ref_ranks.get(ref, 0) + 1

    for talent_ref, rank in ref_ranks.items():
        defn = library.get(talent_ref)
        if not defn:
            continue

        # Only process passive talents with pool modifiers
        if defn.get("talent_type") != "passive":
            continue

        for eff in defn.get("effects", []):
            if eff.get("type") != "modify_pool":
                continue

            # Check if this skill is targeted
            target_skills = eff.get("target_skills", [])
            if target_skills and skill not in target_skills:
                continue

            # Apply modifier × rank
            modifier = eff.get("modifier", {})
            for die_type, delta in modifier.items():
                current = getattr(pool, die_type, 0)
                new_val = max(0, current + delta * rank)
                setattr(pool, die_type, new_val)

            activations.append(TalentActivation(
                talent_name=defn["name"],
                talent_type="passive",
                effect_description=(
                    f"{'Removed' if list(modifier.values())[0] < 0 else 'Added'} "
                    f"{abs(list(modifier.values())[0] * rank)} "
                    f"{list(modifier.keys())[0]} "
                    f"{'die' if abs(list(modifier.values())[0] * rank) == 1 else 'dice'}"
                ),
                narrative_hint=defn.get("narrative_identity", "")[:100],
            ))

    return activations


# ── Pipeline Stage 3: Conditional talent modifiers (§15.3) ───────────

def apply_conditional_modifiers(
    pool,
    character,
    scene_type: str,
    check_skill: str = "",
) -> list[TalentActivation]:
    """
    Stage 3 of pool modification pipeline.
    Applies Type 2 conditional talent modifiers based on scene context.
    Charges strain if triggered. Returns activations.
    """
    library = _get_library()
    activations = []

    acquired_refs = get_acquired_refs(character)
    if not acquired_refs:
        return activations

    ref_ranks: dict[str, int] = {}
    for t in character.acquired_talents:
        ref = t.get("talent_ref")
        if ref:
            ref_ranks[ref] = ref_ranks.get(ref, 0) + 1

    for talent_ref, rank in ref_ranks.items():
        defn = library.get(talent_ref)
        if not defn:
            continue

        if defn.get("talent_type") != "conditional":
            continue

        for eff in defn.get("effects", []):
            if eff.get("type") != "conditional":
                continue

            condition = eff.get("condition", {})

            # Check scene type match
            scene_types = condition.get("scene_types", [])
            if scene_types and scene_type not in scene_types:
                continue

            # Check skill match (for skill-specific conditionals)
            check_skills = condition.get("check_skills", [])
            if check_skills and check_skill not in check_skills:
                continue

            # Check strain affordability
            strain_cost = eff.get("strain_cost", 0) * rank
            if strain_cost > 0:
                threshold = getattr(character, "strain_threshold", 12)
                if character.current_strain + strain_cost > threshold:
                    continue

            # Apply modifier × rank
            modifier = eff.get("modifier", {})
            for die_type, delta in modifier.items():
                total_delta = delta * rank
                current = getattr(pool, die_type, 0)
                new_val = max(0, current + total_delta)
                setattr(pool, die_type, new_val)

            # Charge strain
            if strain_cost > 0:
                character.current_strain += strain_cost

            activations.append(TalentActivation(
                talent_name=defn["name"],
                talent_type="conditional",
                effect_description=(
                    f"Activated in {scene_type} scene"
                    + (f", {strain_cost} strain charged" if strain_cost else "")
                ),
                strain_charged=strain_cost,
                narrative_hint=defn.get("narrative_identity", "")[:100],
            ))

    return activations


# ── Characteristic override (Phase 15.5) ─────────────────────────────

def get_characteristic_override(character, skill: str) -> str | None:
    """
    Check if the character has a Type 3 substitution talent that overrides
    the governing characteristic for a skill (e.g., lightsaber uses
    Willpower instead of Brawn via Niman Technique).

    Returns the override characteristic name, or None if no override applies.
    """
    library = _get_library()
    acquired_refs = get_acquired_refs(character)

    for talent_ref in acquired_refs:
        defn = library.get(talent_ref)
        if not defn:
            continue
        for eff in defn.get("effects", []):
            if eff.get("type") != "substitution":
                continue
            if skill in eff.get("original_skills", []):
                override = eff.get("characteristic_override")
                if override:
                    return override
    return None


# ── Context builders for GM prompts ───────────────────────────────────

def build_talent_check_effects(character) -> str:
    """
    Build the TALENT EFFECTS section for the check decision prompt.
    Includes Type 3 (substitution) and relevant Type 4 (narrative enabler)
    talents. Returns empty string if no relevant talents.
    """
    library = _get_library()
    acquired_refs = get_acquired_refs(character)
    if not acquired_refs:
        return ""

    lines = []
    for talent_ref in acquired_refs:
        defn = library.get(talent_ref)
        if not defn:
            continue

        for eff in defn.get("effects", []):
            if eff.get("type") == "substitution":
                char_override = eff.get("characteristic_override")
                if char_override:
                    # Characteristic substitution (e.g., lightsaber uses Willpower)
                    original = ", ".join(
                        s.replace("_", " ").title()
                        for s in eff.get("original_skills", [])
                    )
                    lines.append(
                        f"- {defn['name']}: {original} skill may use "
                        f"{char_override.replace('_', ' ').title()} "
                        f"instead of the default characteristic."
                    )
                else:
                    # Skill substitution (e.g., use Deception in place of Charm)
                    original = ", ".join(
                        s.replace("_", " ").title()
                        for s in eff.get("original_skills", [])
                    )
                    sub = eff.get("substitute_skill", "").replace("_", " ").title()
                    lines.append(
                        f"- {defn['name']}: This character may use {sub} "
                        f"in place of {original}."
                    )

            elif eff.get("type") == "narrative_enabler":
                desc = eff.get("description", "")
                if desc and _is_check_relevant_enabler(eff):
                    lines.append(f"- {defn['name']}: {desc}")

    if not lines:
        return ""

    return "TALENT EFFECTS:\n" + "\n".join(lines)


def _is_check_relevant_enabler(effect: dict) -> bool:
    """Check if a narrative enabler affects check validity."""
    cap = effect.get("capability", "")
    return cap in {
        "bypass_security_systems",
        "blend_in",
    }


def build_talent_capabilities(character) -> str:
    """
    Build the CHARACTER CAPABILITIES section for the narration prompt.
    Includes Type 3 (substitution) and Type 4 (narrative enabler) talents.
    Returns empty string if no relevant talents.
    """
    library = _get_library()
    acquired_refs = get_acquired_refs(character)
    if not acquired_refs:
        return ""

    lines = []
    for talent_ref in acquired_refs:
        defn = library.get(talent_ref)
        if not defn:
            continue

        talent_type = defn.get("talent_type")
        if talent_type == "substitution":
            lines.append(
                f"- {defn['name']}: {defn.get('narrative_identity', '')}"
            )
        elif talent_type == "narrative_enabler":
            for eff in defn.get("effects", []):
                if eff.get("type") == "narrative_enabler":
                    lines.append(
                        f"- {defn['name']}: {eff.get('description', '')}"
                    )
        elif talent_type == "passive":
            # Multi-effect talents that also have a narrative_enabler effect
            for eff in defn.get("effects", []):
                if eff.get("type") == "narrative_enabler":
                    lines.append(
                        f"- {defn['name']}: {eff.get('description', '')}"
                    )

    if not lines:
        return ""

    return "CHARACTER CAPABILITIES:\n" + "\n".join(lines)


def build_talent_activations_block(activations: list[TalentActivation]) -> str:
    """
    Build the TALENT ACTIVATIONS THIS TURN section for narration prompt.
    Returns empty string if no activations.
    """
    if not activations:
        return ""

    lines = []
    for act in activations:
        line = f"- {act.talent_name}: {act.effect_description}"
        if act.strain_charged:
            line += f" ({act.strain_charged} strain)"
        if act.narrative_hint:
            line += f". {act.narrative_hint}"
        lines.append(line)

    return "TALENT ACTIVATIONS THIS TURN:\n" + "\n".join(lines)


# ── Threshold modifier application (at acquisition time) ─────────────

def apply_threshold_modifiers(character) -> None:
    """
    Apply all Type 1 threshold modifiers (Grit, Toughened) to the character.
    Called when talents are first acquired or loaded.
    Idempotent — recalculates from base thresholds.
    """
    library = _get_library()

    # Base thresholds (from character data, before talent modifications)
    base_strain = getattr(character, "_base_strain_threshold",
                          character.strain_threshold)
    base_wound = getattr(character, "_base_wound_threshold",
                         character.wound_threshold)

    # Store base values if not yet stored
    if not hasattr(character, "_base_strain_threshold"):
        character._base_strain_threshold = base_strain
    if not hasattr(character, "_base_wound_threshold"):
        character._base_wound_threshold = base_wound

    strain_bonus = 0
    wound_bonus = 0

    ref_ranks: dict[str, int] = {}
    for t in getattr(character, "acquired_talents", []):
        ref = t.get("talent_ref")
        if ref:
            ref_ranks[ref] = ref_ranks.get(ref, 0) + 1

    for talent_ref, rank in ref_ranks.items():
        defn = library.get(talent_ref)
        if not defn or defn.get("talent_type") != "passive":
            continue
        for eff in defn.get("effects", []):
            if eff.get("type") != "modify_threshold":
                continue
            target = eff.get("target", "")
            mod = eff.get("modifier", 0)
            if target == "strain_threshold":
                strain_bonus += mod * rank
            elif target == "wound_threshold":
                wound_bonus += mod * rank

    character.strain_threshold = base_strain + strain_bonus
    character.wound_threshold = base_wound + wound_bonus


# ── Milestone reflection helpers (Phase 12, §14.3) ──────────────────

@dataclass
class MilestoneChoice:
    """One option in a talent milestone reflection."""
    branch_key:       str        # tree_path key (e.g. "vehicle_mastery")
    branch_theme:     str        # human-readable theme
    branch_description: str      # tree_path description
    talent_ref:       str        # library key to acquire
    talent_name:      str        # display name
    tree_name:        str        # specialization name
    entry_id:         str        # tree entry ID for acquisition tracking
    xp_cost:          int        # cost in reserved_xp
    narrative_identity: str      # from library — what this talent *means*
    prose_tags:        list[str] # from library — narration flavor


def get_available_talents(
    character,
    tree_names: list[str] | None = None,
) -> list[dict]:
    """
    Find talents available for purchase across the character's trees.
    Returns list of dicts with entry info + library definition.
    Respects prerequisites — only returns talents whose prereqs are all acquired.
    """
    if tree_names is None:
        career_str = (character.career.value
                      if hasattr(character.career, "value")
                      else str(character.career))
        tree_names = [
            f"{career_str}_{spec}"
            for spec in getattr(character, "specializations", [])
        ]

    acquired_entry_ids = {
        t.get("entry_id")
        for t in getattr(character, "acquired_talents", [])
        if t.get("entry_id")
    }
    acquired_refs = get_acquired_refs(character)
    library = _get_library()
    available = []

    for tree_name in tree_names:
        try:
            tree = load_specialization_tree(tree_name)
        except FileNotFoundError:
            continue

        for entry in tree.entries:
            # Skip already acquired entries
            if entry.id in acquired_entry_ids:
                continue

            # Check prerequisites — all must be acquired
            if entry.prerequisites and not all(
                p in acquired_entry_ids for p in entry.prerequisites
            ):
                continue

            # Check ranked talent max rank
            defn = library.get(entry.talent_ref, {})
            max_rank = defn.get("max_rank", 1)
            current_rank = get_talent_rank(character, entry.talent_ref)
            if current_rank >= max_rank:
                continue

            available.append({
                "entry_id": entry.id,
                "talent_ref": entry.talent_ref,
                "tier": entry.tier,
                "position": entry.position,
                "xp_cost": entry.xp_cost,
                "tree_name": tree_name,
                "tree_specialization": tree.specialization,
                "defn": defn,
            })

    return available


def build_milestone_choices(
    character,
    reserved_xp: int,
    max_choices: int = 3,
) -> list[MilestoneChoice]:
    """
    Generate milestone reflection choices grouped by tree branch (§14.3).

    Process:
    1. Find all available talents across character's trees
    2. Group by tree_path branch
    3. Select lowest-tier unacquired talent per branch
    4. Return up to max_choices options (one per branch)
    """
    career_str = (character.career.value
                  if hasattr(character.career, "value")
                  else str(character.career))
    tree_names = [
        f"{career_str}_{spec}"
        for spec in getattr(character, "specializations", [])
    ]

    available = get_available_talents(character, tree_names)
    if not available:
        return []

    library = _get_library()

    # Build branch → available talents mapping
    branch_talents: dict[str, list[dict]] = {}

    for tree_name in tree_names:
        try:
            tree = load_specialization_tree(tree_name)
        except FileNotFoundError:
            continue

        for path_key, path in tree.tree_paths.items():
            branch_key = f"{tree_name}:{path_key}"
            for talent_info in available:
                if (talent_info["tree_name"] == tree_name
                        and talent_info["entry_id"] in path.talent_ids):
                    if branch_key not in branch_talents:
                        branch_talents[branch_key] = []
                    branch_talents[branch_key].append({
                        **talent_info,
                        "path_key": path_key,
                        "path_theme": path.theme,
                        "path_description": path.description,
                    })

    # Select lowest-tier affordable talent per branch
    choices = []
    for branch_key, talents in branch_talents.items():
        # Sort by tier, then position
        talents.sort(key=lambda t: (t["tier"], t["position"]))
        for t in talents:
            if t["xp_cost"] <= reserved_xp:
                defn = t["defn"]
                choices.append(MilestoneChoice(
                    branch_key=t["path_key"],
                    branch_theme=t["path_theme"],
                    branch_description=t["path_description"],
                    talent_ref=t["talent_ref"],
                    talent_name=defn.get("name", t["talent_ref"]),
                    tree_name=t["tree_name"],
                    entry_id=t["entry_id"],
                    xp_cost=t["xp_cost"],
                    narrative_identity=defn.get("narrative_identity", ""),
                    prose_tags=defn.get("prose_tags", []),
                ))
                break  # one per branch

    # Sort by tier (lowest first) and limit to max_choices
    choices.sort(key=lambda c: c.xp_cost)
    return choices[:max_choices]


def acquire_talent(character, choice: MilestoneChoice) -> None:
    """
    Apply a milestone talent acquisition to the character.
    Deducts reserved_xp, adds to acquired_talents, applies threshold modifiers.
    Phase 15: also handles Force Rating increase via Category 3 milestone (§16.4).
    """
    character.reserved_xp = max(0, character.reserved_xp - choice.xp_cost)
    character.acquired_talents.append({
        "talent_ref": choice.talent_ref,
        "tree": choice.tree_name,
        "entry_id": choice.entry_id,
    })

    # Apply threshold modifiers (Grit, Toughened) immediately
    library = _get_library()
    defn = library.get(choice.talent_ref, {})
    if defn.get("talent_type") == "passive":
        for eff in defn.get("effects", []):
            if eff.get("type") == "modify_threshold":
                apply_threshold_modifiers(character)
                break
            # Phase 15: Force Rating increase (§16.4)
            if eff.get("type") == "force_rating_increase":
                old_rating = character.force_rating
                character.force_rating += eff.get("modifier", 1)
                logging.info(
                    f"Force Rating increase: {old_rating} -> {character.force_rating} "
                    f"via {defn.get('name', choice.talent_ref)}"
                )
                character.advancement_log.append({
                    "type": "force_rating_increase",
                    "old_rating": old_rating,
                    "new_rating": character.force_rating,
                    "talent_ref": choice.talent_ref,
                })


# ── Type 5 Intervention helpers (Phase 12, §15.1) ───────────────────

@dataclass
class InterventionOffer:
    """Offer to use a Type 5 intervention talent."""
    talent_ref:        str
    talent_name:       str
    effect:            str        # "reroll"
    applicable_skills: list[str]
    strain_cost:       int
    scope:             str        # "session" or "encounter"
    narrative_prompt:  str        # prose for the pre-narration choice


def check_interventions(
    character,
    check_skill: str,
    roll_succeeded: bool,
    current_act: int = 1,
) -> InterventionOffer | None:
    """
    Check if any Type 5 intervention talent can fire (§15.1).
    Called after dice result is known, before narration.

    Returns an InterventionOffer if one is available, None otherwise.
    Only offers the first applicable intervention (most specific first).
    """
    library = _get_library()
    acquired_refs = get_acquired_refs(character)
    talent_uses = getattr(character, "talent_uses", {})

    for talent_ref in acquired_refs:
        defn = library.get(talent_ref)
        if not defn or defn.get("talent_type") != "intervention":
            continue

        for eff in defn.get("effects", []):
            if eff.get("type") != "intervention":
                continue

            # Check trigger condition
            trigger = eff.get("trigger", "any_check")
            if trigger == "failed_check" and roll_succeeded:
                continue

            # Check applicable skills
            applicable = eff.get("applicable_skills", [])
            if applicable and check_skill not in applicable:
                continue

            # Check usage — "session" means once per act
            scope = eff.get("scope", "session")
            rank = get_talent_rank(character, talent_ref)
            max_uses = rank  # ranked talents get more uses
            current_uses = talent_uses.get(talent_ref, 0)
            if current_uses >= max_uses:
                continue

            # Check strain affordability
            strain_cost = eff.get("strain_cost", 1)
            threshold = getattr(character, "strain_threshold", 12)
            if character.current_strain + strain_cost > threshold:
                continue

            return InterventionOffer(
                talent_ref=talent_ref,
                talent_name=defn["name"],
                effect=eff.get("effect", "reroll"),
                applicable_skills=applicable,
                strain_cost=strain_cost,
                scope=scope,
                narrative_prompt=eff.get("narrative_prompt", ""),
            )

    return None


def apply_intervention(character, offer: InterventionOffer) -> TalentActivation:
    """
    Apply an intervention: charge strain, mark talent as used.
    The caller handles the actual reroll.
    Returns a TalentActivation record for narration context.
    """
    character.current_strain += offer.strain_cost

    # Track usage
    if not hasattr(character, "talent_uses"):
        character.talent_uses = {}
    character.talent_uses[offer.talent_ref] = (
        character.talent_uses.get(offer.talent_ref, 0) + 1
    )

    return TalentActivation(
        talent_name=offer.talent_name,
        talent_type="intervention",
        effect_description=f"Intervention: {offer.effect}",
        strain_charged=offer.strain_cost,
        narrative_hint=offer.narrative_prompt,
    )


def reset_intervention_uses(character) -> None:
    """Reset session-scoped intervention uses at act boundary."""
    if hasattr(character, "talent_uses"):
        character.talent_uses = {}
