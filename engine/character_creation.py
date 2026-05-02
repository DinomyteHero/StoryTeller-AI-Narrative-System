"""Character Creation Redesign — runtime helpers (Phase 24).

Pure-Python helpers for the new character creation flow:

* `apply_background_to_character` — turn a Background spec + refinement
  picks into a live Character.
* `PrologueState` and friends — server-side state machine for the
  Identity Prologue arc.
* `infer_archetype_from_choices` — map prologue axis tags to a
  behavioral archetype string.
* `apply_archetype_skill_tilt` — fold archetype-driven adjustments
  into the character's skill tilt.
* `compute_crystallization_suggestion` — score the three
  (or four) profession paths and return the highest-weight one.
* `apply_crystallization_choice` — commit the player's profession
  choice onto the character.

This module has zero LLM dependencies and zero database imports.
The API layer wires it up to FastAPI and the SQLite session store.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Optional

from engine.character import (
    Character,
    Career,
    BeliefCommitment,
    Pronouns,
    Species,
    SKILL_CHARACTERISTICS,
    PRE_CRYSTALLIZATION_CAREERS,
)


# ── Defaults ─────────────────────────────────────────────────────────


DEFAULT_PRAXEUM_LOADOUT = {
    "weapons": [
        {
            "name": "Training lightsaber",
            "skill": "lightsaber",
            "damage_bonus": 6,
            "critical_rating": 2,
            "qualities": ["breach_1", "sunder"],
            "narrative_note": (
                "Built under Praxeum supervision from salvaged crystal. The "
                "blade hums low and steady. It feels like a tool the "
                "protagonist is still learning to hold."
            ),
        },
    ],
    "armor": {
        "name": "Praxeum training robes",
        "soak_bonus": 1,
        "defense": 0,
        "narrative_note": (
            "Simple, undyed fabric. Designed for movement, not protection."
        ),
    },
    "tools": [
        {
            "category": "knowledge",
            "name": "Jedi archive datapad",
            "mechanical_effect": (
                "Adds 1 boost die to Lore checks when consulting the archive."
            ),
            "narrative_note": (
                "Preloaded with Tionne's curated fragments of Jedi history. "
                "Borrowed, not owned."
            ),
        },
        {
            "category": "medical",
            "name": "Two stimpacks",
            "mechanical_effect": (
                "Heals 5 wounds per stimpack. Two uses before resupply."
            ),
            "narrative_note": "Alliance surplus, stored in a belt pouch.",
        },
    ],
    "special_items": [],
}


DEFAULT_PRAXEUM_FORCE_POWER = {
    "power_id": "sense",
    "name": "Sense",
    "category": "perception_knowledge",
    "base_pips_required": 1,
    "active_upgrades": [],
    "narrative_capability": (
        "The protagonist can read the immediate emotions and intentions "
        "of nearby beings. The discipline is new; the gift is older "
        "than the discipline."
    ),
    "gm_choice_guidance": (
        "Offer sensing choices when the protagonist could read fear, "
        "notice a lie, feel danger before it becomes visible, or "
        "distinguish genuine trust from practiced misdirection."
    ),
    "dark_side_flavor": "",
}


# Skill set defaults for a baseline Praxeum student. These tilt slightly
# toward the spiritual disciplines but stay generic.
PRAXEUM_BASELINE_SKILL_RANKS: dict[str, int] = {
    "discipline": 1,
    "perception": 1,
    "lore": 1,
    "lightsaber": 1,
}

PRAXEUM_BASELINE_CHARACTERISTICS: dict[str, int] = {
    "brawn": 2,
    "agility": 2,
    "intellect": 3,
    "cunning": 2,
    "willpower": 3,
    "presence": 2,
}


# ── Pronoun presets ──────────────────────────────────────────────────


PRONOUN_PRESETS: dict[str, dict[str, str]] = {
    "she_her": {"subject": "she", "object": "her", "possessive": "her"},
    "he_him": {"subject": "he", "object": "him", "possessive": "his"},
    "they_them": {"subject": "they", "object": "them", "possessive": "their"},
}

# Heroes-Rise-style menu, exposed by the API. The first six are
# preset; the seventh is a custom-vocabulary signal.
GENDER_MENU = [
    {"id": "female",        "label": "Female",                           "pronouns": "she_her"},
    {"id": "male",          "label": "Male",                             "pronouns": "he_him"},
    {"id": "afab_male",     "label": "Assigned female at birth, identify as male",  "pronouns": "he_him"},
    {"id": "amab_female",   "label": "Assigned male at birth, identify as female",  "pronouns": "she_her"},
    {"id": "intersex",      "label": "Born intersex",                    "pronouns": "they_them"},
    {"id": "non_binary",    "label": "Non-binary",                       "pronouns": "they_them"},
    {"id": "custom",        "label": "None of these — type my own vocabulary", "pronouns": ""},
]


# ── Refinement helpers ───────────────────────────────────────────────


@dataclass
class RefinementChoice:
    """All optional fields the player can fill on the refinement screen.

    Any field set to None is treated as 'use the background's default'.
    Fields set to '' are treated as explicit empty (the player skipped).
    """
    background_id:       str
    name:                Optional[str]   = None
    species_id:          Optional[str]   = None
    gender_id:           Optional[str]   = None
    custom_pronouns:     Optional[Pronouns] = None
    skill_tilt_override: Optional[dict[str, int]] = None
    appearance_flair:    Optional[str]   = None


def lookup_background(spine: dict, background_id: str) -> dict:
    """Return the background dict from the spine, or raise KeyError."""
    for bg in spine.get("backgrounds", []):
        if bg.get("background_id") == background_id:
            return bg
    raise KeyError(f"Unknown background_id: {background_id}")


def lookup_npc_seed(spine: dict, npc_name: str) -> Optional[dict]:
    """Find an NPC entry in the spine roster (case-insensitive)."""
    target = (npc_name or "").lower().strip()
    for npc in spine.get("npc_roster", []):
        if (npc.get("name") or "").lower().strip() == target:
            return npc
    return None


def resolve_pronouns(
    gender_id: Optional[str], custom: Optional[Pronouns]
) -> Optional[Pronouns]:
    """Convert a gender menu pick into a Pronouns object."""
    if custom is not None:
        return custom
    if not gender_id:
        return None
    for entry in GENDER_MENU:
        if entry["id"] == gender_id:
            preset_key = entry.get("pronouns") or ""
            preset = PRONOUN_PRESETS.get(preset_key)
            if preset:
                return Pronouns(**preset)
            return None
    return None


def coerce_species(species_id: Optional[str]) -> Optional[Species]:
    """Map a species string id onto the Species enum, tolerating misses."""
    if not species_id:
        return None
    key = species_id.strip().lower().replace(" ", "_").replace("'", "")
    for member in Species:
        if member.value == key:
            return member
    # Tolerate "twi_lek" / "twi'lek" / "twilek"
    for member in Species:
        if member.value.replace("_", "") == key.replace("_", ""):
            return member
    return None


def apply_skill_tilt(character: Character, tilt: dict[str, int]) -> None:
    """Apply a skill tilt dict to the character's skill ranks (clamped 0..5)."""
    if not tilt:
        return
    for skill, delta in tilt.items():
        if skill not in SKILL_CHARACTERISTICS and skill != "lightsaber":
            continue
        current = getattr(character.skills, skill, 0)
        new = max(0, min(5, int(current) + int(delta)))
        try:
            setattr(character.skills, skill, new)
        except Exception:
            # Pydantic v2 may need .__dict__ direct assignment under some configs
            character.skills.__dict__[skill] = new
    # Persist the tilt vector so future systems can read what came from
    # the background vs. what came from later play.
    merged = dict(character.skill_tilt)
    for k, v in tilt.items():
        merged[k] = merged.get(k, 0) + int(v)
    character.skill_tilt = merged


