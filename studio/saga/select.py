"""
Saga Stage 5 — Pairwise evaluation and selection.

Evaluates draft spines on three axes:
1. Structural quality — mechanical soundness
2. Novelty — how different from the prior campaign
3. Diversity vs prior — how different from other candidates

Uses pairwise comparison: each pair of spines is compared head-to-head.
The winner is the spine with the highest composite score.
"""

from __future__ import annotations

import json
from typing import Optional

from studio.schema import EvaluationResult, CampaignSpine
from studio.validate import validate_spine


def evaluate_spine_pair(
    spine_a: dict,
    spine_b: dict,
    *,
    llm_call_fn=None,
    evaluator_backend: str = "cloud",
    use_narrative_scoring: bool = False,
) -> dict:
    """Compare two spine drafts head-to-head.

    Args:
        spine_a: First draft spine dict.
        spine_b: Second draft spine dict.
        llm_call_fn: Injectable LLM call function.
        evaluator_backend: "cloud", "local", or "ensemble".
        use_narrative_scoring: If True, include LLM narrative scoring.

    Returns:
        Dict with 'winner' ('a' or 'b' or 'tie'), 'scores_a', 'scores_b',
        'reasoning'.
    """
    # Score each spine independently
    scores_a = _score_spine(
        spine_a,
        use_narrative_scoring=use_narrative_scoring,
        llm_call_fn=llm_call_fn,
    )
    scores_b = _score_spine(
        spine_b,
        use_narrative_scoring=use_narrative_scoring,
        llm_call_fn=llm_call_fn,
    )

    # Determine winner
    if scores_a["composite"] > scores_b["composite"]:
        winner = "a"
    elif scores_b["composite"] > scores_a["composite"]:
        winner = "b"
    else:
        winner = "tie"

    return {
        "winner": winner,
        "scores_a": scores_a,
        "scores_b": scores_b,
        "reasoning": _explain_comparison(scores_a, scores_b, winner),
    }


def select_best(
    drafts: list[dict],
    top_k: int = 1,
    *,
    use_narrative_scoring: bool = False,
    llm_call_fn=None,
) -> list[dict]:
    """Select the best spine(s) from a set of drafts.

    Uses structural scoring (pure Python) to rank candidates. When
    use_narrative_scoring is True, adds LLM-based narrative quality
    assessment and rebalances weights.

    Args:
        drafts: List of dicts with 'spine_data' keys.
        top_k: How many to select.
        use_narrative_scoring: If True, include LLM narrative scoring.
        llm_call_fn: Injectable LLM call function for narrative scoring.

    Returns:
        List of the top-k drafts, sorted by composite score.
    """
    scored = []
    for draft in drafts:
        spine_data = draft.get("spine_data", {})
        scores = _score_spine(
            spine_data,
            use_narrative_scoring=use_narrative_scoring,
            llm_call_fn=llm_call_fn,
        )
        scored.append({
            **draft,
            "scores": scores,
        })

    # Sort by composite score descending
    scored.sort(key=lambda x: x["scores"]["composite"], reverse=True)
    return scored[:top_k]


def _score_spine(
    spine_data: dict,
    *,
    use_narrative_scoring: bool = False,
    llm_call_fn=None,
) -> dict:
    """Score a spine on structural quality, novelty, diversity, and narrative.

    When use_narrative_scoring is False (default), uses the original
    pure Python scoring with weights: structural 50%, novelty 25%,
    diversity 25%.

    When use_narrative_scoring is True, adds LLM-assessed narrative
    quality and rebalances: structural 35%, novelty 15%, diversity 15%,
    narrative 35%.

    Returns:
        Dict with scoring dimensions and composite (all 0.0–1.0).
    """
    structural = _score_structural(spine_data)
    novelty = _score_novelty(spine_data)
    diversity = _score_diversity(spine_data)

    if use_narrative_scoring:
        from studio.narrative_eval import score_narrative_quality
        try:
            narrative = score_narrative_quality(
                spine_data, llm_call_fn=llm_call_fn,
            )
        except Exception:
            narrative = 0.5  # Fallback if LLM scoring fails

        composite = (
            structural * 0.35
            + novelty * 0.15
            + diversity * 0.15
            + narrative * 0.35
        )
        return {
            "structural_quality": round(structural, 3),
            "novelty": round(novelty, 3),
            "diversity_vs_prior": round(diversity, 3),
            "narrative_quality": round(narrative, 3),
            "composite": round(composite, 3),
        }

    composite = structural * 0.5 + novelty * 0.25 + diversity * 0.25

    return {
        "structural_quality": round(structural, 3),
        "novelty": round(novelty, 3),
        "diversity_vs_prior": round(diversity, 3),
        "composite": round(composite, 3),
    }


