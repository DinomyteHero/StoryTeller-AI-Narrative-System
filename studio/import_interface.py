"""
Cross-era character import interface.

Maps a completed character's state onto a new campaign spine. The Game
Engine exports an import package when a character completes a campaign;
this module processes that package against the receiving spine's
ImportInterface specification.

The Game Engine doesn't know the difference — it receives a character
data dict. Whether populated by import or defaults is invisible.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from studio.schema import CampaignSpine, ImportInterface


# ── Import Package ────────────────────────────────────────────────────


@dataclass
class ImportPackage:
    """Character state exported from a completed campaign.

    Mechanical state: Full character sheet.
    Narrative state: Relationships, voice notes, advancement log.
    """
    # ── Mechanical state ──
    name: str
    species: str
    career: str
    specializations: list[str]
    characteristics: dict[str, int]  # brawn, agility, etc.
    skills: dict[str, int]
    wound_threshold: int
    strain_threshold: int
    soak: int
    total_xp: int
    available_xp: int
    force_rating: int = 0
    force_sensitive: bool = False
    latent_force_sensitive: bool = False
    force_rejected_count: int = 0
    acquired_talents: list[dict] = field(default_factory=list)
    force_powers: list[dict] = field(default_factory=list)
    morality_value: Optional[int] = None
    conflict_history: list[int] = field(default_factory=list)
    obligation_type: Optional[str] = None
    obligation_value: Optional[int] = None
    duty_type: Optional[str] = None
    duty_value: Optional[int] = None

    # ── Narrative state ──
    advancement_log: list[dict] = field(default_factory=list)
    npc_relationship_summaries: dict[str, str] = field(default_factory=dict)
    world_state_variables: dict[str, bool] = field(default_factory=dict)
    throughline_question_history: list[str] = field(default_factory=list)
    voice_notes: str = ""

    # ── Loadout ──
    loadout: Optional[dict] = None

    @classmethod
    def from_dict(cls, data: dict) -> "ImportPackage":
        """Create an ImportPackage from a dict."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Import Result ─────────────────────────────────────────────────────


@dataclass
class ImportResult:
    """Result of applying an import interface to an import package."""
    character_data: dict
    applied_mappings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    xp_adjusted: int = 0


# ── Core Import Logic ─────────────────────────────────────────────────


def apply_import(
    package: ImportPackage,
    spine: CampaignSpine,
    variant_id: str,
) -> ImportResult:
    """Apply the spine's import interface to a character import package.

    Args:
        package: Character state from the completed campaign.
        spine: The receiving campaign spine.
        variant_id: Which character variant the player chose.

    Returns:
        ImportResult with the assembled character data dict.

    Raises:
        ValueError: If the spine has no import_interface or variant not found.
    """
    interface = spine.import_interface
    if interface is None:
        raise ValueError("Spine has no import_interface defined")

    # Find the target variant
    target_variant = None
    for allegiance in spine.allegiances:
        for variant in allegiance.character_variants:
            if variant.id == variant_id:
                target_variant = variant
                break

    if target_variant is None:
        raise ValueError(f"Variant '{variant_id}' not found in spine")

    result = ImportResult(character_data={})
    warnings: list[str] = []
    mappings: list[str] = []

    # ── Build base character data from the import package ──
    char = {
        "name": package.name,
        "species": package.species,
        "career": package.career,
        "specializations": list(package.specializations),
        "characteristics": dict(package.characteristics),
        "skills": dict(package.skills),
        "wound_threshold": package.wound_threshold,
        "strain_threshold": package.strain_threshold,
        "soak": package.soak,
        "total_xp": package.total_xp,
        "available_xp": package.available_xp,
        "force_rating": package.force_rating,
        "force_sensitive": package.force_sensitive,
        "latent_force_sensitive": package.latent_force_sensitive,
        "force_rejected_count": package.force_rejected_count,
        "acquired_talents": list(package.acquired_talents),
        "force_powers": list(package.force_powers),
        "advancement_log": list(package.advancement_log),
        "voice_notes": package.voice_notes,
        "throughline_question": spine.throughline_question,
    }

    # ── Apply specialization mappings ──
    char["specializations"] = _apply_specialization_mappings(
        package.specializations, interface, mappings, warnings
    )

    # ── Apply motivation track transition ──
    _apply_motivation_transition(char, package, interface, mappings, warnings)

    # ── Apply XP rebalancing ──
    xp_adjusted = _apply_xp_rebalancing(
        char, package.total_xp, interface, mappings, warnings
    )

    # ── Apply equipment transition ──
    _apply_equipment_transition(char, package, interface, target_variant, mappings)

    # ── Carry forward narrative state ──
    char["npc_relationship_summaries"] = dict(package.npc_relationship_summaries)
    char["world_state_variables"] = dict(package.world_state_variables)
    char["throughline_question_history"] = list(package.throughline_question_history)

    result.character_data = char
    result.applied_mappings = mappings
    result.warnings = warnings
    result.xp_adjusted = xp_adjusted

    return result


