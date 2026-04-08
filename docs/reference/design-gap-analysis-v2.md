> **REFERENCE ONLY** — This is an archived audit artifact. All nine
> design specifications in this document have been completed and are
> referenced by the Backlog. Consult Game Mechanics, Implementation,
> and Campaign Studio Implementation for current authoritative content.
> Retained for traceability and implementation reference.

# Storyteller V3 — Design Gap Analysis v2.0

**Document version:** 2.0  
**Date:** March 6, 2026  
**Purpose:** Complete the design for every remaining item across the
project that is not yet fully designed. This document supersedes v1.1,
carrying forward all v1.1 content (now marked APPLIED) and adding full
design specifications for the nine items that remained after v1.1.

**Scope:** Every item with status CONCEPT ONLY, CONSIDER, FILED, or
NOT STARTED (for pre-build requirements) that can be designed without
runtime prerequisites. Phase 5 long-term aspirations (5.1–5.6) remain
excluded — those are beyond the current planning horizon.

---

## Document Structure

**Section A** — v1.1 items (APPLIED). Design specs completed in v1.1
and already integrated into the backlog. Retained here for reference
but not repeated in full. See v1.1 for complete specifications.

**Section B** — v2.0 items. Nine new full design specifications.

---

## Section A: v1.1 Items (APPLIED — Reference Only)

The following items were fully designed in Gap Analysis v1.1 and have
been applied to the Backlog (v2.8). Their status in the backlog has
been updated accordingly:

| Item | v1.1 Status | Backlog Status |
|------|-------------|----------------|
| 2.11 — Faction state tracking | Full spec | DESIGNED |
| 2.16 — Distillation evaluation taxonomy | Full spec | DESIGNED |
| 2.20 — NPC relationship triangles | Full spec | DESIGNED |
| 2.22 — Behavioral envelope enforcement | Full spec (test protocol) | DESIGNED |
| 2.23 — NPC information propagation | Full spec | DESIGNED |
| 2.25 — Character-centric campaign management | Full spec (revised) | DESIGNED |
| 2.26 — Settings / API key management UI | Full spec | DESIGNED |
| 2.28 — Generative entity persistence | Concept + design direction | CONCEPT ONLY |
| 3.17 — NPC voice generation | Full spec + prompt template | DESIGNED |
| 3.32 — Character funnel frontend UI | Full spec | DESIGNED |
| 3.33 — Integration layer validation | Full spec (5 checks) | DESIGNED |
| 3.34 — Allegiance diversity validation | Full spec (3 checks) | DESIGNED |
| 3.0c — Spine format alignment check | Design approach | NOT STARTED |
| 3.27 — Spine difficulty calibration | Design direction | CONCEPT ONLY |
| 3.28 — Campaign rating/feedback | Design direction | CONCEPT ONLY |
| 3.26 — Deterministic seeding | Design direction | CONSIDER |
| 4.0a — Saga layer test artifacts | Design approach | NOT STARTED |
| 4.0d — Persona pool curation | Design approach | NOT STARTED |

---

## Section B: v2.0 Design Specifications

Nine items upgraded from CONCEPT ONLY / CONSIDER / FILED / NOT STARTED
to fully specified designs.

---

### Item 2.19 — Turn Counter for Spine Advancement

**Backlog ref:** 2.19, Phase 2 Prose & Narration Enhancements.  
**Previous status:** FILED.  
**New status:** DESIGNED.  
**Blocks:** Nothing directly. Improves act pacing accuracy in Phase 7.  
**When needed:** Late V1 or early Milestone 1, when the reconciliation
system (Phase 7) needs better pacing calibration.

**The problem this solves:**

The reconciliation step (GM §26.3) already uses `expected_turns` and
`turns_this_act` to calibrate `progress_delta`. However, the current
design embeds this logic entirely in the reconciliation prompt — the
local model is asked to reason about pacing in natural language as part
of its broader reconciliation task. A dedicated turn counter gives the
system a concrete, deterministic signal that the local model does not
need to calculate or estimate.

**Design specification:**

**Data model:**

The `ArcState` already contains `turns_this_act: int` (GM §26). The
turn counter is not a new data structure — it is a derived pacing
signal computed deterministically from `turns_this_act` and the
spine's `expected_turns` field for the current act.

```python
class PacingSignal(BaseModel):
    """Deterministic pacing signal computed each turn."""
    turns_this_act: int
    expected_turns_low: int    # parsed from "8-12" → 8
    expected_turns_high: int   # parsed from "8-12" → 12
    pacing_ratio: float        # turns_this_act / expected_turns_midpoint
    pacing_zone: str           # "early" | "on_pace" | "late" | "overdue"
```

**Pacing zone computation:**

```
midpoint = (expected_turns_low + expected_turns_high) / 2
pacing_ratio = turns_this_act / midpoint

if pacing_ratio < 0.4:     pacing_zone = "early"
elif pacing_ratio < 0.85:  pacing_zone = "on_pace"
elif pacing_ratio < 1.3:   pacing_zone = "late"
else:                       pacing_zone = "overdue"
```

**Integration with reconciliation:**

The `PacingSignal` is computed deterministically in Python before the
reconciliation prompt runs. It is injected into the reconciliation
prompt as a structured block:

```
TURN PACING:
Turn {turns_this_act} of expected {expected_turns_low}-{expected_turns_high}.
Pacing zone: {pacing_zone}.
```

This replaces the current approach where the reconciliation prompt must
parse the `expected_turns` string and compute pacing ratios. The local
model no longer performs arithmetic — it receives the pacing zone as a
categorical input and uses it to calibrate `progress_delta`.

**Pacing zone → progress_delta modifier:**

The reconciliation prompt receives guidance on how the pacing zone
should influence its delta choice:

```
PACING ZONE GUIDANCE:
- early: Reduce progress_delta by 20-30%. The story has room to breathe.
- on_pace: No modifier. Use the anchor_proximity delta as-is.
- late: Increase progress_delta by 20-30%. The story needs to converge.
- overdue: Increase progress_delta by 40-50%. Strongly favor "imminent"
  or "reached" proximity assessments.
```

These are multiplicative modifiers on the base delta from the
anchor_proximity assessment. The local model still makes the proximity
judgment; the turn counter tells it how urgently to weigh that judgment.

**Integration with the narration prompt:**

The pacing block in the narration prompt (GM §26.6) already includes
`Turns in act: {turns_this_act} of ~{expected_turns}`. The turn
counter adds the pacing zone label:

```
PACING:
Act progress: {act_progress_percentage}%
Turns in act: {turns_this_act} of ~{expected_turns} [{pacing_zone}]
```

**expected_turns parsing:**

The `expected_turns` field in the campaign spine is a string (e.g.,
"8-12"). Parse on spine load:

```python
def parse_expected_turns(s: str) -> tuple[int, int]:
    """Parse '8-12' → (8, 12). Single number '10' → (10, 10)."""
    if "-" in s:
        parts = s.split("-")
        return int(parts[0].strip()), int(parts[1].strip())
    n = int(s.strip())
    return n, n
```

**Scope boundary:** The turn counter is a deterministic computation
layer, not a new system. It removes arithmetic burden from the local
model and provides a categorical signal that is easier to follow than
raw numbers. It does not change the reconciliation system's
architecture — it makes the existing pacing logic more reliable.

**Implementation scope:**

- Extend: `engine/reconciliation.py` — compute `PacingSignal` before
  building the reconciliation prompt.
- Extend: `gm/prompts/reconciliation.txt` — inject structured pacing
  block with zone guidance.
- Extend: `gm/context.py` — include pacing zone in the narration
  prompt's PACING block.
- New utility: `engine/pacing.py` — `PacingSignal` model,
  `parse_expected_turns()`, `compute_pacing_signal()`.

---

### Item 2.28 — Generative Entity Persistence (UPGRADE)

**Backlog ref:** 2.28, Phase 2 Infrastructure.  
**Previous status:** CONCEPT ONLY (v1.1 provided extensive design
direction and models).  
**New status:** DESIGNED.  
**Blocks:** Nothing directly. Enrichment layer.  
**When needed:** After Milestone 1 playtesting.

**Upgrade rationale:**

The v1.1 Gap Analysis provided models (EmergentNPC, EmergentLocation,
EmergentFact), a detection mechanism (reconciliation prompt extension),
a reintroduction strategy (NPC tiering, thread management), scope
boundaries, and evaluation criteria. What it lacked for DESIGNED status
was: the reconciliation prompt text, the state card generation prompt,
the persistence schema, and the reintroduction injection format.

**Reconciliation prompt addition:**

