# Storyteller V3 — Prologue System Spec

> **SPECIALIST SPEC** — Complete specification for the psychometric
> prologue system (Phase 18). Part A covers design robustness. Part B
> covers step-by-step implementation.
>
> **Build phase:** Phase 18 (not yet started).
> **Core design authority:** Game Mechanics §5.
> **This document extends** GM §5 with robustness rules and provides
> the implementation roadmap.

**Version:** 1.0
**Date:** April 5, 2026
**Consolidation note:** This document merges the former
`PROLOGUE_INFERENCE_SPEC.md` (design robustness, v1.0, March 6, 2026)
and `PHASE_18_IMPLEMENTATION_PLAN.md` (implementation steps) into a
single reference for Phase 18 work.

---

# Part A: Design Robustness

Covers edge cases that the existing design (Game Mechanics §5,
Campaign Studio §2.5-2.6) does not fully address: contradiction
handling, tie resolution, confidence scoring, anti-gaming protections,
fallback behavior, and scene library diversity requirements.

**What this spec does NOT replace:** The core prologue design is in
Game Mechanics §5. The three-layer inference model (behavioral
archetype -> mechanical profile -> narrative identity), the four
behavioral axes, the adaptive depth mechanism, and the career-scoped
mapping tables are all specified there. This document extends that
design with robustness rules for edge cases.

---

## A.1. What Already Exists

A brief summary of the existing specification, for reference.

**Four behavioral axes:** Approach (Direct <-> Indirect), Social
(Trusting <-> Guarded), Risk (Bold <-> Cautious), Moral (Principled <->
Pragmatic). Each prologue choice is pre-tagged on these axes by the
campaign author.

**Adaptive depth:** 3 scenes minimum, 5 maximum. After each scene,
the system evaluates signal strength. If all four axes show a clear
majority direction (>=2/3 data points consistent), the prologue ends.
If any axis is ambiguous, a targeted scene fires. After 5 scenes, the
system selects best-fit and proceeds.

**Three inference layers:** Layer 1 (behavioral archetype) is
algorithmic -- pure Python counting axis tags. Layer 2 (mechanical
profile) is a hand-authored mapping table scoped by career type.
Layer 3 (narrative identity -- motivation subtype, throughline question,
voice notes) is a single cloud LLM call.

**Scene library:** Career- and allegiance-scoped. Scenes carry
`career_type` and `allegiance` tags. Recommended: 3 library scenes per
career-allegiance combo + 2 campaign-specific per variant.

---

## A.2. Per-Axis Confidence Scoring

The existing design uses a simple majority rule: >=2/3 data points
consistent on an axis = clear signal. This spec formalizes the
scoring into a per-axis confidence model.

### A.2.1 Signal Accumulation

Each prologue choice tags 1-4 axes. After N scenes, each axis has
accumulated 0 to N data points (an axis may not be tagged in every
scene).

For each axis, the system tracks:

```python
@dataclass
class AxisSignal:
    axis: str           # "approach", "social", "risk", "moral"
    positive_count: int  # e.g., Direct, Trusting, Bold, Principled
    negative_count: int  # e.g., Indirect, Guarded, Cautious, Pragmatic
    total: int           # positive + negative

    @property
    def confidence(self) -> float:
        """0.0 to 1.0. How clearly the axis points in one direction."""
        if self.total == 0:
            return 0.0
        return abs(self.positive_count - self.negative_count) / self.total

    @property
    def direction(self) -> str:
        """Which pole the axis leans toward."""
        if self.positive_count >= self.negative_count:
            return "positive"
        return "negative"

    @property
    def is_clear(self) -> bool:
        """Does this axis have sufficient signal to resolve?"""
        return self.total >= 2 and self.confidence >= 0.5
```

### A.2.2 Confidence Thresholds

| Condition | Confidence | Meaning |
|-----------|-----------|---------|
| Strong signal | >= 0.67 (2/3 majority) | Axis resolved. No further testing needed. |
| Moderate signal | 0.5 - 0.66 | Axis leans but is not definitive. Acceptable if all other axes are clear. |
| Weak signal | < 0.5 | Axis is ambiguous. Targeted scene needed if scenes remain. |
| No data | 0.0 (total = 0) | Axis untested. Must be targeted in next scene. |

