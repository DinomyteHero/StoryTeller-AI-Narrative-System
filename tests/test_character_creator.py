"""Character creator tests (Phase 3) — hermetic, LLM mocked.

Covers the deterministic assembly guarantees (clamping, derived-stat recompute,
fixed XP, signature-talent validation) and the draft/save HTTP round-trip.
"""

import json

import pytest
from fastapi.testclient import TestClient

import gm.character_creator as cc
from gm.character_creator import assemble_character, CharacterDraftError
from engine.character import Character, species_thresholds, species_start_xp


def _good_draft(**overrides) -> dict:
    draft = {
        "name": "Vex Dovan",
        "species": "kel_dor",
        "career": "ex-imperial slicer",
        "archetype_concept": "Jaded ex-Imperial slicer turned freelancer",
        "background": "Sliced for the Empire until a purge made it personal.",
        "force_sensitive": False,
        "characteristics": {"brawn": 2, "agility": 3, "intellect": 4,
                            "cunning": 3, "willpower": 2, "presence": 2},
        "skills": {"computers": 3, "skulduggery": 2, "stealth": 1, "cool": 1},
        "career_skills": ["computers", "skulduggery", "stealth", "cool",
                          "deception", "knowledge"],  # 'knowledge' is bogus
        "signature_talents": [{
            "name": "Slicer Instinct",
            "talent_type": "passive",
            "ranked": True,
            "max_rank": 2,
            "narrative_identity": "Your fingers know the system first.",
            "prose_tags": ["slicing", "instinct"],
            "effects": [{"type": "modify_pool",
                         "target_skills": ["computers"],
                         "modifier": {"boost": 1}}],
        }],
        "narrative_arc": {
            "lie": "Trust is a vulnerability the galaxy punishes.",
            "ghost": "A partner he trusted sold him to ISB.",
            "truth": "Some debts are only paid by trusting again.",
            "want": "To disappear with enough credits to never need anyone.",
            "need": "To let one person in.",
            "arc_type": "positive",
        },
        "voice_notes": "Clipped, sardonic, allergic to sincerity.",
        "throughline_question": "Can a man who trusts no one ever be free?",
        "starting_loadout": {
            "weapons": [{"name": "Hold-out blaster", "skill": "ranged_light",
                         "damage_bonus": 5, "critical_rating": 4,
                         "qualities": ["stun_setting"]}],
            "armor": {"name": "Armored coat", "soak_bonus": 1},
            "tools": [{"name": "Slicer kit", "description": "Bypasses locks."}],
            "special_items": ["Forged Imperial credentials"],
        },
    }
    draft.update(overrides)
    return draft


# ── assemble_character: deterministic guarantees ─────────────────────

def test_assemble_basic_validity():
    ch = assemble_character(_good_draft())
    assert isinstance(ch, Character)
    assert ch.species == "kel_dor"
    assert ch.career == "ex-imperial slicer"
    assert ch.archetype_concept.startswith("Jaded")


def test_assemble_recomputes_derived_stats():
    ch = assemble_character(_good_draft())
    wound_base, strain_base = species_thresholds("kel_dor")  # unknown -> default
    assert ch.soak == ch.characteristics.brawn
    assert ch.wound_threshold == wound_base + ch.characteristics.brawn
    assert ch.strain_threshold == strain_base + ch.characteristics.willpower
    assert ch.current_wounds == 0 and ch.current_strain == 0


def test_assemble_sets_fixed_xp_ignoring_draft():
    draft = _good_draft()
    draft["total_xp"] = 99999  # the LLM/editor cannot inject XP
    ch = assemble_character(draft)
    assert ch.total_xp == species_start_xp("kel_dor")
    assert ch.available_xp == ch.total_xp


def test_assemble_clamps_characteristics_and_skills():
    draft = _good_draft(characteristics={"brawn": 99, "agility": 0,
                                          "intellect": 4, "cunning": 3,
                                          "willpower": 2, "presence": 2},
                        skills={"computers": 50, "stealth": -3})
    ch = assemble_character(draft)
    assert ch.characteristics.brawn == 5      # clamped down
    assert ch.characteristics.agility == 1    # clamped up
    assert ch.skills.computers == 5           # clamped to max rank
    assert ch.skills.stealth == 0             # clamped up from negative


def test_assemble_drops_unknown_career_skills():
    ch = assemble_character(_good_draft())
    assert "knowledge" not in ch.career_skills
    assert "computers" in ch.career_skills


def test_assemble_stores_valid_signature_talent():
    ch = assemble_character(_good_draft())
    assert "slicer_instinct" in ch.custom_talents
    assert ch.custom_talents["slicer_instinct"]["talent_type"] == "passive"


def test_assemble_force_sensitive_sets_rating():
    ch = assemble_character(_good_draft(force_sensitive=True))
    assert ch.force_rating == 1


def test_assemble_rejects_bad_signature_talent():
    bad = _good_draft()
    bad["signature_talents"][0]["effects"][0]["modifier"] = {"wild": 9}  # bad die
    with pytest.raises(CharacterDraftError) as ei:
        assemble_character(bad)
    assert any("signature talent" in e for e in ei.value.errors)


def test_assemble_requires_name():
    with pytest.raises(CharacterDraftError):
        assemble_character(_good_draft(name=""))


# ── HTTP round-trip (LLM mocked) ─────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    # Mock the LLM-backed draft so /character/draft is hermetic.
    import api.character_routes as routes
    monkeypatch.setattr(routes, "draft_character", lambda pitch, hints=None: _good_draft())
    from api.main import app
    return TestClient(app)


def test_draft_endpoint(client):
    res = client.post("/character/draft", json={"pitch": "a jaded ex-imperial slicer"})
    assert res.status_code == 200
    assert res.json()["draft"]["name"] == "Vex Dovan"


def test_save_and_load_round_trip(client, tmp_path, monkeypatch):
    # Redirect the characters dir to a temp location to avoid polluting the repo.
    import api.character_routes as routes
    monkeypatch.setattr(routes, "CHARACTERS_DIR", tmp_path)

    draft = _good_draft(name="Test Roundtrip Hero")
    res = client.post("/character/save", json={"character_json": draft})
    assert res.status_code == 200, res.text
    cid = res.json()["character_id"]
    assert cid == "test_roundtrip_hero"

    # File exists and loads as a Character
    saved = json.loads((tmp_path / f"{cid}.json").read_text(encoding="utf-8"))
    ch = Character.model_validate(saved)
    assert ch.name == "Test Roundtrip Hero"

    # GET round-trip
    res2 = client.get(f"/character/{cid}")
    assert res2.status_code == 200
    assert res2.json()["character_json"]["name"] == "Test Roundtrip Hero"


def test_save_rejects_invalid_talent(client, tmp_path, monkeypatch):
    import api.character_routes as routes
    monkeypatch.setattr(routes, "CHARACTERS_DIR", tmp_path)
    bad = _good_draft()
    bad["signature_talents"][0]["talent_type"] = "bogus_type"
    res = client.post("/character/save", json={"character_json": bad})
    assert res.status_code == 422
    assert "errors" in res.json()["detail"]


def test_save_collision_suffixes(client, tmp_path, monkeypatch):
    import api.character_routes as routes
    monkeypatch.setattr(routes, "CHARACTERS_DIR", tmp_path)
    d = _good_draft(name="Twin")
    r1 = client.post("/character/save", json={"character_json": d})
    r2 = client.post("/character/save", json={"character_json": d})
    assert r1.json()["character_id"] == "twin"
    assert r2.json()["character_id"] == "twin_2"
