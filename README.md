# Storyteller V3

An AI-powered Star Wars narrative RPG engine built on the Fantasy Flight Games (FFG) Edge of the Empire / Age of Rebellion / Force and Destiny dice system.

The player reads prose passages, makes choices, and the story responds — mechanically real (dice determine outcomes) and narratively generative (an LLM writes the prose). Think **Choice of Games meets tabletop RPG meets AI Game Master**.

The prose reads like a Star Wars novel. The dice are real and consequential — failure is narrated as failure, triumph as triumph. The LLM never decides mechanical outcomes; it describes what the dice already determined.

## How It Works

Two independent systems share this repo:

- **Game Engine** — the runtime. Loads a campaign spine JSON and plays it. Player-facing, latency-sensitive, one cloud LLM call per turn maximum.
- **Campaign Studio** — the authoring tool. Produces campaign spine JSON. Author-facing, multi-pass, no latency pressure.

The campaign spine JSON is the interface contract between them.

### Core Loop

1. Player reads a prose passage and selects a choice
2. A local LLM decides whether the action requires a skill check
3. If yes, the engine builds a dice pool and rolls FFG narrative dice
4. A cloud LLM narrates the outcome, honoring the dice result exactly
5. New scene-specific choices are presented
6. State persists across sessions

## Tech Stack

- **Python 3.11+** with **FastAPI + Uvicorn**
- **Local LLM:** Ollama (check decisions, structured JSON)
- **Cloud LLM:** OpenAI-compatible SDK, provider-configurable (OpenAI, OpenRouter, or any compatible endpoint)
- **SQLite** with WAL mode for persistence
- **Pydantic v2** for all data models
- **Single-file HTML frontend**

## Getting Started

### Prerequisites

- Python 3.11+
- An API key for your cloud LLM provider — OpenRouter (default) or OpenAI
- [Ollama](https://ollama.ai/) is optional. Only needed if you set `NARRATIVE_BACKEND=local` for offline play, or enable `CLOUD_FALLBACK_TO_LOCAL=true` as an emergency fallback.

### Installation

```bash
# Clone the repo
git clone https://github.com/DinomyteHero/StoryTeller-AI-Narrative-System.git
cd StoryTeller-AI-Narrative-System

# Install dependencies
pip install -e .

# For development (pytest, ruff)
pip install -e ".[dev]"

# For Campaign Studio features
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
| `NARRATIVE_BACKEND` | `cloud` or `local` | `cloud` |
| `CLOUD_PROVIDER` | `openrouter` or `openai` | `openrouter` |
| `OPENROUTER_API_KEY` | Your OpenRouter API key (default path) | — |
| `OPENAI_API_KEY` | Your OpenAI API key (only if `CLOUD_PROVIDER=openai`) | — |
| `FAST_MODEL` | High-volume tier — decisions, annotations, reconciliation | `deepseek/deepseek-v4-flash` |
| `QUALITY_MODEL` | Quality-critical tier — milestones, time skips, studio | `deepseek/deepseek-v4-pro` |
| `NARRATION_MODEL` | Per-call override for live narration | `deepseek/deepseek-v4-flash` |
| `OLLAMA_URL` | Ollama endpoint (only used in local mode / fallback) | `http://localhost:11434` |
| `LOCAL_FAST_MODEL` | Local model for check decisions (offline / fallback) | `qwen3.5:9b` |
| `DB_PATH` | SQLite database path | `./data/storyteller.db` |
| `PORT` | Server port | `8000` |

See `.env.example` for the full set of tunables (token budgets, hot-path quality gates, OpenRouter provider routing, prose voice).

### Running

```bash
# Start the server
uvicorn api.main:app --port 8000

# Or run fully local (no cloud API key needed — requires Ollama)
NARRATIVE_BACKEND=local uvicorn api.main:app --port 8000
```

Then open `http://localhost:8000` in your browser.

## Project Structure

```
storyteller-v3/
├── engine/          # Pure Python — dice, characters, checks, talents, Force, vehicles
├── gm/              # LLM orchestration — local + cloud GM, context assembly, prompts
├── state/           # SQLite persistence — sessions, turn history, memory compression
├── api/             # FastAPI routes for Game Engine and Campaign Studio
├── web/             # Single-file HTML frontend
├── studio/          # Campaign Studio — spine authoring, validation, saga pipeline
├── data/
│   ├── campaigns/   # Campaign spine JSON files
│   ├── characters/  # Character JSON files
│   ├── talent_trees/ # 6 specialization trees + talent library
│   ├── force_powers/ # 5 Force power definitions
│   └── personas/    # Writer's Room personas (55)
├── eval/            # Evaluation harness (quality metrics, golden scenarios)
├── tests/           # Test suite (20 test files)
└── docs/            # All project documentation (21 files)
```

### Key Design Rules

- **`engine/` is pure Python.** Zero LLM dependencies. Runnable with no API keys and no Ollama.
- **Physics before imagination.** Code resolves all mechanical outcomes (dice, state transitions) *before* the LLM receives context. The LLM describes outcomes; it never decides them.
- **Fail loud.** Bad JSON after retries = exception. Missing markers = exception. Errors surface, never hide.

## Included Content

- **Shadows of the Custodian** — the canonical campaign. A Jedi Praxeum mystery set in 16 ABY starring Clovis Beryl, a smuggler-raised Force-sensitive newly arrived at Luke Skywalker's academy. 5 acts, 26 NPCs, 53 bond events, 8 group scenes, 17 foreshadow threads, 5 distinct endings.

Earlier campaigns (*The Nar Shaddaa Job*, *Echoes of the Force*) live in `data/campaigns/_archive/` for reference. They are not playable from the current build.

## Milestone Status (last synced: 2026-05-01)

| Milestone | Scope | Status |
|---|---|---|
| V1 | Core loop: dice, checks, narration, persistence, API, UI | Complete |
| Milestone 1 | Full single-campaign experience (equipment, XP, talents, NPCs) | Complete |
| Milestone 2 | Force-sensitive campaigns | Complete |
| Milestone 3 | Vehicles and space combat | Complete |
| Milestone 4 | Multi-campaign saga (time skips done; prologue & later phases pending) | Partial |
| Campaign Studio | Spine authoring, validation, collaborative generation, saga pipeline, narrative quality, story engineering | Complete (CS-1 through CS-6) |

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

# Lint
ruff check .
```

## License

See repository for license details.
