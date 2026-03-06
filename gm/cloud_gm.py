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
from gm.context import ContextPackage

PROMPT_PATH = Path(__file__).parent / "prompts" / "narration.txt"
MAX_TOKENS  = 1500

# Provider config — all from environment variables
# CLOUD_PROVIDER:    "openai" | "openrouter"
# CLOUD_MODEL:
#   openai      → "gpt-5.2", "gpt-5.2-mini", etc.
#   openrouter  → "x-ai/grok-4.1-fast", "openai/gpt-5.2", etc. (provider/model format)
# NARRATIVE_BACKEND: "cloud" | "local"

CLOUD_PROVIDER    = os.getenv("CLOUD_PROVIDER", "openai")
CLOUD_MODEL       = os.getenv("CLOUD_MODEL", "gpt-5.2")
NARRATIVE_BACKEND = os.getenv("NARRATIVE_BACKEND", "cloud")
OLLAMA_URL        = os.getenv("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL       = os.getenv("LOCAL_MODEL", "qwen3.5:9b")

PROVIDER_BASE_URLS = {
    "openai":     None,
    "openrouter": "https://openrouter.ai/api/v1",
}

# ── Scene pacing guidance (Game Mechanics §10, Vision §3) ─────────────
# Maps scene_type to:
#   - pacing: word count, sentence rhythm, structural guidance
#   - voice_exemplar: 1-2 sentences in the target register for style anchoring
#   - craft: 3-4 craft constraints SPECIFIC to this scene type (rotated,
#     not cumulative — reduces prompt overload per evaluation §2.1)
#
# HARD CONSTRAINTS (always active regardless of scene type) are in the
# prompt template's YOUR TASK section: dice fidelity, word count, delimiter,
# no game terminology, choice count, anti-slop prohibition.
#
# CRAFT CONSTRAINTS rotate per scene type — only the ones relevant to
# the current scene are injected, reducing cognitive load on the model.

SCENE_PACING = {
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
}


def _get_scene_block(scene_type: str) -> str:
    """Assemble the scene-specific prompt block from SCENE_PACING."""
    entry = SCENE_PACING.get(scene_type, SCENE_PACING["social"])
    return f"{entry['pacing']}\n\n{entry['voice_exemplar']}\n\n{entry['craft']}"


def _make_client() -> tuple[OpenAI, str]:
    """Return (client, model_string) based on active backend/provider."""
    if NARRATIVE_BACKEND == "local":
        return (
            OpenAI(api_key="ollama", base_url=f"{OLLAMA_URL}/v1"),
            LOCAL_MODEL,
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
    template       = PROMPT_PATH.read_text()
    recent_summary = _format_recent_turns(ctx.recent_turns)
    full_summary   = f"{ctx.story_summary}\n\nRECENT TURNS:\n{recent_summary}"
    scene_pacing   = _get_scene_block(ctx.scene_type)
    return template.format(
        character_summary=ctx.character.narrative_status(),
        character_voice=ctx.character.voice_notes,
        campaign_name=ctx.arc.campaign_name,
        story_position=f"Part {ctx.arc.current_act} of {ctx.arc.total_acts} — {ctx.arc.act_name}",
        throughline_question=ctx.arc.throughline_question,
        tension_level=ctx.arc.tension_level,
        story_summary=full_summary,
        open_threads=ctx.build_open_threads_block(),
        npc_states=ctx.build_npc_block(),
        location=ctx.location,
        situation=ctx.situation,
        galactic_context=ctx.galactic_context or "No wider context provided for this act.",
        dice_result_block=ctx.build_dice_result_block(),
        scene_pacing=scene_pacing,
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
    if "---CHOICES---" not in raw:
        raise CloudGMError("GM response missing ---CHOICES--- delimiter")

    passage, choices_raw = raw.split("---CHOICES---", 1)
    passage     = passage.strip()
    choices_raw = choices_raw.strip()

    word_count = len(passage.split())
    if word_count < 250:
        raise CloudGMError(
            f"Passage too short ({word_count} words, minimum 250). Retrying."
        )
    if word_count > 600:
        raise CloudGMError(
            f"Passage too long ({word_count} words, maximum 600). Retrying."
        )

    raw_choices = [
        re.sub(r"^\d+[\.\)]\s*", "", line.strip())
        for line in choices_raw.split("\n")
        if line.strip()
    ]
    raw_choices = [c for c in raw_choices if c]

    if len(raw_choices) < 2:
        raise CloudGMError(
            f"GM returned {len(raw_choices)} choice(s). Minimum 2 required. Retrying."
        )

    # Extract and strip skill tags: "[Deception]" at end of choice text
    skill_tag_pattern = re.compile(r"\s*\[([A-Za-z_\s]+)\]\s*$")
    choices = []
    skill_tags = []
    for choice_text in raw_choices[:4]:
        match = skill_tag_pattern.search(choice_text)
        if match:
            choices.append(skill_tag_pattern.sub("", choice_text).rstrip())
            skill_tags.append(match.group(1).strip().lower().replace(" ", "_"))
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
    """Core narration logic — extracted for fallback reuse."""
    client, model = _make_client()
    prompt        = _build_prompt(ctx)
    last_error    = None

    for attempt in range(max_retries + 1):
        messages = [{"role": "user", "content": prompt}]
        if attempt > 0 and last_error:
            messages.append({
                "role": "user",
                "content": (
                    f"Your previous response was rejected. "
                    f"Reason: {last_error}. Please correct this and try again."
                ),
            })

        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=messages,
            timeout=20.0,  # v1.5: 20-second timeout
        )
        raw = response.choices[0].message.content or ""

        try:
            return _parse_response(raw, used_local=used_local)
        except CloudGMError as e:
            last_error = str(e)
            if attempt == max_retries:
                raise CloudGMError(
                    f"GM failed after {max_retries + 1} attempts. "
                    f"Last error: {last_error}"
                )

    raise CloudGMError("Unreachable")


def _narrate_with_local_fallback(ctx: ContextPackage) -> NarrationResult:
    """
    Emergency fallback: narrate via local model when cloud is unavailable.
    Uses a simplified prompt optimized for the local model's capability.
    Output quality will be lower but the turn advances.
    """
    import httpx
    simplified_prompt = (
        f"You are the narrator for a Star Wars RPG. Write in second person "
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
            "model": LOCAL_MODEL,
            "prompt": simplified_prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 1200},
        },
        timeout=30.0,
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
    stream = client.chat.completions.create(
        model=model,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": _build_prompt(ctx)}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
