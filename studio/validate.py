"""
Campaign spine validation suite — four gates.

Gate 1: Schema contract validation (pure Python)
Gate 2: NPC coherence validation (pure Python)
Gate 3: Relationship network validation (pure Python, optional NetworkX)
Gate 4: Narrative consistency audit (LLM-assisted, optional)
        Difficulty calibration runs as pure Python even when LLM checks skipped.

A spine must pass all four gates before the Game Engine can consume it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from studio.schema import CampaignSpine
from studio.difficulty import compute_difficulty_curve, SpineDifficultyCurve


# ── Validation result types ───────────────────────────────────────────


@dataclass
class ValidationError:
    """A single validation failure with actionable context."""
    gate: int
    code: str
    message: str
    path: str = ""  # e.g. "acts[2].xp_base" or "npc_roster[0].name"


@dataclass
class ValidationWarning:
    """A non-blocking concern flagged for author review."""
    gate: int
    code: str
    message: str
    path: str = ""


@dataclass
class ValidationReport:
    """Complete validation output for a spine."""
    passed: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationWarning] = field(default_factory=list)
    gates_passed: list[int] = field(default_factory=list)
    difficulty_curve: Optional[SpineDifficultyCurve] = None

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "errors": [
                {"gate": e.gate, "code": e.code, "message": e.message, "path": e.path}
                for e in self.errors
            ],
            "warnings": [
                {"gate": w.gate, "code": w.code, "message": w.message, "path": w.path}
                for w in self.warnings
            ],
            "gates_passed": self.gates_passed,
            "difficulty_curve": self.difficulty_curve.to_dict() if self.difficulty_curve else None,
        }


# ── Public API ────────────────────────────────────────────────────────


def validate_spine(
    spine: CampaignSpine,
    *,
    run_gate4_llm: bool = False,
) -> ValidationReport:
    """Run all validation gates on a campaign spine.

    Args:
        spine: A parsed CampaignSpine model.
        run_gate4_llm: If True, run Gate 4 LLM narrative checks.
            Defaults to False (difficulty calibration still runs).

    Returns:
        ValidationReport with all errors, warnings, and gate results.
    """
    report = ValidationReport(passed=True)

    # Gate 1 — Schema contract validation + integration layer (3.33)
    _gate1_schema_contract(spine, report)
    _gate1_integration_layer(spine, report)
    if report.errors:
        report.passed = False
        return report
    report.gates_passed.append(1)

    # Gate 2 — NPC coherence validation
    _gate2_npc_coherence(spine, report)
    if any(e.gate == 2 for e in report.errors):
        report.passed = False
        return report
    report.gates_passed.append(2)

    # Gate 3 — Relationship network + allegiance diversity (3.34)
    _gate3_relationship_network(spine, report)
    _gate3_allegiance_diversity(spine, report)
    if any(e.gate == 3 for e in report.errors):
        report.passed = False
        return report
    report.gates_passed.append(3)

    # Gate 4 — Difficulty calibration (always) + LLM checks (optional)
    difficulty_curve = compute_difficulty_curve(spine)
    report.difficulty_curve = difficulty_curve

    for warning in difficulty_curve.calibration_warnings:
        report.warnings.append(ValidationWarning(
            gate=4, code="difficulty_warning", message=warning,
        ))

    if run_gate4_llm:
        _gate4_narrative_consistency(spine, report)
        if any(e.gate == 4 for e in report.errors):
            report.passed = False
            return report

    report.gates_passed.append(4)
    return report


# ── Gate 1: Schema Contract Validation ────────────────────────────────


def _gate1_schema_contract(spine: CampaignSpine, report: ValidationReport) -> None:
    """Pure Python structural checks beyond what Pydantic enforces."""

    # Act count matches total_acts
    if len(spine.acts) != spine.total_acts:
        report.errors.append(ValidationError(
            gate=1, code="act_count_mismatch",
            message=f"total_acts is {spine.total_acts} but {len(spine.acts)} acts provided",
            path="acts",
        ))

    # Throughline question ends with "?"
    if not spine.throughline_question.strip().endswith("?"):
        report.errors.append(ValidationError(
            gate=1, code="throughline_no_question_mark",
            message="throughline_question must end with '?'",
            path="throughline_question",
        ))

    # Build NPC name set for cross-reference checks
    npc_names = {npc.name for npc in spine.npc_roster}

    # Allegiances contain at least one character variant (Pydantic enforces,
    # but we add context)
    for i, allegiance in enumerate(spine.allegiances):
        # Variant allegiance fields match containing allegiance id
        for j, variant in enumerate(allegiance.character_variants):
            if variant.allegiance != allegiance.id:
                report.errors.append(ValidationError(
                    gate=1, code="variant_allegiance_mismatch",
                    message=(
                        f"Variant '{variant.id}' has allegiance '{variant.allegiance}' "
                        f"but is inside allegiance '{allegiance.id}'"
                    ),
                    path=f"allegiances[{i}].character_variants[{j}].allegiance",
                ))

    # Character variants have matching prologue scenes
    if spine.prologue_scenes:
        prologue_variant_ids = {ps.variant_id for ps in spine.prologue_scenes}
        all_variant_ids = set()
        for allegiance in spine.allegiances:
            for variant in allegiance.character_variants:
                all_variant_ids.add(variant.id)

        for vid in all_variant_ids:
            if vid not in prologue_variant_ids:
                report.warnings.append(ValidationWarning(
                    gate=1, code="missing_prologue_scenes",
                    message=f"Variant '{vid}' has no matching prologue scene set",
                    path="prologue_scenes",
                ))

    # Variation point NPC references resolve to roster
    for i, vp in enumerate(spine.variation_points):
        for j, opt in enumerate(vp.options):
            for npc_ref in opt.npc_state_changes:
                if npc_ref not in npc_names:
                    report.errors.append(ValidationError(
                        gate=1, code="variation_npc_not_in_roster",
                        message=f"Variation '{vp.id}' option '{opt.id}' references NPC '{npc_ref}' not in roster",
                        path=f"variation_points[{i}].options[{j}].npc_state_changes",
                    ))

    # Force-sensitive variants should have starting_force_powers
    for i, allegiance in enumerate(spine.allegiances):
        for j, variant in enumerate(allegiance.character_variants):
            if variant.force_sensitive and not variant.starting_force_powers:
                report.warnings.append(ValidationWarning(
                    gate=1, code="force_sensitive_no_powers",
                    message=f"Variant '{variant.id}' is force_sensitive but has no starting_force_powers",
                    path=f"allegiances[{i}].character_variants[{j}].starting_force_powers",
                ))

    # Force discovery window falls within total_acts
    if spine.force_discovery_window is not None:
        low, high = spine.force_discovery_window
        if low < 1 or high > spine.total_acts:
            report.errors.append(ValidationError(
                gate=1, code="force_discovery_window_out_of_range",
                message=f"force_discovery_window ({low}, {high}) exceeds act range 1-{spine.total_acts}",
                path="force_discovery_window",
            ))

    # Vignette npc_focus references resolve to roster
    for i, act in enumerate(spine.acts):
        if act.time_skip_after:
            for j, vig in enumerate(act.time_skip_after.vignette_library):
                if vig.npc_focus and vig.npc_focus not in npc_names:
                    report.errors.append(ValidationError(
                        gate=1, code="vignette_npc_not_in_roster",
                        message=f"Vignette '{vig.vignette_id}' npc_focus '{vig.npc_focus}' not in roster",
                        path=f"acts[{i}].time_skip_after.vignette_library[{j}].npc_focus",
                    ))

    # XP base is positive on all acts (Pydantic ge=0, but spec says positive)
    for i, act in enumerate(spine.acts):
        if act.xp_base <= 0:
            report.errors.append(ValidationError(
                gate=1, code="xp_base_not_positive",
                message=f"Act {act.number} has xp_base={act.xp_base}, must be positive",
                path=f"acts[{i}].xp_base",
            ))

    # Canon NPC entries have canon_voice and behavioral_envelope populated
    for i, npc in enumerate(spine.npc_roster):
        if npc.canon:
            if not npc.canon_voice:
                report.errors.append(ValidationError(
                    gate=1, code="canon_npc_missing_voice",
                    message=f"Canon NPC '{npc.name}' must have canon_voice populated",
                    path=f"npc_roster[{i}].canon_voice",
                ))
            if not npc.behavioral_envelope:
                report.errors.append(ValidationError(
                    gate=1, code="canon_npc_missing_envelope",
                    message=f"Canon NPC '{npc.name}' must have behavioral_envelope populated",
                    path=f"npc_roster[{i}].behavioral_envelope",
                ))

    # Vehicle ship_id values are unique
    ship_ids = [ship.ship_id for ship in spine.vehicle_registry]
    seen_ship_ids: set[str] = set()
    for i, sid in enumerate(ship_ids):
        if sid in seen_ship_ids:
            report.errors.append(ValidationError(
                gate=1, code="duplicate_ship_id",
                message=f"Duplicate ship_id '{sid}' in vehicle_registry",
                path=f"vehicle_registry[{i}].ship_id",
            ))
        seen_ship_ids.add(sid)

    # Import interface target_xp_range minimum ≤ maximum
    if spine.import_interface is not None:
        low, high = spine.import_interface.target_xp_range
        if low > high:
            report.errors.append(ValidationError(
                gate=1, code="import_xp_range_inverted",
                message=f"import_interface target_xp_range min ({low}) > max ({high})",
                path="import_interface.target_xp_range",
            ))

    # Faction faction_id values are unique
    seen_faction_ids: set[str] = set()
    for i, faction in enumerate(spine.factions):
        if faction.faction_id in seen_faction_ids:
            report.errors.append(ValidationError(
                gate=1, code="duplicate_faction_id",
                message=f"Duplicate faction_id '{faction.faction_id}'",
                path=f"factions[{i}].faction_id",
            ))
        seen_faction_ids.add(faction.faction_id)

    # per_act_drift keys are valid act numbers
    for i, faction in enumerate(spine.factions):
        valid_act_nums = {str(a.number) for a in spine.acts}
        for key in faction.per_act_drift:
            if key not in valid_act_nums:
                report.errors.append(ValidationError(
                    gate=1, code="faction_drift_invalid_act",
                    message=f"Faction '{faction.faction_id}' per_act_drift key '{key}' is not a valid act number",
                    path=f"factions[{i}].per_act_drift",
                ))

    # NPC npc_relationships entries reference NPCs that exist in the roster
    for i, npc in enumerate(spine.npc_roster):
        for j, rel in enumerate(npc.npc_relationships):
            if rel.npc not in npc_names:
                report.errors.append(ValidationError(
                    gate=1, code="npc_relationship_not_in_roster",
                    message=f"NPC '{npc.name}' has relationship with '{rel.npc}' who is not in the roster",
                    path=f"npc_roster[{i}].npc_relationships[{j}].npc",
                ))


# ── Gate 1: Integration Layer Validation (backlog 3.33) ───────────────


def _gate1_integration_layer(spine: CampaignSpine, report: ValidationReport) -> None:
    """Per-variant integration layer checks — closes audit finding 3.33.

    Five checks:
      1. Completeness: entry_point and personal_stakes are populated.
      2. NPC override validity: keys in npc_overrides reference roster NPCs.
      3. Anchor adaptation coverage: every act anchor has an adaptation.
      4. Entry point distinctness: variants don't share near-duplicate entry points.
      5. Personal stakes non-genericity: no "save the galaxy"-tier filler.
    """
    npc_names = {npc.name for npc in spine.npc_roster}
    act_anchors = {act.anchor for act in spine.acts if act.anchor}

    GENERIC_STAKES_PATTERNS = (
        "save the galaxy", "save the world", "stop the empire",
        "defeat evil", "the fate of",  "for the greater good",
        "everyone's counting", "save everyone",
    )

    for i, allegiance in enumerate(spine.allegiances):
        for j, variant in enumerate(allegiance.character_variants):
            il = variant.integration_layer
            base_path = f"allegiances[{i}].character_variants[{j}].integration_layer"

            # 1. Completeness — Pydantic enforces min_length, but check empty-after-strip.
            if not (il.entry_point or "").strip():
                report.errors.append(ValidationError(
                    gate=1, code="integration_entry_point_empty",
                    message=f"Variant '{variant.id}' has empty integration_layer.entry_point",
                    path=f"{base_path}.entry_point",
                ))
            if not (il.personal_stakes or "").strip():
                report.errors.append(ValidationError(
                    gate=1, code="integration_personal_stakes_empty",
                    message=f"Variant '{variant.id}' has empty integration_layer.personal_stakes",
                    path=f"{base_path}.personal_stakes",
                ))

            # 2. NPC override validity
            for npc_key in il.npc_overrides.keys():
                if npc_key not in npc_names:
                    report.errors.append(ValidationError(
                        gate=1, code="integration_npc_override_unknown",
                        message=(
                            f"Variant '{variant.id}' overrides NPC '{npc_key}' "
                            f"which is not in the roster"
                        ),
                        path=f"{base_path}.npc_overrides.{npc_key}",
                    ))

            # 3. Anchor adaptation coverage — each act anchor should be addressed.
            adaptation_keys = set(il.anchor_adaptations.keys())
            missing = act_anchors - adaptation_keys
            if missing:
                report.warnings.append(ValidationWarning(
                    gate=1, code="integration_anchor_adaptation_missing",
                    message=(
                        f"Variant '{variant.id}' missing anchor adaptation(s): "
                        f"{sorted(missing)}"
                    ),
                    path=f"{base_path}.anchor_adaptations",
                ))
            unknown = adaptation_keys - act_anchors
            if unknown:
                report.warnings.append(ValidationWarning(
                    gate=1, code="integration_anchor_adaptation_unknown",
                    message=(
                        f"Variant '{variant.id}' has anchor adaptation(s) for "
                        f"unknown anchors: {sorted(unknown)}"
                    ),
                    path=f"{base_path}.anchor_adaptations",
                ))

            # 5. Personal stakes non-genericity (variant-local heuristic).
            stakes_lower = il.personal_stakes.lower()
            for pattern in GENERIC_STAKES_PATTERNS:
                if pattern in stakes_lower:
                    report.warnings.append(ValidationWarning(
                        gate=1, code="integration_personal_stakes_generic",
                        message=(
                            f"Variant '{variant.id}' personal_stakes contains "
                            f"generic phrase '{pattern}' — stakes should be "
                            f"specific to the protagonist's situation"
                        ),
                        path=f"{base_path}.personal_stakes",
                    ))
                    break

    # 4. Entry point distinctness across all variants — Jaccard similarity.
    all_variants = [
        (v, alg.id) for alg in spine.allegiances for v in alg.character_variants
    ]
    DUPLICATE_THRESHOLD = 0.7
    for a in range(len(all_variants)):
        for b in range(a + 1, len(all_variants)):
            v1, alg1 = all_variants[a]
            v2, alg2 = all_variants[b]
            sim = _jaccard_token_similarity(
                v1.integration_layer.entry_point,
                v2.integration_layer.entry_point,
            )
            if sim >= DUPLICATE_THRESHOLD:
                report.warnings.append(ValidationWarning(
                    gate=1, code="integration_entry_points_too_similar",
                    message=(
                        f"Variants '{v1.id}' and '{v2.id}' have entry points "
                        f"with Jaccard token similarity {sim:.2f} — they should "
                        f"feel like structurally different ways into the campaign"
                    ),
                    path="allegiances[*].character_variants[*].integration_layer.entry_point",
                ))


def _jaccard_token_similarity(a: str, b: str) -> float:
    """Token-set Jaccard similarity. Lowercased, stop words filtered."""
    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "of", "in", "on", "at",
        "to", "for", "with", "by", "from", "as", "is", "are", "was", "were",
        "been", "being", "be", "has", "have", "had", "this", "that", "these",
        "those", "it", "its", "you", "your", "yours", "they", "them", "their",
        "she", "her", "hers", "he", "him", "his", "we", "us", "our",
    }
    def tokens(s: str) -> set[str]:
        return {t for t in (w.strip(".,;:!?'\"()[]{}").lower() for w in s.split()) if t and t not in STOPWORDS}
    sa, sb = tokens(a), tokens(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ── Gate 2: NPC Coherence Validation ──────────────────────────────────


def _gate2_npc_coherence(spine: CampaignSpine, report: ValidationReport) -> None:
    """Per-NPC disposition trajectory analysis.

    Flags disposition shifts > 0.3 between consecutive acts without
    setup in the role_in_act description.
    """
    for i, npc in enumerate(spine.npc_roster):
        if not npc.per_act_state:
            continue

        # Major NPCs (present across 2+ acts) should argue a position on
        # the campaign's throughline. Without a thematic_argument the NPC
        # is plot furniture, not a participant in the theme.
        acts_covered = {s.act for s in npc.per_act_state}
        if len(acts_covered) >= 2 and not (npc.thematic_argument or "").strip():
            report.warnings.append(ValidationWarning(
                gate=2, code="npc_missing_thematic_argument",
                message=(
                    f"NPC '{npc.name}' appears in {len(acts_covered)} acts "
                    f"but has no thematic_argument — major NPCs should argue "
                    f"a position on the campaign's throughline question"
                ),
                path=f"npc_roster[{i}].thematic_argument",
            ))

        # Sort by act number
        sorted_states = sorted(npc.per_act_state, key=lambda s: s.act)

        for j in range(1, len(sorted_states)):
            prev = sorted_states[j - 1]
            curr = sorted_states[j]

            # Extract numeric dispositions where possible
            prev_disp = _parse_disposition(prev.disposition_expected)
            curr_disp = _parse_disposition(curr.disposition_expected)

            if prev_disp is None or curr_disp is None:
                continue

            shift = abs(curr_disp - prev_disp)
            if shift > 0.3:
                # Check if role_in_act mentions any transition language
                transition_words = [
                    "betrayal", "betrays", "reveals", "turns", "shifts",
                    "changes", "evolves", "transforms", "crisis", "conflict",
                    "discovery", "shock", "surprise", "reversal",
                ]
                role_lower = curr.role_in_act.lower()
                has_setup = any(w in role_lower for w in transition_words)

                if not has_setup:
                    report.warnings.append(ValidationWarning(
                        gate=2, code="large_disposition_shift",
                        message=(
                            f"NPC '{npc.name}' disposition shifts {shift:.2f} "
                            f"from act {prev.act} to act {curr.act} without "
                            f"transition language in role_in_act"
                        ),
                        path=f"npc_roster[{i}].per_act_state",
                    ))


def _parse_disposition(value: str | float) -> Optional[float]:
    """Try to extract a numeric disposition from a string or float."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ── Gate 3: Relationship Network Validation ───────────────────────────


