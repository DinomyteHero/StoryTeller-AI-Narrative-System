# Game Engine API Reference

> **Tier:** API Reference
> **Status:** CURRENT
> **Last updated:** 2026-06-09
> **Authoritative for:** Game Engine HTTP endpoints, request/response schemas
> **Source files:** `api/game_routes.py`, `api/character_routes.py`

Base URL: `http://localhost:8000`

---

## Health Check

### GET /health

Returns server status.

**Response:** `{"status": "ok"}`

---

## Campaign Discovery

### GET /campaigns

List available campaigns with their character variants.

**Response:**
```json
[
  {
    "campaign_name": "nar_shaddaa_job",
    "display_name": "The Nar Shaddaa Job",
    "era": "Galactic Civil War",
    "throughline": "What are you willing to become to survive?",
    "characters": [
      {
        "id": "keth_varso_smuggler",
        "name": "Keth Varso",
        "pitch": "A street-smart smuggler...",
        "career": "Smuggler",
        "species": "Human"
      }
    ]
  }
]
```

---

## Session Management

### POST /session

Create a new game session with opening narration.

**Request:**
```json
{
  "campaign_name": "nar_shaddaa_job",
  "character_id": "keth_varso_smuggler"
}
```

**Response:**
```json
{
  "session_id": "uuid-string",
  "opening_narration": "The docking bay smells of...",
  "choices": ["Approach the contact", "Scout the perimeter", "..."],
  "streaming_enabled": true
}
```

### GET /session/{session_id}

Load complete session state. When the player has 3+ turns and the
campaign is still live, this also generates (and caches per turn-count)
an 80-150 word "story so far" `recap` for re-entry — fail-open, gated
by `RESUME_RECAP_ENABLED`.

**Response:**
```json
{
  "session_id": "...",
  "campaign_name": "nar_shaddaa_job",
  "turn_count": 5,
  "streaming_enabled": true,
  "campaign_complete": false,
  "epilogue": null,
  "recap": "You came back to the docking bay with the manifest...",
  "total_acts": 4,
  "destiny": {"light_remaining": 2, "dark_remaining": 1},
  "session_state": {
    "wounds": 0, "strain": 2,
    "current_act": 2, "current_location": "..."
  },
  "arc_state": { "...": "..." },
  "character": { "...": "full character object..." },
  "recent_turns": [ "..." ],
  "last_turn": {
    "narration": "...", "choices": ["..."],
    "check_skill": null, "roll_result": null
  }
}
```

### POST /session/{session_id}/epilogue

Generate (or return the cached) campaign epilogue. Only valid once the
final act's anchor has resolved (`campaign_complete` is true) — returns
400 otherwise. Generated once via the quality tier, then cached in
arc_state; repeat calls return the cached payload. The model selects the
best-matching authored ending from the spine's
`story_architecture.ending_paths`.

**Response:**
```json
{
  "epilogue": "Three weeks later, the Praxeum kitchens still...",
  "ending_name": "The Open Door",
  "campaign_name": "shadows_of_the_custodian",
  "character_name": "Clovis Beryl",
  "turns_played": 104
}
```

---

## Turn Handling

### POST /session/{session_id}/turn

Execute a game turn. Core game loop: resolve choice, decide check,
roll dice, generate narration, reconcile state.

**Request:**
```json
{
  "choice_index": 0
}
```

**Response:**
```json
{
  "narration": "You step forward and...",
  "choices": ["Press the advantage", "Fall back", "Negotiate"],
  "dice_result": {
    "pool": "2P 1A vs 2D",
    "symbols": {"success": 2, "advantage": 1},
    "outcome_label": "Success with Advantage"
  },
  "roll_summary": "Success with Advantage",
  "session_state": {
    "wounds": 0, "strain": 3, "turn_number": 6,
    "act_progress": 0.5, "anchor_proximity": "approaching",
    "current_act": 2, "total_acts": 4
  },
  "act_boundary": false,
  "campaign_complete": false,
  "destiny": {
    "light_spent": false, "dark_spent": false,
    "light_remaining": 2, "dark_remaining": 1
  },
  "milestone": null,
  "force_power_milestone": null,
  "time_skip": null
}
```

`dice_result` and `roll_summary` are null when no check was required.
`milestone`, `force_power_milestone`, and `time_skip` are present only
at act boundaries when applicable. When `campaign_complete` is true the
story has ended — fetch the finale via `POST /epilogue`; further turn
requests return **409**.

### POST /session/{session_id}/turn/stream

SSE streaming variant of turn handler. Same request as `/turn`.

**Events:**
- `data: {"text": "chunk..."}` — Narration text chunks
- `event: temptation` — Dark side temptation offer
- `event: intervention` — Talent intervention offer
- `event: done` — Complete turn payload (same shape as `/turn` response)
- `event: error` — Error message

