> **SPECIALIST SPEC** — Quality standards for cross-campaign character
> import compression.
> **Build phase:** Phase 19 (Cross-Era Import/Export, not yet started).
> **Design authority for:** import package quality rubrics, compression
> validation, narrative preservation requirements.
> **Depends on:** Game Mechanics §20, CS Implementation §6, Phases 7/12/13.
>
> **Implementation Status: NOT STARTED**
> The quality standards and validation logic below are the design
> specification for Phase 19. The mechanical import interface exists
> (`studio/import_interface.py`) but the narrative quality layer
> described here has not been implemented.

# Storyteller V3 — Import Package Quality Spec

**Version:** 1.0
**Date:** March 6, 2026
**Purpose:** Quality standards for the narrative components of the
import package. The existing design (Game Mechanics §20, Campaign Studio
Implementation §6) specifies what gets imported and the format of each
field. This spec defines what makes a *good* import — the fidelity bar
that prevents a sequel from being technically continuous but emotionally
generic.

**What this spec does NOT replace:** The import package contents,
specialization mapping, XP rebalancing, equipment transition, and
transition processing are all specified in GM §20 and CS Impl §6. This
document adds quality standards and validation for the narrative
fields only.

**Build phase:** Phase 19 (Cross-Era Import/Export). This spec is not
needed until then, but is authored now to ensure the quality bar is
defined before compression logic is implemented.

---

## 1. The Problem

The import package carries forward both mechanical and narrative state.
The mechanical state is straightforward — numbers, lists, and mappings
that transfer without quality loss. The narrative state is the problem.

Five narrative fields must survive compression:

1. **NPC relationship summaries** — full state cards compressed to
   one-paragraph distillations
2. **Throughline question history** — the prior campaign's throughline
   and how the character answered it
3. **Character voice notes** — how the character speaks, thinks, and
   presents, evolved through play
4. **Advancement log** — what the character became and when
5. **World state variables** — butterfly-effect booleans (these are
   mechanical, not narrative, and transfer without quality loss)

Fields 1–4 are produced by compression — an LLM summarizing rich state
into compact form. Compression that preserves facts but loses emotional
specificity produces a sequel where the character is technically the
same person but doesn't *feel* like the same person.

---

## 2. Quality Dimensions

Each narrative field is evaluated against specific preservation
requirements. The compression system must preserve these qualities;
the validation system must verify them.

### 2.1 NPC Relationship Summaries

**What they are:** One-paragraph distillations of significant
relationships, keyed by NPC name. Produced at campaign completion by
compressing the full NPC state card (disposition history, knowledge
state, interaction log) into narrative prose.

**What must be preserved:**

| Quality | Description | Example of loss |
|---------|-------------|-----------------|
| **Relationship tension** | The unresolved friction or asymmetry in the relationship. Not just "they get along" but what makes the relationship interesting. | "Keth trusts Doss" vs. "Keth trusts Doss but has never tested whether Doss would choose Keth over self-preservation" |
| **Emotional valence and trajectory** | Not just current disposition but the direction of change. Was trust growing or eroding? Was hostility softening or hardening? | "Disposition: 0.72" vs. "Started wary, grew to genuine respect after Act 2, but the cargo incident in Act 3 introduced doubt that neither has addressed" |
| **Specific shared history** | At least one concrete event that anchors the relationship in lived experience rather than abstract description. | "Close allies" vs. "Doss pulled Keth out of the warehouse fire on Nar Shaddaa — and Keth still doesn't know if Doss started it" |
| **Information asymmetry** | What each party knows or believes about the other that the other doesn't know. | Omitting "Doss doesn't know Keth saw him talking to the ISB agent" |

**Minimum standard:** Each summary must contain at least one
relationship tension, the emotional trajectory direction (improving /
deteriorating / stable / complicated), and one specific shared event.
Information asymmetries are included when they exist.

### 2.2 Throughline Question History

**What it is:** The prior campaign's throughline question and a summary
of how the character's choices answered it (or didn't).

