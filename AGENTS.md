# Storyteller V3 — Agent Instructions

**This project keeps a single source of truth for agent guidance: [CLAUDE.md](CLAUDE.md).**

Whether you are Codex, Claude Code, or any other agent: read `CLAUDE.md` first.
It contains the architecture overview, build phases, critical rules,
documentation map, codebase metrics, and current milestone status.

This file (`AGENTS.md`) used to duplicate that content. Two onboarding
documents drifted at different rates and contradicted each other on
test counts, file inventories, and milestone progress. To prevent
recurrence, only `CLAUDE.md` is maintained. Update `CLAUDE.md` when
project state changes; do not re-introduce duplicate content here.

## Quick orientation (full detail in CLAUDE.md)

- **What this is:** LLM-powered Star Wars narrative RPG using FFG dice.
- **Architecture:** Game Engine (runtime) + Campaign Studio (authoring tool),
  sharing the campaign spine JSON as the interface contract.
- **Tech:** Python 3.11+, FastAPI, OpenAI-compatible cloud LLMs via
  OpenRouter or OpenAI (cloud-only — the local Ollama path was removed
  May 2026), SQLite WAL, Pydantic v2.
- **The rule that overrides everything:** Do not build the second thing
  until the first thing works.
- **Canonical campaign:** `data/campaigns/ledger_of_ossel_minor.json`
  (intended protagonist `kessa_rhane`). The prior canonical campaign
  `shadows_of_the_custodian.json` is retired from the player funnel
  (`player_facing: false`) but stays on disk as a test fixture.
- **Starting character roster:** `data/characters/{kessa_rhane,dhara_vess,rix_calloran,saviin_talas,brin_ohmsa,yara_senn}.json`.
  `clovis_beryl`, `praxeum_student`, and `praxeum_mechanic` remain as
  test fixtures only — do not modify their stats.

## Critical rules (full text in CLAUDE.md)

- **Rule 3:** `engine/` is pure Python. Zero LLM dependencies.
- **Rule 4:** The dice are the truth. No softening.
- **Rule 5:** Fail loud. Surface errors, do not paper over them.
- **Rule 11:** V1 must not block post-V1 mechanics (see CLAUDE.md for the
  four sub-constraints).
- **Physics-before-imagination invariant:** Code resolves all mechanical
  outcomes before the narrative model runs. The LLM describes outcomes
  code has already determined; it never decides them.

## Working scope

- **Game Engine work:** `engine/`, `gm/`, `state/`, `api/game_routes.py`, `web/`.
- **Campaign Studio work:** `studio/`, `api/studio_routes.py`.
- The studio schema (`studio/schema.py`) is the interface contract — both
  systems import it.

For everything else (build phases, post-V1 milestones, file-by-file
inventory, doc index, current status), see `CLAUDE.md`.