def build_baseline_character(spine: dict, refinement: RefinementChoice) -> Character:
    """Build a fresh Character from a Background spec + refinement picks.

    The result is a pre-crystallization Praxeum student with the
    background's tilt applied, the background-themed loadout, and one
    Force power (Sense) as a baseline. Name / species / gender may be
    None if the player skipped — the prologue will fill them.
    """
    bg = lookup_background(spine, refinement.background_id)

    # Pick a default name from the list if the player didn't supply one
    chosen_name = refinement.name
    if chosen_name is None and bg.get("default_names"):
        # Deterministic enough for a session — random.choice is fine here
        chosen_name = random.choice(bg["default_names"])

    # Species
    chosen_species = coerce_species(refinement.species_id)
    if chosen_species is None and bg.get("default_species"):
        chosen_species = coerce_species(bg["default_species"][0])

    # Pronouns
    chosen_pronouns = resolve_pronouns(
        refinement.gender_id, refinement.custom_pronouns
    )

    char = Character(
        name=chosen_name,
        species=chosen_species,
        career=Career.PRAXEUM_STUDENT,
        primary_game_line=__import__(
            "engine.character", fromlist=["GameLine"]
        ).GameLine.FORCE_AND_DESTINY,
        background=refinement.background_id,
        background_summary=bg.get("story_seed", ""),
        gender=refinement.gender_id,
        pronouns=chosen_pronouns,
        appearance_flair=refinement.appearance_flair or "",
        force_rating=1,
        wound_threshold=12,
        strain_threshold=12,
        soak=2,
    )

    # Apply baseline characteristics
    for k, v in PRAXEUM_BASELINE_CHARACTERISTICS.items():
        setattr(char.characteristics, k, v)

    # Apply baseline skills
    for k, v in PRAXEUM_BASELINE_SKILL_RANKS.items():
        try:
            setattr(char.skills, k, v)
        except Exception:
            char.skills.__dict__[k] = v

    # Apply background skill tilt (or override if the player edited it)
    tilt = refinement.skill_tilt_override or bg.get("default_skill_tilt", {})
    apply_skill_tilt(char, tilt)

    # Equip baseline gear
    from engine.equipment import Loadout, WeaponEntry, ArmorEntry, ToolEntry
    weapons = [WeaponEntry(**w) for w in DEFAULT_PRAXEUM_LOADOUT["weapons"]]
    armor   = ArmorEntry(**DEFAULT_PRAXEUM_LOADOUT["armor"])
    tools   = [ToolEntry(**t) for t in DEFAULT_PRAXEUM_LOADOUT["tools"]]
    char.loadout = Loadout(weapons=weapons, armor=armor, tools=tools)

    # Baseline Force power
    char.force_powers = [dict(DEFAULT_PRAXEUM_FORCE_POWER)]

    char.voice_notes = (
        "First-year Praxeum student, freshly arrived. The voice is still "
        "shaped by where they came from; the discipline is new and the "
        "habits are not."
    )

    return char