### A.2.3 Prologue Termination Rules

The prologue ends when **one of** the following is true:

1. **All four axes have strong signal** (confidence >= 0.67). This can
   happen after 3 scenes if axis coverage is efficient.
2. **All four axes have at least moderate signal** (confidence >= 0.5)
   **and** at least 4 scenes have been played. This relaxes the
   threshold after the player has invested enough time.
3. **Five scenes have been played.** The system uses best available
   signal regardless of confidence.

---

## A.3. Contradiction Handling

### A.3.1 The Problem

A player may be Bold in crisis situations but Cautious in social
situations -- or Trusting with allies but Guarded with strangers. These
are not ambiguous signals; they are coherent personality patterns that
happen to express differently depending on context. The existing design
treats them as noise (50/50 split = ambiguous axis). This spec treats
them as signal.

### A.3.2 Contradiction Profiles

When an axis has moderate or weak confidence after 3+ data points
(enough data to rule out random noise), the system checks whether the
split is contextual rather than random. It does this by examining the
scene types that produced the conflicting signals.

Each prologue scene carries a `scene_pressure` tag authored alongside
the axis tags. Scene pressures include:

- `crisis` -- time pressure, danger, immediate stakes
- `social` -- interpersonal negotiation, trust decisions
- `moral` -- ethical dilemma, values under pressure
- `strategic` -- planning, resource allocation, long-term thinking

If the positive and negative data points on a split axis correlate
with different scene pressures, the split is a **contradiction
profile** rather than ambiguity.

```python
@dataclass
class ContradictionProfile:
    axis: str
    primary_context: str      # scene pressure where positive dominates
    primary_direction: str    # "positive" or "negative"
    secondary_context: str    # scene pressure where negative dominates
    secondary_direction: str
```

*Example:* A player who is Bold in `crisis` scenes but Cautious in
`strategic` scenes produces a contradiction profile: Risk axis,
primary Bold under crisis, secondary Cautious under strategic. This
is not an ambiguous person -- this is someone who acts on instinct
under pressure but plans carefully when given time.

### A.3.3 How Contradiction Profiles Are Used

**Layer 1 (behavioral archetype):** The system resolves the axis using
the **primary direction** (the direction with more data points, or the
`crisis` direction if tied -- crisis choices are more revealing of
instinct). The contradiction profile is preserved as metadata.

**Layer 2 (mechanical profile):** The mapping table uses the resolved
direction. No change from the standard path.

**Layer 3 (narrative identity):** The contradiction profile is passed
to the cloud model alongside the resolved archetype. The cloud model
uses it to generate richer voice notes and a more nuanced throughline
question. A character who is "Bold under pressure, Cautious in
planning" produces a different voice than one who is uniformly Bold.

**If no contextual correlation exists** (the split is genuinely
random across scene types), the axis is treated as a true 50/50 split
and resolved by the fallback rules in Section A.5.

---

## A.4. Anti-Gaming Protections

### A.4.1 The Threat Model

A player who understands the system could attempt to manipulate their
character build by selecting choices based on their mechanical tags
rather than their narrative content. The risk is low (the tags are
invisible, the mapping table is not public, and most players will
never encounter the system more than a few times) but the design
should not rely on security through obscurity alone.

### A.4.2 Design Protections (Already Present)

Several aspects of the existing design already resist gaming:

**Invisible tags.** The player never sees axis labels. They see
narrative choices. A player would need to reverse-engineer which
choices map to which axes, which requires multiple playthroughs with
careful tracking.

**Career-scoped mapping tables.** Even if a player knew the axes,
they would not know which cluster maps to which stat distribution
without access to the mapping table data file.

**Constrained selection.** The output is a profile selected from
pre-designed variants. There is no "optimal" build to game toward --
every profile is designed to be viable and interesting.

### A.4.3 Additional Protections (This Spec)

