# Storyteller V3 — Build Roadmap

**Document version:** 1.3
**Purpose:** Phased build plan from V1 completion to a playable multi-
era saga. Each milestone produces a testable system. Each phase within
a milestone has files, a goal, dependencies, and success criteria.

**The rule:** Do not start the next phase until the current phase passes
its success criteria. This is the same constraint as V1's build phases,
extended across the full project.

**Reference documents:**
- Implementation Document (v2.5) — V1 build phases and code specs
- Game Mechanics Document (v1.8) — design for all post-V1 systems
- Campaign Studio Implementation (v1.3) — spine schema and Studio build
- LLM Evaluation Document (v2.0) — model selection for all roles
- Design Gap Analysis (v2.0, in `docs/reference/`) — design specs for
  all items not covered by the Game Mechanics or Implementation documents

---

## Milestone 0: V1 — Core Loop

**Status: COMPLETE — March 2026**

**Already specified in Implementation Document Phases 1–6.**

12 success criteria. Keth Varso, The Nar Shaddaa Job, 5 turns without
errors, session persistence, local narration fallback. See
Implementation Document §15.

**When V1 is complete:** The core turn loop works. A player reads prose,
makes choices, dice resolve mechanically, the GM narrates outcomes,
state persists. Everything after V1 extends this loop — nothing
replaces it.

---

## Milestone 1: Full Single-Campaign Experience

**Status: COMPLETE — March 2026**

**Goal:** A player can play The Nar Shaddaa Job from Act 1 through
Act 4 as Keth Varso and it feels like a complete campaign — motivation
tracks create pressure, equipment matters, the character grows, talents
change what the character can do.

**This is the milestone that proves the engine works at campaign scale.**

### Phase 7: Post-Turn State Reconciliation

**Status: COMPLETE — March 2026.** `engine/reconciliation.py` implements full reconciliation with 16-step between-act pipeline.

Files: `engine/reconciliation.py` (new),
`gm/prompts/reconciliation.txt` (new), `gm/context.py` (extend —
pacing block, anchor instruction)

Design: Game Mechanics §26.

Goal: After each narration, the local model analyzes what happened and
produces structured state updates: NPC knowledge/disposition changes,
story progress advancement, thread updates, anchor proximity detection.
The GM receives pacing guidance. Act boundaries trigger the between-act
processing pipeline.

Note: V1 includes a minimal reconciliation step (NPC knowledge updates
only, no story progression). This phase upgrades it to the full system
with story progression, anchor detection, pacing guidance, and act
transition processing. This must be complete before any other
Milestone 1 phase because playing Acts 1-4 requires act transitions.

Dependencies: V1 complete (the minimal reconciliation step exists).

Success criteria:
1. The reconciliation prompt produces valid JSON with NPC updates,
   thread updates, and story progress
2. NPC knowledge lists update after information exchange in narration
3. NPC disposition shifts are within calibrated ranges
4. act_progress advances each turn with delta proportional to
   anchor proximity and turn-count pacing
5. Anchor proximity transitions through distant → approaching →
   imminent → reached
6. When act_progress reaches 1.0, the anchor instruction appears in
   the next turn's context
7. The between-act pipeline fires at act boundaries and runs all
   16 steps in order
8. The GM's narration reflects pacing guidance — early-act turns
   feel exploratory, late-act turns feel urgent

### Phase 8: Motivation Track Wiring

**Status: COMPLETE — March 2026.** Obligation/Duty/Morality integrated into reconciliation pipeline and context assembly.

Files: `state/session.py` (extend), `gm/context.py` (extend),
`gm/prompts/narration.txt` (extend)

The mechanics are fully designed in Game Mechanics §9. The
`moral_weight` field already exists on turn records. What's missing is
the between-act processing that actually triggers these systems.

Goal: Obligation, Duty, and Morality activate per the §9 design — d100
rolls at act boundaries, strain/wound threshold modification, GM prompt
injection, Morality resolution at end of act.

Dependencies: V1 complete, Phase 7 complete (act boundary detection and
the between-act processing pipeline must exist for motivation rolls to
trigger).

Success criteria:
1. At an act boundary, the system generates a d100 Obligation roll
2. When Obligation activates, the GM prompt contains the pressure
   instruction and strain threshold is reduced by 2