# ── Prologue runner ──────────────────────────────────────────────────


@dataclass
class PrologueChoiceRecord:
    scene_id: str
    chosen_index: int
    axis_tags: dict[str, str]


@dataclass
class PrologueState:
    """Persistent state for a running Identity Prologue.

    Stored as a dict inside the session's arc_state under the key
    `identity_prologue_state`. The schema is:

      {
        "stage": "prologue" | "complete",
        "next_scene_index": int,
        "history": [PrologueChoiceRecord, ...],
        "diegetic_slots_filled": [slot_type, ...],
        "diegetic_slots_pending": [slot_type, ...],
      }
    """
    stage: str = "prologue"
    next_scene_index: int = 0
    history: list[PrologueChoiceRecord] = field(default_factory=list)
    diegetic_slots_filled: list[str] = field(default_factory=list)
    diegetic_slots_pending: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "next_scene_index": self.next_scene_index,
            "history": [
                {
                    "scene_id": h.scene_id,
                    "chosen_index": h.chosen_index,
                    "axis_tags": h.axis_tags,
                }
                for h in self.history
            ],
            "diegetic_slots_filled": list(self.diegetic_slots_filled),
            "diegetic_slots_pending": list(self.diegetic_slots_pending),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PrologueState":
        return cls(
            stage=data.get("stage", "prologue"),
            next_scene_index=int(data.get("next_scene_index", 0)),
            history=[
                PrologueChoiceRecord(
                    scene_id=str(r.get("scene_id", "")),
                    chosen_index=int(r.get("chosen_index", 0)),
                    axis_tags=dict(r.get("axis_tags", {})),
                )
                for r in data.get("history", [])
            ],
            diegetic_slots_filled=list(data.get("diegetic_slots_filled", [])),
            diegetic_slots_pending=list(data.get("diegetic_slots_pending", [])),
        )


def initialize_prologue_state(spine: dict, character: Character) -> PrologueState:
    """Create a fresh prologue state for the given character + spine."""
    arc = spine.get("identity_prologue") or {}
    required_slots = list(arc.get("diegetic_slots_required", []))
    pending: list[str] = []
    if "name_pick" in required_slots and not character.name:
        pending.append("name_pick")
    if "gender_pick" in required_slots and character.pronouns is None:
        pending.append("gender_pick")
    if "appearance_flair" in required_slots and not character.appearance_flair:
        pending.append("appearance_flair")
    return PrologueState(
        stage="prologue",
        next_scene_index=0,
        history=[],
        diegetic_slots_filled=[],
        diegetic_slots_pending=pending,
    )


