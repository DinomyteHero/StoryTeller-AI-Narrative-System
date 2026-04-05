> **SPECIALIST SPEC** — Story architecture vocabulary, quality rubrics,
> and Gate 4 narrative evaluation for the Campaign Studio.
> **Build phase:** CS-5 (Campaign Studio Narrative Quality) — COMPLETE.
> **Design authority for:** architectural vocabulary, Gate 4a/4b/4c
> evaluation, pre-generation planning, narrative quality scoring.
> **Depends on:** Campaign Studio validation infrastructure.

# Story Architecture Specification

**Version:** 1.0
**Date:** April 3, 2026
**Phase:** CS-5 (Campaign Studio Narrative Quality)

## Purpose

This document defines the vocabulary, rubrics, and validation rules for
story architecture in the Campaign Studio. It is the design spec for
the pre-generation planning layer (`studio/architect.py`), Gate 4
narrative evaluation (`studio/narrative_eval.py`), and enhanced
generation prompts.

The existing Campaign Studio produces structurally sound campaign
spines. This specification adds the layer that makes those spines
**dramatically strong** — campaigns that create genuine pressure,
test characters meaningfully, and resist generic patterns.

---

## 1. Story Architecture Vocabulary

### 1.1 Concept Architecture

| Field | Definition | Schema Field |
|-------|-----------|-------------|
| **Dramatic Premise** | The core tension that makes this campaign worth playing. Not a plot summary — a pressure statement. "A smuggler discovers her cargo is a person" is premise. "A smuggler goes to Nar Shaddaa" is not. | `StoryArchitecture.dramatic_premise` |
| **Central Dramatic Question** | The question the campaign exists to explore. Distinct from `throughline_question` (which is what the player ponders). The CDQ is what the *campaign structure* tests. | `StoryArchitecture.central_dramatic_question` |
| **Story Promise** | What the player can expect to experience. Not "what happens" but "what this feels like." A promise of escalating moral compromise, or of identity erosion under pressure. | `StoryArchitecture.story_promise` |
| **Protagonist Pressure Type** | The category of pressure the campaign applies to the protagonist. One of: moral (right vs. right), identity (who you are vs. who you must become), loyalty (competing allegiances), survival (sacrifice vs. self-preservation), ideological (belief vs. evidence). | `StoryArchitecture.protagonist_pressure_type` |
| **Antagonistic Force** | The systemic pressure that creates opposition. Not a villain — a condition. "Imperial occupation makes trust impossible" is an antagonistic force. "Darth Villain wants to destroy the galaxy" is not. Individuals may embody the force, but the force exists beyond any single NPC. | `StoryArchitecture.antagonistic_force` |

### 1.2 Character Architecture

| Field | Definition | Schema Field |
|-------|-----------|-------------|
| **Protagonist Contradiction** | What the character believes about themselves vs. who they actually are. "Believes she's a survivor who doesn't need anyone — actually terrified of being alone." This contradiction is what the campaign tests. | `CharacterVariant.protagonist_contradiction` |
| **Pressure-Revealed Identity** | Who the character becomes when the premise puts them under maximum pressure. Not a prediction — a design intention. The campaign should create conditions where this identity either emerges or is resisted. | `CharacterVariant.pressure_revealed_identity` |

### 1.3 Structural Architecture

| Field | Definition | Schema Field |
|-------|-----------|-------------|
| **Dramatic Function** | What each act does in the campaign's dramatic arc. Beyond tension category — the *purpose* of the act. | `Act.dramatic_function` |

Valid dramatic functions:
- **setup** — Establishes normalcy, relationships, stakes. The world before pressure.
- **destabilization** — First disruption. Something the protagonist relied on breaks or shifts.
- **launch** — The point of no return. After this act, going back to normalcy is impossible.
- **midpoint_shift** — A revelation or reversal that reframes everything that came before.
- **escalation** — Pressure intensifies. Consequences of earlier choices compound.
- **confrontation** — The protagonist must face the central dramatic question directly.
- **consequence** — The aftermath. What the confrontation actually cost or changed.
- **resolution** — Not closure — consequence. The world after the campaign's pressure.

### 1.4 Thematic Architecture

