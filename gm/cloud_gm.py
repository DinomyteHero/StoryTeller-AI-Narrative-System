"""
Cloud GM — narrative generation via cloud or local LLM.

Uses the OpenAI-compatible SDK. Provider and model are read from env vars —
no code changes needed to switch between OpenAI, OpenRouter, or local Ollama.

One cloud call per turn maximum. The physics-before-imagination invariant
ensures all mechanical outcomes are resolved BEFORE the LLM receives context.
"""

import re
import json
import os
import logging
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Iterator, Optional
from openai import OpenAI
from engine.equipment import build_equipment_narration_block
from gm.context import ContextPackage
from gm.llm_client import (
    make_client as _make_unified_client,
    resolve_model,
    _prepare_kwargs,
    log_llm_usage,
    TIER_QUALITY,
)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_PATH = _PROMPTS_DIR / "narration.txt"
PROMPT_PATH_SYSTEM = _PROMPTS_DIR / "narration_system.txt"
PROMPT_PATH_LITERARY = _PROMPTS_DIR / "narration_literary.txt"
MAX_TOKENS  = int(os.getenv("MAX_COMPLETION_TOKENS", "16000"))
NARRATION_MAX_TOKENS = int(os.getenv("NARRATION_MAX_TOKENS", "1200"))
NARRATION_MIN_WORDS = int(os.getenv("NARRATION_MIN_WORDS", "150"))
NARRATION_MAX_WORDS = int(os.getenv("NARRATION_MAX_WORDS", "750"))
NARRATION_TIMEOUT_SEC = float(os.getenv("NARRATION_TIMEOUT_SEC", "45"))
NARRATION_PARSE_RETRIES = int(os.getenv("NARRATION_PARSE_RETRIES", "1"))
NARRATION_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv("NARRATION_FALLBACK_MODELS", "").split(",")
    if model.strip()
]
CHOICE_QUALITY_INLINE = os.getenv("CHOICE_QUALITY_INLINE", "true").lower() == "true"
# Rule 4 enforcement — on failed checks, a fast-tier post-check verifies the
# prose actually depicts failure. Mismatch triggers a narration retry.
DICE_POLARITY_CHECK = os.getenv("DICE_POLARITY_CHECK", "true").lower() == "true"
LLM_TIMING_LOG = os.getenv("LLM_TIMING_LOG", "true").lower() == "true"

# Provider config. The unified client (gm/llm_client.py) is the authoritative
# source for model/provider routing.
PROSE_VOICE = os.getenv("PROSE_VOICE", "clean")  # "clean" | "literary"


def _make_completion_kwargs(
    model: str,
    messages: list,
    *,
    timeout: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stream: bool = False,
) -> dict:
    """Build chat.completions.create kwargs via the unified provider layer.

    Delegates to gm.llm_client._prepare_kwargs so reasoning config, max_tokens
    naming, and OpenRouter provider preferences live in exactly one place.
    """
    if timeout is None:
        timeout = 60.0
    kwargs = _prepare_kwargs(
        model=model,
        messages=messages,
        temperature=1.0,
        max_tokens=max_tokens if max_tokens is not None else MAX_TOKENS,
        timeout=timeout,
        seed=None,
        response_format=None,
        extra=None,
    )
    # Narration uses default sampling; remove temperature so models that
    # require special temperatures (reasoning models) keep their defaults.
    kwargs.pop("temperature", None)
    if stream:
        kwargs["stream"] = True
    return kwargs


def _retry_after_seconds(error: Exception) -> float | None:
    """Extract OpenRouter retry-after metadata when the provider supplies it."""
    response = getattr(error, "response", None)
    if response is None:
        return None
    try:
        data = response.json()
    except Exception:
        return None
    metadata = (data.get("error") or {}).get("metadata") or {}
    value = metadata.get("retry_after_seconds")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_transient_provider_error(error: Exception) -> bool:
    status = getattr(error, "status_code", None)
    if status in {408, 409, 429, 500, 502, 503, 504}:
        return True
    text = str(error).lower()
    return any(token in text for token in ("rate", "timeout", "temporarily", "overloaded"))