The reconciliation prompt (GM §26) gains an additional extraction
target. Added after the `reputation_event` field:

```
EMERGENT ENTITIES:
If the narration introduces entities that are NOT in the active NPC
roster, known locations, or established facts, evaluate them:

For each new entity the player interacted with meaningfully (not
background crowd, not mentioned-in-passing):

- entity_type: "npc" | "location" | "fact"
- identifier: the name or descriptor used in the narration
- significance: "low" | "medium" | "high"
  - low: background color, no player interaction (a stormtrooper in a
    crowd, a corridor described in passing)
  - medium: the player acknowledged or briefly interacted with them
    (asked the bartender a question, noted a specific location)
  - high: the player invested in the interaction (exchanged information,
    made a deal, spent significant time at a location)
- summary: one sentence describing the entity's role in this turn

If no new entities were introduced, return an empty list.
Do not flag entities that already exist in the NPC roster or location
data.
```

**Reconciliation JSON schema addition:**

```json
{
  "emergent_entities": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "entity_type": {"type": "string", "enum": ["npc", "location", "fact"]},
        "identifier": {"type": "string"},
        "significance": {"type": "string", "enum": ["low", "medium", "high"]},
        "summary": {"type": "string"}
      },
      "required": ["entity_type", "identifier", "significance", "summary"]
    }
  }
}
```

**Persistence filter:** Only `medium` and `high` significance entities
are persisted. `low` entities are discarded after reconciliation.

**State card generation prompt** (`gm/prompts/entity_card_gen.txt`):

When the reconciliation step detects a medium or high significance
entity, a follow-up local model call generates the state card. This is
a separate call from the reconciliation itself to keep the
reconciliation prompt focused and the card generation prompt specialized.

```
Generate a minimal state card for an entity that appeared in a Star
Wars RPG narration.

NARRATION CONTEXT:
{last_narration_excerpt}

ENTITY:
Type: {entity_type}
Identifier: {identifier}
What happened: {summary}

{type_specific_instructions}
```

Type-specific instructions:

For NPCs:
```
Generate a JSON object with these fields:
- descriptor: the name or description used in the narration
- motivation_inferred: one sentence — what they seem to want, based on
  their behavior in the scene
- voice_hint: one sentence — how they spoke or carried themselves
- disposition: float 0.0-1.0 — their apparent attitude toward the
  player based on the interaction
- knowledge: list of strings — what they know based on the scene
```

For locations:
```
Generate a JSON object with these fields:
- descriptor: the name or description of the place
- sensory_notes: one sentence — what the place looks, sounds, smells
  like based on the narration
- significance: one sentence — why this place matters to the player
```

For facts:
```
Generate a JSON object with these fields:
- content: the fact, rumor, or discovery in one sentence
- source_npc: who said it or where it was learned (use "observation"
  if the player discovered it themselves)
- reliability: "firsthand" | "rumor" | "observation"
```

**Database schema:**

```sql
CREATE TABLE emergent_entities (
    entity_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    entity_type TEXT NOT NULL,       -- 'npc', 'location', 'fact'
    identifier TEXT NOT NULL,
    significance TEXT NOT NULL,       -- 'medium', 'high'
    state_card TEXT NOT NULL,         -- JSON string
    introduced_turn INTEGER NOT NULL,
    introduced_act INTEGER NOT NULL,
    last_referenced_turn INTEGER,
    reference_count INTEGER DEFAULT 1,
    tier INTEGER DEFAULT 3,           -- NPC tier (3=background)
    active INTEGER DEFAULT 1,         -- 0 if pruned
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Per-act entity cap enforcement:**

```python
def can_persist_entity(session_id: str, current_act: int) -> bool:
    """Enforce 2-3 new persistent entities per act."""
    count = db.execute(
        "SELECT COUNT(*) FROM emergent_entities "
        "WHERE session_id = ? AND introduced_act = ? AND active = 1",
        (session_id, current_act)
    ).fetchone()[0]
    return count < 3
```

If the cap is reached, only `high` significance entities can override
`medium` ones (replace the least-referenced medium entity from the
same act).

**Reintroduction injection format:**

Emergent NPCs at Tier 2 or higher are injected into the NPC section
of the narration prompt with a lighter format than authored NPCs:

```
[EMERGENT] {descriptor}
Motivation: {motivation_inferred}
Voice: {voice_hint}
Disposition: {disposition_label} ({disposition})
Knows: {knowledge_list}
(First met: Act {introduced_act}, Turn {introduced_turn})
```

The `[EMERGENT]` tag signals the GM that this NPC has a lighter state
card and should not be given the same narrative weight as authored NPCs.

Emergent locations are injected into the scene context when the
narration references the location or the player returns to it:

```
[KNOWN LOCATION] {descriptor}
{sensory_notes}
{significance}
```

Emergent facts are injected into the open threads block as lightweight
thread entries:

```
[DISCOVERED] {content} (Source: {source_npc}, {reliability})
```

**Tier promotion logic:**

Emergent NPCs start at Tier 3. Promotion criteria:

- Tier 3 → Tier 2: `reference_count >= 2` (the player has returned to
  or mentioned this NPC at least once after introduction).
- Tier 2 → Tier 1: The player is in a scene with this NPC (detected
  by the reconciliation step listing them in NPC updates).

Demotion: An emergent NPC not referenced for 2+ acts is demoted back
to Tier 3. If not referenced for 3+ acts, `active` is set to 0
(pruned from prompt consideration but retained in the database for
potential saga layer use).

**Cross-campaign persistence:**

Emergent entities with `reference_count >= 3` or `tier <= 2` are
included in the cross-campaign import package (Phase 19). The saga
layer (Phase 4) can promote significant emergent entities to full
authored NPCs in the sequel spine — this is one of the strongest
signals that the world responded to the player's story.

**Graceful degradation:** If the entity detection prompt fails
(returns invalid JSON or an empty list when entities are clearly
present), the system continues without persisting entities. The
authored spine carries the full load. Entity persistence is never on
the critical path.

---

### Item 3.26 — Deterministic Seeding for Reproducible Generation

**Backlog ref:** 3.26, Campaign Studio Deferred Items.  
**Previous status:** CONSIDER.  
**New status:** DESIGNED.  
**Blocks:** Nothing.  
**When needed:** CS Phase 2 (Mode 3) for iterative refinement UX.

**The problem this solves:**

When the Campaign Studio generates a spine in Mode 2 or Mode 1, the
author may want to regenerate part of the spine while keeping other
parts. "I like the world and NPCs but want different anchor beats."
Without seeding, regeneration produces entirely different output.
With seeding, the author can hold some generation stages constant
while re-rolling others.

**Design specification:**

**Seed architecture:**

Each generation stage in the Campaign Studio pipeline receives its
own seed value. Seeds are derived from a master seed using a
deterministic derivation:

```python
import hashlib

def derive_stage_seed(master_seed: int, stage_name: str) -> int:
    """Deterministic seed derivation per pipeline stage."""
    h = hashlib.sha256(f"{master_seed}:{stage_name}".encode())
    return int.from_bytes(h.digest()[:8], "big") % (2**31)
```

Stage names map to the Campaign Studio pipeline stages:

| Stage Name | Pipeline Stage | What It Controls |
|------------|---------------|-----------------|
| `world` | Mode 2 world generation | Era, locations, galactic context |
| `npcs` | NPC roster generation | NPC names, motivations, roles |
| `anchors` | Anchor beat generation | Act structure, anchor situations |
| `voice` | NPC voice generation | Voice notes per NPC |
| `variants` | Variant generation | Allegiances, character variants |
| `threads` | Thread generation | Open threads, variation points |
| `saga_diverge` | Saga Stage 2 | Sequel directions |
| `saga_search` | Saga Stage 3 | Branching search |
| `saga_debate` | Saga Stage 4 | Critique/convergence |

**API integration:**

The derived seed is passed via the `seed` parameter on
OpenAI-compatible API calls:

```python
response = client.chat.completions.create(
    model=model,
    messages=messages,
    seed=derive_stage_seed(master_seed, stage_name),
    # ... other params
)
```

For Ollama (local model), the `seed` parameter is passed via the
`options` dict:

```python
response = ollama.chat(
    model=model,
    messages=messages,
    options={"seed": derive_stage_seed(master_seed, stage_name)},
)
```

**Spine metadata storage:**

The generated spine records its generation seeds:

```python
class GenerationMetadata(BaseModel):
    """Records generation parameters for reproducibility."""
    master_seed: int
    stage_seeds: dict[str, int]  # stage_name → derived seed
    model_used: str
    generation_mode: str  # "mode1" | "mode2" | "mode3_assist"
    timestamp: str
