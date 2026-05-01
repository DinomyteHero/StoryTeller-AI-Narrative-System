# Changelog

All notable changes to Storyteller V3 are documented here.

## [Unreleased] — 2026-04-28 — Brooks/Weiland Pass II — Branching, Length, Edge

A follow-up pass extending the Brooks/Weiland framework into:
real branching paths, multiple endings, Choice-of-Games-comparable
campaign length, edgier and more original framing of the antagonist,
and four new academy students.

### Real branching + 5 endings
- **Two new variation_points** ([data/campaigns/shadows_of_the_custodian.json](data/campaigns/shadows_of_the_custodian.json)):
  - **`act3_loyalty_branch`** — load-bearing Act 3 → Act 4 branch
    with four options: `sanctuary_for_kira`, `hand_kira_to_luke`,
    `help_kira_disappear`, `join_third_path`. Each option
    rewires NPC dispositions, statuses, and the shape of Acts 4–5.
  - **`act4_assault_response`** — three-option choice at the
    Imperial assault (`stand_and_fight`, `evacuate_first`,
    `strike_first`).
- **`story_architecture.ending_paths`** — five named endings
  (The Open Door / The Third Path / The Law / The Long Road / What
  Remains) with branch_id, synopsis, selection signals, and
  `carries_forward` flag for cross-campaign import. Default ending
  is reserved for low-engagement playthroughs and explicitly costs
  the player something.

### Edgier + more original framing
- **Malakai reframed**. No longer a "surviving Inquisitor who
  weaponises truth." He is a survivor of *both* the Jedi and the
  Inquisitorius who has concluded the binary is the actual problem.
  His motivation, voice_notes, behavioral_envelope,
  thematic_argument, knows_at_start, and pressure_role all
  rewritten. New `anti_stereotype_notes` block locks out the
  cackling-Sith / brooding-fallen-Jedi / redeemable-villain
  defaults: "He may not be killed. He may not be wrong."
- **Kira reframed**. Her parent's "ghost" is canonical
  Force-ghost contact, not a metaphor. Malakai is the only person
  in her life treating it as data. Her "betrayal" is, from her
  view, a research alliance.
- **Tone directive added** to era_voice — campaign is permitted
  and encouraged to be edgier than typical Praxeum fiction. People
  the protagonist loves can die. The academy can fall. The
  antagonist's argument must be hard to refute. No clean ending.

### Choice-of-Games-comparable length
- **Per-act `expected_turns` bumped**: Act 1 [22, 28], Act 2
  [16, 22], Act 3 [20, 26], Act 4 [20, 26], Act 5 [16, 22].
  Total target band: **94–124 turns per playthrough** (was 48–68).
  Lands in the Hosted-Games range without bloating to
  full-Tally-Ho 500K word counts.
- **+25 new side-content seeds** spanning all five acts —
  morning runs with Loka Hask, kitchen duty with Kira, Iila Vand
  teaching the protagonist a Cilghal breath exercise, Mira Vex's
  field kitchen on the eve of battle, Kyp Durron's promise of
  companionship one year from now, Iila's "are you going to come
  back" pre-battle question, Loka's Wookiee thank-you. Total
  side-content: 71 seeds across 5 acts.

### Four new academy students
- **Dorsk 81** — canon Khommite clone, identity-themed mirror.
  His arc is "I am the eighty-first identical copy and I will be
  the first to be different."
- **Octa Ramis** — canon Chandrilan archive-focused friend.
  Methodical, dry, generous with what she knows. Tactile thinker.
- **Mira Vex** — original Twi'lek slaver-survivor. Loud, kind,
  refuses to be defined by the worst thing that happened. Living
  counterpoint to Clovis: came from worse, chose transparency.
- **Brann Riako** — original ex-Imperial-cadet defector. Quiet,
  careful, unobtrusively decent. His past is a fact, not a
  scandal. Treats his Imperial training as a competence that
  surprises him, not a shadow.

Each student carries full `voice_notes`, `behavioral_envelope`,
`knows_at_start`, `doesnt_know_at_start`, `per_act_state`,
`thematic_argument`, `pressure_role`, and `anti_stereotype_notes`.

### Anti-stereotype notes added to all new canon NPCs
Eleven NPCs now carry `anti_stereotype_notes` that explicitly
lock out the LLM's default interpretations — Brakiss (not the
obvious-villain), Cilghal (not the wise-fish-mystic), Streen (not
the dotty-old-hermit), Kyp Durron (not the angsty-emo-redeemed-
villain), Kam Solusar (not the brooding-haunted-redeemer), Talon
Karrde (not the lovable-rogue), Iila Vand (not the cute-
precocious-orphan), Sergeant Vex (not the redemption-arc-
Imperial-officer), Loka Hask (not the noble-savage-Wookiee),
Dorsk 81 (not the comic-relief-naive-clone), Octa Ramis (not the
bookish-nerd).

### Per-choice arc alignment
- **`annotate_choice` extended** to receive a `narrative_arc_block`
  parameter and classify each chosen option as `lie | truth |
  neutral` against the protagonist's arc.