def _gate3_relationship_network(spine: CampaignSpine, report: ValidationReport) -> None:
    """Check for LLM-typical positivity skew in NPC relationships.

    Flags:
    - Mean relationship weight > 0.5
    - > 80% positive relationships
    - Sparse antagonist networks
    """
    all_weights: list[float] = []
    positive_count = 0
    negative_count = 0

    for npc in spine.npc_roster:
        for rel in npc.npc_relationships:
            all_weights.append(rel.weight)
            if rel.weight > 0:
                positive_count += 1
            elif rel.weight < 0:
                negative_count += 1

    # Anti-positivity-skew heuristics (Jun 2026) — a roster of any real
    # size needs authored conflict, both inside the relationship graph
    # and in at least one NPC the player starts at odds with. These run
    # even when no relationships are defined (zero is fewer than two).
    roster_size = len(spine.npc_roster)
    if roster_size >= 4 and negative_count < 2:
        report.warnings.append(ValidationWarning(
            gate=3, code="insufficient_negative_relationships",
            message=(
                f"Only {negative_count} negative-weight NPC relationship(s) "
                f"across {roster_size} NPCs. A campaign roster needs at "
                f"least 2 antagonistic relationships for internal cast "
                f"conflict."
            ),
        ))
    if roster_size >= 4 and not any(
        npc.disposition_start < 0.4 for npc in spine.npc_roster
    ):
        report.warnings.append(ValidationWarning(
            gate=3, code="no_antagonistic_npc",
            message=(
                "No NPC has disposition_start below 0.4. At least one NPC "
                "should start antagonistic toward the player."
            ),
        ))

    if not all_weights:
        # No relationships defined — not an error, just skip analysis
        return

    mean_weight = sum(all_weights) / len(all_weights)
    total_nonzero = positive_count + negative_count
    positive_ratio = positive_count / total_nonzero if total_nonzero > 0 else 0.0

    if mean_weight > 0.5:
        report.warnings.append(ValidationWarning(
            gate=3, code="positivity_skew_mean",
            message=(
                f"Mean NPC relationship weight is {mean_weight:.2f} (> 0.5). "
                f"This suggests LLM-typical positivity bias — consider adding "
                f"more antagonistic or neutral relationships."
            ),
        ))

    if positive_ratio > 0.8 and total_nonzero >= 3:
        report.warnings.append(ValidationWarning(
            gate=3, code="positivity_skew_ratio",
            message=(
                f"{positive_ratio:.0%} of relationships are positive "
                f"({positive_count}/{total_nonzero}). Consider adding "
                f"antagonistic relationships for narrative tension."
            ),
        ))

    if negative_count == 0 and len(spine.npc_roster) >= 3:
        report.warnings.append(ValidationWarning(
            gate=3, code="sparse_antagonist_network",
            message=(
                "No negative NPC-NPC relationships found. A campaign with "
                f"{len(spine.npc_roster)} NPCs should have at least some "
                "antagonistic dynamics."
            ),
        ))

    # Optional NetworkX analysis for richer graph metrics
    _gate3_networkx_analysis(spine, report)


