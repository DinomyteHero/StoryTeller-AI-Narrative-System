"""Player policies — automated choice selection strategies for harness runs."""

import random
from dataclasses import dataclass
from typing import Callable


@dataclass
class PlayerPolicy:
    name: str
    select: Callable[[str, list[str]], int]  # (passage, choices) -> choice_index


def cautious_policy(passage: str, choices: list[str]) -> int:
    """Always picks the lowest-risk choice (first choice without a skill tag,
    or the first choice if all have tags)."""
    for i, c in enumerate(choices):
        if "[" not in c:
            return i
    return 0


def reckless_policy(passage: str, choices: list[str]) -> int:
    """Always picks the highest-risk choice (last choice with a skill tag,
    or the last choice)."""
    tagged = [i for i, c in enumerate(choices) if "[" in c]
    return tagged[-1] if tagged else len(choices) - 1


def random_policy(passage: str, choices: list[str]) -> int:
    """Random selection."""
    return random.randint(0, len(choices) - 1)


def first_policy(passage: str, choices: list[str]) -> int:
    """Always picks the first choice. Baseline for consistency testing."""
    return 0


POLICIES = {
    "cautious": PlayerPolicy("cautious", cautious_policy),
    "reckless": PlayerPolicy("reckless", reckless_policy),
    "random":   PlayerPolicy("random", random_policy),
    "first":    PlayerPolicy("first", first_policy),
}
