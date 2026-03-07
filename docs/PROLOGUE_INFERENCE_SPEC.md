# Storyteller V3 — Prologue Inference Spec

**Version:** 1.0  
**Date:** March 6, 2026  
**Purpose:** Robustness specification for the psychometric prologue
system. Covers edge cases that the existing design (Game Mechanics §5,
Campaign Studio §2.5–2.6) does not fully address: contradiction
handling, tie resolution, confidence scoring, anti-gaming protections,
fallback behavior, and scene library diversity requirements.

**What this spec does NOT replace:** The core prologue design is in
Game Mechanics §5. The three-layer inference model (behavioral
archetype → mechanical profile → narrative identity), the four
behavioral axes, the adaptive depth mechanism, and the career-scoped
mapping tables are all specified there. This document extends that
design with robustness rules for edge cases.

**Build phase:** Phase 18 (Psychometric Prologue). This spec is not
needed until then, but is authored now to ensure the design is complete
before implementation begins.

---

## 1. What Already Exists

A brief summary of the existing specification, for reference.

**Four behavioral axes:** Approach (Direct ↔ Indirect), Social
(Trusting ↔ Guarded), Risk (Bold ↔ Cautious), Moral (Principled ↔
Pragmatic). Each prologue choice is pre-tagged on these axes by the
campaign author.

**Adaptive depth:** 3 scenes minimum, 5 maximum. After each scene,
the system evaluates signal strength. If all four axes show a clear
majority direction (≥2/3 data points consistent), the prologue ends.
If any axis is ambiguous, a targeted scene fires. After 5 scenes, the
system selects best-fit and proceeds.

**Three inference layers:** Layer 1 (behavioral archetype) is
algorithmic — pure Python counting axis tags. Layer 2 (mechanical
profile) is a hand-authored mapping table scoped by career type.
Layer 3 (narrative identity — motivation subtype, throughline question,
voice notes) is a single cloud LLM call.

**Scene library:** Career- and allegiance-scoped. Scenes carry
`career_type` and `allegiance` tags. Recommended: 3 library scenes per
career-allegiance combo + 2 campaign-specific per variant.

---

## 2. Per-Axis Confidence Scoring

The existing design uses a simple majority rule: ≥2/3 data points
consistent on an axis = clear signal. This spec formalizes the
scoring into a per-axis confidence model.

### 2.1 Signal Accumulation

Each prologue choice tags 1–4 axes. After N scenes, each axis has
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

### 2.2 Confidence Thresholds

| Condition | Confidence | Meaning |
|-----------|-----------|---------|
| Strong signal | ≥ 0.67 (2/3 majority) | Axis resolved. No further testing needed. |
| Moderate signal | 0.5 – 0.66 | Axis leans but is not definitive. Acceptable if all other axes are clear. |
| Weak signal | < 0.5 | Axis is ambiguous. Targeted scene needed if scenes remain. |
| No data | 0.0 (total = 0) | Axis untested. Must be targeted in next scene. |

### 2.3 Prologue Termination Rules

The prologue ends when **one of** the following is true:

1. **All four axes have strong signal** (confidence ≥ 0.67). This can
   happen after 3 scenes if axis coverage is efficient.
2. **All four axes have at least moderate signal** (confidence ≥ 0.5)
   **and** at least 4 scenes have been played. This relaxes the
   threshold after the player has invested enough time.
3. **Five scenes have been played.** The system uses best available
   signal regardless of confidence.

---

## 3. Contradiction Handling

### 3.1 The Problem

A player may be Bold in crisis situations but Cautious in social
situations — or Trusting with allies but Guarded with strangers. These
are not ambiguous signals; they are coherent personality patterns that
happen to express differently depending on context. The existing design
treats them as noise (50/50 split = ambiguous axis). This spec treats
them as signal.

### 3.2 Contradiction Profiles

When an axis has moderate or weak confidence after 3+ data points
(enough data to rule out random noise), the system checks whether the
split is contextual rather than random. It does this by examining the
scene types that produced the conflicting signals.

Each prologue scene carries a `scene_pressure` tag authored alongside
the axis tags. Scene pressures include:

- `crisis` — time pressure, danger, immediate stakes
- `social` — interpersonal negotiation, trust decisions
- `moral` — ethical dilemma, values under pressure
- `strategic` — planning, resource allocation, long-term thinking

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
is not an ambiguous person — this is someone who acts on instinct
under pressure but plans carefully when given time.

### 3.3 How Contradiction Profiles Are Used

