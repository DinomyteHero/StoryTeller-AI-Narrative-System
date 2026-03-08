"""
Saga Stage 2 — Divergent generation.

Each assigned persona generates sequel direction candidates. The persona
biases creative direction without constraining it. Multiple directions
per persona are generated and collected.

The prior campaign is NOT provided at this stage — seeding does not
recover knowledge partitioning (Implementation Rule 2).
"""

from __future__ import annotations

from typing import Optional

from studio.schema import SequelDirection
from studio.seeding import derive_stage_seed, STAGE_SAGA_DIVERGE


DIVERGE_SYSTEM_PROMPT = """You are a creative consultant with the following background:

{persona_description}

You are generating a sequel direction for a Star Wars tabletop RPG campaign.
The prior campaign had this throughline question: "{prior_throughline}"
The era is: {era}

Generate a SEQUEL DIRECTION — a lightweight creative brief for a new campaign.
The sequel must be structurally distinct from the prior campaign. Think about
what kind of story YOUR background and perspective would find compelling.

Return valid JSON with these fields:
- throughline_question: A new dramatic question (must end with ?)
- primary_conflict_type: The core conflict (not "good vs evil")
- setting_description: 1-2 sentences about the setting
- tone_shift: How this differs from the prior campaign's tone
- key_thematic_elements: 3-5 thematic elements (list of strings)
- denial_constraints_applied: What you deliberately avoided (list of strings)

Return ONLY the JSON. No markdown, no explanation."""


def generate_directions(
    personas: list[dict],
    prior_throughline: str,
    era: str,
    *,
    directions_per_persona: int = 2,
    master_seed: Optional[int] = None,
    llm_call_fn=None,
) -> list[dict]:
    """Generate sequel direction candidates from persona perspectives.

    Args:
        personas: Assigned persona dicts.
        prior_throughline: The prior campaign's throughline question.
        era: Campaign era.
        directions_per_persona: How many directions each persona generates.
        master_seed: For seed derivation.
        llm_call_fn: Injectable LLM call function (for testing).

    Returns:
        List of dicts with 'persona_id', 'direction' (SequelDirection dict).
    """
    if llm_call_fn is None:
        from studio.generate import _call_llm
        llm_call_fn = _call_llm

    base_seed = derive_stage_seed(master_seed, STAGE_SAGA_DIVERGE) if master_seed else None

    results = []
    for i, persona in enumerate(personas):
        system_prompt = DIVERGE_SYSTEM_PROMPT.format(
            persona_description=persona.get("description", ""),
            prior_throughline=prior_throughline,
            era=era,
        )

        for j in range(directions_per_persona):
            seed = (base_seed + i * 100 + j) if base_seed else None
            try:
                raw = llm_call_fn(
                    system_prompt,
                    f"Generate sequel direction #{j+1}. Make it distinct from any prior directions.",
                    seed=seed,
                    max_tokens=1000,
                    temperature=0.9,
                )
                import json
                direction = json.loads(raw.strip().strip("`").strip())
                results.append({
                    "persona_id": persona.get("id", f"persona_{i}"),
                    "direction": direction,
                })
            except Exception:
                continue  # Skip failed generations, collect what we can

    return results
