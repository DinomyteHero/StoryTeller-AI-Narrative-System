"""
Funnel backend contract tests — hermetic, all LLM calls mocked.

Locks the API surface the player-funnel frontend is built against:
1. GET /campaigns entries carry ending_count + total_acts; *.meta.json
   sidecars never appear as campaigns
2. GET /funnel/seeds serves spark tables + premise seeds; missing files
   degrade to {} instead of 500
3. POST /campaign/generate returns generation_mode, writes the
   {slug}.meta.json provenance sidecar, and folds a prior session's
   ending into the brief ("Previously: ...")
4. GET /session/{id} carries the pending interstitial-state object
5. POST /session/{id}/epilogue carries ending_count + names-only
   ending_paths (no synopsis spoilers)
6. GET /sessions excludes fixture characters and retired campaigns
7. Rate limiting on /character/draft (env-derived limit, 0 disables)
8. state/telemetry.funnel_event appends JSON lines and never raises
"""

import copy
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

import api.character_routes as character_routes
import api.game_routes as game_routes
import state.telemetry as telemetry
import studio.generate as gen
import studio.persist as persist
import studio.validate as val
from api.ratelimit import SlidingWindowLimiter, limit_from_env
from engine.character import Character

REPO_ROOT = Path(__file__).parent.parent
CAMPAIGN_DIR = REPO_ROOT / "data" / "campaigns"
_SHADOWS = json.loads(
    (CAMPAIGN_DIR / "shadows_of_the_custodian.json").read_text(encoding="utf-8")
)


@pytest.fixture(autouse=True)
def _telemetry_tmp(tmp_path, monkeypatch):
    # Route calls emit real funnel events — keep them out of data/telemetry.
    monkeypatch.setattr(telemetry, "TELEMETRY_DIR", tmp_path / "telemetry")


def _client() -> TestClient:
    from api.main import app
    return TestClient(app)


def _character_json() -> str:
    path = REPO_ROOT / "data" / "characters" / "praxeum_student.json"
    return path.read_text(encoding="utf-8")


def _fake_spine(name="Generated Test Campaign") -> dict:
    """A real, schema-valid spine with the name overridden for slug assertions."""
    spine = copy.deepcopy(_SHADOWS)
    spine["name"] = name
    return spine


# ── 1. GET /campaigns — funnel scalars + sidecar exclusion ────────────