**Layer 1 (behavioral archetype):** The system resolves the axis using
the **primary direction** (the direction with more data points, or the
`crisis` direction if tied — crisis choices are more revealing of
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
and resolved by the fallback rules in Section 5.

---

## 4. Anti-Gaming Protections

### 4.1 The Threat Model

A player who understands the system could attempt to manipulate their
character build by selecting choices based on their mechanical tags
rather than their narrative content. The risk is low (the tags are
invisible, the mapping table is not public, and most players will
never encounter the system more than a few times) but the design
should not rely on security through obscurity alone.

### 4.2 Design Protections (Already Present)

Several aspects of the existing design already resist gaming:

**Invisible tags.** The player never sees axis labels. They see
narrative choices. A player would need to reverse-engineer which
choices map to which axes, which requires multiple playthroughs with
careful tracking.

**Career-scoped mapping tables.** Even if a player knew the axes,
they would not know which cluster maps to which stat distribution
without access to the mapping table data file.

**Constrained selection.** The output is a profile selected from
pre-designed variants. There is no "optimal" build to game toward —
every profile is designed to be viable and interesting.

### 4.3 Additional Protections (This Spec)

**Scene presentation randomization.** Within the prologue scene pool,
the order of scenes is randomized (subject to the constraint that axis
coverage is maintained across the first three scenes). A player who
replays the prologue sees different scenes in a different order.

**Choice order randomization.** Within each scene, the presentation
order of choices is randomized. A player who sees the same scene twice
cannot rely on "choice 1 is always the Bold option."

**Axis tag diversity per scene.** Campaign Studio validation (Section
7 below) requires that each scene's choices tag at least two different
axes and that no single choice tags more than two axes. This prevents
a scene from becoming a single-axis diagnostic that a savvy player
could read.

**No repeated axis patterns across scenes.** The scene selection
algorithm ensures that consecutive scenes do not test the same axis
pair. If Scene 1 tests Approach + Risk, Scene 2 must test a different
combination. This prevents a player from building a mental model of
"this scene is about risk."

---

## 5. Fallback and Tie-Breaking Rules

### 5.1 Axis-Level Tie-Breaking

When an axis has an exact 50/50 split with no contextual correlation
(no contradiction profile), the system needs a deterministic
tie-breaking rule.

**Rule:** Resolve toward the **variant's default direction.**

Each character variant in the campaign spine includes a
`default_behavioral_lean` — the axis directions that represent the
"baseline" version of this variant before prologue refinement. A
smuggler variant might default to Indirect + Guarded + Bold +
Pragmatic. If the prologue produces a tie on the Social axis, the
system resolves toward Guarded (the variant default) rather than
making an arbitrary choice.

**Rationale:** The variant default represents the campaign author's
intent for who this character is when the player provides no strong
signal in a direction. Defaulting to it produces the most coherent
character. The player still influenced every other axis — the tie on
one axis produces a character who is slightly closer to the authored
baseline on that dimension.

### 5.2 Profile-Level Tie-Breaking

If the resolved behavioral cluster (after per-axis resolution) falls
exactly between two mechanical profiles in the mapping table, the
system selects the profile whose characteristics have higher spread
(more variation between highest and lowest characteristic). Higher
spread produces a more distinctive character — a character who is
notably good at some things and notably weak at others is more
interesting to play than one who is average across the board.

### 5.3 Full Fallback (Low Confidence After 5 Scenes)

If after 5 scenes, two or more axes remain below moderate confidence
(< 0.5) and no contradiction profiles explain the splits:

1. Resolve each axis toward the variant default direction.
2. Select the mechanical profile matching the fully-defaulted cluster.
3. Pass the full choice history to Layer 3 regardless — the cloud
   model may extract meaningful narrative identity even when the
   behavioral axes are inconclusive.
4. Log the low-confidence outcome for monitoring.

The character is playable and coherent. The player simply produced a
character closer to the variant's authored baseline than a player with
stronger preferences would have.

---

## 6. Layer 3 Robustness (Cloud Inference)

The Layer 3 cloud call infers motivation subtype, throughline question,
and voice notes. Game Mechanics §5 specifies validation: motivation
subtype must be from the variant's `possible_types` list, throughline
question must be a question, voice notes must not exceed 100 words.

This spec adds:

### 6.1 Retry on Validation Failure

If the cloud model returns an invalid result (motivation subtype not
in the allowed list, throughline question is not a question, or voice
notes exceed 100 words), retry once with a correction message. If the
second attempt also fails, use the variant's authored defaults:

- Motivation subtype: first entry in `possible_types`
- Throughline question: variant's `default_throughline`
- Voice notes: variant's `default_voice_notes`

Every variant must include these defaults in the campaign spine.

### 6.2 Contradiction Profile Injection

When contradiction profiles exist (Section 3), they are passed to the
Layer 3 prompt as additional context:

```
BEHAVIORAL NOTE: This character shows a contradiction on the {axis}
axis — {primary_direction} under {primary_context} pressure but
{secondary_direction} under {secondary_context} pressure. Reflect
this tension in the voice notes and throughline question. The
character is not confused; they have different instincts in different
situations.
```

This produces voice notes like: "Trusts her crew instinctively. Does
not extend that trust beyond the ship — and watches strangers the way
a dockworker watches weather" instead of a flat "Trusting personality."

### 6.3 Degenerate Input Protection

If the player made choices that tagged only one or two axes across all
scenes (possible if scenes are poorly authored), the Layer 3 prompt
receives a note: "Limited behavioral signal. Lean on the variant
definition and authored defaults. Err toward the variant's baseline
personality rather than inventing personality traits from thin data."

---

## 7. Scene Library Diversity Requirements

Campaign Studio validation must enforce the following to prevent the
prologue from becoming transparent, repetitive, or mechanically thin.

### 7.1 Minimum Library Size

Per career-allegiance combination: **minimum 5 library scenes.** This
ensures at least 5 distinct scenes are available for a 5-scene
prologue. With randomization, a player replaying the same variant may
see a mostly different prologue (3 of 5 scenes could be different).

The recommended size remains 3 library + 2 campaign-specific per the
existing Campaign Studio guidance (CS §2.6), but the library must
contain at least 5 to support randomization.

### 7.2 Axis Coverage

The scene library for a career-allegiance combination must collectively
tag all four axes. Every axis must be tagged in at least 3 different
scenes. This ensures no axis can go untested regardless of scene
selection randomization.

### 7.3 Scene Pressure Diversity

The library must contain scenes with at least 3 different
`scene_pressure` tags. A library consisting entirely of `crisis`
scenes would prevent contradiction profiles from forming (all signals
would come from the same context).

### 7.4 Choice Distinctiveness

Within each scene, no two choices may have identical axis tag
combinations. If Choice A is tagged Direct + Bold and Choice B is
also tagged Direct + Bold, the scene cannot distinguish between two
types of player who both lean that way. At least one axis tag must
differ between any pair of choices in the same scene.

### 7.5 Validation Implementation

These checks run as part of Campaign Studio validation (CS Design §5)
during spine authoring. They are automated, deterministic, and
non-negotiable — matching the pattern of schema contract validation
and NPC coherence validation.

```python
def validate_prologue_library(
    library: list[PrologueScene],
    career_type: str,
    allegiance: str,
) -> list[ValidationFlag]:
    flags = []

    # 7.1: Minimum size
    if len(library) < 5:
        flags.append(ValidationFlag(
            severity="error",
            message=f"Prologue library for {career_type}/{allegiance} "
                    f"has {len(library)} scenes (minimum 5)."
        ))

    # 7.2: Axis coverage
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

    # 7.3: Scene pressure diversity
    pressures = {s.scene_pressure for s in library if hasattr(s, 'scene_pressure')}
    if len(pressures) < 3:
        flags.append(ValidationFlag(
            severity="warning",
            message=f"Only {len(pressures)} scene pressure types in "
                    f"{career_type}/{allegiance} library (minimum 3 "
                    f"recommended for contradiction profile coverage)."
        ))

    # 7.4: Choice distinctiveness (per scene)
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

## 8. Schema Additions

### 8.1 Campaign Spine

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

### 8.2 Character Variant

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

## 9. Build Phase and Dependencies

**Target phase:** Phase 18 (Psychometric Prologue).

**Dependencies:**
- Phase 10 (behavioral inference — prologue uses the same signal
  processing pattern for axis tags)
- Campaign Studio Phase CS-1 (spine schema finalized, including
  prologue scene data format)
- Career-type mapping tables authored (Backlog item 3.31)
- Prologue scene library authored (Backlog item 3.30)

**Backlog integration:** Update item 2.1 (Psychometric prologue system)
to reference this spec for robustness requirements. The core design
remains in GM §5; this spec extends it.

---

*Storyteller V3 — Prologue Inference Spec v1.0*  
*The funnel narrows the space. The prologue reads the player.
This spec handles the edge cases.*