def _score_structural(spine_data: dict) -> float:
    """Score structural completeness (0.0–1.0)."""
    score = 0.0
    checks = 0

    # Has required top-level fields
    for field in ["name", "era", "total_acts", "throughline_question", "acts", "npc_roster", "allegiances"]:
        checks += 1
        if spine_data.get(field):
            score += 1

    # Acts exist and match total_acts
    acts = spine_data.get("acts", [])
    total = spine_data.get("total_acts", 0)
    checks += 1
    if acts and len(acts) == total:
        score += 1

    # NPCs have voice notes and behavioral envelopes
    npcs = spine_data.get("npc_roster", [])
    for npc in npcs:
        checks += 1
        if npc.get("voice_notes") and npc.get("behavioral_envelope"):
            score += 1

    # Allegiances have character variants
    allegiances = spine_data.get("allegiances", [])
    checks += 1
    if len(allegiances) >= 2:
        score += 1

    for alleg in allegiances:
        checks += 1
        if alleg.get("character_variants"):
            score += 1

    # Throughline ends with ?
    checks += 1
    tq = spine_data.get("throughline_question", "")
    if tq.strip().endswith("?"):
        score += 1

    # Variation points exist
    checks += 1
    if spine_data.get("variation_points"):
        score += 1

    # Try Pydantic validation
    checks += 1
    try:
        spine = CampaignSpine(**spine_data)
        report = validate_spine(spine)
        if report.passed:
            score += 1
    except Exception:
        pass

    return score / checks if checks > 0 else 0.0


def _score_novelty(spine_data: dict) -> float:
    """Score novelty potential based on content variety (0.0–1.0)."""
    score = 0.0
    checks = 0

    # NPC count (more NPCs = more narrative potential)
    npcs = spine_data.get("npc_roster", [])
    checks += 1
    if len(npcs) >= 3:
        score += 1
    elif len(npcs) >= 2:
        score += 0.5

    # Variation points (more = more replayability)
    vps = spine_data.get("variation_points", [])
    checks += 1
    if len(vps) >= 2:
        score += 1
    elif len(vps) >= 1:
        score += 0.5

    # NPC disposition variety
    checks += 1
    dispositions = [npc.get("disposition_start", 0.5) for npc in npcs]
    if dispositions:
        disp_range = max(dispositions) - min(dispositions)
        score += min(disp_range / 0.5, 1.0)

    # Act tension variety
    acts = spine_data.get("acts", [])
    checks += 1
    tensions = set(act.get("tension", "") for act in acts)
    if len(tensions) >= 3:
        score += 1
    elif len(tensions) >= 2:
        score += 0.5

    return score / checks if checks > 0 else 0.0


def _score_diversity(spine_data: dict) -> float:
    """Score diversity potential (0.0–1.0)."""
    score = 0.0
    checks = 0

    # Multiple allegiances with distinct variants
    allegiances = spine_data.get("allegiances", [])
    checks += 1
    if len(allegiances) >= 2:
        score += 0.5
        # Check if variants have different careers/species
        all_careers = set()
        all_species = set()
        for alleg in allegiances:
            for var in alleg.get("character_variants", []):
                all_careers.add(var.get("career", ""))
                all_species.add(var.get("species", ""))
        if len(all_careers) >= 2:
            score += 0.25
        if len(all_species) >= 2:
            score += 0.25

    # NPC relationship variety
    npcs = spine_data.get("npc_roster", [])
    checks += 1
    total_rels = sum(len(npc.get("npc_relationships", [])) for npc in npcs)
    if total_rels >= 3:
        score += 1
    elif total_rels >= 1:
        score += 0.5

    return score / checks if checks > 0 else 0.0


def _explain_comparison(scores_a: dict, scores_b: dict, winner: str) -> str:
    """Generate a brief explanation of why one spine won."""
    parts = []
    for axis in ["structural_quality", "novelty", "diversity_vs_prior"]:
        a_val = scores_a.get(axis, 0)
        b_val = scores_b.get(axis, 0)
        if a_val > b_val:
            parts.append(f"Spine A scores higher on {axis} ({a_val:.2f} vs {b_val:.2f})")
        elif b_val > a_val:
            parts.append(f"Spine B scores higher on {axis} ({b_val:.2f} vs {a_val:.2f})")

    if winner == "tie":
        return "Both spines scored equally. " + " ".join(parts)
    return f"Spine {winner.upper()} wins. " + " ".join(parts)
