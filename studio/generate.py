"""
Campaign spine generation orchestration — Modes 3 and 2.

Mode 3 (collaborative authoring):
  Human drives, AI assists. Functions for galactic context drafting,
  NPC voice generation, gap identification, and spine finalization.

Mode 2 (thematic steering):
  AI generates from a thematic brief. Author reviews and edits.
  generate_from_brief() produces a complete spine draft.

This module provides orchestration functions callable via Studio API routes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from openai import OpenAI

from studio.schema import CampaignSpine, NPC, Act
from studio.validate import validate_spine, ValidationReport
from studio.seeding import (
    derive_stage_seed,
    generate_master_seed,
    build_generation_metadata,
    derive_all_seeds,
    STAGE_WORLD,
    STAGE_VOICE,
    STAGE_NPCS,
    STAGE_ANCHORS,
    STAGE_VARIANTS,
    STAGE_THREADS,
)


# ── Configuration ─────────────────────────────────────────────────────

PROMPT_DIR = Path(__file__).parent / "prompts"
MODE3_PROMPT_PATH = PROMPT_DIR / "mode3_assist.txt"
MODE2_PROMPT_PATH = PROMPT_DIR / "mode2_generate.txt"
NPC_VOICE_PROMPT_PATH = PROMPT_DIR / "npc_voice_gen.txt"

CLOUD_PROVIDER = os.getenv("CLOUD_PROVIDER", "openai")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "gpt-5.2")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen3.5:9b")
NARRATIVE_BACKEND = os.getenv("NARRATIVE_BACKEND", "cloud")

PROVIDER_BASE_URLS = {
    "openai": None,
    "openrouter": "https://openrouter.ai/api/v1",
}


# ── LLM Client ───────────────────────────────────────────────────────


def _get_cloud_client() -> OpenAI:
    """Get an OpenAI-compatible client based on environment config."""
    base_url = PROVIDER_BASE_URLS.get(CLOUD_PROVIDER)
    return OpenAI(base_url=base_url)


def _get_local_client() -> OpenAI:
    """Get an Ollama-compatible OpenAI client."""
    return OpenAI(base_url=f"{OLLAMA_URL}/v1", api_key="ollama")


def _get_client() -> tuple[OpenAI, str]:
    """Get the appropriate client and model based on backend config."""
    if NARRATIVE_BACKEND == "local":
        return _get_local_client(), LOCAL_MODEL
    return _get_cloud_client(), CLOUD_MODEL


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    *,
    seed: Optional[int] = None,
    max_tokens: int = 4000,
    temperature: float = 0.7,
) -> str:
    """Make a single LLM call and return the response text.

    Args:
        system_prompt: System message content.
        user_prompt: User message content.
        seed: Optional deterministic seed.
        max_tokens: Maximum completion tokens.
        temperature: Sampling temperature.

    Returns:
        The assistant's response text.

    Raises:
        RuntimeError: If the LLM call fails after retries.
    """
    client, model = _get_client()

    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if seed is not None:
        kwargs["seed"] = seed

    for attempt in range(3):
        try:
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if content is None:
                raise RuntimeError("LLM returned empty content")
            return content.strip()
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(
                    f"LLM call failed after 3 attempts: {e}"
                ) from e


# ── Prompt assembly ───────────────────────────────────────────────────


def _load_prompt(path: Path) -> str:
    """Load a prompt template from disk."""
    return path.read_text(encoding="utf-8")


def _format_acts_summary(spine_data: dict) -> str:
    """Format acts for prompt injection."""
    acts = spine_data.get("acts", [])
    if not acts:
        return "(No acts defined yet)"
    lines = []
    for act in acts:
        lines.append(
            f"Act {act.get('number', '?')}: {act.get('name', 'Unnamed')} "
            f"[tension: {act.get('tension', '?')}] — "
            f"{act.get('opening_situation', '(no situation)')[:100]}..."
        )
    return "\n".join(lines)


def _format_npc_summary(spine_data: dict) -> str:
    """Format NPC roster for prompt injection."""
    npcs = spine_data.get("npc_roster", [])
    if not npcs:
        return "(No NPCs defined yet)"
    lines = []
    for npc in npcs:
        lines.append(
            f"- {npc.get('name', 'Unnamed')} [{npc.get('role', '?')}] "
            f"disp: {npc.get('disposition_start', '?')}, "
            f"motivation: {npc.get('motivation', '?')[:60]}"
        )
    return "\n".join(lines)


def _format_allegiances_summary(spine_data: dict) -> str:
    """Format allegiances for prompt injection."""
    allegiances = spine_data.get("allegiances", [])
    if not allegiances:
        return "(No allegiances defined yet)"
    lines = []
    for alleg in allegiances:
        variant_count = len(alleg.get("character_variants", []))
        lines.append(
            f"- {alleg.get('display_name', 'Unnamed')} "
            f"({variant_count} variant{'s' if variant_count != 1 else ''}): "
            f"{alleg.get('description', '')[:80]}"
        )
    return "\n".join(lines)


def _build_mode3_system_prompt(spine_data: dict) -> str:
    """Build the Mode 3 system prompt with current campaign state."""
    template = _load_prompt(MODE3_PROMPT_PATH)
    return template.format(
        era=spine_data.get("era", "unknown"),
        throughline_question=spine_data.get("throughline_question", "(not set)"),
        total_acts=spine_data.get("total_acts", "?"),
        acts_summary=_format_acts_summary(spine_data),
        npc_summary=_format_npc_summary(spine_data),
        allegiances_summary=_format_allegiances_summary(spine_data),
        task_description="{task_description}",  # Left for per-call formatting
    )


# ── Mode 3 assistance functions ──────────────────────────────────────


def generate_galactic_context(
    spine_data: dict,
    act_number: int,
    *,
    master_seed: Optional[int] = None,
) -> str:
    """Generate galactic context draft for a specific act.

    The author provides the act structure; the AI drafts the wider
    galactic context that grounds the act in the Star Wars timeline.

    Args:
        spine_data: Current spine dict (partial or complete).
        act_number: Which act to generate context for.
        master_seed: Optional seed for reproducibility.

    Returns:
        A galactic context paragraph (3-5 sentences).
    """
    seed = derive_stage_seed(master_seed, STAGE_WORLD) if master_seed else None

    act_data = None
    for act in spine_data.get("acts", []):
        if act.get("number") == act_number:
            act_data = act
            break

    if act_data is None:
        raise ValueError(f"Act {act_number} not found in spine data")

    system_prompt = _build_mode3_system_prompt(spine_data).format(
        task_description=(
            f"Generate a galactic context paragraph for Act {act_number} "
            f"('{act_data.get('name', 'Unnamed')}'). The context should describe "
            f"what is happening in the wider galaxy that affects this location "
            f"during this period. Be specific to the era and location — no "
            f"generic 'the galaxy is in turmoil' filler. 3-5 sentences."
        )
    )

    user_prompt = (
        f"Act {act_number}: {act_data.get('name', 'Unnamed')}\n"
        f"Tension: {act_data.get('tension', 'unknown')}\n"
        f"Location: {act_data.get('opening_location', 'unknown')}\n"
        f"Situation: {act_data.get('opening_situation', 'unknown')}\n\n"
        f"Generate the galactic_context field for this act."
    )

    return _call_llm(system_prompt, user_prompt, seed=seed)


def generate_npc_voice_notes(
    npc_data: dict,
    era: str,
    location: str = "",
    *,
    master_seed: Optional[int] = None,
) -> str:
    """Generate voice notes for an NPC.

    Voice notes describe HOW the character speaks — speech patterns,
    verbal habits, emotional register. Not what they say or their plot role.

    Args:
        npc_data: NPC dict with name, role, motivation, disposition, etc.
        era: Campaign era for context.
        location: Campaign location for context.
        master_seed: Optional seed for reproducibility.

    Returns:
        Voice notes text (2-3 sentences).
    """
    seed = derive_stage_seed(master_seed, STAGE_VOICE) if master_seed else None

    template = _load_prompt(NPC_VOICE_PROMPT_PATH)
    system_prompt = template.format(
        npc_name=npc_data.get("name", "Unknown"),
        npc_role=npc_data.get("role", "Unknown"),
        npc_species=npc_data.get("species", "Unknown"),
        npc_motivation=npc_data.get("motivation", "Unknown"),
        npc_disposition=npc_data.get("disposition_start", 0.5),
        behavioral_envelope=json.dumps(npc_data.get("behavioral_envelope", [])),
        era=era,
        location=location,
    )

    return _call_llm(
        system_prompt,
        "Generate voice notes for this NPC.",
        seed=seed,
        max_tokens=500,
    )


def identify_gaps(spine_data: dict) -> list[dict]:
    """Identify structural gaps in a partially-built spine.

    Pure Python analysis — no LLM calls. Checks for common issues
    authors miss during Mode 3 collaborative authoring.

    Args:
        spine_data: Current spine dict (partial or complete).

    Returns:
        List of gap dicts with 'severity', 'field', and 'message' keys.
    """
    gaps: list[dict] = []

    # Missing throughline question
    if not spine_data.get("throughline_question"):
        gaps.append({
            "severity": "error",
            "field": "throughline_question",
            "message": "Throughline question is missing. This is the campaign's central dramatic question.",
        })

    # No acts
    acts = spine_data.get("acts", [])
    if not acts:
        gaps.append({
            "severity": "error",
            "field": "acts",
            "message": "No acts defined. A campaign needs at least 2 acts.",
        })
    else:
        # Acts without galactic context
        for act in acts:
            if not act.get("galactic_context") or len(act.get("galactic_context", "")) < 20:
                gaps.append({
                    "severity": "warning",
                    "field": f"acts[{act.get('number', '?')}].galactic_context",
                    "message": f"Act {act.get('number', '?')} has no or minimal galactic context.",
                })

            # Acts without open threads (except the last)
            act_num = act.get("number", 0)
            if not act.get("open_threads") and act_num < len(acts):
                gaps.append({
                    "severity": "info",
                    "field": f"acts[{act_num}].open_threads",
                    "message": f"Act {act_num} has no open threads. Consider adding at least one.",
                })

    # No NPCs
    npcs = spine_data.get("npc_roster", [])
    if not npcs:
        gaps.append({
            "severity": "error",
            "field": "npc_roster",
            "message": "No NPCs defined. A campaign needs at least one NPC.",
        })
    else:
        # NPCs without voice notes
        for npc in npcs:
            if not npc.get("voice_notes") or len(npc.get("voice_notes", "")) < 10:
                gaps.append({
                    "severity": "warning",
                    "field": f"npc_roster.{npc.get('name', '?')}.voice_notes",
                    "message": f"NPC '{npc.get('name', '?')}' has no voice notes.",
                })

            # NPCs without per_act_state
            if not npc.get("per_act_state"):
                gaps.append({
                    "severity": "warning",
                    "field": f"npc_roster.{npc.get('name', '?')}.per_act_state",
                    "message": f"NPC '{npc.get('name', '?')}' has no per-act state defined.",
                })

            # NPCs without behavioral envelope
            if not npc.get("behavioral_envelope"):
                gaps.append({
                    "severity": "warning",
                    "field": f"npc_roster.{npc.get('name', '?')}.behavioral_envelope",
                    "message": f"NPC '{npc.get('name', '?')}' has no behavioral envelope.",
                })

    # No allegiances
    allegiances = spine_data.get("allegiances", [])
    if not allegiances:
        gaps.append({
            "severity": "error",
            "field": "allegiances",
            "message": "No allegiances defined. A campaign needs at least 2.",
        })
    elif len(allegiances) < 2:
        gaps.append({
            "severity": "error",
            "field": "allegiances",
            "message": "Only 1 allegiance defined. A campaign needs at least 2.",
        })
    else:
        for alleg in allegiances:
            if not alleg.get("character_variants"):
                gaps.append({
                    "severity": "error",
                    "field": f"allegiances.{alleg.get('id', '?')}.character_variants",
                    "message": f"Allegiance '{alleg.get('display_name', '?')}' has no character variants.",
                })

    # total_acts vs actual act count
    total = spine_data.get("total_acts", 0)
    if total and len(acts) != total:
        gaps.append({
            "severity": "error",
            "field": "total_acts",
            "message": f"total_acts is {total} but {len(acts)} acts defined.",
        })

    return gaps


def validate_and_report(spine_data: dict) -> ValidationReport:
    """Parse spine data and run full validation.

    This is the final step of Mode 3 workflow — validates the complete
    spine before it can be consumed by the Game Engine.

    Args:
        spine_data: Complete spine dict.

    Returns:
        ValidationReport with pass/fail status and all errors/warnings.

    Raises:
        ValueError: If the spine data cannot be parsed as a CampaignSpine.
    """
    try:
        spine = CampaignSpine(**spine_data)
    except Exception as e:
        raise ValueError(f"Spine data failed schema parsing: {e}") from e

    return validate_spine(spine)


def finalize_spine(
    spine_data: dict,
    *,
    master_seed: Optional[int] = None,
    model_used: str = "",
) -> tuple[CampaignSpine, ValidationReport]:
    """Finalize a spine — parse, attach metadata, validate.

    This is the production entry point for completing Mode 3 authoring.

    Args:
        spine_data: Complete spine dict.
        master_seed: If AI assistance was used, the master seed.
        model_used: Model identifier used for assistance.

    Returns:
        Tuple of (validated CampaignSpine, ValidationReport).

    Raises:
        ValueError: If spine fails schema parsing or validation.
    """
    # Attach generation metadata if AI assistance was used
    if master_seed is not None:
        stage_seeds = derive_all_seeds(master_seed)
        spine_data["generation_metadata"] = build_generation_metadata(
            master_seed=master_seed,
            stage_seeds=stage_seeds,
            model_used=model_used,
            generation_mode="mode3_assist",
        )

    spine = CampaignSpine(**spine_data)
    report = validate_spine(spine)

    if not report.passed:
        error_msgs = "; ".join(e.message for e in report.errors)
        raise ValueError(f"Spine failed validation: {error_msgs}")

    return spine, report


# ── Mode 2: Thematic Steering ────────────────────────────────────────


@dataclass
class ThematicBrief:
    """Input for Mode 2 generation."""
    era: str
    location: str
    tone: str
    throughline_question: str
    campaign_concept: str
    moral_register: str = "morally gray"
    total_acts: int = 4
    constraints: str = ""


def generate_from_brief(
    brief: ThematicBrief,
    *,
    master_seed: Optional[int] = None,
    max_retries: int = 3,
) -> tuple[dict, int]:
    """Generate a complete campaign spine from a thematic brief.

    Mode 2 workflow: AI generates the entire spine from thematic direction.
    The author reviews and edits the result.

    Args:
        brief: Thematic direction from the author.
        master_seed: Optional seed for reproducibility. If None, generated.
        max_retries: Number of LLM attempts before giving up.

    Returns:
        Tuple of (spine_data dict, master_seed used).

    Raises:
        RuntimeError: If generation fails after all retries.
    """
    if master_seed is None:
        master_seed = generate_master_seed()

    seed = derive_stage_seed(master_seed, STAGE_WORLD)

    template = _load_prompt(MODE2_PROMPT_PATH)
    system_prompt = template.format(
        era=brief.era,
        location=brief.location,
        tone=brief.tone,
        throughline_question=brief.throughline_question,
        campaign_concept=brief.campaign_concept,
        moral_register=brief.moral_register,
        total_acts=brief.total_acts,
        constraints=brief.constraints or "(none)",
    )

    for attempt in range(max_retries):
        try:
            raw = _call_llm(
                system_prompt,
                "Generate the complete campaign spine JSON now.",
                seed=seed,
                max_tokens=8000,
                temperature=0.8,
            )

            # Strip markdown code fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                # Remove first line (```json) and last line (```)
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            spine_data = json.loads(cleaned)

            # Ensure required top-level fields
            spine_data.setdefault("era", brief.era)
            spine_data.setdefault("total_acts", brief.total_acts)
            spine_data.setdefault("throughline_question", brief.throughline_question)

            # Attach generation metadata
            stage_seeds = derive_all_seeds(master_seed)
            spine_data["generation_metadata"] = build_generation_metadata(
                master_seed=master_seed,
                stage_seeds=stage_seeds,
                model_used=CLOUD_MODEL,
                generation_mode="mode2",
            )

            return spine_data, master_seed

        except json.JSONDecodeError as e:
            if attempt == max_retries - 1:
                raise RuntimeError(
                    f"Mode 2 generation failed: LLM returned invalid JSON after "
                    f"{max_retries} attempts. Last error: {e}"
                )
        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(
                    f"Mode 2 generation failed after {max_retries} attempts: {e}"
                )

    # Should not reach here, but satisfy type checker
    raise RuntimeError("Mode 2 generation failed unexpectedly")