def _gate3_networkx_analysis(spine: CampaignSpine, report: ValidationReport) -> None:
    """Extended graph analysis using NetworkX, if available."""
    try:
        import networkx as nx
    except ImportError:
        return  # Graceful fallback — simple arithmetic above is sufficient

    G = nx.DiGraph()
    for npc in spine.npc_roster:
        G.add_node(npc.name)
    for npc in spine.npc_roster:
        for rel in npc.npc_relationships:
            if rel.npc in G.nodes:
                G.add_edge(npc.name, rel.npc, weight=rel.weight, nature=rel.nature)

    if G.number_of_edges() == 0:
        return

    # Check for isolated NPCs (no relationships at all)
    for node in G.nodes:
        if G.degree(node) == 0:
            report.warnings.append(ValidationWarning(
                gate=3, code="isolated_npc",
                message=f"NPC '{node}' has no relationships with other NPCs",
            ))

    # Check for disconnected components
    undirected = G.to_undirected()
    components = list(nx.connected_components(undirected))
    if len(components) > 1:
        report.warnings.append(ValidationWarning(
            gate=3, code="disconnected_npc_groups",
            message=(
                f"NPC relationship network has {len(components)} disconnected "
                f"groups: {[sorted(c) for c in components]}. Consider connecting them."
            ),
        ))