def _create_completion_with_retries(client: OpenAI, kwargs: dict, model: str):
    """Call the configured provider with bounded retry/backoff for transient errors."""
    attempts = max(1, int(os.getenv("NARRATION_PROVIDER_RETRIES", "3")))
    base_delay = max(0.0, float(os.getenv("NARRATION_PROVIDER_BACKOFF_SEC", "2.0")))
    last_error: Exception | None = None

    for attempt in range(attempts):
        started = time.time()
        try:
            response = client.chat.completions.create(**kwargs)
            log_llm_usage(
                purpose="narration", tier=TIER_QUALITY,
                model=model, response=response,
            )
            if LLM_TIMING_LOG:
                logging.info(
                    "LLM_TIMING kind=narration_completion model=%s ok=true "
                    "attempt=%d/%d elapsed_sec=%.2f",
                    model, attempt + 1, attempts, time.time() - started,
                )
            return response
        except Exception as e:
            last_error = e
            if LLM_TIMING_LOG:
                logging.info(
                    "LLM_TIMING kind=narration_completion model=%s ok=false "
                    "attempt=%d/%d elapsed_sec=%.2f",
                    model, attempt + 1, attempts, time.time() - started,
                )
            if attempt == attempts - 1 or not _is_transient_provider_error(e):
                raise
            delay = _retry_after_seconds(e)
            if delay is None:
                delay = base_delay * (2 ** attempt)
            delay = min(max(delay, 0.5), 20.0)
            logging.warning(
                "Narration provider call failed transiently "
                "(model=%s attempt=%d/%d): %s. Retrying in %.1fs.",
                model, attempt + 1, attempts, e, delay,
            )
            time.sleep(delay)

    raise last_error or RuntimeError("Narration provider call failed")

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


def _make_client(purpose: str = "narration") -> tuple[OpenAI, str]:
    """Return (client, model_string) for a quality-tier purpose.

    Routes through gm.llm_client so live narration can use the fast model
    while milestones/time skips keep the quality tier. Per-call-site overrides
    are available via NARRATION_MODEL, MILESTONE_MODEL, etc.
    """
    return _make_unified_client(), resolve_model(tier=TIER_QUALITY, purpose=purpose)


def _narration_model_candidates(primary_model: str) -> list[str]:
    """Ordered cloud model candidates for a live narration turn."""
    candidates = [primary_model]
    for model in NARRATION_FALLBACK_MODELS:
        if model not in candidates:
            candidates.append(model)

    quality_model = resolve_model(tier=TIER_QUALITY)
    if quality_model and quality_model not in candidates:
        candidates.append(quality_model)
    return candidates


@dataclass
class NarrationResult:
    passage:      str
    choices:      list[str]          # player-facing text (skill tags stripped)
    skill_tags:   list[str | None]   # per-choice skill tag or None if no check
    raw_response: str = ""
    state_patch:  dict = field(default_factory=dict)


class CloudGMError(Exception):
    pass