def render_prologue_scene(
    spine: dict,
    state: PrologueState,
    background_id: str,
) -> Optional[dict]:
    """Render the current prologue scene with the right background variant.

    Returns None when the prologue is already complete.
    """
    if state.stage != "prologue":
        return None
    arc = spine.get("identity_prologue") or {}
    library = arc.get("scene_library", [])
    if state.next_scene_index >= len(library):
        return None
    raw = library[state.next_scene_index]
    variant = (raw.get("background_variants", {}) or {}).get(background_id)
    if variant is None:
        # Fallback to the situation when no variant exists for this background
        variant = {
            "prose": raw.get("situation", ""),
            "npc_names": [],
            "choice_overrides": [],
        }

    # Decide whether to surface this scene's diegetic slot. Surface only
    # if the slot is in the pending list and matches.
    diegetic = raw.get("diegetic_slot")
    if diegetic and diegetic.get("slot_type") not in state.diegetic_slots_pending:
        diegetic = None

    return {
        "scene_id": raw.get("scene_id"),
        "scene_index": state.next_scene_index,
        "scene_count": len(library),
        "situation": raw.get("situation", ""),
        "prose": variant.get("prose", ""),
        "npc_names": variant.get("npc_names", []),
        "axis_tags": raw.get("axis_tags", []),
        "choices": [
            {
                "text": c.get("text", ""),
                "axis_tags": c.get("axis_tags", {}),
            }
            for c in raw.get("choices", [])
        ],
        "diegetic_slot": diegetic,
    }


def record_prologue_choice(
    spine: dict,
    state: PrologueState,
    chosen_index: int,
    diegetic_payload: Optional[dict] = None,
) -> dict:
    """Apply one prologue choice to the running state.

    `diegetic_payload` carries any field the diegetic slot was asking
    for: e.g. {"name": "Sora"} for name_pick, {"gender_id": "non_binary",
    "custom_pronouns": {...}} for gender_pick, or {"appearance_flair":
    "Loose hair, callused hands."} for appearance_flair.

    Returns a dict describing what was committed (for the API layer).
    """
    arc = spine.get("identity_prologue") or {}
    library = arc.get("scene_library", [])
    if state.next_scene_index >= len(library):
        return {"committed": False, "reason": "prologue_complete"}

    raw = library[state.next_scene_index]
    choices = raw.get("choices", [])
    if chosen_index < 0 or chosen_index >= len(choices):
        return {"committed": False, "reason": "invalid_choice_index"}
    chosen = choices[chosen_index]

    state.history.append(
        PrologueChoiceRecord(
            scene_id=raw.get("scene_id", ""),
            chosen_index=chosen_index,
            axis_tags=dict(chosen.get("axis_tags", {})),
        )
    )

    # Process diegetic slot if one was on this scene
    slot = raw.get("diegetic_slot")
    diegetic_committed: dict[str, Any] = {}
    if slot and diegetic_payload:
        slot_type = slot.get("slot_type")
        if slot_type in state.diegetic_slots_pending:
            state.diegetic_slots_pending.remove(slot_type)
            state.diegetic_slots_filled.append(slot_type)
            diegetic_committed = {"slot_type": slot_type, "payload": dict(diegetic_payload)}

    state.next_scene_index += 1
    if state.next_scene_index >= len(library):
        state.stage = "complete"

    return {
        "committed": True,
        "scene_id": raw.get("scene_id", ""),
        "chosen_index": chosen_index,
        "diegetic_committed": diegetic_committed,
        "stage": state.stage,
        "next_scene_index": state.next_scene_index,
    }


# ── Behavioral inference ─────────────────────────────────────────────