def build_default_character(
    spine: CampaignSpine,
    variant_id: str,
) -> dict:
    """Build a default character from a variant (no import).

    For players starting fresh. Produces a character indistinguishable
    from a new start — the Game Engine doesn't know the difference.

    Args:
        spine: The campaign spine.
        variant_id: Which character variant to build from.

    Returns:
        Character data dict ready for the Game Engine.
    """
    target_variant = None
    for allegiance in spine.allegiances:
        for variant in allegiance.character_variants:
            if variant.id == variant_id:
                target_variant = variant
                break

    if target_variant is None:
        raise ValueError(f"Variant '{variant_id}' not found in spine")

    char = {
        "name": "",  # Player sets this
        "species": target_variant.species,
        "career": target_variant.career,
        "primary_game_line": target_variant.primary_game_line,
        "specializations": list(target_variant.specializations),
        "characteristics": target_variant.characteristics_base.model_dump(),
        "skills": dict(target_variant.skills_base),
        "wound_threshold": target_variant.wound_threshold,
        "strain_threshold": target_variant.strain_threshold,
        "soak": target_variant.soak,
        "total_xp": target_variant.starting_xp,
        "available_xp": 0,
        "force_rating": 1 if target_variant.force_sensitive else 0,
        "force_sensitive": target_variant.force_sensitive,
        "acquired_talents": [],
        "force_powers": [],
        "advancement_log": [],
        "voice_notes": target_variant.voice_baseline,
        "throughline_question": spine.throughline_question,
        "motivation": {
            "track": target_variant.motivation_default.track,
        },
    }

    # Apply loadout
    if target_variant.starting_loadout:
        char["loadout"] = target_variant.starting_loadout.model_dump(mode="json")

    # Apply starting force powers
    if target_variant.starting_force_powers:
        char["force_powers"] = [
            fp.model_dump(mode="json") for fp in target_variant.starting_force_powers
        ]

    # Apply defaults from saga metadata if present
    if spine.saga_metadata and spine.saga_metadata.default_state_for_new_characters:
        defaults = spine.saga_metadata.default_state_for_new_characters
        for key, value in defaults.items():
            if key not in char:
                char[key] = value

    return char


# ── Internal helpers ──────────────────────────────────────────────────


def _apply_specialization_mappings(
    source_specs: list[str],
    interface: ImportInterface,
    mappings: list[str],
    warnings: list[str],
) -> list[str]:
    """Map prior specializations to the new campaign context."""
    result_specs = []
    mapping_lookup = {m.source_spec: m for m in interface.specialization_mappings}

    for spec in source_specs:
        mapping = mapping_lookup.get(spec)
        if mapping is None:
            # No explicit mapping — carry forward as continuity
            result_specs.append(spec)
            warnings.append(
                f"Specialization '{spec}' has no explicit mapping — "
                f"carried forward as continuity by default"
            )
            continue

        if mapping.mapping == "continuity":
            result_specs.append(spec)
            mappings.append(f"Specialization '{spec}': continuity (remains active)")

        elif mapping.mapping == "dormancy":
            # Dormant specs are retained but marked inactive
            result_specs.append(spec)
            mappings.append(
                f"Specialization '{spec}': dormancy (inactive, can be reactivated)"
            )

        elif mapping.mapping == "evolution":
            target = mapping.target_spec or spec
            result_specs.append(target)
            mappings.append(
                f"Specialization '{spec}' → '{target}': evolution "
                f"(preserving overlapping talent progress)"
            )

        else:
            warnings.append(
                f"Unknown mapping type '{mapping.mapping}' for spec '{spec}'"
            )
            result_specs.append(spec)

    return result_specs


