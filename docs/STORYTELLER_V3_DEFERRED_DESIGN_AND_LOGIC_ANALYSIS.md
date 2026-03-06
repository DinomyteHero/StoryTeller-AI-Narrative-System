# Storyteller V3 — Deferred Item Design + System Logic Analysis

**Status:** Design content from Sections 1 and 2 has been applied to
Game Mechanics v1.8 (§1.1 and §24.4). Issues found in Section 4 have
been applied to Implementation v2.2 and Build Roadmap. This document
is retained as a reference for the logic analysis in Section 4.

**Purpose:** Complete the design work for two remaining gaps in the
Game Mechanics document, then perform a comprehensive logic walkthrough
of the entire system to verify that all components connect correctly.

**Section 1:** Reputation Echo Delivery Mechanism (completing Deferral 1)
**Section 2:** Conditional Choice Availability (designing Deferral 4)
**Section 3:** Deferral Completion Confirmation
**Section 4:** Deep Logic Analysis — Full System Walkthrough

---

# Section 1: Reputation Echo Delivery Mechanism

**Adds to:** Game Mechanics §1 (Core Engagement Loop), Implementation
Notes subsection.

**What exists:** The reconciliation system (GM §26) captures
`reputation_event` and `notable_action` per turn. The `reputation_log`
table exists in the DB schema (Impl §8.1). GM §21.4 describes cross-
campaign reputation relevance scoring. GM §1 mentions "3-5 most recent
reputation entries" delivered to the GM prompt.

**What's missing:** The complete delivery pipeline — how entries flow
from the reconciliation step into the reputation log, how they are
selected for prompt injection, the surfacing frequency logic, and the
narration prompt instruction block.

---

## 1.1 Reputation Log Population

The reconciliation step (GM §26) produces two fields relevant to
reputation:

`reputation_event: string | null` — a one-sentence summary of a
notable action that could reasonably be known to people beyond the
immediate scene. This field is non-null when the player did something
publicly visible, socially significant, or notable enough that word
would travel. Most turns produce null.

`notable_action: string | null` — a one-sentence summary of the most
significant thing the player did this turn, regardless of whether it
would travel beyond the scene. Used for character drift notes and act
summaries. Not the same as `reputation_event` — an action can be
notable (a private moral choice) without being a reputation event (the
choice was witnessed by no one).

**The reputation filter:** Only `reputation_event` writes to the
`reputation_log` table. The reconciliation prompt includes guidance for
when to generate a reputation event:

```
REPUTATION EVENT:
A reputation event is something the player did this turn that people
beyond the immediate scene could plausibly learn about. NOT every turn
produces one. A reputation event requires:
- At least one witness (NPC present, public location, or consequences
  visible to others)
- An action significant enough that someone would mention it to someone
  else (helped, betrayed, fought, impressed, embarrassed, offended)
If neither condition is met, reputation_event is null.

Examples of reputation events:
- "Helped Reeska's crew through the customs sweep without asking for
  payment" (witnessed, noteworthy)
- "Shot a Besadii enforcer in the Promenade cantina" (public, violent)
- "Talked Doss's way out of ISB custody at the checkpoint" (witnesses,
  impressive)

Examples of NOT reputation events:
- "Examined the cargo crate alone in the hold" (no witness)
- "Made a private promise to Doss" (private, no travel path)
- "Chose to take the maintenance corridor" (routine, unremarkable)
```

When `reputation_event` is non-null, the engine writes it to the
`reputation_log` table with the session_id, turn_number, the event
text, and a `faction_tags` field (list of faction/location identifiers
that determine where the reputation travels — e.g., `["smuggler_network",
"nar_shaddaa_promenade"]`).

**DB schema addition to `reputation_log`:**

```sql
CREATE TABLE IF NOT EXISTS reputation_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    turn_number INTEGER NOT NULL,
    summary     TEXT NOT NULL,
    faction_tags TEXT,          -- JSON array of faction/location tags
    surfaced_count INTEGER DEFAULT 0,  -- how many times this has been echoed
    created_at  TEXT NOT NULL
);
```

`surfaced_count` tracks how many times this entry has been injected
into the narration prompt, preventing the same event from being echoed
repeatedly.

## 1.2 Reputation Echo Selection