# Mapping of axis tag combinations to behavioral archetypes. The
# archetype is a short, descriptive string the narration model will
# use; it also determines the bonus skill tilt that gets folded into
# the character's tilt vector.
ARCHETYPE_DEFINITIONS: dict[str, dict] = {
    "the_steady_hand": {
        "description": "Direct, principled, willing to step between.",
        "axis_signature": {"approach": "direct", "moral": "principled"},
        "skill_tilt": {"discipline": 1, "leadership": 1},
        "starter_force_power_upgrade": "",
        "starter_talent_hint": "guardian.body_guard",
        "compatible_profession": "guardian",
    },
    "the_quiet_listener": {
        "description": "Patient, observant, slow to act but precise when acting.",
        "axis_signature": {"approach": "indirect", "moral": "compassionate"},
        "skill_tilt": {"perception": 1, "vigilance": 1},
        "starter_force_power_upgrade": "sense.range",
        "starter_talent_hint": "consular.kindly_silence",
        "compatible_profession": "consular",
    },
    "the_pattern_reader": {
        "description": "Reads the room, reads the seam, reads the person.",
        "axis_signature": {"approach": "indirect", "social": "guarded"},
        "skill_tilt": {"perception": 1, "skulduggery": 1},
        "starter_force_power_upgrade": "sense.strength",
        "starter_talent_hint": "sentinel.shadow_pattern",
        "compatible_profession": "sentinel",
    },
    "the_warm_diplomat": {
        "description": "Warm, open, wants to be known and wants to know.",
        "axis_signature": {"social": "open", "moral": "honest"},
        "skill_tilt": {"charm": 1, "negotiation": 1},
        "starter_force_power_upgrade": "",
        "starter_talent_hint": "consular.honest_voice",
        "compatible_profession": "consular",
    },
    "the_bold_actor": {
        "description": "Acts first, deliberates after, courageous to a fault.",
        "axis_signature": {"risk": "bold", "approach": "direct"},
        "skill_tilt": {"athletics": 1, "cool": 1},
        "starter_force_power_upgrade": "",
        "starter_talent_hint": "guardian.move_into_fire",
        "compatible_profession": "guardian",
    },
    "the_careful_witness": {
        "description": "Patient, cautious, weighs every move.",
        "axis_signature": {"risk": "cautious", "social": "guarded"},
        "skill_tilt": {"discipline": 1, "vigilance": 1},
        "starter_force_power_upgrade": "sense.control",
        "starter_talent_hint": "sentinel.measured_step",
        "compatible_profession": "sentinel",
    },
}


def _score_archetype(history: list[PrologueChoiceRecord], axis_signature: dict) -> int:
    score = 0
    for record in history:
        for axis, expected in axis_signature.items():
            if record.axis_tags.get(axis) == expected:
                score += 1
    return score


def infer_archetype_from_choices(history: list[PrologueChoiceRecord]) -> tuple[str, dict]:
    """Pick the highest-scoring archetype from the prologue choices.

    Returns (archetype_id, archetype_definition_dict). With an empty
    history all archetypes score 0; we explicitly fall back to
    `the_quiet_listener` (a generous, low-pressure default) so a player
    who didn't get to make any psychometric choices still has a
    coherent starting voice.
    """
    if not history:
        defn = ARCHETYPE_DEFINITIONS["the_quiet_listener"]
        return "the_quiet_listener", defn

    best_id = ""
    best_score = -1
    best_def: dict = {}
    for arch_id, defn in ARCHETYPE_DEFINITIONS.items():
        s = _score_archetype(history, defn.get("axis_signature", {}))
        if s > best_score:
            best_score = s
            best_id = arch_id
            best_def = defn
    if not best_id:
        best_id = "the_quiet_listener"
        best_def = ARCHETYPE_DEFINITIONS[best_id]
    return best_id, best_def


def derive_personality_locks(history: list[PrologueChoiceRecord]) -> list[BeliefCommitment]:
    """Pull a small set of belief commitments from the prologue history.

    Each lock pairs an axis to one of the player's characteristic
    answers and writes a short first-person commitment line. The
    surface text is intentionally generic so it works across
    backgrounds; campaign authors can override this in future passes.
    """
    locks: list[BeliefCommitment] = []
    seen_axes: set[str] = set()
    for record in history:
        for axis, value in record.axis_tags.items():
            if axis in seen_axes:
                continue
            seen_axes.add(axis)
            text = _belief_text(axis, value)
            if text:
                locks.append(
                    BeliefCommitment(
                        axis=axis,
                        commitment_text=text,
                        stat_effects={},
                    )
                )
    return locks


def _belief_text(axis: str, value: str) -> str:
    table = {
        ("approach", "direct"): "When the room is unsure, I name the thing first.",
        ("approach", "indirect"): "I trust patience more than I trust my first impulse.",
        ("social", "warm"): "Strangers are people I do not yet know — that is all.",
        ("social", "open"): "I would rather be seen badly than be invisible.",
        ("social", "guarded"): "I do not give my real face to a room I do not yet trust.",
        ("risk", "bold"): "If a hand has to move first, I would rather it be mine.",
        ("risk", "cautious"): "I would rather be late and right than fast and wrong.",
        ("moral", "honest"): "I will not buy peace with a lie about myself.",
        ("moral", "principled"): "Some things are not for sale at any price.",
        ("moral", "compassionate"): "The wound matters more than the rule that named it.",
        ("moral", "guarded"): "I keep the truth my people need; the rest can wait.",
        ("moral", "neutral"): "I will not pretend a verdict before I have the evidence.",
    }
    return table.get((axis, value), "")


