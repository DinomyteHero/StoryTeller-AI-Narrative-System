# Campaign Studio API Reference

> **Tier:** API Reference
> **Status:** CURRENT
> **Last updated:** 2026-04-08
> **Authoritative for:** Campaign Studio HTTP endpoints, request/response schemas
> **Source file:** `api/studio_routes.py`

Base URL: `http://localhost:8000/studio`

---

## Validation

### POST /studio/spine/validate

Validate a campaign spine against all gates. Accepts partial spines
for early feedback during authoring.

**Request:**
```json
{
  "spine_data": { "...": "campaign spine JSON" }
}
```

**Response:**
```json
{
  "passed": true,
  "errors": [],
  "warnings": [
    {"gate": "gate4", "code": "cs6_pinch_coverage", "message": "...", "path": "acts[2]"}
  ],
  "gates_passed": ["gate1", "gate2", "gate3", "gate4"],
  "difficulty_curve": {
    "per_act_scores": [2.1, 3.4, 4.0, 3.8],
    "composite": 3.3,
    "shape": "rising",
    "warnings": []
  }
}
```

### POST /studio/spine/gaps

Identify structural gaps in a partially-built spine. Pure Python
analysis, no LLM calls.

**Request:**
```json
{
  "spine_data": { "...": "partial spine" }
}
```

**Response:**
```json
{
  "gaps": [
    {"field": "acts[2].galactic_context", "issue": "empty"},
    {"field": "npcs[1].voice_notes", "issue": "missing"}
  ],
  "total": 2
}
```

### POST /studio/spine/finalize

Parse, attach generation metadata, validate, and finalize a campaign
spine for storage.

**Request:**
```json
{
  "spine_data": { "...": "complete spine" },
  "master_seed": 42,
  "model_used": "gpt-5.2"
}
```

**Response:**
```json
{
  "spine": { "...": "validated CampaignSpine as JSON" },
  "validation_report": { "passed": true, "errors": [], "...": "..." }
}
```

---

## AI-Assisted Authoring

### POST /studio/assist/context

Generate galactic context draft for a specific act (Mode 3 assistance).

**Request:**
```json
{
  "spine_data": { "...": "spine with acts" },
  "act_number": 2,
  "master_seed": null
}
```

**Response:**
```json
{
  "act_number": 2,
  "galactic_context": "The Empire's grip on the Outer Rim tightens..."
}
```

### POST /studio/assist/voice

Generate NPC voice notes describing speech patterns.

**Request:**
```json
{
  "npc_data": {
    "name": "Grev Torlo",
    "motivation": "Profit above all",
    "role_in_act": "Information broker",
    "behavioral_envelope": "cautious, transactional"
  },
  "era": "Galactic Civil War",
  "location": "Nar Shaddaa",
  "master_seed": null
}
```

**Response:**
```json
{
  "npc_name": "Grev Torlo",
  "voice_notes": "Clips words short. Drops pronouns when..."
}
```

---

## Spine Generation

### POST /studio/generate/mode2

Generate a complete campaign spine from a thematic brief (Mode 2:
collaborative AI + human review).

**Request:**
```json
{
  "era": "Galactic Civil War",
  "location": "Nar Shaddaa",
  "tone": "gritty noir",
  "throughline_question": "What are you willing to become to survive?",
  "campaign_concept": "A smuggler caught between the Rebellion and a Hutt cartel",
  "moral_register": "morally gray",
  "total_acts": 4,
  "constraints": "",
  "master_seed": null
}
```

**Response:**
```json
{
  "spine_data": { "...": "generated CampaignSpine" },
  "master_seed": 12345,
  "gaps": []
}
```

### POST /studio/generate/mode1

Generate a complete campaign spine from minimal input (Mode 1: fully
autonomous).

**Request:**
```json
{
  "era": "New Republic",
  "location": "Coruscant underlevels",
  "tone": "gritty",
  "moral_register": "morally gray",
  "negative_archetype": "standard hero's journey",
  "archetype_avoidance": "redemptive climax, chosen one",
  "master_seed": null
}
```

**Response:**
```json
{
  "spine_data": { "...": "generated CampaignSpine" },
  "master_seed": 67890,
  "gaps": []
}
```

### POST /studio/generate/saga

Run the full 5-stage Writer's Room saga pipeline for sequel
generation.

**Request:**
```json
{
  "era": "New Jedi Order",
  "location": "Yavin 4",
  "tone": "epic",
  "moral_register": "morally complex",
  "num_directions": 3,
  "prior_campaign_json": { "...": "completed campaign spine" },
  "master_seed": null
}
```

**Response:**
```json
{
  "selected_spine": { "...": "best candidate spine" },
  "all_candidates": [ "..." ],
  "master_seed": 11111,
  "directions_generated": 3,
  "sketches_generated": 6,
  "drafts_generated": 3,
  "passed_validation": 2,
  "validation_report": { "...": "..." }
}
```

---

## Cross-Era Import

### POST /studio/import/apply

Apply a character import package to transfer a character into a new
campaign.

**Request:**
```json
{
  "import_package": { "...": "character export data" },
  "spine_data": { "...": "receiving campaign spine" },
  "variant_id": "jedi_padawan"
}
```

**Response:**
```json
{
  "character_data": { "...": "assembled character for Game Engine" },
  "applied_mappings": { "motivation_track": "duty", "...": "..." },
  "warnings": [],
  "xp_adjusted": -5
}
```

### POST /studio/import/default

Build a default character from a campaign variant (fresh start, no
import).

**Request:**
```json
{
  "spine_data": { "...": "campaign spine" },
  "variant_id": "keth_varso_smuggler"
}
```

**Response:**
```json
{
  "character_data": { "...": "character indistinguishable from new start" }
}
```

---

## Campaign Storage

### GET /studio/campaigns

List all stored campaign spines.

**Response:**
```json
{
  "campaigns": [
    {
      "id": "uuid-string",
      "name": "The Nar Shaddaa Job",
      "era": "Galactic Civil War",
      "created_at": "2026-03-08T12:00:00Z",
      "authoring_mode": "mode3"
    }
  ]
}
```

### POST /studio/campaigns

Store a validated campaign spine. Spine is validated before storage;
fails if validation errors exist.

**Request:**
```json
{
  "spine_data": { "...": "complete spine" },
  "authoring_mode": "mode2",
  "prior_campaign_id": null
}
```

**Response:**
```json
{
  "campaign_id": "uuid-string",
  "name": "The Nar Shaddaa Job",
  "era": "Galactic Civil War"
}
```

### GET /studio/campaigns/{campaign_id}

Retrieve a stored campaign spine by ID.

**Response:**
```json
{
  "id": "uuid-string",
  "name": "The Nar Shaddaa Job",
  "era": "Galactic Civil War",
  "created_at": "2026-03-08T12:00:00Z",
  "authoring_mode": "mode3",
  "spine": { "...": "full campaign spine JSON" },
  "validation_report": { "...": "..." }
}
```