Each turn, before the context package is assembled, the engine selects
0-3 reputation entries for potential injection into the narration
prompt.

**Selection logic:**

1. Query the reputation log for this session, ordered by recency.
2. Score each entry by relevance to the current scene:
   - **Faction match** (+3): entry's `faction_tags` overlap with the
     current scene's NPC factions or location.
   - **Recency** (+2 if < 5 turns ago, +1 if < 15 turns ago, +0
     otherwise).
   - **Novelty** (+2 if `surfaced_count` == 0, +1 if == 1, +0 if > 1).
   - **NPC connection** (+2): an NPC in the current scene has a
     plausible connection to the faction/location where the event
     occurred.
3. Select the top 3 entries with score > 3 (ensures minimum relevance).
4. If no entries meet the threshold, inject nothing.

**Surfacing frequency control:**

Reputation echoes should feel occasional, not systematic. The engine
applies a **cooldown**: after a reputation echo appears in the narration,
no reputation echo context is injected for the next 3 turns. This
prevents the player from feeling like every NPC is talking about them.

The cooldown is tracked via `last_reputation_echo_turn` in the session's
arc state.

## 1.3 Prompt Injection

Selected reputation entries are injected into the narration prompt as
a new block within the STORY CONTEXT section:

```
REPUTATION ECHOES (use sparingly — not every turn):
The character's actions have traveled beyond the scenes where they
occurred. The following are things that people in this world may have
heard about:
{reputation_entries}

Do NOT reference all of these. Pick AT MOST one, and only if it fits
naturally into the scene — through NPC dialogue, overheard conversation,
a reaction from someone who recognizes the character, or environmental
detail (a wanted poster, a grateful look from a stranger). Most turns
should NOT include a reputation echo. When you do include one, it should
feel like a surprise — the world remembering something the player did.
```

The `{reputation_entries}` block contains the selected entries as a
simple list:

```
- "Helped Reeska's crew through the customs sweep" (Promenade docks,
  recent)
- "Shot a Besadii enforcer at Vek's cantina" (Promenade, 8 turns ago)
```

When the block is injected and the GM does use an echo, the engine
increments `surfaced_count` for that entry and updates the cooldown
counter. The increment happens via a lightweight post-narration check:
does the narration text contain keywords from any of the injected
reputation entries? If yes, increment. This is a string matching
heuristic, not an LLM call.

## 1.4 Cross-Campaign Reputation