def apply_archetype_skill_tilt(character: Character, archetype_def: dict) -> None:
    """Fold the archetype's skill_tilt into the character's tilt vector."""
    tilt = archetype_def.get("skill_tilt") or {}
    if not tilt:
        return
    apply_skill_tilt(character, tilt)


def grant_starter_force_power_upgrade(character: Character, archetype_def: dict) -> None:
    """Apply the archetype's recommended starter Force-power upgrade."""
    upgrade = archetype_def.get("starter_force_power_upgrade") or ""
    if not upgrade or "." not in upgrade:
        return
    power_id, upgrade_id = upgrade.split(".", 1)
    for power in character.force_powers:
        if power.get("power_id") == power_id:
            actives = power.setdefault("active_upgrades", [])
            if upgrade_id not in actives:
                actives.append(upgrade_id)
            return


def grant_starter_talent_hint(character: Character, archetype_def: dict) -> None:
    """Record the archetype's suggested starter talent.

    We only stash the hint as an advancement-log entry — the talent is
    not actually granted yet, because the talent tree is not opened
    until the crystallization beat. The hint surfaces in narration so
    the LLM can reference 'you find that ___ comes more naturally'.
    """
    hint = archetype_def.get("starter_talent_hint") or ""
    if not hint:
        return
    log_entry = {
        "kind": "archetype_talent_hint",
        "talent": hint,
        "note": (
            "Archetype-driven leaning detected during the prologue. "
            "Reference as emergent, not yet committed."
        ),
    }
    character.advancement_log.append(log_entry)


def finalize_prologue(
    spine: dict, character: Character, state: PrologueState
) -> dict:
    """Compute archetype + tilt + locks and apply them to the character.

    Returns a dict summarising what the prologue produced, suitable for
    feeding back to the frontend and storing in the session log.
    """
    archetype_id, archetype_def = infer_archetype_from_choices(state.history)
    character.behavioral_archetype = archetype_id

    # Fold archetype into tilt
    apply_archetype_skill_tilt(character, archetype_def)

    # Grant starter Force power upgrade
    grant_starter_force_power_upgrade(character, archetype_def)

    # Hint at a talent leaning (record only — not granted)
    grant_starter_talent_hint(character, archetype_def)

    # Personality locks
    locks = derive_personality_locks(state.history)
    character.personality_locks = locks

    return {
        "behavioral_archetype": archetype_id,
        "archetype_description": archetype_def.get("description", ""),
        "skill_tilt": dict(character.skill_tilt),
        "personality_locks": [
            {"axis": l.axis, "commitment_text": l.commitment_text}
            for l in locks
        ],
        "starter_force_power_upgrade": archetype_def.get(
            "starter_force_power_upgrade", ""
        ),
        "starter_talent_hint": archetype_def.get("starter_talent_hint", ""),
    }


# ── Crystallization helpers ──────────────────────────────────────────


@dataclass
class CrystallizationSuggestion:
    suggested_path_index: int
    weights: list[int]
    reasoning: list[str]


def _path_visible(path: dict, background_id: str) -> bool:
    bg_specific = path.get("background_specific_id") or ""
    if not bg_specific:
        return True
    return bg_specific == background_id


def _top_skills(character: Character, n: int = 3) -> list[str]:
    """Return the character's top-N skill names by current rank."""
    pairs: list[tuple[str, int]] = []
    skills = character.skills
    # Iterate over the SkillRanks model's class-level fields. Pydantic v2.11
    # deprecated instance-level access to `model_fields`, so use the class.
    for field_name in type(skills).model_fields:
        rank = int(getattr(skills, field_name, 0) or 0)
        if rank > 0:
            pairs.append((field_name, rank))
    pairs.sort(key=lambda p: (-p[1], p[0]))
    return [p[0] for p in pairs[:n]]


# Skill clusters that map to each profession path. Used to reward skill
# matches in the crystallization suggestion algorithm.
PROFESSION_SKILL_CLUSTERS: dict[str, set[str]] = {
    "guardian": {
        "discipline", "lightsaber", "athletics", "resilience",
        "leadership", "vigilance", "cool",
    },
    "consular": {
        "discipline", "negotiation", "charm", "lore", "medicine",
        "knowledge_lore",
    },
    "sentinel": {
        "perception", "skulduggery", "stealth", "computers",
        "streetwise", "deception", "vigilance",
    },
}


