# Storyteller V3 — Game Engine Implementation Document
### For use with Claude Code

---

## 0. Read This First

**Scope:** This document specifies the Game Engine — the runtime system
that consumes a campaign spine JSON and plays the game. The companion
document `STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md` specifies
the Campaign Studio — the authoring system that produces campaign
spines. The two systems share a Python project, a SQLite database, and
the Ollama/OpenRouter infrastructure, but they are architecturally
independent. The campaign spine JSON is the interface contract between
them.

This document is the complete specification for the Game Engine. Before
writing any code, read this entire document. Every architectural
decision here was made deliberately. Do not deviate from the build
order. Do not add features not listed in the current phase.

**The single rule that overrides everything else:**

> Do not build the second thing until the first thing works and feels good.

The previous version of this project (V2) failed by building infrastructure
before validating the core loop. V3 exists to correct that. If you find
yourself wanting to add a companion system, a campaign manager, a RAG pipeline,
or anything not in the current phase — stop. Add it to the backlog. Finish the
phase you are in.

---

## 1. Project Overview

Storyteller V3 is an LLM-powered narrative RPG engine that delivers a
Choice-of-Games style reading experience using the FFG Star Wars TTRPG system
(Edge of the Empire, Age of Rebellion, Force and Destiny) as its mechanical
foundation.

**What it is:**
- A prose-first narrative game where the player reads passages and makes choices
- A GM powered by an LLM that understands FFG rules, interprets dice results
  dramatically, and maintains story continuity across a campaign
- A faithful implementation of the FFG symbol dice system as the mechanical layer

**What it is not:**
- A real-time game
- A visual novel with pre-authored branching paths
- A chatbot with RPG flavoring
- V2 with a different name

**The core loop:**

```
Player reads a 250-600 word prose passage
        ↓
Player selects one of 2-4 choices
        ↓
Local model decides: does this require a dice check?
        ↓                           ↓
    No check                  Build dice pool
        ↓                           ↓
Assemble context package      Roll FFG symbols
        ↓                           ↓
Cloud model narrates      Interpret net result
the outcome and                     ↓
generates next choices      Assemble context package
                                    ↓
                          Cloud model narrates the
                          outcome (honoring the dice)
                          and generates next choices
```

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Language | Python 3.11+ | All backend |
| Local LLM | Ollama — Qwen3.5:9B | Structured decisions, JSON, local narration fallback |
| Cloud LLM | OpenAI-compatible SDK — provider-configurable | Narrative prose, GM voice |
| Cloud provider (current) | OpenAI (`gpt-5.2`) | Active while OpenAI credits exist |
| Cloud provider (planned) | OpenRouter (`x-ai/grok-4.1-fast`) | Post-credits primary path |
| Database | SQLite (WAL mode) via Python stdlib | Session and campaign persistence |
| Data models | Pydantic v2 | Validation throughout |
| API | FastAPI + Uvicorn | Thin HTTP layer |
| Frontend | Single HTML file | Prose reader UI |
| Package mgmt | pyproject.toml (no Poetry) | Simple dependency management |

**Critical model constraint:**
One cloud LLM call per turn maximum. No exceptions. The moment a second cloud
call is added to a turn, complexity compounds and latency breaks immersion.

**Hardware note (dev machine):**
RTX 4070 (12GB VRAM) + 32GB RAM + Ryzen 7. Qwen3.5:9B at Q4_K_M quantization
(~5.5GB) fits entirely in VRAM with room to spare. Check decisions will return
in 1-2 seconds. Verify quantization with `ollama show qwen3.5:9b` — if the
pulled model is full BF16, explicitly pull `qwen3.5:9b-instruct-q4_K_M`.

**NARRATIVE_BACKEND flag:**
Set `NARRATIVE_BACKEND=local` to route narration through Ollama instead of the
cloud provider. Use this during active development to test the full loop without
burning API credits. Local output quality is lower — use it to validate that
mechanics, parsing, and context assembly work correctly. Never use it to
evaluate prose quality. In DEV_MODE the UI must display a visible warning when
local narration is active (e.g. "⚠ Local narration — loop test only").

**OpenRouter model string format:**
When `CLOUD_PROVIDER=openrouter`, model strings use the `provider/model` prefix
format: `x-ai/grok-4-1-fast`, `anthropic/claude-sonnet-4-5`, `openai/gpt-4o`.
This differs from direct provider strings. `CLOUD_MODEL` must match the format
expected by the active provider.

**Physics-before-imagination invariant:**
The narrative model never determines mechanical outcomes. Code resolves all
state transitions — dice rolls, NPC disposition changes, strain/wound updates,
Obligation triggers, Morality Conflict accumulation — before the narrative
model receives the updated context package. The LLM describes outcomes that
code has already determined. It does not decide them. If a future feature
proposal requires the cloud model to influence a mechanical outcome (e.g.,
"the LLM decides whether this NPC helps based on narrative feel"), it violates
this invariant and must be redesigned so the decision lives in code.

---

## 3. Repository Structure

The Game Engine and Campaign Studio share a single repository. Game
Engine code lives in `engine/`, `gm/`, `state/`, and `web/`. Campaign
Studio code lives in `studio/`. The spine schema models in
`studio/schema.py` define the interface contract — both systems import
from there. The `api/` directory is shared, with separate route files
per system. See the Campaign Studio Implementation Document for the
full `studio/` specification.

```
storyteller-v3/
├── CLAUDE.md                    # Game Engine impl (abridged) for Claude Code
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── engine/                      # Game Engine — pure Python, zero LLM, zero I/O
│   ├── __init__.py
│   ├── dice.py                  # FFG symbol tables, pool builder, resolver
│   ├── character.py             # Pydantic models for all three game lines
│   └── checks.py                # Pool construction, difficulty tables
│
├── gm/                          # Game Engine — LLM orchestration layer
│   ├── __init__.py
│   ├── local_gm.py              # Ollama calls → structured JSON decisions
│   ├── cloud_gm.py              # OpenAI-compatible → narrative prose + choices
│   ├── context.py               # Context package assembly
│   └── prompts/
│       ├── check_decision.txt   # Local model prompt template
│       └── narration.txt        # Cloud model prompt template
│
├── state/                       # Shared — persistence layer
│   ├── __init__.py
│   ├── db.py                    # SQLite connection, WAL mode, schema
│   ├── session.py               # Turn logging and state queries
│   └── memory.py                # Episodic compression, meaningful choice log
│
├── api/                         # Shared — HTTP layer
│   ├── __init__.py
│   ├── main.py                  # FastAPI app
│   ├── game_routes.py           # Game Engine API routes
│   └── studio_routes.py         # Campaign Studio API routes (post-V1)
│
├── web/                         # Game Engine — frontend
│   └── index.html               # Single-file prose reader UI
│
├── studio/                      # Campaign Studio (see Studio Implementation Doc)
│   ├── __init__.py
│   ├── schema.py                # Pydantic models for campaign spine JSON
│   ├── validate.py              # Validation suite (schema, NPC, network, audit)
│   ├── generate.py              # Spine generation orchestration (Modes 1–3)
│   ├── critique.py              # Debate/critique agent
│   ├── evaluate.py              # Pairwise spine evaluator
│   ├── import_interface.py      # Cross-era character import
│   ├── saga/                    # Saga layer pipeline
│   │   ├── __init__.py
│   │   ├── pipeline.py          # Five-stage orchestrator
│   │   ├── personas.py          # Persona pool management
│   │   ├── diverge.py           # Stage 2 — divergent generation
│   │   ├── search.py            # Stage 3 — branching search
│   │   ├── converge.py          # Stage 4 — debate and coherence
│   │   └── select.py            # Stage 5 — pairwise evaluation
│   └── prompts/                 # Studio-specific LLM prompt templates
│       └── ...
│
├── data/
│   ├── characters/
│   │   └── keth_varso.json      # Test character
│   ├── campaigns/
│   │   └── nar_shaddaa_job.json # Test campaign spine
│   ├── personas/
│   │   └── pool.json            # Saga layer persona pool
│   └── saga/
│       └── test_pipeline/       # Saga layer test artifacts
│
└── tests/
    ├── dice_validation.py       # Game Engine — verify symbol tables
    ├── studio_schema_test.py    # Spine schema validation tests
    └── saga_pipeline_test.py    # Saga pipeline integration tests
```

**Game Engine scope:** `engine/`, `gm/`, `state/`, `api/game_routes.py`,
`web/`, and the Game Engine's consumption of `studio/schema.py` for
spine loading. Everything else in `studio/` is specified in the Campaign
Studio Implementation Document and should not be modified when working
on the Game Engine.

---

## 4. Build Phases — Strict Order

### Phase 1: The Engine (Pure Python)
Files: `engine/dice.py`, `engine/character.py`, `engine/checks.py`

No LLM. No database. No API. Just Python.
Goal: Roll a dice pool for Keth's Deception check and get a correct result.

### Phase 2: The Local GM
Files: `gm/fast_gm.py`, `gm/prompts/check_decision.txt`

Goal: Given a scene description and player action, correctly decide whether a
check is needed and return structured JSON.

### Phase 3: The Cloud GM
Files: `gm/cloud_gm.py`, `gm/context.py`, `gm/prompts/narration.txt`

Goal: Given a complete context package including dice result, produce a
250-600 word narrative passage and 2-4 choices. Works with any OpenAI-compatible
provider. `NARRATIVE_BACKEND=local` routes through Ollama for loop testing.

### Phase 4: State and Persistence
Files: `state/db.py`, `state/session.py`, `state/memory.py`

Goal: A session persists across process restarts. Turn history compresses
correctly. NPC cards update.

### Phase 5: API
Files: `api/main.py`

Goal: Three working routes. The full loop is accessible via HTTP.

### Phase 6: Frontend
Files: `web/index.html`

Goal: A readable prose UI. Choices render as buttons. Dice panel is hidden
by default and expandable. Local narration warning visible in DEV_MODE.

**Do not start Phase 2 until Phase 1 produces correct dice results.**
**Do not start Phase 3 until Phase 2 produces valid JSON reliably.**
And so on.

---

## 5. Phase 1 — The Engine

### 5.1 `engine/dice.py`

This is the most important file in the project. Everything else depends on
it being correct. Verify every symbol table against the physical rulebooks
before proceeding.

```python
import random
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict


class DieType(Enum):
    ABILITY     = "ability"       # Green d8
    PROFICIENCY = "proficiency"   # Yellow d12
    DIFFICULTY  = "difficulty"    # Purple d8
    CHALLENGE   = "challenge"     # Red d12
    BOOST       = "boost"         # Blue d6
    SETBACK     = "setback"       # Black d6
    FORCE       = "force"         # White d12


class Symbol(Enum):
    SUCCESS   = "success"
    FAILURE   = "failure"
    ADVANTAGE = "advantage"
    THREAT    = "threat"
    TRIUMPH   = "triumph"   # Uncancellable success + critical positive
    DESPAIR   = "despair"   # Uncancellable failure + critical negative
    LIGHT     = "light"     # Force die only
    DARK      = "dark"      # Force die only
    BLANK     = "blank"


# ── Symbol tables ─────────────────────────────────────────────────────────────
# Each entry is a tuple of Symbol values for that face.
# Index 0 = face 1, index 1 = face 2, etc.
# Verified against FFG Edge of the Empire core rulebook.

ABILITY_TABLE = [
    (),                                      # Face 1: blank
    (Symbol.SUCCESS,),                       # Face 2
    (Symbol.SUCCESS,),                       # Face 3
    (Symbol.SUCCESS, Symbol.SUCCESS),        # Face 4
    (Symbol.ADVANTAGE,),                     # Face 5
    (Symbol.ADVANTAGE,),                     # Face 6
    (Symbol.SUCCESS, Symbol.ADVANTAGE),      # Face 7
    (Symbol.ADVANTAGE, Symbol.ADVANTAGE),    # Face 8
]

PROFICIENCY_TABLE = [
    (),                                      # Face 1: blank
    (Symbol.SUCCESS,),                       # Face 2
    (Symbol.SUCCESS,),                       # Face 3
    (Symbol.SUCCESS, Symbol.SUCCESS),        # Face 4
    (Symbol.SUCCESS, Symbol.SUCCESS),        # Face 5
    (Symbol.ADVANTAGE,),                     # Face 6
    (Symbol.SUCCESS, Symbol.ADVANTAGE),      # Face 7
    (Symbol.SUCCESS, Symbol.ADVANTAGE),      # Face 8
    (Symbol.SUCCESS, Symbol.ADVANTAGE),      # Face 9
    (Symbol.ADVANTAGE, Symbol.ADVANTAGE),    # Face 10
    (Symbol.ADVANTAGE, Symbol.ADVANTAGE),    # Face 11
    (Symbol.TRIUMPH,),                       # Face 12
]

DIFFICULTY_TABLE = [
    (),                                      # Face 1: blank
    (Symbol.FAILURE,),                       # Face 2
    (Symbol.FAILURE, Symbol.FAILURE),        # Face 3
    (Symbol.FAILURE,),                       # Face 4
    (Symbol.THREAT,),                        # Face 5
    (Symbol.THREAT,),                        # Face 6
    (Symbol.FAILURE, Symbol.THREAT),         # Face 7
    (Symbol.THREAT, Symbol.THREAT),          # Face 8
]

CHALLENGE_TABLE = [
    (),                                      # Face 1: blank
    (Symbol.FAILURE,),                       # Face 2
    (Symbol.FAILURE,),                       # Face 3
    (Symbol.FAILURE, Symbol.FAILURE),        # Face 4
    (Symbol.FAILURE, Symbol.FAILURE),        # Face 5
    (Symbol.THREAT,),                        # Face 6
    (Symbol.THREAT,),                        # Face 7
    (Symbol.FAILURE, Symbol.THREAT),         # Face 8
    (Symbol.FAILURE, Symbol.THREAT),         # Face 9
    (Symbol.THREAT, Symbol.THREAT),          # Face 10
    (Symbol.THREAT, Symbol.THREAT),          # Face 11
    (Symbol.DESPAIR,),                       # Face 12
]

BOOST_TABLE = [
    (),                                      # Face 1: blank
    (),                                      # Face 2: blank
    (Symbol.SUCCESS,),                       # Face 3
    (Symbol.SUCCESS, Symbol.ADVANTAGE),      # Face 4
    (Symbol.ADVANTAGE, Symbol.ADVANTAGE),    # Face 5
    (Symbol.ADVANTAGE,),                     # Face 6
]

SETBACK_TABLE = [
    (),                  # Face 1: blank
    (),                  # Face 2: blank
    (Symbol.FAILURE,),   # Face 3
    (Symbol.FAILURE,),   # Face 4
    (Symbol.THREAT,),    # Face 5
    (Symbol.THREAT,),    # Face 6
]

FORCE_TABLE = [
    (Symbol.DARK,),                          # Face 1
    (Symbol.DARK,),                          # Face 2
    (Symbol.DARK,),                          # Face 3
    (Symbol.DARK,),                          # Face 4
    (Symbol.DARK,),                          # Face 5
    (Symbol.DARK,),                          # Face 6
    (Symbol.DARK, Symbol.DARK),              # Face 7
    (Symbol.LIGHT,),                         # Face 8
    (Symbol.LIGHT, Symbol.LIGHT),            # Face 9
    (Symbol.LIGHT, Symbol.LIGHT),            # Face 10
    (Symbol.LIGHT, Symbol.LIGHT),            # Face 11
    (Symbol.LIGHT, Symbol.LIGHT),            # Face 12
]

DIE_TABLES = {
    DieType.ABILITY:     ABILITY_TABLE,
    DieType.PROFICIENCY: PROFICIENCY_TABLE,
    DieType.DIFFICULTY:  DIFFICULTY_TABLE,
    DieType.CHALLENGE:   CHALLENGE_TABLE,
    DieType.BOOST:       BOOST_TABLE,
    DieType.SETBACK:     SETBACK_TABLE,
    DieType.FORCE:       FORCE_TABLE,
}


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class DicePool:
    ability:    int = 0
    proficiency:int = 0
    difficulty: int = 0
    challenge:  int = 0
    boost:      int = 0
    setback:    int = 0
    force:      int = 0

    def description(self) -> str:
        parts = []
        if self.proficiency: parts.append(f"{self.proficiency}Y")
        if self.ability:     parts.append(f"{self.ability}G")
        if self.challenge:   parts.append(f"{self.challenge}R")
        if self.difficulty:  parts.append(f"{self.difficulty}P")
        if self.boost:       parts.append(f"{self.boost}B")
        if self.setback:     parts.append(f"{self.setback}K")
        if self.force:       parts.append(f"{self.force}W")
        return " ".join(parts)


@dataclass
class RollResult:
    # Raw counts before cancellation
    raw_successes:  int = 0
    raw_failures:   int = 0
    raw_advantages: int = 0
    raw_threats:    int = 0
    raw_triumphs:   int = 0
    raw_despairs:   int = 0
    raw_light:      int = 0
    raw_dark:       int = 0

    # Net after cancellation
    net_successes:  int = 0    # positive = net success, negative = net failure
    net_advantages: int = 0    # positive = net advantage, negative = net threat
    triumphs:       int = 0    # uncancellable
    despairs:       int = 0    # uncancellable
    light_pips:     int = 0
    dark_pips:      int = 0

    # Derived
    succeeded:        bool = False
    outcome_quadrant: str  = ""

    def narrative_label(self) -> str:
        """Plain English result for GM prompt injection."""
        parts = []

        if self.net_successes > 0:
            count = self.net_successes
            parts.append(
                f"SUCCEEDED ({count} net success{'es' if count != 1 else ''})"
            )
        elif self.net_successes < 0:
            count = abs(self.net_successes)
            parts.append(
                f"FAILED ({count} net failure{'s' if count != 1 else ''})"
            )
        else:
            # Exactly zero — tie goes to failure per FFG rules
            parts.append("FAILED (tied — successes and failures cancelled exactly)")

        if self.net_advantages > 0:
            count = self.net_advantages
            parts.append(f"with {count} Advantage{'s' if count != 1 else ''}")
        elif self.net_advantages < 0:
            count = abs(self.net_advantages)
            parts.append(f"with {count} Threat{'s' if count != 1 else ''}")

        if self.triumphs:
            parts.append(f"and {self.triumphs} TRIUMPH")
        if self.despairs:
            parts.append(f"and {self.despairs} DESPAIR")

        return " ".join(parts)


# ── Core functions ────────────────────────────────────────────────────────────

def roll_die(die_type: DieType) -> tuple:
    """Roll one die and return its face symbols."""
    return random.choice(DIE_TABLES[die_type])


def roll_pool(pool: DicePool) -> RollResult:
    """Roll a complete dice pool and return the resolved result."""
    raw = defaultdict(int)

    die_counts = [
        (DieType.ABILITY,     pool.ability),
        (DieType.PROFICIENCY, pool.proficiency),
        (DieType.DIFFICULTY,  pool.difficulty),
        (DieType.CHALLENGE,   pool.challenge),
        (DieType.BOOST,       pool.boost),
        (DieType.SETBACK,     pool.setback),
        (DieType.FORCE,       pool.force),
    ]

    for die_type, count in die_counts:
        for _ in range(count):
            for symbol in roll_die(die_type):
                raw[symbol] += 1

    result = RollResult(
        raw_successes=raw[Symbol.SUCCESS],
        raw_failures=raw[Symbol.FAILURE],
        raw_advantages=raw[Symbol.ADVANTAGE],
        raw_threats=raw[Symbol.THREAT],
        raw_triumphs=raw[Symbol.TRIUMPH],
        raw_despairs=raw[Symbol.DESPAIR],
        raw_light=raw[Symbol.LIGHT],
        raw_dark=raw[Symbol.DARK],
    )

    # Triumph counts as success for cancellation; Despair as failure
    total_successes = result.raw_successes + result.raw_triumphs
    total_failures  = result.raw_failures  + result.raw_despairs

    result.net_successes  = total_successes - total_failures
    result.net_advantages = result.raw_advantages - result.raw_threats
    result.triumphs       = result.raw_triumphs
    result.despairs       = result.raw_despairs
    result.light_pips     = result.raw_light
    result.dark_pips      = result.raw_dark
    result.succeeded      = result.net_successes > 0  # ties → failure

    adv = result.net_advantages >= 0
    if result.succeeded and adv:
        result.outcome_quadrant = "success_advantage"
    elif result.succeeded and not adv:
        result.outcome_quadrant = "success_threat"
    elif not result.succeeded and adv:
        result.outcome_quadrant = "failure_advantage"
    else:
        result.outcome_quadrant = "failure_threat"

    return result
```

