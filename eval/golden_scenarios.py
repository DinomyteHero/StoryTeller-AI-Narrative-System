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
        "custodian_cautious_20",
        "shadows_of_the_custodian", "clovis_beryl",
        dice_seed=42, max_turns=20, policy="cautious",
    ),
    GoldenScenario(
        "custodian_reckless_20",
        "shadows_of_the_custodian", "clovis_beryl",
        dice_seed=42, max_turns=20, policy="reckless",
    ),
    GoldenScenario(
        "custodian_random_20_a",
        "shadows_of_the_custodian", "clovis_beryl",
        dice_seed=42, max_turns=20, policy="random",
    ),
    GoldenScenario(
        "custodian_random_20_b",
        "shadows_of_the_custodian", "clovis_beryl",
        dice_seed=99, max_turns=20, policy="random",
    ),
    GoldenScenario(
        "custodian_first_40",
        "shadows_of_the_custodian", "clovis_beryl",
        dice_seed=42, max_turns=40, policy="first",
    ),
]
