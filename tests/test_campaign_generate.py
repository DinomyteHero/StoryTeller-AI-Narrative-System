"""Generate-on-demand campaign tests (Phase 4) — hermetic, generation mocked.

Verifies POST /campaign/generate: writes a slug file, returns the campaign
name, the file is loadable; gate failure -> 502 with no file; name collisions
get numeric suffixes; the created character is folded into the brief.

The mocked "generated" spine is the real (known-valid) Shadows spine with its
name overridden, so the route's real CampaignSpine(**candidate) construction
succeeds. Nothing global is stubbed — avoids cross-test pollution.
"""

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import studio.validate as val
import studio.generate as gen
import studio.persist as persist

CAMPAIGN_DIR = Path(__file__).parent.parent / "data" / "campaigns"
_SHADOWS = json.loads(
    (CAMPAIGN_DIR / "shadows_of_the_custodian.json").read_text(encoding="utf-8")
)


def _fake_spine(name="Generated Test Campaign") -> dict:
    """A real, schema-valid spine with the name overridden for slug assertions."""
    spine = copy.deepcopy(_SHADOWS)
    spine["name"] = name
    return spine


@pytest.fixture
def client(monkeypatch):
    # Generators return our (valid) fake spine without calling an LLM.
    monkeypatch.setattr(gen, "generate_mode1",
                        lambda inputs, **kw: (_fake_spine(), 12345))
    monkeypatch.setattr(gen, "generate_from_brief",
                        lambda brief, **kw: (_fake_spine(), 12345))
    # Validation passes deterministically (skip gate flakiness). The route still
    # runs the real CampaignSpine(**candidate), which the fake spine satisfies.
    monkeypatch.setattr(val, "validate_spine",
                        lambda spine, **kw: val.ValidationReport(passed=True, warnings=[]))
    from api.main import app
    return TestClient(app)


def test_generate_writes_and_returns_slug(client, tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "CAMPAIGNS_DIR", tmp_path)
    res = client.post("/campaign/generate", json={
        "premise": "A short premise.",
        "era": "Galactic Civil War",
        "location": "Nar Shaddaa",
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["campaign_name"] == "generated_test_campaign"
    assert body["seed"] == 12345
    saved = json.loads((tmp_path / "generated_test_campaign.json").read_text(encoding="utf-8"))
    assert saved["name"] == "Generated Test Campaign"


def test_generate_gate_failure_returns_502_no_file(client, tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "CAMPAIGNS_DIR", tmp_path)
    monkeypatch.setattr(
        val, "validate_spine",
        lambda spine, **kw: val.ValidationReport(passed=False, errors=["bad anchor"]),
    )
    res = client.post("/campaign/generate", json={"era": "X", "location": "Y"})
    assert res.status_code == 502
    assert "details" in res.json()["detail"]
    assert list(tmp_path.glob("*.json")) == []


def test_generate_collision_suffixes(client, tmp_path, monkeypatch):
    monkeypatch.setattr(persist, "CAMPAIGNS_DIR", tmp_path)
    r1 = client.post("/campaign/generate", json={"era": "X", "location": "Y"})
    r2 = client.post("/campaign/generate", json={"era": "X", "location": "Y"})
    assert r1.json()["campaign_name"] == "generated_test_campaign"
    assert r2.json()["campaign_name"] == "generated_test_campaign_2"


def test_generate_tailors_to_character(client, tmp_path, monkeypatch):
    """When character_id resolves, the character's identity is folded into the
    brief (thematic input) and generation still succeeds."""
    monkeypatch.setattr(persist, "CAMPAIGNS_DIR", tmp_path)

    captured = {}

    def _capture_brief(brief, **kw):
        captured["concept"] = brief.campaign_concept
        return (_fake_spine(), 999)

    monkeypatch.setattr(gen, "generate_from_brief", _capture_brief)

    res = client.post("/campaign/generate", json={
        "premise": "A long premise that exceeds forty characters to force mode 2.",
        "character_id": "clovis_beryl",
    })
    assert res.status_code == 200, res.text
    assert "Clovis" in captured.get("concept", "")
