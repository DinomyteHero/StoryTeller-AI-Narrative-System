"""
Hybrid character creator (Phase 3).

draft_character(): prose pitch -> LLM-drafted character stat block (FAST tier).
assemble_character(): a (possibly player-edited) draft dict -> a validated,
mechanically-coherent Character. The deterministic assembly step — NOT the LLM —
is the guarantee of mechanical validity: it clamps characteristics/skills,
recomputes derived stats (soak, wound/strain thresholds) from species + traits,
sets the starting XP budget, and validates every signature talent through
engine.talents.validate_talent_definition before admitting it to custom_talents.

Pure orchestration on top of gm.llm_client; no dice math, no DB.
"""

import logging
import re
from pathlib import Path
from typing import Optional

from engine.character import (
    Character, Characteristics, SkillRanks, NarrativeArc, MotivationTrack,
    SKILL_CHARACTERISTICS, GameLine,
    species_thresholds, species_start_xp,
)
from engine.equipment import Loadout, WeaponEntry, ArmorEntry, ToolEntry, SpecialItem
from engine.talents import validate_talent_definition
from gm.llm_client import call_chat_json, TIER_FAST

log = logging.getLogger(__name__)

_PROMPT = Path(__file__).parent / "prompts" / "character_draft.txt"


class CharacterDraftError(Exception):
    """Raised when a draft cannot be assembled into a valid character.

    .errors carries the human-readable reasons (surfaced to the editor UI).
    """

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


# Loose JSON-schema guidance for the draft. Strictness is intentionally NOT
# enforced at the schema layer (signature-talent effects are polymorphic);
# assemble_character() is the real validity gate.
CHARACTER_DRAFT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "species": {"type": "string"},
        "career": {"type": "string"},
        "specializations": {"type": "array", "items": {"type": "string"}},
        "archetype_concept": {"type": "string"},
        "background": {"type": "string"},
        "force_sensitive": {"type": "boolean"},
        "characteristics": {"type": "object"},
        "skills": {"type": "object"},
        "career_skills": {"type": "array", "items": {"type": "string"}},
        "signature_talents": {"type": "array", "items": {"type": "object"}},
        "narrative_arc": {"type": "object"},
        "voice_notes": {"type": "string"},
        "throughline_question": {"type": "string"},
        "starting_loadout": {"type": "object"},
    },
    "required": ["name", "species", "career", "characteristics", "skills"],
}


def draft_character(pitch: str, hints: Optional[dict] = None) -> dict:
    """Generate a character draft from a prose pitch via the FAST tier.

    Returns the raw draft dict (NOT yet a Character) so the player can edit it
    before saving. Raises RuntimeError (from gm.llm_client) on model failure.
    """
    if not pitch or not pitch.strip():
        raise CharacterDraftError(["pitch must not be empty"])

    hint_text = ""
    if hints:
        hint_text = "; ".join(f"{k}: {v}" for k, v in hints.items() if v)

    # Use targeted replace (not str.format) — the template is full of literal
    # JSON braces, and escaping them all is error-prone.
    prompt = (
        _PROMPT.read_text(encoding="utf-8")
        .replace("{pitch}", pitch.strip())
        .replace("{hints}", hint_text or "(none)")
    )
    draft = call_chat_json(
        tier=TIER_FAST,
        user=prompt,
        schema=CHARACTER_DRAFT_SCHEMA,
        schema_name="character_draft",
        temperature=0.4,
        max_tokens=2500,
        strict_schema=False,
        purpose="character_draft",
    )
    return draft


# ── Deterministic assembly ──────────────────────────────────────────