3. When Obligation does not activate, no Obligation context appears
4. Conflict accumulates from `moral_weight` across turns in an act
5. At act end, Morality resolves: Conflict vs 1d10, Morality adjusts
6. The GM prompt receives the correct Morality label for the current
   band (Light/Grey/Dark)

### Phase 8.5: NPC Emotional State

**Status: COMPLETE — March 2026.** `EmotionalState` dataclass in `gm/context.py` with mood decay, sustained emotion disposition nudging.

Files: `gm/context.py` (extend — NPCState gains emotional_state),
`state/session.py` (extend — emotional decay processing)

Design: Game Mechanics §25.

Goal: NPCs have transient emotional states that overlay their long-term
disposition. Emotions are set by check results, spine triggers, and
GM-inferred cues. Emotions decay over turns. The GM prompt reflects
current mood.

Dependencies: V1 complete (NPC state cards must exist).

Success criteria:
1. NPCState includes `emotional_state` with mood, intensity, source,
   and decay_rate
2. A failed Deception check sets the target NPC to `suspicious`
3. The NPC's prompt block includes a `Currently:` line when emotional
   state is non-calm
4. Emotional intensity decays by `decay_rate` per turn
5. Decay pauses when the source condition is still active
6. Sustained non-calm states (3+ turns) nudge disposition

### Phase 9: Equipment and Loadout

**Status: COMPLETE — March 2026.** `engine/equipment.py` with full loadout system (weapons, armor, tools, special items, damage calculation).

Files: `engine/equipment.py` (new), `engine/character.py` (extend),
`gm/prompts/check_decision.txt` (extend), `gm/prompts/narration.txt`
(extend)

Design: Game Mechanics §18. Spine schema: `Loadout`, `WeaponEntry`,
`ArmorEntry`, `ToolEntry`, `SpecialItem` in Campaign Studio
Implementation §4.1.

Goal: Keth's loadout (DL-44, armored jacket, slicing kit, stimpacks)
affects checks and narration. The GM knows what the character is
carrying and writes accordingly.

Dependencies: V1 complete.

Success criteria:
1. The character's loadout loads from the campaign spine and persists
   in session state
2. The check decision prompt includes an EQUIPMENT section listing
   capability-relevant gear
3. Weapon damage modifies combat outcome narration
4. Armor soak reduces wounds taken
5. Tool presence/absence gates or modifies relevant checks (slicing
   kit enables Computers on secured systems)
6. The narration prompt receives loadout with narrative notes

### Phase 10: XP Earning and Behavioral Inference

**Status: COMPLETE — March 2026.** `engine/advancement.py` with XP awards, three behavioral signals, skill advancement inference.

Files: `engine/advancement.py` (new), `state/session.py` (extend)

Design: Game Mechanics §14.1 (XP earning) and §14.2 (behavioral
inference for skill ranks).

Goal: At each act boundary, XP is awarded based on performance. The
behavioral inference engine analyzes the player's choice patterns and
automatically allocates XP to skill rank increases.

Dependencies: Phase 8 (motivation wiring — the between-act processing
pipeline must exist).

Success criteria:
1. At act boundary, base XP + bonus conditions are evaluated from the
   turn log
2. 40% of earned XP is reserved for milestones; 60% flows to the
   inference pool
3. The behavioral inference engine produces weighted skill scores from
   three signals: choice aspiration (50%), failure learning (35%),
   practiced competence (15%)
4. The engine selects the highest-scoring affordable skill rank
   increase and applies it
5. No skill increases more than 1 rank per act
6. No skill increases above rank 3 through inference alone
7. Unspent XP carries forward correctly
8. The advancement log records each change

### Phase 11: Talent Tree Engine

**Status: COMPLETE — March 2026.** `engine/talents.py` with 5 talent types, 6 specialization trees, talent library. Pool modification pipeline Stages 2-3 active.

Files: `engine/talents.py` (new), `data/talent_trees/talent_library.json`
(new), `data/talent_trees/smuggler_pilot.json` (new),
`data/talent_trees/smuggler_scoundrel.json` (new),
`data/talent_trees/smuggler_thief.json` (new),
`engine/checks.py` (extend — pool modification pipeline)

Design: Game Mechanics §15.

Goal: Talent data exists for the Smuggler career. The pool modification
pipeline applies Type 1 (passive) and Type 2 (conditional) talents
automatically. The check decision prompt knows about Type 3 (skill
substitution) talents. The narration prompt knows about Type 4
(narrative enabler) talents and per-turn activations.

