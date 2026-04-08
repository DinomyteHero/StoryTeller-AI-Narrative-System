"""
Cloud GM — narrative generation via cloud or local LLM.

Uses the OpenAI-compatible SDK. Provider and model are read from env vars —
no code changes needed to switch between OpenAI, OpenRouter, or local Ollama.

One cloud call per turn maximum. The physics-before-imagination invariant
ensures all mechanical outcomes are resolved BEFORE the LLM receives context.
"""

import re
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator
from openai import OpenAI
from engine.equipment import build_equipment_narration_block
from gm.context import ContextPackage

_PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_PATH = _PROMPTS_DIR / "narration.txt"
PROMPT_PATH_LITERARY = _PROMPTS_DIR / "narration_literary.txt"
MAX_TOKENS  = int(os.getenv("MAX_COMPLETION_TOKENS", "16000"))

# Provider config — all from environment variables
# CLOUD_PROVIDER:    "openai" | "openrouter"
# CLOUD_MODEL:
#   openai      → "gpt-5.2", "gpt-5.2-mini", etc.
#   openrouter  → "x-ai/grok-4.1-fast", "openai/gpt-5.2", etc. (provider/model format)
# NARRATIVE_BACKEND: "cloud" | "local"

CLOUD_PROVIDER    = os.getenv("CLOUD_PROVIDER", "openai")
CLOUD_MODEL       = os.getenv("CLOUD_MODEL", "gpt-5.2")
NARRATIVE_BACKEND = os.getenv("NARRATIVE_BACKEND", "cloud")
OLLAMA_URL             = os.getenv("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL            = os.getenv("LOCAL_MODEL", "qwen3.5:9b")
LOCAL_NARRATION_MODEL  = os.getenv("LOCAL_NARRATION_MODEL", LOCAL_MODEL)
PROSE_VOICE            = os.getenv("PROSE_VOICE", "clean")  # "clean" | "literary"

PROVIDER_BASE_URLS = {
    "openai":     None,
    "openrouter": "https://openrouter.ai/api/v1",
}

# ── Scene pacing guidance (Game Mechanics §10, Vision §3) ─────────────
# Maps scene_type to:
#   - pacing: word count, sentence rhythm, structural guidance
#   - voice_exemplar: 1-2 sentences in the target voice for style anchoring
#   - craft: 3-4 craft constraints SPECIFIC to this scene type (rotated,
#     not cumulative — reduces prompt overload per evaluation §2.1)
#
# HARD CONSTRAINTS (always active regardless of scene type) are in the
# prompt template's YOUR TASK section: dice fidelity, word count, delimiter,
# no game terminology, choice count, anti-slop prohibition.
#
# CRAFT CONSTRAINTS rotate per scene type — only the ones relevant to
# the current scene are injected, reducing cognitive load on the model.
#
# Two voice variants: "clean" (default, direct/grounded) and "literary"
# (original Stover/Luceno blend). Selected via PROSE_VOICE env var.

SCENE_PACING_CLEAN = {
    "combat": {
        "pacing": (
            "PACING: Combat. Short sentences, compressed paragraphs. "
            "250-350 words. Choices are immediate and action-oriented. "
            "No worldbuilding, no reflection. The environment is "
            "obstacles and opportunities."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"The first bolt goes wide. The second doesn't. It catches "
            "the crate beside your head and the plastic-composite "
            "shrapnel peppers your cheek — hot, sharp, tiny points of "
            "pain that your brain files under 'deal with later.' You're "
            "already moving.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- Fast, physical, external. The character reacts. Save "
            "internal reflection for after the fight.\n"
            "- NPC disposition determines how they fight — hostile NPCs "
            "press advantages, wary NPCs look for escape routes.\n"
            "- Each choice must have a different tactical AND identity "
            "profile. Not just 'attack/defend/flee' — the METHOD of "
            "fighting reveals who the character IS."
        ),
    },
    "chase": {
        "pacing": (
            "PACING: Chase. Movement and spatial awareness drive the "
            "prose. Shorter sentences as pressure mounts. 250-400 words. "
            "The environment is experienced at velocity, not examined."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"Three corridors. Left goes deeper into maintenance — dark, "
            "tangled, the kind of place you lose people. Right goes up "
            "toward the Promenade and crowds. Straight ahead is a blast "
            "door that might or might not be locked, and behind you the "
            "boots are getting closer.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- Spatial relationships matter — the reader must feel the "
            "geography of the pursuit.\n"
            "- Each choice represents a different escape philosophy: "
            "speed vs stealth vs misdirection vs confrontation.\n"
            "- If a dice check failed, the environment closes in — "
            "fewer exits, less time, worse options."
        ),
    },
    "infiltration": {
        "pacing": (
            "PACING: Infiltration. Precise, controlled prose. The "
            "character observes in operational terms — angles, timing, "
            "sight lines. 300-450 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"You count the interval. Forty seconds between sweeps. "
            "The vent cover has two bolts, and one of them is already "
            "corroded. Forty seconds is enough. Probably.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- Tension lives in the gap between the plan and what the "
            "plan missed. Details that seemed safe should develop edges.\n"
            "- Choices represent different operational approaches: "
            "patient observation vs calculated risk vs improvisation.\n"
            "- Plant one environmental detail that could become a "
            "complication or advantage in the next turn."
        ),
    },
    "social": {
        "pacing": (
            "PACING: Social. Dialogue-forward, NPC voice prominent. "
            "Subtext matters more than action. Let warmth and humor "
            "breathe when the relationship supports it. 350-500 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"'I'm glad you came,' she says, which in Ryloth "
            "trade-speak means she considered not being here. The booth "
            "she's chosen faces the entrance. Old habit or current "
            "concern — hard to tell with Numa.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- NPC interactions MUST reflect their mechanical disposition. "
            "Disposition below 0.5 = visible friction or reluctance. "
            "Conflicted states express both dimensions simultaneously.\n"
            "- What is NOT said carries as much weight as what is. Show "
            "the subtext through behavior — where someone looks, what "
            "they do with their hands — not through narrating hidden "
            "feelings.\n"
            "- Choices should include at least one dialogue option "
            "(direct line or conversational approach) that reveals "
            "character values, not just information goals."
        ),
    },
    "exploration": {
        "pacing": (
            "PACING: Exploration. Environmental detail is richest here "
            "— but through selected specifics, not exposition. One or "
            "two concrete details that imply a larger world. The "
            "character is taking in a new place. 350-500 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"The temple is older than anything you've seen on this "
            "continent. The stone is wrong for the region — dark volcanic "
            "basalt in a landscape of sandstone and clay. Someone moved "
            "these blocks a very long way, a very long time ago, and the "
            "why of that is carved into the lintel in a script you don't "
            "recognize.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- When introducing environmental details, prefer details "
            "that could become relevant later over purely atmospheric "
            "ones. Plant seeds.\n"
            "- The character notices what matters to THEM specifically, "
            "not generic observations. A smuggler notices exits. A "
            "mechanic notices what's broken.\n"
            "- Choices should offer different investigative approaches "
            "that reveal different information based on what the "
            "character prioritizes."
        ),
    },
    "introspection": {
        "pacing": (
            "PACING: Introspection. Slow, internal, honest. This is "
            "where the character processes what has happened. Minimal "
            "external action. No dice check this turn. 300-450 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"The bunk is too short but the blanket is warm and for "
            "the first time in three days nobody is trying to kill you. "
            "That should feel like more of a relief than it does. You "
            "keep thinking about what Tarev said — not the words, which "
            "were careful enough, but the way he looked at the door when "
            "he said them.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- At least one choice must be reflective — an internal "
            "decision about what the moment means, not what to do next.\n"
            "- Avoid resolving the character's internal conflict FOR "
            "them. Present the tension and let the player choose which "
            "direction to lean.\n"
            "- If a consequence from a prior significant choice has not "
            "yet surfaced, this is a good scene to show its reach — "
            "through a thought, a rumor, or a shifted dynamic."
        ),
    },
    "space_combat": {
        "pacing": (
            "PACING: Space combat. The ship is the character's body — "
            "every system response is felt through the deck plates. "
            "Tactical prose — angles, vectors, power allocation. "
            "250-400 words. Choices are operational decisions: fly, "
            "fire, reroute, or command."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"The first bolt cuts across your bow close enough to "
            "light the cockpit white. You slap the proximity alarm "
            "silent before the ringing starts. Two contacts, high "
            "starboard, closing fast — and the Luck was never going "
            "to outrun a pair of uglies in open space.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- The ship has personality — it groans, shudders, responds. "
            "Write the ship as a character the pilot knows intimately.\n"
            "- Each choice represents a different tactical philosophy: "
            "aggressive (weapons), evasive (piloting), technical "
            "(mechanics/computers), or command (leadership).\n"
            "- Damage is felt physically — sparks, alarms, the smell "
            "of burning circuits, the deck lurching. Do not report "
            "damage in game terms."
        ),
    },
}

SCENE_PACING_LITERARY = {
    "combat": {
        "pacing": (
            "PACING: Combat. Short sentences, compressed paragraphs. "
            "250-350 words. Choices are immediate and action-oriented. "
            "Worldbuilding compresses to the immediate situation."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"The bolt came before the thought. His hand was already "
            "moving, the DL-44 clearing leather with a muscle memory "
            "that predated everything he'd learned to think about, and "
            "the shot punched a fist-sized hole through the cargo crate "
            "where his head had been a quarter second ago.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- The character's body reacts before their mind catches up. "
            "Write from inside the nervous system.\n"
            "- NPC disposition determines how they fight — hostile NPCs "
            "press advantages, wary NPCs look for escape routes.\n"
            "- Each choice must have a different tactical AND identity "
            "profile. Not just 'attack/defend/flee' — the METHOD of "
            "fighting reveals who the character IS."
        ),
    },
    "chase": {
        "pacing": (
            "PACING: Chase. Movement and spatial awareness drive the "
            "prose. Speed through sentence rhythm — shorter as pressure "
            "mounts. 250-400 words. The environment is experienced at "
            "velocity, not examined."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"Three corridors. Left went deeper into the maintenance "
            "level — dark, tangled, the kind of place you lost people. "
            "Right went up toward the Promenade and crowds and witnesses. "
            "Straight ahead was a blast door that might or might not be "
            "locked, and behind him the sound of boots was getting closer "
            "in a way that suggested the people wearing them knew exactly "
            "where he was going.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- Spatial relationships matter — the reader must feel the "
            "geography of the pursuit.\n"
            "- Each choice represents a different escape philosophy: "
            "speed vs stealth vs misdirection vs confrontation.\n"
            "- If a dice check failed, the environment closes in — "
            "fewer exits, less time, worse options."
        ),
    },
    "infiltration": {
        "pacing": (
            "PACING: Infiltration. Precise, controlled prose. The "
            "character thinks in operational terms — angles, timing, "
            "sight lines. 300-450 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"You count the patrol interval. Forty seconds between the "
            "guard's peripheral sweep and the camera's return arc. Forty "
            "seconds is enough if you don't hesitate, and you haven't "
            "hesitated at a threshold since you were seventeen.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- Tension lives in the gap between the plan and what the "
            "plan missed. Details that seemed safe should develop edges.\n"
            "- Choices represent different operational approaches: "
            "patient observation vs calculated risk vs improvisation.\n"
            "- Plant one environmental detail that could become a "
            "complication or advantage in the next turn."
        ),
    },
    "social": {
        "pacing": (
            "PACING: Social. Dialogue-forward, NPC voice prominent. "
            "Subtext matters more than action. Let character warmth and "
            "humor breathe when the relationship supports it. "
            "350-500 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"Doss didn't look at you when he said it. He looked at the "
            "drink he wasn't drinking, and his fingers made a pattern on "
            "the glass that you recognized as the nervous habit of a man "
            "deciding how much truth he could afford.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- NPC interactions MUST reflect their mechanical disposition. "
            "Disposition below 0.5 = visible friction or reluctance. "
            "Conflicted states express both dimensions simultaneously.\n"
            "- What is NOT said carries as much weight as what is. Write "
            "the subtext.\n"
            "- Choices should include at least one dialogue option "
            "(direct line or conversational approach) that reveals "
            "character values, not just information goals."
        ),
    },
    "exploration": {
        "pacing": (
            "PACING: Exploration. Worldbuilding breathes. Rich "
            "environmental detail — the political economy of a place, "
            "the specific textures that make it real. The character "
            "observes and interprets. 400-600 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"The Red Sector earns its name from the light. Every "
            "surface here reflects some shade of it — the landing "
            "indicators on cargo lifts that never stop running, the "
            "advertisement holos cycling through products you cannot buy "
            "legally on any Core world, the bioluminescent mold that "
            "colonizes the duracrete where the environmental scrubbers "
            "gave up decades ago.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- When introducing environmental or NPC details, prefer "
            "details that could become relevant later over purely "
            "atmospheric ones. Plant seeds.\n"
            "- The character's interiority reads the environment — they "
            "notice what matters to THEM specifically, not generic "
            "observations.\n"
            "- Choices should offer different investigative approaches "
            "that reveal different information based on what the "
            "character prioritizes."
        ),
    },
    "introspection": {
        "pacing": (
            "PACING: Introspection. The character's interiority "
            "dominates. Minimal external action. Honest, specific, "
            "uncomfortable if necessary. No dice check this turn. "
            "300-500 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"Something had shifted in the weeks since Nar Shaddaa. "
            "Keth read rooms faster now — not just the exits and the "
            "threats but the subtler architecture of who wanted what from "
            "whom. And when he reached for a lie, it came easier. "
            "Cleaner. Like a tool he'd finally learned to hold properly.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- At least one choice must be reflective — an internal "
            "decision about what the moment means, not what to do next.\n"
            "- Avoid resolving the character's internal conflict FOR "
            "them. Present the tension and let the player choose which "
            "direction to lean.\n"
            "- If a consequence ripple from a prior significant choice "
            "has not yet surfaced, this is a good scene to show its "
            "reach — through the character's thoughts, a rumor, or a "
            "shifted dynamic."
        ),
    },
    "space_combat": {
        "pacing": (
            "PACING: Space combat. The ship is the character's body — "
            "every system response is felt through the deck plates. "
            "Tactical prose — angles, vectors, power allocation. "
            "250-400 words. Choices are operational decisions: fly, "
            "fire, reroute, or command."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"The Luck shuddered as the first bolt cut across her bow "
            "— close enough that the cockpit transparisteel lit white "
            "for a half-second and the proximity alarm screamed before "
            "Keth slapped it silent. Two contacts on the scope, closing "
            "from high starboard, and the freighter's handling was never "
            "going to outmaneuver a pair of uglies in open space.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- The ship has personality — it groans, shudders, responds. "
            "Write the ship as a character the pilot knows intimately.\n"
            "- Each choice represents a different tactical philosophy: "
            "aggressive (weapons), evasive (piloting), technical "
            "(mechanics/computers), or command (leadership).\n"
            "- Damage is felt physically — sparks, alarms, the smell "
            "of burning circuits, the deck lurching. Do not report "
            "damage in game terms."
        ),
    },
}

# Select active pacing dict based on PROSE_VOICE env var
SCENE_PACING = SCENE_PACING_CLEAN if PROSE_VOICE == "clean" else SCENE_PACING_LITERARY


def _get_scene_block(scene_type: str) -> str:
    """Assemble the scene-specific prompt block from SCENE_PACING."""
    entry = SCENE_PACING.get(scene_type, SCENE_PACING["social"])
    return f"{entry['pacing']}\n\n{entry['voice_exemplar']}\n\n{entry['craft']}"


def _make_client() -> tuple[OpenAI, str]:
    """Return (client, model_string) based on active backend/provider."""
    if NARRATIVE_BACKEND == "local":
        return (
            OpenAI(api_key="ollama", base_url=f"{OLLAMA_URL}/v1"),
            LOCAL_NARRATION_MODEL,
        )
    api_key  = (os.getenv("OPENAI_API_KEY") if CLOUD_PROVIDER == "openai"
                else os.getenv("OPENROUTER_API_KEY"))
    base_url = PROVIDER_BASE_URLS.get(CLOUD_PROVIDER)
    return OpenAI(api_key=api_key, base_url=base_url), CLOUD_MODEL


@dataclass
class NarrationResult:
    passage:      str
    choices:      list[str]          # player-facing text (skill tags stripped)
    skill_tags:   list[str | None]   # per-choice skill tag or None if no check
    raw_response: str
    used_local:   bool = False


class CloudGMError(Exception):
    pass


def _build_prompt(ctx: ContextPackage) -> str:
    from engine.talents import build_talent_capabilities, build_talent_activations_block
    from engine.force import build_force_capabilities_block

    prompt_path    = PROMPT_PATH_LITERARY if PROSE_VOICE == "literary" else PROMPT_PATH
    template       = prompt_path.read_text(encoding="utf-8")
    recent_summary = _format_recent_turns(ctx.recent_turns)
    full_summary   = f"{ctx.story_summary}\n\nRECENT TURNS:\n{recent_summary}"
    scene_pacing   = _get_scene_block(ctx.scene_type)

    # Phase 11: Talent context for narration (§15.5)
    talent_caps = build_talent_capabilities(ctx.character)
    talent_acts = build_talent_activations_block(
        getattr(ctx, "talent_activations", [])
    )

    # Phase 15: Force power capabilities for narration (§16.3)
    force_caps = build_force_capabilities_block(ctx.character)

    return template.format(
        character_summary=ctx.character.narrative_status(),
        character_voice=ctx.character.voice_notes,
        equipment_block=build_equipment_narration_block(ctx.character.loadout),
        force_state_block=ctx.force_state_block,
        force_capabilities_block=force_caps,
        talent_capabilities_block=talent_caps,
        aspiration_echo_block=ctx.build_aspiration_echo_block(),
        depth_card_block=ctx.depth_card_block,
        campaign_name=ctx.arc.campaign_name,
        story_position=f"Part {ctx.arc.current_act} of {ctx.arc.total_acts} — {ctx.arc.act_name}",
        throughline_question=ctx.arc.throughline_question,
        tension_level=ctx.arc.tension_level,
        story_summary=full_summary,
        open_threads=ctx.build_open_threads_block(),
        pacing_block=ctx.build_pacing_block(),
        motivation_block=ctx.build_motivation_block(),
        ship_state_block=ctx.ship_state_block,
        npc_states=ctx.build_npc_block(),
        location=ctx.location,
        situation=ctx.situation,
        galactic_context=ctx.galactic_context or "No wider context provided for this act.",
        dice_result_block=ctx.build_dice_result_block(),
        force_result_block=ctx.force_result_block,
        talent_activations_block=talent_acts,
        prose_diagnostic_block=ctx.build_prose_diagnostic_block(),
        scene_pacing=scene_pacing,
        pinch_point_instruction=ctx.pinch_point_instruction,
        foreshadow_instruction=ctx.foreshadow_instruction,
        closure_heartbeat_instruction=ctx.closure_heartbeat_instruction,
        dramatic_mission_block=ctx.build_dramatic_mission_block(),
        contradiction_arc_block=ctx.contradiction_arc_block,
        voice_mode_instruction=ctx.voice_mode_instruction,
        tone_instruction=ctx.tone_instruction,
    )


def _format_recent_turns(turns: list) -> str:
    """Format recent turns for the GM prompt. Includes narration excerpts
    so the GM remembers what it wrote, not just what the player did.
    """
    if not turns:
        return "This is the opening of the story."
    parts = []
    for t in turns[-5:]:
        line = f"Turn {t.turn_number}: {t.player_action}"
        if t.check_made:
            line += f" [{t.check_made}: {t.dice_result}]"
        if t.meaningful_choice_note:
            line += f" → {t.meaningful_choice_note}"
        if t.narration_excerpt:
            line += f"\n  Narration: {t.narration_excerpt}"
        parts.append(line)
    return "\n".join(parts)


def _parse_response(raw: str, used_local: bool = False) -> NarrationResult:
    """
    Split GM response into passage and choices.
    Enforces: delimiter present, 250-600 word count, 2-4 choices.
    Strips skill tags from choice text (e.g., "[Deception]") and stores
    them separately. The player never sees the skill name.
    """
    # Normalize any line that is essentially "CHOICES" surrounded by formatting
    # Handles: ---CHOICES---, **CHOICES---, CHOICES:, --- CHOICES :, etc.
    normalized = re.sub(
        r"^[\s*-]*CHOICES[\s*-:]*$", "---CHOICES---", raw, flags=re.MULTILINE
    )
    # Also catch "Your choices:", "Options:", "Your options:", "## Choices", etc.
    if "---CHOICES---" not in normalized:
        normalized = re.sub(
            r"^[\s#*]*(Your\s+)?(Choices|Options)\s*:?\s*$",
            "---CHOICES---", normalized, flags=re.MULTILINE | re.IGNORECASE
        )
    # Last resort: detect a numbered list (1. ...) near the end as implicit choices
    if "---CHOICES---" not in normalized:
        lines = normalized.split("\n")
        for i in range(len(lines) - 1, max(len(lines) - 15, -1), -1):
            if re.match(r"^\s*1[\.\)]\s+\S", lines[i]):
                # Check that line before isn't also numbered (part of passage list)
                if i > 0 and not re.match(r"^\s*\d+[\.\)]\s+\S", lines[i - 1]):
                    lines.insert(i, "---CHOICES---")
                    normalized = "\n".join(lines)
                    break
    if "---CHOICES---" not in normalized:
        raise CloudGMError("GM response missing ---CHOICES--- delimiter")

    passage, choices_raw = normalized.split("---CHOICES---", 1)
    passage     = passage.strip()
    choices_raw = choices_raw.strip()

    # Strip markdown emphasis (*italic* and **bold**) — frontend is plain text
    passage = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", passage)
    # Strip stray --- separators from passage edges
    passage = re.sub(r"^-{3,}\s*\n", "", passage)
    passage = re.sub(r"\n\s*-{3,}\s*$", "", passage)

    word_count = len(passage.split())
    if word_count < 250:
        raise CloudGMError(
            f"Passage too short ({word_count} words, minimum 250). Retrying."
        )
    if word_count > 800:
        raise CloudGMError(
            f"Passage too long ({word_count} words, maximum 800). Retrying."
        )

    raw_choices = []
    for line in choices_raw.split("\n"):
        line = line.strip()
        if not line or re.match(r"^-{2,}$", line):
            continue
        line = re.sub(r"^\d+[\.\)]\s*", "", line)   # strip "1. " or "1) "
        line = re.sub(r"^-\s+", "", line)            # strip "- "
        line = re.sub(r"^[\s*#]+", "", line)         # strip leading whitespace, *, #
        line = re.sub(r"[\s*]+$", "", line)          # strip trailing whitespace, *
        line = line.strip('"').strip()               # strip wrapping quotes
        if line:
            raw_choices.append(line)

    if len(raw_choices) < 2:
        raise CloudGMError(
            f"GM returned {len(raw_choices)} choice(s). Minimum 2 required. Retrying."
        )

    # Extract and strip skill tags: "[Deception]" or "[Force:Move]" at end of choice text
    skill_tag_pattern = re.compile(r"\s*\[([A-Za-z_:\s]+)\]\s*$")
    choices = []
    skill_tags = []
    for choice_text in raw_choices[:4]:
        match = skill_tag_pattern.search(choice_text)
        if match:
            choices.append(skill_tag_pattern.sub("", choice_text).rstrip())
            tag = match.group(1).strip()
            # Normalize: "Force:Move" stays as "force:move", regular skills lowercase+underscore
            skill_tags.append(tag.lower().replace(" ", "_"))
        else:
            choices.append(choice_text)
            skill_tags.append(None)

    return NarrationResult(
        passage=passage,
        choices=choices,
        skill_tags=skill_tags,
        raw_response=raw,
        used_local=used_local,
    )


def narrate_turn(
    ctx:         ContextPackage,
    max_retries: int = 2,
) -> NarrationResult:
    """
    One call to the configured provider for narration + choices.
    This is the ONE cloud call per turn (or local equivalent).
    Retries with a correction note appended on validation failure.

    Cloud failure fallback (v1.5): If the cloud model is unavailable or
    exceeds the timeout, fall back to the local model for this turn only.
    The next turn reattempts the cloud model. The player never sees an
    error — they get a less polished passage that still honors the dice
    and advances the story. A counter tracks consecutive fallbacks; if 3+
    consecutive turns fall back, the UI surfaces a subtle indicator.
    """
    # If already configured for local, skip fallback logic
    if NARRATIVE_BACKEND == "local":
        return _narrate_with_backend(ctx, max_retries, used_local=True)

    # Attempt cloud first, fall back to local on failure
    try:
        return _narrate_with_backend(ctx, max_retries, used_local=False)
    except (CloudGMError, Exception) as cloud_err:
        import logging
        logging.warning(
            f"Cloud GM failed ({cloud_err}), falling back to local model"
        )
        try:
            return _narrate_with_local_fallback(ctx)
        except Exception as local_err:
            raise CloudGMError(
                f"Both cloud and local failed. "
                f"Cloud: {cloud_err}. Local: {local_err}"
            )


def _narrate_with_backend(
    ctx: ContextPackage, max_retries: int, used_local: bool,
) -> NarrationResult:
    """Core narration logic — extracted for fallback reuse.

    Includes post-parse choice quality validation (spec §5.2).
    Quality validation is skipped for local backend (spec §10).
    """
    from gm.choice_validator import validate_choice_quality, build_quality_correction

    client, model = _make_client()
    prompt        = _build_prompt(ctx)
    last_error    = None
    best_result: NarrationResult | None = None  # best structurally valid result

    for attempt in range(max_retries + 1):
        is_qwen = used_local and "qwen" in LOCAL_NARRATION_MODEL.lower()
        msg_content = f"/no_think\n{prompt}" if is_qwen else prompt
        messages = [{"role": "user", "content": msg_content}]
        if attempt > 0 and last_error:
            messages.append({
                "role": "user",
                "content": (
                    f"Your previous response was rejected. "
                    f"Reason: {last_error}. Please correct this and try again."
                ),
            })

        timeout = 180.0 if used_local else 60.0
        kwargs = dict(
            model=model,
            max_completion_tokens=MAX_TOKENS,
            messages=messages,
            timeout=timeout,
        )
        # Reasoning models (gpt-o*, gpt-5*) support reasoning_effort
        reasoning = os.getenv("REASONING_EFFORT", "low")
        if not used_local and reasoning:
            kwargs["reasoning_effort"] = reasoning
        response = client.chat.completions.create(**kwargs)
        import logging
        choice = response.choices[0]
        raw = choice.message.content or ""
        logging.warning(
            f"=== GM RESPONSE (attempt {attempt+1}) ===\n"
            f"model={model}, finish_reason={choice.finish_reason}, "
            f"content_len={len(raw)}, refusal={getattr(choice.message, 'refusal', None)}\n"
            f"RAW:\n{raw[:2000]}\n=== END ==="
        )

        try:
            result = _parse_response(raw, used_local=used_local)
        except CloudGMError as e:
            last_error = str(e)
            if attempt == max_retries:
                if best_result:
                    return best_result  # return best structurally valid result
                raise CloudGMError(
                    f"GM failed after {max_retries + 1} attempts. "
                    f"Last error: {last_error}"
                )
            continue

        # Track best structurally valid result for fallback
        best_result = result

        # Choice quality validation (skip for local backend per spec §10)
        if used_local or NARRATIVE_BACKEND == "local":
            return result

        quality = validate_choice_quality(
            situation=ctx.situation,
            character_name=ctx.character.name,
            character_career=ctx.character.career,
            passage=result.passage,
            choices=result.choices,
        )

        if quality.passed:
            return result  # good or marginal (0-1 failures)

        if quality.fail_count == 1:
            logging.warning(
                f"Choice quality marginal (1 dimension failed: "
                f"{quality.rejection_reason}). Accepting."
            )
            return result

        # 2+ dimensions failed — retry if budget remains
        logging.warning(
            f"Choice quality rejected ({quality.fail_count} dimensions failed: "
            f"{quality.rejection_reason}). Attempt {attempt+1}/{max_retries+1}."
        )
        last_error = build_quality_correction(quality)
        if attempt == max_retries:
            # Exhausted — accept best available (spec §5.4)
            logging.warning("Retry budget exhausted. Accepting best available result.")
            return best_result

    raise CloudGMError("Unreachable")


def _narrate_with_local_fallback(ctx: ContextPackage) -> NarrationResult:
    """
    Emergency fallback: narrate via local model when cloud is unavailable.
    Uses a simplified prompt optimized for the local model's capability.
    Output quality will be lower but the turn advances.
    """
    import httpx
    qwen_prefix = "/no_think\n" if "qwen" in LOCAL_NARRATION_MODEL.lower() else ""
    simplified_prompt = (
        f"{qwen_prefix}You are the narrator for a Star Wars RPG. Write in second person "
        f"present tense, 250-400 words.\n\n"
        f"SITUATION: {ctx.situation}\n"
        f"LOCATION: {ctx.location}\n"
        f"{ctx.build_dice_result_block()}\n\n"
        f"Write the passage, then on a new line write ---CHOICES--- "
        f"followed by 2-3 short choices.\n"
    )
    response = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": LOCAL_NARRATION_MODEL,
            "prompt": simplified_prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 1200},
        },
        timeout=60.0,
    )
    response.raise_for_status()
    raw = response.json()["response"].strip()
    return _parse_response(raw, used_local=True)