def _build_prompts(ctx: ContextPackage) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for narration.

    The system prompt is byte-identical across every turn of every session
    — style guide, task rules, dice interpretation. Providers with prefix
    caching (DeepSeek caches automatically) only bill those tokens at the
    cache-hit rate when the prefix is stable, so static instruction must
    never be interleaved with per-turn context. The user prompt orders
    per-act-stable blocks before per-turn-volatile ones for the same reason.

    The literary voice variant predates the split and keeps its legacy
    single-message structure: system_prompt is "" and the full template
    is returned as the user prompt.
    """
    user = _build_prompt(ctx)
    if PROSE_VOICE == "literary":
        return "", user
    return PROMPT_PATH_SYSTEM.read_text(encoding="utf-8"), user


def _build_prompt(ctx: ContextPackage) -> str:
    from engine.talents import build_talent_capabilities, build_talent_activations_block
    from engine.force import build_force_capabilities_block
    from gm.context import (
        build_evolved_voice_block as _build_evolved_voice_block,
        build_background_block as _build_background_block,
    )

    prompt_path    = PROMPT_PATH_LITERARY if PROSE_VOICE == "literary" else PROMPT_PATH
    template       = prompt_path.read_text(encoding="utf-8")
    recent_summary = _format_recent_turns(ctx.recent_turns)
    full_summary   = (
        f"{ctx.story_summary}\n\nRECENT TURNS:\n{recent_summary}\n\n"
        "IMMEDIATE CONTINUITY RULE: Continue from the final state of the "
        "most recent narration excerpt. Do not replay dialogue, discovery "
        "beats, reveals, or environmental beats that already happened unless "
        "the player explicitly repeats them."
    )
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
        evolved_voice_block=_build_evolved_voice_block(ctx.character),
        background_block=_build_background_block(ctx.character),
        lore_seeds_block=getattr(ctx, "lore_seeds_block", "") or "",
        growth_recognition_block=getattr(ctx, "growth_recognition_block", "") or "",
        tactical_state_block=getattr(ctx, "tactical_state_block", "") or "",
        npc_counter_move_block=getattr(ctx, "npc_counter_move_block", "") or "",
        faction_reactivity_block=getattr(ctx, "faction_reactivity_block", "") or "",
        side_content_block=getattr(ctx, "side_content_block", "") or "",
        pivot_warning_block=getattr(ctx, "pivot_warning_block", "") or "",
        equipment_block=build_equipment_narration_block(ctx.character.loadout),
        force_state_block=ctx.force_state_block,
        force_capabilities_block=force_caps,
        talent_capabilities_block=talent_caps,
        aspiration_echo_block=ctx.build_aspiration_echo_block(),
        identity_drift_block=ctx.build_identity_drift_block(),
        introspection_trigger_block=ctx.build_introspection_trigger_block(),
        depth_card_block=ctx.depth_card_block,
        narrative_arc_block=getattr(ctx, "narrative_arc_block", "") or "",
        campaign_name=ctx.arc.campaign_name,
        story_position=f"Part {ctx.arc.current_act} of {ctx.arc.total_acts} — {ctx.arc.act_name}",
        throughline_question=ctx.arc.throughline_question,
        tension_level=ctx.arc.tension_level,
        beat_role_block=getattr(ctx, "beat_role_block", "") or "",
        story_summary=full_summary,
        open_threads=ctx.build_open_threads_block(),
        memorable_moments_block=ctx.build_memorable_moments_block(),
        reputation_block=ctx.build_reputation_block(),
        era_voice_block=ctx.era_voice_block,
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
        behavioral_availability_block=ctx.build_behavioral_availability_block(),
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


def _parse_state_patch(raw_patch: str) -> dict:
    """Parse optional hidden scene-state JSON from narration output.

    The state patch is advisory: malformed or missing JSON must not block a
    turn. The deterministic scene-state updater in api.game_routes supplies
    a fallback, so this only strengthens continuity when the model complies.
    """
    if not raw_patch:
        return {}

    match = re.search(r"\{.*\}", raw_patch, flags=re.DOTALL)
    if not match:
        return {}

    try:
        data = json.loads(match.group(0))
    except Exception:
        logging.warning("Narration state patch was not valid JSON")
        return {}

    if not isinstance(data, dict):
        return {}

    allowed = {
        "current_location",
        "current_objective",
        "present_npcs",
        "scene_type",
        "immediate_pressure",
        "known_facts",
        "threads_advanced",
        "threads_resolved",
        "threads_opened",
        "avoid_repeating",
        "next_beat_requirement",
    }
    return {k: v for k, v in data.items() if k in allowed}


def _strip_wrapped_narration_quotes(passage: str) -> str:
    """Remove accidental quote wrappers around whole prose paragraphs."""
    cleaned: list[str] = []
    for paragraph in re.split(r"\n\s*\n", passage.strip()):
        text = paragraph.strip()
        if not text:
            continue
        if len(text) > 80:
            for left, right in (('"', '"'), ("“", "”")):
                if text.startswith(left) and text.endswith(right):
                    if re.search(
                        r'^"[^"\n]+,"\s+\w+\s+'
                        r'(says|said|asks|asked|answers|answered|'
                        r'whispers|whispered|shouts|shouted|murmurs|murmured)\b',
                        text,
                    ):
                        break
                    inner = text[1:-1].strip()
                    if (
                        re.search(
                            r"\b(you|You|Kira|Luke|Tionne|the|The)\s+"
                            r"(ask|step|feel|hold|move|look|keep|hear|see|"
                            r"reach|wait|stand|turn|draw|follow|press|let|"
                            r"try|take|say|says|does|stops|drags|answers|"
                            r"glances|shakes|goes|freezes|watches)",
                            inner,
                        )
                        or re.search(
                            r"\b(the|The)\s+\w+\s+"
                            r"(stops|drags|waits|stays|holds|comes|goes|"
                            r"answers|moves|echoes|rings|turns|lands|opens|closes)",
                            inner,
                        )
                    ):
                        text = inner
                    break
        cleaned.append(text)
    return "\n\n".join(cleaned)


def _parse_choice_lines(choices_raw: str) -> tuple[list[str], list[str | None]]:
    """Parse choice lines into (choices, skill_tags), max 4.

    Strips numbering, bullets, markdown noise, and wrapping quotes, then
    extracts and strips skill tags: "[Deception]", "[Force:Move]", or
    "[Force:Sense -- why this is risky]".
    """
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

    skill_tag_pattern = re.compile(r"\[([^\]]+)\]")
    choices: list[str] = []
    skill_tags: list[str | None] = []
    for choice_text in raw_choices[:4]:
        matches = list(skill_tag_pattern.finditer(choice_text))
        match = matches[-1] if matches else None
        tag = None
        if match:
            tag = _normalize_choice_tag(match.group(1))
            choice_text = (
                choice_text[:match.start()] + choice_text[match.end():]
            ).strip()
        choices.append(_clean_choice_text(choice_text))
        skill_tags.append(tag)
    return choices, skill_tags


def _parse_response(raw: str) -> NarrationResult:
    """
    Split GM response into passage and choices.
    Enforces: delimiter present, configured word count bounds, 2-4 choices.
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
    # Also recover bare bullet choices at the end of the response.
    if "---CHOICES---" not in normalized:
        lines = normalized.split("\n")
        start = max(len(lines) - 15, 0)
        for i in range(start, len(lines)):
            if not re.match(r"^\s*[-*]\s+\S", lines[i]):
                continue
            bullet_count = 0
            for line in lines[i:]:
                if re.match(r"^\s*[-*]\s+\S", line):
                    bullet_count += 1
                elif line.strip():
                    break
            if bullet_count >= 2:
                lines.insert(i, "---CHOICES---")
                normalized = "\n".join(lines)
                break
    if "---CHOICES---" not in normalized:
        raise CloudGMError("GM response missing ---CHOICES--- delimiter")

    passage, choices_raw = normalized.split("---CHOICES---", 1)
    passage     = passage.strip()
    choices_raw = choices_raw.strip()

    state_patch = {}
    for delimiter in ("---STATE_PATCH---", "---STATE PATCH---", "STATE_PATCH:"):
        if delimiter in choices_raw:
            choices_raw, patch_raw = choices_raw.split(delimiter, 1)
            state_patch = _parse_state_patch(patch_raw)
            choices_raw = choices_raw.strip()
            break

    # Strip markdown emphasis (*italic* and **bold**) — frontend is plain text
    passage = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", passage)
    # Strip stray --- separators from passage edges
    passage = re.sub(r"^-{3,}\s*\n", "", passage)
    passage = re.sub(r"\n\s*-{3,}\s*$", "", passage)
    passage = _strip_wrapped_narration_quotes(passage)

    word_count = len(passage.split())
    if word_count < NARRATION_MIN_WORDS:
        raise CloudGMError(
            f"Passage too short ({word_count} words, minimum {NARRATION_MIN_WORDS}). Retrying."
        )
    if word_count > NARRATION_MAX_WORDS:
        raise CloudGMError(
            f"Passage too long ({word_count} words, maximum {NARRATION_MAX_WORDS}). Retrying."
        )

    choices, skill_tags = _parse_choice_lines(choices_raw)

    if len(choices) < 2:
        raise CloudGMError(
            f"GM returned {len(choices)} choice(s). Minimum 2 required. Retrying."
        )

    return NarrationResult(
        passage=passage,
        choices=choices,
        skill_tags=skill_tags,
        raw_response=raw,
        state_patch=state_patch,
    )


