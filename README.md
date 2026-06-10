# Storyteller V3

An experimental AI-powered Star Wars narrative RPG engine built on the Fantasy Flight Games (FFG) *Edge of the Empire* / *Age of Rebellion* / *Force and Destiny* dice system.

The player reads prose passages, makes choices, and the story responds — mechanically real (dice determine outcomes) and narratively generative (an LLM writes the prose). Think **Choice of Games meets tabletop RPG meets AI Game Master**.

The dice are real and consequential — failure is narrated as failure, triumph as triumph. The LLM never decides mechanical outcomes; it describes what the dice already determined.

> ## ⚠️ Experimental Project
>
> This is a personal research project, not a finished game. The engine is functional end-to-end and the core systems work, but the project is best understood as an **active experiment** in marrying tabletop RPG mechanics to LLM-generated prose. Expect rough edges, missing content, and the occasional dragon. See [Project Status](#project-status) below for an honest breakdown of what works and what does not.

## Project Status

| Area | State |
|---|---|
| **Game mechanics** (dice pools, checks, character sheets, talents, Force, vehicles, XP) | Working |
| **Storytelling mechanics** (turn loop, context assembly, prose generation, choice annotation, reconciliation, scene validation) | Working |
| **Persistence and session continuity** | Working |
| **Campaign Studio authoring pipeline** (CS-1 through CS-6) | Working |
| **Story content depth** | Thin — only one canonical campaign exists, and even that needs substantially more detail, NPC interiority, and act-level texture before it reads like a finished narrative experience |
| **Multi-campaign saga features** (psychometric prologue, cross-campaign import quality, etc.) | Not started |
| **Polish, balancing, content moderation, accessibility** | Minimal |

In short: the **plumbing works**, the **scaffolding for stories works**, but the **stories themselves need a lot more meat on the bone**. If you load a session and play through it, the loop will hold together — but you'll see the cracks where authored detail is meant to be.

This repo is published in the spirit of "show your work." Use it as a reference, fork it, break it, build on it. It is not a product.

## How It Works

Two independent systems share this repo:

- **Game Engine** — the runtime. Loads a campaign spine JSON and plays it. Player-facing, latency-sensitive, one cloud LLM call per turn maximum.
- **Campaign Studio** — the authoring tool. Produces campaign spine JSON. Author-facing, multi-pass, no latency pressure.

The campaign spine JSON is the interface contract between them.

### Core Loop

1. Player reads a prose passage and selects a choice
2. A fast-tier LLM call decides whether the action requires a skill check
3. If yes, the engine builds a dice pool and rolls FFG narrative dice
4. A quality-tier LLM call narrates the outcome, honoring the dice result exactly
5. New scene-specific choices are presented
6. State persists across sessions

### Key Design Rules

- **`engine/` is pure Python.** Zero LLM dependencies. Runnable with no API keys.
- **Physics before imagination.** Code resolves all mechanical outcomes (dice, state transitions, NPC disposition changes) *before* the LLM receives context. The LLM describes outcomes; it never decides them.
- **Fail loud.** Bad JSON after retries = exception. Missing markers = exception. Errors surface, never hide.

## Tech Stack

- **Python 3.11+** with **FastAPI + Uvicorn**
- **Cloud LLM only** — OpenAI-compatible SDK with two-tier routing
  - **FAST tier:** structured JSON for decisions, annotations, reconciliation, scene validation (default: DeepSeek V4 Flash via OpenRouter)
  - **QUALITY tier:** turn narration, milestone reflections, time-skip prose, studio generation (default: DeepSeek V4 Pro via OpenRouter)
  - Provider configurable via `CLOUD_PROVIDER=openrouter|openai`
- **SQLite** with WAL mode for persistence
- **Pydantic v2** for all data models
- **Single-file HTML frontend**

## Getting Started

### Prerequisites

- Python 3.11+
- An API key for your cloud LLM provider — OpenRouter (default) or OpenAI

> **Note:** This project incurs cloud LLM costs per turn. Test with the cheapest model tier first. There is no local-model fallback.

### Installation

```bash
# Clone the repo
git clone https://github.com/DinomyteHero/StoryTeller-AI-Narrative-System.git
cd StoryTeller-AI-Narrative-System

# Install runtime
pip install -e .

# For development (pytest, ruff)
pip install -e ".[dev]"

# For Campaign Studio features (NetworkX for graph validation)
pip install -e ".[studio]"
```

### Configuration

Copy the example environment file and fill in your keys:

```bash
cp .env.example .env
```

Key settings in `.env`:

| Variable | Description | Default |
|---|---|---|
| `CLOUD_PROVIDER` | `openrouter` or `openai` | `openrouter` |
| `OPENROUTER_API_KEY` | Your OpenRouter API key (default path) | — |
| `OPENAI_API_KEY` | Your OpenAI API key (only if `CLOUD_PROVIDER=openai`) | — |
| `FAST_MODEL` | High-volume tier — decisions, annotations, reconciliation | `deepseek/deepseek-v4-flash` |
| `QUALITY_MODEL` | Quality-critical tier — milestones, time skips, studio | `deepseek/deepseek-v4-pro` |
| `NARRATION_MODEL` | Per-call override for live narration | `deepseek/deepseek-v4-flash` |
| `DB_PATH` | SQLite database path | `./data/storyteller.db` |
| `PORT` | Server port | `8000` |

See `.env.example` for the full set of tunables (token budgets, hot-path quality gates, OpenRouter provider routing, prose voice).

### Running

```bash
uvicorn api.main:app --port 8000
```

Then open `http://localhost:8000` in your browser.

## Project Structure

```
storyteller-v3/
├── engine/          # Pure Python — dice, characters, checks, talents, Force, vehicles
├── gm/              # LLM orchestration — fast + quality tiers, context assembly, prompts
├── state/           # SQLite persistence — sessions, turn history, memory compression
├── api/             # FastAPI routes for Game Engine and Campaign Studio
├── web/             # Single-file HTML frontend
├── studio/          # Campaign Studio — spine authoring, validation, saga pipeline
├── data/
│   ├── campaigns/   # Campaign spine JSON files
│   ├── characters/  # 6-protagonist starting roster + test fixtures
│   ├── talent_trees/ # 20 specialization trees + 52-talent library
│   ├── force_powers/ # 5 Force power definitions
│   ├── content_packs/ # Per-campaign design contracts
│   ├── era_packs/   # Era anchoring templates
│   └── personas/    # Writer's Room personas (55)
├── eval/            # Evaluation harness (quality metrics, golden scenarios)
├── tests/           # Test suite (31 test files)
└── docs/            # Project documentation (23 active files across 6 subdirectories)
```

## Included Content

- **The Ledger of Ossel Minor** — the canonical campaign. A defector
  drama set at Luke Skywalker's Jedi Praxeum in 16 ABY starring Kessa
  Rhane, a Force-sensitive deserter from a surviving Imperial
  child-acquisitions cell, hunted by the bureaucracy that built her and
  doubted by the academy sheltering her. 4 acts, 11 NPCs (5 canon
  figures with full voice profiles), 6 foreshadow threads, 4 factions,
  3 authored endings. Studio-generated via Mode 2 + architect, then
  hand-polished; passes all validation gates including the Gate 4 LLM
  narrative evaluation.
- **A starting roster of six protagonists** spanning all three FFG game
  lines, each with a full narrative arc (lie/ghost/truth/want/need),
  voice notes, and a signature item with bounded mechanics: Kessa Rhane
  (guardian), Dhara Vess (bounty hunter), Rix Calloran (ace), Saviin
  Talas (spy), Brin Ohmsa (mystic), Yara Senn (colonist).
- **Talent trees for all 18 careers** — 20 specialization trees plus a
  52-talent shared library, all enforced by the engine's dice-safety
  validator.

The previous canonical campaign (*Shadows of the Custodian*, 5 acts /
26 NPCs / 53 bond events) is retired from the player funnel
(`player_facing: false`) but remains on disk as a test fixture and
reference. Earlier campaigns (*The Nar Shaddaa Job*, *Echoes of the
Force*) live in `data/campaigns/_archive/`. They are not playable from
the current build.

## Milestone Status (last synced: 2026-05-03)

| Milestone | Scope | Status |
|---|---|---|
| V1 | Core loop: dice, checks, narration, persistence, API, UI | Complete |
| Milestone 1 | Full single-campaign experience (equipment, XP, talents, NPCs) | Complete |
| Milestone 2 | Force-sensitive campaigns | Complete |
| Milestone 3 | Vehicles and space combat | Complete |
| Milestone 4 | Multi-campaign saga (time skips done; prologue & later phases pending) | Partial |
| Campaign Studio | Spine authoring, validation, collaborative generation, saga pipeline, narrative quality, story engineering | Complete (CS-1 through CS-6) |

## Known Limitations

- **Story content is young.** *The Ledger of Ossel Minor* is gate-valid and hand-polished but has not yet accreted the bond-event and group-scene depth the previous campaign gained over two iterations (its content pack lists the gaps honestly). Expect to author or generate your own spines to see the system stretch.
- **Cloud LLM only.** No local model fallback. Costs scale with play time.
- **Single player-facing campaign.** *The Ledger of Ossel Minor* is the only campaign in the picker; on-demand generation (`POST /campaign/generate`) covers everything else.
- **No content moderation layer.** The system relies on the upstream model provider's safety. Star Wars themes can include violence; tune your provider settings accordingly.
- **No accessibility audit.** The frontend is a single HTML file optimized for readability, not screen readers or assistive tech.

## Documentation

All docs live in `docs/`, organized into tier-based subdirectories.
Start with [`docs/index.md`](docs/index.md) for full orientation —
authority map, reading order, current state, and navigation.

Key documents:

- [Implementation Spec](docs/specs/engine-implementation.md) — complete code-level specification
- [Build Roadmap](docs/status/roadmap.md) — phased build plan
- [Game Mechanics](docs/specs/game-mechanics.md) — 27 sections of game design
- [Vision](docs/specs/vision.md) — creative vision and design philosophy
- [Game Engine API](docs/api/game-engine-api.md) — HTTP endpoint reference
- [Campaign Studio API](docs/api/studio-api.md) — Studio endpoint reference

## Development

```bash
# Run tests
pytest

# Run a single test file
pytest tests/test_phase14_force.py -v

# Lint
ruff check .

# Auto-fix
ruff check --fix .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit conventions, and the project's "do not build the second thing until the first thing works" rule.

## Disclaimer

This is an unofficial, non-commercial fan project. *Star Wars* and the FFG dice mechanics are the intellectual property of their respective owners (Lucasfilm Ltd. / Disney, and the original *Edge of the Empire* publisher). This project is not affiliated with, endorsed by, or sponsored by any of them. No copyrighted text, art, or audio from those properties is included in this repository.

## License

Licensed under the [Apache License, Version 2.0](LICENSE). You are free to use, modify, and distribute the code subject to the terms of that license. The Apache 2.0 license includes an explicit patent grant and requires preservation of attribution and the NOTICE if one is added later.

This license applies to the **code in this repository only**. It does not grant rights to *Star Wars* or FFG intellectual property — see the Disclaimer above.