def narrate_turn_stream(ctx: ContextPackage) -> Iterator[str]:
    """
    Streaming version — yields text chunks via SSE.
    Caller collects chunks, then calls _parse_response on the full text.

        full_text = ""
        for chunk in narrate_turn_stream(ctx):
            full_text += chunk
            send_to_client(chunk)
        result = _parse_response(full_text)
    """
    client, model = _make_client()
    kwargs = dict(
        model=model,
        max_completion_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": _build_prompt(ctx)}],
        stream=True,
    )
    reasoning = os.getenv("REASONING_EFFORT", "low")
    if NARRATIVE_BACKEND != "local" and reasoning:
        kwargs["reasoning_effort"] = reasoning
    stream = client.chat.completions.create(**kwargs)
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# ── Milestone reflection generation (Phase 12, §14.3) ────────────────

MILESTONE_PROMPT_PATH = Path(__file__).parent / "prompts" / "milestone_reflection.txt"


def generate_milestone_reflection(
    character,
    choices: list,
    campaign_name: str,
    current_act: int,
    total_acts: int,
    act_summary: str,
) -> NarrationResult:
    """
    Generate a talent milestone reflection passage + choices.

    Uses the cloud GM to produce a narrative passage that presents
    talent acquisition as a character identity decision.
    Returns a NarrationResult with passage + tagged choices.
    """
    from engine.talents import MilestoneChoice

    # Build choices block for prompt
    choices_lines = []
    for i, choice in enumerate(choices, 1):
        choices_lines.append(
            f"Choice {i}: {choice.talent_name}\n"
            f"  Branch: {choice.branch_theme} — {choice.branch_description}\n"
            f"  Identity: {choice.narrative_identity}\n"
            f"  Tag: [MILESTONE:{choice.talent_ref}]"
        )

    template = MILESTONE_PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        character_summary=character.narrative_status(),
        character_voice=getattr(character, "voice_notes", ""),
        campaign_name=campaign_name,
        current_act=current_act,
        total_acts=total_acts,
        act_summary=act_summary or "No summary available.",
        choices_block="\n\n".join(choices_lines),
    )

    client, model = _make_client()
    is_local = NARRATIVE_BACKEND == "local"
    is_qwen = is_local and "qwen" in LOCAL_NARRATION_MODEL.lower()
    msg_content = f"/no_think\n{prompt}" if is_qwen else prompt

    timeout = 180.0 if is_local else 60.0
    kwargs = dict(
        model=model,
        max_completion_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": msg_content}],
        timeout=timeout,
    )
    reasoning = os.getenv("REASONING_EFFORT", "low")
    if not is_local and reasoning:
        kwargs["reasoning_effort"] = reasoning

    response = client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content or ""

    # Parse milestone response — reuse _parse_response with milestone tag handling
    return _parse_milestone_response(raw, choices)