| Field | Definition | Schema Field |
|-------|-----------|-------------|
| **Thematic Throughline** | The recurring idea the campaign explores from multiple angles. Not a message — a question embodied in structure. "Whether loyalty earned through crisis can survive peace" recurs when NPCs embody competing answers. | `StoryArchitecture.thematic_throughline` |
| **Thematic Argument** (per NPC) | What this NPC's existence and behavior argues about the campaign's theme. Each major NPC should embody a different answer to the thematic throughline. | `NPC.thematic_argument` |
| **Ending Payoff Sketch** | How the final act connects back to the dramatic premise and CDQ. Not a scripted ending — a design intention for what the ending should *feel like* based on how the premise was tested. | `StoryArchitecture.ending_payoff_sketch` |

---

## 2. Quality Rubrics

### 2.1 Gate 4a: Narrative Coherence

Checks whether the spine is internally consistent as a story, not just
as a data structure.

| Check | Pass Condition | Failure Mode |
|-------|---------------|-------------|
| **Thread continuity** | Every thread opened in `open_threads` is either resolved in a later act or explicitly carried as unresolved tension. | A thread appears in Act 1 and is never referenced again. |
| **NPC trajectory consistency** | NPC `per_act_state` changes are explained by act events, not arbitrary. Disposition shifts > 0.3 have causal grounding in the act's situation. | An NPC goes from hostile to loyal between acts with no catalyst. |
| **Throughline presence** | The `throughline_question` is testable in at least 2 acts (not just stated in Act 1 and forgotten). | Throughline is "Can trust survive betrayal?" but no acts involve trust or betrayal. |
| **Galactic context relevance** | Each act's `galactic_context` connects to the campaign's pressure, not generic setting. | "The Empire tightens its grip" appears in every act regardless of plot. |

### 2.2 Gate 4b: Dramatic Quality

Only runs when `story_architecture` is populated. Checks whether the
architecture brief actually manifests in the spine structure.

| Check | Pass Condition | Failure Mode |
|-------|---------------|-------------|
| **Premise manifestation** | The `dramatic_premise` creates observable pressure in at least the launch and confrontation acts. | Premise is "a healer must choose between saving her patient and exposing a conspiracy" but no act puts her in that position. |
| **CDQ testability** | The `central_dramatic_question` is testable through at least one variation point or anchor beat. | CDQ is "Is redemption possible for the irredeemable?" but no NPC or beat tests this. |
| **Antagonistic force presence** | The `antagonistic_force` is reflected in act galactic contexts or NPC behaviors, not just stated. | Force is "Imperial bureaucracy makes honesty dangerous" but no NPC or situation involves bureaucracy. |
| **NPC thematic diversity** | At least 2 NPCs with `thematic_argument` fields embody *different* answers to the throughline. | All NPCs effectively argue the same position. |
| **Protagonist contradiction testability** | At least one act's anchor or situation creates conditions where the `protagonist_contradiction` is tested. | Contradiction is "believes violence solves nothing — resorts to violence under pressure" but no act creates that pressure. |

### 2.3 Gate 4c: Anti-Genericity Audit

Catches patterns that are structurally sound but dramatically flat.

| Check | Pass Condition | Failure Mode |
|-------|---------------|-------------|
| **NPC distinctiveness** | NPCs have distinguishable motivations, voice notes, and behavioral envelopes. Swapping two NPCs' names should change the story. | Two NPCs have near-identical motivations ("protect the community") and similar voice notes. |
| **Tension variety** | Not all acts have the same tension category or dramatic function pattern. | Every non-final act is "rising" tension. |
| **Anchor specificity** | Anchors describe specific dramatic moments, not generic encounters. "Keth discovers the cargo manifest names his sister" vs. "Keth investigates the cargo." | Anchors read like quest objectives rather than dramatic beats. |
| **Disposition realism** | NPC disposition trajectories include genuine uncertainty or reversal, not monotonic arcs. | Every NPC starts neutral and becomes either allied or hostile — no complexity. |
| **Escalation authenticity** | Later acts raise stakes that feel earned by earlier choices, not arbitrary "bigger threat" escalation. | Act 1: local problem. Act 2: planetary crisis. Act 3: galactic threat. (Scale escalation without causal chain.) |

---

## 3. Pre-Generation Architecture Brief

### 3.1 Flow

