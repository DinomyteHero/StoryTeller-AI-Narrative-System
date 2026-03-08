# Phase 18: Psychometric Prologue — Implementation Plan

## Context

Before the main game loop starts, players currently pick a pre-built character from a JSON file. Phase 18 replaces this with a **psychometric prologue**: a 3-5 scene interactive sequence that infers the player's behavioral profile and produces a mechanically configured character. The prologue is invisible inference — the player experiences story scenes with narrative choices, not a personality quiz.

Three inference layers:
- **Layer 1** (pure Python): Track 4 behavioral axes from tagged choices, compute confidence, detect contradictions
- **Layer 2** (hand-authored JSON): Map behavioral cluster to stat/skill profile via career-type mapping table
- **Layer 3** (single cloud LLM call): Infer motivation subtype, throughline question, voice notes

The resulting Character is identical (same Pydantic model, same session creation path) to a hand-built character.

---

## Step 1: Schema Extensions

**Files:** `studio/schema.py`

Add to `PrologueScene`:
- `scene_pressure: str` — constrained to "crisis" | "social" | "moral" | "strategic" (optional with default, so existing data doesn't break)
- `library_reusable: bool = True`

Add to `CharacterVariant`:
- `default_behavioral_lean: dict[str, str] = {}` — axis tie-breaking defaults (keys: approach/social/risk/moral)
- `default_throughline: str = ""` — fallback throughline question
- `default_voice_notes: str = ""` — fallback voice notes (max 300 chars)

All new fields have defaults so existing campaign spines continue to load.

**Verify:** Construct models with new fields in a test, confirm existing spine JSON still validates.

---

## Step 2: Core Inference Engine — Layer 1

**Files:** `engine/prologue.py` (NEW)

Pure Python, zero LLM dependencies (Rule 3). Contains:

**Dataclasses:**
- `AxisSignal` — `axis`, `positive_count`, `negative_count`, `total`; properties: `confidence` (0.0-1.0), `direction`, `is_clear`
- `ContradictionProfile` — `axis`, `primary_context`, `primary_direction`, `secondary_context`, `secondary_direction`
- `PrologueState` — four `AxisSignal` objects, scene choices made, scenes played, contradiction profiles
- `BehavioralArchetype` — four resolved axis directions

**Functions:**
- `init_prologue_state()` → fresh PrologueState
- `record_choice(state, scene, choice_index)` → updated PrologueState (accumulates axis tags)
- `evaluate_termination(state)` → bool (3 rules: all strong; all moderate + 4 scenes; 5 scenes)
- `select_next_scene(state, available_scenes, played_ids)` → PrologueScene (targets weakest axis, avoids repeated patterns)
- `randomize_choices(choices)` → (shuffled_choices, index_mapping) (anti-gaming)
- `detect_contradictions(state, scene_history)` → list[ContradictionProfile]
- `resolve_axes(state, contradictions, default_lean)` → BehavioralArchetype

Follows the `engine/advancement.py` pattern: dataclasses for intermediate results, pure functions that transform data.

**Verify:** Unit tests with mock scenes and known axis tags. Test all three termination conditions, contradiction detection, tie-breaking to variant defaults.

---

## Step 3: Core Inference Engine — Layer 2

**Files:** `engine/prologue.py` (extend), `data/prologue/career_type_mapping_tables/guardian.json` (NEW)

**Add to engine/prologue.py:**
- `load_mapping_table(career: str)` → loads from `data/prologue/career_type_mapping_tables/{career}.json`
- `select_profile(archetype, mapping_table)` → matches cluster to closest profile entry; tie-break by highest characteristic spread
- `build_character_from_prologue(variant_data, profile, layer3_result)` → `Character` Pydantic object with all fields populated

**guardian.json structure:**
```json
{
  "career": "guardian",
  "profiles": [
    {
      "cluster": {"approach": "direct", "social": "trusting", "risk": "bold", "moral": "principled"},
      "profile_name": "Stalwart Defender",
      "characteristics": {"brawn": 3, "agility": 2, "intellect": 2, "cunning": 2, "willpower": 3, "presence": 3},
      "skills": {"discipline": 2, "resilience": 2, "lightsaber": 2, ...},
      ...
    },
    ...8-12 profiles total...
  ]
}
```

Profiles vary around the Talia Ren baseline (Willpower 4, Presence 3) by 1-2 points depending on behavioral cluster.

**Verify:** Load table, pass known archetype, get valid profile. `build_character_from_prologue()` returns a Character that round-trips through `Character.model_validate()`.

---

## Step 4: Prologue Scene Data

**Files:** `data/campaigns/echoes_of_the_force.json` (modify)

Add to each character variant:
- `default_behavioral_lean` (e.g., Talia: `{"approach": "indirect", "social": "trusting", "risk": "cautious", "moral": "principled"}`)
- `default_throughline` (reuse the campaign's throughline_question)
- `default_voice_notes` (reuse the existing voice_baseline)

Add `prologue_scenes` array to the campaign spine with a `PrologueSet` for Talia Ren containing 5 scenes:

| Scene | Pressure | Axes Tested | Theme |
|-------|----------|-------------|-------|
| 1 | crisis | approach + risk | Imperial patrol forces a split-second decision |
| 2 | social | social + moral | Settler asks for help with a dispute |
| 3 | moral | moral + risk | Force vision reveals someone in danger |
| 4 | strategic | approach + social | Planning an escape route |
| 5 | crisis | all four | Inquisitor's agent arrives |

Each scene has 3 choices with distinct axis tag combinations. All 4 axes tagged in ≥3 scenes. ≥3 scene_pressure types represented.

**Verify:** Load spine, validate against updated Pydantic models. Check axis coverage and pressure diversity.

---

## Step 5: Layer 3 — Cloud LLM Identity Inference

**Files:** `gm/prompts/prologue_identity.txt` (NEW), `gm/cloud_gm.py` (modify)

**Prompt template** receives: variant definition, resolved archetype, contradiction profiles, full choice history, motivation possible_types list. Instructs LLM to return structured JSON with `motivation_subtype`, `throughline_question`, `voice_notes`.

**Add to cloud_gm.py:**
- `generate_prologue_identity(variant, archetype, contradictions, choice_history)` → dict
- `_parse_prologue_identity_response(raw, variant)` → validates: subtype in possible_types, throughline ends with "?", voice_notes ≤100 words

Follows `generate_milestone_reflection()` pattern: load template → format → `_make_client()` → `chat.completions.create()` → parse → retry once → fallback to variant defaults.

**Verify:** Unit test validation logic with mock responses. Integration test with real LLM call for Talia Ren.

---

## Step 6: Prologue API Endpoints

**Files:** `api/game_routes.py` (modify)

Three new endpoints, prologue state held in-memory (dict keyed by UUID):

1. **`POST /prologue/start`** — `{campaign_name, variant_id}` → loads spine, finds variant + prologue scenes, selects first scene, returns scene situation + shuffled choices (no axis tags exposed)
2. **`POST /prologue/{id}/choice`** — `{choice_index}` → records choice, updates state, evaluates termination. Returns next scene OR `{complete: true, character_summary}` with Layer 1→2→3 results
3. **`POST /prologue/{id}/confirm`** — creates session using the prologue-built Character via the existing session creation logic (NPC init, destiny roll, opening narration). Returns same response structure as `POST /session`

Extend `GET /campaigns` to include `has_prologue: true/false` per character.

`POST /session` remains unchanged for pre-built characters (backward compatible).

**Verify:** Call all three endpoints in sequence. Confirm the returned session plays identically to a pre-built character session.

---

## Step 7: Frontend — Funnel UI

**Files:** `web/index.html` (modify)

Three new UI states within the single-file frontend:

**7a — Campaign picker enhancement:** If selected character has prologue, button says "Begin Prologue" and enters prologue flow. If no prologue, "Begin Campaign" enters existing direct flow.

**7b — Prologue scene screen:** Situation text in `.passage` style, choice buttons in `.choice-btn` style. Progress indicator ("Scene 1 of 3-5"). No dice panel or status bar. On choice click → POST /prologue/{id}/choice → render next scene or transition to reveal.

**7c — Character reveal screen:** Character name, species, career, throughline question, voice notes. "Begin Campaign" button calls POST /prologue/{id}/confirm → transitions to game screen with opening narration.

**7d — Loading states:** "Your character takes shape..." during Layer 3 inference, "The story begins..." during session creation.

**Verify:** Manual walkthrough: Echoes of the Force → Talia Ren → 3-5 prologue scenes → reveal → campaign starts. Also verify: Nar Shaddaa Job → Keth Varso → direct start (no prologue, no regression).

---

## Step 8: End-to-End Integration

**Verify all 5 success criteria:**
1. Funnel UI presents Allegiance and Variant steps
2. 3-5 prologue scenes present choices with hidden axis tags
3. Behavioral archetype computed from axis tag patterns
4. Mechanical profile selected from career-type mapping table
5. Resulting character indistinguishable from hand-built character

**Additional tests:**
- Prologue-built character produces correct dice pools in gameplay
- Voice notes and throughline appear in narration prompt context
- Motivation track initialized correctly
- Edge case: 5 scenes with ambiguous signals → falls back to variant defaults
- Edge case: Abandon prologue mid-flow → no orphaned state

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Prologue scenes in campaign spine JSON | Schema already has `CampaignSpine.prologue_scenes`; keeps data co-located |
| Mapping tables in separate files | Reusable across campaigns (like talent trees under `data/talent_trees/`) |
| In-memory prologue state (no DB) | Prologue is 3-5 scenes, ephemeral; restart on browser close is fine |
| Prologue builds Character in memory | No file written to disk; serialized directly into session table |
| Timeline step is implicit | Selecting a campaign = selecting a timeline; no separate UI step needed |
| Nar Shaddaa Job remains prologue-free | Phase 18 validates with Echoes of the Force only |

---

## Critical File Paths

| File | Role |
|------|------|
| `engine/prologue.py` | NEW — Core inference (Layer 1 + 2), character construction |
| `studio/schema.py` | MODIFY — scene_pressure, default_behavioral_lean/throughline/voice_notes |
| `gm/cloud_gm.py` | MODIFY — generate_prologue_identity() (Layer 3) |
| `gm/prompts/prologue_identity.txt` | NEW — Layer 3 prompt template |
| `data/prologue/career_type_mapping_tables/guardian.json` | NEW — Guardian behavioral cluster → stats mapping |
| `data/campaigns/echoes_of_the_force.json` | MODIFY — prologue scenes + variant defaults |
| `api/game_routes.py` | MODIFY — 3 prologue endpoints |
| `web/index.html` | MODIFY — funnel UI, scene screen, reveal screen |
