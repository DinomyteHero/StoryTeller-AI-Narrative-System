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
- [Ollama](https://ollama.ai/) running locally with a model pulled (default: `qwen3.5:9b`)
- An API key for your chosen cloud LLM provider (OpenAI, OpenRouter, etc.)

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
| `CLOUD_PROVIDER` | `openai` or `openrouter` | `openai` |
| `CLOUD_MODEL` | Cloud model for narration | `gpt-5.2` |
| `OPENAI_API_KEY` | Your OpenAI API key | — |
| `OLLAMA_URL` | Ollama endpoint | `http://localhost:11434` |
| `LOCAL_MODEL` | Local model for check decisions | `qwen3.5:9b` |
| `DB_PATH` | SQLite database path | `./data/storyteller.db` |
| `PORT` | Server port | `8000` |

### Running

```bash
# Start the server
uvicorn api.main:app --port 8000

# Or run fully local (no cloud API key needed)
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
├── tests/           # Test suite (17 test files)
└── docs/            # All project documentation (20 files)
```

### Key Design Rules

- **`engine/` is pure Python.** Zero LLM dependencies. Runnable with no API keys and no Ollama.
- **Physics before imagination.** Code resolves all mechanical outcomes (dice, state transitions) *before* the LLM receives context. The LLM describes outcomes; it never decides them.
- **Fail loud.** Bad JSON after retries = exception. Missing markers = exception. Errors surface, never hide.

## Included Content

- **The Nar Shaddaa Job** — a smuggler campaign starring Keth Varso
- **Echoes of the Force** — a Force-sensitive campaign starring Talia Ren

## Milestone Status

| Milestone | Scope | Status |
|---|---|---|
| V1 | Core loop: dice, checks, narration, persistence, API, UI | Complete |
| Milestone 1 | Full single-campaign experience (equipment, XP, talents, NPCs) | Complete |
| Milestone 2 | Force-sensitive campaigns | Complete |
| Milestone 3 | Vehicles and space combat | Complete |
| Milestone 4 | Multi-campaign saga (time skips done; prologue & later phases pending) | Partial |
| Campaign Studio | Spine authoring, validation, collaborative generation, saga pipeline | Complete (CS-1 through CS-4) |

## Documentation

All docs live in `docs/`. Start with [`docs/00_PROJECT_GUIDE.md`](docs/00_PROJECT_GUIDE.md) for full orientation — authority map, reading order, current state, and navigation.

Key documents:

- [Implementation Spec](docs/STORYTELLER_V3_IMPLEMENTATION.md) — complete code-level specification
- [Build Roadmap](docs/STORYTELLER_V3_BUILD_ROADMAP.md) — phased build plan
- [Game Mechanics](docs/STORYTELLER_V3_GAME_MECHANICS.md) — 27 sections of game design
- [Vision](docs/STORYTELLER_V3_VISION.md) — creative vision and design philosophy

## Development

```bash
# Run tests
pytest

# Lint
ruff check .
```

## License

See repository for license details.