def compute_crystallization_suggestion(
    spine: dict, character: Character
) -> CrystallizationSuggestion:
    """Score each visible path and return the highest-weight one.

    Weights:
      background.strong_fit   → +bg_weight
      background.possible_fit → +1
      archetype.compatible    → +archetype_weight
      skill match (top-3)     → +skill_match_weight per match
    """
    cryst = spine.get("profession_crystallization") or {}
    paths = cryst.get("paths", [])
    algo = cryst.get("suggestion_algorithm", {}) or {}
    bg_weight = int(algo.get("background_weight", 2))
    arch_weight = int(algo.get("archetype_weight", 2))
    skill_weight = int(algo.get("skill_match_weight", 1))

    bg_id = character.background or ""
    bg_data: Optional[dict] = None
    for bg in spine.get("backgrounds", []):
        if bg.get("background_id") == bg_id:
            bg_data = bg
            break
    affinities = (bg_data or {}).get("profession_affinities") or {}
    strong_fit = affinities.get("strong_fit") or ""
    possible_fit = set(affinities.get("possible_fit") or [])

    archetype_id = character.behavioral_archetype or ""
    archetype_def = ARCHETYPE_DEFINITIONS.get(archetype_id, {})
    compatible_profession = archetype_def.get("compatible_profession", "")

    top_skills = set(_top_skills(character, n=3))

    weights: list[int] = []
    reasoning: list[str] = []
    for path in paths:
        w = 0
        notes: list[str] = []
        if not _path_visible(path, bg_id):
            weights.append(-1)  # masked
            reasoning.append("hidden_for_background")
            continue

        career_id = path.get("career_id", "")
        # Background fit
        if career_id == strong_fit:
            w += bg_weight
            notes.append(f"+{bg_weight} background strong fit")
        elif career_id in possible_fit:
            w += 1
            notes.append("+1 background possible fit")

        # Archetype fit
        if career_id == compatible_profession:
            w += arch_weight
            notes.append(f"+{arch_weight} archetype")

        # Skill fit
        cluster = PROFESSION_SKILL_CLUSTERS.get(career_id, set())
        match_count = len(top_skills & cluster)
        if match_count > 0:
            w += skill_weight * match_count
            notes.append(f"+{skill_weight * match_count} skill match")

        # Background-specific path: tiny bonus so it tends to surface
        # when allowed
        if path.get("background_specific_id"):
            w += 1
            notes.append("+1 background-specific path bonus")

        weights.append(w)
        reasoning.append(", ".join(notes) or "neutral")

    # Pick the highest-weight visible path; -1 entries skipped
    suggested = -1
    best = -1
    for i, w in enumerate(weights):
        if w >= 0 and w > best:
            best = w
            suggested = i

    return CrystallizationSuggestion(
        suggested_path_index=suggested,
        weights=weights,
        reasoning=reasoning,
    )


def _career_from_id(career_id: str) -> Career:
    target = (career_id or "").lower()
    for member in Career:
        if member.value == target:
            return member
    raise ValueError(f"Unknown career_id: {career_id}")


def apply_crystallization_choice(
    spine: dict,
    character: Character,
    chosen_path_index: int,
) -> dict:
    """Commit a profession choice onto the character.

    Sets `career`, opens the specialization tree, sets `crystallized=True`,
    and grants 1-2 baseline talents from the tree (recorded in
    advancement_log; the talents engine surfaces them on next reference).
    """
    cryst = spine.get("profession_crystallization") or {}
    paths = cryst.get("paths", [])
    if chosen_path_index < 0 or chosen_path_index >= len(paths):
        raise ValueError("Invalid crystallization path index")
    path = paths[chosen_path_index]
    career = _career_from_id(path.get("career_id", ""))
    talent_tree = path.get("talent_tree_id") or ""
    if not _path_visible(path, character.background or ""):
        raise ValueError("Path not available for this background")

    character.career = career
    if talent_tree:
        if talent_tree not in character.specializations:
            character.specializations.append(talent_tree)
    character.crystallized = True

    character.advancement_log.append({
        "kind": "profession_crystallization",
        "career": career.value,
        "talent_tree": talent_tree,
        "background": character.background or "",
        "note": (
            "Profession crystallized. Specialization tree opened. "
            "Two baseline talents available for unlock at the next "
            "milestone."
        ),
    })

    return {
        "career":            career.value,
        "talent_tree":       talent_tree,
        "specializations":   list(character.specializations),
        "crystallized":      character.crystallized,
        "display_name":      path.get("display_name", career.value.title()),
        "prose_flavor":      path.get("prose_flavor", ""),
    }