**Scene presentation randomization.** Within the prologue scene pool,
the order of scenes is randomized (subject to the constraint that axis
coverage is maintained across the first three scenes). A player who
replays the prologue sees different scenes in a different order.

**Choice order randomization.** Within each scene, the presentation
order of choices is randomized. A player who sees the same scene twice
cannot rely on "choice 1 is always the Bold option."

**Axis tag diversity per scene.** Campaign Studio validation (Section
A.7 below) requires that each scene's choices tag at least two different
axes and that no single choice tags more than two axes. This prevents
a scene from becoming a single-axis diagnostic that a savvy player
could read.

**No repeated axis patterns across scenes.** The scene selection
algorithm ensures that consecutive scenes do not test the same axis
pair. If Scene 1 tests Approach + Risk, Scene 2 must test a different
combination. This prevents a player from building a mental model of
"this scene is about risk."

---

## A.5. Fallback and Tie-Breaking Rules

### A.5.1 Axis-Level Tie-Breaking

When an axis has an exact 50/50 split with no contextual correlation
(no contradiction profile), the system needs a deterministic
tie-breaking rule.

**Rule:** Resolve toward the **variant's default direction.**

Each character variant in the campaign spine includes a
`default_behavioral_lean` -- the axis directions that represent the
"baseline" version of this variant before prologue refinement. A
smuggler variant might default to Indirect + Guarded + Bold +
Pragmatic. If the prologue produces a tie on the Social axis, the
system resolves toward Guarded (the variant default) rather than
making an arbitrary choice.

**Rationale:** The variant default represents the campaign author's
intent for who this character is when the player provides no strong
signal in a direction. Defaulting to it produces the most coherent
character. The player still influenced every other axis -- the tie on
one axis produces a character who is slightly closer to the authored
baseline on that dimension.

### A.5.2 Profile-Level Tie-Breaking

If the resolved behavioral cluster (after per-axis resolution) falls
exactly between two mechanical profiles in the mapping table, the
system selects the profile whose characteristics have higher spread
(more variation between highest and lowest characteristic). Higher
spread produces a more distinctive character -- a character who is
notably good at some things and notably weak at others is more
interesting to play than one who is average across the board.

### A.5.3 Full Fallback (Low Confidence After 5 Scenes)

If after 5 scenes, two or more axes remain below moderate confidence
(< 0.5) and no contradiction profiles explain the splits:

1. Resolve each axis toward the variant default direction.
2. Select the mechanical profile matching the fully-defaulted cluster.
3. Pass the full choice history to Layer 3 regardless -- the cloud
   model may extract meaningful narrative identity even when the
   behavioral axes are inconclusive.
4. Log the low-confidence outcome for monitoring.

The character is playable and coherent. The player simply produced a
character closer to the variant's authored baseline than a player with
stronger preferences would have.

---

## A.6. Layer 3 Robustness (Cloud Inference)

The Layer 3 cloud call infers motivation subtype, throughline question,
and voice notes. Game Mechanics §5 specifies validation: motivation
subtype must be from the variant's `possible_types` list, throughline
question must be a question, voice notes must not exceed 100 words.

This spec adds:

### A.6.1 Retry on Validation Failure

If the cloud model returns an invalid result (motivation subtype not
in the allowed list, throughline question is not a question, or voice
notes exceed 100 words), retry once with a correction message. If the
second attempt also fails, use the variant's authored defaults:

- Motivation subtype: first entry in `possible_types`
- Throughline question: variant's `default_throughline`
- Voice notes: variant's `default_voice_notes`

Every variant must include these defaults in the campaign spine.

### A.6.2 Contradiction Profile Injection

When contradiction profiles exist (Section A.3), they are passed to the
Layer 3 prompt as additional context:

```
BEHAVIORAL NOTE: This character shows a contradiction on the {axis}
axis -- {primary_direction} under {primary_context} pressure but
{secondary_direction} under {secondary_context} pressure. Reflect
this tension in the voice notes and throughline question. The
character is not confused; they have different instincts in different
situations.
```

