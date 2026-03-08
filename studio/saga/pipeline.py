"""
Five-stage saga pipeline orchestrator.

Stage 1: Persona assignment — select diverse personas from pool
Stage 2: Divergent generation — each persona generates sequel directions
Stage 3: Branching search — expand top directions into spine sketches
Stage 4: Convergent debate — produce full draft spines with critique
Stage 5: Pairwise evaluation — select the best spine

The pipeline degrades gracefully: every configurable parameter works at 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from studio.schema import SagaConfig, CampaignSpine
from studio.validate import validate_spine, ValidationReport
from studio.seeding import (
    generate_master_seed,
    derive_all_seeds,
    build_generation_metadata,
)
from studio.saga.personas import load_persona_pool, select_personas
from studio.saga.diverge import generate_directions
from studio.saga.search import expand_to_sketches
from studio.saga.converge import produce_draft_spines
from studio.saga.select import select_best


@dataclass
class PipelineResult:
    """Result of a complete saga pipeline run."""
    selected_spine: Optional[dict] = None
    validation_report: Optional[dict] = None
    all_candidates: list[dict] = field(default_factory=list)
    directions_generated: int = 0
    sketches_generated: int = 0
    drafts_generated: int = 0
    master_seed: int = 0
    passed_validation: bool = False


def run_saga_pipeline(
    prior_spine: dict,
    *,
    config: Optional[SagaConfig] = None,
    master_seed: Optional[int] = None,
    persona_pool_path: Optional[Path] = None,
    llm_call_fn=None,
) -> PipelineResult:
    """Run the complete five-stage saga pipeline.

    Args:
        prior_spine: The completed campaign's spine dict.
        config: Saga configuration. Defaults to sensible values.
        master_seed: For reproducibility. Generated if None.
        persona_pool_path: Override persona pool path for testing.
        llm_call_fn: Injectable LLM call function for testing.

    Returns:
        PipelineResult with the selected spine and metrics.
    """
    if config is None:
        config = SagaConfig()

    if master_seed is None:
        master_seed = generate_master_seed()

    result = PipelineResult(master_seed=master_seed)

    prior_throughline = prior_spine.get("throughline_question", "")
    prior_era = prior_spine.get("era", "galactic_civil_war")
    total_acts = prior_spine.get("total_acts", 4)

    # ── Stage 1: Persona assignment ──
    try:
        pool = load_persona_pool(persona_pool_path)
    except FileNotFoundError:
        pool = _fallback_personas(config.writer_count)

    personas = select_personas(pool, config.writer_count, seed=master_seed)

    # ── Stage 2: Divergent generation ──
    directions = generate_directions(
        personas,
        prior_throughline,
        prior_era,
        directions_per_persona=2,
        master_seed=master_seed,
        llm_call_fn=llm_call_fn,
    )
    result.directions_generated = len(directions)

    if not directions:
        return result

    # ── Stage 3: Branching search ──
    sketches = expand_to_sketches(
        directions,
        prior_era,
        total_acts=total_acts,
        search_depth=config.search_depth,
        master_seed=master_seed,
        llm_call_fn=llm_call_fn,
    )
    result.sketches_generated = len(sketches)

    if not sketches:
        return result

    # ── Stage 4: Convergent debate ──
    drafts = produce_draft_spines(
        sketches,
        prior_throughline,
        prior_era,
        debate_rounds=config.debate_rounds,
        master_seed=master_seed,
        llm_call_fn=llm_call_fn,
    )
    result.drafts_generated = len(drafts)
    result.all_candidates = drafts

    if not drafts:
        return result

    # ── Stage 5: Selection ──
    top = select_best(drafts, top_k=1)

    if top:
        selected = top[0]
        spine_data = selected.get("spine_data", {})

        # Attach generation metadata
        stage_seeds = derive_all_seeds(master_seed)
        spine_data["generation_metadata"] = build_generation_metadata(
            master_seed=master_seed,
            stage_seeds=stage_seeds,
            model_used="saga_pipeline",
            generation_mode="mode1",
        )

        # Validate
        try:
            spine = CampaignSpine(**spine_data)
            report = validate_spine(spine)
            result.selected_spine = spine_data
            result.validation_report = report.to_dict()
            result.passed_validation = report.passed
        except Exception:
            result.selected_spine = spine_data
            result.passed_validation = False

    return result


def _fallback_personas(count: int) -> list[dict]:
    """Generate minimal fallback personas when pool file is missing."""
    fallback_descriptions = [
        "A retired dockworker who spent thirty years loading cargo at a spaceport",
        "A traveling merchant who trades spices between outer rim systems",
        "A former Republic bureaucrat who processed refugee applications",
        "A cantina owner who has heard every kind of trouble story",
        "A moisture farmer's spouse who dreams of life beyond the homestead",
        "A shipyard mechanic who can tell a vessel's history by its hull welds",
        "A retired teacher from a Core World academy, now living simply",
    ]
    return [
        {
            "id": f"fallback_{i}",
            "description": desc,
            "cluster": f"cluster_{i % 5}",
        }
        for i, desc in enumerate(fallback_descriptions[:count])
    ]