def _apply_motivation_transition(
    char: dict,
    package: ImportPackage,
    interface: ImportInterface,
    mappings: list[str],
    warnings: list[str],
) -> None:
    """Apply motivation track transitions."""
    transition = interface.motivation_transition
    if not transition:
        # No transition — preserve existing track
        if package.obligation_type:
            char["motivation"] = {
                "track": "obligation",
                "type": package.obligation_type,
                "value": package.obligation_value or 0,
            }
        elif package.duty_type:
            char["motivation"] = {
                "track": "duty",
                "type": package.duty_type,
                "value": package.duty_value or 0,
            }
        elif package.morality_value is not None:
            char["motivation"] = {
                "track": "morality",
                "value": package.morality_value,
            }
        return

    new_track = transition.get("new_track")
    if new_track:
        char["motivation"] = {"track": new_track}

        # Carry forward values if same track
        if new_track == "obligation" and package.obligation_type:
            char["motivation"]["type"] = package.obligation_type
            char["motivation"]["value"] = package.obligation_value or 0
        elif new_track == "duty" and package.duty_type:
            char["motivation"]["type"] = package.duty_type
            char["motivation"]["value"] = package.duty_value or 0
        elif new_track == "morality" and package.morality_value is not None:
            char["motivation"]["value"] = package.morality_value

        mappings.append(f"Motivation track: transitioned to '{new_track}'")
    else:
        # Preserve existing
        if package.obligation_type:
            char["motivation"] = {
                "track": "obligation",
                "type": package.obligation_type,
                "value": package.obligation_value or 0,
            }
        mappings.append("Motivation track: preserved from prior campaign")


def _apply_xp_rebalancing(
    char: dict,
    total_xp: int,
    interface: ImportInterface,
    mappings: list[str],
    warnings: list[str],
) -> int:
    """Apply XP rebalancing per target_xp_range."""
    low, high = interface.target_xp_range
    adjusted = 0

    if total_xp < low:
        bonus = low - total_xp
        char["total_xp"] = low
        char["available_xp"] = char.get("available_xp", 0) + bonus
        adjusted = bonus
        mappings.append(
            f"XP rebalanced: +{bonus} bonus XP (from {total_xp} to {low} minimum)"
        )
    elif total_xp > high:
        # Spec says no XP is removed above maximum
        warnings.append(
            f"Character has {total_xp} XP, above target max {high}. "
            f"No XP removed per import rules."
        )
        mappings.append(f"XP: {total_xp} (above target max {high}, preserved)")
    else:
        mappings.append(f"XP: {total_xp} (within target range {low}-{high})")

    return adjusted


def _apply_equipment_transition(
    char: dict,
    package: ImportPackage,
    interface: ImportInterface,
    target_variant,
    mappings: list[str],
) -> None:
    """Apply equipment transition — replace gear with imported loadout."""
    if interface.imported_loadout:
        char["loadout"] = interface.imported_loadout.model_dump(mode="json")
        mappings.append("Equipment: replaced with spine's imported loadout")
    elif target_variant.starting_loadout:
        char["loadout"] = target_variant.starting_loadout.model_dump(mode="json")
        mappings.append("Equipment: using variant's starting loadout (no import loadout defined)")
    elif package.loadout:
        char["loadout"] = package.loadout
        mappings.append("Equipment: carried forward from prior campaign")