---

### 5.2 `engine/character.py`

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class GameLine(Enum):
    EDGE_OF_EMPIRE    = "edge_of_empire"
    AGE_OF_REBELLION  = "age_of_rebellion"
    FORCE_AND_DESTINY = "force_and_destiny"


class Species(Enum):
    HUMAN    = "human"
    BOTHAN   = "bothan"
    TWIL_EK  = "twi_lek"
    RODIAN   = "rodian"
    WOOKIEE  = "wookiee"
    ZABRAK   = "zabrak"
    TOGRUTA  = "togruta"
    NAUTOLAN = "nautolan"
    MIRIALAN = "mirialan"
    DROID    = "droid"


class Career(Enum):
    # Edge of the Empire
    BOUNTY_HUNTER = "bounty_hunter"
    COLONIST      = "colonist"
    EXPLORER      = "explorer"
    HIRED_GUN     = "hired_gun"
    SMUGGLER      = "smuggler"
    TECHNICIAN    = "technician"
    # Age of Rebellion
    ACE       = "ace"
    COMMANDER = "commander"
    DIPLOMAT  = "diplomat"
    ENGINEER  = "engineer"
    SOLDIER   = "soldier"
    SPY       = "spy"
    # Force and Destiny
    CONSULAR = "consular"
    GUARDIAN = "guardian"
    MYSTIC   = "mystic"
    SEEKER   = "seeker"
    SENTINEL = "sentinel"
    WARRIOR  = "warrior"


class Characteristics(BaseModel):
    brawn:    int = Field(ge=1, le=6, default=2)
    agility:  int = Field(ge=1, le=6, default=2)
    intellect:int = Field(ge=1, le=6, default=2)
    cunning:  int = Field(ge=1, le=6, default=2)
    willpower:int = Field(ge=1, le=6, default=2)
    presence: int = Field(ge=1, le=6, default=2)


class SkillRanks(BaseModel):
    # General
    astrogation:       int = Field(ge=0, le=5, default=0)
    athletics:         int = Field(ge=0, le=5, default=0)
    charm:             int = Field(ge=0, le=5, default=0)
    coercion:          int = Field(ge=0, le=5, default=0)
    computers:         int = Field(ge=0, le=5, default=0)
    cool:              int = Field(ge=0, le=5, default=0)
    coordination:      int = Field(ge=0, le=5, default=0)
    deception:         int = Field(ge=0, le=5, default=0)
    discipline:        int = Field(ge=0, le=5, default=0)
    leadership:        int = Field(ge=0, le=5, default=0)
    mechanics:         int = Field(ge=0, le=5, default=0)
    medicine:          int = Field(ge=0, le=5, default=0)
    negotiation:       int = Field(ge=0, le=5, default=0)
    perception:        int = Field(ge=0, le=5, default=0)
    piloting_planetary:int = Field(ge=0, le=5, default=0)
    piloting_space:    int = Field(ge=0, le=5, default=0)
    resilience:        int = Field(ge=0, le=5, default=0)
    skulduggery:       int = Field(ge=0, le=5, default=0)
    stealth:           int = Field(ge=0, le=5, default=0)
    streetwise:        int = Field(ge=0, le=5, default=0)
    survival:          int = Field(ge=0, le=5, default=0)
    vigilance:         int = Field(ge=0, le=5, default=0)
    # Combat
    brawl:       int = Field(ge=0, le=5, default=0)
    gunnery:     int = Field(ge=0, le=5, default=0)
    melee:       int = Field(ge=0, le=5, default=0)
    ranged_light:int = Field(ge=0, le=5, default=0)
    ranged_heavy:int = Field(ge=0, le=5, default=0)
    # Knowledge
    core_worlds:int = Field(ge=0, le=5, default=0)
    education:  int = Field(ge=0, le=5, default=0)
    lore:       int = Field(ge=0, le=5, default=0)
    outer_rim:  int = Field(ge=0, le=5, default=0)
    underworld: int = Field(ge=0, le=5, default=0)
    warfare:    int = Field(ge=0, le=5, default=0)
    xenology:   int = Field(ge=0, le=5, default=0)
    # Force and Destiny
    lightsaber: int = Field(ge=0, le=5, default=0)


SKILL_CHARACTERISTICS: dict[str, str] = {
    "astrogation":        "intellect",
    "athletics":          "brawn",
    "charm":              "presence",
    "coercion":           "willpower",
    "computers":          "intellect",
    "cool":               "presence",
    "coordination":       "agility",
    "deception":          "cunning",
    "discipline":         "willpower",
    "leadership":         "presence",
    "mechanics":          "intellect",
    "medicine":           "intellect",
    "negotiation":        "presence",
    "perception":         "cunning",
    "piloting_planetary": "agility",
    "piloting_space":     "agility",
    "resilience":         "brawn",
    "skulduggery":        "cunning",
    "stealth":            "agility",
    "streetwise":         "cunning",
    "survival":           "cunning",
    "vigilance":          "willpower",
    "brawl":              "brawn",
    "gunnery":            "agility",
    "melee":              "brawn",
    "ranged_light":       "agility",
    "ranged_heavy":       "agility",
    "core_worlds":        "intellect",
    "education":          "intellect",
    "lore":               "intellect",
    "outer_rim":          "intellect",
    "underworld":         "intellect",
    "warfare":            "intellect",
    "xenology":           "intellect",
    "lightsaber":         "brawn",
}


class MotivationTrack(BaseModel):
    obligation_type:  Optional[str] = None
    obligation_value: int = 0
    duty_type:        Optional[str] = None
    duty_value:       int = 0
    morality:         int = 50
    conflict:         int = 0


class Character(BaseModel):
    name:               str
    species:            Species
    career:             Career
    specializations:    list[str]       = Field(default_factory=list)
    primary_game_line:  GameLine        = GameLine.EDGE_OF_EMPIRE
    background:         str             = ""
    characteristics:    Characteristics = Field(default_factory=Characteristics)
    skills:             SkillRanks      = Field(default_factory=SkillRanks)
    wound_threshold:    int = 0
    strain_threshold:   int = 0
    current_wounds:     int = 0
    current_strain:     int = 0
    soak:               int = 0
    total_xp:           int = 0
    available_xp:       int = 0
    motivation:         MotivationTrack = Field(default_factory=MotivationTrack)
    force_rating:       int = 0
    force_committed:    int = 0
    throughline_question: str = ""
    voice_notes:          str = ""
    active_injuries:      list[str] = Field(default_factory=list)  # narrative injury descriptions (Game Mechanics §3)

    def get_characteristic(self, name: str) -> int:
        return getattr(self.characteristics, name)

    def get_skill_rank(self, skill_name: str) -> int:
        return getattr(self.skills, skill_name, 0)

    def is_incapacitated(self) -> bool:
        return self.current_wounds >= self.wound_threshold

    def narrative_status(self) -> str:
        lines = [
            f"{self.name} | "
            f"{self.species.value.title()} "
            f"{self.career.value.replace('_', ' ').title()}",
            f"Wounds: {self.current_wounds}/{self.wound_threshold} | "
            f"Strain: {self.current_strain}/{self.strain_threshold}",
        ]
        if self.active_injuries:
            lines.append(f"Injuries: {'; '.join(self.active_injuries)}")
        if self.motivation.obligation_value > 0:
            lines.append(
                f"Obligation: {self.motivation.obligation_value} "
                f"({self.motivation.obligation_type})"
            )
        if self.motivation.duty_value > 0:
            lines.append(
                f"Duty: {self.motivation.duty_value} "
                f"({self.motivation.duty_type})"
            )
        if self.force_rating > 0:
            lines.append(
                f"Force Rating: {self.force_rating} | "
                f"Morality: {self.motivation.morality}"
            )
        return "\n".join(lines)
```

---

### 5.3 `engine/checks.py`

```python
from enum import Enum                          # required — do not omit
from engine.dice import DicePool
from engine.character import Character, SKILL_CHARACTERISTICS
from dataclasses import dataclass


class Difficulty(Enum):
    SIMPLE     = 0   # no purple dice — automatic success
    EASY       = 1   # 1 purple
    AVERAGE    = 2   # 2 purple
    HARD       = 3   # 3 purple
    DAUNTING   = 4   # 4 purple
    FORMIDABLE = 5   # 5 purple


DIFFICULTY_LABELS: dict[str, Difficulty] = {
    "simple":     Difficulty.SIMPLE,
    "easy":       Difficulty.EASY,
    "average":    Difficulty.AVERAGE,
    "hard":       Difficulty.HARD,
    "daunting":   Difficulty.DAUNTING,
    "formidable": Difficulty.FORMIDABLE,
}


@dataclass
class CheckRequest:
    skill:       str
    difficulty:  Difficulty
    boost_dice:  int = 0
    setback_dice:int = 0
    force_dice:  int = 0


def _stage_1_base_pool(character: Character, check: CheckRequest) -> DicePool:
    """
    Stage 1 — Base pool construction.
    Standard FFG formula: max(characteristic, skill_rank) ability dice,
    upgrade min(characteristic, skill_rank) to proficiency. Add difficulty
    dice. Situational boost/setback from check decision.
    """
    skill_name     = check.skill.lower().replace(" ", "_").replace("-", "_")
    governing_char = SKILL_CHARACTERISTICS.get(skill_name)

    if governing_char is None:
        raise ValueError(f"Unknown skill: {check.skill!r}")

    char_value   = character.get_characteristic(governing_char)
    skill_rank   = character.get_skill_rank(skill_name)
    total_dice   = max(char_value, skill_rank)
    prof_dice    = min(char_value, skill_rank)
    ability_dice = total_dice - prof_dice

    return DicePool(
        ability=ability_dice,
        proficiency=prof_dice,
        difficulty=check.difficulty.value,
        challenge=0,
        boost=check.boost_dice,
        setback=check.setback_dice,
        force=check.force_dice,
    )


# ── Pipeline stages 2-5 (post-V1) ─────────────────────────────────────
# Each stage takes a DicePool and returns a modified DicePool.
# Stage 2: Passive talent modifiers (Phase 11)
# Stage 3: Conditional talent modifiers (Phase 11)
# Stage 4: Destiny Point modification (Phase 11.5)
# Stage 5: Force dice addition (Phase 14)
# See Game Mechanics §23.5 for the full pipeline specification.


def build_pool(character: Character, check: CheckRequest, **kwargs) -> DicePool:
    """
    Full pool modification pipeline.

    V1 runs Stage 1 only. Post-V1 phases insert stages by adding
    calls between Stage 1 and return. Each stage function accepts
    and returns a DicePool, plus whatever additional context it needs
    via kwargs.

    Pipeline order (Game Mechanics §23.5):
      Stage 1 — Base pool construction (V1)
      Stage 2 — Passive talent modifiers (post-V1)
      Stage 3 — Conditional talent modifiers (post-V1)
      Stage 4 — Destiny Point modification (post-V1)
      Stage 5 — Force dice addition (post-V1)
    """
    pool = _stage_1_base_pool(character, check)
    # Stage 2: pool = _stage_2_passive_talents(pool, talents)
    # Stage 3: pool = _stage_3_conditional_talents(pool, talents, scene_ctx)
    # Stage 4: pool = _stage_4_destiny(pool, destiny_state, arc_state)
    # Stage 5: pool = _stage_5_force(pool, character)
    return pool


def describe_pool_for_display(pool: DicePool) -> dict:
    """
    Return a display-friendly dict for the frontend dice panel.
    Only includes die types actually present (count > 0).
    """
    all_dice = [
        {"type": "proficiency", "count": pool.proficiency, "color": "yellow"},
        {"type": "ability",     "count": pool.ability,     "color": "green"},
        {"type": "challenge",   "count": pool.challenge,   "color": "red"},
        {"type": "difficulty",  "count": pool.difficulty,  "color": "purple"},
        {"type": "boost",       "count": pool.boost,       "color": "blue"},
        {"type": "setback",     "count": pool.setback,     "color": "black"},
        {"type": "force",       "count": pool.force,       "color": "white"},
    ]
    return {
        "dice": [d for d in all_dice if d["count"] > 0],
        "description": pool.description(),
    }