This produces voice notes like: "Trusts her crew instinctively. Does
not extend that trust beyond the ship -- and watches strangers the way
a dockworker watches weather" instead of a flat "Trusting personality."

### A.6.3 Degenerate Input Protection

If the player made choices that tagged only one or two axes across all
scenes (possible if scenes are poorly authored), the Layer 3 prompt
receives a note: "Limited behavioral signal. Lean on the variant
definition and authored defaults. Err toward the variant's baseline
personality rather than inventing personality traits from thin data."

---

## A.7. Scene Library Diversity Requirements

Campaign Studio validation must enforce the following to prevent the
prologue from becoming transparent, repetitive, or mechanically thin.

### A.7.1 Minimum Library Size

Per career-allegiance combination: **minimum 5 library scenes.** This
ensures at least 5 distinct scenes are available for a 5-scene
prologue. With randomization, a player replaying the same variant may
see a mostly different prologue (3 of 5 scenes could be different).

The recommended size remains 3 library + 2 campaign-specific per the
existing Campaign Studio guidance (CS §2.6), but the library must
contain at least 5 to support randomization.

### A.7.2 Axis Coverage

The scene library for a career-allegiance combination must collectively
tag all four axes. Every axis must be tagged in at least 3 different
scenes. This ensures no axis can go untested regardless of scene
selection randomization.

### A.7.3 Scene Pressure Diversity

The library must contain scenes with at least 3 different
`scene_pressure` tags. A library consisting entirely of `crisis`
scenes would prevent contradiction profiles from forming (all signals
would come from the same context).

### A.7.4 Choice Distinctiveness

Within each scene, no two choices may have identical axis tag
combinations. If Choice A is tagged Direct + Bold and Choice B is
also tagged Direct + Bold, the scene cannot distinguish between two
types of player who both lean that way. At least one axis tag must
differ between any pair of choices in the same scene.

### A.7.5 Validation Implementation

These checks run as part of Campaign Studio validation (CS Design §5)
during spine authoring. They are automated, deterministic, and
non-negotiable -- matching the pattern of schema contract validation
and NPC coherence validation.

```python
def validate_prologue_library(
    library: list[PrologueScene],
    career_type: str,
    allegiance: str,
) -> list[ValidationFlag]:
    flags = []

    # A.7.1: Minimum size
    if len(library) < 5:
        flags.append(ValidationFlag(
            severity="error",
            message=f"Prologue library for {career_type}/{allegiance} "
                    f"has {len(library)} scenes (minimum 5)."
        ))

    # A.7.2: Axis coverage
    axis_scene_counts = {"approach": 0, "social": 0, "risk": 0, "moral": 0}
    for scene in library:
        axes_in_scene = set()
        for choice in scene.choices:
            for axis in ["approach", "social", "risk", "moral"]:
                if getattr(choice.axis_tags, axis) is not None:
                    axes_in_scene.add(axis)
        for axis in axes_in_scene:
            axis_scene_counts[axis] += 1

    for axis, count in axis_scene_counts.items():
        if count < 3:
            flags.append(ValidationFlag(
                severity="error",
                message=f"Axis '{axis}' tagged in only {count} scenes "
                        f"(minimum 3) for {career_type}/{allegiance}."
            ))

    # A.7.3: Scene pressure diversity
    pressures = {s.scene_pressure for s in library if hasattr(s, 'scene_pressure')}
    if len(pressures) < 3:
        flags.append(ValidationFlag(
            severity="warning",
            message=f"Only {len(pressures)} scene pressure types in "
                    f"{career_type}/{allegiance} library (minimum 3 "
                    f"recommended for contradiction profile coverage)."
        ))

    # A.7.4: Choice distinctiveness (per scene)
    for scene in library:
        tag_combos = []
        for choice in scene.choices:
            combo = (
                getattr(choice.axis_tags, 'approach', None),
                getattr(choice.axis_tags, 'social', None),
                getattr(choice.axis_tags, 'risk', None),
                getattr(choice.axis_tags, 'moral', None),
            )
            tag_combos.append(combo)
        if len(tag_combos) != len(set(tag_combos)):
            flags.append(ValidationFlag(
                severity="error",
                message=f"Scene {scene.scene_number} has duplicate "
                        f"axis tag combinations across choices."
            ))

    return flags
```

