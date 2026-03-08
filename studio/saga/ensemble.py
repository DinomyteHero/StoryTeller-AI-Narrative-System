"""
Multi-model writer assignment and parallel execution.

When ensemble mode is enabled, different writers (personas) can be
assigned to different LLM models. This increases output diversity
by leveraging different model architectures' creative tendencies.

Default behavior: all writers use the same model (single-model mode).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


DEFAULT_MODEL_POOL = [
    {"model": "gpt-5.2", "provider": "openai", "weight": 1.0},
]


@dataclass
class ModelAssignment:
    """Maps a persona to a specific model for generation."""
    persona_id: str
    model: str
    provider: str


def assign_models(
    persona_ids: list[str],
    *,
    model_pool: Optional[list[dict]] = None,
    strategy: str = "round_robin",
    seed: Optional[int] = None,
) -> list[ModelAssignment]:
    """Assign models to personas based on strategy.

    Args:
        persona_ids: List of persona IDs to assign.
        model_pool: Available models. Defaults to single-model pool.
        strategy: "round_robin", "weighted", or "random".
        seed: Random seed for reproducibility.

    Returns:
        List of ModelAssignment objects.
    """
    pool = model_pool or DEFAULT_MODEL_POOL
    if not pool:
        pool = DEFAULT_MODEL_POOL

    assignments = []

    if strategy == "round_robin":
        for i, pid in enumerate(persona_ids):
            model_entry = pool[i % len(pool)]
            assignments.append(ModelAssignment(
                persona_id=pid,
                model=model_entry["model"],
                provider=model_entry.get("provider", "openai"),
            ))

    elif strategy == "random":
        import random
        rng = random.Random(seed)
        for pid in persona_ids:
            model_entry = rng.choice(pool)
            assignments.append(ModelAssignment(
                persona_id=pid,
                model=model_entry["model"],
                provider=model_entry.get("provider", "openai"),
            ))

    elif strategy == "weighted":
        import random
        rng = random.Random(seed)
        weights = [m.get("weight", 1.0) for m in pool]
        for pid in persona_ids:
            choices = rng.choices(pool, weights=weights, k=1)
            model_entry = choices[0]
            assignments.append(ModelAssignment(
                persona_id=pid,
                model=model_entry["model"],
                provider=model_entry.get("provider", "openai"),
            ))

    else:
        # Fallback to round_robin
        return assign_models(persona_ids, model_pool=pool, strategy="round_robin")

    return assignments