```

---

### 5.4 Test Character Data File

`data/characters/keth_varso.json`

```json
{
    "name": "Keth Varso",
    "species": "bothan",
    "career": "smuggler",
    "specializations": ["pilot"],
    "primary_game_line": "edge_of_empire",
    "background": "A Bothan smuggler who owes a significant debt to a Hutt crime lord named Vossk the Patient. Operates the ship Mira's Luck on independent contracts, always looking for the job that will finally settle the balance.",
    "characteristics": {
        "brawn": 2, "agility": 3, "intellect": 3,
        "cunning": 4, "willpower": 2, "presence": 3
    },
    "skills": {
        "deception": 2, "piloting_space": 2, "streetwise": 1,
        "skulduggery": 1, "coordination": 1, "perception": 1
    },
    "wound_threshold": 12,
    "strain_threshold": 12,
    "current_wounds": 0,
    "current_strain": 0,
    "soak": 2,
    "total_xp": 110,
    "available_xp": 0,
    "motivation": {
        "obligation_type": "Debt",
        "obligation_value": 15
    },
    "force_rating": 0,
    "throughline_question": "Can a man who has only ever looked out for himself become someone worth following?",
    "voice_notes": "Dry, observational. Dark humor as a defense mechanism. Reads situations and people quickly. Rarely surprised, rarely panicked. Makes decisions by feel rather than plan, and the feel is usually right."
}
```

---

## 6. Phase 2 — The Local GM

### 6.1 `gm/prompts/check_decision.txt`

```
You are the mechanical judge for a Star Wars tabletop RPG using the FFG
narrative dice system (Edge of the Empire / Age of Rebellion / Force and Destiny).

Your job is to decide whether a player's action requires a skill check,
and if so, which skill and difficulty applies.

CHARACTER:
{character_summary}

STORY POSITION:
Act {current_act} of {total_acts} — {act_name}
Tension level: {tension_level}
{failure_calibration}

Use story position to calibrate difficulty:
- Early acts (calm/rising tension): prefer average difficulty, reserve hard
  for genuinely challenging actions
- Late acts (critical/climax): hard and daunting are appropriate
- Climax scenes: formidable is acceptable for the decisive moment

CURRENT SCENE:
{scene_description}

PLAYER ACTION:
{player_action}

DECISION RULES:
- Only call for a check when the outcome is genuinely uncertain AND failure
  would be interesting. Do not call checks for trivial actions.
- Use FFG skill names EXACTLY as listed below. Do not invent variants.
- Difficulty: simple (0 purple), easy (1), average (2), hard (3),
  daunting (4), formidable (5)
- Add boost dice for favorable circumstances (cover, preparation, assistance)
- Add setback dice for unfavorable circumstances (poor conditions, distraction,
  opposition awareness)
- Never add more than 2 boost or 2 setback dice without extraordinary reason

SCENE TYPE CLASSIFICATION:
Classify the current scene. This controls prose pacing in the narration.
- combat: active violence or immediate physical threat
- chase: pursuit, escape, or rapid movement under pressure
- infiltration: stealth, breaking in, avoiding detection
- social: dialogue-driven, NPC interaction, negotiation
- exploration: investigating, observing, navigating, gathering information
- introspection: quiet reflection, internal decision, no external pressure

MORAL WEIGHT:
Rate the moral weight of the player's action (0-3):
- 0: no moral dimension
- 1: minor — slightly self-serving or slightly costly choice
- 2: significant — clear moral trade-off, someone benefits or suffers
- 3: severe — betrayal, violence against innocents, major sacrifice

VALID SKILLS — use these exact strings, no variations:
astrogation, athletics, charm, coercion, computers, cool, coordination,
deception, discipline, leadership, mechanics, medicine, negotiation,
perception, piloting_planetary, piloting_space, resilience, skulduggery,
stealth, streetwise, survival, vigilance, brawl, gunnery, melee,
ranged_light, ranged_heavy, core_worlds, education, lore, outer_rim,
underworld, warfare, xenology, lightsaber

Respond ONLY with valid JSON. No preamble, no explanation, no markdown fences.

If a check IS required:
{
    "requires_check": true,
    "skill": "<exact_skill_name_from_list>",
    "difficulty": "<difficulty_label>",
    "boost_dice": <0-2>,
    "setback_dice": <0-2>,
    "scene_type": "<scene_type>",
    "moral_weight": <0-3>,
    "reasoning": "<one sentence explaining the call>"
}

If NO check is required:
{
    "requires_check": false,
    "scene_type": "<scene_type>",
    "moral_weight": <0-3>,
    "reasoning": "<one sentence explaining why no check is needed>"
}
```

### 6.2 `gm/fast_gm.py`

```python
import json
import os
import httpx
from pathlib import Path
from engine.character import Character
from dataclasses import dataclass
from typing import Optional

PROMPT_PATH = Path(__file__).parent / "prompts" / "check_decision.txt"
OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen3.5:9b")

VALID_SKILLS = {
    "astrogation", "athletics", "charm", "coercion", "computers", "cool",
    "coordination", "deception", "discipline", "leadership", "mechanics",
    "medicine", "negotiation", "perception", "piloting_planetary",
    "piloting_space", "resilience", "skulduggery", "stealth", "streetwise",
    "survival", "vigilance", "brawl", "gunnery", "melee", "ranged_light",
    "ranged_heavy", "core_worlds", "education", "lore", "outer_rim",
    "underworld", "warfare", "xenology", "lightsaber",
}

SKILL_ALIASES = {
    "piloting":             "piloting_space",
    "pilot":                "piloting_space",
    "space_piloting":       "piloting_space",
    "spaceship_piloting":   "piloting_space",
    "planetary_piloting":   "piloting_planetary",
    "range_light":          "ranged_light",
    "range_heavy":          "ranged_heavy",
    "light_ranged":         "ranged_light",
    "heavy_ranged":         "ranged_heavy",
    "skullduggery":         "skulduggery",
    "street_wise":          "streetwise",
    "knowledge_underworld": "underworld",
    "knowledge_lore":       "lore",
}

CHECK_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "requires_check": {"type": "boolean"},
        "skill":          {"type": "string"},
        "difficulty": {
            "type": "string",
            "enum": ["simple", "easy", "average", "hard", "daunting", "formidable"],
        },
        "boost_dice":   {"type": "integer", "minimum": 0, "maximum": 2},
        "setback_dice": {"type": "integer", "minimum": 0, "maximum": 2},
        "scene_type": {
            "type": "string",
            "enum": ["combat", "chase", "infiltration", "social",
                     "exploration", "introspection"],
        },
        "moral_weight": {"type": "integer", "minimum": 0, "maximum": 3},
        "reasoning":    {"type": "string"},
    },
    "required": ["requires_check", "scene_type", "reasoning"],
}


@dataclass
class CheckDecision:
    requires_check: bool
    skill:          Optional[str] = None
    difficulty:     Optional[str] = None
    boost_dice:     int = 0
    setback_dice:   int = 0
    scene_type:     str = "social"     # default fallback per Game Mechanics §10
    moral_weight:   int = 0            # 0=none, 1=minor, 2=significant, 3=severe (Game Mechanics §9)
    reasoning:      str = ""


class LocalGMError(Exception):
    pass


def _normalize_skill(raw: str) -> str:
    normalised = raw.lower().strip().replace(" ", "_").replace("-", "_")
    if normalised in VALID_SKILLS:
        return normalised
    if normalised in SKILL_ALIASES:
        return SKILL_ALIASES[normalised]
    raise ValueError(f"Unknown skill {raw!r}. Valid: {sorted(VALID_SKILLS)}")


def decide_check(
    character:            Character,
    scene_description:    str,
    player_action:        str,
    arc_state:            dict,
    recent_failure_count: int = 0,
    max_retries:          int = 3,
) -> CheckDecision:
    # Failure recovery calibration (Game Mechanics §2)
    if recent_failure_count >= 2:
        failure_calibration = (
            "DIFFICULTY CALIBRATION: The character is under sustained pressure "
            f"({recent_failure_count} failed checks in recent turns). Prefer "
            "average difficulty over hard. Reserve hard/daunting for actions "
            "that are genuinely reckless in context."
        )
    else:
        failure_calibration = ""

    template = PROMPT_PATH.read_text()
    prompt   = template.format(
        character_summary=character.narrative_status(),
        current_act=arc_state.get("current_act", 1),
        total_acts=arc_state.get("total_acts", 4),
        act_name=arc_state.get("act_name", "Unknown"),
        tension_level=arc_state.get("tension_level", "rising"),
        failure_calibration=failure_calibration,
        scene_description=scene_description,
        player_action=player_action,
    )

    last_error = None
    for _ in range(max_retries):
        try:
            response = httpx.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model":  LOCAL_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": CHECK_DECISION_SCHEMA,
                    "options": {"temperature": 0.1, "num_predict": 200},
                },
                timeout=30.0,
            )
            response.raise_for_status()
            raw_text = response.json()["response"].strip()

            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            return _validate_decision(json.loads(raw_text))

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            last_error = e
        except httpx.HTTPError as e:
            raise LocalGMError(f"Ollama connection error: {e}")

    raise LocalGMError(
        f"Local model failed after {max_retries} attempts. Last error: {last_error}"
    )


VALID_SCENE_TYPES = {
    "combat", "chase", "infiltration", "social", "exploration", "introspection",
}


def _validate_decision(data: dict) -> CheckDecision:
    if "requires_check" not in data:
        raise ValueError("Missing 'requires_check'")

    # scene_type and moral_weight apply to all decisions (check or no-check)
    raw_scene = data.get("scene_type", "social").lower().strip()
    scene_type = raw_scene if raw_scene in VALID_SCENE_TYPES else "social"
    moral_weight = max(0, min(3, int(data.get("moral_weight", 0))))

    if not data["requires_check"]:
        return CheckDecision(
            requires_check=False,
            scene_type=scene_type,
            moral_weight=moral_weight,
            reasoning=data.get("reasoning", ""),
        )
    if "skill" not in data:
        raise ValueError("Missing 'skill'")
    if "difficulty" not in data:
        raise ValueError("Missing 'difficulty'")
    return CheckDecision(
        requires_check=True,
        skill=_normalize_skill(data["skill"]),
        difficulty=data["difficulty"].lower().strip(),
        boost_dice=min(int(data.get("boost_dice", 0)), 2),
        setback_dice=min(int(data.get("setback_dice", 0)), 2),
        scene_type=scene_type,
        moral_weight=moral_weight,
        reasoning=data.get("reasoning", ""),
    )
```

**Schema validation note (v1.5):** The `_validate_decision` function above
provides basic structural validation. For production robustness, the check
decision should additionally be validated via a Pydantic model (already in
the tech stack) that enforces enum membership for `skill`, `difficulty`, and
`scene_type` fields at the type level. If the local model returns a response
that fails validation after `max_retries` attempts, the fallback behavior
is: `requires_check=False`, `scene_type="social"`, and a logged warning.
This ensures the turn always advances — a missed check is better than a
stalled game. The same principle applies to the scene type classification
added in Game Mechanics Document Section 10: if `scene_type` is missing
or invalid, default to `"social"` and log.

---

## 7. Phase 3 — The Cloud GM

### 7.1 `gm/prompts/narration.txt`

```
You are the Game Master for a Star Wars narrative RPG campaign. Your voice
is that of a literary Star Wars author — specific, atmospheric, grounded.
You write in second person present tense. Your prose earns every sentence.

You do not summarize. You do not explain. You show.

ABSOLUTE PROHIBITION — AI HOUSE STYLE:
Your prose must never sound like a language model. Every register — warm,
precise, visceral, atmospheric — must sound like a specific human author
writing in a specific mode. Specifically banned:
- "tapestry," "delve," "testament to," "couldn't help but notice"
- "a sense of [emotion] settled over," "hung in the air," "seemed to"
- "the weight of [abstraction]," "a flicker of," "something shifted"
- "In that moment," "It was then that," "And yet, despite everything"
- "sent a shiver," "washed over," "pierced the silence"
- Resumptive structures that hedge ("And yet," "But still," "Even so")
  used as paragraph openers
If a phrase could appear in any AI-generated story about any character
in any setting, it is too generic. Cut it. Prefer concrete, specific
language grounded in this character's sensory experience of this moment.

═══════════════════════════════════════════
CHARACTER
═══════════════════════════════════════════
{character_summary}

CHARACTER VOICE:
{character_voice}

═══════════════════════════════════════════
STORY CONTEXT
═══════════════════════════════════════════
CAMPAIGN: {campaign_name}
STORY POSITION: {story_position}
THROUGHLINE: {throughline_question}
TENSION LEVEL: {tension_level}

Never use the words "act," "chapter," "session," "turn," or any
structural game terminology in your prose. The player is reading a
story, not navigating a game structure.

STORY SO FAR:
{story_summary}

OPEN THREADS:
{open_threads}

═══════════════════════════════════════════
ACTIVE NPCs
═══════════════════════════════════════════
{npc_states}

═══════════════════════════════════════════
CURRENT SCENE
═══════════════════════════════════════════
LOCATION: {location}
SITUATION: {situation}

GALACTIC CONTEXT:
{galactic_context}

{scene_pacing}

{dice_result_block}

═══════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════
Write a narrative passage that:

1. Narrates this moment in the character's story
2. HONORS THE DICE RESULT EXACTLY — do not soften failures, do not reduce
   triumphs. The dice are the truth of what happened.
3. Maintains the established character voice
4. Does not introduce new named characters or locations not already established
5. Does not resolve open threads prematurely
6. Does not reference game mechanics (no "you roll", "you succeed", etc.)
7. OPENS BY REFLECTING THE PLAYER'S SPECIFIC CHOICE — the first sentences
   must show the consequence of what the player chose to do. Do not write
   a passage that could follow from any choice.

Follow the PACING, VOICE TARGET, and SCENE CRAFT instructions in the
CURRENT SCENE block above. They are calibrated to this turn's scene type.
Word count target is in the pacing guidance.

After the passage, on a new line write exactly: ---CHOICES---
Then provide 2-4 choices following these rules:
- Each choice must be specific to this scene and this character
- At least one choice should have lower risk
- At least one choice should have higher risk
- Choices may be actions, dialogue lines, or conversational approaches
- CHARACTER THROUGH TACTICS: the tactical decision and the identity
  decision must be the SAME choice. Each option should reveal something
  different about who the character is, not just accomplish a goal
  differently.
  BAD: "Pick the lock" / "Force the door" / "Talk your way in"
  (these test what the player DOES — generic action types)
  GOOD: "Work the lock yourself — patience is cheaper than favors" /
  "Signal Doss's frequency one more time — if he's in there, he'll hear
  it" / "Buy a drink next door and watch who comes and goes — the door
  will still be there in an hour"
  (these test who the player IS — self-reliant patience, loyalty to a
  missing friend, tactical caution)
- If a choice would require a dice check, append the skill tag at the very
  end in square brackets, e.g. "Bluff your way past the checkpoint [Deception]"
  The tag will be stripped before the player sees the choice.
- Choices without a dice check have no tag
- Do not use generic action types (attack/defend/talk/run)
- Write choices as actions or words the character would naturally consider
- RISK SIGNALING: Write choices that would require a dice check with
  language that conveys uncertainty or risk from the character's perspective
  (doubt, hedging, awareness of difficulty). Write choices that do not
  require a check with language that conveys confidence or certainty
  (straightforward action, routine capability). The player should develop
  intuition for risk through the writing, not through labels.
- INTROSPECTION CHOICES: When the pacing guidance indicates introspection,
  or when a major event has just resolved and the character has a natural
  moment to process, at least one choice should be reflective — an internal
  decision about what the moment means, not what to do next. These choices
  have no skill tag. They shape who the character is becoming.
  Examples of introspection choice texture:
  "Sit with it. Let the silence hold the weight of what just happened."
  "Push it down. There will be time to think later — right now there is
  still work to do."
  "Turn the name over in your mind. You know what it means. You are not
  ready to say it out loud yet."

TONE: {tone_instruction}

═══════════════════════════════════════════
DICE RESULT INTERPRETATION GUIDE
═══════════════════════════════════════════
success_advantage: "Yes, and..." — achieved goal + something additional gained
success_threat:    "Yes, but..." — achieved goal + new problem emerged
failure_advantage: "No, but..."  — did not achieve goal + something useful emerged
failure_threat:    "No, and..."  — did not achieve goal + situation now worse

TRIUMPH adds a critical positive effect on top of the base outcome.
DESPAIR adds a critical negative effect on top of the base outcome.
Strong advantages/threats (3+) should be notably impactful in the narrative.
```

### 7.2 `gm/context.py`

```python
import re
from dataclasses import dataclass, field
from typing import Optional
from engine.character import Character
from engine.dice import RollResult, DicePool