---

## A.8. Schema Additions

### A.8.1 Campaign Spine

The `PrologueScene` model (CS Implementation §4.1) gains:

```python
class PrologueScene(BaseModel):
    scene_number: int = Field(ge=1)
    situation: str = Field(min_length=20)
    choices: list[PrologueChoice] = Field(min_length=2, max_length=4)
    scene_pressure: str = Field(
        pattern="^(crisis|social|moral|strategic)$"
    )
    library_reusable: bool = True
```

### A.8.2 Character Variant

Each variant gains default behavioral and narrative fallbacks:

```python
class CharacterVariant(BaseModel):
    # ... existing fields ...
    default_behavioral_lean: dict[str, str] = Field(
        description="Default axis directions for tie-breaking. "
                    "Keys: approach, social, risk, moral. "
                    "Values: positive/negative pole names."
    )
    default_throughline: str = Field(
        description="Fallback throughline question if Layer 3 fails."
    )
    default_voice_notes: str = Field(
        max_length=300,
        description="Fallback voice notes if Layer 3 fails."
    )
```

---

## A.9. Build Phase and Dependencies

**Target phase:** Phase 18 (Psychometric Prologue).

**Dependencies:**
- Phase 10 (behavioral inference -- prologue uses the same signal
  processing pattern for axis tags)
- Campaign Studio Phase CS-1 (spine schema finalized, including
  prologue scene data format)
- Career-type mapping tables authored (Backlog item 3.31)
- Prologue scene library authored (Backlog item 3.30)

**Backlog integration:** Update item 2.1 (Psychometric prologue system)
to reference this spec for robustness requirements. The core design
remains in GM §5; this spec extends it.

---

# Part B: Implementation Plan

Step-by-step implementation guide for Phase 18. Before the main game
loop starts, players currently pick a pre-built character from a JSON
file. Phase 18 replaces this with a **psychometric prologue**: a 3-5
scene interactive sequence that infers the player's behavioral profile
and produces a mechanically configured character. The prologue is
invisible inference -- the player experiences story scenes with
narrative choices, not a personality quiz.

Three inference layers:
- **Layer 1** (pure Python): Track 4 behavioral axes from tagged
  choices, compute confidence, detect contradictions
- **Layer 2** (hand-authored JSON): Map behavioral cluster to
  stat/skill profile via career-type mapping table
- **Layer 3** (single cloud LLM call): Infer motivation subtype,
  throughline question, voice notes

The resulting Character is identical (same Pydantic model, same session
creation path) to a hand-built character.

---

## B.1. Schema Extensions

**Files:** `studio/schema.py`