- **`ANNOTATION_SCHEMA` extended** with `arc_alignment` (enum)
  and `arc_evidence` fields.
- **Annotation prompt rewritten** to instruct the model on how to
  read for lie-defence vs truth-risking texture.
- **`_run_annotation_background`** now passes
  `build_narrative_arc_block(character)` through. The annotation
  result lands in the `choice_implications` column on the turn
  row, so arc honoring becomes queryable end-to-end.

### Studio narrative_arc support
- **`NarrativeArcSpec`** model added to [studio/schema.py](studio/schema.py).
  Optional field on `CharacterVariant`. Carries lie / ghost /
  truth / want / need / arc_type / lie_grip_initial.
- **Gate 4 arc-coherence checks** added to
  [studio/narrative_eval.py](studio/narrative_eval.py) —
  validates that populated arcs have lie + ghost + truth, that
  the ghost is concrete enough (≥ 60 chars) to land in prose,
  that arc_type is valid, and that lie_grip_initial aligns with
  the arc_type's expected starting range.
- **Mode 1 generation prompt updated** ([studio/prompts/mode1_generate.txt](studio/prompts/mode1_generate.txt))
  to require `narrative_arc` on every variant, with an
  authoring note that the truth must directly negate the lie
  (not be a parallel platitude) and that the ghost must
  plausibly cause the lie.

### Front-end character creation funnel
- **Campaign cards** now expose the dramatic premise, central
  question, and antagonistic force in an expandable "What this
  story is about" section.
- **Character cards** now surface the Brooks/Weiland inner
  story — "What they believe (wrongly):", "The wound behind it:",
  "What they want:", "What they need:" — so the player picks a
  character understanding the inner story they are signing up
  for, not just species + career.
- **`renderSessionIntro`** displays a "YOU ARE ABOUT TO PLAY"
  card before the opening narration on turn 1 with the campaign
  premise, central question, and the chosen character's full
  arc. The card stays visible alongside the opening passage.

### Files touched (10 files, ~+800 net new lines)
- [data/campaigns/shadows_of_the_custodian.json](data/campaigns/shadows_of_the_custodian.json)
  (4 new students, expected_turns bumped, 25 new side-content
  seeds, 2 new variation_points, 5-ending architecture, Malakai
  + Kira reframed, anti-stereotype notes on 11 NPCs, edgy tone
  directive)
- [gm/local_gm.py](gm/local_gm.py) (arc_alignment in schema +
  validator)
- [gm/prompts/choice_annotation.txt](gm/prompts/choice_annotation.txt)
  (arc_alignment field + narrative_arc_block placeholder)
- [api/game_routes.py](api/game_routes.py) (annotation call site
  passes narrative_arc_block; build_narrative_arc_block import)
- [studio/schema.py](studio/schema.py) (NarrativeArcSpec model
  + CharacterVariant.narrative_arc field)
- [studio/narrative_eval.py](studio/narrative_eval.py) (Gate 4
  arc coherence check)
- [studio/prompts/mode1_generate.txt](studio/prompts/mode1_generate.txt)
  (narrative_arc required field with authoring guidance)