```
Mode 1/2 Input
      ↓
  architect.py: generate_architecture()
      ↓
  StoryArchitecture object
      ↓
  generate.py: generate_from_brief() / generate_mode1()
  (architecture injected into prompt)
      ↓
  Campaign Spine (with story_architecture populated)
      ↓
  validate.py: Gate 4 checks architecture ↔ spine alignment
```

### 3.2 Architecture Generation Prompt Design

The architect prompt should:

1. **Accept** the same inputs as Mode 1/2 (era, location, tone, etc.)
2. **Produce** a `StoryArchitecture` JSON with all fields populated
3. **Apply** the same anti-default constraints as generation
4. **Focus on** dramatic design, not structural fields
5. **Use** lower temperature (0.7) for coherent architecture
6. **Use** shorter max tokens (2000) — architecture is concise

The generated architecture is then injected into the Mode 1/2 prompt
as an additional section:

```
## STORY ARCHITECTURE (generate the spine to embody this)

Dramatic Premise: {dramatic_premise}
Central Dramatic Question: {central_dramatic_question}
Story Promise: {story_promise}
Protagonist Pressure Type: {protagonist_pressure_type}
Antagonistic Force: {antagonistic_force}
Thematic Throughline: {thematic_throughline}
Ending Payoff Sketch: {ending_payoff_sketch}
```

### 3.3 Saga Pipeline Integration

For the saga layer, architecture generation sits between Stage 2
(diverge) and Stage 3 (search). Each `SequelDirection` gets an
architecture brief before being expanded into a `SpineSketch`.

New seeding stage: `STAGE_ARCHITECT`

---

## 4. Evaluation Scoring (Stage 5 Enhancement)

### 4.1 Current Scoring (Retained)

- `structural_quality` (50%): Schema completeness, field population
- `novelty` (25%): NPC count, tension variety, variation points
- `diversity_vs_prior` (25%): Allegiance distinctiveness, relationships

### 4.2 New Scoring Dimension

- `narrative_quality` (new): LLM-assessed dramatic strength

When narrative quality scoring is active, weights rebalance:
- `structural_quality`: 35%
- `novelty`: 15%
- `diversity_vs_prior`: 15%
- `narrative_quality`: 35%

Narrative quality is scored via a single LLM call with a structured
rubric (5-point scale per dimension):
1. Premise strength (1-5)
2. NPC thematic diversity (1-5)
3. Dramatic function progression (1-5)
4. Throughline testability (1-5)
5. Anti-genericity (1-5)

Composite: mean of 5 dimensions, normalized to 0.0-1.0.

---

## 5. Implementation Files

| File | Purpose | New/Modified |
|------|---------|-------------|
| `studio/schema.py` | `StoryArchitecture` model, new optional fields | Modified |
| `studio/architect.py` | Pre-generation architecture planning | New |
| `studio/narrative_eval.py` | Gate 4 implementation (4a, 4b, 4c) | New |
| `studio/validate.py` | Wire Gate 4 to `narrative_eval.py` | Modified |
| `studio/generate.py` | Inject architecture into generation flow | Modified |
| `studio/seeding.py` | Add `STAGE_ARCHITECT` constant | Modified |
| `studio/saga/select.py` | Add narrative quality scoring dimension | Modified |
| `studio/prompts/mode1_generate.txt` | Add architecture section | Modified |
| `studio/prompts/mode2_generate.txt` | Add architecture section | Modified |
| `studio/prompts/architect.txt` | Architecture generation prompt | New |
| `studio/prompts/narrative_eval.txt` | Gate 4 evaluation prompt | New |
| `studio/prompts/narrative_score.txt` | Stage 5 scoring prompt | New |
| `tests/test_cs5_narrative_quality.py` | CS-5 test suite | New |

---

## 6. Backward Compatibility

All new schema fields are optional with defaults:
- `CampaignSpine.story_architecture: Optional[StoryArchitecture] = None`
- `CharacterVariant.protagonist_contradiction: str = ""`
- `CharacterVariant.pressure_revealed_identity: str = ""`
- `Act.dramatic_function: str = ""`
- `NPC.thematic_argument: str = ""`

Existing campaign spines pass validation unchanged. Gate 4b only runs
when `story_architecture` is populated. The Engine never accesses
these fields (they're Studio-side design metadata).