class TestListCampaigns:
    def test_entries_carry_ending_count_and_total_acts(self):
        res = _client().get("/campaigns")
        assert res.status_code == 200
        body = res.json()
        assert body, "expected at least one player-facing campaign"
        names = [c["campaign_name"] for c in body]
        assert "ledger_of_ossel_minor" in names
        for entry in body:
            assert isinstance(entry["ending_count"], int)
            assert isinstance(entry["total_acts"], int)
            assert not entry["campaign_name"].endswith(".meta")

    def test_sidecar_never_listed_as_campaign(self, tmp_path, monkeypatch):
        # Hermetic campaigns dir: one real campaign, its sidecar, and a
        # retired spine. Only the campaign may surface.
        campaigns = tmp_path / "data" / "campaigns"
        campaigns.mkdir(parents=True)
        (tmp_path / "data" / "characters").mkdir()
        (campaigns / "test_camp.json").write_text(json.dumps({
            "name": "Test Camp",
            "player_facing": True,
            "acts": [{}, {}, {}],
            "story_architecture": {
                "ending_paths": [
                    {"branch_id": "a", "name": "A"},
                    {"branch_id": "b", "name": "B"},
                ],
            },
        }), encoding="utf-8")
        (campaigns / "test_camp.meta.json").write_text(
            json.dumps({"premise": "sidecar", "mode": "2"}), encoding="utf-8",
        )
        (campaigns / "retired.json").write_text(
            json.dumps({"name": "Retired", "player_facing": False, "acts": []}),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        res = _client().get("/campaigns")
        assert res.status_code == 200
        body = res.json()
        assert [c["campaign_name"] for c in body] == ["test_camp"]
        assert body[0]["ending_count"] == 2
        assert body[0]["total_acts"] == 3


# ── 2. GET /funnel/seeds ───────────────────────────────────────────────

class TestFunnelSeeds:
    def test_seed_files_served_with_required_content(self):
        res = _client().get("/funnel/seeds")
        assert res.status_code == 200
        body = res.json()

        spark = body["spark_tables"]
        for table in ("species", "careers", "hooks", "flaws"):
            assert spark.get(table), f"spark table '{table}' missing/empty"

        seeds = body["premise_seeds"]
        eras = seeds.get("eras", [])
        assert len(eras) == 2
        for era in eras:
            era_seeds = seeds["seeds"][era["id"]]
            assert len(era_seeds) >= 12
            for s in era_seeds:
                assert isinstance(s, str) and len(s) >= 60

    def test_missing_files_degrade_to_empty_not_500(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # no data/funnel here
        monkeypatch.setattr(game_routes, "_funnel_seeds_cache", {})
        res = _client().get("/funnel/seeds")
        assert res.status_code == 200
        assert res.json() == {"spark_tables": {}, "premise_seeds": {}}


# ── 3. POST /campaign/generate — mode, sidecar, sequel hook ──────────

@pytest.fixture
def gen_client(monkeypatch, tmp_path):
    """Generate route with LLM generation + gates mocked (test_campaign_generate
    pattern) and its own campaigns dir + a fresh (non-shared) rate limiter."""
    monkeypatch.setattr(gen, "generate_mode1",
                        lambda inputs, **kw: (_fake_spine(), 12345))
    monkeypatch.setattr(gen, "generate_from_brief",
                        lambda brief, **kw: (_fake_spine(), 12345))
    monkeypatch.setattr(val, "validate_spine",
                        lambda spine, **kw: val.ValidationReport(passed=True, warnings=[]))
    monkeypatch.setattr(persist, "CAMPAIGNS_DIR", tmp_path)
    monkeypatch.setattr(game_routes, "GENERATE_LIMITER", SlidingWindowLimiter(0))
    return _client()


class TestCampaignGenerate:
    def test_mode2_returns_generation_mode_and_writes_sidecar(
        self, gen_client, tmp_path,
    ):
        premise = "A long premise that exceeds forty characters to force mode 2."
        res = gen_client.post("/campaign/generate", json={
            "premise": premise,
            "character_id": "kessa_rhane",
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["campaign_name"] == "generated_test_campaign"
        assert body["generation_mode"] == "2"

        meta = json.loads(
            (tmp_path / "generated_test_campaign.meta.json").read_text(encoding="utf-8")
        )
        assert meta["premise"] == premise
        assert meta["mode"] == "2"
        assert meta["character_id"] == "kessa_rhane"
        assert meta["prior_session_id"] is None
        assert meta["surprise_me"] is False
        assert isinstance(meta["era"], str) and meta["era"]

    def test_mode1_sidecar_records_mode_1(self, gen_client, tmp_path):
        res = gen_client.post("/campaign/generate", json={
            "premise": "", "era": "X", "location": "Y",
        })
        assert res.status_code == 200, res.text
        assert res.json()["generation_mode"] == "1"
        meta = json.loads(
            (tmp_path / "generated_test_campaign.meta.json").read_text(encoding="utf-8")
        )
        assert meta["mode"] == "1"

    def test_prior_session_ending_folded_into_brief(
        self, gen_client, tmp_path, monkeypatch,
    ):
        prior = {
            "arc_state_json": json.dumps({
                "campaign_complete": True,
                "epilogue": {
                    "ending_name": "The Long Road",
                    "epilogue": "You walk out under two moons. " * 20,
                },
            }),
        }
        monkeypatch.setattr(game_routes, "get_session", lambda sid: prior)

        captured = {}

        def _capture_brief(brief, **kw):
            captured["concept"] = brief.campaign_concept
            return (_fake_spine(), 999)

        monkeypatch.setattr(gen, "generate_from_brief", _capture_brief)

        res = gen_client.post("/campaign/generate", json={
            "premise": "A long premise that exceeds forty characters to force mode 2.",
            "prior_session_id": "prior-session-id",
        })
        assert res.status_code == 200, res.text
        concept = captured["concept"]
        assert "Previously: The Long Road — " in concept
        assert "You walk out under two moons." in concept

        meta = json.loads(
            (tmp_path / "generated_test_campaign.meta.json").read_text(encoding="utf-8")
        )
        assert meta["prior_session_id"] == "prior-session-id"


# ── 4. GET /session/{id} — pending interstitial states ────────────────

class TestSessionPending:
    def test_pending_object_aggregates_arc_state_flags(self):
        fake_session = {
            "campaign_name": "x",
            "character_json": _character_json(),
            "arc_state_json": json.dumps({
                "current_act": 2,
                "pending_milestone": {"choices": []},
                "pending_intervention": None,
                "pending_temptation": {"offer": "power"},
                "pending_time_skip": False,
            }),
            "destiny_light": 2,
            "destiny_dark": 1,
        }
        with patch.object(game_routes, "get_session", return_value=fake_session), \
             patch.object(game_routes, "get_recent_turns", return_value=[]), \
             patch.object(game_routes, "get_turn_count", return_value=0), \
             patch.object(game_routes, "load_campaign_spine",
                          return_value={"name": "X", "total_acts": 4}):
            res = _client().get("/session/test-id")
        assert res.status_code == 200
        assert res.json()["pending"] == {
            "milestone": True,
            "intervention": False,
            "temptation": True,
            "time_skip": False,
        }


# ── 5. POST /session/{id}/epilogue — ending space, spoiler-free ──────

class TestEpilogueEndingSpace:
    def test_response_carries_ending_count_and_names_only_paths(self):
        spine = {
            "name": "Test Campaign",
            "throughline_question": "Can they go home?",
            "story_architecture": {
                "ending_paths": [
                    {"branch_id": "walk_away", "name": "The Long Road",
                     "synopsis": "They walk away.", "thematic_payoff": "Freedom costs"},
                    {"branch_id": "stay_and_fight", "name": "The Stand",
                     "synopsis": "They hold the line.", "thematic_payoff": "Roots cost"},
                ],
            },
        }
        fake_session = {
            "campaign_name": "x",
            "character_json": _character_json(),
            "arc_state_json": json.dumps({"campaign_complete": True}),
        }
        with patch.object(game_routes, "get_session", return_value=fake_session), \
             patch.object(game_routes, "load_campaign_spine", return_value=spine), \
             patch.object(game_routes, "get_act_summaries", return_value="summary"), \
             patch.object(game_routes, "get_recent_turns", return_value=[]), \
             patch.object(game_routes, "get_turn_count", return_value=42), \
             patch.object(game_routes, "classify_ending_branch",
                          return_value="walk_away"), \
             patch.object(game_routes, "load_npc_states", return_value=[]), \
             patch.object(game_routes, "update_session_state"), \
             patch.object(game_routes, "generate_epilogue",
                          return_value={"epilogue": "It is finished.",
                                        "ending_name": "The Long Road"}):
            res = _client().post("/session/test-id/epilogue")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["ending_count"] == 2
        assert body["ending_branch_id"] == "walk_away"
        assert body["ending_paths"] == [
            {"branch_id": "walk_away", "name": "The Long Road"},
            {"branch_id": "stay_and_fight", "name": "The Stand"},
        ]
        for ep in body["ending_paths"]:
            assert set(ep.keys()) == {"branch_id", "name"}


# ── 6. GET /sessions — resume picker listing ──────────────────────────

class TestListSessions:
    def test_listing_shape_and_fixture_exclusion(self):
        rows = [
            {
                "id": "s-good",
                "campaign_name": "ledger_of_ossel_minor",
                "character_json": json.dumps({"name": "Kessa Rhane"}),
                "arc_state_json": json.dumps(
                    {"variant_id": "kessa_rhane", "current_act": 2}
                ),
                "updated_at": "2026-07-01T12:00:00+00:00",
                "turn_count": 14,
            },
            {   # fixture character — must be excluded
                "id": "s-fixture",
                "campaign_name": "ledger_of_ossel_minor",
                "character_json": json.dumps({"name": "Clovis Beryl"}),
                "arc_state_json": json.dumps({"variant_id": "clovis_beryl"}),
                "updated_at": "2026-07-01T11:00:00+00:00",
                "turn_count": 3,
            },
            {   # retired (player_facing=False) campaign — must be excluded
                "id": "s-retired",
                "campaign_name": "shadows_of_the_custodian",
                "character_json": json.dumps({"name": "Someone New"}),
                "arc_state_json": json.dumps({"variant_id": "someone_new"}),
                "updated_at": "2026-07-01T10:00:00+00:00",
                "turn_count": 8,
            },
        ]
        with patch.object(game_routes, "list_recent_sessions", return_value=rows):
            res = _client().get("/sessions?limit=20")
        assert res.status_code == 200
        body = res.json()
        assert [s["session_id"] for s in body] == ["s-good"]
        entry = body[0]
        assert set(entry.keys()) == {
            "session_id", "campaign_name", "campaign_display_name",
            "character_name", "turn_count", "current_act", "total_acts",
            "campaign_complete", "last_played",
        }
        assert entry["campaign_name"] == "ledger_of_ossel_minor"
        assert isinstance(entry["campaign_display_name"], str)
        assert entry["campaign_display_name"]
        assert entry["character_name"] == "Kessa Rhane"
        assert entry["turn_count"] == 14
        assert entry["current_act"] == 2
        assert isinstance(entry["total_acts"], int)
        assert entry["campaign_complete"] is False
        assert entry["last_played"] == "2026-07-01T12:00:00+00:00"


# ── 7. Rate limiting — /character/draft ───────────────────────────────

class TestDraftRateLimit:
    def _client_with_limit(self, monkeypatch, env_value: str) -> TestClient:
        monkeypatch.setenv("FUNNEL_DRAFT_LIMIT_PER_HOUR", env_value)
        # The module-level limiter was built at import time — rebuild it
        # from the (patched) environment, exactly as the module does.
        monkeypatch.setattr(
            character_routes, "DRAFT_LIMITER",
            SlidingWindowLimiter(limit_from_env("FUNNEL_DRAFT_LIMIT_PER_HOUR", 30)),
        )
        monkeypatch.setattr(
            character_routes, "draft_character",
            lambda pitch, hints=None: {"name": "Test Draft"},
        )
        return _client()

    def test_third_draft_hits_429(self, monkeypatch):
        client = self._client_with_limit(monkeypatch, "2")
        for _ in range(2):
            assert client.post(
                "/character/draft", json={"pitch": "a scoundrel"}
            ).status_code == 200
        res = client.post("/character/draft", json={"pitch": "a scoundrel"})
        assert res.status_code == 429
        assert "hour" in res.json()["detail"]

    def test_zero_disables_limit(self, monkeypatch):
        client = self._client_with_limit(monkeypatch, "0")
        for _ in range(5):
            assert client.post(
                "/character/draft", json={"pitch": "a scoundrel"}
            ).status_code == 200

    def test_limit_from_env_semantics(self, monkeypatch):
        monkeypatch.setenv("FUNNEL_DRAFT_LIMIT_PER_HOUR", "7")
        assert limit_from_env("FUNNEL_DRAFT_LIMIT_PER_HOUR", 30) == 7
        monkeypatch.setenv("FUNNEL_DRAFT_LIMIT_PER_HOUR", "garbage")
        assert limit_from_env("FUNNEL_DRAFT_LIMIT_PER_HOUR", 30) == 30
        monkeypatch.delenv("FUNNEL_DRAFT_LIMIT_PER_HOUR")
        assert limit_from_env("FUNNEL_DRAFT_LIMIT_PER_HOUR", 30) == 30

    def test_sliding_window_limiter_recovers_after_window(self):
        limiter = SlidingWindowLimiter(1, window_seconds=0.0)
        assert limiter.allow("k") is True
        # Zero-length window: the first hit has already aged out.
        assert limiter.allow("k") is True


# ── 8. Telemetry — funnel_event ────────────────────────────────────────

class TestFunnelEvent:
    def test_writes_json_line(self, tmp_path, monkeypatch):
        monkeypatch.setattr(telemetry, "TELEMETRY_DIR", tmp_path)
        telemetry.funnel_event("character_draft", ok=True, duration_s=1.2)
        telemetry.funnel_event("session_create", campaign="ledger")

        lines = (tmp_path / "funnel_events.jsonl").read_text(
            encoding="utf-8"
        ).strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["event"] == "character_draft"
        assert first["ok"] is True
        assert first["duration_s"] == 1.2
        assert "timestamp" in first
        assert json.loads(lines[1])["campaign"] == "ledger"

    def test_never_raises_on_bad_path(self, tmp_path, monkeypatch):
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        monkeypatch.setattr(telemetry, "TELEMETRY_DIR", blocker / "sub")
        telemetry.funnel_event("epilogue", ending_branch_id="walk_away")

    def test_never_raises_on_unserializable_field(self, tmp_path, monkeypatch):
        monkeypatch.setattr(telemetry, "TELEMETRY_DIR", tmp_path)
        telemetry.funnel_event("session_create", obj=object())
        line = (tmp_path / "funnel_events.jsonl").read_text(encoding="utf-8")
        assert json.loads(line)["event"] == "session_create"
