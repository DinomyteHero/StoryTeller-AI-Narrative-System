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
        "nar_shaddaa_job", "keth_varso",
        dice_seed=42, max_turns=20, policy="cautious",
    ),
    GoldenScenario(
        "nar_shaddaa_reckless_20",
        "nar_shaddaa_job", "keth_varso",
        dice_seed=42, max_turns=20, policy="reckless",
    ),
    GoldenScenario(
        "nar_shaddaa_random_20_a",
        "nar_shaddaa_job", "keth_varso",
        dice_seed=42, max_turns=20, policy="random",
    ),
    GoldenScenario(
        "nar_shaddaa_random_20_b",
        "nar_shaddaa_job", "keth_varso",
        dice_seed=99, max_turns=20, policy="random",
    ),
    GoldenScenario(
        "nar_shaddaa_first_40",
        "nar_shaddaa_job", "keth_varso",
        dice_seed=42, max_turns=40, policy="first",
    ),
]