Add to `PrologueScene`:
- `scene_pressure: str` -- constrained to "crisis" | "social" |
  "moral" | "strategic" (optional with default, so existing data
  doesn't break)
- `library_reusable: bool = True`

Add to `CharacterVariant`:
- `default_behavioral_lean: dict[str, str] = {}` -- axis tie-breaking
  defaults (keys: approach/social/risk/moral)
- `default_throughline: str = ""` -- fallback throughline question
- `default_voice_notes: str = ""` -- fallback voice notes (max 300
  chars)

All new fields have defaults so existing campaign spines continue to
load.

**Verify:** Construct models with new fields in a test, confirm
existing spine JSON still validates.

---

## B.2. Core Inference Engine -- Layer 1

**Files:** `engine/prologue.py` (NEW)

Pure Python, zero LLM dependencies (Rule 3). Contains:

**Dataclasses:**
- `AxisSignal` -- `axis`, `positive_count`, `negative_count`, `total`;
  properties: `confidence` (0.0-1.0), `direction`, `is_clear`
- `ContradictionProfile` -- `axis`, `primary_context`,
  `primary_direction`, `secondary_context`, `secondary_direction`
- `PrologueState` -- four `AxisSignal` objects, scene choices made,
  scenes played, contradiction profiles
- `BehavioralArchetype` -- four resolved axis directions

**Functions:**
- `init_prologue_state()` -> fresh PrologueState
- `record_choice(state, scene, choice_index)` -> updated PrologueState
  (accumulates axis tags)
- `evaluate_termination(state)` -> bool (3 rules: all strong; all
  moderate + 4 scenes; 5 scenes)
- `select_next_scene(state, available_scenes, played_ids)` ->
  PrologueScene (targets weakest axis, avoids repeated patterns)
- `randomize_choices(choices)` -> (shuffled_choices, index_mapping)
  (anti-gaming)
- `detect_contradictions(state, scene_history)` ->
  list[ContradictionProfile]
- `resolve_axes(state, contradictions, default_lean)` ->
  BehavioralArchetype

Follows the `engine/advancement.py` pattern: dataclasses for
intermediate results, pure functions that transform data.

**Verify:** Unit tests with mock scenes and known axis tags. Test all
three termination conditions, contradiction detection, tie-breaking
to variant defaults.

---

## B.3. Core Inference Engine -- Layer 2

**Files:** `engine/prologue.py` (extend),
`data/prologue/career_type_mapping_tables/guardian.json` (NEW)

**Add to engine/prologue.py:**
- `load_mapping_table(career: str)` -> loads from
  `data/prologue/career_type_mapping_tables/{career}.json`
- `select_profile(archetype, mapping_table)` -> matches cluster to
  closest profile entry; tie-break by highest characteristic spread
- `build_character_from_prologue(variant_data, profile, layer3_result)`
  -> `Character` Pydantic object with all fields populated

**guardian.json structure:**
```json
{
  "career": "guardian",
  "profiles": [
    {
      "cluster": {"approach": "direct", "social": "trusting",
                  "risk": "bold", "moral": "principled"},
      "profile_name": "Stalwart Defender",
      "characteristics": {"brawn": 3, "agility": 2, "intellect": 2,
                          "cunning": 2, "willpower": 3, "presence": 3},
      "skills": {"discipline": 2, "resilience": 2, "lightsaber": 2}
    }
  ]
}
```

Profiles vary around the Talia Ren baseline (Willpower 4, Presence 3)
by 1-2 points depending on behavioral cluster. 8-12 profiles total.

**Verify:** Load table, pass known archetype, get valid profile.
`build_character_from_prologue()` returns a Character that round-trips
through `Character.model_validate()`.

---

## B.4. Prologue Scene Data

**Files:** `data/campaigns/echoes_of_the_force.json` (modify)

Add to each character variant:
- `default_behavioral_lean` (e.g., Talia: `{"approach": "indirect",
  "social": "trusting", "risk": "cautious", "moral": "principled"}`)
- `default_throughline` (reuse the campaign's throughline_question)
- `default_voice_notes` (reuse the existing voice_baseline)

Add `prologue_scenes` array to the campaign spine with a `PrologueSet`
for Talia Ren containing 5 scenes:

| Scene | Pressure | Axes Tested | Theme |
|-------|----------|-------------|-------|
| 1 | crisis | approach + risk | Imperial patrol forces a split-second decision |
| 2 | social | social + moral | Settler asks for help with a dispute |
| 3 | moral | moral + risk | Force vision reveals someone in danger |
| 4 | strategic | approach + social | Planning an escape route |
| 5 | crisis | all four | Inquisitor's agent arrives |

Each scene has 3 choices with distinct axis tag combinations. All 4
axes tagged in >=3 scenes. >=3 scene_pressure types represented.

**Verify:** Load spine, validate against updated Pydantic models.
Check axis coverage and pressure diversity.

---

## B.5. Layer 3 -- Cloud LLM Identity Inference

**Files:** `gm/prompts/prologue_identity.txt` (NEW),
`gm/cloud_gm.py` (modify)

**Prompt template** receives: variant definition, resolved archetype,
contradiction profiles, full choice history, motivation possible_types
list. Instructs LLM to return structured JSON with
`motivation_subtype`, `throughline_question`, `voice_notes`.

**Add to cloud_gm.py:**
- `generate_prologue_identity(variant, archetype, contradictions,
  choice_history)` -> dict
- `_parse_prologue_identity_response(raw, variant)` -> validates:
  subtype in possible_types, throughline ends with "?", voice_notes
  <=100 words

Follows `generate_milestone_reflection()` pattern: load template ->
format -> `_make_client()` -> `chat.completions.create()` -> parse ->
retry once -> fallback to variant defaults.

**Verify:** Unit test validation logic with mock responses. Integration
test with real LLM call for Talia Ren.

---

## B.6. Prologue API Endpoints

**Files:** `api/game_routes.py` (modify)

Three new endpoints, prologue state held in-memory (dict keyed by
UUID):

1. **`POST /prologue/start`** -- `{campaign_name, variant_id}` -> loads
   spine, finds variant + prologue scenes, selects first scene, returns
   scene situation + shuffled choices (no axis tags exposed)
2. **`POST /prologue/{id}/choice`** -- `{choice_index}` -> records
   choice, updates state, evaluates termination. Returns next scene OR
   `{complete: true, character_summary}` with Layer 1->2->3 results
3. **`POST /prologue/{id}/confirm`** -- creates session using the
   prologue-built Character via the existing session creation logic
   (NPC init, destiny roll, opening narration). Returns same response
   structure as `POST /session`

Extend `GET /campaigns` to include `has_prologue: true/false` per
character.

`POST /session` remains unchanged for pre-built characters (backward
compatible).

**Verify:** Call all three endpoints in sequence. Confirm the returned
session plays identically to a pre-built character session.

---

## B.7. Frontend -- Funnel UI

**Files:** `web/index.html` (modify)

Three new UI states within the single-file frontend:

**7a -- Campaign picker enhancement:** If selected character has
prologue, button says "Begin Prologue" and enters prologue flow. If no
prologue, "Begin Campaign" enters existing direct flow.

**7b -- Prologue scene screen:** Situation text in `.passage` style,
choice buttons in `.choice-btn` style. Progress indicator ("Scene 1 of
3-5"). No dice panel or status bar. On choice click -> POST
/prologue/{id}/choice -> render next scene or transition to reveal.

**7c -- Character reveal screen:** Character name, species, career,
throughline question, voice notes. "Begin Campaign" button calls POST
/prologue/{id}/confirm -> transitions to game screen with opening
narration.

**7d -- Loading states:** "Your character takes shape..." during
Layer 3 inference, "The story begins..." during session creation.

**Verify:** Manual walkthrough: Echoes of the Force -> Talia Ren ->
3-5 prologue scenes -> reveal -> campaign starts. Also verify: Nar
Shaddaa Job -> Keth Varso -> direct start (no prologue, no
regression).

---

## B.8. End-to-End Integration

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
- Edge case: 5 scenes with ambiguous signals -> falls back to variant
  defaults
- Edge case: Abandon prologue mid-flow -> no orphaned state

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

## Critical File Paths

| File | Role |
|------|------|
| `engine/prologue.py` | NEW -- Core inference (Layer 1 + 2), character construction |
| `studio/schema.py` | MODIFY -- scene_pressure, default_behavioral_lean/throughline/voice_notes |
| `gm/cloud_gm.py` | MODIFY -- generate_prologue_identity() (Layer 3) |
| `gm/prompts/prologue_identity.txt` | NEW -- Layer 3 prompt template |
| `data/prologue/career_type_mapping_tables/guardian.json` | NEW -- Guardian behavioral cluster -> stats mapping |
| `data/campaigns/echoes_of_the_force.json` | MODIFY -- prologue scenes + variant defaults |
| `api/game_routes.py` | MODIFY -- 3 prologue endpoints |
| `web/index.html` | MODIFY -- funnel UI, scene screen, reveal screen |

---

*Storyteller V3 -- Prologue System Spec v1.0*
*The funnel narrows the space. The prologue reads the player.
This spec handles the edge cases and the implementation path.*