@dataclass
class NPCState:
    name:                str
    knows:               list[str] = field(default_factory=list)
    doesnt_know:         list[str] = field(default_factory=list)
    disposition:         float = 0.5   # 0.0 (hostile) to 1.0 (loyal)
    last_seen_turn:      int = 0
    voice_notes:         str = ""
    motivation:          str = ""
    behavioral_envelope: list[str] = field(default_factory=list)  # hard "never" constraints

    def disposition_label(self) -> str:
        """Human-readable label for prompt injection."""
        if self.disposition >= 0.8:   return "loyal"
        if self.disposition >= 0.6:   return "friendly"
        if self.disposition >= 0.4:   return "neutral"
        if self.disposition >= 0.2:   return "wary"
        return "hostile"

    def to_prompt_block(self) -> str:
        lines = [f"{self.name}:"]
        if self.knows:
            lines.append(f"  Knows: {'; '.join(self.knows)}")
        if self.doesnt_know:
            lines.append(f"  Doesn't know: {'; '.join(self.doesnt_know)}")
        lines.append(f"  Disposition: {self.disposition_label()} ({self.disposition:.2f})")
        if self.voice_notes:
            lines.append(f"  Voice: {self.voice_notes}")
        if self.motivation:
            lines.append(f"  Wants: {self.motivation}")
        if self.behavioral_envelope:
            lines.append(f"  Never: {'; '.join(self.behavioral_envelope)}")
        return "\n".join(lines)


@dataclass
class TurnMemory:
    turn_number:            int
    player_action:          str
    narration_excerpt:      str = ""     # v2.4: first 2-3 sentences of passage (evaluation §2.2)
    check_made:             Optional[str] = None
    dice_result:            Optional[str] = None
    outcome_quadrant:       Optional[str] = None
    meaningful_choice_note: str = ""


@dataclass
class ThreadState:
    """Stateful thread tracking — name + what's known/unknown."""
    name:           str
    player_knows:   list[str] = field(default_factory=list)
    player_unknown: list[str] = field(default_factory=list)


@dataclass
class ArcState:
    campaign_name:        str
    current_act:          int
    total_acts:           int
    act_name:             str
    act_progress:         float
    current_anchor:       str
    next_anchor:          str
    anchors_completed:    list[str]
    throughline_question: str
    tension_level:        str
    open_threads:         list[ThreadState]  # v2.4: structured threads with state (evaluation §2.2)
    closed_threads:       list[str]


@dataclass
class ContextPackage:
    character:        Character
    arc:              ArcState
    story_summary:    str
    recent_turns:     list[TurnMemory]
    active_npcs:      list[NPCState]
    location:         str
    situation:        str
    galactic_context: str = ""         # v1.6: per-act worldbuilding (Game Mechanics §4, Campaign Studio §4.4)
    sequence:         Optional[dict] = None  # v1.6: multi-beat sequence state (Game Mechanics §3) — null for normal turns
    dice_pool:        Optional[DicePool]   = None
    roll_result:      Optional[RollResult] = None
    scene_type:       str = "social"   # v2.1: from check decision (Game Mechanics §10)
    tone_instruction: str = "Maintain established tone"
    prose_diagnostic: Optional[dict] = None  # v1.5: reserved for prose diagnostic signal (Game Mechanics v1.1 §13)

    def build_dice_result_block(self) -> str:
        if self.roll_result is None:
            return "NO DICE CHECK THIS TURN — narrate the action directly."
        lines = [
            "DICE CHECK RESULT:",
            f"  Pool: {self.dice_pool.description() if self.dice_pool else 'unknown'}",
            f"  Result: {self.roll_result.narrative_label()}",
            f"  Outcome quadrant: {self.roll_result.outcome_quadrant}",
        ]
        if self.roll_result.triumphs:
            lines.append(
                f"  TRIUMPH x{self.roll_result.triumphs}: "
                "Include a significant critical positive effect"
            )
        if self.roll_result.despairs:
            lines.append(
                f"  DESPAIR x{self.roll_result.despairs}: "
                "Include a significant critical negative effect"
            )
        if abs(self.roll_result.net_advantages) >= 3:
            side = ("advantages" if self.roll_result.net_advantages > 0
                    else "threats")
            lines.append(
                f"  Strong {side} ({abs(self.roll_result.net_advantages)}): "
                "This should be notably impactful in the narrative"
            )
        return "\n".join(lines)

    def build_npc_block(self) -> str:
        if not self.active_npcs:
            return "No NPCs currently active in scene."
        return "\n\n".join(npc.to_prompt_block() for npc in self.active_npcs)

    def build_open_threads_block(self) -> str:
        if not self.arc.open_threads:
            return "None established yet."
        lines = []
        for t in self.arc.open_threads:
            line = f"- {t.name}"
            if t.player_knows:
                line += f"\n  Player knows: {'; '.join(t.player_knows)}"
            if t.player_unknown:
                line += f"\n  Player does NOT know: {'; '.join(t.player_unknown)}"
            lines.append(line)
        return "\n".join(lines)
```

**Context package validation (v1.5):** Before the assembled context package
is formatted into the cloud prompt, validate structural completeness:
`situation` and `location` must be non-empty strings; `active_npcs` must
contain at least one NPC; `recent_turns` must be non-empty (except on
Turn 1); `character` must have a populated `voice_notes` field. If
validation fails, log the error with full context details — do not send an
incomplete package to the cloud model, as it will hallucinate to fill gaps.
This should never occur in normal operation; a validation failure here
indicates a bug in context assembly. Surface a generic "the story pauses
for a moment" passage to the player while the error is investigated.

### 7.3 `gm/cloud_gm.py`

Uses the OpenAI-compatible SDK. Provider and model are read from env vars —
no code changes needed to switch between OpenAI, OpenRouter, or local Ollama.

```python
import re
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator
from openai import OpenAI
from gm.context import ContextPackage

PROMPT_PATH = Path(__file__).parent / "prompts" / "narration.txt"
MAX_TOKENS  = 1500

# Provider config — all from environment variables
# CLOUD_PROVIDER:    "openai" | "openrouter"
# CLOUD_MODEL:
#   openai      → "gpt-5.2", "gpt-5.2-mini", etc.
#   openrouter  → "x-ai/grok-4.1-fast", "openai/gpt-5.2", etc. (provider/model format)
# NARRATIVE_BACKEND: "cloud" | "local"

CLOUD_PROVIDER    = os.getenv("CLOUD_PROVIDER", "openai")
CLOUD_MODEL       = os.getenv("CLOUD_MODEL", "gpt-5.2")
NARRATIVE_BACKEND = os.getenv("NARRATIVE_BACKEND", "cloud")
OLLAMA_URL        = os.getenv("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL       = os.getenv("LOCAL_MODEL", "qwen3.5:9b")

PROVIDER_BASE_URLS = {
    "openai":     None,
    "openrouter": "https://openrouter.ai/api/v1",
}

# ── Scene pacing guidance (Game Mechanics §10, Vision §3) ─────────────
# Maps scene_type to:
#   - pacing: word count, sentence rhythm, structural guidance
#   - voice_exemplar: 1-2 sentences in the target register for style anchoring
#   - craft: 3-4 craft constraints SPECIFIC to this scene type (rotated,
#     not cumulative — reduces prompt overload per evaluation §2.1)
#
# HARD CONSTRAINTS (always active regardless of scene type) are in the
# prompt template's YOUR TASK section: dice fidelity, word count, delimiter,
# no game terminology, choice count, anti-slop prohibition.
#
# CRAFT CONSTRAINTS rotate per scene type — only the ones relevant to
# the current scene are injected, reducing cognitive load on the model.

SCENE_PACING = {
    "combat": {
        "pacing": (
            "PACING: Combat. Short sentences, compressed paragraphs. "
            "250-350 words. Choices are immediate and action-oriented. "
            "Worldbuilding compresses to the immediate situation."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"The bolt came before the thought. His hand was already "
            "moving, the DL-44 clearing leather with a muscle memory "
            "that predated everything he'd learned to think about, and "
            "the shot punched a fist-sized hole through the cargo crate "
            "where his head had been a quarter second ago.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- The character's body reacts before their mind catches up. "
            "Write from inside the nervous system.\n"
            "- NPC disposition determines how they fight — hostile NPCs "
            "press advantages, wary NPCs look for escape routes.\n"
            "- Each choice must have a different tactical AND identity "
            "profile. Not just 'attack/defend/flee' — the METHOD of "
            "fighting reveals who the character IS."
        ),
    },
    "chase": {
        "pacing": (
            "PACING: Chase. Movement and spatial awareness drive the "
            "prose. Speed through sentence rhythm — shorter as pressure "
            "mounts. 250-400 words. The environment is experienced at "
            "velocity, not examined."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"Three corridors. Left went deeper into the maintenance "
            "level — dark, tangled, the kind of place you lost people. "
            "Right went up toward the Promenade and crowds and witnesses. "
            "Straight ahead was a blast door that might or might not be "
            "locked, and behind him the sound of boots was getting closer "
            "in a way that suggested the people wearing them knew exactly "
            "where he was going.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- Spatial relationships matter — the reader must feel the "
            "geography of the pursuit.\n"
            "- Each choice represents a different escape philosophy: "
            "speed vs stealth vs misdirection vs confrontation.\n"
            "- If a dice check failed, the environment closes in — "
            "fewer exits, less time, worse options."
        ),
    },
    "infiltration": {
        "pacing": (
            "PACING: Infiltration. Precise, controlled prose. The "
            "character thinks in operational terms — angles, timing, "
            "sight lines. 300-450 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"You count the patrol interval. Forty seconds between the "
            "guard's peripheral sweep and the camera's return arc. Forty "
            "seconds is enough if you don't hesitate, and you haven't "
            "hesitated at a threshold since you were seventeen.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- Tension lives in the gap between the plan and what the "
            "plan missed. Details that seemed safe should develop edges.\n"
            "- Choices represent different operational approaches: "
            "patient observation vs calculated risk vs improvisation.\n"
            "- Plant one environmental detail that could become a "
            "complication or advantage in the next turn."
        ),
    },
    "social": {
        "pacing": (
            "PACING: Social. Dialogue-forward, NPC voice prominent. "
            "Subtext matters more than action. Let character warmth and "
            "humor breathe when the relationship supports it. "
            "350-500 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"Doss didn't look at you when he said it. He looked at the "
            "drink he wasn't drinking, and his fingers made a pattern on "
            "the glass that you recognized as the nervous habit of a man "
            "deciding how much truth he could afford.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- NPC interactions MUST reflect their mechanical disposition. "
            "Disposition below 0.5 = visible friction or reluctance. "
            "Conflicted states express both dimensions simultaneously.\n"
            "- What is NOT said carries as much weight as what is. Write "
            "the subtext.\n"
            "- Choices should include at least one dialogue option "
            "(direct line or conversational approach) that reveals "
            "character values, not just information goals."
        ),
    },
    "exploration": {
        "pacing": (
            "PACING: Exploration. Worldbuilding breathes. Rich "
            "environmental detail — the political economy of a place, "
            "the specific textures that make it real. The character "
            "observes and interprets. 400-600 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"The Red Sector earns its name from the light. Every "
            "surface here reflects some shade of it — the landing "
            "indicators on cargo lifts that never stop running, the "
            "advertisement holos cycling through products you cannot buy "
            "legally on any Core world, the bioluminescent mold that "
            "colonizes the duracrete where the environmental scrubbers "
            "gave up decades ago.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- When introducing environmental or NPC details, prefer "
            "details that could become relevant later over purely "
            "atmospheric ones. Plant seeds.\n"
            "- The character's interiority reads the environment — they "
            "notice what matters to THEM specifically, not generic "
            "observations.\n"
            "- Choices should offer different investigative approaches "
            "that reveal different information based on what the "
            "character prioritizes."
        ),
    },
    "introspection": {
        "pacing": (
            "PACING: Introspection. The character's interiority "
            "dominates. Minimal external action. Honest, specific, "
            "uncomfortable if necessary. No dice check this turn. "
            "300-500 words."
        ),
        "voice_exemplar": (
            "VOICE TARGET — write like this:\n"
            "\"Something had shifted in the weeks since Nar Shaddaa. "
            "Keth read rooms faster now — not just the exits and the "
            "threats but the subtler architecture of who wanted what from "
            "whom. And when he reached for a lie, it came easier. "
            "Cleaner. Like a tool he'd finally learned to hold properly.\""
        ),
        "craft": (
            "SCENE CRAFT:\n"
            "- At least one choice must be reflective — an internal "
            "decision about what the moment means, not what to do next.\n"
            "- Avoid resolving the character's internal conflict FOR "
            "them. Present the tension and let the player choose which "
            "direction to lean.\n"
            "- If a consequence ripple from a prior significant choice "
            "has not yet surfaced, this is a good scene to show its "
            "reach — through the character's thoughts, a rumor, or a "
            "shifted dynamic."
        ),
    },
}


def _get_scene_block(scene_type: str) -> str:
    """Assemble the scene-specific prompt block from SCENE_PACING."""
    entry = SCENE_PACING.get(scene_type, SCENE_PACING["social"])
    return f"{entry['pacing']}\n\n{entry['voice_exemplar']}\n\n{entry['craft']}"


def _make_client() -> tuple[OpenAI, str]:
    """Return (client, model_string) based on active backend/provider."""
    if NARRATIVE_BACKEND == "local":
        return (
            OpenAI(api_key="ollama", base_url=f"{OLLAMA_URL}/v1"),
            LOCAL_MODEL,
        )
    api_key  = (os.getenv("OPENAI_API_KEY") if CLOUD_PROVIDER == "openai"
                else os.getenv("OPENROUTER_API_KEY"))
    base_url = PROVIDER_BASE_URLS.get(CLOUD_PROVIDER)
    return OpenAI(api_key=api_key, base_url=base_url), CLOUD_MODEL


@dataclass
class NarrationResult:
    passage:      str
    choices:      list[str]          # player-facing text (skill tags stripped)
    skill_tags:   list[str | None]   # per-choice skill tag or None if no check
    raw_response: str
    used_local:   bool = False


class CloudGMError(Exception):
    pass


def _build_prompt(ctx: ContextPackage) -> str:
    template       = PROMPT_PATH.read_text()
    recent_summary = _format_recent_turns(ctx.recent_turns)
    full_summary   = f"{ctx.story_summary}\n\nRECENT TURNS:\n{recent_summary}"
    scene_pacing   = _get_scene_block(ctx.scene_type)
    return template.format(
        character_summary=ctx.character.narrative_status(),
        character_voice=ctx.character.voice_notes,
        campaign_name=ctx.arc.campaign_name,
        story_position=f"Part {ctx.arc.current_act} of {ctx.arc.total_acts} — {ctx.arc.act_name}",
        throughline_question=ctx.arc.throughline_question,
        tension_level=ctx.arc.tension_level,
        story_summary=full_summary,
        open_threads=ctx.build_open_threads_block(),
        npc_states=ctx.build_npc_block(),
        location=ctx.location,
        situation=ctx.situation,
        galactic_context=ctx.galactic_context or "No wider context provided for this act.",
        dice_result_block=ctx.build_dice_result_block(),
        scene_pacing=scene_pacing,
        tone_instruction=ctx.tone_instruction,
    )


def _format_recent_turns(turns: list) -> str:
    """Format recent turns for the GM prompt. Includes narration excerpts
    so the GM remembers what it wrote, not just what the player did.
    """
    if not turns:
        return "This is the opening of the story."
    parts = []
    for t in turns[-5:]:
        line = f"Turn {t.turn_number}: {t.player_action}"
        if t.check_made:
            line += f" [{t.check_made}: {t.dice_result}]"
        if t.meaningful_choice_note:
            line += f" → {t.meaningful_choice_note}"
        if t.narration_excerpt:
            line += f"\n  Narration: {t.narration_excerpt}"
        parts.append(line)
    return "\n".join(parts)


def _parse_response(raw: str, used_local: bool = False) -> NarrationResult:
    """
    Split GM response into passage and choices.
    Enforces: delimiter present, 250-600 word count, 2-4 choices.
    Strips skill tags from choice text (e.g., "[Deception]") and stores
    them separately. The player never sees the skill name.
    """
    if "---CHOICES---" not in raw:
        raise CloudGMError("GM response missing ---CHOICES--- delimiter")

    passage, choices_raw = raw.split("---CHOICES---", 1)
    passage     = passage.strip()
    choices_raw = choices_raw.strip()

    word_count = len(passage.split())
    if word_count < 250:
        raise CloudGMError(
            f"Passage too short ({word_count} words, minimum 250). Retrying."
        )
    if word_count > 600:
        raise CloudGMError(
            f"Passage too long ({word_count} words, maximum 600). Retrying."
        )

    raw_choices = [
        re.sub(r"^\d+[\.\)]\s*", "", line.strip())
        for line in choices_raw.split("\n")
        if line.strip()
    ]
    raw_choices = [c for c in raw_choices if c]

    if len(raw_choices) < 2:
        raise CloudGMError(
            f"GM returned {len(raw_choices)} choice(s). Minimum 2 required. Retrying."
        )

    # Extract and strip skill tags: "[Deception]" at end of choice text
    skill_tag_pattern = re.compile(r"\s*\[([A-Za-z_\s]+)\]\s*$")
    choices = []
    skill_tags = []
    for choice_text in raw_choices[:4]:
        match = skill_tag_pattern.search(choice_text)
        if match:
            choices.append(skill_tag_pattern.sub("", choice_text).rstrip())
            skill_tags.append(match.group(1).strip().lower().replace(" ", "_"))
        else:
            choices.append(choice_text)
            skill_tags.append(None)

    return NarrationResult(
        passage=passage,
        choices=choices,
        skill_tags=skill_tags,
        raw_response=raw,
        used_local=used_local,
    )


def narrate_turn(
    ctx:         ContextPackage,
    max_retries: int = 2,
) -> NarrationResult:
    """
    One call to the configured provider for narration + choices.
    This is the ONE cloud call per turn (or local equivalent).
    Retries with a correction note appended on validation failure.

    Cloud failure fallback (v1.5): If the cloud model is unavailable or
    exceeds the timeout, fall back to the local model for this turn only.
    The next turn reattempts the cloud model. The player never sees an
    error — they get a less polished passage that still honors the dice
    and advances the story. A counter tracks consecutive fallbacks; if 3+
    consecutive turns fall back, the UI surfaces a subtle indicator.
    """
    # If already configured for local, skip fallback logic
    if NARRATIVE_BACKEND == "local":
        return _narrate_with_backend(ctx, max_retries, used_local=True)

    # Attempt cloud first, fall back to local on failure
    try:
        return _narrate_with_backend(ctx, max_retries, used_local=False)
    except (CloudGMError, Exception) as cloud_err:
        import logging
        logging.warning(
            f"Cloud GM failed ({cloud_err}), falling back to local model"
        )
        try:
            return _narrate_with_local_fallback(ctx)
        except Exception as local_err:
            raise CloudGMError(
                f"Both cloud and local failed. "
                f"Cloud: {cloud_err}. Local: {local_err}"
            )


def _narrate_with_backend(
    ctx: ContextPackage, max_retries: int, used_local: bool,
) -> NarrationResult:
    """Core narration logic — extracted for fallback reuse."""
    client, model = _make_client()
    prompt        = _build_prompt(ctx)
    last_error    = None

    for attempt in range(max_retries + 1):
        messages = [{"role": "user", "content": prompt}]
        if attempt > 0 and last_error:
            messages.append({
                "role": "user",
                "content": (
                    f"Your previous response was rejected. "
                    f"Reason: {last_error}. Please correct this and try again."
                ),
            })

        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=messages,
            timeout=20.0,  # v1.5: 20-second timeout
        )
        raw = response.choices[0].message.content or ""

        try:
            return _parse_response(raw, used_local=used_local)
        except CloudGMError as e:
            last_error = str(e)
            if attempt == max_retries:
                raise CloudGMError(
                    f"GM failed after {max_retries + 1} attempts. "
                    f"Last error: {last_error}"
                )

    raise CloudGMError("Unreachable")