**Critical:** The pool modification pipeline built in this phase must
follow the six-stage architecture from Game Mechanics §23.5: base →
passives → conditionals → destiny → Force dice → roll. Stages 4 and 5
are empty in this phase but the pipeline structure must support them.

Dependencies: Phase 9 (equipment — pool modification pipeline shared
infrastructure).

Success criteria:
1. Talent library loads and specialization trees load and cross-
   reference correctly
2. A character with Skilled Jockey has 1 fewer setback on Piloting
   checks (Type 1 passive verified)
3. A character with Dodge in a combat scene has difficulty upgraded
   on incoming attacks, strain charged automatically (Type 2
   conditional verified)
4. A character with Convincing Demeanor — the check decision prompt
   lists the substitution and the local model can select Deception
   for a Charm situation (Type 3 verified)
5. Narrative enabler talents appear in the narration prompt's
   CHARACTER CAPABILITIES block (Type 4 verified)
6. Talent activations are logged per turn and included in narration
   context
7. The pipeline has empty-but-present Stage 4 (destiny) and Stage 5
   (Force dice) slots that pass through without modification

### Phase 11.5: Destiny Point Pool

**Status: COMPLETE — March 2026.** `engine/destiny.py` with Light/Dark spending, escalation pacing, seize-the-moment choice.

Files: `engine/destiny.py` (new), `engine/checks.py` (extend — Stage 4
of pool pipeline)

Design: Game Mechanics §23.

Goal: Light Side and Dark Side Destiny Points modify the dice pool
based on narrative conditions. The pool flip mechanic works. The GM
prompt receives destiny narrative notes.

Dependencies: Phase 11 (the pipeline must exist with Stage 4 slot).

Success criteria:
1. Destiny pool initializes from Force die roll at session creation
2. Light Side spend triggers on a high-stakes check, upgrading one
   ability → proficiency
3. Dark Side spend triggers when Obligation is active, upgrading one
   difficulty → challenge
4. Pool flips correctly after each spend
5. Escalation pacing tracks spends and adjusts thresholds
6. The GM prompt receives `destiny_spent` flag with narrative guidance
7. The seize-the-moment choice presents correctly at spine-authored
   moments (when a Light Side point is available)

### Phase 12: Milestone Reflections and Intervention

**Status: COMPLETE — March 2026.** Milestone reflections via `gm/cloud_gm.py`, Type 5 interventions via `engine/talents.py`. Prompt: `milestone_reflection.txt`.

Files: `engine/advancement.py` (extend), `gm/cloud_gm.py` (extend —
milestone passage generation), `engine/talents.py` (extend —
intervention step)

Design: Game Mechanics §14.3 (milestone reflections), §15.1 Type 5
(intervention talents), §15.6 (tree navigation).

Goal: Talent milestone reflections fire at act boundaries when
conditions are met. The player makes narrative choices that map to
talent acquisitions. Type 5 intervention talents create a pre-narration
choice point after dice resolution.

Dependencies: Phase 10 (XP — reserved_xp must exist), Phase 11 (talent
engine — tree data and available talent computation).

Success criteria:
1. When reserved_xp is sufficient and behavioral signals suggest a
   tree direction, a talent milestone triggers at the act boundary
2. The cloud GM generates a reflection passage with 2-3 narrative
   choices mapping to different tree branches
3. The player's selection results in the correct talent being acquired
4. Acquired talents immediately affect subsequent checks (pool
   modification pipeline reflects the new talent)
5. A character with Natural Charmer who fails a Deception check is
   offered a pre-narration "push through" choice
6. Accepting the intervention rerolls the check and charges strain
7. Declining preserves the original result and the talent remains
   available
8. Intervention talents track usage per act and reset at boundaries

### Phase 13: Semantic Memory, Aspiration Echoes, and Prose Diagnostics

**Status: COMPLETE — March 2026.** Choice annotation via `gm/fast_gm.py`, aspiration echoes via `gm/context.py`, prose diagnostic via `gm/fast_gm.py`. Prompt: `choice_annotation.txt`.

Files: `gm/context.py` (extend — aspiration echo block),
`gm/prompts/narration.txt` (extend), `gm/fast_gm.py` (extend —
prose diagnostic call + choice annotation call),
`gm/prompts/choice_annotation.txt` (new)