def regenerate_choices(
    ctx: ContextPackage,
    result: NarrationResult,
    quality,
) -> Optional[NarrationResult]:
    """Repair a rejected choice set without re-running full narration.

    The passage already passed structural validation — rewriting 4 lines
    of choices does not justify re-spending the full narration budget.
    Returns a new NarrationResult with replacement choices, or None when
    repair fails (caller accepts the original — fail-open).
    """
    from gm.choice_validator import build_quality_correction
    from gm.llm_client import call_chat

    words = result.passage.split()
    passage_tail = " ".join(words[-150:]) if len(words) > 150 else result.passage
    old_choices = "\n".join(f"{i+1}. {c}" for i, c in enumerate(result.choices))

    prompt = (
        "You wrote a story passage with player choices for a Star Wars "
        "narrative RPG. The choices were rejected for quality issues; the "
        "passage itself is fine and must not change.\n\n"
        f"SCENE: {ctx.situation[:600]}\n\n"
        f"CHARACTER: {ctx.character.name}, {ctx.character.career}\n\n"
        f"END OF PASSAGE:\n...{passage_tail}\n\n"
        f"REJECTED CHOICES:\n{old_choices}\n\n"
        f"{build_quality_correction(quality)}\n\n"
        "Write 2-4 replacement choices. Rules:\n"
        "- Each choice must be specific to this scene and this character\n"
        "- Each choice should reveal something different about who the "
        "character is, not just accomplish a goal differently\n"
        "- At least one lower-risk and one higher-risk option\n"
        "- If a choice would require a dice check, append the skill tag at "
        'the very end in square brackets, e.g. "Bluff your way past the '
        'checkpoint [Deception]"\n'
        "- Choices without a dice check have no tag\n"
        "Return ONLY the numbered choices, one per line. No preamble, no "
        "commentary."
    )

    try:
        raw = call_chat(
            tier=TIER_QUALITY,
            purpose="choice_repair",
            user=prompt,
            temperature=0.7,
            max_tokens=300,
            timeout=30.0,
            retries=2,
        )
        choices, skill_tags = _parse_choice_lines(raw)
    except Exception as e:
        logging.warning(f"Choice repair failed (keeping original choices): {e}")
        return None

    if len(choices) < 2:
        logging.warning(
            "Choice repair returned %d choice(s); keeping original choices.",
            len(choices),
        )
        return None

    return NarrationResult(
        passage=result.passage,
        choices=choices,
        skill_tags=skill_tags,
        raw_response=result.raw_response,
        state_patch=result.state_patch,
    )