As designed in GM §21.4, reputation entries persist through campaign
imports. The import package includes the full `reputation_log`. In the
new campaign, older entries have lower recency scores but can still
surface when faction/NPC connections match. A reputation entry from a
prior campaign that surfaces in a new era ("A name from the Academy —
someone who remembered Keth from the old days") is one of the most
powerful moments the system can produce.

### Implementation Notes

**ContextPackage addition:**

- `reputation_entries: list[str]` — 0-3 selected reputation echo
  strings for prompt injection. Empty list when nothing qualifies or
  during cooldown.

**ArcState addition:**

- `last_reputation_echo_turn: int` — turn number of the most recent
  narration that included a reputation echo. Default 0. Used for
  cooldown enforcement (current_turn - last_echo >= 3).

**New function in `state/session.py`:**

- `select_reputation_echoes(session_id, scene_context, current_turn)
  -> list[str]` — implements the selection and scoring logic.

**Reconciliation prompt update:** Add the REPUTATION EVENT guidance
to `gm/prompts/reconciliation.txt`.

**Build Roadmap:** Reputation echo population begins with the full
reconciliation system (Phase 7). Reputation echo delivery can be
wired as soon as the log has entries — potentially late Phase 7 or
Phase 8.

---

# Section 2: Conditional Choice Availability from Behavioral Patterns

**Adds to:** Game Mechanics as new §24.4, extending §24 (Semantic
Memory and Meaningful Choice Extraction).

**What exists:** Vision §7 describes the concept — some choices are
only available because of who the character has become. GM §24 designs
the behavioral annotation system that produces the pattern data. GM
§14.5 designs aspiration echoes that reflect growth direction.

**What's missing:** The mechanism by which accumulated behavioral
patterns actually constrain or expand the cloud GM's choice generation.

---

## 2.1 The Design Principle

The Vision Document (§7) specifies two manifestations:

**Unlocked choices:** "A choice that requires trusting an NPC might
only appear if the player has established a pattern of trust in prior
turns." A player who has consistently chosen protective, relationship-
oriented actions should see options that assume earned trust — options a
guarded, self-interested player would never be offered.

**Foreclosed choices:** "A choice that involves calling on a contact
might only appear if that contact is alive and favorably disposed."
More broadly, a player who has burned every bridge should find that
certain options simply don't exist when they need them most.

The critical design constraint: **the player never knows what they're
missing.** Foreclosed choices don't appear with a "locked" icon. They
simply aren't there. The absence is felt, not announced. This preserves
the invisible mechanics principle.

## 2.2 The Behavioral Availability Signal

The choice annotation system (GM §24) produces per-turn annotations
with `priority_revealed`, `behavioral_tags`, and `throughline_direction`
fields. At act boundaries, the compression system aggregates these into
a **behavioral fingerprint** — the top 5 `priority_revealed` values and
the top 10 `behavioral_tags` across the act.

The accumulated fingerprint across the campaign becomes the **behavioral
availability signal** — a structured summary of who the character has
revealed themselves to be through their choices.

**Signal structure:**

```json
{
  "dominant_priorities": [
    "relationship_over_safety",
    "truth_over_advantage",
    "patience_over_speed"
  ],
  "dominant_tags": [
    "protective", "loyal", "cautious", "observant",
    "honest_with_allies", "deceptive_with_strangers"
  ],
  "throughline_lean": "becoming_someone_worth_following",
  "pattern_strength": 0.72
}
```

`dominant_priorities` — the 3 most frequent `priority_revealed` values
across all annotated turns in the campaign so far.

`dominant_tags` — the 6 most frequent `behavioral_tags`.

`throughline_lean` — the dominant `throughline_direction` from
annotations with `throughline_relevance: "high"`.

`pattern_strength` — a 0-1 confidence score. How consistent the
player's behavioral pattern has been. Computed as the concentration
ratio of the top 3 priorities relative to total annotated turns.
A player who always chooses the same way scores 0.8+. A player whose
choices are genuinely mixed scores 0.3-0.5. Below 0.3, the signal is
too weak to drive choice availability.

## 2.3 Choice Availability Injection

The behavioral availability signal is injected into the narration
prompt as a new block in the YOUR TASK section, within the choice
generation rules:

```
BEHAVIORAL CONTEXT FOR CHOICES:
This character has established the following patterns through their
choices:
{behavioral_signal}

Use this to shape which choices you offer:
- If the character has consistently shown [trust/loyalty/protectiveness],
  include at least one choice that ASSUMES this trust is established —
  an option that only someone who has earned trust would be offered.
  ("Doss tells you something he would not tell anyone else.")
- If the character has consistently shown [self-interest/pragmatism/
  deception], do NOT offer choices that assume deep trust from NPCs
  whose disposition does not warrant it.
- If the character has NOT established a pattern in a relevant dimension
  (pattern_strength < 0.4), do not constrain choices in that dimension.
- NEVER announce availability constraints. Do not write "because of your
  history" or "given what you've done." The choices simply reflect the
  world as it has been shaped by the player's behavior.
```

**What this does NOT do:**

It does not give the cloud GM a list of locked/unlocked choices. That
would require the GM to reason about negation, which LLMs handle
poorly. Instead, it gives the GM a behavioral portrait and asks it to
generate choices that naturally reflect the world's response to that
portrait. A player who has been generous and protective finds that NPCs
offer them things. A player who has been self-serving finds that NPCs
are transactional. The availability emerges from the GM's understanding
of how people respond to patterns, not from a mechanical lock system.

## 2.4 NPC-Specific Availability

Beyond the general behavioral signal, specific NPC dispositions create
hard availability constraints. These are already in the system — NPC
state cards with disposition values and knowledge states — but the
connection to choice availability needs to be explicit.

**Narration prompt addition to choice rules:**

```
- NPC AVAILABILITY: An NPC with disposition below 0.3 will NOT offer
  help, share information voluntarily, or extend trust. Choices that
  depend on NPC cooperation should only appear for NPCs whose
  disposition supports it. An NPC who does not know something cannot
  reveal it. An NPC who is afraid will not take risks for the player
  unless their motivation compels it.
```

This is simpler than the behavioral pattern system because it's
state-based rather than pattern-based. The NPC state card already tells
the GM everything it needs.

## 2.5 Authored Availability Gates

Some choice availability is authored in the campaign spine rather than
inferred from behavior. The campaign spine can include
`availability_gates` on specific anchor beats or variation points:

```json
{
  "choice_gate": {
    "description": "Offer the option to call for NPC help",
    "requires": {
      "npc_disposition_min": {"doss": 0.5},
      "behavioral_tag_present": ["loyal"],
      "npc_alive": "doss"
    }
  }
}
```

When a gate's conditions are met, the context package includes the
gated choice option in the narration prompt's situation description.
When not met, the option is absent. The GM generates choices from what
it receives — no special logic needed.

**V1 note:** Authored gates are a Campaign Studio feature (spine data).
They are evaluated by the Game Engine at context assembly time. Simple
NPC disposition gates can exist in V1 spines. Behavioral tag gates
require the semantic memory system (Phase 13).

## 2.6 Threshold and Edge Cases

**Pattern strength threshold:** When `pattern_strength` is below 0.4,
the behavioral signal block is omitted from the prompt entirely. The
cloud GM generates choices unconstrained by behavioral patterns. This
is correct early in a campaign (turns 1-10) when insufficient data
exists.

**Mixed patterns:** A player whose behavioral tags include both
"protective" and "ruthless" presents a mixed signal. The GM should
reflect this as ambivalence — choices that let the player continue to
be contradictory, because contradictory characters are interesting.
The prompt instruction: "If the behavioral pattern shows contradictions,
reflect the contradiction in the choices — offer options that pull in
different directions. Do not resolve the contradiction for the player."

**Pattern evolution:** The behavioral signal updates at each act
boundary (when annotations are aggregated). Within an act, the signal
is static. This means a dramatic mid-act reversal (a previously
cautious player suddenly takes a huge risk) won't immediately change
the choice landscape. The shift becomes visible in the next act. This
is correct — behavioral patterns should be slow-moving, not reactive.

### Implementation Notes

**ContextPackage addition:**

- `behavioral_signal: Optional[dict]` — the behavioral availability
  signal structure from §2.2. Null when pattern_strength < 0.4 or when
  annotations are unavailable.

**New function in `engine/advancement.py`:**

- `compute_behavioral_signal(annotations: list[dict],
  turns_annotated: int) -> Optional[dict]` — aggregates per-turn
  annotations into the behavioral signal structure. Returns None when
  insufficient data.

**Compression integration:** The behavioral signal is recomputed at
each act boundary as part of the compression step. The signal is
stored in the session's arc state so it persists across process
restarts and is available without recomputation each turn.

**Build Roadmap:** Conditional choice availability requires:
1. Phase 13 (semantic memory — annotations must exist)
2. The behavioral signal computation (new function)
3. Prompt injection (narration template addition)

This system comes online alongside the semantic memory system in
Phase 13. Before Phase 13, all choices are unconstrained by behavioral
patterns (the system falls back to NPC state and disposition, which
are available from Phase 7).

---

# Section 3: Deferral Completion Confirmation

| Deferral | Design Location | Status |
|----------|----------------|--------|
| 1. Reputation Echoes | GM §1 (existing) + §1.1-1.4 (new, above) | **NOW COMPLETE** |
| 2. Within-Act Pacing Arc | GM §26 (§27.3-27.6) | **Already complete** |
| 3. Meaningful Choice Tagging | GM §24 (§24.1-24.3) | **Already complete** |
| 4. Conditional Choice Availability | GM §24.4 (new, above, §2.1-2.6) | **NOW COMPLETE** |
| 5. Scene-Type-Aware Context Assembly | GM §10 (full routing profiles) | **Already complete** |

All five deferrals now have complete design specifications.

---

# Section 4: Deep Logic Analysis — Full System Walkthrough

This section traces every data flow through the entire system — V1
through post-V1 — to verify that all components connect correctly,
no data is produced without a consumer, no consumer depends on data
that isn't produced, and no invariant is violated.

## 4.1 The V1 Turn Loop — Step-by-Step Data Flow

**Precondition:** A session exists. Turn 0 (opening) has been logged.
The player has read the opening narration and is selecting a choice.

### Step 1: Player selects choice_index

**Input:** Integer index (0-3) from the frontend.
**Action:** Turn handler loads session from DB, retrieves the most
recent turn row, extracts `choices_json[choice_index]` as
`player_action` and `skill_tags_json[choice_index]` as the skill
hint.
**Output:** `player_action: str`, `skill_hint: str | None`

**Verification:** The choices_json and skill_tags_json are stored by
the previous turn's `log_turn()` call. Both are populated from
`NarrationResult.choices` and `NarrationResult.skill_tags`. The
`_parse_response()` function guarantees both lists have the same
length. ✓

### Step 2: Scene description assembly

**Input:** Previous turn's narration, player's selected action.
**Action:** Concatenate last narration excerpt + player action into a
scene description for the local GM.
**Output:** `scene_description: str`

**Verification:** The narration is stored in the turn row. The
combination gives the local model enough context to determine check
requirements. ✓

### Step 3: Check decision (local model)

**Input:** `character`, `scene_description`, `player_action`,
`arc_state`, `recent_failure_count`
**Action:** `decide_check()` calls Ollama with the check decision
prompt. Returns structured JSON.
**Output:** `CheckDecision` with `requires_check`, `skill`,
`difficulty`, `boost_dice`, `setback_dice`, `scene_type`,
`moral_weight`, `reasoning`

**Verification:**
- Skill normalization via `_normalize_skill()` handles LLM
  hallucinated skill names. ✓
- Scene type defaults to "social" on invalid value. ✓
- Moral weight clamped to 0-3. ✓
- 3 retries with JSON schema enforcement. ✓
- Fallback on total failure: `requires_check=False`. ✓

**Potential issue:** The `recent_failure_count` is computed from the
last 3 turns' outcome quadrants. If the player hasn't had any checks
in 3 turns, this is 0 even if they had failures earlier. This is
correct behavior — failure calibration should only respond to *recent*
pressure. ✓

### Step 4: Dice resolution

**Input:** `CheckDecision` (if `requires_check=True`), `Character`
**Action:** `build_pool()` → `_stage_1_base_pool()` → `roll_pool()`
**Output:** `DicePool`, `RollResult` (or None, None if no check)

**Verification:**
- Pool construction: `max(char, skill)` total dice, upgrade
  `min(char, skill)` to proficiency. Worked example: Keth's Deception
  (Cunning 4, Deception 2) → max(4,2) = 4, upgrade min(4,2) = 2 →
  2 Proficiency + 2 Ability. ✓
- Difficulty dice from enum value. Average = 2 purple. ✓
- Symbol cancellation: successes cancel failures, advantages cancel
  threats. Triumph counts as success for cancellation but is also
  tracked separately (uncancellable). Despair same for failures. ✓
- Tied result (net 0): failure per FFG rules. ✓
- Outcome quadrant: 4 states from success/failure × advantage/threat.
  Net advantages ≥ 0 counts as advantage side. ✓

**Potential issue:** `net_advantages == 0` is classified as advantage
side (`adv = result.net_advantages >= 0`). FFG RAW is ambiguous on
zero advantages — some tables treat it as neutral. For narration
purposes, classifying zero as advantage-side means the "yes, and" /
"no, but" interpretation applies even when there are no net advantages.
This is a reasonable design choice — strictly zero advantage/threat
means the outcome was clean, which "yes, and" / "no, but" handles
well. ✓

### Step 5: Context package assembly

**Input:** Everything — character, arc state, NPC states, story
summary, recent turns, location, situation, galactic context, dice
result, scene type.
**Output:** `ContextPackage`

**Verification:**
- `story_summary` from `get_act_summaries()` — concatenated act
  summaries. Empty on first act. ✓
- `recent_turns` from `get_recent_turns()` — last 5 uncompressed
  turns in chronological order. ✓
- `active_npcs` from `load_npc_states()` — initialized from spine
  on first turn, then from DB thereafter. ✓
- `location` from `arc_state["current_location"]` — initialized from
  `opening_location` at session creation. Static within act in V1. ✓
- `situation` = scene description (previous narration + player action). ✓
- `galactic_context` from spine's current act. ✓
- `scene_type` from check decision. ✓
- `dice_pool` and `roll_result` — None when no check. ✓

**Validation (§7.2 note):** `situation` and `location` must be
non-empty; `active_npcs` must contain at least one NPC; `recent_turns`
must be non-empty except Turn 0. Turn 1 has Turn 0 as a recent turn. ✓

### Step 6: Cloud GM narration

**Input:** `ContextPackage`
**Action:** `_build_prompt()` formats the template, `narrate_turn()`
sends to cloud, `_parse_response()` validates the output.
**Output:** `NarrationResult` with `passage`, `choices`,
`skill_tags`, `raw_response`, `used_local`

**Verification:**
- Template format: all placeholders have matching parameters in
  `_build_prompt()`. New placeholders from v2.1: `{story_position}`,
  `{scene_pacing}`. Both populated. ✓
- Word count enforcement: 250-600 words. Retry on violation. ✓
- Choice count: 2-4. Retry if fewer than 2. ✓
- Skill tag extraction: regex strips `[SkillName]` from end of
  choice text, stores in parallel `skill_tags` list. ✓
- Cloud failure fallback: timeout 20s → local model simplified
  prompt. ✓

**Potential issue:** The retry mechanism appends a correction note
as a second user message. Some providers may handle multi-turn
correction differently. The OpenAI-compatible SDK handles this
correctly for OpenAI and OpenRouter. ✓

### Step 7: Persist

**Input:** All turn data
**Action:** `log_turn()` writes to DB.
**Output:** Turn row in `turns` table.

**Verification:**
- `moral_weight` is now included (Issue 2 fix). ✓
- `context_json` stored when `NARRATIVE_BACKEND != "local"`. ✓
- `scene_type` stored. ✓
- `skill_tags_json` stored alongside `choices_json`. ✓
- `session.updated_at` bumped. ✓

### Step 8: Background tasks

**Action:** Compression check + V1 minimal NPC knowledge update.

**Verification:**
- Compression threshold: 8 uncompressed turns → local model
  summarizes → marks turns compressed. ✓
- Compression never blocks the player (BackgroundTask). ✓
- NPC knowledge update: local model infers what NPCs learned from
  narration. Background task. ✓

---

## 4.2 Cross-Cutting Data Flow Verification

### Data that is produced but has no V1 consumer

| Data | Producer | V1 Status | Future Consumer |
|------|----------|-----------|----------------|
| `moral_weight` on turns | Check decision | Stored, not used | Phase 8 (Morality resolution) |
| `reputation_log` table | Exists in schema | Empty in V1 | Phase 7 (Reconciliation populates) |
| `distillation_pairs` view | SQL view on turns | Populated when cloud active | Backlog (QLoRA fine-tune) |
| `destiny_light/dark` on sessions | Session table | Stored as 0/0 | Phase 11.5 (Destiny Points) |
| `prose_diagnostic` on ContextPackage | Reserved field | Always null | Phase 13 (Prose diagnostic) |
| `sequence` on ContextPackage | Reserved field | Always null | Phase 7 (Multi-beat sequences) |
| `character_drift` on act_summaries | Column exists | Not populated in V1 | Phase 7 (Reconciliation) |

**Assessment:** All of these are correctly deferred. Data is reserved
but not consumed. No V1 code depends on their values. ✓

### Data that is consumed but has a fallback for missing production

| Consumer | Expected Data | Fallback When Missing |
|----------|--------------|----------------------|
| `_build_prompt()` | `scene_pacing` | Defaults to "social" pacing |
| `_build_prompt()` | `galactic_context` | "No wider context provided" |
| `_build_prompt()` | `reputation_entries` | Empty list → block omitted |
| `_build_prompt()` | `behavioral_signal` | Null → block omitted |
| `get_act_summaries()` | Act summaries | Empty string (no prior acts) |
| `get_recent_turns()` | Recent turns | Empty list (Turn 0 only) |
| Failure calibration | Recent failure count | 0 (no recent failures) |

**Assessment:** Every consumer has an explicit fallback for empty/
missing data. No component crashes on missing upstream data. ✓

---

## 4.3 Invariant Verification

### Physics-before-imagination

**The invariant:** Code resolves all mechanical outcomes before the
narrative model receives the context package.

**Verification path through the turn loop:**

1. Check decision (local model) → mechanical decision ✓
2. Pool construction → pure code ✓
3. Dice roll → pure code ✓
4. Wound/strain application → pure code ✓
5. Context package assembly → packages mechanical results ✓
6. Cloud GM narration → receives the *results*, not the *inputs* ✓

The cloud GM never sees the dice pool before it's rolled. It receives
the already-computed `RollResult` with net successes, advantages,
triumphs, despairs, and outcome quadrant. It cannot influence the
mechanical outcome. ✓

**Post-V1 additions that must preserve this invariant:**

- Talent pool modification (Phase 11): modifies pool *before* roll. ✓
- Destiny Point spending (Phase 11.5): modifies pool *before* roll. ✓
- Force dice (Phase 14): added to pool *before* roll. ✓
- Force pip resolution: happens *after* roll but *before* narration. ✓
- Dark side temptation: happens *after* roll but *before* narration —
  a player choice that determines Conflict, not narrative outcome. ✓
- Intervention talents (Phase 12): post-roll re-roll option — happens
  *before* narration as a pre-narration choice point. ✓

All post-V1 additions respect the invariant. No mechanical decision
is delegated to the cloud model. ✓

### One cloud call per turn

**Verification:** `narrate_turn()` is called exactly once in the turn
handler (Step 6). The local model is called for check decisions
(Step 3) and background tasks (Step 8), but these are local calls,
not cloud. ✓

**Post-V1 additions:**

- Choice annotation (Phase 13): local model. ✓
- Reconciliation (Phase 7): local model. ✓
- Milestone reflection (Phase 12): cloud call — but this is a
  *between-act* call, not a *within-turn* call. Between-act processing
  is player-facing but not part of the turn loop. The invariant applies
  to turn-level calls. ✓
- Growth passage (Phase 14): cloud call — same as milestone, runs
  between acts. ✓

The one-cloud-call-per-turn limit is preserved. Between-act cloud
calls are separate. ✓

### The dice are the truth

**Verification:** The narration prompt contains: "HONORS THE DICE
RESULT EXACTLY — do not soften failures, do not reduce triumphs."
The dice result block in the context package includes explicit
quadrant labels and Triumph/Despair instructions. ✓

**What could violate this:** If the cloud GM ignores the instruction
and writes a success when the dice said failure. This is a compliance
testing concern (Backlog item 1.36), not an architectural concern.
The system enforces correctness through prompt instruction. A
non-compliant model is caught during the 5-category compliance test
(LLM Eval §11). ✓

---

## 4.4 Post-V1 Integration Points

### Phase 7 → Phase 8 dependency chain

Phase 7 (Reconciliation) must exist before Phase 8 (Motivation Wiring)
because:

1. Motivation wiring depends on act boundary detection (reconciliation
   detects when `act_progress` reaches 1.0).
2. Obligation/Duty activation rolls happen at act boundaries (step 8
   of the between-act pipeline).
3. Morality resolution (Conflict vs d10) happens at act boundaries
   (step 10).

**Verification:** Build Roadmap has Phase 7 before Phase 8.
Phase 7 depends on V1 complete. Phase 8 depends on V1 complete
(but *should* depend on Phase 7). ✓

**NOTE — Dependency gap in Build Roadmap:** Phase 8 (Motivation Track
Wiring) lists dependencies as "V1 complete" but should also list
"Phase 7 complete" because motivation activation rolls depend on act
boundary detection from the reconciliation system. The between-act
pipeline (§26, §27.5) runs step 8 (Obligation/Duty roll) and step 10
(Morality resolution) as part of the pipeline that only fires when
Phase 7's act boundary detection triggers. Without Phase 7, there are
no act boundaries, so motivation rolls never fire.

**Recommendation:** Add "Phase 7 complete" as a dependency for Phase 8.

### Phase 13 → Conditional Choice Availability

Phase 13 (Semantic Memory) produces annotations. Conditional choice
availability (§24.4, designed above) depends on annotations being
aggregated into behavioral fingerprints.

**Verification:** The design specifies that when `pattern_strength <
0.4` or annotations are unavailable, the behavioral signal block is
omitted and choices are unconstrained. This means the system degrades
gracefully before Phase 13 is implemented. ✓

### Reputation Echoes → Phase 7

Reputation echo population depends on the reconciliation step
producing `reputation_event` entries. This begins in Phase 7.

**Verification:** The design specifies that the reputation block is
omitted when the log is empty. Before Phase 7, no entries exist and
no reputation echoes appear. ✓

---

## 4.5 Token Budget Analysis

The narration prompt has grown significantly through the pre-build
fixes. Let me estimate token usage for a typical turn:

| Section | Estimated Tokens | Notes |
|---------|-----------------|-------|
| Voice + anti-slop | ~200 | Static text |
| CHARACTER | ~120 | `narrative_status()` output |
| CHARACTER VOICE | ~60 | 2-3 sentences |
| STORY CONTEXT | ~100 | Campaign, position, throughline, tension, terminology prohibition |
| STORY SO FAR | ~200-400 | Act summaries + 5 recent turns |
| OPEN THREADS | ~50-100 | 3-5 bullet threads |
| ACTIVE NPCs | ~150-300 | 2-3 NPC state cards |
| CURRENT SCENE | ~200-300 | Location, situation, galactic context, scene pacing |
| DICE RESULT | ~50-80 | Result block |
| YOUR TASK | ~400 | 10 instructions + choice rules |
| DICE GUIDE | ~80 | Static interpretation guide |
| **Total** | **~1600-2100** | |

Cloud model context window: most candidates have 128K+ tokens.
Narration prompt at ~2000 tokens is < 2% of context. No concern. ✓

`MAX_TOKENS` for response: 1500. A 600-word passage is ~800 tokens.
4 choices with tags add ~200 tokens. Total response ~1000 tokens.
1500 token max provides adequate headroom. ✓

---

## 4.6 Issues Found During Analysis

### Issue A — Phase 8 dependency (noted above)

Phase 8 (Motivation Track Wiring) should depend on Phase 7 (Post-Turn
Reconciliation), not just V1 complete.

**Fix:** Update Build Roadmap Phase 8 dependencies from "V1 complete"
to "V1 complete, Phase 7 complete."

### Issue B — `skill_tags_json` column missing from DB schema

The turn orchestration (Impl §9.1) stores `skill_tags_json` alongside
`choices_json`, but the `turns` table schema in §8.1 doesn't include
this column. The Implementation doc v2.0 revision notes mention it but
the actual CREATE TABLE statement was not updated.

**Fix:** Add `skill_tags_json TEXT` to the `turns` table schema in
§8.1.

### Issue C — `faction_tags` on reputation_log

The existing `reputation_log` schema in §8.1 has only `session_id`,
`turn_number`, `summary`, `created_at`. The reputation echo design
(Section 1 above) adds `faction_tags TEXT` and
`surfaced_count INTEGER DEFAULT 0`. These need to be added to the
schema.

**Fix:** Update the `reputation_log` CREATE TABLE in §8.1.

### Issue D — Opening narration context validation edge case

The context validation rule says "`active_npcs` must contain at least
one NPC." But on Turn 0 (opening narration), are NPCs initialized
before the context package is assembled? The session creation flow
(§9.2) initializes NPC states from the spine before building the
context. **Verified: yes, NPC initialization happens before context
assembly.** ✓

### Issue E — Reconciliation section number mismatch

GM §26 is titled "Post-Turn State Reconciliation" but its subsections
use `27.1`, `27.2`, etc. instead of `26.1`, `26.2`. This is a typo in
the section numbering.

**Fix:** Renumber internal subsections from `27.x` to `26.x`.

---

## 4.7 Final Assessment

The system is architecturally sound. The data flows connect correctly
from player input through mechanical resolution through narrative
generation through state persistence. Every component has explicit
fallbacks for missing upstream data. The physics-before-imagination
invariant is preserved through all post-V1 additions. The one-cloud-
call-per-turn limit is maintained. Token budgets are comfortable.

The five deferrals now all have complete design specifications.

Three minor issues found (A, B, C) and one typo (E) — all fixable
in the documents before build. One edge case verified as already
handled (D).

**Verdict: Ready for implementation.**