Design: Game Mechanics §14.5 (aspiration echoes), §13 (prose
diagnostic signal), §24 (semantic memory).

Goal: The GM prompt includes an aspiration echo block. The prose
diagnostic runs per turn and flags staleness patterns. The choice
annotation system extracts behavioral meaning from each player choice,
feeding richer data to the behavioral inference engine and character
drift notes.

Dependencies: Phase 10 (behavioral inference — echo content derived
from weighted scores, annotations enrich inference signal).

Success criteria:
1. The aspiration echo block appears in the narration prompt when
   active (non-empty) and is omitted when inactive
2. Echo content reflects the behavioral inference engine's current
   skill direction
3. The prose diagnostic produces structured JSON flagging repetition,
   sensory monotony, and positivity bias
4. Diagnostic results inject into the next turn's context package
5. Scene-type-aware assembly routes echo content correctly
   (foregrounded in introspection, omitted in combat)
6. The choice annotation prompt runs (parallel with check decision)
   and produces structured JSON with priority_revealed,
   behavioral_tags, throughline_relevance
7. Annotations are stored in the turn record's `choice_implications`
   field
8. The behavioral inference engine uses annotations when available
   and falls back to skill-tag-only when annotations are null
9. Act summaries include aggregated behavioral fingerprint from
   annotations

### Milestone 1 Success Criteria — ACHIEVED

Play The Nar Shaddaa Job Acts 1–4 as Keth Varso:

1. Obligation triggers at least once across 4 acts and produces
   visible narrative pressure
2. At least one NPC exhibits a non-calm emotional state that
   visibly affects the GM's narration
3. Keth's DL-44 and slicing kit affect at least one check each
4. At least 2 skill rank increases occur through behavioral inference
5. At least 1 talent milestone reflection fires and the acquired
   talent is visible in subsequent checks or narration
6. At least 1 Destiny Point (Light or Dark) fires and the
   narrative reflects luck or misfortune
7. Choice annotations are being recorded in the turn log
8. The character feels meaningfully different at Act 4 than Act 1
9. The loop runs 20+ turns across 4 acts without errors

---

## Milestone 2: Force-Sensitive Campaign

**Status: COMPLETE — March 2026**

**Goal:** A player can play as a Force-sensitive character through a
campaign — rolling Force dice, facing dark side temptation choices,
acquiring Force powers, and experiencing the Morality spiral.

### Phase 14: Force Dice Resolution

**Status: COMPLETE — March 2026.** `engine/force.py` with pip resolution, temptation mechanics, dark-dominant inversion.

Files: `engine/force.py` (new), `engine/checks.py` (extend —
Force-enhanced pool construction), `gm/fast_gm.py` (extend —
check decision Force fields)

Design: Game Mechanics §16.1 (Force dice), §16.2 (dark side
temptation), §16.7 (check decision Force fields).

Goal: Force dice are added to pools when force_use is true. Pip
resolution determines Force success/failure. Dark side temptation
fires as a pre-narration choice when light pips are insufficient.

Dependencies: Phase 12 (intervention step — the pre-narration choice
mechanism is shared).

Success criteria:
1. A Force Rating 1 character rolls 1 Force die on a force_use check
2. Light pips ≥ requirement → Force succeeds, no Conflict
3. Light pips insufficient, light + dark ≥ requirement → dark side
   temptation choice is presented
4. Player accepts temptation → Force succeeds, Conflict earned equal
   to dark pips used, strain charged
5. Player rejects temptation → Force fails, no Conflict
6. Dark-dominant character (Morality < 40) → dark pips are free,
   light pips cost strain
7. The four-result matrix (skill × Force success/failure) produces
   correct narration guidance for the GM
8. The check decision prompt includes FORCE POWERS section and the
   local model correctly identifies Force actions

### Phase 15: Force Powers and Progression

**Status: COMPLETE — March 2026.** 5 Force powers (enhance, heal_harm, influence, move, sense) as JSON data. Force power milestones via `engine/force.py`. Prompt: `force_power_milestone.txt`.

Files: `data/force_powers/move.json` (new), `data/force_powers/
sense.json` (new), `data/force_powers/influence.json` (new),
`data/force_powers/enhance.json` (new), `data/force_powers/
heal_harm.json` (new), `engine/force.py` (extend),
`engine/advancement.py` (extend — Force power milestones)