**What must be preserved:**

| Quality | Description | Example of loss |
|---------|-------------|-----------------|
| **The question itself** | Verbatim from the campaign. | Paraphrasing "Can a man who has only ever looked out for himself become someone worth following?" into "The character struggled with leadership" |
| **The answer-in-progress** | Where the character's choices left the question — not a definitive answer but the trajectory and the evidence. | "The character developed over the campaign" vs. "His choices consistently answered 'yes, but only for specific people' — he would die for Doss but would not risk himself for a stranger's cause" |
| **Unresolved tension** | What the character's choices left open or contradicted. The most interesting throughlines are never fully resolved. | Omitting "He saved the refugees in Act 3 despite everything, which he still can't explain to himself" |

**Minimum standard:** The throughline question preserved verbatim,
the answer-in-progress in the character's own terms (not abstract
psychological language), and at least one unresolved tension or
contradiction.

### 2.3 Character Voice Notes

**What they are:** 2–5 sentences describing how the character speaks,
thinks, and presents. These calibrate every passage of prose the GM
writes.

**What must be preserved:**

| Quality | Description | Example of loss |
|---------|-------------|-----------------|
| **Specificity of expression** | Concrete details about how this person communicates — cadence, vocabulary, habits, silences. | "Speaks casually" vs. "Talks around things he cares about — uses humor to create distance, goes quiet when something actually matters" |
| **Internal voice** | How the character's interiority reads — what their inner monologue sounds like, what they notice, what they avoid thinking about. | Omitting "Notices exits before he notices people. Has started noticing people first, which bothers him" |
| **Evolution markers** | How the voice changed during the campaign. The voice notes at export should reflect who the character became, not just who they started as. | Using the variant's original authored voice notes unchanged |

**Minimum standard:** Voice notes must contain at least one concrete
behavioral or linguistic detail (not just adjectives), at least one
internal observation, and must differ from the variant's starting
voice notes if the character experienced meaningful change.

### 2.4 Advancement Log

**What it is:** A structured record of what the character became and
when — skill rank increases, talents acquired, specializations entered,
Force awakening, characteristic increases.

**What must be preserved:**

| Quality | Description | Example of loss |
|---------|-------------|-----------------|
| **Narrative framing** | Each entry should carry the narrative context of why this growth happened, not just the mechanical change. | "Deception 2 → 3" vs. "Deception 2 → 3 (Act 2 — learned to lie to protect Doss, not just to protect himself)" |
| **Milestone moments** | The specific reflection passages that accompanied transformative growth events. | Omitting the milestone text that accompanied the character's first specialization choice |

**Minimum standard:** Each advancement entry includes the act number,
the mechanical change, and a one-sentence narrative context. Milestone
reflection passages (Category 2+ from GM §14.3) are preserved in full
— they are short (2-4 sentences) and carry irreplaceable character
identity.

---

## 3. Compression Method

### 3.1 Who Compresses

The compression runs at campaign completion as part of the export
process (Phase 19). It uses the **cloud model**, not the local model.
The quality requirements above are beyond the local model's prose
capability (LLM Eval rates it 2/5 on prose quality). The compression
is a one-time cost per completed campaign — a single cloud call per
narrative field, or a single combined call.

### 3.2 Compression Prompt Structure

The compression prompt receives the raw data and the quality
requirements as explicit instructions:

```
You are compressing a character's campaign history for import into
a new campaign. The compressed output must preserve the character's
emotional reality, not just their factual record.

CHARACTER: {character_name}
CAMPAIGN: {campaign_name}

{field_specific_instructions}

RAW DATA:
{raw_field_data}

Compress to the specified format. Preserve relationship tensions,
emotional trajectories, specific shared events, and unresolved
contradictions. Generic summaries that could describe any character
are failures.
```

Each field gets field-specific instructions drawn from the quality
dimensions in Section 2.

### 3.3 Compression Validation

After compression, each field is validated against its minimum
standard. The validation is structural where possible and LLM-assisted
where necessary.

**Structural checks (pure Python):**

