# Claude Code Initial Prompt — Storyteller V3

Use this as your first message to Claude Code after setting up the repo with CLAUDE.md and all project documentation.

---

## The Prompt

```
I'm building Storyteller V3 — an LLM-powered Star Wars narrative RPG engine using the FFG dice system. The complete design and implementation spec is in the project documentation. Start by reading CLAUDE.md in the repo root for the full project overview.

Your primary spec is docs/STORYTELLER_V3_IMPLEMENTATION.md — it contains the complete code-level specification for every file in V1, including exact Python code, Pydantic models, prompt templates, database schemas, and API routes. Every piece of code in that document has been carefully designed and reviewed. Implement it as written unless you find a clear bug.

docs/STORYTELLER_V3_BUILD_ROADMAP.md defines the phased build plan from V1 through the finished product. Follow its phase ordering strictly.

docs/STORYTELLER_V3_GAME_MECHANICS.md contains the game design — 27 sections (§0-§26) covering every mechanical system. Sections 0-13 are V1-relevant. Sections 14-26 are post-V1 but contain forward-compatibility requirements that V1 code must respect (documented as Rule 11 in the Implementation doc).

Start with Phase 1: The Engine.

Build these three files in order:
1. engine/dice.py — FFG symbol dice tables and pool resolution
2. engine/character.py — Pydantic character model for all three game lines
3. engine/checks.py — Dice pool construction from character stats

The complete code for all three files is in docs/STORYTELLER_V3_IMPLEMENTATION.md Sections 5.1, 5.2, and 5.3. Implement them as specified. The dice symbol tables must be verified against the FFG rulebooks — they are the mechanical foundation everything else depends on.

Critical constraints for Phase 1:
- engine/ must be pure Python. Zero LLM dependencies. Zero I/O. No imports from gm/, state/, or api/.
- The dice engine must be data-driven — dice types defined by symbol tables, engine agnostic about what symbols mean. Do not hardcode assumptions about which symbols exist.
- build_pool() is structured as a sequential pipeline per Rule 11d. The spec in Section 5.3 already has `_stage_1_base_pool()` extracted as a standalone function with commented insertion points for future stages (talent modifiers, destiny modification, Force dice). Implement it as specified.
- The Character model includes force_rating, force_committed, total_xp, available_xp, and specializations as a list. These are not used in V1 but must not be removed.

After building the three files, also build:
- data/characters/keth_varso.json — the test character (spec in Section 5.4)
- tests/dice_validation.py — verify every symbol table face count and symbol against the spec

Phase 1 is complete when:
- All dice symbol tables match the FFG rulebook (ability=8 faces, proficiency=12, difficulty=8, challenge=12, boost=6, setback=6, force=12)
- build_pool(keth, CheckRequest(skill="deception", difficulty=Difficulty.AVERAGE)) returns 2 Proficiency + 2 Ability + 2 Difficulty (Cunning 4, Deception 2)
- roll_pool() produces valid results with correct cancellation (successes cancel failures, advantages cancel threats, triumphs and despairs are uncancellable)
- All tests pass

Do not proceed to Phase 2 until Phase 1 is verified.
```

---

## Setup Steps Before Using This Prompt

1. Create the repo: `mkdir storyteller-v3 && cd storyteller-v3 && git init`

2. Copy CLAUDE.md into the repo root

3. Create docs/ and copy all project documents into it:
```bash
mkdir docs
# Copy these files into docs/:
#   STORYTELLER_V3_VISION.md
#   STORYTELLER_V3_GAME_MECHANICS.md
#   STORYTELLER_V3_IMPLEMENTATION.md
#   STORYTELLER_V3_BUILD_ROADMAP.md
#   STORYTELLER_V3_BACKLOG.md
#   STORYTELLER_V3_CAMPAIGN_STUDIO.md
#   STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md
#   STORYTELLER_V3_LLM_EVALUATION.md
#   STORYTELLER_V3_RESEARCH_CATALOGUE.md
#   STORYTELLER_V3_DEFERRED_DESIGN_AND_LOGIC_ANALYSIS.md
#   STORYTELLER_V3_DESIGN_GAP_ANALYSIS.md
#   STORYTELLER_V3_DESIGN_GAP_ANALYSIS_V2.md
```

4. Create the directory structure:
```bash
mkdir -p engine gm/prompts state api web studio/saga data/characters data/campaigns data/personas data/evaluation_pairs data/talent_trees data/force_powers data/canon_profiles tests
touch engine/__init__.py gm/__init__.py state/__init__.py api/__init__.py studio/__init__.py studio/saga/__init__.py
```

5. Set up pyproject.toml (spec is in Implementation doc Section 11):
```bash
# The dependencies are in the Implementation doc, but Phase 1 needs nothing external
# Just ensure Python 3.11+ is available
python --version  # Should be 3.11+
```

6. Start Claude Code and paste the prompt above.

---

## For Subsequent Sessions

After Phase 1, start each new Claude Code session with a brief status update:

```
Continuing Storyteller V3. Phase [N] is complete and verified.
Starting Phase [N+1]. Read CLAUDE.md for project context and
docs/STORYTELLER_V3_IMPLEMENTATION.md Section [X] for the code spec.
[Any specific notes about what was completed or issues found.]
```

After V1 is complete:

```
V1 is complete — all 12 success criteria pass. Moving to post-V1
development. Read docs/STORYTELLER_V3_BUILD_ROADMAP.md for the phased
plan. Starting Milestone 1, Phase 7: [phase name]. The design spec
is in docs/STORYTELLER_V3_GAME_MECHANICS.md Section [X].
```

---

## What Claude Code Has Access To

Claude Code reads CLAUDE.md automatically from the repo root. All
project documentation lives in `docs/`. The most important docs in
order of frequency of reference:

1. docs/STORYTELLER_V3_IMPLEMENTATION.md — referenced every phase
2. docs/STORYTELLER_V3_BUILD_ROADMAP.md — referenced at phase transitions
3. docs/STORYTELLER_V3_GAME_MECHANICS.md — referenced for design detail
4. docs/STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md — referenced
   for spine schema (studio/schema.py)
5. docs/STORYTELLER_V3_DEFERRED_DESIGN_AND_LOGIC_ANALYSIS.md — system
   logic walkthrough, data flow verification, integration point analysis
6. docs/STORYTELLER_V3_DESIGN_GAP_ANALYSIS_V2.md — design specs for all
   items not fully specified in the Game Mechanics or Implementation
   docs (turn counter, entity persistence, seeding, difficulty
   calibration, ratings, trained evaluator, ensemble, persona pool)
7. Everything else in docs/ — background reference as needed

## Phase-Specific Notes

**Phase 5 (API):** The Implementation doc §9.1 and §9.2 contain
complete orchestration code for the turn handler and session creation
flow. These are the most important specs for Phase 5 — they chain
every component built in Phases 1-4 together. Implement them as
written.

**Phase 3 (Cloud GM):** The narration prompt template in §7.1 is
substantial (~2000 tokens). It includes scene-type-adaptive pacing,
an anti-AI-slop prohibition, NPC disposition fidelity instructions,
introspection choice guidance, and a game terminology quarantine. All
of this was carefully designed. Implement the prompt exactly as
specified.