# ── Diegetic slot helpers ────────────────────────────────────────────


def apply_diegetic_payload(
    character: Character,
    slot_type: str,
    payload: dict,
) -> None:
    """Fold a diegetic-slot payload onto the character.

    Used when the prologue surfaces a name_pick / gender_pick /
    appearance_flair beat and the player fills it inline.
    """
    if slot_type == "name_pick":
        name = (payload or {}).get("name")
        if name and isinstance(name, str):
            character.name = name.strip()[:32] or character.name
    elif slot_type == "gender_pick":
        gender_id = (payload or {}).get("gender_id")
        if gender_id:
            character.gender = gender_id
        custom = (payload or {}).get("custom_pronouns")
        if isinstance(custom, dict) and custom:
            character.pronouns = Pronouns(
                subject=str(custom.get("subject", "they"))[:32] or "they",
                object=str(custom.get("object", "them"))[:32] or "them",
                possessive=str(custom.get("possessive", "their"))[:32] or "their",
            )
        else:
            preset = resolve_pronouns(gender_id, None)
            if preset is not None:
                character.pronouns = preset
    elif slot_type == "appearance_flair":
        flair = (payload or {}).get("appearance_flair")
        if isinstance(flair, str):
            character.appearance_flair = flair.strip()[:240]


# ── Talent earned-through-use mechanism (Mechanism 3) ────────────────


PATTERN_THRESHOLDS: dict[str, dict] = {
    # Pattern_id → {scene_count_threshold, talent_id, unlock_career,
    #               description}
    "consular_influence_uses": {
        "threshold": 4,
        "talent_id": "consular.hard_pressed_influence",
        "unlock_career": "consular",
        "description": (
            "Influence used in 4+ scenes — the discipline is finding "
            "purchase under pressure."
        ),
    },
    "guardian_protection_uses": {
        "threshold": 4,
        "talent_id": "guardian.body_guard_advanced",
        "unlock_career": "guardian",
        "description": (
            "Protection action taken in 4+ scenes — the body has "
            "learned the seam."
        ),
    },
    "sentinel_investigation_uses": {
        "threshold": 4,
        "talent_id": "sentinel.pattern_recognition_advanced",
        "unlock_career": "sentinel",
        "description": (
            "Investigation pattern used in 4+ scenes — the eye is "
            "trained."
        ),
    },
}


def increment_use_pattern(character: Character, pattern_id: str, delta: int = 1) -> None:
    """Bump the use-pattern counter on the character."""
    if not pattern_id:
        return
    counts = dict(character.use_pattern_counts)
    counts[pattern_id] = counts.get(pattern_id, 0) + int(delta)
    character.use_pattern_counts = counts


def check_pattern_unlocks(character: Character) -> list[dict]:
    """Return a list of newly-unlocked talent entries based on patterns.

    Each entry: {"pattern_id", "talent_id", "description"}.
    Only fires for talents the character does not already have.
    """
    unlocks: list[dict] = []
    if not character.crystallized:
        # Pattern-based unlocks gate on crystallization — pre-commit, the
        # leanings are recorded as hints (see `grant_starter_talent_hint`)
        # but no actual talents are granted.
        return unlocks
    have: set[str] = set()
    for t in character.acquired_talents:
        tid = t.get("talent_id") or t.get("id") or ""
        if tid:
            have.add(tid)
    for pattern_id, spec in PATTERN_THRESHOLDS.items():
        if spec.get("unlock_career") != character.career.value:
            continue
        count = int(character.use_pattern_counts.get(pattern_id, 0))
        if count < int(spec.get("threshold", 999)):
            continue
        talent_id = spec.get("talent_id", "")
        if talent_id in have:
            continue
        unlocks.append({
            "pattern_id":  pattern_id,
            "talent_id":   talent_id,
            "description": spec.get("description", ""),
        })
    return unlocks


def grant_pattern_unlock(character: Character, talent_id: str, description: str) -> None:
    """Add a pattern-based unlock to the character's acquired_talents."""
    character.acquired_talents.append({
        "talent_id":   talent_id,
        "source":      "pattern_use",
        "description": description,
    })
    character.advancement_log.append({
        "kind":        "pattern_use_unlock",
        "talent_id":   talent_id,
        "description": description,
    })