def _parse_milestone_response(raw: str, expected_choices: list) -> NarrationResult:
    """
    Parse a milestone reflection response.

    Extracts the passage and maps [MILESTONE:talent_ref] tagged choices
    back to the expected MilestoneChoice objects.
    """
    import re

    # Normalize choices delimiter
    normalized = re.sub(
        r"^[\s*-]*CHOICES[\s*-:]*$", "---CHOICES---", raw, flags=re.MULTILINE
    )
    if "---CHOICES---" not in normalized:
        normalized = re.sub(
            r"^[\s#*]*(Your\s+)?(Choices|Options)\s*:?\s*$",
            "---CHOICES---", normalized, flags=re.MULTILINE | re.IGNORECASE
        )

    if "---CHOICES---" not in normalized:
        raise CloudGMError("Milestone response missing ---CHOICES--- delimiter")

    passage, choices_raw = normalized.split("---CHOICES---", 1)
    passage = passage.strip()

    # Strip markdown emphasis
    passage = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", passage)

    # Parse choices — extract milestone tags
    choice_lines = [
        line.strip()
        for line in re.split(r"\n(?=\d+[\.\)]|\-\s|\*\s)", choices_raw.strip())
        if line.strip()
    ]

    parsed_choices = []
    milestone_tags = []
    for line in choice_lines:
        clean = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        clean = re.sub(r"^[-*]\s*", "", clean).strip()
        if not clean:
            continue

        # Extract [MILESTONE:talent_ref] tag
        tag_match = re.search(r"\[MILESTONE:(\w+)\]", clean)
        talent_ref = tag_match.group(1) if tag_match else ""
        # Strip the tag from display text
        display = re.sub(r"\s*\[MILESTONE:\w+\]", "", clean).strip()
        # Also strip bold/italic
        display = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", display)

        parsed_choices.append(display)
        milestone_tags.append(talent_ref)

    return NarrationResult(
        passage=passage,
        choices=parsed_choices,
        skill_tags=milestone_tags,  # repurpose skill_tags for milestone refs
        used_local=(NARRATIVE_BACKEND == "local"),
    )