Design: Game Mechanics §16.3 (Force powers), §16.4 (progression),
§16.5 (committed dice).

Goal: Five core Force powers exist as data. The GM generates Force-
tagged choices for powers the character possesses. Force power upgrade
milestones work through the reflection system. Committed Force dice
reduce available pool.

Dependencies: Phase 14 (Force dice resolution).

Success criteria:
1. A character with Move can receive `[Force:Move]` tagged choices
   from the GM
2. A character without Move never receives Move-tagged choices
3. Force power upgrade milestones fire and produce narrative choices
   mapping to range/strength/control upgrade paths
4. Committing 1 Force die to Sense reduces available Force dice by 1
   on subsequent rolls
5. Releasing a commitment restores the die to the available pool
6. Force Rating increase through a specialization talent (Dedication
   equivalent) works via Category 3 milestone

### Phase 15.5: Force and Destiny Talent Trees

**Status: COMPLETE — March 2026.** 3 FaD trees (guardian_protector, consular_niman_disciple, sentinel_shadow) + 3 Smuggler trees.

Files: `data/talent_trees/` — add Force and Destiny specialization
trees (Guardian, Consular, Sentinel at minimum)

Design: Game Mechanics §15.7 (phased data entry — Phase 3).

Goal: Force-sensitive characters have specialization trees to progress
through. Lightsaber characteristic substitution talents work.

Dependencies: Phase 11 (talent engine), Phase 15 (Force powers).

Success criteria:
1. At least 3 Force and Destiny specialization trees load correctly
2. Lightsaber characteristic substitution (e.g., use Willpower
   instead of Brawn) functions via Type 3 substitution talent
3. Force-sensitive talent milestones generate appropriate reflection
   passages themed around Force training

### Milestone 2 Success Criteria — ACHIEVED

Play a 2-act test campaign as a Force Rating 1 character:

1. At least 3 Force checks occur with correct pip resolution
2. Dark side temptation fires at least once and both accept/reject
   paths work
3. At least 1 Force power upgrade milestone fires
4. Committed Force dice correctly reduce available dice
5. Morality drifts in the direction indicated by the player's Force
   choices
6. The experience feels meaningfully different from playing a non-
   Force character

---

## Milestone 3: Vehicles and Space

**Status: COMPLETE — March 2026**

**Goal:** The player can fly Mira's Luck, engage in space encounters,
and the ship feels like a persistent part of the story.

### Phase 16: Vehicle System

**Status: COMPLETE — March 2026.** `engine/vehicle.py` with ShipState, damage tiers, handling, critical hit table. Ship persistence in `state/db.py`.

Files: `engine/vehicle.py` (new), `state/db.py` (extend — ship_states
table), `gm/fast_gm.py` (extend — space_combat scene type),
`gm/context.py` (extend — ship state injection)

Design: Game Mechanics §17.

Goal: Ship state cards persist. The `space_combat` scene type routes
to vehicle-appropriate skills. Handling modifies piloting pools. The
three-tier damage model (operational/stressed/critical) affects checks
and narration.

Dependencies: Milestone 1 complete (equipment and talent systems
provide the pool modification infrastructure).

Success criteria:
1. Mira's Luck loads from the campaign spine vehicle registry and
   persists in session state
2. The `space_combat` scene type activates vehicle-appropriate check
   decisions (Piloting, Gunnery, Mechanics)
3. Handling rating adds/removes boost/setback on Piloting checks
4. Ship damage transitions through operational → stressed → critical
   with correct setback additions and narration guidance
5. Vehicle critical hits are resolved from the simplified table and
   applied as narrative tags
6. The GM prompt includes ship state and writes accordingly

### Milestone 3 Success Criteria — ACHIEVED

Play a test scenario involving a space chase and a ship combat:

1. The player flies the ship using Piloting choices and the pool
   reflects the ship's handling
2. Ship takes damage, transitions to stressed, setback appears
3. At least one vehicle critical hit resolves correctly
4. Ship status persists across turns

---

## Milestone 4: Multi-Campaign Saga

**Status: PARTIAL — Phase 17 complete, Phases 18-22 not started**

**Goal:** A player can complete one campaign, carry their character
into a new campaign spine, and the transition feels like a chapter
break in an ongoing story — not a system reset.

