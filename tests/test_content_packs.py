import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "data" / "content_packs"
ERA_PACK_DIR = ROOT / "data" / "era_packs"

REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "id",
    "display_name",
    "status",
    "continuity",
    "source_spine",
    "campaign_identity",
    "design_contract",
    "terminology",
    "runtime_assets_snapshot",
    "funnel_state",
    "npc_content_cards",
    "faction_guidance",
    "act_content_guidance",
    "ffg_scene_guidance",
    "prologue_scene_seeds",
    "content_gaps",
}


def _load_pack(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_content_pack_directory_has_sample_campaign_pack():
    assert (PACK_DIR / "shadows_of_the_custodian.json").exists()


def test_all_content_packs_have_required_shape():
    for path in PACK_DIR.glob("*.json"):
        pack = _load_pack(path)
        missing = REQUIRED_TOP_LEVEL_KEYS - set(pack)
        assert not missing, f"{path.name} missing keys: {sorted(missing)}"

        assert pack["schema_version"].startswith("campaign_content_pack.")
        assert pack["id"]
        assert pack["continuity"] in {"legends", "canon", "custom"}

        source_spine = ROOT / pack["source_spine"]
        assert source_spine.exists(), f"{path.name} source spine does not exist"

        identity = pack["campaign_identity"]
        assert identity.get("dramatic_premise")
        assert identity.get("central_dramatic_question", "").endswith("?")
        assert identity.get("thematic_throughline")

        assert pack["terminology"].get("campaign_terms")
        assert pack["design_contract"].get("must_feel_like")
        assert pack["design_contract"].get("must_not_feel_like")
        assert pack["content_gaps"]

        if pack.get("era_pack_id") and pack.get("era_pack_status") == "available":
            era_pack = ERA_PACK_DIR / f"{pack['era_pack_id']}.json"
            assert era_pack.exists(), f"{path.name} era pack does not exist"


def test_shadows_pack_matches_sample_spine_counts():
    pack = _load_pack(PACK_DIR / "shadows_of_the_custodian.json")
    spine = _load_pack(ROOT / pack["source_spine"])

    snapshot = pack["runtime_assets_snapshot"]
    assert snapshot["acts"] == len(spine["acts"])
    assert snapshot["allegiances"] == len(spine["allegiances"])
    assert snapshot["npc_count"] == len(spine["npc_roster"])
    assert snapshot["faction_count"] == len(spine["factions"])
    assert snapshot["vehicle_count"] == len(spine["vehicle_registry"])
    assert snapshot["variation_point_count"] == len(spine["variation_points"])
    assert snapshot["foreshadow_link_count"] == len(spine["foreshadow_registry"])
    assert snapshot["prologue_scene_sets"] == len(spine.get("prologue_scenes", []))


def test_shadows_pack_names_current_content_gaps():
    pack = _load_pack(PACK_DIR / "shadows_of_the_custodian.json")
    gap_ids = {gap["gap"] for gap in pack["content_gaps"]}

    assert pack["era_pack_id"] == "new_republic_praxeum"
    assert pack["era_pack_status"] == "available"

    assert {
        "era_pack_runtime_integration",
        "thin_funnel",
        "missing_prologue_sets",
        "talent_tree_coverage",
        "content_pack_loader",
    }.issubset(gap_ids)

    variant_seeds = pack["funnel_state"]["expansion_variant_seeds"]
    assert len(variant_seeds) >= 4

    prologue_seeds = pack["prologue_scene_seeds"]
    assert len(prologue_seeds) >= 4


def test_shadows_pack_preserves_legends_rpg_guardrails():
    pack = _load_pack(PACK_DIR / "shadows_of_the_custodian.json")

    premise = pack["campaign_identity"]["dramatic_premise"]
    assert "five-year-old Praxeum" in premise

    terms = {
        term["term"]: term
        for term in pack["terminology"]["campaign_terms"]
    }
    assert "Sadow-line holocron fragment" in terms
    assert "not Naga Sadow's one definitive holocron" in (
        terms["Sadow-line holocron fragment"]["usage"]
    )

    avoid_terms = {
        term["term"]: term["guidance"]
        for term in pack["terminology"]["avoid_or_contextualize"]
    }
    assert "Outer Rim-based Remnant" in avoid_terms["Imperial Remnant"]
    assert "settled peace" in avoid_terms["Imperial Remnant"]

    ffg_scene_types = {
        entry["scene_type"]: entry
        for entry in pack["ffg_scene_guidance"]
    }
    assert "lore_artifact" in ffg_scene_types
    assert "strain" in ffg_scene_types["lore_artifact"]["threat"]
