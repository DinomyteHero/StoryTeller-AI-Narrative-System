"""
Saga Stage 3 — Branching search.

Expands the top sequel directions into spine sketches with act-level
structure. Each direction can branch into multiple sketches based on
search_depth configuration.
"""

from __future__ import annotations

from typing import Optional

from studio.schema import SpineSketch, ActOutline, NPCOutline, SequelDirection
from studio.seeding import derive_stage_seed, STAGE_SAGA_SEARCH


SEARCH_SYSTEM_PROMPT = """You are expanding a sequel direction into a campaign spine sketch.

Sequel direction:
- Throughline question: {throughline_question}
- Primary conflict: {primary_conflict_type}
- Setting: {setting_description}
- Tone shift: {tone_shift}
- Thematic elements: {thematic_elements}

Era: {era}
Target acts: {total_acts}

Generate a SPINE SKETCH with act-level structure. Return valid JSON with:
- direction: (repeat the direction fields above as a nested object)
- act_outlines: list of objects with number, anchor_summary (one sentence), tension
- npc_roster_outline: list of objects with name, role (one sentence), motivation_summary (one sentence)
- galactic_context_notes: list of strings (one per act, one sentence each)

Tensions should follow a dramatic arc: rising → critical → climax → falling.
Include at least 3 NPCs with distinct motivations.

Return ONLY the JSON."""


def expand_to_sketches(
    directions: list[dict],
    era: str,
    total_acts: int = 4,
    *,
    search_depth: int = 1,
    master_seed: Optional[int] = None,
    llm_call_fn=None,
) -> list[dict]:
    """Expand sequel directions into spine sketches.

    Args:
        directions: Output from Stage 2 (list of persona_id + direction dicts).
        era: Campaign era.
        total_acts: Target number of acts.
        search_depth: How many sketch variants per direction.
        master_seed: For seed derivation.
        llm_call_fn: Injectable LLM call function.

    Returns:
        List of dicts with 'persona_id', 'sketch' (SpineSketch-compatible dict).
    """
    if llm_call_fn is None:
        from studio.generate import _call_llm
        llm_call_fn = _call_llm

    base_seed = derive_stage_seed(master_seed, STAGE_SAGA_SEARCH) if master_seed else None

    results = []
    for i, entry in enumerate(directions):
        direction = entry.get("direction", {})
        thematic = ", ".join(direction.get("key_thematic_elements", []))

        system_prompt = SEARCH_SYSTEM_PROMPT.format(
            throughline_question=direction.get("throughline_question", ""),
            primary_conflict_type=direction.get("primary_conflict_type", ""),
            setting_description=direction.get("setting_description", ""),
            tone_shift=direction.get("tone_shift", ""),
            thematic_elements=thematic,
            era=era,
            total_acts=total_acts,
        )

        for j in range(search_depth):
            seed = (base_seed + i * 100 + j) if base_seed else None
            try:
                raw = llm_call_fn(
                    system_prompt,
                    f"Generate spine sketch variant #{j+1}.",
                    seed=seed,
                    max_tokens=2000,
                    temperature=0.7,
                )
                import json
                sketch = json.loads(raw.strip().strip("`").strip())
                results.append({
                    "persona_id": entry.get("persona_id", ""),
                    "sketch": sketch,
                })
            except Exception:
                continue

    return results