# ── Gate 3: Allegiance Diversity Validation (backlog 3.34) ────────────


def _gate3_allegiance_diversity(spine: CampaignSpine, report: ValidationReport) -> None:
    """Cross-allegiance diversity checks — closes audit finding 3.34.

    Three checks (pure Python, Jaccard token similarity):
      1. NPC override disposition diversity — different allegiances should
         move NPCs in meaningfully different directions.
      2. Anchor adaptation similarity — each anchor should have distinct
         adaptations across variants, not minor wording changes.
      3. Entry point structural difference — entry points should describe
         genuinely different lives, not the same archetype with synonyms.

    A campaign with one allegiance/one variant is silently skipped.
    """
    all_variants = [
        v for alg in spine.allegiances for v in alg.character_variants
    ]
    if len(all_variants) < 2:
        return  # Single-variant campaign — no diversity to evaluate.

    DIVERSITY_THRESHOLD_ANCHOR = 0.65   # anchor adaptations are content-rich
    DIVERSITY_THRESHOLD_ENTRY  = 0.55   # entry points should be more distinct

    # 1. NPC override disposition diversity.
    # When two variants both override the same NPC, those overrides should
    # tend to push in different directions. We inspect the relationship_label
    # field if present, else the freeform fields.
    pair_count = 0
    diverse_pair_count = 0
    for a in range(len(all_variants)):
        for b in range(a + 1, len(all_variants)):
            v1, v2 = all_variants[a], all_variants[b]
            shared_npcs = (
                set(v1.integration_layer.npc_overrides.keys())
                & set(v2.integration_layer.npc_overrides.keys())
            )
            for npc_name in shared_npcs:
                pair_count += 1
                ov1 = v1.integration_layer.npc_overrides[npc_name]
                ov2 = v2.integration_layer.npc_overrides[npc_name]
                # Compare relationship_label first, fall back to other text.
                label1 = (getattr(ov1, "relationship_label", "") or "").strip().lower()
                label2 = (getattr(ov2, "relationship_label", "") or "").strip().lower()
                if label1 and label2 and label1 != label2:
                    diverse_pair_count += 1
                    continue
                # Fallback: token similarity on full override text content.
                t1 = " ".join(
                    str(v) for v in ov1.model_dump().values() if isinstance(v, str)
                )
                t2 = " ".join(
                    str(v) for v in ov2.model_dump().values() if isinstance(v, str)
                )
                if _jaccard_token_similarity(t1, t2) < 0.8:
                    diverse_pair_count += 1
    if pair_count >= 3 and diverse_pair_count / pair_count < 0.5:
        report.warnings.append(ValidationWarning(
            gate=3, code="allegiance_npc_overrides_too_similar",
            message=(
                f"Across allegiances, only {diverse_pair_count}/{pair_count} "
                f"shared-NPC override pairs feel meaningfully different. "
                f"Allegiances should pull NPCs in different directions."
            ),
            path="allegiances[*].character_variants[*].integration_layer.npc_overrides",
        ))

    # 2. Anchor adaptation similarity — per-anchor, across variants.
    anchors = {act.anchor for act in spine.acts if act.anchor}
    for anchor in anchors:
        adaptations = []
        for v in all_variants:
            text = v.integration_layer.anchor_adaptations.get(anchor)
            if text:
                adaptations.append((v.id, text))
        if len(adaptations) < 2:
            continue
        for i in range(len(adaptations)):
            for j in range(i + 1, len(adaptations)):
                vid1, t1 = adaptations[i]
                vid2, t2 = adaptations[j]
                sim = _jaccard_token_similarity(t1, t2)
                if sim >= DIVERSITY_THRESHOLD_ANCHOR:
                    report.warnings.append(ValidationWarning(
                        gate=3, code="allegiance_anchor_adaptations_too_similar",
                        message=(
                            f"Variants '{vid1}' and '{vid2}' adapt anchor "
                            f"'{anchor}' with Jaccard similarity {sim:.2f} "
                            f"— each variant should fill the anchor with their "
                            f"own concerns and stakes"
                        ),
                        path=f"allegiances[*].character_variants[*].integration_layer.anchor_adaptations.{anchor}",
                    ))

    # 3. Entry point structural difference (stricter threshold than Gate 1's
    # near-duplicate check — Gate 3 wants genuinely distinct lives).
    for a in range(len(all_variants)):
        for b in range(a + 1, len(all_variants)):
            v1, v2 = all_variants[a], all_variants[b]
            sim = _jaccard_token_similarity(
                v1.integration_layer.entry_point,
                v2.integration_layer.entry_point,
            )
            if sim >= DIVERSITY_THRESHOLD_ENTRY:
                report.warnings.append(ValidationWarning(
                    gate=3, code="allegiance_entry_points_low_diversity",
                    message=(
                        f"Variants '{v1.id}' and '{v2.id}' entry points share "
                        f"{sim:.0%} of significant tokens — paths should describe "
                        f"structurally different lives, not synonyms of the same one"
                    ),
                    path="allegiances[*].character_variants[*].integration_layer.entry_point",
                ))


