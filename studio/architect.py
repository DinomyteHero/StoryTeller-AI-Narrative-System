"""
Pre-generation story architecture planning layer.

Produces a StoryArchitecture object from Mode 1 or Mode 2 inputs
BEFORE spine generation begins. This separates "what is this story
about dramatically" from "populate the structural fields," giving
the generation LLM a narrative scaffolding to work from.

Phase: CS-5 (Campaign Studio Narrative Quality)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Callable

from studio.schema import StoryArchitecture
from studio.seeding import derive_stage_seed, STAGE_ARCHITECT


PROMPT_DIR = Path(__file__).parent / "prompts"
ARCHITECT_PROMPT_PATH = PROMPT_DIR / "architect.txt"


def _load_prompt(path: Path) -> str:
    """Load a prompt template from disk."""
    return path.read_text(encoding="utf-8")


def generate_architecture(
    era: str,
    location: str,
    tone: str,
    *,
    throughline_question: str = "",
    campaign_concept: str = "",
    moral_register: str = "",
    master_seed: Optional[int] = None,
    llm_call_fn: Optional[Callable[..., str]] = None,
    max_retries: int = 3,
) -> StoryArchitecture:
    """Generate a StoryArchitecture from campaign inputs.

    This is the first LLM call in the generation pipeline. It produces
    the dramatic scaffolding that the spine generation prompt will
    reference.

    Args:
        era: Star Wars era (e.g., "galactic_civil_war").
        location: Primary campaign location.
        tone: Campaign tone (e.g., "gritty", "hopeful").
        throughline_question: Optional — from Mode 2 ThematicBrief.
        campaign_concept: Optional — from Mode 2 ThematicBrief.
        moral_register: Optional — e.g., "morally gray".
        master_seed: Optional seed for reproducibility.
        llm_call_fn: LLM call function matching the signature of
            generate._call_llm. If None, imports from generate.
        max_retries: Number of attempts before raising.

    Returns:
        A validated StoryArchitecture object.

    Raises:
        RuntimeError: If generation fails after all retries.
    """
    if llm_call_fn is None:
        from studio.generate import _call_llm
        llm_call_fn = _call_llm

    seed = derive_stage_seed(master_seed, STAGE_ARCHITECT) if master_seed else None

    # Build extra context from Mode 2 fields if available
    extra_lines = []
    if throughline_question:
        extra_lines.append(f"Throughline Question: {throughline_question}")
    if campaign_concept:
        extra_lines.append(f"Campaign Concept: {campaign_concept}")
    if moral_register:
        extra_lines.append(f"Moral Register: {moral_register}")
    extra_context = "\n".join(extra_lines) if extra_lines else "(no additional context)"

    template = _load_prompt(ARCHITECT_PROMPT_PATH)
    system_prompt = template.format(
        era=era,
        location=location,
        tone=tone,
        extra_context=extra_context,
    )

    for attempt in range(max_retries):
        try:
            raw = llm_call_fn(
                system_prompt,
                "Design the story architecture now.",
                seed=seed,
                max_tokens=4000,
                temperature=0.7,
            )

            # Strip markdown code fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            arch_data = json.loads(cleaned)
            return StoryArchitecture(**arch_data)

        except (json.JSONDecodeError, Exception) as e:
            if attempt == max_retries - 1:
                raise RuntimeError(
                    f"Architecture generation failed after {max_retries} "
                    f"attempts: {e}"
                )

    raise RuntimeError("Architecture generation failed unexpectedly")


def architecture_to_prompt_block(arch: StoryArchitecture) -> str:
    """Format a StoryArchitecture as a prompt injection block.

    This block is injected into Mode 1/2 generation prompts so the
    spine generation LLM has the dramatic scaffolding to work from.

    Returns:
        A formatted string block ready for prompt injection.
    """
    lines = [
        "## STORY ARCHITECTURE (generate the spine to embody this)",
        "",
        f"Dramatic Premise: {arch.dramatic_premise}",
        f"Central Dramatic Question: {arch.central_dramatic_question}",
        f"Story Promise: {arch.story_promise}",
        f"Protagonist Pressure Type: {arch.protagonist_pressure_type}",
        f"Antagonistic Force: {arch.antagonistic_force}",
        f"Thematic Throughline: {arch.thematic_throughline}",
    ]
    if arch.ending_payoff_sketch:
        lines.append(f"Ending Payoff Sketch: {arch.ending_payoff_sketch}")

    # Milestone beat sheet — act anchors must align with these (CS-6).
    mbs = arch.milestone_beat_sheet
    if mbs:
        lines.extend([
            "",
            "### Milestone beat sheet (align act anchors with these):",
            f"Concept Question: {mbs.concept_question}",
            f"First Plot Point (act {mbs.first_plot_point_act}): {mbs.first_plot_point}",
            f"Midpoint (act {mbs.midpoint_act}): {mbs.midpoint}",
            f"Second Plot Point (act {mbs.second_plot_point_act}): {mbs.second_plot_point}",
        ])
        if mbs.pre_resolution_lull:
            lines.append(f"Pre-Resolution Lull: {mbs.pre_resolution_lull}")
        lines.append(
            "The anchors of these acts ARE the milestones: the first plot "
            "point anchor is the point of no return, the midpoint anchor "
            "turns the protagonist proactive, and the second plot point "
            "anchor delivers the last piece of new information."
        )

    # Planned foreshadowing — generated acts must respect these pairs.
    if arch.foreshadow_registry:
        lines.extend([
            "",
            "### Planned foreshadowing (setup → payoff; acts must honor these):",
        ])
        for link in arch.foreshadow_registry:
            lines.append(
                f"- [{link.id}] Act {link.setup_act} setup: "
                f"{link.setup_description} → Act {link.payoff_act} "
                f"{link.payoff_type or 'payoff'}: {link.payoff_description}"
            )

    # Planned endings — each must connect to a variation point option.
    if arch.ending_paths:
        lines.extend([
            "",
            "### Ending paths (each branch_id must match a variation_point option id):",
        ])
        for ep in arch.ending_paths:
            line = f"- {ep.name} (branch_id: {ep.branch_id}): {ep.synopsis}"
            if ep.thematic_payoff:
                line += f" — thematic payoff: {ep.thematic_payoff}"
            lines.append(line)

    lines.extend([
        "",
        "### Requirements from architecture:",
        "- Each major NPC must have a `thematic_argument` field stating what they argue about the thematic throughline",
        "- Each act must have a `dramatic_function` field (setup/destabilization/launch/midpoint_shift/escalation/confrontation/consequence/resolution)",
        "- Each act must have `beat_roles` (1-3 structural beats consistent with its dramatic_function) and 6-12 `side_content` scene seeds",
        "- Each character variant must have `protagonist_contradiction` and `pressure_revealed_identity` fields",
        "- At least one act anchor in Act 2 or later must directly test the protagonist_contradiction",
        "- The antagonistic force must be reflected in act galactic_context fields, not just stated",
        "- At least one variation_point must test the central dramatic question",
        "- Include the planned foreshadow pairs as the top-level `foreshadow_registry` field",
        "- Every ending path's branch_id must resolve to a variation_point option id you define",
        "- Include at least one antagonistic NPC (disposition_start < 0.4) and at least 2 negative-weight npc_relationships",
        "- Include `story_architecture` in the top-level JSON with all fields from this block",
    ])

    return "\n".join(lines)