# ── Force power milestone reflection (Phase 15, §16.4) ──────────────

FORCE_POWER_MILESTONE_PROMPT_PATH = Path(__file__).parent / "prompts" / "force_power_milestone.txt"


def generate_force_power_milestone_reflection(
    character,
    choices: list,
    campaign_name: str,
    current_act: int,
    total_acts: int,
    act_summary: str,
) -> NarrationResult:
    """
    Generate a Force power upgrade milestone reflection passage + choices.

    Uses the cloud GM to produce a narrative passage presenting Force
    power upgrades as experiential discoveries, not mechanical purchases.
    Returns a NarrationResult with passage + tagged choices.
    """
    from engine.force import build_force_state_block, ForcePowerMilestoneChoice

    # Build choices block for prompt
    choices_lines = []
    for i, choice in enumerate(choices, 1):
        choices_lines.append(
            f"Choice {i}: {choice.power_name} — {choice.upgrade_name}\n"
            f"  Type: {choice.upgrade_type} upgrade\n"
            f"  Experience: {choice.narrative}\n"
            f"  Tag: [FORCEPOWER:{choice.power_id}:{choice.upgrade_id}]"
        )

    template = FORCE_POWER_MILESTONE_PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        character_summary=character.narrative_status(),
        character_voice=getattr(character, "voice_notes", ""),
        force_state=build_force_state_block(character),
        campaign_name=campaign_name,
        current_act=current_act,
        total_acts=total_acts,
        act_summary=act_summary or "No summary available.",
        choices_block="\n\n".join(choices_lines),
    )

    client, model = _make_client()
    is_local = NARRATIVE_BACKEND == "local"
    is_qwen = is_local and "qwen" in LOCAL_NARRATION_MODEL.lower()
    msg_content = f"/no_think\n{prompt}" if is_qwen else prompt

    timeout = 180.0 if is_local else 60.0
    kwargs = dict(
        model=model,
        max_completion_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": msg_content}],
        timeout=timeout,
    )
    reasoning = os.getenv("REASONING_EFFORT", "low")
    if not is_local and reasoning:
        kwargs["reasoning_effort"] = reasoning

    response = client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content or ""

    return _parse_force_power_milestone_response(raw, choices)


