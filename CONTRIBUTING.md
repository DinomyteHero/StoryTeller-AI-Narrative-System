# Contributing to Storyteller V3

## Getting Started

```bash
# Clone and install
git clone https://github.com/DinomyteHero/StoryTeller-AI-Narrative-System.git
cd StoryTeller-AI-Narrative-System
pip install -e ".[dev,studio]"

# Copy environment config
cp .env.example .env
# Fill in your API keys in .env
```

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) running locally with `qwen3.5:9b` pulled
- An API key for a cloud LLM provider (OpenAI, OpenRouter, etc.)

## Project Structure

Two independent systems share this repo:

- **Game Engine** (`engine/`, `gm/`, `state/`, `api/game_routes.py`, `web/`)
- **Campaign Studio** (`studio/`, `api/studio_routes.py`)

The campaign spine JSON (`studio/schema.py`) is the interface contract.
Do not modify `studio/` when working on the Game Engine (except
importing from `studio/schema.py`).

Read `docs/index.md` for full orientation.

## Code Style

- **Linter:** [Ruff](https://docs.astral.sh/ruff/)
- **Type hints:** Use Pydantic v2 models for data structures
- **`engine/` is pure Python.** Zero LLM dependencies. No API keys, no
  Ollama imports. Must be runnable standalone.
- Keep functions focused and testable

```bash
# Lint
ruff check .

# Auto-fix
ruff check --fix .
```

## Testing

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_phase14_force.py

# Run with verbose output
pytest -v
```

Test files live in `tests/` and follow the pattern
`test_phaseNN_feature.py` for Game Engine phases or
`test_csN_feature.py` for Campaign Studio phases.

## Key Rules

1. **Do not build the second thing until the first thing works.**
   Follow the build order in `docs/status/roadmap.md`.

2. **The dice are the truth.** Failure is narrated as failure. The LLM
   never decides mechanical outcomes.

3. **Physics before imagination.** Code resolves all mechanical
   outcomes before the LLM receives context.

4. **Fail loud.** Bad JSON after retries = exception. Missing markers =
   exception. Errors surface, never hide.

## Documentation

All docs live in `docs/`. When completing an implementation phase:

1. Update `docs/status/backlog.md` (mark items DONE)
2. Add entry to `docs/status/changelog.md`
3. Update `CLAUDE.md` metrics and milestone status
4. Update `README.md` milestone table if a milestone is completed

See `docs/index.md` for the four-tier document architecture
and authority resolution rules.

## Branching

- `main` is the stable branch
- Feature branches: `feature/phase-NN-description` or
  `feature/cs-N-description`
- PRs should reference the relevant build phase

## Commit Messages

Use clear, descriptive commit messages. Reference the phase or
milestone when applicable:

```
Add Phase 14 Force dice resolution and dark side temptation

Implements Force die rolling, pip allocation, dark side temptation
offers, and conflict tracking per Game Mechanics §9.
```