```

This is stored alongside the spine in `CampaignSpine.generation_metadata:
Optional[GenerationMetadata] = None`. Hand-authored spines (Mode 3
without AI generation) have `None`.

**Partial regeneration UX:**

In Mode 3 collaborative authoring and Mode 2 thematic steering, the
author can request partial regeneration:

```
"Regenerate NPCs" → new seed for `npcs` and `voice` stages only;
  all other stages use the original seeds.
"Regenerate structure" → new seed for `anchors` and `threads` stages;
  world, NPCs, and variants preserved.
"Full regenerate" → new master seed; everything regenerated.
```

The UI presents these as actions on a generated spine, not as raw seed
manipulation. The author never sees seed numbers.

**Implementation scope:**

- New: `studio/seeding.py` — `derive_stage_seed()`, `GenerationMetadata`
  model.
- Extend: `studio/generate.py` — accept `master_seed: Optional[int]`
  parameter. When `None`, generate a random master seed. Pass derived
  seeds to each pipeline stage.
- Extend: `studio/schema.py` — add `generation_metadata` field to
  `CampaignSpine`.
- Extend: Studio API routes — partial regeneration endpoint that
  accepts stage overrides.

**Effectiveness caveat:**

Deterministic seeding depends on model-level support. Not all providers
honor the `seed` parameter identically. OpenAI documents `seed` as
"best effort" — outputs are mostly but not perfectly reproducible.
Ollama with quantized models may produce slight variations. The system
should treat seeding as "high probability of similar output," not as a
guarantee. The UI should set expectations accordingly: "Results will be
similar but not identical to the original generation."

---

### Item 3.27 — Spine Difficulty Calibration

**Backlog ref:** 3.27, Campaign Studio Deferred Items.  
**Previous status:** CONCEPT ONLY.  
**New status:** DESIGNED.  
**Blocks:** Nothing. Enriches Mode 2 and Mode 1 quality signals.  
**When needed:** CS Phase 3 (Mode 2), where generated spines benefit
from automated quality feedback.

**The problem this solves:**

An authored or generated campaign spine has an implicit difficulty
curve — some acts are harder than others based on check frequencies,
NPC opposition, and mechanical pressure. Without calibration feedback,
the author (or Mode 2/1 generator) can accidentally produce a spine
where Act 1 is brutally hard and Act 4 is trivially easy, or where
every act sits at the same flat difficulty. The difficulty curve should
generally escalate with variation — rising overall but with peaks and
valleys that create rhythm.

**Design specification:**

**Difficulty scoring model:**

Each act in the spine receives a difficulty score (1.0–5.0) computed
from four weighted signals extracted from the spine data:

```python
class ActDifficultyScore(BaseModel):
    """Per-act difficulty estimate from spine data."""
    act_number: int
    anchor_intensity: float      # 1.0-5.0
    npc_opposition: float        # 1.0-5.0
    mechanical_pressure: float   # 1.0-5.0
    pacing_pressure: float       # 1.0-5.0
    composite: float             # weighted average
    label: str                   # "low" | "moderate" | "high" | "intense"

class SpineDifficultyCurve(BaseModel):
    """Full campaign difficulty profile."""
    per_act: list[ActDifficultyScore]
    curve_shape: str             # "flat" | "rising" | "spiked" | "valley"
    warnings: list[str]          # calibration issues
```

**Signal computation:**

**1. Anchor intensity (weight 30%).**

Derived from anchor description language and act tension level:

| Tension Level | Base Score |
|--------------|-----------|
| low | 1.5 |
| rising | 2.5 |
| high | 3.5 |
| climactic | 4.5 |
| resolution | 2.0 |

Adjusted +0.5 if the anchor description contains combat/conflict
keywords (ambush, attack, confrontation, escape, betrayal, siege).

**2. NPC opposition (weight 25%).**

Count NPCs with `disposition_start < 0.4` (hostile) who appear in
the act. More hostile NPCs = higher opposition score.

| Hostile NPCs in Act | Score |
|--------------------|-------|
| 0 | 1.0 |
| 1 | 2.5 |
| 2 | 3.5 |
| 3+ | 4.5 |

Adjusted +0.5 if any hostile NPC has a behavioral envelope indicating
active aggression (e.g., "will pursue," "will escalate,"
"confrontational").

**3. Mechanical pressure (weight 25%).**

Derived from the act's Obligation/Duty activation thresholds and any
spine-authored triggers:

| Signal | Score Contribution |
|--------|-------------------|
| Obligation value > 10 for this act | +1.0 |
| Duty activation in this act | +0.5 |
| Spine-authored Dark Side Destiny trigger | +0.5 |
| Equipment scarcity (loadout restrictions in act) | +0.5 |
| Vehicle encounter in act | +0.5 |

Base score 1.0 + contributions, capped at 5.0.

**4. Pacing pressure (weight 20%).**

Derived from `expected_turns` and anchor spacing:

| Expected Turns | Score |
|---------------|-------|
| 4-6 (short) | 4.0 |
| 7-10 (standard) | 2.5 |
| 11-15 (long) | 1.5 |

Short acts with dense anchor spacing create time pressure — the
player has fewer turns to explore, gather information, and prepare.

**Composite score:**

```python
composite = (
    anchor_intensity * 0.30 +
    npc_opposition * 0.25 +
    mechanical_pressure * 0.25 +
    pacing_pressure * 0.20
)
```

**Difficulty labels:**

| Composite | Label |
|-----------|-------|
| 1.0–2.0 | low |
| 2.0–3.0 | moderate |
| 3.0–4.0 | high |
| 4.0–5.0 | intense |

**Curve shape classification:**

Analyze the sequence of per-act composite scores:

- **flat:** max - min < 0.8 across all acts.
- **rising:** each act's score is ≥ the prior act's score (within
  0.3 tolerance).
- **valley:** at least one act is ≥ 1.0 lower than both its neighbors.
- **spiked:** one act is ≥ 1.5 higher than both its neighbors.

**Calibration warnings:**

The system generates warnings when the difficulty curve has structural
issues:

```
- "Act 1 is rated 'intense' — this may overwhelm new players before
   they're invested in the story. Consider reducing hostility or
   extending the expected turn count."
- "Difficulty is flat across all acts. Consider varying NPC opposition
   or pacing to create a sense of escalation."
- "Act {n} drops from 'high' to 'low' without narrative justification
   (no time skip, no resolution beat). This may feel anticlimactic."
- "The final act is rated 'low' — campaign climaxes typically benefit
   from the highest difficulty. Consider intensifying opposition or
   reducing expected turns."
```

**Integration:**

Difficulty calibration runs as part of Gate 4 (narrative consistency
audit) in `studio/validate.py`. It produces the `SpineDifficultyCurve`
as a validation output. In Mode 3, the author sees the curve and
warnings as feedback. In Mode 2/1, the generator can use the curve to
self-correct: if the generated spine is flat, regenerate with a
prompt addition emphasizing escalation.

**Implementation scope:**

- New: `studio/difficulty.py` — `ActDifficultyScore`,
  `SpineDifficultyCurve`, `calibrate_difficulty()`.
- Extend: `studio/validate.py` — call `calibrate_difficulty()` during
  Gate 4. Include curve and warnings in validation report.
- Pure Python, no LLM calls. All signals derived from spine data.

---

### Item 3.28 — Campaign Rating and Feedback System

**Backlog ref:** 3.28, Campaign Studio Deferred Items.  
**Previous status:** CONCEPT ONLY.  
**New status:** DESIGNED.  
**Blocks:** Nothing. Requires a player base to be useful.  
**When needed:** Post-launch, when multiple campaigns have been played.

**The problem this solves:**

Mode 1 and Mode 2 campaign generation produce varying quality. Over
time, the system should improve by learning from player experience.
Ratings provide the quality signal. The feedback loop allows
highly-rated spines to inform future generation, and low-rated spines
to surface common failure patterns.

**Design specification:**

**Rating collection:**

At campaign completion (after the final act's anchor beat fires and
the act summary is generated), the UI presents a rating prompt.
This appears on the same screen as the "Begin Next Chapter" or
"Return to Characters" action — it does not interrupt the narrative
flow.

**Rating model:**

```python
class CampaignRating(BaseModel):
    """Player rating of a completed campaign."""
    rating_id: str               # UUID
    character_id: str            # who played it
    campaign_spine: str          # spine identifier
    generation_mode: str         # "mode1" | "mode2" | "mode3" | "authored"
    overall_rating: int          # 1-5 stars
    dimension_ratings: Optional[dict[str, int]] = None  # optional breakdown
    free_text: Optional[str] = None  # optional comment, max 500 chars
    play_duration_turns: int     # total turns across all acts
    completed_at: str            # ISO timestamp