def narrate_turn(
    ctx:         ContextPackage,
    max_retries: Optional[int] = None,
) -> NarrationResult:
    """
    One call to the configured provider for narration + choices. This is
    the ONE cloud call per turn. Retries with a correction note appended
    on validation failure.
    """
    if max_retries is None:
        max_retries = NARRATION_PARSE_RETRIES

    return _narrate_with_backend(ctx, max_retries)


def _narrate_with_backend(
    ctx: ContextPackage, max_retries: int,
) -> NarrationResult:
    """Core narration logic.

    Includes post-parse choice quality validation (spec §5.2).
    """
    from gm.choice_validator import validate_choice_quality

    client, model = _make_client()
    fallback_models = [
        candidate
        for candidate in _narration_model_candidates(model)
        if candidate != model
    ]
    system_prompt, user_prompt = _build_prompts(ctx)
    last_error    = None
    best_result: NarrationResult | None = None  # best structurally valid result

    for attempt in range(max_retries + 1):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        if attempt > 0 and last_error:
            messages.append({
                "role": "user",
                "content": (
                    f"Your previous response was rejected. "
                    f"Reason: {last_error}. Please correct this and try again."
                ),
            })

        model_candidates = [model] + [
            candidate for candidate in fallback_models if candidate != model
        ]
        response = None
        for candidate_index, candidate_model in enumerate(model_candidates):
            kwargs = _make_completion_kwargs(
                candidate_model,
                messages,
                timeout=NARRATION_TIMEOUT_SEC,
                max_tokens=NARRATION_MAX_TOKENS,
            )
            try:
                response = _create_completion_with_retries(client, kwargs, candidate_model)
                if candidate_model != model:
                    logging.warning(
                        "Narration recovered with fallback model=%s after failure: %s",
                        candidate_model,
                        last_error,
                    )
                model = candidate_model
                break
            except Exception as e:
                last_error = str(e)
                if candidate_index == len(model_candidates) - 1:
                    raise
                logging.warning(
                    "Narration provider failed for model=%s; trying fallback model=%s. Error: %s",
                    candidate_model,
                    model_candidates[candidate_index + 1],
                    e,
                )
        if response is None:
            raise CloudGMError(f"Narration provider failed: {last_error}")
        choice = response.choices[0]
        raw = choice.message.content or ""
        logging.debug(
            f"=== GM RESPONSE (attempt {attempt+1}) ===\n"
            f"model={model}, finish_reason={choice.finish_reason}, "
            f"content_len={len(raw)}, refusal={getattr(choice.message, 'refusal', None)}\n"
            f"RAW:\n{raw[:2000]}\n=== END ==="
        )

        try:
            result = _parse_response(raw)
        except CloudGMError as e:
            last_error = str(e)
            logging.warning(
                "Narration parse rejected attempt=%d/%d model=%s reason=%s",
                attempt + 1, max_retries + 1, model, last_error,
            )
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

        # Rule 4 enforcement — the dice are the truth. On failed checks,
        # a cheap fast-tier post-check verifies the prose depicts failure.
        # A mismatch is a real validation failure: retry the narration with
        # a correction note, exactly like a word-count violation.
        if (
            DICE_POLARITY_CHECK
            and ctx.roll_result is not None
            and not ctx.roll_result.succeeded
        ):
            from gm.fast_gm import check_narration_polarity

            verdict = check_narration_polarity(
                result.passage,
                ctx.situation,
                outcome_label=ctx.roll_result.narrative_label(),
            )
            if verdict == "success":
                last_error = (
                    "The dice ruled this attempt a FAILURE, but your passage "
                    "depicts the attempted action succeeding. Rewrite so the "
                    "core attempted goal is denied. Advantage may soften the "
                    "landing with a peripheral gain, but the attempted goal "
                    "itself must visibly fail."
                )
                logging.warning(
                    "Narration polarity mismatch (dice=failure, prose=success) "
                    "attempt=%d/%d model=%s",
                    attempt + 1, max_retries + 1, model,
                )
                if attempt < max_retries:
                    continue
                logging.warning(
                    "Polarity retry budget exhausted — accepting narration "
                    "despite dice/prose mismatch."
                )

        # Choice quality validation
        if not CHOICE_QUALITY_INLINE:
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

        # 2+ dimensions failed — repair the choices in place. The passage
        # is structurally valid; regenerating the full narration to fix
        # 4 lines of choices burns the whole narration budget for nothing.
        logging.warning(
            f"Choice quality rejected ({quality.fail_count} dimensions failed: "
            f"{quality.rejection_reason}). Regenerating choices only."
        )
        repaired = regenerate_choices(ctx, result, quality)
        if repaired is None:
            return result  # repair failed — fail-open on the original

        requality = validate_choice_quality(
            situation=ctx.situation,
            character_name=ctx.character.name,
            character_career=ctx.character.career,
            passage=repaired.passage,
            choices=repaired.choices,
        )
        if requality.passed or requality.fail_count <= quality.fail_count:
            return repaired
        logging.warning(
            "Choice repair did not improve quality "
            f"({requality.fail_count} dimensions still failing). "
            "Keeping original choices."
        )
        return result

    raise CloudGMError("Unreachable")


