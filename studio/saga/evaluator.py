"""
Trained local evaluator for pairwise comparison.

Post-CS-4 optimization: QLoRA-trained local model for spine evaluation.
Until calibrated (80% agreement with cloud evaluator on 600+ pairs),
falls back to cloud evaluation or pure-Python structural scoring.

This module provides the evaluator interface and calibration tracking.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class EvaluatorConfig:
    """Configuration for the evaluator backend."""
    backend: str = "cloud"  # "cloud" | "local" | "ensemble"
    local_model: str = ""
    calibration_score: float = 0.0  # 0.0-1.0, target: 0.8
    total_pairs_trained: int = 0
    target_pairs: int = 600


def get_evaluator_status(config: EvaluatorConfig) -> dict:
    """Get the current evaluator status.

    Returns:
        Dict with status information about the evaluator.
    """
    calibrated = config.calibration_score >= 0.8
    return {
        "backend": config.backend,
        "local_model": config.local_model,
        "calibrated": calibrated,
        "calibration_score": config.calibration_score,
        "pairs_trained": config.total_pairs_trained,
        "target_pairs": config.target_pairs,
        "ready_for_local": calibrated and config.local_model != "",
    }


def should_use_local(config: EvaluatorConfig) -> bool:
    """Determine if local evaluator should be used.

    Only use local when calibration threshold is met.
    """
    return (
        config.backend in ("local", "ensemble")
        and config.calibration_score >= 0.8
        and config.local_model != ""
    )


def log_evaluation_pair(
    spine_a_summary: str,
    spine_b_summary: str,
    axis: str,
    winner: str,
    confidence: float,
    reasoning: str,
    source: str = "cloud_stage5",
) -> dict:
    """Create an evaluation pair record for training data.

    These records accumulate and are used to train the local evaluator.

    Returns:
        Dict suitable for storage in the evaluation_pairs table.
    """
    import uuid
    return {
        "pair_id": str(uuid.uuid4()),
        "spine_a_summary": spine_a_summary,
        "spine_b_summary": spine_b_summary,
        "axis": axis,
        "winner": winner,
        "confidence": confidence,
        "reasoning": reasoning,
        "source": source,
    }
