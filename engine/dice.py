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
