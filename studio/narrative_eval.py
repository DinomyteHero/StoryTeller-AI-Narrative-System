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

    return errors, warnings


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