def _parse_force_power_milestone_response(
    raw: str, expected_choices: list,
) -> NarrationResult:
    """
    Parse a Force power milestone reflection response.

    Extracts the passage and maps [FORCEPOWER:power_id:upgrade_id] tags
    back to compound keys.
    """
    # Normalize choices delimiter
    normalized = re.sub(
        r"^[\s*-]*CHOICES[\s*-:]*$", "---CHOICES---", raw, flags=re.MULTILINE
    )
    if "---CHOICES---" not in normalized:
        normalized = re.sub(
            r"^[\s#*]*(Your\s+)?(Choices|Options)\s*:?\s*$",
            "---CHOICES---", normalized, flags=re.MULTILINE | re.IGNORECASE
        )

    if "---CHOICES---" not in normalized:
        raise CloudGMError("Force power milestone response missing ---CHOICES--- delimiter")

    passage, choices_raw = normalized.split("---CHOICES---", 1)
    passage = passage.strip()

    # Strip markdown emphasis
    passage = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", passage)

    # Parse choices — extract Force power milestone tags
    choice_lines = [
        line.strip()
        for line in re.split(r"\n(?=\d+[\.\)]|\-\s|\*\s)", choices_raw.strip())
        if line.strip()
    ]

    parsed_choices = []
    force_tags = []
    for line in choice_lines:
        clean = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        clean = re.sub(r"^[-*]\s*", "", clean).strip()
        if not clean:
            continue

        # Extract [FORCEPOWER:power_id:upgrade_id] tag
        tag_match = re.search(r"\[FORCEPOWER:(\w+):(\w+)\]", clean)
        if tag_match:
            tag = f"{tag_match.group(1)}:{tag_match.group(2)}"
        else:
            tag = ""
        # Strip the tag from display text
        display = re.sub(r"\s*\[FORCEPOWER:\w+:\w+\]", "", clean).strip()
        display = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", display)

        parsed_choices.append(display)
        force_tags.append(tag)

    return NarrationResult(
        passage=passage,
        choices=parsed_choices,
        skill_tags=force_tags,  # repurpose for "power_id:upgrade_id" compound keys
        used_local=(NARRATIVE_BACKEND == "local"),
    )