- Throughline question preserved verbatim (string match against the
  campaign's throughline)
- Voice notes differ from the variant's starting voice notes (string
  similarity below threshold — exact implementation TBD)
- Advancement log entries include act numbers and mechanical changes
- NPC relationship summaries are keyed by NPC name and non-empty

**LLM-assisted checks (local model, structured JSON):**

```
Evaluate this relationship summary for compression quality.

NPC NAME: {npc_name}
SUMMARY: {summary_text}

Answer each question YES or NO:
1. TENSION: Does the summary describe unresolved friction, asymmetry,
   or complication in the relationship (not just positive/negative)?
2. TRAJECTORY: Does the summary indicate whether the relationship was
   improving, deteriorating, stable, or complicated?
3. SPECIFIC: Does the summary reference at least one concrete event
   from the campaign (not just abstract description)?
4. ASYMMETRY: If information asymmetry existed, is it mentioned?

{"tension": true/false, "trajectory": true/false,
 "specific": true/false, "asymmetry": true/false}
```

A summary that fails on tension or specific is flagged for
regeneration. Trajectory and asymmetry failures are logged as
warnings.

### 3.4 Regeneration on Failure

If a compressed field fails validation, the system retries the
compression once with a correction message identifying the missing
quality dimension. If the second attempt also fails, the system
accepts the result and logs the quality gap. A low-quality import is
better than a blocked campaign transition.

---

## 4. Memory Shards

Beyond the structured narrative fields, the import package includes
2–4 **memory shards** — brief, evocative prose fragments drawn from
the campaign's most significant moments. These are not summaries.
They are snapshots: a sentence or two of narration from a moment that
defined the character.

### 4.1 Purpose

Memory shards serve two functions in the receiving campaign:

**Transition passage enrichment.** The cloud GM's transition passage
(GM §20.3) receives the memory shards as context. They give the GM
concrete sensory material to reference when bridging from the old
campaign to the new one. Instead of "He thought about his time on Nar
Shaddaa," the GM can reference the specific moment: the smell of the
warehouse fire, the sound of Doss's voice on the comm.

**Reputation echo material.** Memory shards can surface as reputation
echoes in the new campaign — moments the character remembers, triggered
by environmental similarity or NPC connection. A shard about a
betrayal surfaces when the character faces a similar situation. A shard
about a rescue surfaces when someone mentions the place it happened.

### 4.2 Selection Criteria

Memory shards are selected from the campaign's turn history at export
time. The selection prioritizes:

1. **Turns with high `throughline_relevance`** from the semantic memory
   annotations (GM §24). These are the moments that most directly
   addressed the campaign's central question.
2. **Turns at act boundaries** — the climactic moments of each act.
3. **Turns with extreme NPC disposition changes** — the moments where
   relationships shifted dramatically (betrayals, rescues, revelations).
4. **Turns with Triumph or Despair results** — the dice moments that
   produced exceptional outcomes.

From the candidate pool, select the 2–4 turns whose narration excerpts
(stored in the `narration_excerpt` field on turn records) are most
distinct from each other in content and emotional register. Two shards
about combat are less useful than one about combat and one about a
quiet conversation.

### 4.3 Shard Format

```json
{
  "shard_id": "nar_shaddaa_warehouse_fire",
  "source_act": 2,
  "source_turn": 14,
  "trigger_tags": ["fire", "warehouse", "doss", "rescue", "betrayal"],
  "excerpt": "The heat hit him before the light did. Somewhere in the
    back of the building, something structural gave way with a sound
    like a ship's hull breach. Doss was in there. Doss was in there
    and the door was still locked."
}
```

**`trigger_tags`:** Keywords that the reputation echo system and
transition passage generator can match against current scene context.
When a new campaign scene involves fire, warehouses, or Doss, the
relevant shard becomes available for injection.

**`excerpt`:** 2–4 sentences of narration from the original turn.
These are the GM's own words from the moment — preserved verbatim,
not rewritten or summarized.

---

## 5. The Identity Test