def _clamp(value, lo: int, hi: int, default: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")
    return slug or "character"


def assemble_character(draft: dict) -> Character:
    """Turn a draft dict into a validated, mechanically-coherent Character.

    Deterministic guarantees (the LLM's numbers are never trusted blindly):
    - characteristics clamped to 1..5, skills clamped to 0..5
    - soak = brawn; wound/strain thresholds = species base + brawn/willpower
    - starting XP budget from species table (LLM cannot invent XP)
    - career_skills filtered to real skill names
    - each signature talent validated; invalid ones -> CharacterDraftError(422)
    """
    if not isinstance(draft, dict):
        raise CharacterDraftError(["draft must be a JSON object"])

    errors: list[str] = []

    name = str(draft.get("name") or "").strip()
    if not name:
        errors.append("character needs a name")
    species = str(draft.get("species") or "human").strip().lower()
    career = str(draft.get("career") or "wanderer").strip().lower()
    archetype = str(draft.get("archetype_concept") or "").strip()

    # Specializations: lowercase slugs, capped at 2. When {career}_{spec}
    # matches a curated tree file, milestones offer that tree's branches;
    # freeform spec strings are legal and fall back to freeform choices.
    specializations: list[str] = []
    for spec in draft.get("specializations") or []:
        slug = _slugify(spec)
        if slug and slug not in specializations:
            specializations.append(slug)
        if len(specializations) >= 2:
            break

    # Characteristics: clamp 1..5 (starting hero ceiling).
    cdata = draft.get("characteristics") or {}
    characteristics = Characteristics(
        brawn=_clamp(cdata.get("brawn"), 1, 5, 2),
        agility=_clamp(cdata.get("agility"), 1, 5, 2),
        intellect=_clamp(cdata.get("intellect"), 1, 5, 2),
        cunning=_clamp(cdata.get("cunning"), 1, 5, 2),
        willpower=_clamp(cdata.get("willpower"), 1, 5, 2),
        presence=_clamp(cdata.get("presence"), 1, 5, 2),
    )

    # Skills: keep only real names, clamp ranks 0..5.
    sdata = draft.get("skills") or {}
    skill_kwargs: dict[str, int] = {}
    for skill, rank in sdata.items():
        if skill in SKILL_CHARACTERISTICS:
            skill_kwargs[skill] = _clamp(rank, 0, 5, 0)
        else:
            log.info("character_creator: dropping unknown skill %r", skill)
    skills = SkillRanks(**skill_kwargs)

    # Career skills: real names only, de-duplicated, order preserved.
    career_skills: list[str] = []
    for sk in draft.get("career_skills") or []:
        if sk in SKILL_CHARACTERISTICS and sk not in career_skills:
            career_skills.append(sk)

    # Derived stats — recomputed, never taken from the draft.
    wound_base, strain_base = species_thresholds(species)
    wound_threshold = wound_base + characteristics.brawn
    strain_threshold = strain_base + characteristics.willpower
    soak = characteristics.brawn

    start_xp = species_start_xp(species)

    force_sensitive = bool(draft.get("force_sensitive", False))
    force_rating = 1 if force_sensitive else 0
    game_line = (GameLine.FORCE_AND_DESTINY if force_sensitive
                 else GameLine.EDGE_OF_EMPIRE)

    # Narrative arc (optional but encouraged).
    arc = None
    adata = draft.get("narrative_arc") or {}
    if any(adata.get(k) for k in ("lie", "ghost", "truth", "want", "need")):
        arc_type = str(adata.get("arc_type") or "positive").strip().lower()
        if arc_type not in ("positive", "flat", "disillusionment", "fall", "corruption"):
            arc_type = "positive"
        arc = NarrativeArc(
            lie=str(adata.get("lie", "")),
            ghost=str(adata.get("ghost", "")),
            truth=str(adata.get("truth", "")),
            want=str(adata.get("want", "")),
            need=str(adata.get("need", "")),
            arc_type=arc_type,
        )

    # Signature talents -> validated custom_talents (the dice-safety gate).
    custom_talents: dict[str, dict] = {}
    for i, tdef in enumerate(draft.get("signature_talents") or []):
        if not isinstance(tdef, dict):
            errors.append(f"signature_talents[{i}] must be an object")
            continue
        ok, talent_errors = validate_talent_definition(tdef)
        if not ok:
            tname = tdef.get("name", f"#{i}")
            errors.extend(f"signature talent {tname!r}: {e}" for e in talent_errors)
            continue
        ref = _slugify(tdef.get("name", f"signature_{i}"))
        custom_talents[ref] = tdef

    loadout = _build_loadout(draft.get("starting_loadout") or {})

    if errors:
        raise CharacterDraftError(errors)

    character = Character(
        name=name,
        species=species,
        career=career,
        specializations=specializations,
        archetype_concept=archetype,
        primary_game_line=game_line,
        background=str(draft.get("background", "")),
        characteristics=characteristics,
        skills=skills,
        wound_threshold=wound_threshold,
        strain_threshold=strain_threshold,
        current_wounds=0,
        current_strain=0,
        soak=soak,
        total_xp=start_xp,
        available_xp=start_xp,
        motivation=MotivationTrack(),
        force_rating=force_rating,
        loadout=loadout,
        career_skills=career_skills,
        custom_talents=custom_talents,
        throughline_question=str(draft.get("throughline_question", "")),
        voice_notes=str(draft.get("voice_notes", "")),
        narrative_arc=arc,
    )
    # Final schema gate (raises ValidationError -> caller turns into 422).
    return Character.model_validate(character.model_dump())


def _build_loadout(data: dict) -> Loadout:
    weapons = []
    for w in data.get("weapons") or []:
        if not isinstance(w, dict):
            continue
        weapons.append(WeaponEntry(
            name=str(w.get("name", "Improvised weapon")),
            skill=w.get("skill") if w.get("skill") in SKILL_CHARACTERISTICS else "ranged_light",
            damage_bonus=_clamp(w.get("damage_bonus", 0), 0, 12, 0),
            critical_rating=_clamp(w.get("critical_rating", 3), 1, 6, 3),
            qualities=[str(q) for q in (w.get("qualities") or [])],
        ))
    armor = None
    adata = data.get("armor")
    if isinstance(adata, dict) and adata.get("name"):
        armor = ArmorEntry(
            name=str(adata["name"]),
            soak_bonus=_clamp(adata.get("soak_bonus", 0), 0, 4, 0),
            defense=_clamp(adata.get("defense", 0), 0, 4, 0),
        )
    tools = []
    for t in data.get("tools") or []:
        if isinstance(t, dict) and t.get("name"):
            tools.append(ToolEntry(
                category=str(t.get("category", "general")),
                name=str(t["name"]),
                mechanical_effect=str(t.get("description", t.get("mechanical_effect", ""))),
            ))
    special = []
    for s in data.get("special_items") or []:
        if isinstance(s, dict) and s.get("name"):
            special.append(SpecialItem(
                name=str(s["name"]),
                mechanical_effect=str(s.get("mechanical_effect", "")),
                narrative_note=str(s.get("narrative_note", "")),
            ))
        elif isinstance(s, str):
            special.append(SpecialItem(name=s))
    return Loadout(weapons=weapons, armor=armor, tools=tools, special_items=special)
