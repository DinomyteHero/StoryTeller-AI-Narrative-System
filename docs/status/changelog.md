# Changelog

All notable changes to Storyteller V3 are documented here.

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
  (currently authored on Shadows of the Praxeum): 6 sensory anchors,
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
`web/index.html`, `data/campaigns/shadows_of_the_praxeum.json`,
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

### Campaign repository narrowed to Shadows of the Praxeum
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
- Shadows of the Praxeum campaign

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
- **Shadows of the Praxeum** — Jedi academy campaign
- 6 talent specialization trees, 5 Force powers, 55 Writer's Room
  personas