def _narrate_with_local_fallback(ctx: ContextPackage) -> NarrationResult:
    """
    Emergency fallback: narrate via local model when cloud is unavailable.
    Uses a simplified prompt optimized for the local model's capability.
    Output quality will be lower but the turn advances.
    """
    import httpx
    simplified_prompt = (
        f"You are the narrator for a Star Wars RPG. Write in second person "
        f"present tense, 250-400 words.\n\n"
        f"SITUATION: {ctx.situation}\n"
        f"LOCATION: {ctx.location}\n"
        f"{ctx.build_dice_result_block()}\n\n"
        f"Write the passage, then on a new line write ---CHOICES--- "
        f"followed by 2-3 short choices.\n"
    )
    response = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": LOCAL_MODEL,
            "prompt": simplified_prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 1200},
        },
        timeout=30.0,
    )
    response.raise_for_status()
    raw = response.json()["response"].strip()
    return _parse_response(raw, used_local=True)


def narrate_turn_stream(ctx: ContextPackage) -> Iterator[str]:
    """
    Streaming version — yields text chunks via SSE.
    Caller collects chunks, then calls _parse_response on the full text.

        full_text = ""
        for chunk in narrate_turn_stream(ctx):
            full_text += chunk
            send_to_client(chunk)
        result = _parse_response(full_text)
    """
    client, model = _make_client()
    stream = client.chat.completions.create(
        model=model,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": _build_prompt(ctx)}],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
```

---

## 8. Phase 4 — State and Persistence

### 8.1 `state/db.py`

WAL mode is set on every connection. This allows concurrent reads during
background compression writes, preventing locked-database errors.

```python
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "./data/storyteller.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,
    campaign_name  TEXT NOT NULL,
    character_json TEXT NOT NULL,
    arc_state_json TEXT NOT NULL,
    destiny_light  INTEGER DEFAULT 0,
    destiny_dark   INTEGER DEFAULT 0,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT    NOT NULL REFERENCES sessions(id),
    turn_number      INTEGER NOT NULL,
    player_action    TEXT    NOT NULL,
    choice_index     INTEGER,
    check_skill      TEXT,
    check_difficulty TEXT,
    dice_pool_json   TEXT,
    roll_result_json TEXT,
    narration        TEXT NOT NULL,
    choices_json     TEXT NOT NULL,
    skill_tags_json  TEXT,
    meaningful_note  TEXT,
    context_json     TEXT,
    scene_type       TEXT,
    moral_weight     INTEGER DEFAULT 0,
    compressed       INTEGER DEFAULT 0,
    created_at       TEXT NOT NULL
);

-- Distillation training data view (V2 — schema laid now, used later).
-- Each row pairs the full context package sent to the cloud GM with the
-- narration it produced. scene_type and dice metadata enable filtered
-- dataset construction (e.g. "only combat scenes with failures").
-- Populated automatically by log_turn when NARRATIVE_BACKEND != local.
CREATE VIEW IF NOT EXISTS distillation_pairs AS
SELECT
    t.session_id,
    t.turn_number,
    t.context_json,
    t.narration,
    t.scene_type,
    t.check_skill,
    t.check_difficulty,
    t.roll_result_json,
    t.created_at
FROM turns t
WHERE t.context_json IS NOT NULL
ORDER BY t.created_at;

CREATE TABLE IF NOT EXISTS npc_states (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    npc_name   TEXT NOT NULL,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(session_id, npc_name)
);

CREATE TABLE IF NOT EXISTS act_summaries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT    NOT NULL REFERENCES sessions(id),
    act_number     INTEGER NOT NULL,
    summary        TEXT    NOT NULL,
    meaningful_choices TEXT,
    character_drift    TEXT,
    turns_covered  INTEGER NOT NULL,
    created_at     TEXT    NOT NULL,
    UNIQUE(session_id, act_number)
);

CREATE TABLE IF NOT EXISTS reputation_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT NOT NULL REFERENCES sessions(id),
    turn_number    INTEGER NOT NULL,
    summary        TEXT NOT NULL,
    faction_tags   TEXT,
    surfaced_count INTEGER DEFAULT 0,
    created_at     TEXT NOT NULL
);
"""


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Run schema creation. Safe to call on every startup."""
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
```

### 8.2 `state/session.py`

Turn logging and state queries — the glue between SQLite and the GM layer.
Provides everything needed to rebuild a `ContextPackage` from the database.

```python
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from state.db import get_connection
from gm.context import TurnMemory


def create_session(
    campaign_name:  str,
    character_json: str,
    arc_state_json: str,
) -> str:
    """Create a new session and return its ID."""
    session_id = str(uuid.uuid4())
    now        = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sessions "
            "(id, campaign_name, character_json, arc_state_json, "
            " destiny_light, destiny_dark, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 0, 0, ?, ?)",
            (session_id, campaign_name, character_json, arc_state_json, now, now),
        )
        conn.commit()
    return session_id


def log_turn(
    session_id:       str,
    turn_number:      int,
    player_action:    str,
    choice_index:     int,
    narration:        str,
    choices:          list[str],
    check_skill:      str | None = None,
    check_difficulty: str | None = None,
    dice_pool_json:   str | None = None,
    roll_result_json: str | None = None,
    meaningful_note:  str | None = None,
    context_json:     str | None = None,
    scene_type:       str | None = None,
    moral_weight:     int = 0,
    skill_tags_json:  str | None = None,
) -> None:
    """Write one completed turn to the database.

    context_json and scene_type are stored for future distillation training
    data. When NARRATIVE_BACKEND != local, pass the serialized context
    package as context_json so the distillation_pairs view can pair it
    with the cloud-generated narration. This costs nothing at write time
    and avoids expensive backfilling later.
    """
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO turns "
            "(session_id, turn_number, player_action, choice_index, "
            " check_skill, check_difficulty, dice_pool_json, roll_result_json, "
            " narration, choices_json, skill_tags_json, meaningful_note, "
            " context_json, scene_type, moral_weight, compressed, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (
                session_id, turn_number, player_action, choice_index,
                check_skill, check_difficulty, dice_pool_json, roll_result_json,
                narration, json.dumps(choices), skill_tags_json, meaningful_note,
                context_json, scene_type, moral_weight, now,
            ),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
        )
        conn.commit()


def get_recent_turns(session_id: str, limit: int = 5) -> list[TurnMemory]:
    """Return most recent uncompressed turns in chronological order.
    Includes a narration excerpt (first 2-3 sentences) for narrative
    continuity — the cloud GM needs to know what it said, not just
    what the player did (evaluation §2.2).
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT turn_number, player_action, narration, check_skill, "
            "roll_result_json, meaningful_note "
            "FROM turns WHERE session_id = ? AND compressed = 0 "
            "ORDER BY turn_number DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()

    turns = []
    for row in reversed(rows):
        result_data = (json.loads(row["roll_result_json"])
                       if row["roll_result_json"] else {})
        # Extract first 2-3 sentences as narration excerpt
        narration = row["narration"] or ""
        sentences = narration.split(". ")
        excerpt = ". ".join(sentences[:3]).strip()
        if excerpt and not excerpt.endswith("."):
            excerpt += "."
        turns.append(TurnMemory(
            turn_number=row["turn_number"],
            player_action=row["player_action"],
            narration_excerpt=excerpt,
            check_made=row["check_skill"],
            dice_result=result_data.get("narrative_label"),
            outcome_quadrant=result_data.get("outcome_quadrant"),
            meaningful_choice_note=row["meaningful_note"] or "",
        ))
    return turns


def get_act_summaries(session_id: str) -> str:
    """
    Return all act summaries as a single story_summary string for context
    package injection. Returns empty string if no summaries exist yet.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT act_number, summary FROM act_summaries "
            "WHERE session_id = ? ORDER BY act_number ASC",
            (session_id,),
        ).fetchall()

    if not rows:
        return ""
    return "\n\n".join(f"Act {r['act_number']}: {r['summary']}" for r in rows)


def get_session(session_id: str) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()


def get_turn_count(session_id: str) -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM turns WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
```

### 8.3 `state/memory.py`

```python
import asyncio
import json
import logging
import os
import httpx
from state.db import get_connection

COMPRESSION_THRESHOLD = 8
OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen3.5:9b")

COMPRESSION_PROMPT = """
You are summarizing turns from a narrative RPG session for long-term memory.

TURNS TO COMPRESS:
{turns_text}

Write a concise summary (100-150 words) covering:
1. What happened (key events only, no padding)
2. Which meaningful choices the player made and what they implied about character
3. What changed in the world or NPC relationships

Write in past tense. Be specific. Prioritize consequences over actions.
Do not use bullet points. Plain prose only.
"""


def should_compress(session_id: str) -> bool:
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM turns WHERE session_id = ? AND compressed = 0",
            (session_id,),
        ).fetchone()[0]
    return count >= COMPRESSION_THRESHOLD


