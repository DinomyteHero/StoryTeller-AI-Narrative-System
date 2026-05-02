# Storyteller V3 — Runtime Experience Redesign

> **SPECIALIST SPEC** — Companion to
> `character-creation-redesign.md`. Specifies all the
> *non-character-creation* changes needed to make the runtime
> experience fun, exciting, and easy to read. Aligns the system
> with Choice of Games / Heroes Rise patterns where they fit, while
> keeping our LLM-driven advantages.
>
> **Build phase:** Phase 25 (proposed; layered on top of Phase 24
> character creation work). Most slices are independently shippable.
> **Core design authority:** Game Mechanics §1-26.
> **Implementation Status: COMPLETE (May 2026)**

**Version:** 1.0
**Date:** 2026-05-01
**Originating analysis:** comparative review of *Eternal* (EndMaster)
and *Heroes Rise: The Prodigy* (Choice of Games) against Storyteller V3.

---

## 0. Why this exists

The character creation redesign in
`character-creation-redesign.md`
fixes the front of the experience. It doesn't fix the *middle* — the
hours of play between prologue and finale where the player needs to
keep wanting to click the next choice.

This spec catalogues the runtime-experience changes that the
comparative review identified as the gap between us and the
reference systems we want to emulate. It is organized around two
goals:

1. **Fun and exciting.** The system should produce the sensation that
   the player's choices genuinely matter, that surprises are
   coming, and that the character is becoming someone real.
2. **Easy to read and comprehend.** The player should never wonder
   what they are supposed to do next, who the people on screen are,
   what their character can do, or what just happened.

Goal 1 is about *engagement* — what makes the next click compelling.
Goal 2 is about *legibility* — what makes the experience usable. The
two reinforce each other: a legible system is a fun system, because
players who understand what's happening can make the kinds of
choices that produce the satisfying moments.

---

## Implementation map

The following sections of the original spec are implemented:

| § | Feature | Implementation |
|---|---------|----------------|
| 2.1 | Codex layer | `gm/runtime_experience.select_available_codex_entries`, `gm/choice_tags` codex link parser, `/session/{id}/codex/{entry_id}` route, web overlay |
| 2.2 | Inline mechanical cost on choices | `gm/choice_tags.parse_choice_tags`, `_apply_visible_cost` in `api/game_routes.py`, web cost tag rendering |
| 2.3 | Variable choice count | `gm/cloud_gm._parse_response` accepts 1-5 choices; pacing-continuation regex |
| 2.4 | Loosened choice format | Narration prompt CHOICE FORMAT GUIDANCE block |
| 2.5 | Personality-lock choices | `studio.schema.PersonalityLockMoment`, `Character.add_personality_lock`, runtime hook |
| 2.6 | Opposed-pair personality stats | `engine.character.OpposedPair`, `default_personality_axes`, `annotate_axis_movement` |
| 2.7 | Achievements and milestones | `studio.schema.Achievement`, `gm.runtime_experience.evaluate_achievements`, dashboard panel |
| 2.8 | Set-piece scene declarations | `studio.schema.SetPieceDeclaration`, `lookup_set_piece`, web title cards |
| 2.9 | Foreshadowing and callbacks (lightweight) | `Act.foreshadowing_plants`, `select_foreshadowing`, `mark_light_foreshadow_delivered` |
| 2.10 | Stakes communication | `compute_stakes_level`, `build_stakes_block`, web stakes badges |
| 3.1 | Pre-allocated relationship slots | `CampaignSpine.expected_relationship_count`, dashboard slot layout |
| 3.2 | Goal-priming convention | `should_emit_goal_priming`, `build_goal_priming_block` |
| 3.3 | Chapter and scene titles | `Act.title_visible`, web chapter title display |
| 3.4 | Visual prose formatting | Cloud GM keeps Markdown; web `renderProseMarkdown` |
| 3.5 | State visibility (dashboard) | `/session/{id}/dashboard` route, 10-tab web dashboard overlay |
| 3.6 | Glossary / quick-reference | `CampaignSpine.glossary`, `setGlossary` + `applyGlossaryToHtml` |
| 3.7 | Recap / re-reading affordance | `build_recap` in runtime_experience, recap card on session resume |
| 3.8 | First-turn onboarding wrapper | Implicit through Phase 18 prologue + first-scene SET PIECE |

---

## Files added

- `gm/choice_tags.py` — tag classifier
- `gm/runtime_experience.py` — runtime experience helpers
- `scripts/add_phase25_content.py` — content augmentation script
- `tests/test_phase25_runtime_experience.py` — 60 test cases

## Files modified

- `studio/schema.py` — new model classes
- `engine/character.py` — runtime fields and helper methods
- `gm/cloud_gm.py` — choice tag classifier integration
- `gm/context.py` — context package fields
- `gm/prompts/narration.txt`, `narration_literary.txt` — guidance updates
- `api/game_routes.py` — dashboard/codex routes, post-turn hook
- `state/db.py`, `state/session.py` — visible cost / codex link columns
- `web/index.html` — UI overhaul

## Content authored

`data/campaigns/shadows_of_the_custodian.json` was augmented with:
- 12 codex entries across (History Lesson), (Reality), (Imperial
  Doctrine), (Reputation), (Crew Roster), (Holocron Fragment),
  (Whispers), (Dossier) tags
- 29 glossary terms
- 5 set-piece declarations (one per act)
- 3 personality-lock moments at long_watch, two_brothers, custodians_hand
- 15 achievements (5 anchor-based, 3 relationship-based, 3 Force-power,
  others pattern/codex)
- 4 foreshadowing plants spanning Acts 1→2, 1→3, 2→4, 3→5
- `title_visible` set on all 5 acts

---

## Tests

`python -m pytest tests/test_phase25_runtime_experience.py -v`

Covers:
- Choice tag classifier (visible cost, codex link, skill tag, mixed)
- Personality axes (defaults, adjust, clamp, dominant pole, axis annotation)
- Personality locks (add, replace, render block, find)
- Codex (act/NPC/location filtering, block format)
- Set pieces + stakes (lookup, treatment, all stakes levels)
- Foreshadowing (plant detection, payoff after plant, delivery marking)
- Achievements (anchor, relationship, pattern, idempotent, unknown safe)
- Goal priming (triggers, block text)
- Recap (with turns, no turns)
- Spine schema integration (Shadows of the Custodian)
- Cost-tag application (Strain, Morality, Obligation, clamping)
- Cloud GM parser (multi-tag choices, pacing continuation)
