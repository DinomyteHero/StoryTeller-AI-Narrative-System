"""
Gate 4 narrative evaluation — LLM-assisted quality checks.

Gate 4a: Narrative coherence (thread continuity, NPC consistency,
         throughline presence, context relevance)
Gate 4b: Dramatic quality (architecture-spine alignment) — only runs
         when story_architecture is populated
Gate 4c: Anti-genericity audit (NPC distinctiveness, anchor specificity,
         escalation authenticity)

Phase: CS-5 (Campaign Studio Narrative Quality)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Callable

from studio.schema import CampaignSpine


PROMPT_DIR = Path(__file__).parent / "prompts"
EVAL_PROMPT_PATH = PROMPT_DIR / "narrative_eval.txt"
SCORE_PROMPT_PATH = PROMPT_DIR / "narrative_score.txt"

# Dimensions grouped by sub-gate
GATE_4A_DIMS = (
    "thread_continuity",
    "npc_trajectory_consistency",
    "throughline_presence",
    "galactic_context_relevance",
)
GATE_4C_DIMS = (
    "npc_distinctiveness",
    "anchor_specificity",
    "escalation_authenticity",
)
GATE_4B_DIMS = (
    "premise_manifestation",
    "cdq_testability",
    "antagonistic_force_presence",
    "npc_thematic_diversity",
    "contradiction_testability",
)


def _load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _build_acts_summary(spine: CampaignSpine) -> str:
    lines = []
    for act in spine.acts:
        df = f" [{act.dramatic_function}]" if act.dramatic_function else ""
        lines.append(
            f"Act {act.number}: {act.name} (tension: {act.tension}{df})\n"
            f"  Anchor: {act.anchor}\n"
            f"  Opening: {act.opening_situation[:100]}\n"
            f"  Context: {act.galactic_context[:100]}\n"
            f"  Threads: {', '.join(act.open_threads) if act.open_threads else '(none)'}"
        )
    return "\n\n".join(lines)


def _build_npc_summary(spine: CampaignSpine) -> str:
    lines = []
    for npc in spine.npc_roster:
        ta = f"\n  Thematic argument: {npc.thematic_argument}" if npc.thematic_argument else ""
        per_act = "; ".join(
            f"Act {s.act}: {s.role_in_act} (disp: {s.disposition_expected})"
            for s in npc.per_act_state
        )
        lines.append(
            f"{npc.name} — {npc.role} (disp: {npc.disposition_start})\n"
            f"  Motivation: {npc.motivation}\n"
            f"  Voice: {npc.voice_notes[:80]}\n"
            f"  Envelope: {'; '.join(npc.behavioral_envelope[:2])}\n"
            f"  Trajectory: {per_act}{ta}"
        )
    return "\n\n".join(lines)


def _build_threads_summary(spine: CampaignSpine) -> str:
    all_threads = set()
    thread_acts = {}
    for act in spine.acts:
        for t in act.open_threads:
            all_threads.add(t)
            thread_acts.setdefault(t, []).append(act.number)

    if not all_threads:
        return "(no explicit threads)"

    lines = []
    for t in sorted(all_threads):
        acts = thread_acts[t]
        lines.append(f"- {t} (appears in acts: {', '.join(str(a) for a in acts)})")
    return "\n".join(lines)


def evaluate_narrative(
    spine: CampaignSpine,
    *,
    llm_call_fn: Optional[Callable[..., str]] = None,
) -> dict:
    """Run the full Gate 4 narrative evaluation.

    Returns a dict mapping dimension names to {"pass": bool, "detail": str}.
    Dimensions from Gates 4a and 4c always run. Gate 4b dimensions only
    run when story_architecture is populated on the spine.

    Args:
        spine: A parsed CampaignSpine model.
        llm_call_fn: LLM call function. If None, imports from generate.

    Returns:
        Dict of dimension → {"pass": bool, "detail": str}.

    Raises:
        RuntimeError: If the LLM call fails or returns unparseable JSON.
    """
    if llm_call_fn is None:
        from studio.generate import _call_llm
        llm_call_fn = _call_llm

    has_architecture = spine.story_architecture is not None

    # Build prompt context
    acts_summary = _build_acts_summary(spine)
    npc_summary = _build_npc_summary(spine)
    threads_summary = _build_threads_summary(spine)

    # Architecture-specific prompt sections
    if has_architecture:
        arch = spine.story_architecture
        architecture_section = (
            f"### Story Architecture:\n"
            f"Dramatic Premise: {arch.dramatic_premise}\n"
            f"Central Dramatic Question: {arch.central_dramatic_question}\n"
            f"Protagonist Pressure Type: {arch.protagonist_pressure_type}\n"
            f"Antagonistic Force: {arch.antagonistic_force}\n"
            f"Thematic Throughline: {arch.thematic_throughline}"
        )
        architecture_dimensions = (
            '8. **premise_manifestation** — Does the dramatic premise create observable pressure in the launch and confrontation acts?\n\n'
            '9. **cdq_testability** — Is the central dramatic question testable through variation points or anchor beats?\n\n'
            '10. **antagonistic_force_presence** — Is the antagonistic force reflected in act contexts or NPC behaviors, not just stated?\n\n'
            '11. **npc_thematic_diversity** — Do at least 2 NPCs embody different answers to the thematic throughline?\n\n'
            '12. **contradiction_testability** — Does at least one act test the protagonist contradiction?'
        )
        architecture_output_fields = (
            ',\n  "premise_manifestation": {"pass": true/false, "detail": "..."},\n'
            '  "cdq_testability": {"pass": true/false, "detail": "..."},\n'
            '  "antagonistic_force_presence": {"pass": true/false, "detail": "..."},\n'
            '  "npc_thematic_diversity": {"pass": true/false, "detail": "..."},\n'
            '  "contradiction_testability": {"pass": true/false, "detail": "..."}'
        )
    else:
        architecture_section = "(No story architecture provided — Gate 4b dimensions skipped)"
        architecture_dimensions = ""
        architecture_output_fields = ""

    template = _load_prompt(EVAL_PROMPT_PATH)
    system_prompt = template.format(
        name=spine.name,
        era=spine.era,
        throughline_question=spine.throughline_question,
        total_acts=spine.total_acts,
        acts_summary=acts_summary,
        npc_summary=npc_summary,
        threads_summary=threads_summary,
        architecture_section=architecture_section,
        architecture_dimensions=architecture_dimensions,
        architecture_output_fields=architecture_output_fields,
    )

    raw = llm_call_fn(
        system_prompt,
        "Evaluate the campaign spine now.",
        max_tokens=3000,
        temperature=0.3,  # Low temperature for consistent evaluation
    )

    # Parse response
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        results = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Gate 4 evaluation returned invalid JSON: {e}")

    # Validate expected dimensions are present
    expected = set(GATE_4A_DIMS) | set(GATE_4C_DIMS)
    if has_architecture:
        expected |= set(GATE_4B_DIMS)

    for dim in expected:
        if dim not in results:
            results[dim] = {"pass": True, "detail": "Dimension not evaluated by LLM"}

    return results


def gate4_check(
    spine: CampaignSpine,
    *,
    llm_call_fn: Optional[Callable[..., str]] = None,
) -> tuple[list, list]:
    """Run Gate 4 and return (errors, warnings).

    Gate 4a and 4c failures are warnings (non-blocking for now).
    Gate 4b failures are warnings (non-blocking, advisory).

    Multiple dimension failures in the same sub-gate escalate to an error
    only if 3+ dimensions in Gates 4a/4c fail simultaneously.

    Returns:
        Tuple of (error_list, warning_list) where each item is a dict
        with keys: gate, code, message, path.
    """
    results = evaluate_narrative(spine, llm_call_fn=llm_call_fn)

    errors = []
    warnings = []

    # Count failures per sub-gate
    gate4a_failures = []
    gate4c_failures = []
    gate4b_failures = []

    for dim, result in results.items():
        if not isinstance(result, dict) or "pass" not in result:
            continue

        if not result["pass"]:
            detail = result.get("detail", "No detail provided")
            entry = {
                "gate": 4,
                "code": f"narrative_{dim}",
                "message": f"{dim}: {detail}",
                "path": "",
            }

            if dim in GATE_4A_DIMS:
                gate4a_failures.append(entry)
            elif dim in GATE_4C_DIMS:
                gate4c_failures.append(entry)
            elif dim in GATE_4B_DIMS:
                gate4b_failures.append(entry)

    # All individual failures are warnings
    for entry in gate4a_failures + gate4c_failures + gate4b_failures:
        warnings.append(entry)

    # 3+ failures in coherence or anti-genericity escalate to error
    if len(gate4a_failures) >= 3:
        errors.append({
            "gate": 4,
            "code": "narrative_coherence_failure",
            "message": (
                f"Narrative coherence: {len(gate4a_failures)} of "
                f"{len(GATE_4A_DIMS)} dimensions failed. "
                "The campaign may have significant narrative inconsistencies."
            ),
            "path": "",
        })

    if len(gate4c_failures) >= 3:
        errors.append({
            "gate": 4,
            "code": "narrative_genericity_failure",
            "message": (
                f"Anti-genericity: {len(gate4c_failures)} of "
                f"{len(GATE_4C_DIMS)} dimensions failed. "
                "The campaign may be dramatically flat or generic."
            ),
            "path": "",
        })

    # ── CS-6 deterministic structural checks ───────────────────────────
    cs6_warnings = _check_cs6_structural(spine)
    warnings.extend(cs6_warnings)

    return errors, warnings


def _check_cs6_structural(spine: CampaignSpine) -> list[dict]:
    """CS-6 Story Engineering deterministic checks.

    These are structural checks that don't require an LLM — they
    validate schema-level properties of the spine.
    """
    warnings = []
    acts = spine.acts
    total_acts = spine.total_acts
    has_architecture = spine.story_architecture is not None

    # ── Phase 2: Pinch point coverage ────────────────────────────────
    # Only check when spine has opted into CS-6 features (has architecture
    # or any act has CS-6 fields populated). Legacy spines skip this.
    any_pinch_points = any(act.pinch_point for act in acts)
    any_protagonist_modes = any(act.protagonist_mode for act in acts)
    # Only check pinch point coverage when at least one act uses CS-6 features
    if any_pinch_points or any_protagonist_modes:
        setup_functions = {"setup", "destabilization"}
        resolution_functions = {"resolution", "consequence"}
        for act in acts:
            if act.number == 1:
                continue  # First act often setup
            if act.dramatic_function in setup_functions:
                continue
            if act.dramatic_function in resolution_functions:
                continue
            if not act.pinch_point:
                warnings.append({
                    "gate": 4,
                    "code": "cs6_pinch_point_missing",
                    "message": (
                        f"Act {act.number} ({act.name}) has no pinch point. "
                        f"Mid-campaign acts should have a direct antagonist pressure beat."
                    ),
                    "path": f"acts[{act.number - 1}].pinch_point",
                })

    # ── Phase 3: Milestone beat sheet checks ─────────────────────────
    if has_architecture and hasattr(spine.story_architecture, "milestone_beat_sheet"):
        mbs = spine.story_architecture.milestone_beat_sheet
        if mbs:
            # Milestone sequence
            if mbs.first_plot_point_act >= mbs.midpoint_act:
                warnings.append({
                    "gate": 4,
                    "code": "cs6_milestone_sequence",
                    "message": (
                        f"First Plot Point (act {mbs.first_plot_point_act}) must come "
                        f"before Midpoint (act {mbs.midpoint_act})."
                    ),
                    "path": "story_architecture.milestone_beat_sheet",
                })
            if mbs.midpoint_act >= mbs.second_plot_point_act:
                warnings.append({
                    "gate": 4,
                    "code": "cs6_milestone_sequence",
                    "message": (
                        f"Midpoint (act {mbs.midpoint_act}) must come before "
                        f"Second Plot Point (act {mbs.second_plot_point_act})."
                    ),
                    "path": "story_architecture.milestone_beat_sheet",
                })

            # Milestone placement
            fpp_pct = mbs.first_plot_point_act / total_acts
            if fpp_pct < 0.15 or fpp_pct > 0.40:
                warnings.append({
                    "gate": 4,
                    "code": "cs6_milestone_placement",
                    "message": (
                        f"First Plot Point at act {mbs.first_plot_point_act} of "
                        f"{total_acts} ({fpp_pct:.0%}) — should be 20-35% of acts."
                    ),
                    "path": "story_architecture.milestone_beat_sheet.first_plot_point_act",
                })
            mid_pct = mbs.midpoint_act / total_acts
            if mid_pct < 0.35 or mid_pct > 0.65:
                warnings.append({
                    "gate": 4,
                    "code": "cs6_milestone_placement",
                    "message": (
                        f"Midpoint at act {mbs.midpoint_act} of {total_acts} "
                        f"({mid_pct:.0%}) — should be 40-60% of acts."
                    ),
                    "path": "story_architecture.milestone_beat_sheet.midpoint_act",
                })
            spp_pct = mbs.second_plot_point_act / total_acts
            if spp_pct < 0.60 or spp_pct > 0.85:
                warnings.append({
                    "gate": 4,
                    "code": "cs6_milestone_placement",
                    "message": (
                        f"Second Plot Point at act {mbs.second_plot_point_act} of "
                        f"{total_acts} ({spp_pct:.0%}) — should be 65-80% of acts."
                    ),
                    "path": "story_architecture.milestone_beat_sheet.second_plot_point_act",
                })

            # Concept question format
            if mbs.concept_question:
                cq = mbs.concept_question.strip()
                if not cq.lower().startswith("what if"):
                    warnings.append({
                        "gate": 4,
                        "code": "cs6_concept_question_format",
                        "message": (
                            f"Concept question should start with 'What if': "
                            f"'{cq[:50]}...'"
                        ),
                        "path": "story_architecture.milestone_beat_sheet.concept_question",
                    })
                if not cq.endswith("?"):
                    warnings.append({
                        "gate": 4,
                        "code": "cs6_concept_question_format",
                        "message": "Concept question must end with '?'",
                        "path": "story_architecture.milestone_beat_sheet.concept_question",
                    })

    # ── Phase 3: Protagonist mode progression ────────────────────────
    PROTAGONIST_MODE_ORDER = {"orphan": 0, "wanderer": 1, "warrior": 2, "martyr": 3}
    last_mode_rank = -1
    for act in acts:
        if act.protagonist_mode:
            rank = PROTAGONIST_MODE_ORDER.get(act.protagonist_mode, -1)
            if rank < last_mode_rank:
                warnings.append({
                    "gate": 4,
                    "code": "cs6_protagonist_mode_regression",
                    "message": (
                        f"Act {act.number} protagonist mode '{act.protagonist_mode}' "
                        f"regresses from a later mode. Modes must progress: "
                        f"orphan → wanderer → warrior → martyr."
                    ),
                    "path": f"acts[{act.number - 1}].protagonist_mode",
                })
            if rank >= 0:
                last_mode_rank = rank

    # ── Phase 4: NPC pressure role diversity ─────────────────────────
    pressure_roles = [
        npc.pressure_role for npc in spine.npc_roster
        if hasattr(npc, "pressure_role") and npc.pressure_role
    ]
    if len(pressure_roles) >= 2:
        unique_roles = set(pressure_roles)
        if len(unique_roles) == 1:
            warnings.append({
                "gate": 4,
                "code": "cs6_pressure_role_monotonic",
                "message": (
                    f"All {len(pressure_roles)} NPCs with pressure roles are "
                    f"'{pressure_roles[0]}'. Vary dramatic pressure types."
                ),
                "path": "npc_roster[*].pressure_role",
            })

    # ── Phase 5: Foreshadow registry checks ──────────────────────────
    if hasattr(spine, "foreshadow_registry") and spine.foreshadow_registry:
        for link in spine.foreshadow_registry:
            if link.setup_act >= link.payoff_act:
                warnings.append({
                    "gate": 4,
                    "code": "cs6_foreshadow_order",
                    "message": (
                        f"Foreshadow '{link.id}': setup_act ({link.setup_act}) must "
                        f"be before payoff_act ({link.payoff_act})."
                    ),
                    "path": f"foreshadow_registry[{link.id}]",
                })

        # Check for payoff coverage in final third
        final_third_start = max(1, int(total_acts * 0.67))
        has_late_payoff = any(
            link.payoff_act >= final_third_start
            for link in spine.foreshadow_registry
        )
        if not has_late_payoff:
            warnings.append({
                "gate": 4,
                "code": "cs6_foreshadow_no_late_payoff",
                "message": (
                    "No foreshadow links pay off in the final third of the "
                    "campaign. Climactic resolutions may feel arbitrary."
                ),
                "path": "foreshadow_registry",
            })

    return warnings


def score_narrative_quality(
    spine_data: dict,
    *,
    llm_call_fn: Optional[Callable[..., str]] = None,
) -> float:
    """Score a spine's narrative quality for Stage 5 selection.

    Returns a float 0.0–1.0 representing narrative quality, based on
    a 5-dimension rubric scored 1–5 each by an LLM.

    Args:
        spine_data: Raw spine dict (not necessarily validated).
        llm_call_fn: LLM call function. If None, imports from generate.

    Returns:
        Normalized narrative quality score (0.0–1.0).
    """
    if llm_call_fn is None:
        from studio.generate import _call_llm
        llm_call_fn = _call_llm

    # Build summaries from raw dict
    name = spine_data.get("name", "Untitled")
    era = spine_data.get("era", "unknown")
    throughline = spine_data.get("throughline_question", "")
    total_acts = spine_data.get("total_acts", 0)

    acts = spine_data.get("acts", [])
    acts_lines = []
    for act in acts:
        df = f" [{act.get('dramatic_function', '')}]" if act.get('dramatic_function') else ""
        acts_lines.append(
            f"Act {act.get('number', '?')}: {act.get('name', '?')} "
            f"(tension: {act.get('tension', '?')}{df})\n"
            f"  Anchor: {act.get('anchor', '?')}\n"
            f"  Opening: {str(act.get('opening_situation', ''))[:100]}"
        )
    acts_summary = "\n\n".join(acts_lines) if acts_lines else "(no acts)"

    npcs = spine_data.get("npc_roster", [])
    npc_lines = []
    for npc in npcs:
        npc_lines.append(
            f"{npc.get('name', '?')} — {npc.get('role', '?')}\n"
            f"  Motivation: {npc.get('motivation', '?')}\n"
            f"  Voice: {str(npc.get('voice_notes', ''))[:80]}"
        )
    npc_summary = "\n\n".join(npc_lines) if npc_lines else "(no NPCs)"

    template = _load_prompt(SCORE_PROMPT_PATH)
    system_prompt = template.format(
        name=name,
        era=era,
        throughline_question=throughline,
        total_acts=total_acts,
        acts_summary=acts_summary,
        npc_summary=npc_summary,
    )

    raw = llm_call_fn(
        system_prompt,
        "Score the campaign spine now.",
        max_tokens=500,
        temperature=0.3,
    )

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        scores = json.loads(cleaned)
    except json.JSONDecodeError:
        return 0.5  # Fallback to neutral if parse fails

    dims = [
        "premise_strength",
        "npc_thematic_diversity",
        "dramatic_progression",
        "throughline_testability",
        "anti_genericity",
    ]

    total = 0.0
    count = 0
    for dim in dims:
        val = scores.get(dim, 3)
        if isinstance(val, (int, float)) and 1 <= val <= 5:
            total += val
            count += 1

    if count == 0:
        return 0.5

    # Normalize from 1-5 scale to 0.0-1.0
    return round((total / count - 1) / 4, 3)