def compress_act_turns(session_id: str, act_number: int) -> None:
    """
    Compress uncompressed turns into an act summary using the local model.
    No cloud call. Marks turns as compressed after writing the summary.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT turn_number, player_action, check_skill, "
            "roll_result_json, meaningful_note "
            "FROM turns WHERE session_id = ? AND compressed = 0 "
            "ORDER BY turn_number ASC",
            (session_id,),
        ).fetchall()

    if not rows:
        return

    lines = []
    for row in rows:
        line   = f"Turn {row['turn_number']}: {row['player_action']}"
        result = (json.loads(row["roll_result_json"])
                  if row["roll_result_json"] else {})
        if row["check_skill"]:
            line += f" [{row['check_skill']}: {result.get('outcome_quadrant', '?')}]"
        if row["meaningful_note"]:
            line += f" — {row['meaningful_note']}"
        lines.append(line)

    response = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model":  LOCAL_MODEL,
            "prompt": COMPRESSION_PROMPT.format(turns_text="\n".join(lines)),
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 300},
        },
        timeout=45.0,
    )
    response.raise_for_status()
    summary = response.json()["response"].strip()

    turn_numbers = [row["turn_number"] for row in rows]
    placeholders = ",".join("?" * len(turn_numbers))

    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO act_summaries "
            "(session_id, act_number, summary, turns_covered, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (session_id, act_number, summary, len(rows)),
        )
        conn.execute(
            f"UPDATE turns SET compressed = 1 "
            f"WHERE session_id = ? AND turn_number IN ({placeholders})",
            (session_id, *turn_numbers),
        )
        conn.commit()


async def compress_if_needed(session_id: str, act_number: int) -> None:
    """
    Non-blocking wrapper. Always call via FastAPI BackgroundTasks — never await
    inline. Errors are logged but never propagate; failed compression means
    context grows slightly, not that the game breaks.
    """
    if not should_compress(session_id):
        return
    try:
        loop = asyncio.get_running_loop()   # Python 3.10+ — not get_event_loop()
        await loop.run_in_executor(
            None, compress_act_turns, session_id, act_number
        )
    except Exception as e:
        logging.error(
            f"Memory compression failed for session {session_id}: {e}"
        )
```

**How the API uses this (Phase 5):**

```python
# In the /turn route, after writing to DB:
background_tasks.add_task(
    compress_if_needed,
    session_id=session_id,
    act_number=arc_state.current_act,
)
```

---

## 9. Phase 5 — API Routes

`api/main.py` — Three routes. Nothing else until all three work.

```
POST /session
  Body:    { campaign_name, character_id }
  Returns: { session_id, opening_narration, choices }

POST /session/{session_id}/turn
  Body:    { choice_index }
  Returns: { narration, choices, dice_result (optional), session_state,
             used_local_narration }
  Triggers background compression after writing to DB.

GET /session/{session_id}
  Returns: { session_state, recent_turns, arc_state }

Streaming variant:
POST /session/{session_id}/turn/stream
  Returns: SSE stream of text chunks, then final JSON event
```

`used_local_narration` in the turn response lets the frontend show the local
narration warning without the backend needing to know about UI state.

### 9.1 Turn Orchestration — `POST /session/{session_id}/turn`

The turn handler chains every component in this exact order. This is
the core game loop.

```python
async def handle_turn(session_id: str, choice_index: int, background_tasks):
    """
    Complete turn handler. Steps are sequential and must not be reordered.
    The physics-before-imagination invariant is enforced by steps 1-5
    completing before step 6 (narration).
    """
    # ── Step 0: Load session state ────────────────────────────────────
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")

    character = Character.model_validate_json(session["character_json"])
    arc_state = json.loads(session["arc_state_json"])
    spine = load_campaign_spine(session["campaign_name"])
    current_act = spine["acts"][arc_state["current_act"] - 1]

    # ── Step 1: Resolve the player's choice ───────────────────────────
    # Get the choices from the most recent turn
    last_turn = get_most_recent_turn(session_id)
    previous_choices = json.loads(last_turn["choices_json"])
    previous_skill_tags = json.loads(last_turn.get("skill_tags_json") or "[]")
    player_action = previous_choices[choice_index]

    # ── Step 2: Build scene description for local GM ──────────────────
    # Combine: last turn's narration (what just happened) + player's
    # choice (what they're doing now). This is the "current scene" the
    # local model evaluates.
    scene_description = (
        f"PREVIOUS: {last_turn['narration'][-500:]}\n\n"
        f"THE PLAYER CHOSE: {player_action}"
    )

    # ── Step 3: Check decision (local model) ──────────────────────────
    recent_turns = get_recent_turns(session_id, limit=5)
    recent_failure_count = sum(
        1 for t in recent_turns[-3:]
        if t.outcome_quadrant and t.outcome_quadrant.startswith("failure")
    )

    check_decision = decide_check(
        character=character,
        scene_description=scene_description,
        player_action=player_action,
        arc_state=arc_state,
        recent_failure_count=recent_failure_count,
    )

    # ── Step 4: Dice resolution (if check required) ───────────────────
    dice_pool = None
    roll_result = None

    if check_decision.requires_check:
        check_request = CheckRequest(
            skill=check_decision.skill,
            difficulty=DIFFICULTY_LABELS[check_decision.difficulty],
            boost_dice=check_decision.boost_dice,
            setback_dice=check_decision.setback_dice,
        )
        dice_pool = build_pool(character, check_request)
        roll_result = roll_pool(dice_pool)

        # Apply mechanical consequences (wounds, strain) — physics first
        if roll_result.outcome_quadrant in ("failure_threat", "success_threat"):
            if abs(roll_result.net_advantages) >= 2:
                character.current_strain = min(
                    character.current_strain + 1,
                    character.strain_threshold,
                )

    # ── Step 5: Assemble context package ──────────────────────────────
    story_summary = get_act_summaries(session_id)
    npc_states = load_npc_states(session_id, spine)

    ctx = ContextPackage(
        character=character,
        arc=ArcState(
            campaign_name=spine["name"],
            current_act=arc_state["current_act"],
            total_acts=spine["total_acts"],
            act_name=current_act["name"],
            act_progress=arc_state.get("act_progress", 0.0),
            current_anchor=current_act["anchor"],
            next_anchor=current_act.get("next_anchor", ""),
            anchors_completed=arc_state.get("anchors_completed", []),
            throughline_question=spine["throughline_question"],
            tension_level=current_act["tension"],
            open_threads=[
                ThreadState(name=t) if isinstance(t, str) else t
                for t in (
                    current_act.get("open_threads", [])
                    + arc_state.get("dynamic_threads", [])
                )
            ],
            closed_threads=arc_state.get("closed_threads", []),
        ),
        story_summary=story_summary,
        recent_turns=recent_turns,
        active_npcs=npc_states,
        location=arc_state.get("current_location", ""),
        situation=scene_description,
        galactic_context=current_act.get("galactic_context", ""),
        scene_type=check_decision.scene_type,
        dice_pool=dice_pool,
        roll_result=roll_result,
    )

    # ── Step 6: Narrate (cloud model — one call) ─────────────────────
    narration_result = narrate_turn(ctx)

    # ── Step 7: Persist ──────────────────────────────────────────────
    turn_number = get_turn_count(session_id) + 1

    log_turn(
        session_id=session_id,
        turn_number=turn_number,
        player_action=player_action,
        choice_index=choice_index,
        narration=narration_result.passage,
        choices=narration_result.choices,
        check_skill=check_decision.skill if check_decision.requires_check else None,
        check_difficulty=check_decision.difficulty if check_decision.requires_check else None,
        dice_pool_json=json.dumps(asdict(dice_pool)) if dice_pool else None,
        roll_result_json=json.dumps(asdict(roll_result)) if roll_result else None,
        context_json=json.dumps(asdict(ctx)) if NARRATIVE_BACKEND != "local" else None,
        scene_type=check_decision.scene_type,
        moral_weight=check_decision.moral_weight,
        skill_tags_json=json.dumps(narration_result.skill_tags),
    )

    # ── Step 8: Update session state ──────────────────────────────────
    # Update character (wounds/strain may have changed)
    # Update arc state (act_progress, location, etc.)
    update_session_state(session_id, character, arc_state)

    # ── Step 9: Background tasks ──────────────────────────────────────
    background_tasks.add_task(
        compress_if_needed, session_id, arc_state["current_act"]
    )

    # ── Step 10: NPC state update (V1 minimal reconciliation) ────────
    # In V1, NPC knowledge updates only (no disposition drift, no
    # emotional state). The local model infers which NPCs learned
    # new information from this turn's narration.
    background_tasks.add_task(
        update_npc_knowledge, session_id, narration_result.passage, npc_states
    )

    # ── Return ────────────────────────────────────────────────────────
    return {
        "narration": narration_result.passage,
        "choices": narration_result.choices,
        "dice_result": describe_pool_for_display(dice_pool) if dice_pool else None,
        "roll_summary": roll_result.narrative_label() if roll_result else None,
        "session_state": {
            "turn_number": turn_number,
            "wounds": character.current_wounds,
            "strain": character.current_strain,
        },
        "used_local_narration": narration_result.used_local,
    }
```

**Helper functions referenced above:**

`load_campaign_spine(name)` — reads the spine JSON from
`data/campaigns/{name}.json`. Validates basic structure.

`load_npc_states(session_id, spine)` — loads NPC states from the
`npc_states` table for this session. On the first turn, initializes from
the spine's `npc_roster` (using `disposition_start`, `knows_at_start`,
`doesnt_know_at_start`, `voice_notes`, `behavioral_envelope`,
`motivation`).

`get_most_recent_turn(session_id)` — returns the most recent turn row
from the `turns` table for this session.

`update_session_state(session_id, character, arc_state)` — writes
updated character JSON and arc state JSON back to the `sessions` table.

`update_npc_knowledge(session_id, narration, npc_states)` — V1 minimal
reconciliation. Calls the local model with the narration text and
current NPC knowledge states. The local model returns a JSON list of
knowledge updates (which NPC learned what). Updates the `npc_states`
table. This runs as a background task and does not block the response.

**Location tracking (V1):** `current_location` is stored in
`arc_state_json` and initialized from the current act's
`opening_location`. In V1, location resets to the act's
`opening_location` at act transitions. Within an act, the cloud GM
may describe movement, but the `current_location` field does not update
automatically — the prose provides location context through the
`situation` field, which carries the most recent narration. Post-V1,
the reconciliation system (Phase 7) will infer location changes from
narration and update the field between turns.

**Reconciliation error budget (post-V1):** The local model (9B) performs
reconciliation tasks: NPC knowledge updates, disposition shifts, story
progress, thread tracking. These are high-abstraction inference tasks
where the model analyzes literary prose and infers state changes. Error
rate will be non-zero.

Acceptable error budget: ~2-3 errors per 10-turn act before the player
notices inconsistency (an NPC referencing something they shouldn't know,
a thread contradicting established facts). If the local model's error
rate exceeds ~20% on reconciliation tasks during Phase 7 testing, the
system supports **selective cloud routing**: critical reconciliation
decisions (NPC knowledge updates after deception checks, anchor
proximity at late-act progress >0.7, thread resolution) can be routed
to the cloud model as a lightweight JSON-schema-enforced call. This
adds a second cloud call on ~10-20% of turns — a controlled exception
to the one-cloud-call rule, justified by the alternative being
accumulated state corruption.

The routing decision is configurable via `RECONCILIATION_ROUTING`:
`local` (default, all reconciliation via local model), `selective`
(critical decisions via cloud), `cloud` (all reconciliation via cloud,
highest accuracy, highest cost). This is a Phase 7 configuration
decision based on empirical testing of the local model's accuracy on
reconciliation tasks.

### 9.2 Session Creation — `POST /session`

```python
async def handle_create_session(campaign_name: str, character_id: str):
    """
    Create a new session and generate the opening narration.
    """
    # ── Load campaign and character data ──────────────────────────────
    spine = load_campaign_spine(campaign_name)
    character = load_character(character_id)
    act_1 = spine["acts"][0]

    # ── Initialize arc state ──────────────────────────────────────────
    arc_state = {
        "current_act": 1,
        "act_progress": 0.0,
        "anchors_completed": [],
        "closed_threads": [],
        "dynamic_threads": [],
        "current_location": act_1.get("opening_location", ""),
    }

    # ── Create session in database ────────────────────────────────────
    session_id = create_session(
        campaign_name=campaign_name,
        character_json=character.model_dump_json(),
        arc_state_json=json.dumps(arc_state),
    )

    # ── Initialize NPC states from spine roster ───────────────────────
    for npc_data in spine.get("npc_roster", []):
        save_npc_state(session_id, NPCState(
            name=npc_data["name"],
            knows=npc_data.get("knows_at_start", []),
            doesnt_know=npc_data.get("doesnt_know_at_start", []),
            disposition=npc_data.get("disposition_start", 0.5),
            last_seen_turn=0,
            voice_notes=npc_data.get("voice_notes", ""),
            motivation=npc_data.get("motivation", ""),
            behavioral_envelope=npc_data.get("behavioral_envelope", []),
        ))

    # ── Resolve variation points (e.g. Doss's fate) ───────────────────
    # V1: random selection for variation points with
    # selection_method="randomly_determined"
    resolve_initial_variations(session_id, spine)

    # ── Build opening context package ─────────────────────────────────
    # No player action, no dice, no prior turns. The opening_situation
    # from Act 1 drives the first passage.
    npc_states = load_npc_states(session_id, spine)

    ctx = ContextPackage(
        character=character,
        arc=ArcState(
            campaign_name=spine["name"],
            current_act=1,
            total_acts=spine["total_acts"],
            act_name=act_1["name"],
            act_progress=0.0,
            current_anchor=act_1["anchor"],
            next_anchor=act_1.get("next_anchor", ""),
            anchors_completed=[],
            throughline_question=spine["throughline_question"],
            tension_level=act_1["tension"],
            open_threads=[
                ThreadState(name=t) for t in act_1.get("open_threads", [])
            ],
            closed_threads=[],
        ),
        story_summary="",
        recent_turns=[],
        active_npcs=npc_states,
        location=arc_state["current_location"],
        situation=act_1["opening_situation"],
        galactic_context=act_1.get("galactic_context", ""),
        scene_type="exploration",  # opening is always exploration
        tone_instruction=(
            "This is the opening of the campaign. Establish the world, "
            "the character's voice, and the immediate situation. Ground "
            "the reader in a specific sensory moment."
        ),
    )

    # ── Generate opening narration (one cloud call) ───────────────────
    narration_result = narrate_turn(ctx)

    # ── Log Turn 0 ────────────────────────────────────────────────────
    log_turn(
        session_id=session_id,
        turn_number=0,
        player_action="[session_start]",
        choice_index=-1,
        narration=narration_result.passage,
        choices=narration_result.choices,
        scene_type="exploration",  # opening is always exploration
        skill_tags_json=json.dumps(narration_result.skill_tags),
        context_json=(json.dumps(asdict(ctx))
                      if NARRATIVE_BACKEND != "local" else None),
    )

    return {
        "session_id": session_id,
        "opening_narration": narration_result.passage,
        "choices": narration_result.choices,
    }
```

**Notes:**

`load_character(character_id)` reads from `data/characters/{id}.json`
and returns a `Character` instance.

`save_npc_state(session_id, npc_state)` writes one NPC state to the
`npc_states` table.

`resolve_initial_variations(session_id, spine)` resolves variation
points with `selection_method: "randomly_determined"` at session
creation (e.g., Doss's fate). Stores the selected option in session
state so it persists.

The opening turn is logged as Turn 0 with `player_action="[session_start]"`
and `choice_index=-1`. This distinguishes it from player-initiated turns
and ensures `get_turn_count` returns the correct number.

The context validation rule "recent_turns must be non-empty except on
Turn 1" (§7.2) is satisfied because Turn 0 is the opening and Turn 1
is the first player-initiated turn (which will have Turn 0 as a recent
turn).

---

## 10. Phase 6 — Frontend

`web/index.html` — Single file, no build step.

```
┌─────────────────────────────────────────┐
│  [Campaign Name]          [≡ Menu]      │
│  [⚠ Local narration — loop test only]  │  ← shown when used_local_narration=true
├─────────────────────────────────────────┤
│                                         │
│  [Prose passage]                        │
│  650px max width, dark bg, light text   │
│                                         │
├─────────────────────────────────────────┤
│  [◆ Show dice result]  ← collapsed      │
│  (only visible when check occurred)     │
│                                         │
│  When expanded:                         │
│  Pool: 2Y 2G 2P   Result: Success +     │
│  [dice symbols grid]   2 Advantages     │
├─────────────────────────────────────────┤
│  [Choice 1 — full text]                 │
│  [Choice 2 — full text]                 │
│  [Choice 3 — full text]                 │
│  [Choice 4 — full text]  (if present)   │
└─────────────────────────────────────────┘
```

Key UI requirements:
- Choices are buttons, not a dropdown
- Prose streams word-by-word when using the SSE endpoint
- Dice panel collapsed by default; only rendered when a check occurred
- Local narration warning visible when `used_local_narration = true`
- No avatars, no maps, no character sheet in V1
- Mobile readable (single column, touch targets ≥ 44px)
- Disable all choice buttons on selection; re-enable on next passage

---

## 11. Configuration

`.env.example`:

```bash
# ── Cloud narration ───────────────────────────────────────────────────────────
NARRATIVE_BACKEND=cloud         # cloud | local  (local = Ollama, loop-test only)
CLOUD_PROVIDER=openai           # openai | openrouter

# OpenAI (CLOUD_PROVIDER=openai)
OPENAI_API_KEY=sk-...
CLOUD_MODEL=gpt-5.2

# OpenRouter (CLOUD_PROVIDER=openrouter)
# OPENROUTER_API_KEY=sk-or-...
# CLOUD_MODEL=x-ai/grok-4.1-fast   # provider/model prefix required for OpenRouter

# ── Local model ───────────────────────────────────────────────────────────────
OLLAMA_URL=http://localhost:11434
LOCAL_MODEL=qwen3.5:9b           # verify quant: ollama show qwen3.5:9b

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH=./data/storyteller.db

# ── Server ────────────────────────────────────────────────────────────────────
PORT=8000
DEV_MODE=true
STREAMING_ENABLED=true
```

`pyproject.toml`:

```toml
[project]
name = "storyteller-v3"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
    "openai>=1.30.0",       # OpenAI-compatible SDK — OpenAI + OpenRouter + Ollama
    "httpx>=0.27.0",        # Ollama calls (local GM + memory compression)
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.4.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## 12. Test Campaign Spine

**Spine model validation:** When `studio/schema.py` exists (post-
Campaign Studio Phase 1), campaign spines should be loaded via the
`CampaignSpine` Pydantic model for type-safe validation. Until then,
the Game Engine loads spine JSON directly and validates against the
structure below. The test spine format aligns with Campaign Studio
Design Document Section 4.

`data/campaigns/nar_shaddaa_job.json`

```json
{
    "name": "The Nar Shaddaa Job",
    "era": "galactic_civil_war",
    "character_id": "keth_varso",
    "total_acts": 4,
    "throughline_question": "Can a man who has only ever looked out for himself become someone worth following?",
    "acts": [
        {
            "number": 1,
            "name": "The Approach",
            "tension": "rising",
            "opening_situation": "Keth has just dropped out of hyperspace above Nar Shaddaa. His contact Doss has gone dark. A sealed cargo container sits in his hold. An unknown voice on the comm has warned him off the original drop coordinates.",
            "opening_location": "Aboard Mira's Luck, approaching Nar Shaddaa orbit",
            "galactic_context": "Imperial customs interdiction has tightened across the Y'Toub system following a Rebel supply intercept at Nal Hutta. Hutt Council territorial disputes between Vossk's faction and the Besadii clan have made landing clearances unpredictable — bribes that worked last month now go to the wrong people. An unrelated freighter explosion at Dock 14 yesterday has every security team on the Promenade running nervous.",
            "anchor": "arrival_with_hot_cargo",
            "next_anchor": "contact_discovered",
            "open_threads": [
                "Who is the mysterious comm voice?",
                "What happened to Doss?",
                "What is actually in the cargo?"
            ]
        },
        {
            "number": 2,
            "name": "The Complication",
            "tension": "critical",
            "opening_location": "Nar Shaddaa, mid-level Promenade district",
            "galactic_context": "A Rebel cell has been broken on the Smuggler's Moon — ISB is running sweeps through the mid-levels. Vossk's patience with late deliveries has become a topic of discussion among his intermediaries, and discussions among Hutts have consequences.",
            "anchor": "contact_discovered",
            "next_anchor": "obligation_triggered",
            "open_threads": []
        },
        {
            "number": 3,
            "name": "The Squeeze",
            "tension": "climax",
            "opening_location": "Nar Shaddaa, lower levels near Vossk's territory",
            "galactic_context": "The Besadii clan has moved on one of Vossk's subsidiary operations in the lower levels, pulling his enforcers away from the Promenade. For a narrow window, Vossk's grip on this district is weaker than it has been in years.",
            "anchor": "obligation_triggered",
            "next_anchor": "resolution_approach",
            "open_threads": []
        },
        {
            "number": 4,
            "name": "The Resolution",
            "tension": "falling",
            "opening_location": "Nar Shaddaa, docking ring and departure corridors",
            "galactic_context": "Imperial customs has announced a 48-hour lockdown of all non-essential departures from Nar Shaddaa. Officially, it is a security sweep. Unofficially, someone important lost something valuable, and nobody leaves until it is found.",
            "anchor": "resolution_approach",
            "next_anchor": "campaign_end",
            "open_threads": []
        }
    ],
    "npc_roster": [
        {
            "name": "Vossk the Patient",
            "role": "Hutt crime lord — Keth's creditor",
            "disposition_start": 0.45,
            "motivation": "Profit and reputation, in that order.",
            "voice_notes": "Always through intermediaries. Formal. Indirect. Never threatens directly — observes possibilities.",
            "behavioral_envelope": [
                "Never appears in person during this campaign",
                "Never makes direct threats — always frames consequences as observations"
            ],
            "knows_at_start": ["Keth owes him", "The job exists", "It is late"],
            "doesnt_know_at_start": ["What is actually in the cargo", "That Doss has gone dark"]
        },
        {
            "name": "Doss",
            "role": "Keth's contact — status unknown at campaign start",
            "disposition_start": 0.65,
            "motivation": "Survival — Doss is in over his head and knows it.",
            "voice_notes": "Half-sentences and nervous deflections. Talks fast when scared. Loyal in his way but self-preservation wins when it has to.",
            "behavioral_envelope": [
                "Never confronts anyone directly — always deflects or runs"
            ],
            "knows_at_start": ["The drop coordinates", "Keth's ship signature"],
            "doesnt_know_at_start": [],
            "resolution": "randomly_determined",
            "options": ["arrested_by_isb", "sold_keth_out", "in_hiding"]
        }
    ]
}
```

---

## 13. Critical Implementation Rules

**Rule 1: One cloud call per turn.**
No exceptions. `NARRATIVE_BACKEND=local` routes this through Ollama — it still
counts as one call. Memory compression runs asynchronously after the turn
commits and does not count toward this limit.

**Rule 2: Validate before passing downstream.**
Every LLM response is validated before use. Bad check decisions never corrupt
the context package. Malformed narration never reaches the frontend.

**Rule 3: The engine has zero LLM dependencies.**
`engine/` is pure Python. Runnable with no API keys and no Ollama running.

**Rule 4: The dice are the truth.**
Failure is narrated as failure. Triumph is narrated as triumph. No softening.

**Rule 5: Fail loud, not silently.**
Garbage JSON after 3 retries = exception. Missing `---CHOICES---` = exception.
Surface errors so they get fixed.

**Rule 6: Simple state, single source of truth.**
All session state lives in SQLite. If the process restarts, the session is
recoverable.

**Rule 7: No premature abstraction.**
The code is FFG-specific. No `RulesSystem` protocol until the FFG vertical
slice is complete and proven.

**Rule 8: Destiny Points are tracked, not spent.**
`destiny_light` and `destiny_dark` exist in the session table. Spending
mechanics are deferred to V2.

**Rule 9: Compression never blocks the player.**
`compress_if_needed` is always a `BackgroundTask`. Compression failure is
logged, not raised. A failed compression means larger context, not a broken game.

**Rule 10: Local narration is for loop testing only.**
`NARRATIVE_BACKEND=local` validates mechanics and parsing. It does not validate
prose quality. Never evaluate game feel against local narration output.

**Rule 11: V1 must not block post-V1 mechanics.**
The Game Mechanics Document (v1.5) specifies nine post-V1 mechanical
systems (Sections 14–22). V1 does not build these systems, but V1 code
must not require refactoring to support them. Three specific constraints:

(a) **Dice engine extensibility.** `engine/dice.py` symbol resolution
must be data-driven (dice types defined by symbol tables, engine
agnostic about what symbols mean). Force dice are already in the symbol
tables and DicePool. Do not hardcode assumptions that every die produces
success/failure/advantage/threat. The Force die produces light/dark
pips, which are resolved by a separate path (Game Mechanics §16).

(b) **Character schema forward-compatibility.** The Character model
already includes `force_rating`, `force_committed`, `total_xp`,
`available_xp`, and `specializations` as a list. These fields must not
be removed or repurposed. The following fields are reserved for post-V1
systems — they may be added to the model at any time but V1 code must
not depend on their absence: `reserved_xp`, `latent_force_sensitive`,
`force_rejected_count`, `force_discovery_phase`, `force_powers`,
`acquired_talents`, `talent_uses`, `advancement_log`, `loadout`,
`active_commitments`.

The NPCState model reserves: `emotional_state` (EmotionalState
dataclass with mood, intensity, source, set_at_turn, decay_rate).
V1 code must not assume NPCs have only disposition-based state.

The turn record reserves: `choice_implications` (Optional[str], JSON
annotation of behavioral meaning), `destiny_light_spent` (bool),
`destiny_dark_spent` (bool). V1 code must not assume these columns
do not exist.

(c) **Context assembly composability.** `gm/context.py` must assemble
the GM prompt from registered context sources rather than a monolithic
string concatenation. Post-V1 systems add new context sources: talent
effects for check decision, talent capabilities and activations for
narration, Force state, aspiration echoes, equipment summary, ship
state, NPC tier-based injection, NPC emotional state, choice
annotations, and Destiny Point narrative notes. Each source must be
insertable without editing the core assembly function. The current
`ContextPackage` dataclass is the right pattern — extend it with
optional fields that default to empty strings and are omitted from
the prompt when empty.

(d) **Pool modification pipeline extensibility.** `engine/checks.py`'s
`build_pool()` must be structured as a sequential pipeline, not a
single monolithic function. Post-V1 stages (in order): base pool →
passive talent modifiers → conditional talent modifiers → Destiny
Point modification → Force dice addition. The function must accept
and return a pool at each stage so new stages can be inserted without
rewriting existing ones. (Game Mechanics §23.5 defines the full
six-stage pipeline.)

---

## 14. Backlog (Do Not Build Yet)

**Game Engine post-V1 items (fully designed in Game Mechanics v1.5):**

The following items have complete design specifications in the Game
Mechanics Document (Sections 14–22) and are ready for implementation
after V1 is proven. Implementation order should follow the tier
structure defined during the design phase:

- **Tier 1:** Character advancement engine and behavioral inference
  (Game Mechanics §14), talent tree system and pool modification
  pipeline (§15)
- **Tier 2:** Force mechanics — dice resolution, dark side temptation,
  Force powers (§16)
- **Tier 3:** Vehicle/starship encounters (§17), equipment and loadout
  system (§18)
- **Tier 4:** Time skip vignettes (§19), cross-era character
  progression (§20), large-scale NPC management (§21), canon character
  profiles (§22)

**Game Engine post-V1 items (not yet designed — implementation
unspecified):**

- Character creation / prologue psychometric system (design exists in
  Game Mechanics §5; implementation unspecified — Campaign Studio
  Phase 4 concern)
- RulesSystem abstraction for non-FFG settings (Phase 5 long-term
  aspiration, no design expected)

**Game Engine post-V1 items (designed, ready for implementation):**

- Obligation trigger system — GM §9, §26 (between-act pipeline step 8)
- Duty trigger system — GM §9, §26 (between-act pipeline step 8)
- Morality drift tracking — GM §9, §26 (between-act pipeline step 10)
- Semantic memory / meaningful choice extraction — GM §24
- Destiny Point spending mechanics — GM §23
- Faction state tracking — Gap Analysis v1.1 (FactionState model,
  reconciliation integration, galactic context injection)
- Character-centric campaign management — Gap Analysis v1.1
  (character as primary entity, `characters` and `character_campaigns`
  tables, character screen UI)
- Settings / API key management UI — Gap Analysis v1.1
  (`state/settings.py`, encrypted key storage, test connection)
- NPC relationship triangles — Gap Analysis v1.1 (`npc_dispositions`
  on NPCState, campaign spine `npc_relationships`)
- NPC information propagation — Gap Analysis v1.1
  (`social_connections` graph, one-hop act-boundary propagation)
- Distillation evaluation failure taxonomy — Gap Analysis v1.1
  (five binary categories, 50+ narration test set)
- **Turn counter for spine advancement** — Gap Analysis v2.0.
  `PacingSignal` model with deterministic pacing zone (early,
  on_pace, late, overdue) computed from `turns_this_act` and
  `expected_turns`. Removes arithmetic from local model. Zone injected
  into reconciliation and narration prompts with delta modifier
  guidance. New file: `engine/pacing.py`. Extend:
  `engine/reconciliation.py`, `gm/prompts/reconciliation.txt`,
  `gm/context.py`.
- **Narration distillation pipeline** — LLM Eval §8.4, Backlog 2.14.
  QLoRA fine-tune of the local model using cloud-generated
  context→narration pairs collected during V1 play. Goal: handle
  lower-stakes scene types (exploration, transitions) locally, reserve
  cloud for climactic beats. Depends on the `distillation_pairs` view
  being populated during normal V1 sessions. Minimum dataset: 500–1000
  curated pairs. Curation dual-filter spec designed (Backlog 2.15).
- **Generative entity persistence** — Gap Analysis v2.0. Reconciliation
  prompt extension for entity detection (low/medium/high significance).
  Entity card generation prompt per type. SQLite `emergent_entities`
  table with per-act cap (max 3). Tier promotion logic (3→2→1 based on
  reference count). Reintroduction injection formats for NPCs,
  locations, and facts. New files: `engine/entities.py`,
  `gm/prompts/entity_card_gen.txt`. Extend: `state/db.py`,
  `gm/prompts/reconciliation.txt`, `gm/context.py`,
  `engine/reconciliation.py`. Evaluate need after Milestone 1
  playtesting.
- **Campaign rating and feedback system (Game Engine side)** — Gap
  Analysis v2.0. Post-completion rating collection (1–5 overall,
  optional 3-dimension breakdown, optional free-text). SQLite
  `campaign_ratings` table. Rating card UI at campaign completion.
  New file: `state/ratings.py`. Extend: `state/db.py`,
  `web/index.html`, `api/game_routes.py`. Campaign Studio side
  (exemplar selection, generation prompt integration) specified
  separately in CS Implementation.

**Items migrated to Campaign Studio Implementation Document:**

The following items previously in this backlog are now fully specified
in `STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md`:

- Campaign spine generator (Studio Phases 2, 5, 6)
- NPC voice generation (Studio §15 Backlog)
- Multi-arc campaign structure (Studio §4, Phase 7)

**Items implemented (removed from backlog):**

- ~~Local model fallback for cloud outage~~ — Implemented in v1.5 as
  the cloud failure fallback path (Section 7.3)

---

## 14.5. Known V1 Limitations (Correctly Deferred)

The following Vision Document commitments are intentionally absent from
V1. They are documented here so they are not mistaken for oversights
during implementation.

**Deferral 1 — Reputation Echoes** (Vision §1, §11). NPCs the player
has never met reference things the player did. The `reputation_log`
table exists but nothing populates it and the narration prompt does not
receive reputation entries. **Becomes real:** Phase 7 (Post-Turn
Reconciliation).

**Deferral 2 — Within-Act Pacing Arc** (Vision §13). Hook → rising
middle → the turn → cliffhanger within each act. V1 has a static
`tension` field per act. Dynamic within-act pacing requires
`act_progress` tracking and pacing guidance from Phase 7.

**Deferral 3 — Meaningful Choice Tagging** (Vision §16). The system
infers behavioral meaning from each player choice. The
`meaningful_note` field exists on turns. The `choice_implications` field
is reserved. **Becomes real:** Phase 13 (Semantic Memory).

**Deferral 4 — Conditional Choice Availability from Patterns** (Vision
§7). Some choices are only available because of accumulated behavioral
patterns. V1 choices are constrained by character state and NPC state
but not by accumulated behavioral fingerprints. **Becomes real:** Phase
13 (Semantic Memory).

**Deferral 5 — Scene-Type-Aware Context Assembly Routing** (Game
Mechanics §10). Kinetic/balanced/reflective prompt assembly profiles
that modulate which context fields are emphasized. The scene type field
and pacing guidance now exist (v2.1), but the routing that shifts
context field emphasis per scene type is deferred to late V1 or Phase 7.

---

## 15. Success Criteria for V1

V1 is complete when:

1. A player can start a session as Keth Varso
2. The opening passage of The Nar Shaddaa Job appears in the browser
3. The player can select a choice
4. The local model correctly identifies whether a check is needed
5. If a check is needed, the dice pool is built correctly per FFG rules
6. The dice are rolled and the symbols are correct
7. The cloud GM narrates the outcome, honoring the dice result
8. The dice panel shows the actual roll on demand
9. New choices appear that are specific to this scene
10. This loop repeats for at least 5 turns without errors
11. The session persists across a process restart
12. `NARRATIVE_BACKEND=local` runs the full loop without cloud credits

If all 12 criteria are met, V1 is done. Everything else is V2.

---

*Document version: 2.5*
*Project: Storyteller V3 — Game Engine*
*Do not modify the build order.*

---

## 16. Revision History

**v2.5 — Design gap analysis v2.0 backlog integration (March 2026)**

1. **§14 backlog reorganized.** "Not yet designed" section reduced to
   two items (prologue system implementation unspecified, RulesSystem
   abstraction deferred). Narration distillation pipeline (2.14) and
   generative entity persistence (2.28) moved to "designed" section —
   both now have full specs.

2. **Three new items added to designed backlog.** Turn counter for
   spine advancement (2.19 — `PacingSignal` model, `engine/pacing.py`),
   generative entity persistence (2.28 — reconciliation prompt
   extension, `emergent_entities` table, tier promotion), campaign
   rating system Game Engine side (3.28 — `campaign_ratings` table,
   `state/ratings.py`, rating card UI).

3. **Gap Analysis references updated.** All references to Design Gap
   Analysis §Tier N updated to reference "Gap Analysis v1.1" or "Gap
   Analysis v2.0" explicitly, matching the current document structure.

**v2.4 — Evaluation risk mitigations (March 2026)**

1. **Prompt constraint rotation implemented** — The narration prompt's
   YOUR TASK section now contains only 7 hard constraints (always active).
   Scene-specific craft constraints (NPC fidelity, forward-echoing,
   consequence ripple, and others) rotate based on scene type via the
   `SCENE_PACING` dict. Each scene type gets 3 craft instructions relevant
   to that scene, rather than all 10+ constraints on every turn. Reduces
   prompt cognitive load per independent evaluation §2.1.

2. **Style exemplars added to scene pacing** — Each scene type in
   `SCENE_PACING` now includes a `voice_exemplar` field: 1-2 sentences
   of prose in the target register that the model can use as a style
   anchor. Addresses the single-voice problem (evaluation §2.5) by
   giving the model a concrete example rather than just a description.

3. **Memory cliff mitigated** — `TurnMemory` gains `narration_excerpt`
   (first 2-3 sentences of each passage). `get_recent_turns()` now
   fetches narration text and extracts excerpts. `_format_recent_turns()`
   includes excerpts in the GM prompt. The cloud GM now remembers what
   it wrote, not just what the player did. Addresses evaluation §2.2.

4. **Thread state enriched** — `open_threads` upgraded from `list[str]`
   to `list[ThreadState]` with `player_knows` and `player_unknown`
   fields. `build_open_threads_block()` outputs structured thread state
   giving the GM information asymmetry data for tension maintenance.
   Spine threads converted to ThreadState at session creation.

5. **Character Through Tactics in prompt** — Choice rules now include
   a compressed good-vs-bad example drawn from Vision §7, plus the
   principle: "the tactical decision and the identity decision must be
   the SAME choice." Addresses evaluation §2.3.

6. **Selective cloud routing for reconciliation designed** — Error
   budget analysis framework added. `RECONCILIATION_ROUTING` config
   (`local`/`selective`/`cloud`) supports routing critical reconciliation
   decisions to the cloud model if local model error rate exceeds 20%.
   Addresses evaluation §2.4.

7. **`SCENE_PACING` restructured** — Changed from flat string dict to
   structured dict with `pacing`, `voice_exemplar`, and `craft` keys.
   New `_get_scene_block()` helper assembles the complete scene block.

**v2.3 — Final pre-build sweep (March 2026)**

1. **Opening narration scene_type fixed** — Session creation flow (§9.2)
   now sets `scene_type="exploration"` on the ContextPackage before
   generating the opening narration. Previously defaulted to "social",
   giving the cloud GM social pacing guidance instead of exploration
   pacing for the opening passage.

2. **`skill_tags_json` folded into `log_turn()`** — `skill_tags_json`
   parameter added to `log_turn()` signature and INSERT statement.
   Eliminates the separate `store_skill_tags()` helper. Single atomic
   INSERT instead of INSERT + UPDATE.

3. **Backlog section §14 cleaned up** — Items now designed (Obligation,
   Duty, Morality, Semantic Memory, Destiny Points) moved from "not yet
   designed" to new "designed, ready for implementation" subsection.
   "Multiple career/species options" removed (now the character funnel
   system, fully designed in GM §5 and CS Design §2.5).

**v2.2 — Schema fixes from logic analysis (March 2026)**

1. **`skill_tags_json` column added to `turns` table** — Required by
   the turn orchestration flow (§9.1) to persist per-choice skill tag
   hints for the next turn's check decision.

2. **`reputation_log` schema updated** — Added `faction_tags TEXT` and
   `surfaced_count INTEGER DEFAULT 0` columns per the reputation echo
   delivery mechanism (Game Mechanics §1.1).

**v2.1 — Vision alignment pass (March 2026)**

1. **Scene type pacing wired to narration prompt** — `scene_type` field
   added to `ContextPackage`. `SCENE_PACING` lookup dict added to
   `cloud_gm.py` mapping each scene type to prose voice and pacing
   guidance derived from Vision §3 (author registers) and Game Mechanics
   §10. `_build_prompt()` populates `{scene_pacing}` in the narration
   template. The six scene types now actively modulate the GM's prose
   output rather than being classified and discarded.

2. **Anti-AI-slop prohibition added to narration prompt** — Explicit
   banned phrase list and generic-language prohibition added to the
   prompt's voice section. Implements the Vision §3 "absolute
   prohibition" on AI house style. Twelve specific patterns banned.
   Positive voice instruction retained; negative list added as defense
   in depth.

3. **Introspection choice guidance added** — Choice rules section of
   narration prompt now includes guidance for generating reflective
   choices during introspection scenes or after major events. Three
   worked examples of introspection choice texture. Implements the
   Vision §7 introspection choices design.

4. **Game terminology quarantined from prose** — `ACT:` label in
   narration prompt replaced with `STORY POSITION:`. Format parameters
   consolidated from `current_act`/`total_acts`/`act_name` to single
   `story_position` string using neutral "Part X of Y" framing.
   Explicit instruction added: "Never use the words 'act,' 'chapter,'
   'session,' 'turn,' or any structural game terminology in your prose."
   Implements the Vision's invisible mechanics principle at the prompt
   level.

5. **V1 deferrals documented** — New Section 14.5 lists five Vision
   commitments intentionally absent from V1 (reputation echoes,
   within-act pacing arc, meaningful choice tagging, conditional choice
   availability, scene-type-aware context assembly routing) with the
   phase where each becomes real.

**v2.0 — Pre-build audit fixes (March 2026)**

1. **Narration prompt template completed** — Five prompt additions from
   Game Mechanics (§1, §4, §7) added to narration template in §7.1:
   turn-level consequence reflection (item 7), NPC disposition fidelity /
   anti-positivity-bias (item 8), forward-echoing (item 9), consequence
   ripple (item 10), and risk signaling in choice text. These were
   designed in Game Mechanics and tracked in the Backlog (items 1.17–1.21)
   but never added to the actual prompt template.

2. **`moral_weight` wired to database** — `log_turn()` in §8.2 now
   accepts `moral_weight: int` parameter and includes it in the INSERT
   statement. Previously, the value was computed in the check decision
   and silently discarded.

3. **Turn orchestration specified** — §9.1 added: complete turn handler
   pseudocode showing the exact step order from session load through
   check decision, dice resolution, context assembly, narration, state
   persistence, and background tasks. Defines six helper functions.

4. **Session creation flow specified** — §9.2 added: complete session
   creation handler including NPC initialization from spine roster,
   variation point resolution, opening context package assembly, Turn 0
   logging, and opening narration generation.

5. **Location tracking specified** — `opening_location` field added to
   test campaign spine acts. `current_location` tracked in arc state JSON.
   V1 location resets at act transitions; post-V1 reconciliation (Phase 7)
   will infer location changes from narration.

6. **`build_pool()` restructured as pipeline** — §5.3 rewritten with
   `_stage_1_base_pool()` as an extracted function and `build_pool()` as
   the pipeline orchestrator with commented Stage 2-5 insertion points.
   Satisfies Rule 11d without premature abstraction.

**v1.9 — Retrofit-risk field reservations (March 2026)**

1. **Rule 11b expanded.** NPCState reserves `emotional_state` field
   (EmotionalState dataclass). Turn record reserves
   `choice_implications` (semantic memory annotation),
   `destiny_light_spent`, `destiny_dark_spent`. V1 code must not
   assume these do not exist.

2. **Rule 11c expanded.** Context assembly composability note updated
   with additional sources: NPC emotional state, choice annotations,
   Destiny Point narrative notes.

3. **Rule 11d added.** Pool modification pipeline extensibility —
   `build_pool()` must be structured as a sequential pipeline with
   insertable stages. Six-stage order defined in Game Mechanics §23.5.

**v1.8 — Post-V1 architectural awareness and backlog update (March 2026)**

1. **Rule 11 added to Section 13:** "V1 must not block post-V1
   mechanics." Three specific forward-compatibility constraints for
   V1 code: dice engine extensibility for Force dice, character schema
   field reservations for nine post-V1 systems, and context assembly
   composability for new context sources. References Game Mechanics
   Document v1.5 Sections 14–22.

2. **Backlog reorganized (Section 14).** Split into two categories:
   items fully designed in Game Mechanics v1.5 (ready for post-V1
   implementation in tier order) and items not yet designed. Character
   advancement and XP spending removed from "not yet designed" — now
   fully specified in Game Mechanics §14. Tier implementation order
   documented: Tier 1 (advancement, talents) → Tier 2 (Force) →
   Tier 3 (vehicles, equipment) → Tier 4 (saga-scale systems).

**v1.7 — Two-system split and backlog cleanup (March 2026)**

1. **Scope statement added to Section 0:** This document now explicitly
   covers the Game Engine only. The Campaign Studio is specified in a
   separate companion document
   (`STORYTELLER_V3_CAMPAIGN_STUDIO_IMPLEMENTATION.md`). The two systems
   share infrastructure (Python, SQLite, Ollama, OpenRouter) but are
   architecturally independent. The campaign spine JSON is the interface
   contract between them.

2. **Document title updated** from "Full Implementation Document" to
   "Game Engine Implementation Document."

3. **Repository structure updated (Section 3).** Now shows the full
   unified repo aligned with the Campaign Studio Implementation
   Document's canonical structure. Spine schema models live in
   `studio/schema.py` (imported by both systems). API split into
   `game_routes.py` and `studio_routes.py`. `data/personas/` and
   `data/saga/` added. Test files updated. Game Engine scope within
   the repo explicitly identified.

4. **Backlog cleaned up (Section 14).** Three items migrated to
   Campaign Studio Implementation Document: campaign spine generator,
   NPC voice generation, multi-arc campaign structure. One item removed
   as already implemented: local model fallback for cloud outage
   (implemented in v1.5 as the cloud failure fallback path). Remaining
   items confirmed as Game Engine post-V1 scope.

5. **Spine models note added (Section 12).** Documents the migration
   path: Game Engine currently loads spine JSON directly; once
   `studio/schema.py` exists (Campaign Studio Phase 1), spines should
   be loaded via the Pydantic `CampaignSpine` model for type-safe
   validation.

**v1.6 — Cross-document alignment pass (March 2026)**

1. **NPCState disposition changed from string to float** — `disposition: str
   = "neutral"` replaced with `disposition: float = 0.5` (0.0 hostile to 1.0
   loyal). Added `disposition_label()` method for human-readable prompt output.
   Added `voice_notes` (renamed from `speech_notes`) and
   `behavioral_envelope: list[str]` for hard NPC constraints. Aligns with
   Game Mechanics Document numeric disposition throughout and Campaign Studio
   NPC roster schema.

2. **Choice skill tags now stripped before player display** — Narration prompt
   updated: GM tags choices with skill in square brackets at end of line (e.g.,
   `[Deception]`). `_parse_response` extracts tags into `NarrationResult.
   skill_tags` list and strips them from player-facing choice text. Vision
   Document's invisible mechanics principle now honored.

3. **Galactic context layer implemented** — `galactic_context: str` added to
   `ContextPackage`. `{galactic_context}` placeholder added to narration
   prompt template. `_build_prompt` passes it. Test campaign spine updated
   with per-act galactic context for all four acts. Aligns with Game Mechanics
   Document Section 4 and Campaign Studio Section 4.4.

4. **Test campaign spine format aligned with Campaign Studio** — NPC fields
   updated: `speech` → `voice_notes`, added `disposition_start` (numeric),
   `behavioral_envelope`, `knows_at_start`, `doesnt_know_at_start`. Added
   `era`, `galactic_context` per act, and `throughline_question` at top level.
   `key_npcs` renamed to `npc_roster`. Doss NPC fully specified.

5. **Scene type enum canonicalized** — Six scene types: `combat`, `chase`,
   `infiltration`, `social`, `exploration`, `introspection`. Added to
   `CHECK_DECISION_SCHEMA` and `CheckDecision` dataclass. Check decision
   prompt updated with scene type classification guidance. Default fallback
   is `"social"` on missing or invalid values.

6. **`moral_weight` added to check decision** — Integer 0-3 field added to
   schema, dataclass, and prompt. Tracks Morality Conflict accumulation per
   Game Mechanics Document Section 9. Added `moral_weight` column to `turns`
   table.

7. **Failure recovery difficulty calibration wired** — `decide_check()`
   accepts `recent_failure_count: int`. When ≥ 2, injects calibration note
   into check decision prompt per Game Mechanics Document Section 2. Check
   decision prompt template updated with `{failure_calibration}` placeholder.

8. **Reputation log table added** — `reputation_log` table in SQLite schema
   with session_id, turn_number, and one-sentence summary. Supports Game
   Mechanics Document Section 1 reputation echoes system.

9. **Act summary character drift field added** — `character_drift TEXT` column
   added to `act_summaries` table alongside existing `meaningful_choices`.

10. **Character active injuries and sequence state added** — `active_injuries:
    list[str]` added to `Character` model with narrative_status output.
    `sequence: Optional[dict]` added to `ContextPackage` for multi-beat
    combat/chase tracking per Game Mechanics Document Section 3.

**v1.5 — Research-informed defensive infrastructure**

1. **Physics-before-imagination invariant documented** — Section 2 now
   explicitly states the ordering rule: code resolves all state transitions
   before the narrative model receives the updated context. The LLM describes
   outcomes; it does not decide them. Informed by the Web World Models paper's
   formalization of the same principle (Feng et al., Princeton 2025).

2. **Check decision schema validation strengthened** — Phase 2 note added
   recommending Pydantic model validation on local model output, with defined
   fallback behavior (no-check default) when validation fails after retries.

3. **Context package validation added** — Phase 3 note specifying structural
   completeness checks on the assembled context package before cloud
   submission. Prevents hallucination from incomplete context.

4. **`prose_diagnostic` field reserved on ContextPackage** — Optional dict
   field, null in V1. Schema reservation for the prose diagnostic signal
   (Game Mechanics Document v1.1, Section 13). Ensures future addition is
   not a structural change.

5. **Cloud failure fallback path implemented** — `narrate_turn` refactored
   to attempt cloud first, then automatically fall back to local model on
   timeout (20s) or API error. The player never sees an error. The local
   model receives a simplified prompt optimized for its capability level.
   Fallback is per-turn, not per-session. Informed by the Web World Models
   paper's Graceful Degradation principle.

6. **`_narrate_with_local_fallback` added** — Emergency narration via Ollama
   with a simplified prompt. Lower quality but honors dice results and
   advances the story. Strictly better than an error screen during a
   climactic moment.

**v1.4 — Distillation data instrumentation**

1. **`turns` table extended** — `context_json` and `scene_type` columns added.
   When `NARRATIVE_BACKEND != local`, the serialized context package is stored
   alongside the cloud-generated narration. Zero cost at write time; enables
   future fine-tuning without backfilling.

2. **`distillation_pairs` view added** — SQL view pairing context packages with
   narration output, filtered to cloud-generated turns only. Includes scene
   type, dice metadata, and skill info for targeted dataset construction.

3. **`log_turn` updated** — accepts `context_json` and `scene_type` parameters.
   Docstring documents the distillation rationale.

4. **Backlog item added** — "Narration distillation pipeline" — QLoRA fine-tune
   of local model using collected pairs. Depends on `distillation_pairs` view
   being populated during V1 play. Cross-references LLM Evaluation Document
   Section 8.4.

   No architectural changes. No build order changes. The data collection is
   passive instrumentation on the existing turn logging path.

**v1.3 — Model strings updated per LLM Evaluation Document v1.3**

1. **Tech stack table updated** — Cloud provider (current) changed from
   `gpt-4o` to `gpt-5.2`. Cloud provider (planned) changed from
   `x-ai/grok-4-1-fast` to `x-ai/grok-4.1-fast`.

2. **`.env.example` updated** — `CLOUD_MODEL=gpt-5.2` (was `gpt-4o`).
   OpenRouter commented example corrected to `x-ai/grok-4.1-fast`.

3. **`cloud_gm.py` comment block updated** — Model string examples and
   `CLOUD_MODEL` default updated to match.

   No architectural changes. The OpenAI-compatible SDK abstraction in
   `cloud_gm.py` handles all providers without code modification.
   Verify all model strings and pricing against current provider documentation
   before deployment.

**v1.2 — Hardware confirmed, cloud abstracted, code bugs fixed**

1. **Cloud backend rewritten for OpenAI-compatible SDK** — `anthropic` removed.
   `cloud_gm.py` uses `openai` SDK throughout. Provider set via `CLOUD_PROVIDER`
   (`openai` | `openrouter`). Model via `CLOUD_MODEL`. No code changes to swap.

2. **OpenRouter model string format documented** — `CLOUD_MODEL` must use
   `provider/model` prefix format when `CLOUD_PROVIDER=openrouter`
   (e.g. `x-ai/grok-4-1-fast`).

3. **Local model updated to Qwen3.5:9B** — replaces `qwen2.5:7b-instruct`.
   Hardware confirmed: RTX 4070 (12GB VRAM) + 32GB RAM. Q4_K_M quantization
   (~5.5GB) fits in VRAM with room to spare.

4. **`NARRATIVE_BACKEND=local` fully specced** — routes narration through Ollama
   for cost-free loop testing. UI warning added. Rule 10 added. Success criterion
   12 added.

5. **SQLite WAL mode added** — `PRAGMA journal_mode=WAL` on every connection.
   Prevents locked-database errors during concurrent compression writes.

6. **`state/session.py` fully specced** — previously unspecced. Now includes
   `create_session`, `log_turn`, `get_recent_turns`, `get_act_summaries`,
   `get_session`, `get_turn_count`.

7. **`asyncio.get_event_loop()` replaced with `get_running_loop()`** — the
   former is deprecated in Python 3.10+ and errors in 3.12+.

8. **Missing `from enum import Enum` added to `checks.py`** — would have caused
   immediate `NameError` on first import.

9. **`TurnMemory.narrative_summary` removed** — was defined but never populated
   or used anywhere. Removed to eliminate dead field confusion.

10. **Tied-result label fixed** — `net_successes == 0` previously produced
    "FAILED (0 net failures)". Now: "FAILED (tied — successes and failures
    cancelled exactly)".

11. **`describe_pool_for_display` filters zero-count dice** — now returns only
    die types present in the pool. Frontend no longer needs client-side filtering.

12. **`import re` moved to module level in `cloud_gm.py`** — was inside
    `_parse_response`, re-imported on every turn call.

13. **`pyproject.toml` updated** — `anthropic` replaced with `openai>=1.30.0`.

14. **`.env.example` restructured** — provider-agnostic cloud config with
    OpenRouter commented example included.

---

**v1.1 — Post-Gemini review fixes**

1. JSON schema enforcement via Ollama `format` parameter + skill normalization
2. Memory compression spec with async background worker
3. Destiny Points tracked in session table
4. Narration length validation (250–600 words) with retry
5. Minimum 2 choices enforcement with retry
6. Arc state injected into check decision prompt