### Phase 17: Time Skip Vignettes

**Status: COMPLETE — March 2026.** `engine/time_skip.py` with vignette selection, effects, NPC drift. Time skip prose via `gm/cloud_gm.py`. Prompts: `time_skip_opening.txt`, `time_skip_closing.txt`.

Files: `engine/time_skip.py` (new), `gm/cloud_gm.py` (extend —
opening/closing passage generation), `state/session.py` (extend —
between-act vignette processing)

Design: Game Mechanics §19.

Goal: Between acts, when a time skip is defined, the player
experiences: opening passage → 2-3 authored vignettes with choices →
closing passage. Vignette choices feed behavioral inference and NPC
disposition changes.

Dependencies: Phase 10 (behavioral inference — vignette choices must
feed the inference engine).

Success criteria:
1. A time skip with a 3-month duration presents 2 vignettes from the
   spine's vignette library
2. Vignette selection respects prerequisites and category diversity
3. Each vignette presents its passage and 2-3 choices
4. Vignette choice skill tags feed into behavioral inference weighting
5. Vignette NPC effects modify disposition correctly
6. Vignette moral_weight feeds into Conflict accumulation
7. The closing passage reflects the pattern of vignette choices made

### Phase 18: Psychometric Prologue

**Status: NOT STARTED.** Full spec (design robustness + implementation plan) at `docs/specialist/prologue-system.md`.

Files: `engine/prologue.py` (new), `web/index.html` (extend — funnel
UI)

Design: Game Mechanics §5, Campaign Studio Design §§2.5-2.6.

Goal: A player navigates the character funnel (Timeline → Allegiance →
Variant), plays 3-5 prologue scenes, and emerges with a mechanically
configured character. The prologue selects from pre-designed variants
based on behavioral signals.

Dependencies: Phase 10 (behavioral inference — prologue uses the same
signal processing for axis tags).

Success criteria:
1. The funnel UI presents Timeline, Allegiance, and Variant steps
2. 3-5 prologue scenes present choices with hidden axis tags
3. Behavioral archetype is computed from axis tag patterns
4. Mechanical profile is selected from the career-type mapping table
5. The resulting character is indistinguishable from a hand-built
   character (same Pydantic model, same session creation path)

### Phase 19: Cross-Era Import/Export

**Status: NOT STARTED.** Note: The Campaign Studio side (`studio/import_interface.py`) is built as part of CS-3. The Game Engine side (`engine/import_export.py`) is not yet implemented.

Files: `engine/import_export.py` (new), `engine/advancement.py`
(extend — Category 5 career transition milestone)

Design: Game Mechanics §20, Campaign Studio Implementation §6.

Goal: A completed character exports an import package. A new campaign
spine ingests the package, applies specialization mappings, XP
rebalancing, loadout transition, and motivation track changes. The
Category 5 milestone reflection presents the era transition as a
narrative choice.

Dependencies: Phase 12 (milestone reflections), Phase 17 (time skips
— inter-campaign skip uses the same passage generation).

Success criteria:
1. Export produces a complete import package with mechanical and
   narrative state
2. Import applies specialization mappings (continuity, dormancy,
   evolution) correctly
3. XP rebalancing adds bonus XP when below target range
4. Equipment transitions to the imported loadout
5. The transition passage is generated reflecting the character's
   history
6. The Category 5 milestone presents specialization and motivation
   choices for the new era
7. The receiving campaign plays identically whether the character was
   imported or created fresh (with different starting state)

### Phase 20: Large-Scale NPC Management

**Status: NOT STARTED.**

Files: `engine/npc_relevance.py` (new), `gm/context.py` (extend —
tiered NPC injection)

Design: Game Mechanics §21.

Goal: NPCs are scored for relevance each turn and assigned to Tier 1
(full state card), Tier 2 (one-sentence summary), or Tier 3 (omitted).
Cross-campaign NPC summaries compress and rehydrate correctly.

Dependencies: Phase 19 (import/export — NPC summaries are part of the
import package).

Success criteria:
1. Relevance scoring produces a ranked NPC list each turn
2. Top 4-6 NPCs inject as full state cards (Tier 1)
3. Next 6-10 inject as one-sentence summaries (Tier 2)
4. Remaining NPCs are omitted from the prompt (Tier 3)
5. Total NPC context stays within the token budget
6. Imported NPC relationship summaries rehydrate into full state
   cards when the NPC appears in the new campaign's roster
