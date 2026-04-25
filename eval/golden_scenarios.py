"""Golden test scenarios — fixed seeds and policies for reproducible harness runs."""

from dataclasses import dataclass


@dataclass
class GoldenScenario:
    name: str
    campaign: str
    character: str
    dice_seed: int
    max_turns: int
    policy: str


GOLDEN_SCENARIOS = [
    GoldenScenario(
        "nar_shaddaa_cautious_20",
        "shadows_of_the_praxeum", "praxeum_student",
        dice_seed=42, max_turns=20, policy="cautious",
    ),
    GoldenScenario(
        "nar_shaddaa_reckless_20",
        "shadows_of_the_praxeum", "praxeum_student",
        dice_seed=42, max_turns=20, policy="reckless",
    ),
    GoldenScenario(
        "nar_shaddaa_random_20_a",
        "shadows_of_the_praxeum", "praxeum_student",
        dice_seed=42, max_turns=20, policy="random",
    ),
    GoldenScenario(
        "nar_shaddaa_random_20_b",
        "shadows_of_the_praxeum", "praxeum_student",
        dice_seed=99, max_turns=20, policy="random",
    ),
    GoldenScenario(
        "nar_shaddaa_first_40",
        "shadows_of_the_praxeum", "praxeum_student",
        dice_seed=42, max_turns=40, policy="first",
    ),
]
