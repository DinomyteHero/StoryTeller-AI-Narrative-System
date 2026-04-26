import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "data" / "era_packs"

REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "id",
    "display_name",
    "continuity",
    "date_range",
    "era_voice",
    "timeline_bands",
    "terminology",
    "faction_templates",
    "allegiance_templates",
    "force_traditions",
    "scene_pressures",
    "ffg_outcome_guidance",
    "campaign_templates",
    "implementation_gaps",
}

REQUIRED_FACTION_KEYS = {
    "faction_id",
    "display_name",
    "description",
    "disposition_start",
    "influence_start",
    "awareness_start",
    "per_act_drift",
}


def _load_pack(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_era_pack_directory_has_seed_content():
    packs = sorted(PACK_DIR.glob("*.json"))
    assert packs, "Expected at least one era pack JSON file"


def test_all_era_packs_have_required_shape():
    for path in PACK_DIR.glob("*.json"):
        pack = _load_pack(path)
        missing = REQUIRED_TOP_LEVEL_KEYS - set(pack)
        assert not missing, f"{path.name} missing keys: {sorted(missing)}"

        assert pack["schema_version"].startswith("era_pack.")
        assert pack["id"]
        assert pack["continuity"] in {"legends", "canon", "custom"}

        era_voice = pack["era_voice"]
        assert era_voice.get("era")
        assert era_voice.get("voice_notes")
        assert era_voice.get("period_details")
        assert era_voice.get("period_avoid")

        timeline_ids = [band["id"] for band in pack["timeline_bands"]]
        assert len(timeline_ids) == len(set(timeline_ids))

        for faction in pack["faction_templates"]:
            missing_faction = REQUIRED_FACTION_KEYS - set(faction)
            assert not missing_faction, (
                f"{path.name} faction missing keys: {sorted(missing_faction)}"
            )
            for key in ("disposition_start", "influence_start", "awareness_start"):
                assert 0.0 <= faction[key] <= 1.0

        allegiance_ids = [a["id"] for a in pack["allegiance_templates"]]
        assert len(allegiance_ids) == len(set(allegiance_ids))
        for allegiance in pack["allegiance_templates"]:
            assert allegiance.get("variant_seeds")
            variant_ids = [v["id"] for v in allegiance["variant_seeds"]]
            assert len(variant_ids) == len(set(variant_ids))


def test_new_jedi_order_pack_has_legends_specific_core():
    pack = _load_pack(PACK_DIR / "new_jedi_order.json")

    assert pack["id"] == "new_jedi_order"
    assert pack["continuity"] == "legends"
    assert "Yuuzhan Vong" in pack["core_premise"]

    faction_ids = {f["faction_id"] for f in pack["faction_templates"]}
    assert {
        "new_jedi_order",
        "new_republic",
        "yuuzhan_vong",
        "peace_brigade",
        "imperial_remnant",
        "refugee_networks",
    }.issubset(faction_ids)

    term_names = {t["term"] for t in pack["terminology"]["era_terms"]}
    assert {"Yuuzhan Vong", "Peace Brigade", "Dovin basal"}.issubset(term_names)

    gap_ids = {g["gap"] for g in pack["implementation_gaps"]}
    assert {"species_breadth", "era_pack_loader"}.issubset(gap_ids)


def test_new_republic_praxeum_pack_has_sample_campaign_core():
    pack = _load_pack(PACK_DIR / "new_republic_praxeum.json")

    assert pack["id"] == "new_republic_praxeum"
    assert pack["continuity"] == "legends"
    assert "Jedi Praxeum" in pack["core_premise"]
    assert "11-14 ABY" in pack["date_range"]["primary_play_window"]

    faction_ids = {f["faction_id"] for f in pack["faction_templates"]}
    assert {
        "new_republic",
        "jedi_praxeum",
        "imperial_remnant",
        "imperial_holdouts",
        "academy_support",
    }.issubset(faction_ids)

    allegiance_ids = {a["id"] for a in pack["allegiance_templates"]}
    assert {
        "jedi_order",
        "academy_support",
        "new_republic_service",
        "imperial_survivor",
    }.issubset(allegiance_ids)

    term_names = {t["term"] for t in pack["terminology"]["era_terms"]}
    assert {
        "New Republic",
        "Imperial Remnant",
        "Jedi Praxeum",
        "Massassi ruins",
    }.issubset(term_names)

    template_ids = {t["id"] for t in pack["campaign_templates"]}
    assert {"academy_mystery", "ruins_under_the_school"}.issubset(template_ids)

    gap_ids = {g["gap"] for g in pack["implementation_gaps"]}
    assert {"era_pack_loader", "canon_profile_directory"}.issubset(gap_ids)