7. The GM writes appropriately for each tier — Tier 1 NPCs feel
   fully realized, Tier 2 NPCs can be referenced without deep
   characterization

### Phase 21: Canon Character Profiles

**Status: NOT STARTED.** `data/canon_profiles/` directory does not yet exist (will be created when this phase begins). Schema fields (CanonVoice, CanonRelationshipDynamics, CanonActOverride) exist in `studio/schema.py`.

Files: `data/canon_profiles/` (new — initial profiles for Academy/NJO
era characters), `gm/context.py` (extend — canon profile injection)

Design: Game Mechanics §22.

Goal: Canon characters use extended profiles with voice, behavioral
envelope, relationship dynamics, era-specific notes, and anti-
stereotype notes. Per-act overrides evolve the profile during the
campaign.

Dependencies: Phase 20 (NPC management — canon profiles use the same
tier injection system).

Success criteria:
1. A canon NPC entry with `canon: true` loads the extended profile
   fields
2. The narration prompt injects the full canon profile for Tier 1
   canon characters
3. Per-act overrides merge onto the base profile at act transitions
4. Anti-stereotype notes are present in the prompt and the GM avoids
   the specified stereotypes
5. Player-influenced relationship dynamics (from import) reflect
   shared history in the narration

### Phase 22: Force Discovery System

**Status: NOT STARTED.**

Files: `engine/advancement.py` (extend — Force awakening milestone),
`engine/force.py` (extend — latent Force sensitivity processing)

Design: Game Mechanics §14.4 (Force sensitivity discovery).

Goal: The "Let the Force decide" posture works — hidden randomization
at session creation, Phase 2 interiority during the discovery window,
Phase 3 trigger, and the acceptance/rejection choice with persistent
latent flag across campaigns.

Dependencies: Phase 14 (Force dice — the Force system must exist for
awakening to activate it), Phase 13 (aspiration echoes — latent Force
hints use the echo infrastructure), Phase 19 (import — the latent flag
and rejection count persist across campaigns).

Success criteria:
1. A character with `latent_force_sensitive: null` resolves to true or
   false at session creation using the spine's probability
2. When true and the discovery window is open, the GM prompt receives
   Phase 2 interiority instructions
3. When the discovery trigger is met, the Force awakening milestone
   fires
4. Accepting sets Force Rating to 1 and activates Morality
5. Rejecting increments `force_rejected_count` and suppresses Force
   interiority for the campaign
6. The latent flag and rejection count persist through import into
   the next campaign
7. A recurring discovery (rejected once before) uses the intensified
   Phase 2 instructions

### Milestone 4 Success Criteria

Chain two campaign spines with one character:

1. Complete Campaign A (4 acts, including a time skip with vignettes
   between Acts 2 and 3)
2. Export the character at campaign completion
3. Import into Campaign B with a different era and context
4. The transition passage references Campaign A events
5. Specialization mappings apply correctly (at least one dormancy or
   evolution mapping)
6. NPC relationships from Campaign A appear when relevant NPCs are
   reintroduced
7. The character's advancement log spans both campaigns
8. If the character is Force-sensitive, Force powers and Morality
   carry forward

---

## Campaign Studio Track (Parallel — starts after V1)

**Status: ALL SIX PHASES COMPLETE — CS-1 through CS-4 March 2026,
CS-5 and CS-6 April 2026**

The Campaign Studio builds in parallel with the Game Engine post-V1
milestones. Its six phases are specified in Campaign Studio
Implementation Document §3.

**Coordination points:**

- **CS Phase 1 (Schema & Validation)** can start immediately after V1.
  The spine schema in `studio/schema.py` is the interface contract.
  The Game Engine already loads spines directly; once the Pydantic
  models exist, spine loading should migrate to use them.

- **CS Phase 2 (Mode 3)** can proceed in parallel with Milestones 1-2.
  Mode 3 produces spines that the Game Engine consumes. Testing Mode 3
  output requires the Game Engine to be at least at Milestone 1
  (full single-campaign experience) to validate that the produced spine
  plays well.

- **CS Phase 3 (Mode 2 + Import)** requires Game Engine Phase 18
  (cross-era import/export). The import interface is implemented in the
  Game Engine; the Campaign Studio calls it.