def _normalize_choice_tag(raw_tag: str) -> str | None:
    """Normalize bracketed choice metadata into a mechanical tag.

    The narrator sometimes helpfully adds prose inside the brackets
    ("[Force:Sense -- gauge her fear]"). Keep the mechanical prefix and
    discard the annotation so the player never sees the bracket text and
    the turn loop still gets a usable tag.
    """
    tag = raw_tag.strip()
    lower = tag.lower()
    if lower.startswith("force") and ":" in lower:
        power_text = lower.split(":", 1)[1].strip().replace(" ", "_")
        power_match = re.match(r"[a-z]+(?:_[a-z]+)*", power_text)
        if power_match:
            return f"force:{power_match.group(0)}"

    tag = re.split(r"\s+(?:--+|\u2014|\u2013|-)\s+|\s+\(", tag, maxsplit=1)[0]
    tag = tag.strip().strip(":").lower().replace(" ", "_").replace("-", "_")
    tag = re.sub(r"[^a-z0-9_:]", "", tag)
    try:
        from gm.fast_gm import SKILL_ALIASES, VALID_SKILLS

        if tag in VALID_SKILLS:
            return tag
        if tag in SKILL_ALIASES:
            return SKILL_ALIASES[tag]
        for alias, skill in SKILL_ALIASES.items():
            if tag.startswith(f"{alias}_"):
                return skill
        for skill in sorted(VALID_SKILLS, key=len, reverse=True):
            if tag.startswith(f"{skill}_"):
                return skill
    except Exception:
        pass
    return tag or None