---

## Force Mechanics

### POST /session/{session_id}/temptation

Accept or reject dark side temptation during Force power use.

**Request:**
```json
{
  "accept": true
}
```

**Response:** Same shape as `/turn` response, plus:
```json
{
  "temptation_accepted": true,
  "force_result": {
    "force_succeeded": true,
    "conflict_earned": 2,
    "strain_charged": 0
  }
}
```

### POST /session/{session_id}/commitment

Commit or release a Force die for sustained power effects.

**Request:**
```json
{
  "power_id": "enhance",
  "upgrade_id": "enhance_brawn",
  "release": false
}
```

**Response:**
```json
{
  "action": "committed",
  "power_id": "enhance",
  "upgrade_id": "enhance_brawn",
  "force_committed": 1,
  "force_available": 1,
  "active_commitments": [
    {"power_id": "enhance", "upgrade_id": "enhance_brawn"}
  ]
}
```

---

## Talent and Advancement

### POST /session/{session_id}/intervention

Accept or decline a talent intervention offer (reroll dice at strain
cost).

**Request:**
```json
{
  "accept": true
}
```

**Response:** Same shape as `/turn` response, plus
`"intervention_used": true`.

### POST /session/{session_id}/milestone

Select a talent at an act boundary milestone.

**Request:**
```json
{
  "choice_index": 0
}
```

**Response:**
```json
{
  "acquired": {
    "talent_ref": "streetwise_3",
    "talent_name": "Black Market Contacts",
    "branch_theme": "Underworld Connections",
    "xp_cost": 15
  },
  "character_state": {
    "reserved_xp": 10,
    "acquired_talents": ["..."],
    "wound_threshold": 12,
    "strain_threshold": 13
  }
}
```

### POST /session/{session_id}/force_power_milestone

Select a Force power upgrade at an act boundary.

**Request:**
```json
{
  "choice_index": 0
}
```

**Response:**
```json
{
  "acquired": {
    "power_id": "move",
    "power_name": "Move",
    "upgrade_id": "move_strength_1",
    "upgrade_name": "Strength",
    "upgrade_type": "strength",
    "xp_cost": 10
  },
  "character_state": {
    "reserved_xp": 5,
    "force_powers": {"move": {"upgrades": ["..."]}}
  }
}
```

---

## Time Skips

### POST /session/{session_id}/vignette

Handle a vignette choice during a time skip sequence.

**Request:**
```json
{
  "choice_index": 1
}
```

**Response (mid-sequence):**
```json
{
  "vignette_id": "vignette_2",
  "choice_index": 1,
  "narrative_consequence": "Your decision echoes...",
  "is_complete": false,
  "next_vignette": {
    "id": "vignette_3",
    "passage": "Years pass...",
    "choices": ["...", "..."]
  }
}
```

**Response (final):**
```json
{
  "vignette_id": "vignette_3",
  "choice_index": 0,
  "narrative_consequence": "...",
  "is_complete": true,
  "closing_passage": "The years have changed you...",
  "effects_summary": {
    "skill_tags": ["Deception", "Streetwise"],
    "npc_effects": [{"npc": "Grev", "disposition_shift": 0.1}],
    "conflict": 0,
    "morality_bonus": 0
  }
}
```

---

## Character Creation (`api/character_routes.py`)

The create-your-own-hero flow: prose pitch → editable draft →
saved character → generated campaign → normal `POST /session`.

### POST /character/draft

LLM-draft a character stat block from a prose pitch (fast tier).

**Request:** `{"pitch": "A jaded ex-Imperial slicer who defected..."}`
(1-2000 chars)

**Response:** `{"draft": {...}}` — name, species, archetype_concept,
characteristics, skills, signature_talents, narrative_arc (lie / ghost /
want / need), voice_notes, starting_loadout.

### POST /character/save

Validate and persist an (edited) draft to `data/characters/{slug}.json`.
Deterministic assembly clamps characteristics/skills to bounds, derives
wound/strain thresholds, and validates every signature talent.

**Request:** `{"character_json": {...draft...}}`

**Response:** `{"character_id": "slug"}` — 422 with an `errors` list on
validation failure.

### GET /character/{character_id}

Load a saved character JSON.

### POST /campaign/generate

Generate a campaign spine on demand (Studio Mode 1/2), validate it
through the four-gate suite, and write it to `data/campaigns/`. Play
then starts via the existing `POST /session` with the returned
`campaign_name` and the creator's `character_id`.

**Request:**
```json
{
  "premise": "optional hook",
  "era": "optional era",
  "location": "optional location",
  "use_architect": false,
  "character_id": "slug-from-character-save"
}
```

**Response:** `{"campaign_name": "...", "display_name": "...",
"seed": 1234, "warnings": ["..."]}`
