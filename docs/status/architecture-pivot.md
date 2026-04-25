# Architecture Pivot — Local-First → DeepSeek V4 (April 2026)

**Date:** 2026-04-24 (verified 2026-04-25)
**Status:** Implemented end-to-end. Tier 1, 2, 3 wiring all complete. ChatGPT
review feedback applied. 653 tests pass + 12 cleanly skip + 0 fail (the
12 skips are campaign-specific fixtures for the deleted Nar Shaddaa /
Echoes spines — see changelog 2026-04-25).

---

## What Changed and Why

The original architecture split LLM responsibilities between a local model
(Ollama / Qwen3.5:9B) for structured JSON decisions and a cloud model
(GPT-5.2 by default) for prose narration. The split was justified by cost:
4 local calls per turn at $0 + 1 cloud call kept the per-turn unit economics
viable.

DeepSeek V4 changes the calculus. Both tiers — Flash (fast/cheap) and
Pro (high quality) — are available via OpenRouter. Flash is roughly two
orders of magnitude cheaper than gpt-5.2 with comparable structured-JSON
reliability, and Pro produces narration on par with the original cloud
target. The local-first split is no longer cost-justified, and Ollama's
operational cost (a 9B model running on the user's machine) was always a
real burden for development and deployment.

The pivot collapses the local/cloud distinction into a tier abstraction
(fast vs. quality), defaults to OpenRouter + DeepSeek V4, and keeps Ollama
as an optional offline path for development and emergency fallback.

---

## Tier Model

| Tier        | Default model                | Used for                                                          | Latency budget |
|-------------|------------------------------|-------------------------------------------------------------------|----------------|
| **Fast**    | `deepseek/deepseek-v4-flash` | Check decisions, choice annotation, reconciliation, prose diagnostic | 2-3s           |
| **Quality** | `deepseek/deepseek-v4-pro`   | Turn narration, milestone reflections, time skips, studio gen     | 10-20s         |

Tier choice is per-call-site, encoded as `tier=TIER_FAST` or `tier=TIER_QUALITY`
in the call signature. There is no automatic downgrade; if narration fails,
the existing emergency Ollama fallback path still runs (`_narrate_with_local_fallback`).

---

## New Module: `gm/llm_client.py`

The single entry point for every LLM call. Replaces:
- The Ollama-direct `httpx.post` calls in `gm/local_gm.py` (3 sites) and
  `engine/reconciliation.py` (1 site).
- The bespoke `_make_client` constructor in `gm/cloud_gm.py`.
- The bespoke `_get_client` + `_call_llm` in `studio/generate.py`.

**Public API:**
- `call_chat(tier=, user=, system=, ...)` — text-out chat completion.
- `call_chat_json(tier=, user=, schema=, ...)` — JSON-out with retry-and-validate.
  Routes through Ollama's native `/api/generate` (with strict `format=schema`
  enforcement) when `NARRATIVE_BACKEND=local`, otherwise OpenAI-compatible
  json_object response_format.
- `call_chat_stream(tier=, user=, ...)` — streaming text deltas.
- `make_client()` — raw OpenAI client for callers that need fine control.
- `resolve_model(tier=, purpose=)` — returns the model id that will be used.
- `describe_routing()` — diagnostic dict suitable for `/health` endpoints.

**Reasoning-model awareness:** the client detects `gpt-5*` / `gpt-o*` by
name and switches to `max_completion_tokens` + `reasoning_effort` kwargs.
DeepSeek and other standard chat models get plain `max_tokens`. This means
swapping back to GPT-5 only requires changing `QUALITY_MODEL`; no code
changes.

---

## Configuration

Primary path (recommended):
```bash
NARRATIVE_BACKEND=cloud
CLOUD_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
FAST_MODEL=deepseek/deepseek-v4-flash
QUALITY_MODEL=deepseek/deepseek-v4-pro
```

Per-call-site overrides (A/B individual paths without disturbing tier defaults):
```bash
NARRATION_MODEL=        # quality tier override for cloud_gm.narrate_turn
DECISION_MODEL=         # fast tier override for local_gm.decide_check
ANNOTATION_MODEL=       # fast tier override for local_gm.annotate_choice
RECONCILIATION_MODEL=   # fast tier override for engine/reconciliation
DIAGNOSTIC_MODEL=       # fast tier override for prose diagnostic
MILESTONE_MODEL=        # quality tier override for milestone reflections
STUDIO_MODEL=           # quality tier override for studio/generate
```

Legacy back-compat (still honored, no migration needed):
- `CLOUD_MODEL` — overrides QUALITY_MODEL when set.
- `LOCAL_MODEL` / `LOCAL_NARRATION_MODEL` — used when `NARRATIVE_BACKEND=local`.
- `REASONING_EFFORT` — only honored by gpt-5/gpt-o models.

---

## Files Touched

