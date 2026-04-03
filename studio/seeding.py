"""
Deterministic seed derivation for Campaign Studio pipeline stages.

Each generation stage receives its own seed, derived from a master seed
using SHA-256. This enables partial regeneration — the author can re-roll
specific stages while keeping others constant.

Seeding is "best effort" — OpenAI documents seed as mostly reproducible,
Ollama may produce slight variations with quantized models. The system
treats seeding as "high probability of similar output," not a guarantee.
"""

import hashlib
import random
import time
from typing import Optional


# ── Stage name constants ──────────────────────────────────────────────

STAGE_WORLD = "world"
STAGE_NPCS = "npcs"
STAGE_ANCHORS = "anchors"
STAGE_VOICE = "voice"
STAGE_VARIANTS = "variants"
STAGE_THREADS = "threads"
STAGE_SAGA_DIVERGE = "saga_diverge"
STAGE_SAGA_SEARCH = "saga_search"
STAGE_SAGA_DEBATE = "saga_debate"
STAGE_ARCHITECT = "architect"

ALL_STAGES = [
    STAGE_WORLD, STAGE_NPCS, STAGE_ANCHORS, STAGE_VOICE,
    STAGE_VARIANTS, STAGE_THREADS, STAGE_SAGA_DIVERGE,
    STAGE_SAGA_SEARCH, STAGE_SAGA_DEBATE, STAGE_ARCHITECT,
]


# ── Core derivation ──────────────────────────────────────────────────


def derive_stage_seed(master_seed: int, stage_name: str) -> int:
    """Deterministic seed derivation per pipeline stage.

    Args:
        master_seed: The campaign's master seed.
        stage_name: One of the stage name constants above.

    Returns:
        An integer seed for this specific stage.
    """
    h = hashlib.sha256(f"{master_seed}:{stage_name}".encode())
    return int.from_bytes(h.digest()[:8], "big") % (2**31)


def generate_master_seed() -> int:
    """Generate a random master seed for a new generation run."""
    return random.randint(0, 2**31 - 1)


def derive_all_seeds(master_seed: int) -> dict[str, int]:
    """Derive seeds for all pipeline stages from a master seed.

    Returns:
        Dict mapping stage_name → derived seed.
    """
    return {stage: derive_stage_seed(master_seed, stage) for stage in ALL_STAGES}


def derive_seeds_with_overrides(
    master_seed: int,
    stage_overrides: Optional[dict[str, int]] = None,
) -> dict[str, int]:
    """Derive seeds with optional per-stage overrides for partial regeneration.

    For stages in stage_overrides, use the override seed instead of the
    derived seed. This enables "regenerate NPCs" while keeping world and
    anchors constant.

    Args:
        master_seed: The campaign's master seed.
        stage_overrides: Dict of stage_name → new seed for stages to re-roll.

    Returns:
        Dict mapping stage_name → final seed (derived or overridden).
    """
    seeds = derive_all_seeds(master_seed)
    if stage_overrides:
        for stage, seed in stage_overrides.items():
            if stage in seeds:
                seeds[stage] = seed
    return seeds


def build_generation_metadata(
    master_seed: int,
    stage_seeds: dict[str, int],
    model_used: str = "",
    generation_mode: str = "",
) -> dict:
    """Build generation metadata dict for spine storage.

    Returns a dict suitable for CampaignSpine.generation_metadata.
    """
    return {
        "master_seed": master_seed,
        "stage_seeds": stage_seeds,
        "model_used": model_used,
        "generation_mode": generation_mode,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
