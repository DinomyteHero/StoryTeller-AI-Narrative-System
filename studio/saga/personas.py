"""
Persona pool management for the Writer's Room pipeline.

Personas are "ordinary people" descriptions — a retired politician, a
dock worker, a traveling merchant. NOT narrative archetypes. Each persona
biases the LLM's creative direction without constraining it to genre
tropes.

55 personas across 11 clusters. Each cluster represents a demographic
or experiential category. Subset diversity validation ensures that
different persona subsets produce distinct sequel directions.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Optional


PERSONA_POOL_PATH = Path(__file__).parent.parent.parent / "data" / "personas" / "writer_room_personas.json"


def load_persona_pool(path: Optional[Path] = None) -> list[dict]:
    """Load the persona pool from disk.

    Args:
        path: Override path for testing.

    Returns:
        List of persona dicts with 'id', 'description', 'cluster' keys.
    """
    pool_path = path or PERSONA_POOL_PATH
    with open(pool_path) as f:
        return json.load(f)


def select_personas(
    pool: list[dict],
    count: int = 5,
    *,
    seed: Optional[int] = None,
    exclude_ids: Optional[set[str]] = None,
) -> list[dict]:
    """Select a diverse subset of personas from the pool.

    Ensures at least one persona from each cluster when possible.

    Args:
        pool: Full persona pool.
        count: Number of personas to select.
        seed: Random seed for reproducibility.
        exclude_ids: Persona IDs to exclude (e.g., from prior runs).

    Returns:
        List of selected persona dicts.
    """
    rng = random.Random(seed)

    # Filter excluded
    available = [p for p in pool if not exclude_ids or p["id"] not in exclude_ids]
    if not available:
        return []

    if count >= len(available):
        return list(available)

    # Group by cluster
    clusters: dict[str, list[dict]] = {}
    for persona in available:
        cluster = persona.get("cluster", "unknown")
        clusters.setdefault(cluster, []).append(persona)

    selected: list[dict] = []
    selected_ids: set[str] = set()

    # First pass: one from each cluster (round-robin)
    cluster_keys = list(clusters.keys())
    rng.shuffle(cluster_keys)
    for cluster in cluster_keys:
        if len(selected) >= count:
            break
        candidates = [p for p in clusters[cluster] if p["id"] not in selected_ids]
        if candidates:
            pick = rng.choice(candidates)
            selected.append(pick)
            selected_ids.add(pick["id"])

    # Second pass: fill remaining from all available
    remaining = [p for p in available if p["id"] not in selected_ids]
    rng.shuffle(remaining)
    while len(selected) < count and remaining:
        selected.append(remaining.pop())

    return selected


def validate_diversity(pool: list[dict], num_subsets: int = 5, subset_size: int = 5) -> dict:
    """Validate that different persona subsets produce diversity.

    Tests that at least 3 of 5 random subsets have distinct cluster
    compositions.

    Args:
        pool: Full persona pool.
        num_subsets: Number of subsets to generate.
        subset_size: Size of each subset.

    Returns:
        Dict with 'passed', 'unique_compositions', 'total_subsets'.
    """
    compositions = set()
    for i in range(num_subsets):
        subset = select_personas(pool, subset_size, seed=i * 1000)
        cluster_set = frozenset(p.get("cluster", "unknown") for p in subset)
        compositions.add(cluster_set)

    return {
        "passed": len(compositions) >= 3,
        "unique_compositions": len(compositions),
        "total_subsets": num_subsets,
    }