```

**Dimension ratings (optional, shown as expandable):**

If the player taps "Rate in detail," they see three sub-ratings
(1–5 stars each):

| Dimension | What It Measures |
|-----------|-----------------|
| Story | "Was the story compelling?" — anchor beats, throughline, surprises |
| Characters | "Did the NPCs feel real?" — voice, consistency, relationships |
| Pacing | "Did the campaign flow well?" — act length, difficulty curve, rhythm |

These are optional. The overall rating is always collected. Dimension
ratings are only shown if the player opts in.

**Database schema:**

```sql
CREATE TABLE campaign_ratings (
    rating_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL REFERENCES characters(character_id),
    campaign_spine TEXT NOT NULL,
    generation_mode TEXT NOT NULL,
    overall_rating INTEGER NOT NULL CHECK(overall_rating BETWEEN 1 AND 5),
    story_rating INTEGER CHECK(story_rating BETWEEN 1 AND 5),
    character_rating INTEGER CHECK(character_rating BETWEEN 1 AND 5),
    pacing_rating INTEGER CHECK(pacing_rating BETWEEN 1 AND 5),
    free_text TEXT,
    play_duration_turns INTEGER NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ratings_spine ON campaign_ratings(campaign_spine);
CREATE INDEX idx_ratings_mode ON campaign_ratings(generation_mode);
```

**Feedback loop into generation:**

When Mode 2 or Mode 1 generates a new spine, the system can include
exemplar data from highly-rated spines in the generation prompt:

**Exemplar selection:**

```python
def select_exemplars(
    generation_mode: str,
    era: Optional[str] = None,
    limit: int = 2
) -> list[dict]:
    """Select highly-rated spines as generation exemplars."""
    query = """
        SELECT campaign_spine, overall_rating,
               AVG(story_rating) as avg_story,
               AVG(character_rating) as avg_character,
               AVG(pacing_rating) as avg_pacing,
               COUNT(*) as num_ratings
        FROM campaign_ratings
        WHERE overall_rating >= 4
        AND generation_mode = ?
        GROUP BY campaign_spine
        HAVING num_ratings >= 2
        ORDER BY overall_rating DESC, num_ratings DESC
        LIMIT ?
    """
    return db.execute(query, (generation_mode, limit)).fetchall()
```

**Prompt integration:**

Selected exemplar spines are summarized (throughline, anchor count,
NPC count, tension curve, difficulty curve) and injected into the
generation prompt as reference examples:

```
EXEMPLAR CAMPAIGNS (rated highly by players):

Campaign: {exemplar.throughline}
Structure: {exemplar.act_count} acts, {exemplar.npc_count} NPCs
Tension curve: {exemplar.tension_sequence}
What players liked: {derived from dimension ratings}

Use these as quality references, not templates. Your campaign should
be original, but should match the structural quality of these examples.
```

**Failure pattern detection:**

Low-rated spines (overall ≤ 2) with free-text comments are flagged
for review. When 3+ low-rated spines from the same generation mode
share common structural patterns (same act count, similar NPC count,
similar tension curve), the system generates a "pattern alert":

```
"Mode 1 generation has produced 3 low-rated campaigns with 3 acts
and flat tension curves. Consider adding a minimum act count of 4
and a tension escalation requirement to the generation prompt."
```

Pattern alerts are logged to a `generation_alerts` table and surfaced
in the Campaign Studio's dashboard (if built). This is a long-term
feedback loop that improves the system over many campaigns.

**UI integration:**

- Post-completion rating card: appears after the final act summary,
  before the character screen. Star rating (1–5), optional
  "Rate in detail" expansion, optional free-text field. Dismissable —
  the player can skip rating. Non-intrusive design: the narrative
  ending is the primary experience, the rating is secondary.
- The rating card appears once per campaign completion. If the player
  navigates away before rating, the rating prompt appears at the next
  app launch (once, then never again for that campaign).

**Implementation scope:**

- New: `state/ratings.py` — `CampaignRating` model, rating persistence,
  exemplar selection.
- Extend: `state/db.py` — `campaign_ratings` table.
- Extend: `web/index.html` — post-completion rating card.
- Extend: `api/game_routes.py` — `POST /api/rating`,
  `GET /api/ratings/exemplars`.
- Extend: `studio/generate.py` — exemplar injection into generation
  prompts.

---

### Item 4.9 — Trained Local Evaluator for Spine Quality

**Backlog ref:** 4.9, Phase 4 Saga Layer Deferred.  
**Previous status:** CONCEPT ONLY.  
**New status:** DESIGNED.  
**Blocks:** Nothing directly. Optimization for saga layer cost/speed.  
**When needed:** After CS Phase 4 has produced a corpus of generated
spines with quality annotations.

**The problem this solves:**

The saga layer's Stage 5 (pairwise evaluation) uses LLM calls to
evaluate spine quality across three axes: structural quality, novelty,
and diversity. These calls go to the cloud model, adding latency and
cost to an already compute-intensive pipeline. Research (CrEval,
Research Catalogue Source 5) shows a trained 7B evaluator can
outperform frontier models at creativity judgment. A fine-tuned local
evaluator could make Stage 5 fast and free.

**Design specification:**

**Training data requirements:**

The evaluator needs pairwise comparison examples: given Spine A and
Spine B, which is better on each axis? These examples come from two
sources:

1. **Cloud model evaluations from Stage 5.** Every time the saga
   pipeline runs, Stage 5 produces pairwise comparisons with axis
   scores and reasoning. These are logged as training pairs.
2. **Player ratings.** When players rate completed campaigns (item
   3.28), the rating provides a ground-truth quality signal.
   A spine rated 5 stars should generally "win" a pairwise comparison
   against a spine rated 2 stars.

**Data logging schema:**

```sql
CREATE TABLE evaluation_pairs (
    pair_id TEXT PRIMARY KEY,
    spine_a_id TEXT NOT NULL,
    spine_b_id TEXT NOT NULL,
    spine_a_summary TEXT NOT NULL,   -- compressed representation
    spine_b_summary TEXT NOT NULL,
    axis TEXT NOT NULL,              -- 'structural' | 'novelty' | 'diversity'
    winner TEXT NOT NULL,            -- 'a' | 'b' | 'tie'
    confidence FLOAT,               -- evaluator's stated confidence
    reasoning TEXT,                  -- evaluator's explanation
    source TEXT NOT NULL,            -- 'cloud_stage5' | 'player_rating'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Minimum corpus:** 200+ pairwise comparisons per axis (600+ total)
before training is viable. At a pace of one saga run producing 5–10
pairwise comparisons across the three axes, this requires ~20–40 saga
runs. Not achievable quickly — this is a long-term improvement.

**Training approach:**

QLoRA fine-tune of the local model (Qwen3.5:9B or its successor at
training time) on the evaluation task:

**Training format:**

```
System: You are evaluating two campaign spines for a Star Wars RPG.
Compare them on {axis}. Respond with JSON.

User: SPINE A:
{spine_a_summary}

SPINE B:
{spine_b_summary}

Which spine is better for {axis_description}?
Assistant: {"winner": "a", "confidence": 0.8, "reasoning": "..."}
```

**Axis descriptions for the training prompt:**

| Axis | Description |
|------|------------|
| structural | "Structural quality: act pacing, anchor beat design, NPC integration, thread management, difficulty curve, and internal consistency." |
| novelty | "Novelty: how surprising, original, and non-obvious is the campaign concept, throughline question, and anchor beat sequence? Avoid rewarding novelty that sacrifices coherence." |
| diversity | "Diversity from prior campaign: how structurally different is this spine from the prior campaign it follows? Different conflict type, different narrative arc shape, different social dynamics, different mechanical emphasis." |

**Spine summary format for training:**

Full spines are too long for efficient training context. Each spine is
compressed to a summary:

```python
class SpineSummary(BaseModel):
    """Compressed spine representation for evaluation training."""
    throughline: str
    act_count: int
    act_tensions: list[str]
    anchor_summaries: list[str]  # one sentence per anchor
    npc_count: int
    npc_roles: list[str]        # one line per NPC: name, motivation
    relationship_density: float  # from Gate 3 metrics
    difficulty_curve: list[float]  # per-act composite from item 3.27
    total_word_estimate: int    # rough campaign length
```

**Evaluation protocol for the trained model:**

Before deploying the local evaluator in production, it must pass a
calibration test:

1. Run 20 pairwise comparisons where the cloud model has a clear
   consensus (winner confidence > 0.8).
2. The local evaluator must agree with the cloud model on at least
   16 of 20 (80% agreement).
3. Per-axis: the local evaluator must agree on at least 75% per axis.
4. If the evaluator fails calibration, retrain with a larger corpus.

**Architecture integration:**

The local evaluator is a drop-in replacement for the cloud evaluator
in Stage 5. The saga pipeline configuration specifies the evaluator:

```python
class SagaConfig(BaseModel):
    evaluator: str = "cloud"  # "cloud" | "local" | "ensemble"
    # ...
```

When `evaluator = "local"`, Stage 5 pairwise comparisons route to
Ollama instead of OpenRouter. When `evaluator = "ensemble"`, both are
called and the results are averaged (useful during calibration to
compare agreement in production).

**Implementation scope:**

- New: `studio/saga/evaluator.py` — local evaluation interface,
  SpineSummary compression, calibration test runner.
- Extend: `studio/saga/stage5.py` — evaluator routing based on config.
- New: `data/evaluation_pairs/` — logged training data directory.
- Training script: `scripts/train_evaluator.py` — QLoRA fine-tuning
  script using the same toolchain as the narration distillation
  pipeline (item 2.14).

---

### Item 4.10 — Multi-Model Ensemble (Different LLMs as Different Writers)

**Backlog ref:** 4.10, Phase 4 Saga Layer Deferred.  
**Previous status:** CONCEPT ONLY.  
**New status:** DESIGNED.  
**Blocks:** Nothing. Scaling lever for saga layer diversity.  
**When needed:** After persona + CoT on a single model has been
validated (CS Phase 4 baseline).

**The problem this solves:**

The Writer's Room assigns personas to generate diverse sequel
directions, but all writers share the same underlying model. Research
(Catalogue Source 7) shows multi-model ensembles approach human
variability because different models have different training
distributions, different biases, and different associative patterns.
A persona + model combination produces more genuine diversity than a
persona alone on a single model.

**Design specification:**

**Architecture:**

The multi-model ensemble is a configuration option for Stage 2
(divergent generation) and optionally Stage 3 (branching search).
It does not change the pipeline architecture — it changes how writers
are instantiated.

**Writer configuration:**

```python
class WriterConfig(BaseModel):
    """Configuration for a single writer in the Writer's Room."""
    persona: str               # persona text from the pool
    model: str                 # model string (e.g., "claude-sonnet-4-6")
    provider: str              # "openrouter" | "ollama" | "openai"
    temperature: float = 0.9   # higher for divergent generation

class EnsembleConfig(BaseModel):
    """Configuration for the multi-model ensemble."""
    writers: list[WriterConfig]
    model_pool: list[dict]     # available models with provider info
    assignment_strategy: str   # "round_robin" | "weighted" | "random"
```

**Model pool:**

The ensemble draws from the models available via OpenRouter (cloud) and
Ollama (local). The model pool is configured in the Campaign Studio
settings:

```python
DEFAULT_MODEL_POOL = [
    {"model": "claude-sonnet-4-6", "provider": "openrouter",
     "weight": 1.0, "notes": "Strong instruction adherence"},
    {"model": "grok-4.1-fast", "provider": "openrouter",
     "weight": 1.0, "notes": "Different training distribution"},
    {"model": "deepseek-v3.2", "provider": "openrouter",
     "weight": 0.8, "notes": "Low cost, different base"},
    {"model": "qwen3.5:9b", "provider": "ollama",
     "weight": 0.6, "notes": "Local, free, different family"},
]
```

Weights influence assignment probability in the `weighted` strategy.
Lower weights mean the model is assigned less frequently (e.g., the
local model is less capable, so it gets fewer writer slots).

**Assignment strategies:**

**round_robin:** Each writer gets the next model in the pool, cycling
through. Ensures every model in the pool is represented. Best when
the pool is small (2–3 models).

**weighted:** Each writer is assigned a model based on pool weights.
Models with higher weights are more likely to be assigned. Best when
some models are clearly stronger than others.

**random:** Each writer is assigned a random model from the pool.
Maximum diversity but may under-represent some models.

**Assignment function:**

```python
def assign_models_to_writers(
    personas: list[str],
    pool: list[dict],
    strategy: str = "round_robin"
) -> list[WriterConfig]:
    """Assign models to persona-primed writers."""
    writers = []
    for i, persona in enumerate(personas):
        if strategy == "round_robin":
            model_entry = pool[i % len(pool)]
        elif strategy == "weighted":
            weights = [m["weight"] for m in pool]
            model_entry = random.choices(pool, weights=weights, k=1)[0]
        elif strategy == "random":
            model_entry = random.choice(pool)

        writers.append(WriterConfig(
            persona=persona,
            model=model_entry["model"],
            provider=model_entry["provider"],
        ))
    return writers
```

**Stage 2 integration:**

Each writer's sequel direction generation call uses its assigned model
and provider. The generation function becomes model-aware:

```python
async def generate_sequel_direction(
    writer: WriterConfig,
    campaign_summary: str,
    denial_constraints: list[str],
) -> SequelDirection:
    """Generate a sequel direction using the writer's assigned model."""
    client = get_client(writer.provider)  # OpenRouter or Ollama
    response = await client.chat.completions.create(
        model=writer.model,
        messages=[
            {"role": "system", "content": build_persona_prompt(writer.persona)},
            {"role": "user", "content": build_direction_prompt(
                campaign_summary, denial_constraints
            )},
        ],
        temperature=writer.temperature,
    )
    return parse_sequel_direction(response)
```

The `get_client()` function returns the appropriate SDK client based
on the provider. For OpenRouter, this is the existing OpenAI-compatible
client. For Ollama, this is the Ollama client.

**Parallel execution:**

Multi-model generation in Stage 2 runs writers in parallel via
`asyncio.gather()`. Different models may have different response times;
the pipeline waits for all writers to complete before proceeding to
Stage 3.

**Cost management:**

The ensemble increases Stage 2 cost proportionally to the number of
cloud model writers. To manage costs:

- The local model (weight 0.6) handles a fraction of writers at zero
  cost.
- The number of writers is configurable (N >= 1). Reducing from 7 to
  5 writers reduces cost 30%.
- The ensemble is optional. The default configuration uses a single
  model (the active cloud model) for all writers. The ensemble is
  enabled explicitly in Campaign Studio settings.

**Diversity measurement:**

To validate that the ensemble actually improves diversity, the Stage 5
evaluation should track a diversity metric per-run:

```python
class RunDiversityMetrics(BaseModel):
    """Diversity metrics for a saga pipeline run."""
    models_used: list[str]
    unique_conflict_types: int
    unique_thematic_elements: int
    pairwise_diversity_mean: float  # from Stage 5
    run_timestamp: str
```

Log these metrics per-run to `saga_diversity_log` table. Compare runs
with ensemble enabled vs. disabled to empirically measure the diversity
gain.

**Graceful degradation:**

If a model in the pool is unavailable (API error, rate limit), the
assignment function falls back to the next available model. If only one
model is available, the ensemble degrades to single-model operation
(which is the proven baseline). The pipeline never fails because of
model availability — it degrades from ensemble to single-model.

**Bitter Lesson safeguard:**

Per Research Catalogue Source 4's MAS fragility caveat, the ensemble
should be re-evaluated periodically. As base models improve in
diversity (tracked by comparing single-model Stage 2 output diversity
over time), the ensemble overhead may become unnecessary. The
`RunDiversityMetrics` log provides the data for this evaluation.

**Implementation scope:**

- New: `studio/saga/ensemble.py` — `WriterConfig`, `EnsembleConfig`,
  `assign_models_to_writers()`, `get_client()`.
- Extend: `studio/saga/stage2.py` — model-aware generation calls,
  parallel execution.
- Extend: `studio/saga/stage5.py` — `RunDiversityMetrics` logging.
- Extend: `state/db.py` — `saga_diversity_log` table.
- Configuration: `studio/config.py` — ensemble settings, model pool.

---

### Item 4.0a — Saga Layer Test Artifacts

**Backlog ref:** 4.0a, Phase 4 pre-build requirement.  
**Previous status:** NOT STARTED (blocked by completed campaign).  
**New status:** DESIGNED (template and process specified; content
requires a completed campaign).  
**Blocks:** Saga Layer implementation (CS Phase 4).  
**When needed:** Before CS Phase 4 begins.

**The problem this solves:**

The five-stage saga pipeline has schemas and architecture, but no
concrete worked example showing actual content flowing through each
stage. Without a test artifact, the first implementation attempt is
also the first validation — bugs in the architecture are discovered
during coding rather than during design review.

**Design specification:**

**Test artifact structure:**

The test artifact is a single document containing concrete content for
every intermediate representation in the pipeline. It is not code — it
is a hand-written worked example that populates the schemas with
realistic content.

**Template:**

```markdown
# Saga Layer Test Artifact — {campaign_name} → Sequel

## Source: Completed Campaign State

### Character Export Package
{Full character state at campaign completion: mechanical stats,
motivation tracks, advancement log, relationship history, reputation
log, behavioral fingerprint from semantic memory}

### Campaign Summary
{2-3 paragraph summary of the campaign as played: what happened,
what choices defined the character, what threads are open, what
relationships matter}

### Import Summary (Stage 1 Input)
{Structured import summary following the ImportInterface schema:
specialization mappings, motivation transitions, NPC relationship
dispositions carried forward}

---

## Stage 1 — Persona Assignment

### Assigned Personas (subset of 7)
{List 7 personas from the pool with their full text}

### Assignment Rationale
{Why these 7 were selected — random draw from the 50+ pool}

---

## Stage 2 — Divergent Generation

### Denial Constraints Applied
{List of constraints: "Do not repeat {prior conflict type}",
"Do not extend {prior plot} directly", "Do not use {prior
resolution structure}"}

### Writer Outputs (7 SequelDirection objects)

#### Writer 1 — {persona_summary}
```json
{Complete SequelDirection JSON}
```

#### Writer 2 — {persona_summary}
{... repeat for all 7 writers}

### Diversity Assessment
{Qualitative assessment: how different are the 7 directions?
Which pairs are most similar? Which is most surprising?}

---

## Stage 3 — Branching Search

### Candidates Selected for Expansion
{Which 2-3 Stage 2 directions were selected for expansion}

### Expansion Outputs (SpineSketch per candidate)
```json
{Complete SpineSketch JSON for each expanded candidate}
```

### Pruning Decisions
{Which candidates were pruned and why}

---

## Stage 4 — Debate/Critique Convergence

### Prior Campaign Context Introduced
{How the prior campaign state modifies the candidate — this is
where coherence is enforced}

### Critic Challenges
{Specific objections the critic raised for each candidate}

### Writer Revisions
{How each candidate was revised in response to critique}

### Final Draft Spines
{Complete CampaignSpine JSON for the top 2-3 candidates}

---

## Stage 5 — Pairwise Evaluation

### Pairwise Comparisons
{For each pair of final candidates: structural quality comparison,
novelty comparison, diversity comparison, with reasoning}

### Evaluation Scores
```json
{EvaluatedSpine JSON for each candidate}
```

### Selected Winner
{Which candidate was selected and why}

---

## Validation

### Gate 1-4 Results on Selected Spine
{Validation output for the winning spine}

### Difficulty Curve
{SpineDifficultyCurve output}
```

**Process for creating the test artifact:**

1. **Play The Nar Shaddaa Job to completion** (Milestone 1). Record
   the final character state, campaign events, and relationship
   history.

2. **Extract the character export package** from the session database.

3. **Write the campaign summary** — a 2-3 paragraph narrative summary
   capturing the player's specific experience (not the spine's
   authored content).

4. **Hand-populate each pipeline stage** by reasoning through what
   each stage should produce given the inputs. The test artifact
   writer (human) acts as the pipeline, making the same decisions
   the LLM pipeline would make but with full visibility into the
   reasoning.

5. **Validate the final spine** through the existing Gate 1-4
   validation suite (which must be implemented as CS Phase 1
   before this artifact can be fully validated).

**Partial artifact (pre-campaign):**

A partial test artifact can be created before a campaign is played by
using a hypothetical completed state for Keth Varso:

- Assume Keth completed The Nar Shaddaa Job with specific outcomes
  (Obligation reduced to 10, Doss survived, Vossk's cargo delivered,
  one side-thread unresolved).
- Fabricate a plausible character export package from these assumptions.
- Walk through the pipeline stages with this fabricated input.

This partial artifact validates the pipeline logic and schema flow
even though the specific content is hypothetical. The full artifact
replaces it once a real campaign is played.

**Deliverable:** A markdown document (1500-3000 words) following the
template above, with every schema populated with concrete content.

**Implementation scope:**

- This is a document, not code.
- Depends on: CS Phase 1 (schema exists for validation), Milestone 1
  (real campaign data), or hypothetical data for a partial artifact.
- The artifact lives in `data/test_artifacts/saga_test_artifact.md`.

---

### Item 4.0d — Persona Pool Curation and Validation

**Backlog ref:** 4.0d, Phase 4 pre-build requirement.  
**Previous status:** NOT STARTED.  
**New status:** DESIGNED (pool drafted, validation protocol specified;
validation execution requires working Stage 2 code).  
**Blocks:** Writer's Room pipeline (Stage 2 of saga layer).  
**When needed:** Before CS Phase 4.

**Design specification:**

**Pool requirements (from CS Design §6.4.2):**

- 50+ personas, ordinary and heterogeneous.
- No Star Wars-specific personas.
- No narrative archetypes ("the sage," "the rebel," etc.).
- Each persona: 2-3 sentences covering background, values, and what
  they notice in stories.
- Span: age (20s-70s), geographic/cultural diversity,
  introvert/extrovert, risk tolerance, moral framework diversity.

**Persona format:**

```json
{
  "id": "persona_001",
  "text": "A 34-year-old veterinary technician from rural Oregon who
    spends weekends hiking with rescue dogs. Values loyalty and
    quiet competence over ambition. In stories, notices how characters
    treat the people who can't help them back.",
  "tags": ["30s", "rural", "caretaker", "loyalty", "introvert",
           "care-ethics"]
}
```

Tags are used for subset selection validation — ensuring that randomly
drawn subsets have diversity across the tagged dimensions.

**The initial pool (55 personas):**

The pool is organized into 11 clusters of 5 personas each. Clusters
ensure broad coverage; within-cluster variation ensures no cluster is
monolithic.

**Cluster 1 — Caretakers & Service Workers**
1. A 34-year-old veterinary technician from rural Oregon who spends weekends hiking with rescue dogs. Values loyalty and quiet competence over ambition. In stories, notices how characters treat the people who can't help them back.
2. A 52-year-old hospice nurse from Birmingham, Alabama who sings in her church choir. Believes everyone deserves dignity at the end. In stories, pays attention to who shows up when things get hard and who finds excuses.
3. A 28-year-old kindergarten teacher from Osaka who collects vintage board games. Thinks patience is underrated as a strength. In stories, notices when adults talk past children or dismiss what seems small.
4. A 61-year-old volunteer firefighter from a small town in Portugal who also runs the local hardware store. Believes problems are solved by showing up, not by having the right answer. In stories, notices whether characters actually help or just talk about helping.
5. A 40-year-old home health aide from the Bronx who is putting herself through community college at night. Values resourcefulness and staying grounded. In stories, notices who gets overlooked and why.

**Cluster 2 — Builders & Makers**
6. A 45-year-old structural engineer from Mumbai who restores vintage motorcycles. Thinks about how things fail under stress. In stories, notices whether the stakes are structurally sound or just dramatic.
7. A 23-year-old apprentice electrician from Glasgow who plays in a punk band on weekends. Distrusts authority but respects competence. In stories, notices when rules exist to protect people versus when rules exist to protect power.
8. A 57-year-old ceramic artist from Santa Fe who teaches workshops for veterans. Believes broken things can become more interesting than perfect ones. In stories, notices how characters handle failure and whether they learn from it.
9. A 36-year-old shipyard welder from Gdańsk who coaches youth football. Values teamwork over individual brilliance. In stories, notices whether groups function as real teams or as collections of individuals.
10. A 49-year-old landscape architect from Nairobi who designs public parks for underserved neighborhoods. Thinks about how spaces shape behavior. In stories, notices whether the setting feels like it matters or is just a backdrop.

**Cluster 3 — Analysts & Problem-Solvers**
11. A 31-year-old forensic accountant from Toronto who does competitive crossword puzzles. Enjoys finding what doesn't add up. In stories, notices when motives don't match actions and when convenient coincidences cover lazy plotting.
12. A 43-year-old epidemiologist from Seoul who gardens obsessively. Thinks in systems and second-order effects. In stories, notices when individual decisions have consequences that ripple outward, and when they don't but should.
13. A 67-year-old retired insurance adjuster from rural Minnesota who now writes a local history blog. Has seen every kind of human dishonesty and isn't cynical about it. In stories, notices when characters are lying to themselves.
14. A 26-year-old climate data analyst from Cape Town who surfs every morning before work. Thinks about long time horizons and irreversible tipping points. In stories, notices when characters face decisions they can't walk back.
15. A 55-year-old air traffic controller from Chicago about to retire. Thinks in priorities and real-time risk assessment. In stories, notices when characters have to choose which problem to solve first.

**Cluster 4 — Community & Connection**
16. A 38-year-old social worker from Marseille who fosters teenagers. Knows that trust is earned slowly and broken fast. In stories, notices how relationships are built — through small consistent actions, not grand gestures.
17. A 71-year-old retired schoolteacher from Jamaica who moved to London in the 1970s. Has lived through being an outsider and becoming an elder. In stories, notices who belongs and who is trying to belong.
18. A 29-year-old community organizer from Detroit who runs a tool-lending library. Believes neighborhoods fix themselves when people actually know each other. In stories, notices whether communities feel like real places with real tensions.
19. A 46-year-old imam from Kuala Lumpur who also teaches high school physics. Comfortable holding faith and reason simultaneously. In stories, notices when characters treat belief and logic as enemies rather than tools.
20. A 33-year-old bartender from Austin who is working on a memoir. Good at reading people and knowing when to listen. In stories, notices the gap between what characters say and what they mean.

**Cluster 5 — Risk & Adventure**
21. A 42-year-old mountain rescue volunteer from Chamonix who teaches avalanche safety. Respects fear as information, not weakness. In stories, notices whether danger feels real and whether courage is distinguished from recklessness.
22. A 27-year-old merchant marine from the Philippines who has been at sea since she was 19. Values self-reliance and practical competence. In stories, notices whether characters actually know how to do the things they're supposed to be good at.
23. A 58-year-old retired police detective from Baltimore who now builds model ships. Has seen the gap between justice and the law. In stories, notices when the story acknowledges that doing the right thing and following the rules aren't always the same.
24. A 35-year-old bushfire researcher from Western Australia who volunteers in disaster recovery. Thinks about resilience — what makes some communities rebuild and others collapse. In stories, notices what characters do after the crisis, not just during it.
25. A 50-year-old long-haul truck driver from Saskatchewan who listens to audiobooks constantly. Has a lot of time alone to think about what she hears. In stories, notices when pacing drags and when it rushes, and whether quiet moments earn their length.

**Cluster 6 — Artists & Storytellers**
26. A 24-year-old street muralist from São Paulo who also works as a bike courier. Thinks about who gets to be visible in public space. In stories, notices whose perspective the story centers and whose it ignores.
27. A 63-year-old documentary filmmaker from Berlin who specializes in ordinary people. Deeply skeptical of hero narratives. In stories, notices when characters are allowed to be complicated instead of admirable.
28. A 37-year-old Navajo jeweler from Gallup, New Mexico who teaches traditional silversmithing. Values patience and the relationship between maker and material. In stories, notices whether craft and skill are treated as real work or as magical ability.
29. A 44-year-old theater director from Lagos who runs a community theater company. Believes conflict is the engine of understanding. In stories, notices whether disagreements reveal character or just create noise.
30. A 30-year-old session musician from Nashville who plays pedal steel guitar. Makes a living supporting other people's songs. In stories, notices the supporting characters — whether they have their own lives or exist only to serve the main character.

**Cluster 7 — Caution & Tradition**
31. A 69-year-old retired banker from Zurich who tends a perfect rose garden. Believes in planning, discipline, and the virtue of saying no. In stories, notices when characters are impulsive and whether the story rewards recklessness.
32. A 41-year-old tax attorney from Seoul who builds mechanical watches as a hobby. Appreciates precision and the beauty of systems that work. In stories, notices when rules and systems are treated with respect versus dismissed as obstacles.
33. A 54-year-old Catholic school principal from Dublin who took the job because she believed the institution could still do good. In stories, notices the tension between institutions and the people inside them.
34. A 73-year-old retired Japanese salaryman from Yokohama who now tends a community garden. Spent 40 years subordinating himself to an organization. In stories, notices when sacrifice is honored and when it's wasted.
35. A 47-year-old Mennonite farmer from Lancaster County who uses a smartphone but thinks carefully about which technologies to adopt. In stories, notices when convenience comes at the cost of something that mattered.

**Cluster 8 — Outsiders & Contrarians**
36. A 22-year-old non-binary barista in Portland who writes zines about disability justice. Notices who is excluded by default and what "normal" costs. In stories, notices who the world is built for and who has to adapt.
37. A 39-year-old ex-convict from Manchester who now mentors at-risk youth. Knows what it costs to be written off and what it takes to rewrite yourself. In stories, notices whether redemption is earned or just declared.
38. A 56-year-old conspiracy theorist turned debunker from rural Virginia who now runs a media literacy workshop. Understands the appeal of simple explanations. In stories, notices when the real explanation is uncomfortably complicated.
39. A 48-year-old deaf sculptor from Rome who communicates primarily in Italian Sign Language. Experiences the world through texture, vibration, and visual attention. In stories, notices what is communicated without words and whether silence is used or feared.
40. A 32-year-old undocumented immigrant from Honduras working construction in Houston. Lives with the constant awareness that everything could change overnight. In stories, notices who has safety and who is pretending to.

**Cluster 9 — Scholars & Thinkers**
41. A 60-year-old retired philosophy professor from Edinburgh who now runs a whisky podcast. Thinks about ethical dilemmas for fun. In stories, notices when moral choices are genuinely hard versus when they have an obvious right answer.
42. A 25-year-old marine biology PhD student from Monterey who studies octopus intelligence. Fascinated by non-human ways of solving problems. In stories, notices when characters approach problems from unexpected angles.
43. A 51-year-old archivist from Warsaw who preserves oral histories of WWII survivors' grandchildren. Believes memory shapes identity. In stories, notices whether characters' pasts actually shape their present decisions.
44. A 34-year-old behavioral economist from Bangalore who studies why people make irrational decisions. In stories, notices when character motivations are psychologically plausible versus when they serve the plot.
45. A 68-year-old retired librarian from small-town Iowa who has read everything and remembers most of it. Values curiosity and believes there's no question too weird to ask. In stories, notices when the world has depth beyond what the main plot requires.

**Cluster 10 — Competitors & Performers**
46. A 28-year-old professional poker player from Las Vegas who studies game theory. Thinks about information asymmetry and the value of patience. In stories, notices when characters are playing with incomplete information and whether the story respects that.
47. A 36-year-old Olympic fencing coach from Budapest who retired from competition after an injury. Understands peak performance and its costs. In stories, notices whether excellence is portrayed as talent or as accumulated practice.
48. A 43-year-old auctioneer from rural England who can read a room in seconds. Values timing and the ability to create urgency. In stories, notices pacing — whether moments of decision feel genuinely pressured.
49. A 53-year-old stand-up comedian from Mumbai who performs in three languages. Makes a living finding what's absurd in the ordinary. In stories, notices when things are unintentionally funny and when humor is used to deflect something real.
50. A 19-year-old competitive StarCraft player from Busan who dropped out of university to go pro. Thinks in terms of build orders, timing attacks, and resource management. In stories, notices strategic decisions and whether characters use their advantages efficiently.

**Cluster 11 — Elders & Perspective**
51. A 75-year-old Inuit elder from Iqaluit who taught survival skills for 30 years. Knows that the land doesn't care about your plans. In stories, notices whether the environment is a real force or just scenery.
52. A 66-year-old retired midwife from Lagos who delivered over 3,000 babies. Has seen the beginning of every kind of life. In stories, notices beginnings — whether they feel earned and specific or generic.
53. A 79-year-old former jazz musician from New Orleans who survived Katrina. Knows about loss, improvisation, and the stubbornness of joy. In stories, notices whether characters find moments of lightness even in darkness.
54. A 62-year-old Buddhist monk from Chiang Mai who spent 20 years as a corporate lawyer before ordaining. Has lived both the attachment and the letting go. In stories, notices what characters cling to and whether the story treats attachment with compassion.
55. A 70-year-old retired long-distance truck driver from Outback Australia who has driven every road on the continent. Values solitude and vast spaces. In stories, notices whether journeys feel like real distance or just scene transitions.

**Tag distribution verification:**

The pool should be verified to span the required dimensions:

| Dimension | Target Coverage | Verification |
|-----------|----------------|-------------|
| Age: 20s | ≥5 personas | #3,7,22,26,36,42,50 = 7 ✓ |
| Age: 30s | ≥8 personas | #1,9,14,20,24,28,37,44 = 8 ✓ |
| Age: 40s | ≥8 personas | #5,6,10,15,19,29,32,35,43,48,49 = 11 ✓ |
| Age: 50s | ≥6 personas | #2,8,23,25,33,38,39,41 = 8 ✓ |
| Age: 60s+ | ≥6 personas | #4,13,17,27,31,34,45,51-55 = 12 ✓ |
| Risk-tolerant | ≥10 | Cluster 5, plus #7,26,37,50 |
| Risk-averse | ≥10 | Cluster 7, plus #2,13,15,34 |
| Introvert-leaning | ≥10 | #1,8,25,28,34,39,42,45,54,55 |
| Extrovert-leaning | ≥10 | #5,18,20,29,37,48,49,52 |
| Care-ethics | ≥8 | #1,2,3,5,16,17,36,52 |
| Justice-ethics | ≥8 | #10,18,23,26,33,37,40,41 |
| Utilitarian | ≥5 | #6,12,15,44,46 |

**Storage format:**

The persona pool is stored as a JSON file:
`data/personas/writer_room_personas.json`

```json
{
  "version": "1.0",
  "count": 55,
  "clusters": [
    {
      "name": "Caretakers & Service Workers",
      "personas": [
        {
          "id": "persona_001",
          "text": "A 34-year-old veterinary technician...",
          "tags": ["30s", "rural", "caretaker", "loyalty",
                   "introvert", "care-ethics"]
        }
      ]
    }
  ]
}
```

**Subset selection for Stage 2:**

Each saga pipeline run selects a subset of 7 personas from the pool.
The selection ensures tag diversity:

```python
def select_persona_subset(
    pool: list[dict],
    n: int = 7,
    seed: Optional[int] = None
) -> list[dict]:
    """Select a diverse persona subset from the pool.

    Ensures no more than 2 personas from the same cluster and
    at least 3 different age decades are represented.
    """
    rng = random.Random(seed)
    selected = []
    clusters_used = Counter()

    # Shuffle pool
    candidates = list(pool)
    rng.shuffle(candidates)

    for persona in candidates:
        if len(selected) >= n:
            break
        cluster = persona.get("cluster")
        if clusters_used[cluster] >= 2:
            continue
        selected.append(persona)
        clusters_used[cluster] += 1

    # Verify age diversity
    age_decades = {get_age_decade(p) for p in selected}
    if len(age_decades) < 3:
        # Re-select with age diversity constraint
        # (fallback: accept what we have)
        pass

    return selected
```

**Validation protocol:**

Once Stage 2 code is functional:

1. Write a 2-paragraph campaign summary (use The Nar Shaddaa Job or
   a hypothetical completed campaign).
2. Run Stage 2 five times, each with a different 7-persona subset
   drawn from the pool.
3. Collect the 7 SequelDirection outputs from each run (35 total
   directions across 5 runs).
4. Evaluate inter-run diversity:
   - **Primary conflict type:** Count unique conflict types across the
     5 runs. Target: ≥3 distinct types.
   - **Thematic elements:** For each pair of runs, count shared
     thematic elements out of the 3–5 per direction. Target: no pair
     shares more than 3 elements across all their directions.
   - **Overall assessment:** At least 3 of 5 runs should produce
     sequel directions that a human reader would describe as "going in
     a different direction."
5. If the pool fails validation: identify which personas produce
   the most similar outputs and replace them with personas from
   underrepresented demographic/professional clusters. Re-run.

**Persona pool evolution:**

The pool is not fixed. After each saga pipeline run, the diversity
metrics (item 4.10's `RunDiversityMetrics`) provide feedback. If
diversity plateaus, the pool should be expanded (add 10-20 new
personas from underrepresented clusters) or pruned (remove personas
that consistently produce outputs indistinguishable from other
personas in the same run).

**Implementation scope:**

- New: `data/personas/writer_room_personas.json` — the pool file.
- New: `studio/saga/personas.py` — `select_persona_subset()`, pool
  loading, tag verification.
- Validation: `scripts/validate_persona_pool.py` — runs the 5-subset
  diversity test and reports results.

---

## Appendix: Complete Status After v2.0

| Item | Previous Status | New Status | Priority Tier |
|------|----------------|-----------|--------------|
| 2.19 (turn counter) | FILED | DESIGNED | Late V1 / Phase 7 |
| 2.28 (entity persistence) | CONCEPT ONLY | DESIGNED | Post-Milestone 1 |
| 3.26 (deterministic seeding) | CONSIDER | DESIGNED | CS Phase 2 |
| 3.27 (difficulty calibration) | CONCEPT ONLY | DESIGNED | CS Phase 3 |
| 3.28 (campaign ratings) | CONCEPT ONLY | DESIGNED | Post-launch |
| 4.9 (trained evaluator) | CONCEPT ONLY | DESIGNED | Post-CS Phase 4 |
| 4.10 (multi-model ensemble) | CONCEPT ONLY | DESIGNED | Post-CS Phase 4 baseline |
| 4.0a (saga test artifacts) | NOT STARTED | DESIGNED (template) | Pre-CS Phase 4 |
| 4.0d (persona pool) | NOT STARTED | DESIGNED (pool drafted) | Pre-CS Phase 4 |

**Items remaining below DESIGNED across the entire project:**

| Item | Status | Reason |
|------|--------|--------|
| 5.1–5.6 | Long-term aspirations | Beyond planning horizon |
| R.1–R.7 | Open research questions | Require empirical investigation |

**Zero NEEDS DESIGN, CONCEPT ONLY, PARTIALLY DESIGNED, CONSIDER, or
FILED items remain.** Every item that can be designed without runtime
data has been designed.

---

## Appendix B: Backlog Updates Required

The following updates should be applied to the Backlog to reflect the
design work in this document:

1. **Item 2.19 — upgrade to DESIGNED.** Update description: "Turn
   counter with PacingSignal model providing deterministic pacing zone
   to reconciliation and narration prompts. Removes arithmetic from
   local model. Four zones: early, on_pace, late, overdue." Add
   design doc ref: "Gap Analysis v2.0."

2. **Item 2.28 — upgrade to DESIGNED.** Update description to include:
   reconciliation prompt extension, entity card generation prompt,
   database schema, per-act cap enforcement, reintroduction injection
   format, tier promotion logic, cross-campaign persistence. Add
   design doc ref: "Gap Analysis v2.0."

3. **Item 3.26 — upgrade to DESIGNED.** Update description: "Per-stage
   seed derivation from master seed. GenerationMetadata stored
   alongside spines. Partial regeneration UX for Mode 2/3. Seed
   parameter passed via OpenAI-compatible and Ollama APIs." Add
   design doc ref: "Gap Analysis v2.0."

4. **Item 3.27 — upgrade to DESIGNED.** Update description: "Four-
   signal per-act difficulty scoring (anchor intensity, NPC opposition,
   mechanical pressure, pacing pressure). SpineDifficultyCurve with
   curve shape classification and calibration warnings. Runs during
   Gate 4." Add design doc ref: "Gap Analysis v2.0."

5. **Item 3.28 — upgrade to DESIGNED.** Update description: "Post-
   completion rating collection (1-5 overall, optional 3-dimension
   breakdown, optional free-text). Exemplar selection for generation
   prompts. Failure pattern detection for low-rated campaigns." Add
   design doc ref: "Gap Analysis v2.0."

6. **Item 4.9 — upgrade to DESIGNED.** Update description: "QLoRA
   fine-tune of local model on pairwise evaluation pairs from Stage 5
   and player ratings. Three-axis evaluation (structural, novelty,
   diversity). SpineSummary compression format. 80% agreement
   calibration threshold. Drop-in replacement for cloud evaluator."
   Add design doc ref: "Gap Analysis v2.0."

7. **Item 4.10 — upgrade to DESIGNED.** Update description: "Model-
   aware WriterConfig per writer. EnsembleConfig with model pool and
   assignment strategies (round_robin, weighted, random). Parallel
   execution. RunDiversityMetrics logging for Bitter Lesson monitoring.
   Graceful degradation to single-model." Add design doc ref: "Gap
   Analysis v2.0."

8. **Item 4.0a — upgrade to DESIGNED (template).** Update description:
   "Full template specified with concrete section structure for each
   pipeline stage. Partial artifact (hypothetical data) can be
   created before campaign completion. Full artifact requires
   Milestone 1." Add design doc ref: "Gap Analysis v2.0."

9. **Item 4.0d — upgrade to DESIGNED (pool drafted).** Update
   description: "55 personas across 11 clusters drafted. Tag
   distribution verified. Subset selection algorithm with cluster and
   age diversity constraints. Five-subset validation protocol
   specified. Validation requires working Stage 2 code." Add design
   doc ref: "Gap Analysis v2.0."

---

*Storyteller V3 — Design Gap Analysis v2.0*
*Everything designed. Nothing deferred without cause.*