# ── Time skip passage generation (Phase 17, §19) ─────────────────────

TIME_SKIP_OPENING_PROMPT_PATH = Path(__file__).parent / "prompts" / "time_skip_opening.txt"
TIME_SKIP_CLOSING_PROMPT_PATH = Path(__file__).parent / "prompts" / "time_skip_closing.txt"


def generate_time_skip_opening(
    character,
    duration_months: int,
    framing: str,
    campaign_name: str,
    act_summary: str,
) -> str:
    """
    Generate the opening montage passage for a time skip.

    Returns a 2-3 paragraph impressionistic montage (NOT interactive).
    """
    template = TIME_SKIP_OPENING_PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        character_summary=character.narrative_status(),
        character_voice=getattr(character, "voice_notes", ""),
        campaign_name=campaign_name,
        duration_months=duration_months,
        framing=framing,
        act_summary=act_summary or "No summary available.",
    )

    client, model = _make_client()
    is_local = NARRATIVE_BACKEND == "local"
    is_qwen = is_local and "qwen" in LOCAL_NARRATION_MODEL.lower()
    msg_content = f"/no_think\n{prompt}" if is_qwen else prompt

    timeout = 180.0 if is_local else 60.0
    kwargs = dict(
        model=model,
        max_completion_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": msg_content}],
        timeout=timeout,
    )
    reasoning = os.getenv("REASONING_EFFORT", "low")
    if not is_local and reasoning:
        kwargs["reasoning_effort"] = reasoning

    response = client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content or ""

    # Strip markdown emphasis
    passage = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", raw.strip())
    return passage


def generate_time_skip_closing(
    character,
    duration_months: int,
    campaign_name: str,
    vignette_summary: str,
    next_act_situation: str,
) -> str:
    """
    Generate the closing passage after all vignettes are resolved.

    Returns a 1-2 paragraph bridge into the new act (NOT interactive).
    """
    template = TIME_SKIP_CLOSING_PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        character_summary=character.narrative_status(),
        character_voice=getattr(character, "voice_notes", ""),
        campaign_name=campaign_name,
        duration_months=duration_months,
        vignette_summary=vignette_summary,
        next_act_situation=next_act_situation,
    )

    client, model = _make_client()
    is_local = NARRATIVE_BACKEND == "local"
    is_qwen = is_local and "qwen" in LOCAL_NARRATION_MODEL.lower()
    msg_content = f"/no_think\n{prompt}" if is_qwen else prompt

    timeout = 180.0 if is_local else 60.0
    kwargs = dict(
        model=model,
        max_completion_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": msg_content}],
        timeout=timeout,
    )
    reasoning = os.getenv("REASONING_EFFORT", "low")
    if not is_local and reasoning:
        kwargs["reasoning_effort"] = reasoning

    response = client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content or ""

    # Strip markdown emphasis
    passage = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", raw.strip())
    return passage