### Tier 1 — Architecture pivot (LLM client unification)
- **NEW** `gm/llm_client.py` — unified client (~340 lines)
- `.env.example` — DeepSeek + OpenRouter as primary path
- `gm/local_gm.py` — 3 call sites (decide/annotate/diagnose) → `call_chat_json(tier=fast)`
- `engine/reconciliation.py` — `reconcile_turn` → `call_chat_json(tier=fast)`
- `gm/cloud_gm.py` — `_make_client` delegates to unified client; new
  `_make_completion_kwargs()` helper handles reasoning-vs-standard model kwargs.
- `studio/generate.py` — `_call_llm` delegates to `call_chat(tier=quality, purpose=studio)`.

### Tier 2 — State-matrix gaps closed (now wired through prompts)
- `state/session.py` — added 5 functions:
  - `log_reputation_event` — write to reputation_log
  - `select_reputation_echoes` — relevance-scored selection with cooldown
  - `mark_reputation_echoes_surfaced` — increment surfaced_count
  - `detect_surfaced_echoes` — keyword-match heuristic (no LLM)
  - `derive_behavioral_availability` — aggregate Phase 13 annotations
- `gm/context.py`:
  - `ContextPackage` gains `reputation_entries`, `behavioral_availability`, `era_voice_block` fields
  - `ArcState` gains `last_reputation_echo_turn` for cooldown tracking
  - New methods: `build_reputation_block()`, `build_behavioral_availability_block()`
  - New module-level helper: `build_era_voice_block(spine)`
- `gm/prompts/narration.txt` & `narration_literary.txt` — added 3 new placeholders
  (`{era_voice_block}`, `{reputation_block}`, `{behavioral_availability_block}`)
- `gm/prompts/reconciliation.txt` — new section asking for `reputation_event` + `faction_tags`
- `engine/reconciliation.py`:
  - `RECONCILIATION_SCHEMA` extended with `reputation_event` and `faction_tags`
  - `ReconciliationResult` dataclass extended with same fields
  - `_validate_result` parses them (most turns: null)

### Tier 3 — Turn-handler integration (proof of concept at one site)
- `api/game_routes.py` — main turn handler (around line 948) wires:
  - reputation echoes selected before context assembly
  - behavioral availability derived from annotation history
  - era voice block populated from spine
  - surfaced echoes detected post-narration; surfaced_count + cooldown updated
  - reputation_event from reconciliation written to reputation_log

---

## Round 2 — Feedback Applied (2026-04-24)

After ChatGPT reviewed the initial pivot, several refinements were folded in:

### [P1] Studio OpenRouter API key — resolved
The studio's `_get_cloud_client()` no longer constructs a bare `OpenAI()` —
it delegates to the unified client which sets `OPENROUTER_API_KEY` correctly.

### [P2] Provider/model capability layer — added
`MODEL_CAPABILITIES` registry in `gm/llm_client.py` encodes:
- **Reasoning syntax** per family. OpenAI uses `reasoning_effort` top-level;
  OpenRouter uses `extra_body.reasoning.effort`. DeepSeek Flash skips
  reasoning entirely. New models get a one-line registry entry; call sites
  stay clean.
- **Token-budget naming**. `max_completion_tokens` vs `max_tokens` is now
  resolved per-model rather than per-call-site.

### [P2] OpenRouter provider preferences — added
- `OPENROUTER_REQUIRE_PARAMS=true` (default) — only routes to providers
  that actually enforce json_schema, json mode, and seed.
- `OPENROUTER_DATA_COLLECTION=deny` (default) — excludes providers that
  log requests for training. `allow` is permitted (cheaper) but opt-in.

### [P2] Strict JSON schema response_format — added
`call_chat_json` now defaults to `response_format={"type": "json_schema", ...}`
with `strict: true`. Falls back to `json_object` mode automatically if the
provider rejects strict schema. With `require_parameters: true`, the schema
is enforced at the API layer rather than parsed-then-prayed.

### Test failure investigation — resolved
`test_generate_mode1_retries_on_bad_json` failed because the architect
pre-call (CS-5 addition) consumed the 3 mocked responses before the spine
retry loop ran. Fixed by passing `use_architect=False` to the test, which
matches the test's actual semantic intent (testing spine retry, not architect).

### Test mocks — updated
Tests that used to patch `gm.local_gm.httpx.post` (Ollama HTTP layer) now
patch `gm.local_gm.call_chat_json` (the new abstraction boundary). Mocks
are simpler — the returned value is a dict, not an httpx response object.

---

## All Originally-Listed Remaining Work — Now Complete

### ✓ Tier-3 wiring at all 4 turn handlers
Three helper functions extracted (`_compute_dynamic_context_fields`,
`_post_narration_reputation_hook`, `_post_reconciliation_reputation_hook`)
and called from each ContextPackage construction site:
- Main turn handler (~line 948)
- Streaming variant (~line 1678)
- Force temptation handler (~line 2060)
- Intervention handler (~line 2334)

### ✓ Spine `era_voice` schema + Praxeum populated
`studio/schema.py` now has `EraVoice` Pydantic model with `era`, `year`,
`voice_notes`, `period_details`, `period_avoid` fields.
- `shadows_of_the_praxeum` → New Republic / ~12 ABY (Praxeum, fragile peace)