- [web/index.html](web/index.html) (campaign + character cards
  expose architecture and arc; renderSessionIntro for the "you
  are about to play" pre-turn card)
- [docs/status/changelog.md](docs/status/changelog.md) (this entry)

### Test impact
- 121 pass on the focused regression suite
  (CS-5/6 runtime + story engineering + schema + e2e).
- Schema parses cleanly with all new NPC + faction + variation
  point + ending_paths additions.

---

## [Unreleased] — 2026-04-28 — Brooks/Weiland Framework Pass

A focused pass that gives the engine the *named* vocabulary the
narration model expects when honoring story structure (Larry Brooks)
and character arc (K.M. Weiland), and rebuilds *Shadows of the Custodian*
around it.

### Schema
- **`NarrativeArc` model** added to `engine/character.py` — `lie`,
  `ghost`, `truth`, `want`, `need`, `arc_type` (positive | flat |
  disillusionment | fall | corruption), `lie_grip` (0.0–1.0), and
  per-turn `movements` ledger. Optional; existing characters
  without it render identically.

### Runtime surfaces
- **`build_narrative_arc_block`** in `gm/context.py` renders the
  inner story as a GM-only block in the narration prompt with a
  lie-grip label (iron / loosening / cracking / broken) and arc-type-
  specific guidance. New `{narrative_arc_block}` placeholder added
  to both narration prompts.
- **`build_beat_role_block`** in `gm/context.py` reads the active
  act's `dramatic_function` + `protagonist_mode` + `act_progress`
  and writes a Brooks beat cue ("PART 1 — SETUP. The world is still
  recognizable…"; "ACT IS ENDING…"). New `{beat_role_block}`
  placeholder under STORY POSITION in both prompts.

### Lie-grip tracking
- **`accumulate_contradiction_arc`** now also takes the protagonist
  and nudges `narrative_arc.lie_grip` per turn from the same
  `contradiction_tracking` movement that drives the contradiction-arc
  ledger. Deltas: reinforced +0.05, cost_paid +0.02, resisted −0.05,
  transformed −0.10. 16-entry rolling movements ledger with turn,
  kind, delta, new grip, evidence note.
- **Fast-path contradiction tracking** added to `_fast_reconciliation_result`
  in `api/game_routes.py` — keyword-based heuristic that fires
  when `RECONCILIATION_INLINE` is off (the default), so lie_grip
  moves at default settings without per-turn LLM calls. The
  slow LLM reconciler remains the calibrated path when enabled.

### Choice-level pressure cue
- Both narration prompts now carry a "LIE / TRUTH PRESSURE" block:
  when `narrative_arc_block` is present, at least one choice each
  turn should defend the Lie and at least one should risk the Truth.
  Choices are never *labeled* — the texture does the work.

### Reconciliation engagement
- The CS-6 contradiction-tracking instruction was rewritten to
  default toward flagging micro-engagement. A routine setup-act
  turn where the protagonist hides / withholds / holds back is now
  `reinforced` rather than `none`. Setup stretches accumulate
  movements rather than sit flat.

### Character creation funnel
- **`GET /campaigns`** enriched: returns `dramatic_premise`,
  `central_dramatic_question`, `story_promise`,
  `protagonist_pressure_type`, `antagonistic_force`, `era_year`,
  and per-character `narrative_arc` summaries.
- **`GET /characters`** new endpoint: returns every character
  file with name, species, career, background excerpt, voice
  notes, throughline question, and full narrative arc.
- **`POST /session`** response now carries a `session_intro`
  block (campaign architecture + character arc surface) so the
  opening UI can show a "you are about to play…" card before turn 1.
- **`GET /session/{id}`** now returns the full character object,
  exposing live `lie_grip` and movements ledger to harness/frontend.

### Campaign deep-edit — *Shadows of the Custodian*
Pinned to **~12 ABY**, one year after the Exar Kun crisis is
canonically resolved. Substantive content additions:
- **9 new NPCs** (was 5; now 14): Kam Solusar, Cilghal, Streen,
  Kyp Durron, Brakiss (Imperial mole — co-antagonist), Loka Hask,
  Iila Vand (innocent stake), Sergeant Daro Vex, Talon Karrde
  (offscreen). All with proper `voice_notes`,
  `behavioral_envelope`, `knows_at_start`, `doesnt_know_at_start`,
  `per_act_state`, `pressure_role`, and `thematic_argument`.
- **3 new factions**: The Glass Wake, Imperial Intelligence
  Remnant, Exar Kun Residue.
- **9 new side-content seeds** spanning Acts 1–5 (Kyp's resistance
  meditation offer, Iila's gift, Streen's tower-stair warning,
  perimeter walk with Vex, Glass Wake encrypted job, archive
  sealed crate, Brakiss's late-night practice, Cilghal's medical
  evaluation, Karrde's information offer, Streen leaving the
  tower, Iila's pre-battle question).
- **Sharpened opening** — Act 1 now opens *in medias res* with
  Kira's first on-screen absence at morning meditation; the
  mystery begins as a missed lesson, not a slow build.
- **Per-act `beat_roles`** explicit (`["setup", "inciting"]`,
  `["response", "first_plot_point"]`, `["midpoint", "pinch1"]`,
  `["attack", "pinch2", "second_plot_point"]`,
  `["climax", "resolution"]`).
- **Lore seed enrichments** for the post-Exar-Kun feel
  (sealed-stairway draft, salt-iron taste after meditation,
  twelve-second silence at the start of the noon meal, Kyp Durron's
  evening loop, Luke's scorched Massassi-stone fragment, Tionne's
  sealed crate, Streen's whittled wood that never finishes).

### Inner story populated
Each of the three character files now carries a hand-authored
`narrative_arc` block with `lie`, `ghost`, `truth`, `want`,
`need`, `arc_type=positive`, and a starting `lie_grip` (Clovis
0.9, Praxeum Student 0.85, Praxeum Mechanic 0.88).

### Playtest
- 30 cloud turns as Clovis Beryl: 0 errors, reached Act 3 @ 50%,
  57 threads, 11 unique memorable moments, 13 side-content engaged
  (3 of them new entries). Median latency 15.9 s, max 25.0 s.
- A 15-turn validation pass with the fast-path contradiction
  heuristic loaded confirms `lie_grip` moves with player choices
  (see `docs/research/brooks-weiland-pass-2026-04.md`).

### Test impact
- 210 pass + 11 cleanly skip on the focused suite.
- 2 pre-existing destiny-narrative-note ASCII em-dash failures
  unrelated to this pass.
- 1 brittle `test_shadows_of_praxeum_loads` assertion relaxed
  from `== 5 NPCs` to `>= 5 NPCs` so future enrichment doesn't
  break it.

### Files touched (15 files, ~+550 net new lines + spine enrichment)
`engine/character.py`, `gm/context.py`, `gm/cloud_gm.py`,
`gm/prompts/narration.txt`, `gm/prompts/narration_literary.txt`,
`engine/reconciliation.py`, `api/game_routes.py`,
`data/characters/clovis_beryl.json`,
`data/characters/praxeum_student.json`,
`data/characters/praxeum_mechanic.json`,
`data/campaigns/shadows_of_the_custodian.json`,
`eval/playtest_long.py`,
`tests/test_cs6_story_engineering.py`,
`docs/research/brooks-weiland-pass-2026-04.md`,
`docs/status/changelog.md`.

---

## [Unreleased] — 2026-04-26 — Depth & Enjoyment Pass

A six-phase pass that addresses the deepest gaps in player-felt experience
identified by the gameplay audit (April 2026). The audit found that the
engine tracked rich state — disposition, threads, morality, talents,
equipment narrative notes — but the player rarely *felt* any of it. The
LLM either didn't see the right slice, wasn't told to honor it, or only
surfaced it at act boundaries. Fix lands across context assembly,
prompts, scene grammar, character identity, and campaign data.

### Phase A — activate what's already built
- **Choice quality validator on by default.** `CHOICE_QUALITY_INLINE`
  default flipped from `false` to `true` in `gm/cloud_gm.py`. Validator
  was fully implemented but disabled — choice sets weak on
  specificity/identity/risk/grounding now hit a one-attempt repair loop.
- **CS-6 closure heartbeat wired.** `compute_closure_heartbeat_instruction`
  in `gm/context.py` reads `arc_state.turns_since_last_thread_change`
  and produces a "threads must move" prompt when the silence runs past
  4 turns. Counter incremented/reset by `_post_reconciliation_cs6_hook`.
- **CS-6 foreshadow setup/payoff wired.** `compute_foreshadow_instruction`
  walks `spine.foreshadow_registry` for the active act, prefers payoff
  over setup, marks delivered links in `arc_state.foreshadow_setups_delivered`
  / `foreshadow_payoffs_delivered`. Audit gap closed.
- **CS-6 contradiction arc accumulation wired.** `accumulate_contradiction_arc`
  + `build_contradiction_arc_block` build a per-act ledger from
  reconciliation's per-turn `contradiction_tracking` records. Dominant
  movement (reinforced / resisted / transformed / cost_paid) surfaces in
  the narration prompt. Audit gap closed.
- **Destiny spending surfaced to player.** Light- and dark-Destiny
  `narrative_note` strings in `engine/destiny.py` upgraded from advisory
  to "REQUIRED BEAT — exactly one sentence of interior recognition."
  API turn response now carries a `destiny: { light_spent, dark_spent,
  light_remaining, dark_remaining }` object; frontend renders pill badges
  on the dice panel.

### Phase B — narrative memory and coherence
- **Memorable moments ledger.** New `MemorableMoment` dataclass and
  `register_memorable_moment` / `select_callback_candidates` /
  `mark_callback_surfaced` / `build_memorable_moments_block` helpers in
  `gm/context.py`. `_flag_memorable_moments` in `api/game_routes.py`
  auto-flags from Triumph, Despair, NPC disposition shifts ≥ 0.15,
  thread resolutions, reputation events, motivation activations,
  force-temptation acceptance, and milestone firing. 0–2 candidates
  surface in narration each turn (suppressed in combat/chase). 4-turn
  cooldown per moment + weight-aware eviction at a 25-moment cap.
  `arc_state.memorable_moments` persists the ledger.
- **Callback instruction added to narration prompts.** New
  `{memorable_moments_block}` placeholder in `narration.txt` and
  `narration_literary.txt`, plus a "narrative coherence contract" that
  tells the LLM how to honor NPC crystallized memory and the new
  thread status labels. Weave at most one moment as resonance, never
  as exposition.
- **Multi-stage thread state.** `ThreadState` promoted from binary
  open/closed to a six-stage status model: `dormant`, `active`, `hot`,
  `approaching_resolution`, `resolved_pending_fallout`, `closed`.
  Each thread carries `progress` (0.0–1.0), `hot_question`,
  `last_movement_turn`, `fallout_remaining_turns`. `apply_thread_updates`
  in `engine/reconciliation.py` advances status on each
  advance/resolve/open and applies per-turn decay (`hot → active`,
  `active → dormant`, `resolved_pending_fallout → closed` on countdown).
  `_thread_states_for_context` in `api/game_routes.py` merges the rich
  state when building the prompt; resolved-with-fallout threads stay
  visible so consequences ripple. New `thread_state` map persisted on
  `arc_state`.
- **Slowed emotion decay for high-stakes moods + crystallized memory.**
  `MOOD_DECAY_RATES` in `gm/context.py` rebalanced: `angry` 0.15 → 0.06,
  `afraid` 0.10 → 0.05, `grieving` 0.05 → 0.03, `suspicious` 0.08 → 0.04,
  others tuned. New `betrayed` (0.02), `awed` (0.04), `bonded` (0.03)
  moods. `HIGH_INTENSITY_DECAY_MULT = 0.5` halves decay further when an
  emotion is set ≥ 0.6 intensity. `NPCState.crystallized_memory` field
  + `crystallize_memory` method imprint a single non-decaying impression
  per NPC; rendered in `to_prompt_block` as "Sharpest memory of
  protagonist."

### Phase C — identity becomes voice
- **Evolved voice block.** New `build_evolved_voice_block` in
  `gm/context.py` overlays dynamic deltas on the static `voice_notes`:
  morality band (Force-sensitive only), accumulated Conflict, wounds /
  strain ratio, recent talent acquisitions, active injuries. New
  `{evolved_voice_block}` placeholder in both narration prompts.
- **Growth recognition (Step 13 of between-act pipeline activated).**
  Was stubbed (`growth_passage_stub`); now `build_growth_recognition`
  in `engine/advancement.py` composes a one-shot interior recognition
  from the behavioral fingerprint + skill advancement. Stored on
  `arc_state.pending_growth_recognition`, surfaced via
  `{growth_recognition_block}` in the next act's first turn, then
  cleared by `_post_narration_drift_hook`.
- **Background activation.** New `build_background_block` in `gm/context.py`
  surfaces the previously dormant `Character.background` field as
  living context. Praxeum Student and Praxeum Mechanic backgrounds
  populated with full evocative prose (recurring dreams, signature
  gestures, lost relationships, sensory anchors).
- **Items of meaning.** `build_equipment_narration_block` in
  `engine/equipment.py` extended with an "items of meaning" handling
  instruction: any item carrying a `narrative_note` should color
  posture and silence when touched/drawn/used; never quoted back to
  the player.
- **Milestone scenes (acknowledgment beat required).** Updated
  `gm/prompts/milestone_reflection.txt` to require an acknowledgment
  beat — an NPC notices the change, an object/place/ritual mirrors
  it, or the protagonist catches their own reflection. Milestones
  become character moments instead of stat-pickers.

### Phase D — scene grammar differentiation
- **Tactical state infrastructure.** New `tactical_state` block
  on `arc_state` with three sub-grammars:
  - **Combat:** `round`, `range_band` (engaged / short / medium /
    long / extreme), `cover`, `suppressed`. Range band shifts on
    intent keywords (close/charge/retreat). Cover and suppression
    update on dice outcome.
  - **Negotiation:** 5-stage progression (`opening` → `probing` →
    `pressure` → `give_or_break` → `concluded`), `walk_away_pressure`
    that rises on harsh failures, lists of `positions_yielded`,
    `positions_held`, `shared_ground`.
  - **Chase:** 5-zone distance bands (`sighted` → `closing` →
    `neck_and_neck` → `breaking_clear` → `lost_or_caught`),
    `environment_hazards`, `split_attempts`.
  - `initialize_tactical_state` / `advance_tactical_state` /
    `build_tactical_state_block` in `gm/context.py`. Lifecycle
    managed in `_compute_dynamic_context_fields`: initialized when
    entering a tactical scene type, advanced post-turn by
    `_post_turn_world_state_hook`, cleared when scene type leaves.
  - New `{tactical_state_block}` placeholder in both narration prompts.
- **Free-form player input.** `TurnRequest` extended with
  `free_form_action: Optional[str]`. When non-empty (with `choice_index = -1`),
  the turn handler routes the typed text through the local check-decision
  model so the system picks an appropriate skill and difficulty.
  Frontend gained a collapsible "Speak or act in your own words"
  panel below the choice buttons with `Ctrl+Enter` submit and a
  600-character cap. Closes the longest-standing player-agency gap.

### Phase E — reactive world
- **NPC counter-move cue.** `_build_npc_counter_move_block` in
  `api/game_routes.py` picks the most-pressuring scene NPC (lowest
  disposition, strongest active emotion, hostile pressure_role) and
  produces a one-line GM cue: escalate / test / withhold / press /
  offer-shortcut, with the NPC's crystallized memory color when set.
  NPCs become proactive instead of purely reactive.
- **Emergent faction reactivity.** `_build_faction_reactivity_block` +
  `_post_turn_world_state_hook` derive faction `delta` from player
  action keywords against `faction.trigger_keywords` and `alignment`,
  on top of authored per-act drift. Surfaced as a "tightening /
  easing" cue per faction. Cap ±0.5.
- **Hard pivot points.** New `act.pivot_points` schema —
  `id`, `description`, `target_progress`, `locks_off`. When fired,
  `_build_pivot_warning_block` tells the LLM to make the choices feel
  like real alternatives and let the consequences land in the prose.
- **Side content scaffold.** New `act.side_content` schema —
  `id`, `title`, `hook`, `keywords`. `_build_side_content_block`
  surfaces an unengaged item as an offer-to-the-LLM; the LLM may
  plant the hook if a natural opening arrives. `side_content_engaged`
  tracking matches title or keywords against the player action.

### Phase F — backstory deepening
- **Lore seeds block.** `lore_seeds` added to `CampaignSpine`
  (currently authored on Shadows of the Custodian): 6 sensory anchors,
  4 rituals, 5 significant objects, 4 language conventions. Surfaced
  via `build_lore_seeds_block` + `{lore_seeds_block}` placeholder.
  Verified in playtest — opening passages now thread 5+ lore seeds
  naturally per scene without prompting.
- **Faction extensions.** Each faction in Shadows now carries
  `name`, `alignment` (`friendly` / `hostile` / `neutral`), and
  `trigger_keywords` for emergent reactivity matching.
- **Side content + pivot points seeded.** Acts 1, 2, and 3 of
  Shadows gained 1–2 side content entries each (Tionne archive
  evening, perimeter lantern repair, sealed-stairs meditation,
  freighter-transponder intercept). Act 3 gained a pivot point
  (`act3_kira_disclosure_pivot`).
- **Deepened character backgrounds.** `data/characters/praxeum_student.json`
  background populated with the Mirialan home, the Bothan recruiter
  Soriya, the recurring flooded-temple dream, the prayer beads as a
  living object. `praxeum_mechanic.json` background populated with
  Iridonia → Tatooine chop shop, the father lost in a deal gone
  wrong, the Mon Cala carrier service, the unfired Imperial blaster,
  the Iridonian work-songs as a fear tell.

### Frontend additions
- Free-form input panel added to `web/index.html` with collapsible
  details/summary, Ctrl+Enter submit, 600-character cap, and a hint
  line.
- Destiny indicator pills (Light / Dark) added to the dice panel
  when `destiny.light_spent` or `destiny.dark_spent` is true on the
  turn response.
- New CSS sections for both above.

### Bug fixes (caught during self-playtest)
- `scene_npcs` vs `scene_npcs_t` / `scene_npcs_iv` / `scene_npcs_s`
  variable-name mismatch in three of four turn handlers' new
  post-turn hooks (caused 500 on the temptation, intervention, and
  streaming paths).
- `session.get("destiny_light", 0)` — `session` is a `sqlite3.Row`,
  not a dict. Switched to bracket access.

### Self-playtest results
- 10 turns played as Praxeum Student through Act 1 — reached act
  boundary on turn 10.
- Mixed canned choices (7/10) and free-form input (3/10).
- Final state: 23 threads tracked with rich status, 2 memorable
  moments captured (1 callback already surfaced), 2 foreshadow
  setups delivered, 1 side content engaged, negotiation-grammar
  tactical state activated and cleared correctly across scene-type
  shifts.
- Opening passage threaded 5+ lore seeds and the protagonist
  background into the prose without prompting (chime tuning, the
  Whyren-fliers, jungle rot + ozone, the prayer beads gesture, the
  cracked obsidian disc, "May the Force breathe").

### Test impact
- 210 pass + 11 cleanly skip on the focused suite (CS-6 runtime,
  story engineering, talents, force, time skips, dice validation).
- 2 pre-existing failures in `tests/dice_validation.py` reference
  the removed Keth/Nar-Shaddaa spine — confirmed pre-existing on
  `main`, not regressions from this work. Worth skipping in a
  cleanup follow-up.

### Files touched
15 files, +2,264 / −79 lines:
`api/game_routes.py`, `engine/advancement.py`, `engine/destiny.py`,
`engine/equipment.py`, `engine/reconciliation.py`, `gm/cloud_gm.py`,
`gm/context.py`, `gm/prompts/milestone_reflection.txt`,
`gm/prompts/narration.txt`, `gm/prompts/narration_literary.txt`,
`web/index.html`, `data/campaigns/shadows_of_the_custodian.json`,
`data/characters/praxeum_student.json`,
`data/characters/praxeum_mechanic.json`, `.env.example`.

---

## [Unreleased] — 2026-04-25

### Audit-finding closures (architecture pivot follow-up)

- **Opening-route era_voice gap closed.** `POST /session` was constructing
  the very first `ContextPackage` without calling `_compute_dynamic_context_fields`,
  so the opening narration of every campaign lost its `era_voice_block`
  (period anchoring) and ran with empty defaults. Fixed at
  `api/game_routes.py:608`.
- **Selective reconciliation escalation.** New `reconcile_turn_with_escalation`
  in `engine/reconciliation.py` plus an `is_silent_reconciliation` predicate.
  When the fast tier returns no NPC updates, no thread movement, and no
  reputation event for two consecutive turns, the engine reruns through the
  quality tier and emits a `reconciliation_escalated` telemetry event. The
  quality result wins if it found anything; otherwise the streak counter
  resets. Wired at all 4 turn-handler ContextPackage construction sites.
- **Identity drift surfacing policy.** New `compute_identity_drift_cue` and
  `update_drift_baseline` helpers in `gm/context.py`. Tracks morality /
  conflict / motivation-activation deltas against a per-session baseline
  and surfaces a one-line interior cue when thresholds are crossed
  (5-point morality, 3-point conflict, or fresh obligation/duty activation).
  5-turn cooldown to keep cues sparse. New `{identity_drift_block}`
  placeholder in `narration.txt` + `narration_literary.txt`.
- **Introspection trigger logic.** New `compute_introspection_trigger`
  in `gm/context.py`. Three explicit conditions: post-Despair, post-pinch
  point, mid-act dry spell. Replaces the implicit-in-prompts behavior with
  testable signal logic. New `{introspection_trigger_block}` placeholder
  in narration prompts. Wired through the four turn handlers' new
  `_post_narration_drift_hook`.
- **Path differentiation audit (backlog 3.33 / 3.34).** Added eight
  pure-Python checks to `studio/validate.py`:
  - **Gate 1 (3.33):** integration layer completeness, NPC override
    validity (must reference roster), anchor adaptation coverage,
    entry point distinctness (Jaccard < 0.7), personal stakes
    non-genericity (heuristic phrase blocklist).
  - **Gate 3 (3.34):** allegiance NPC override diversity, anchor
    adaptation similarity (Jaccard < 0.65), entry point structural
    difference (Jaccard < 0.55).
  - Helper `_jaccard_token_similarity` with stopword filtering.
- **CS-6 runtime wiring (newly discovered gap).** During the audit pass we
  found that several CS-6 features were documented as "complete" but had
  unit tests only — they were never invoked from the live turn loop in
  `api/game_routes.py`. Wired now:
  - **Pinch point firing** (`compute_pinch_point_instruction`) — every
    turn checks the act's `pinch_point` config against current progress
    and fires once per act when the target threshold is reached. Reset
    on act boundary in `run_between_act_pipeline`.
  - **Depth card block** (`build_depth_card_block`) — looks up the
    active variant's `CharacterDepthCard` from the spine and renders
    GM-only enrichment (inner demon, secret yearning, social mask, etc.)
    into the narration prompt.
  - **Voice mode mapping** (`compute_voice_mode_instruction`) — captures
    the previous turn's `dramatic_mission.selected_mission` from the
    reconciliation result, maps it through `MISSION_TO_VOICE` to a voice
    mode, and injects the corresponding `VOICE_INSTRUCTIONS` snippet
    into the next turn's narration prompt.
  - Session creation now persists `variant_id` in `arc_state` so later
    turns can resolve the active character variant.
  - Per-act state resets (`pinch_point_fired`, consecutive-zero counters)
    added to the between-act pipeline.
- **Test coverage.** 51 new tests across four files
  (`test_reconciliation_escalation.py`, `test_identity_drift_introspection.py`,
  `test_path_differentiation_audit.py`, `test_cs6_runtime_wiring.py`).
  Total: 704 pass + 12 skip + 0 fail.

### Still deferred (CS-6 wiring, partial)

The same audit found three CS-6 features that remain unwired into the
turn loop and are NOT included in this pass — each requires more design
work than a quick wrap:
- **Closure heartbeat** (`check_closure_heartbeat`) — needs accurate
  per-thread last-change tracking, which the current arc_state doesn't
  carry per-thread.
- **Foreshadow setup/payoff tracking** (`ForeshadowLink`) — requires a
  setup-delivery detector and a payoff trigger, both of which need
  spine-side authoring and runtime state.
- **Contradiction arc accumulation** — reconciliation already returns
  the per-turn signal (`contradiction_tracking`), but no runtime code
  accumulates it into a turn-to-turn `contradiction_arc_block` for the
  GM. Needs a multi-turn aggregator.
- **Doc sync.** `state-matrix.md` v1.6 → v1.7 with new Infrastructure
  section, reputation/behavioral/era-voice rows updated to ✓ Built,
  selective-escalation row added. `architecture-pivot.md` test count
  corrected to actual numbers.

### Architecture pivot — Local-first → DeepSeek V4
- Unified LLM client (`gm/llm_client.py`) with two-tier routing (fast/quality)
  and OpenRouter as the primary provider. DeepSeek V4 Flash is the default
  fast tier; DeepSeek V4 Pro is the default quality tier. Ollama remains as
  an optional offline path.
- Provider/model capability layer encodes reasoning syntax differences
  (OpenAI `reasoning_effort` vs OpenRouter `extra_body.reasoning`).
  OpenRouter `require_parameters: true` and `data_collection: deny`
  enforced by default.
- Strict `json_schema` response_format for studio JSON calls, with
  automatic fallback to `json_object` if a provider rejects it.
- `/health` endpoint surfaces the active routing config.

### Reputation echo, behavioral availability, era voice — wired end-to-end
- Reputation echo system fully wired: reconciliation captures
  `reputation_event` + `faction_tags`, the engine writes to
  `reputation_log`, eligible entries surface in narration with a 3-turn
  cooldown.
- Behavioral availability signal derived from Phase 13 annotation history
  injects choice-weighting guidance into narration.
- `EraVoice` schema field added to `CampaignSpine`; the active campaign
  populates it with New Republic / Praxeum-era anchoring.

### Campaign repository narrowed to Shadows of the Custodian
- Deleted: `data/campaigns/nar_shaddaa_job.json`,
  `data/campaigns/echoes_of_the_force.json`,
  `data/characters/keth_varso.json`, `data/characters/talia_ren.json`.
- Materialized: `data/characters/praxeum_student.json` and
  `praxeum_mechanic.json` from the Praxeum spine variants so existing
  test fixtures still load a standalone character file.
- Tests, eval scenarios, and docs updated to reference the canonical
  Praxeum campaign. Tests that exercised Nar-Shaddaa-specific
  features (time skip vignettes) now skip cleanly when the active
  campaign doesn't carry that data — the engine-level behavior is
  still covered by synthetic-fixture tests.

## [0.1.0] — 2026-04-08

Initial public version. All Game Engine milestones 0-3 complete,
Campaign Studio CS-1 through CS-6 complete.

### Game Engine — V1 Core (Phases 1-6)

- **Phase 1:** FFG dice system with all 7 die types, character model
  (Pydantic, 33 skills), 6-stage pool construction pipeline
- **Phase 2:** Local GM via Ollama — structured JSON check decisions
- **Phase 3:** Cloud GM — prose narration (250-800 words), 2-4
  choices, NPC state cards, context package assembly
- **Phase 4:** SQLite persistence with WAL mode, turn logging,
  episodic memory compression
- **Phase 5:** FastAPI routes — session creation, turn handling,
  SSE streaming
- **Phase 6:** Single-file HTML prose reader UI

### Game Engine — Milestone 1: Full Campaign (Phases 7-13)

- **Phase 7:** Post-turn reconciliation, act boundary detection,
  pacing arc system
- **Phase 8:** Motivation tracks (Obligation, Duty, Morality) with
  trigger systems and between-act processing
- **Phase 8.5:** NPC emotional state system
- **Phase 9:** Equipment and loadout system (weapons, armor, tools)
- **Phase 10:** XP earning and behavioral inference engine
- **Phase 11:** Talent tree engine (5-type taxonomy, 6 specializations)
- **Phase 11.5:** Destiny Point pool (light/dark spending)
- **Phase 12:** Milestone reflections and talent acquisition
- **Phase 13:** Semantic memory, choice annotation, prose diagnostics

### Game Engine — Milestone 2: Force (Phases 14-15.5)

- **Phase 14:** Force dice resolution, dark side temptation,
  conflict tracking
- **Phase 15:** Force powers (enhance, heal/harm, influence, move,
  sense) with narrative-tagged choices
- **Phase 15.5:** Force and Destiny specialization trees

### Game Engine — Milestone 3: Vehicles (Phase 16)

- **Phase 16:** Vehicle and starship encounter system

### Game Engine — Milestone 4 Partial (Phase 17)

- **Phase 17:** Time skip vignettes (authored between-era scenes)

### Campaign Studio — CS-1 through CS-4 (March 2026)

- **CS-1:** Pydantic spine schema, 4-gate validation suite
  (schema contract, NPC coherence, relationship network, narrative
  consistency)
- **CS-2:** Mode 3 collaborative authoring, NPC voice generation,
  deterministic seeding, difficulty calibration, studio API routes
- **CS-3:** Mode 2 thematic steering, cross-era character import
  interface
- **CS-4:** 5-stage saga pipeline (Writer's Room), Mode 1 autonomous
  generation, 55-persona pool across 11 clusters

### Campaign Studio — CS-5: Narrative Quality (April 2026)

- Pre-generation story architecture planning (`studio/architect.py`)
- Gate 4 narrative evaluation: coherence, dramatic quality,
  anti-genericity (`studio/narrative_eval.py`)
- Narrative quality scoring (0.0-1.0 normalized)
- StoryArchitecture schema model with five pressure types
- Anti-default rules preventing generic "hero vs villain" architectures

### Campaign Studio — CS-6: Story Engineering (April 2026)

- Dramatic mission classification with 14 mission types across
  Brooks's four-part model (`engine/dramatic_mission.py`)
- Scene purpose validation with 5-dimension scoring
  (`engine/scene_validator.py`)
- MilestoneBeatSheet, PinchPoint, ForeshadowLink, CharacterDepthCard,
  ProtagonistMode schema models
- NPC pressure roles (9 types)
- Deterministic structural validation checks
- Voice mode prose guidance system
- Shadows of the Custodian campaign

### Quality and Evaluation (April 2026)

- Narrative telemetry event system (`state/telemetry.py`)
- Evaluation harness with golden scenarios and automated policies
- Quality metrics (Tier 1 heuristic + Tier 2 LLM-assisted)
- Cross-session divergence analysis
- Prose voice evaluation benchmarking

### Documentation (March-April 2026)

- 15 active documentation files across four tiers
- 6 archived reference documents
- Four-tier document architecture with authority resolution rules
- Comprehensive project guide and state matrix

### Content

- **The Nar Shaddaa Job** — smuggler campaign (Keth Varso)
- **Echoes of the Force** — Force-sensitive campaign (Talia Ren)
- **Shadows of the Custodian** — Jedi academy campaign
- 6 talent specialization trees, 5 Force powers, 55 Writer's Room
  personas
