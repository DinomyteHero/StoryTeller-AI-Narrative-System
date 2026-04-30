"""Path differentiation validation — closes backlog items 3.33 and 3.34.

3.33 — Integration layer Gate 1 checks (NPC override validity, anchor
adaptation coverage, entry point distinctness, personal stakes non-genericity).

3.34 — Allegiance diversity Gate 3 checks (NPC override diversity, anchor
adaptation similarity, entry point structural difference).
"""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from studio.schema import CampaignSpine
from studio.validate import (
    validate_spine,
    _gate1_integration_layer,
    _gate3_allegiance_diversity,
    _jaccard_token_similarity,
    ValidationReport,
)


PRAXEUM_PATH = Path("data/campaigns/shadows_of_the_praxeum.json")


@pytest.fixture
def praxeum_spine_dict():
    """Load and return the canonical Praxeum spine as a dict, fresh per test."""
    return json.loads(PRAXEUM_PATH.read_text(encoding="utf-8"))


def _validate(spine_dict) -> ValidationReport:
    spine = CampaignSpine(**spine_dict)
    report = ValidationReport(passed=True)
    _gate1_integration_layer(spine, report)
    _gate3_allegiance_diversity(spine, report)
    return report


def _warning_codes(report: ValidationReport) -> set[str]:
    return {w.code for w in report.warnings}


def _error_codes(report: ValidationReport) -> set[str]:
    return {e.code for e in report.errors}


# ── Jaccard helper ───────────────────────────────────────────────────────

def test_jaccard_zero_for_disjoint():
    assert _jaccard_token_similarity("alpha beta", "gamma delta") == 0.0


def test_jaccard_one_for_identical():
    assert _jaccard_token_similarity("alpha beta gamma", "alpha beta gamma") == 1.0


def test_jaccard_filters_stopwords():
    """'the cat' vs 'the dog' should be 0% — stopword 'the' shouldn't dominate."""
    assert _jaccard_token_similarity("the cat", "the dog") == 0.0


def test_jaccard_partial_overlap():
    sim = _jaccard_token_similarity("alpha beta gamma", "alpha beta delta")
    assert 0.4 <= sim <= 0.6


# ── Praxeum baseline (canonical spine should pass cleanly) ───────────────

def test_praxeum_passes_path_differentiation(praxeum_spine_dict):
    report = _validate(praxeum_spine_dict)
    integration_codes = {c for c in _warning_codes(report) if c.startswith("integration_")}
    allegiance_codes = {c for c in _warning_codes(report) if c.startswith("allegiance_")}
    assert _error_codes(report) == set()
    assert integration_codes == set()
    assert allegiance_codes == set()


# ── Gate 1 (3.33) integration layer checks ──────────────────────────────

def _all_variants(spine_dict):
    """Yield (allegiance_idx, variant_idx, variant_dict) across all allegiances."""
    out = []
    for ai, alg in enumerate(spine_dict["allegiances"]):
        for vi, v in enumerate(alg["character_variants"]):
            out.append((ai, vi, v))
    return out


def test_gate1_flags_unknown_npc_override(praxeum_spine_dict):
    spine = deepcopy(praxeum_spine_dict)
    variant = spine["allegiances"][0]["character_variants"][0]
    # Borrow a real override's full schema, just rename the key.
    real_overrides = variant["integration_layer"]["npc_overrides"]
    real_key = next(iter(real_overrides.keys()))
    variant["integration_layer"]["npc_overrides"]["Phantom NPC"] = (
        deepcopy(real_overrides[real_key])
    )
    report = _validate(spine)
    assert "integration_npc_override_unknown" in _error_codes(report)


def test_gate1_flags_missing_anchor_adaptation(praxeum_spine_dict):
    spine = deepcopy(praxeum_spine_dict)
    variant = spine["allegiances"][0]["character_variants"][0]
    # Drop one anchor adaptation — should flag as missing.
    variant["integration_layer"]["anchor_adaptations"].pop("arrivals")
    report = _validate(spine)
    assert "integration_anchor_adaptation_missing" in _warning_codes(report)


def test_gate1_flags_unknown_anchor_adaptation_key(praxeum_spine_dict):
    spine = deepcopy(praxeum_spine_dict)
    variant = spine["allegiances"][0]["character_variants"][0]
    variant["integration_layer"]["anchor_adaptations"]["nonexistent_anchor"] = "bogus"
    report = _validate(spine)
    assert "integration_anchor_adaptation_unknown" in _warning_codes(report)


