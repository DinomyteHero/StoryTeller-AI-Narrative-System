"""
Saga Stage 4 — Convergent debate and coherence.

Takes spine sketches and the prior campaign context, then produces
full draft spines through iterative critique and refinement.

The prior campaign enters HERE (Stage 4) — not at Stage 2. This
prevents the prior campaign from constraining divergent ideation.
"""

from __future__ import annotations

import json
from typing import Optional

from studio.seeding import derive_stage_seed, STAGE_SAGA_DEBATE


CONVERGE_SYSTEM_PROMPT = """You are a campaign architect refining a spine sketch into a complete campaign spine.

## SPINE SKETCH
{sketch_json}

## PRIOR CAMPAIGN CONTEXT (for convergence, not imitation)
Prior throughline: {prior_throughline}
Prior era: {prior_era}

The sequel must be STRUCTURALLY DISTINCT from the prior campaign. The prior
context is provided so you can ensure the sequel makes narrative sense as a
follow-up, NOT so you can repeat the same story.

## TASK
Expand this sketch into a complete campaign spine JSON matching the CampaignSpine
schema. Include all required fields:
- name, era, total_acts, throughline_question (must end with ?)
- allegiances (2, each with character variants)
- acts (with tension, opening_situation, galactic_context, anchor, xp_base, etc.)
- npc_roster (with disposition_trajectory, per_act_state, voice_notes, behavioral_envelope)
- variation_points (at least 1)

{critique_feedback}

Return ONLY valid JSON. No markdown, no explanation."""


def produce_draft_spines(
    sketches: list[dict],
    prior_throughline: str,
    prior_era: str,
    *,
    debate_rounds: int = 1,
    master_seed: Optional[int] = None,
    llm_call_fn=None,
) -> list[dict]:
    """Produce full draft spines from sketches via debate/refinement.

    Args:
        sketches: Output from Stage 3.
        prior_throughline: Prior campaign's throughline question.
        prior_era: Prior campaign's era.
        debate_rounds: Number of critique-refine iterations.
        master_seed: For seed derivation.
        llm_call_fn: Injectable LLM call function.

    Returns:
        List of draft spine dicts (CampaignSpine-compatible).
    """
    if llm_call_fn is None:
        from studio.generate import _call_llm
        llm_call_fn = _call_llm

    base_seed = derive_stage_seed(master_seed, STAGE_SAGA_DEBATE) if master_seed else None

    drafts = []
    for i, entry in enumerate(sketches):
        sketch = entry.get("sketch", {})
        critique_feedback = ""

        for round_num in range(debate_rounds):
            seed = (base_seed + i * 100 + round_num) if base_seed else None

            system_prompt = CONVERGE_SYSTEM_PROMPT.format(
                sketch_json=json.dumps(sketch, indent=2),
                prior_throughline=prior_throughline,
                prior_era=prior_era,
                critique_feedback=(
                    f"\n## CRITIQUE FROM PRIOR ROUND\n{critique_feedback}"
                    if critique_feedback else ""
                ),
            )

            try:
                raw = llm_call_fn(
                    system_prompt,
                    f"Generate the complete campaign spine (round {round_num + 1}).",
                    seed=seed,
                    max_tokens=8000,
                    temperature=0.7,
                )
                cleaned = raw.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    cleaned = "\n".join(lines)

                draft = json.loads(cleaned)

                # Run a quick critique for next round
                if round_num < debate_rounds - 1:
                    critique_feedback = _generate_critique(
                        draft, llm_call_fn, seed=(seed + 50 if seed else None)
                    )

                # Only keep the final round's draft
                if round_num == debate_rounds - 1:
                    drafts.append({
                        "persona_id": entry.get("persona_id", ""),
                        "spine_data": draft,
                    })

            except Exception:
                # If final round fails, try to salvage
                if round_num == debate_rounds - 1:
                    continue

    return drafts


def _generate_critique(draft: dict, llm_call_fn, seed=None) -> str:
    """Generate a brief critique of a draft spine for the next round."""
    try:
        critique = llm_call_fn(
            "You are a campaign critique agent. Identify 2-3 specific structural "
            "issues in this campaign spine draft. Focus on: NPC motivation depth, "
            "act pacing, allegiance diversity, and throughline coherence. Be specific.",
            f"Critique this spine:\n{json.dumps(draft, indent=2)[:3000]}",
            seed=seed,
            max_tokens=500,
            temperature=0.5,
        )
        return critique
    except Exception:
        return ""