# ── Gate 4: Narrative Consistency Audit (LLM) ────────────────────────


def _gate4_narrative_consistency(spine: CampaignSpine, report: ValidationReport) -> None:
    """LLM-assisted narrative quality checks.

    Sub-gates:
    4a: Narrative coherence (thread continuity, NPC consistency,
        throughline presence, context relevance)
    4b: Dramatic quality (architecture-spine alignment) — only runs
        when story_architecture is populated
    4c: Anti-genericity audit (NPC distinctiveness, anchor specificity,
        escalation authenticity)

    Uses a single LLM call with a structured evaluation prompt.
    Multiple failures within a sub-gate escalate to errors.
    """
    from studio.narrative_eval import gate4_check

    try:
        errors, warnings = gate4_check(spine)
    except RuntimeError as e:
        # LLM call failed — add a warning but don't block validation
        report.warnings.append(ValidationWarning(
            gate=4,
            code="gate4_llm_failure",
            message=f"Gate 4 LLM evaluation failed: {e}",
        ))
        return

    for w in warnings:
        report.warnings.append(ValidationWarning(
            gate=w["gate"],
            code=w["code"],
            message=w["message"],
            path=w.get("path", ""),
        ))

    for e in errors:
        report.errors.append(ValidationError(
            gate=e["gate"],
            code=e["code"],
            message=e["message"],
            path=e.get("path", ""),
        ))