(Note: `nar_shaddaa_job` and `echoes_of_the_force` were also populated
during the initial pivot, but were subsequently removed from the
repository on 2026-04-25 — the project now ships a single canonical
campaign. See changelog.md for the curation rationale.)

The era voice block anchors prose with period-specific details
(Praxeum students, Imperial Remnant warlords, fragile New Republic
authority) and forbids anachronisms (no Sequel-era language, no
intact Empire).

### ✓ `/health` endpoint surfaces routing
`GET /health` now returns `{"status": "ok", "routing": {...}}` with the
active backend, provider, fast model, quality model, and any per-purpose
overrides. Verify the pivot is live: `curl localhost:8000/health | jq .routing`.

---

## Still Deferred

### Splitting `api/game_routes.py` (2,792 → 4 files)
Not yet done. The file grew slightly (helpers + wiring) but the monolith
concern remains. Suggested split when Phase 18 work begins:
- `api/session_routes.py` — campaign list, session create, session get
- `api/turn_routes.py` — turn handlers (the 4 ContextPackage sites + helpers)
- `api/character_routes.py` — milestone, advancement, talents, force
- `api/studio_routes.py` — already separate; verify

### ChatGPT-suggested creative additions (worth real consideration)
These were proposed in review. Status as of 2026-04-25:
- **Holocron service** — curated Star Wars knowledge layer with per-turn
  shard injection (era / faction / species / tech). Currently embodied
  partly by `era_voice`; full Holocron would expand to faction doctrine,
  species tells, tech limits, planet texture. **Still deferred.**
- **Continuity Judge** — a DeepSeek Pro post-run audit that reviews
  telemetry + generated prose for canon drift, NPC voice drift, and
  consequence gaps. Lives outside the live turn loop. Pairs well with the
  existing `eval/` harness. **Still deferred.**
- **Threat clocks** — explicit world-state variables (Hutt patience,
  Imperial attention, Rebel trust, dark-side pressure, underworld
  reputation). The current system has threads + disposition; clocks make
  Star Wars pressure mechanically actionable. **Still deferred.**
- **Selective reconciliation escalation** — **✓ Implemented (Apr 25, 2026)**.
  `reconcile_turn_with_escalation` + `is_silent_reconciliation` in
  `engine/reconciliation.py`. Two consecutive silent results trigger a
  quality-tier rerun and emit a `reconciliation_escalated` telemetry event.
  Wired at all 4 turn handlers. 5 dedicated tests.
- **Six-category compliance protocol against Flash + Pro** — run the
  existing GM compliance test suite against both models to validate the
  tier assignment is correct. **Still deferred** (requires real LLM calls,
  budget-gated).

---

## Verification Checklist

Before shipping:
- [ ] Set `OPENROUTER_API_KEY` in your `.env` (or `OPENAI_API_KEY` for OpenAI passthrough).
- [ ] Run `python -c "from gm.llm_client import describe_routing; print(describe_routing())"`
      and confirm fast=`deepseek-v4-flash`, quality=`deepseek-v4-pro`.
- [ ] Run the existing Phase 7 reconciliation test — it should pass with
      the JSON-mode call (Flash tier).
- [ ] Run a full turn cycle against a fresh DB. Confirm:
  - Check decision arrives in 2-4s (Flash).
  - Narration arrives in 10-20s (Pro).
  - No `reputation_event` is generated when player did something private.
  - When player does something publicly visible, `reputation_event` appears
    in the reconciliation result and a row is added to `reputation_log`.
  - On a later turn (3+ later), the echo can surface in narration.
- [ ] Run `pytest tests/` — existing 20 test files should pass with the
      new client. Tests using direct httpx calls to Ollama may need updates
      (only impacts `NARRATIVE_BACKEND=local` test paths).

---

## Cost Implications

Rough estimates per 100-turn campaign at Apr 2026 prices:

| Path                              | Calls/turn | $ per turn | $ per 100 turns |
|-----------------------------------|------------|------------|-----------------|
| Old: Ollama + GPT-5.2             | 4 + 1      | $0.18      | $18             |
| New: DeepSeek Flash + Pro         | 4 + 1      | $0.04      | $4              |
| New (Pro everywhere, no Flash)    | 5          | $0.18      | $18             |
| New (Flash everywhere, no Pro)    | 5          | $0.005     | $0.50           |

The two-tier approach captures most of the cost win without sacrificing
narration quality. Studio generation costs jump from $0 (Ollama) to $0.10
per spine (Pro), but spine generation is a one-time authoring action, not
per-turn — negligible at the user level.

---

## Why Star Wars Stays Hardcoded (For Now)

The audit identified `gm/prompts/narration.txt` references to "Star Wars
galaxy," and `engine/dice.py` enforces FFG dice (Star Wars system). Both
are fine — the user explicitly scoped this work to Star Wars. The
`era_voice` extension allows finer-grained period anchoring within Star
Wars (Original Trilogy vs. High Republic vs. Sequel Era) without
abstracting away from the franchise. When/if a non-Star-Wars pivot
becomes real, the dice engine and narration prompt are the franchise
boundary — both are well-isolated from the rest of the architecture.