def _clean_choice_text(text: str) -> str:
    """Remove model-side choice annotations that should not face players."""
    cleaned = re.sub(r"\*{1,2}", "", text).strip()
    cleaned = re.sub(r"\s+\([^)]{18,}\)\s*$", "", cleaned).strip()
    cleaned = re.sub(r"\s+--\s+[^.?!\"]{18,}$", "", cleaned).strip()
    cleaned = cleaned.strip().strip('"').strip()
    return cleaned


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
    system_prompt, user_prompt = _build_prompts(ctx)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    kwargs = _make_completion_kwargs(
        model,
        messages,
        timeout=NARRATION_TIMEOUT_SEC,
        max_tokens=NARRATION_MAX_TOKENS,
        stream=True,
    )
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

    client, model = _make_client(purpose="milestone")
    msg_content = prompt

    kwargs = _make_completion_kwargs(
        model,
        [{"role": "user", "content": msg_content}],
    )
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

    client, model = _make_client(purpose="milestone")
    msg_content = prompt

    kwargs = _make_completion_kwargs(
        model,
        [{"role": "user", "content": msg_content}],
    )
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
    )


# ── Campaign epilogue generation ──────────────────────────────────────

EPILOGUE_PROMPT_PATH = Path(__file__).parent / "prompts" / "epilogue.txt"