The ultimate quality bar for the import package is not whether each
field passes its individual checks. It is whether the receiving
campaign produces a character who feels like the same person.

### 5.1 The Test

After import processing and before the first act begins, the system
runs a single cloud model evaluation call. The prompt provides: the
import package's narrative fields (relationship summaries, throughline
history, voice notes, advancement log, memory shards) and the
variant's original authored baseline (starting voice notes, starting
throughline, starting relationships).

The cloud model answers one question:

```
Based on the import package below, could you write a paragraph of
this character's interiority that would be recognizably different
from the authored baseline? If the import package has enough specific,
personal detail to produce a voice distinct from the generic variant,
answer YES. If the import package reads like it could describe any
character of this variant type, answer NO.

AUTHORED BASELINE:
{variant_starting_state}

IMPORT PACKAGE (NARRATIVE FIELDS):
{compressed_narrative_fields}

Answer: YES or NO, then one sentence explaining why.
```

### 5.2 What Happens on Failure

A NO answer does not block the import. It logs a quality warning
that is surfaced to the player as part of the campaign transition:

*"Your character's history from the previous campaign has been
imported. Some details of your journey may be less detailed than
others — but the story continues."*

This is an honest acknowledgment that the compression was imperfect.
It sets expectations without breaking immersion.

A YES answer logs a quality success. No player-visible message is
needed — the character simply feels right.

### 5.3 When to Run

The identity test runs once per import, at import processing time
(between campaign completion and new campaign first act). It is a
single cloud call and adds 5–10 seconds to the transition. The player
is experiencing a transition passage during this time, so the delay
is invisible.

---

## 6. Schema Additions

### 6.1 Import Package Narrative Extension

The import package data model (GM §20.1, CS Impl §6.1) gains:

```python
class MemoryShard(BaseModel):
    shard_id: str
    source_act: int
    source_turn: int
    trigger_tags: list[str] = Field(min_length=2)
    excerpt: str = Field(min_length=20, max_length=500)

class NarrativeImportFields(BaseModel):
    relationship_summaries: list[RelationshipSummary]
    throughline_history: ThroughlineHistory
    voice_notes: str = Field(max_length=500)
    advancement_log: list[AdvancementEntry]
    memory_shards: list[MemoryShard] = Field(
        min_length=2, max_length=4
    )
    identity_test_passed: Optional[bool] = None

class RelationshipSummary(BaseModel):
    npc_name: str
    summary: str = Field(min_length=50)
    disposition_at_export: float = Field(ge=0.0, le=1.0)
    era: str
    last_campaign: str

class ThroughlineHistory(BaseModel):
    question: str  # verbatim from campaign
    answer_in_progress: str = Field(min_length=30)
    unresolved_tensions: list[str] = Field(min_length=1)

class AdvancementEntry(BaseModel):
    act: int
    mechanical_change: str
    narrative_context: str = Field(min_length=10)
    milestone_text: Optional[str] = None  # preserved for Category 2+
```

### 6.2 Compression Quality Log

```sql
CREATE TABLE IF NOT EXISTS import_quality_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    source_campaign_id TEXT NOT NULL,
    target_campaign_id TEXT NOT NULL,
    field TEXT NOT NULL,
    validation_result TEXT NOT NULL,
    quality_flags TEXT,
    identity_test_passed BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 7. Build Phase and Dependencies

**Target phase:** Phase 19 (Cross-Era Import/Export).

**Dependencies:**
- Phase 12 (milestone reflections — advancement log entries require
  milestone text)
- Phase 13 (semantic memory — memory shard selection uses
  `throughline_relevance` annotations)
- Phase 7 (reconciliation — NPC state cards must be fully populated
  for relationship summary compression)

**Backlog integration:** Add quality requirements to item 2.27
(multi-arc campaign structure) and create a new cross-cutting item
referencing this spec for import package validation.

---

*Storyteller V3 — Import Package Quality Spec v1.0*  
*Technical continuity is the floor. Emotional continuity is the bar.*