def test_gate1_flags_generic_personal_stakes(praxeum_spine_dict):
    spine = deepcopy(praxeum_spine_dict)
    variant = spine["allegiances"][0]["character_variants"][0]
    variant["integration_layer"]["personal_stakes"] = (
        "The protagonist must save the galaxy from the rising darkness."
    )
    report = _validate(spine)
    assert "integration_personal_stakes_generic" in _warning_codes(report)


def test_gate1_flags_near_duplicate_entry_points(praxeum_spine_dict):
    spine = deepcopy(praxeum_spine_dict)
    # Force two variants to share an almost-identical entry point.
    all_v = _all_variants(spine)
    if len(all_v) < 2:
        pytest.skip("Spine needs 2+ variants for this test")
    variants = [t[2] for t in all_v]
    shared = (
        "The protagonist arrives at the Praxeum Academy on Ossus to begin "
        "Jedi training under Master Skywalker, drawn by curiosity and a "
        "deep sense of calling toward the Force."
    )
    variants[0]["integration_layer"]["entry_point"] = shared
    variants[1]["integration_layer"]["entry_point"] = shared
    report = _validate(spine)
    assert "integration_entry_points_too_similar" in _warning_codes(report)


# ── Gate 3 (3.34) allegiance diversity checks ──────────────────────────

def test_gate3_flags_identical_anchor_adaptations(praxeum_spine_dict):
    spine = deepcopy(praxeum_spine_dict)
    all_v = _all_variants(spine)
    if len(all_v) < 2:
        pytest.skip("Spine needs 2+ variants for this test")
    variants = [t[2] for t in all_v]
    # Force two variants to use the same wording for an anchor.
    same_text = (
        "The protagonist arrives at the academy with mixed feelings about "
        "what they have left behind and what awaits inside the walls."
    )
    variants[0]["integration_layer"]["anchor_adaptations"]["arrivals"] = same_text
    variants[1]["integration_layer"]["anchor_adaptations"]["arrivals"] = same_text
    report = _validate(spine)
    assert "allegiance_anchor_adaptations_too_similar" in _warning_codes(report)


def test_gate3_flags_low_diversity_entry_points(praxeum_spine_dict):
    """When entry points share most significant tokens, the stricter Gate 3
    threshold should fire even when Gate 1's 0.7 threshold doesn't."""
    spine = deepcopy(praxeum_spine_dict)
    all_v = _all_variants(spine)
    if len(all_v) < 2:
        pytest.skip("Spine needs 2+ variants for this test")
    variants = [t[2] for t in all_v]
    variants[0]["integration_layer"]["entry_point"] = (
        "The protagonist studies Force philosophy at the Praxeum and "
        "trains alongside fellow students under Master Skywalker daily."
    )
    variants[1]["integration_layer"]["entry_point"] = (
        "The protagonist studies Force philosophy at the Praxeum and "
        "trains alongside fellow students under Master Skywalker often."
    )
    report = _validate(spine)
    codes = _warning_codes(report)
    # Either Gate 1 or Gate 3 should catch this.
    assert (
        "allegiance_entry_points_low_diversity" in codes
        or "integration_entry_points_too_similar" in codes
    )


def test_gate3_skips_single_variant_spine(praxeum_spine_dict):
    """No diversity warnings when only one variant exists across the spine.

    Constructs the CampaignSpine via .model_construct to bypass the
    `min_length=2` allegiance constraint, since the diversity guard is
    a runtime safety net for hypothetical future schema relaxations.
    """
    spine = CampaignSpine(**praxeum_spine_dict)
    object.__setattr__(spine, "allegiances", [spine.allegiances[0]])
    object.__setattr__(
        spine.allegiances[0],
        "character_variants",
        [spine.allegiances[0].character_variants[0]],
    )
    report = ValidationReport(passed=True)
    _gate3_allegiance_diversity(spine, report)
    allegiance_codes = {w.code for w in report.warnings if w.code.startswith("allegiance_")}
    assert allegiance_codes == set()


# ── End-to-end via validate_spine ───────────────────────────────────────

def test_validate_spine_passes_canonical_praxeum(praxeum_spine_dict):
    spine = CampaignSpine(**praxeum_spine_dict)
    report = validate_spine(spine, run_gate4_llm=False)
    assert report.passed is True
    assert {1, 2, 3, 4}.issubset(set(report.gates_passed))