def generate_epilogue(
    character,
    spine: dict,
    story_summary: str,
    *,
    resolved_ending: dict | None = None,
    ending_state_block: str = "",
) -> dict:
    """Generate the campaign-closing epilogue after the final act resolves.

    When the engine has already resolved which authored ending the played
    story took (`resolved_ending` — classified from the climax branch and
    persisted in arc_state), the model WRITES that ending; it does not
    choose. Without a resolved ending it falls back to offering the menu
    and letting the model match (legacy sessions, spines without branch
    structure).

    `ending_state_block` carries the final mechanical truth — NPC
    dispositions, morality, threads — so NPC fates in the epilogue are
    grounded in play state, not invented.

    Returns {"ending_name": str, "epilogue": str}. Raises on provider
    failure — the API endpoint surfaces the error and the player can
    retry; a campaign ending deserves better than a silently degraded
    fallback (Rule 5).
    """
    if resolved_ending:
        name = resolved_ending.get("name", "What Comes After")
        synopsis = resolved_ending.get("synopsis", "")
        payoff = (resolved_ending.get("thematic_payoff", "")
                  or resolved_ending.get("branch_id", ""))
        ending_paths_block = (
            "THE ENDING THE STORY REACHED (the climax branch is already "
            "decided — write the epilogue as THIS ending, no other):\n"
            f"- {name}: {synopsis} [{payoff}]"
        )
    else:
        ending_paths = (spine.get("story_architecture") or {}).get("ending_paths", [])
        if ending_paths:
            path_lines = ["ENDING PATHS (choose the one the played story earned):"]
            for path in ending_paths:
                if not isinstance(path, dict):
                    continue
                name = path.get("name", "")
                synopsis = path.get("synopsis", "")
                payoff = path.get("thematic_payoff", "") or path.get("branch_id", "")
                path_lines.append(f"- {name}: {synopsis} [{payoff}]")
            ending_paths_block = "\n".join(path_lines)
        else:
            ending_paths_block = ""

    if ending_state_block:
        story_summary = (story_summary or "") + "\n\n" + ending_state_block

    arc = getattr(character, "narrative_arc", None)
    arc_block = ""
    if arc is not None:
        lie = getattr(arc, "lie", "") or ""
        need = getattr(arc, "need", "") or ""
        if lie or need:
            arc_block = (
                "CHARACTER INNER STORY (resolve it honestly — transformed, "
                f"resisted, or still gripping):\nThe lie they believed: {lie}\n"
                f"What they needed: {need}"
            )

    template = EPILOGUE_PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template.format(
        campaign_name=spine.get("name", "the campaign"),
        throughline_question=spine.get("throughline_question", ""),
        character_summary=character.narrative_status(),
        character_voice=getattr(character, "voice_notes", ""),
        story_summary=story_summary or "No summary available.",
        ending_paths_block=ending_paths_block,
        arc_block=arc_block,
    )

    raw = _call_chat_for_epilogue(prompt)

    ending_name = "What Comes After"
    passage = raw.strip()
    match = re.match(r"^ENDING:\s*(.+?)\s*\n+", passage)
    if match:
        ending_name = match.group(1).strip()
        passage = passage[match.end():].strip()
    passage = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", passage)

    # When the engine resolved the branch, the engine owns the ending name —
    # the model writes the ending; it does not get to rename or swap it.
    if resolved_ending:
        ending_name = resolved_ending.get("name", ending_name)

    return {"ending_name": ending_name, "epilogue": passage}


def _call_chat_for_epilogue(prompt: str) -> str:
    from gm.llm_client import call_chat

    return call_chat(
        tier=TIER_QUALITY,
        purpose="epilogue",
        user=prompt,
        temperature=0.7,
        max_tokens=1200,
        timeout=NARRATION_TIMEOUT_SEC,
        retries=3,
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

    client, model = _make_client(purpose="narration")
    msg_content = prompt

    kwargs = _make_completion_kwargs(
        model,
        [{"role": "user", "content": msg_content}],
    )
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

    client, model = _make_client(purpose="narration")
    msg_content = prompt

    kwargs = _make_completion_kwargs(
        model,
        [{"role": "user", "content": msg_content}],
    )
    response = client.chat.completions.create(**kwargs)
    raw = response.choices[0].message.content or ""

    # Strip markdown emphasis
    passage = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", raw.strip())
    return passage