- **CS Phase 4 (Saga Layer + Mode 1)** is the final baseline Campaign
  Studio phase and has no Game Engine dependency beyond CS Phase 3.

- **CS Phase 5 (Narrative Quality)** adds pre-generation story
  architecture planning and Gate 4 narrative evaluation. Depends on
  CS-4 (schema and validation must be established). Produces
  `studio/architect.py`, `studio/narrative_eval.py`, and three prompt
  templates.

- **CS Phase 6 (Story Engineering Integration)** extends the
  architecture layer with structural storytelling tools. Depends on
  CS-5. Adds `engine/dramatic_mission.py` and `engine/scene_validator.py`
  (both pure Python) plus schema extensions (MilestoneBeatSheet,
  PinchPoint, ForeshadowLink, CharacterDepthCard, ProtagonistMode,
  NPC.pressure_role). Deterministic structural validation checks
  complement LLM-assisted Gate 4 evaluation.

---

## The Final Test: The Saga

When all four Game Engine milestones and all four Campaign Studio phases
are complete, the system supports the full saga concept:

1. **Campaign 1 — Smuggler Kid.** Create a character through the funnel
   (Criminal allegiance, street urchin variant, "Let the Force decide").
   Play 4 acts running with smugglers. Equipment matters, Obligation
   creates pressure, the behavioral inference engine grows the character
   from their experiences. Time skip vignettes between acts show the kid
   aging.

2. **Campaign 2 — Jedi Academy.** Import the character. The Category 5
   milestone presents the era transition. If the Force decided "yes,"
   the discovery arc plays out — latent hints, the awakening moment, the
   choice. The character trains alongside the Solo kids (canon profiles
   in the NPC roster). Force dice, Force powers, dark side temptation.
   Time skip vignettes show years at the Academy.

3. **Campaign 3 — New Jedi Order.** Import again. The character is now a
   Jedi Knight with years of history. NPC management handles 30+
   accumulated relationships. Canon character profiles evolve as the war
   changes people. The galactic context layer reflects the Yuuzhan Vong
   invasion. The player's original scenarios — defending a star system
   with a Sith army, rallying Clone Wars droids — live as authored
   anchor beats alongside canon environmental pressure.

The character's story spans 15-20 years, three eras, and hundreds of
choices. The dice were real. The growth was earned. The relationships
were built. And the story was theirs.

---

## Revision History

**v1.4 — CS-5 and CS-6 additions (April 8, 2026)**

Added Campaign Studio Phase CS-5 (Narrative Quality) and CS-6 (Story
Engineering Integration) to the Campaign Studio Track section. Both
phases COMPLETE. Updated header status to "ALL SIX PHASES COMPLETE."
Added coordination point descriptions for CS-5 and CS-6.

**v1.3 — Documentation audit corrections (March 17, 2026)**

1. **Phase 21 directory correction.** `data/canon_profiles/` was
   incorrectly described as "exists but is empty" — the directory does
   not yet exist in the repo. Corrected to "does not yet exist."

2. **No phase content changed.** All milestone definitions, phase
   ordering, success criteria, and dependencies remain as specified.

**v1.2 — Phase status annotations (March 2026)**

1. **Status annotations added to every phase and milestone.** Each
   phase now includes a status line (COMPLETE, PARTIAL, or NOT
   STARTED) reflecting the actual implementation state as of March
   2026. Milestones 0-3 are complete. Milestone 4 is partial (Phase
   17 complete, Phases 18-22 not started). All four Campaign Studio
   phases are complete.

2. **No phase content changed.** All milestone definitions, phase
   ordering, success criteria, and dependencies remain as specified.
   Only status annotations were added.

**v1.1 — Document reference updates (March 2026)**

1. **Reference document versions updated.** Implementation Document
   v1.8 → v2.5, Game Mechanics v1.5 → v1.8, Campaign Studio
   Implementation v1.2 → v1.3. Design Gap Analysis v2.0 added to
   reference list.

2. **Phase content unchanged.** All milestone definitions, phase
   ordering, success criteria, and dependencies remain as specified
   in v1.0. The design gap analysis work produced new design specs
   for items already within these phases — it did not create new
   phases or change the build sequence.

---

*Storyteller V3 — Build Roadmap v1.4*
*The path from first dice roll to the saga.*
