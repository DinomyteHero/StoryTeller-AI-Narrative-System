"""Evaluation harness — runs scripted play sessions and measures quality.

Usage:
    python -m eval.harness                          # Run all golden scenarios
    python -m eval.harness --scenario NAME          # Run one scenario
    python -m eval.harness --scenario NAME --turns 5  # Quick smoke test
    python -m eval.harness --list                   # List available scenarios

Requires LLM services (cloud + Ollama) to be running. The harness calls
through the real game loop — no mocks. Dice are seeded for reproducibility.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


@dataclass
class TurnRecord:
    turn_number: int
    passage: str
    choices: list[str]
    selected_choice: int
    player_action: str
    dice_result: dict | None = None
    scene_type: str = ""
    npc_states: list[dict] = field(default_factory=list)
    state_deltas: dict = field(default_factory=dict)
    choice_quality: dict | None = None
    word_count: int = 0


@dataclass
class SessionRecord:
    scenario_name: str
    turns: list[TurnRecord] = field(default_factory=list)
    final_state: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


def _setup_temp_db() -> str:
    """Create a temporary database for harness runs."""
    import state.db
    tmp = tempfile.mkdtemp(prefix="storyteller_eval_")
    db_path = os.path.join(tmp, "eval.db")
    os.environ["DB_PATH"] = db_path
    state.db._DB_PATH = db_path
    state.db.init_db()
    return db_path


def _restore_db(original_path: str | None, original_env: str | None):
    """Restore original DB path after harness run."""
    import state.db
    state.db._DB_PATH = original_path
    if original_env is not None:
        os.environ["DB_PATH"] = original_env
    elif "DB_PATH" in os.environ:
        del os.environ["DB_PATH"]


def run_scenario(
    scenario_name: str,
    campaign: str,
    character: str,
    dice_seed: int,
    max_turns: int,
    policy_name: str,
) -> SessionRecord:
    """Run a single scenario through the real game loop.

    Seeds the random module for dice reproducibility, creates a session,
    then plays max_turns using the specified player policy.
    """
    from eval.policies import POLICIES

    policy = POLICIES[policy_name]
    record = SessionRecord(scenario_name=scenario_name)
    start_time = time.time()

    # Save and set up temp DB
    import state.db
    original_db_path = state.db._DB_PATH
    original_db_env = os.environ.get("DB_PATH")
    db_path = _setup_temp_db()

    try:
        # Import app after DB is configured
        from api.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)

        # Seed RNG for dice reproducibility
        random.seed(dice_seed)

        # Create session
        resp = client.post("/session", json={
            "campaign_name": campaign,
            "character_id": character,
        })
        if resp.status_code != 200:
            record.errors.append(f"Session creation failed: {resp.status_code} {resp.text}")
            return record

        data = resp.json()
        session_id = data["session_id"]
        opening_passage = data["opening_narration"]
        choices = data["choices"]

        # Record turn 0 (opening)
        record.turns.append(TurnRecord(
            turn_number=0,
            passage=opening_passage,
            choices=choices,
            selected_choice=-1,
            player_action="[session_start]",
            word_count=len(opening_passage.split()),
            scene_type="exploration",
        ))

        # Play turns
        for turn_num in range(1, max_turns + 1):
            if not choices:
                record.errors.append(f"Turn {turn_num}: no choices available")
                break

            # Re-seed before each turn so dice sequence is reproducible
            # regardless of how much randomness the policy consumed
            random.seed(dice_seed + turn_num)

            # Select choice using policy
            choice_idx = policy.select(opening_passage if turn_num == 1 else record.turns[-1].passage, choices)
            choice_idx = min(choice_idx, len(choices) - 1)
            player_action = choices[choice_idx]

            # Execute turn
            resp = client.post(f"/session/{session_id}/turn", json={
                "choice_index": choice_idx,
            })
            if resp.status_code != 200:
                record.errors.append(
                    f"Turn {turn_num} failed: {resp.status_code} {resp.text[:200]}"
                )
                break

            turn_data = resp.json()
            passage = turn_data.get("narration", "")
            choices = turn_data.get("choices", [])
            dice_info = turn_data.get("dice_result")
            scene_type = turn_data.get("scene_type", "")

            # Extract state deltas from reconciliation if available
            state_deltas = {}
            recon = turn_data.get("reconciliation")
            if recon:
                state_deltas = recon

            # Extract NPC states if available
            npc_states = turn_data.get("npc_states", [])

            record.turns.append(TurnRecord(
                turn_number=turn_num,
                passage=passage,
                choices=choices,
                selected_choice=choice_idx,
                player_action=player_action,
                dice_result=dice_info,
                scene_type=scene_type,
                npc_states=npc_states,
                state_deltas=state_deltas,
                word_count=len(passage.split()),
            ))

        # Capture final state
        resp = client.get(f"/session/{session_id}")
        if resp.status_code == 200:
            record.final_state = resp.json()

    except Exception as e:
        record.errors.append(f"Harness error: {type(e).__name__}: {e}")
    finally:
        record.duration_seconds = time.time() - start_time
        _restore_db(original_db_path, original_db_env)

    return record


def run_golden_scenarios(
    scenario_filter: str | None = None,
    max_turns_override: int | None = None,
) -> dict[str, SessionRecord]:
    """Run golden scenarios and return session records.

    Args:
        scenario_filter: If set, only run the scenario matching this name.
        max_turns_override: If set, override max_turns for all scenarios.
    """
    from eval.golden_scenarios import GOLDEN_SCENARIOS

    sessions: dict[str, SessionRecord] = {}
    scenarios = GOLDEN_SCENARIOS

    if scenario_filter:
        scenarios = [s for s in scenarios if s.name == scenario_filter]
        if not scenarios:
            print(f"Unknown scenario: {scenario_filter}")
            print("Available:", ", ".join(s.name for s in GOLDEN_SCENARIOS))
            return sessions

    for scenario in scenarios:
        max_turns = max_turns_override if max_turns_override is not None else scenario.max_turns
        print(f"\n{'='*60}")
        print(f"Running: {scenario.name} ({max_turns} turns, {scenario.policy} policy)")
        print(f"{'='*60}")

        record = run_scenario(
            scenario_name=scenario.name,
            campaign=scenario.campaign,
            character=scenario.character,
            dice_seed=scenario.dice_seed,
            max_turns=max_turns,
            policy_name=scenario.policy,
        )

        sessions[scenario.name] = record
        print(f"  Completed: {len(record.turns)} turns, "
              f"{len(record.errors)} errors, "
              f"{record.duration_seconds:.1f}s")
        if record.errors:
            for err in record.errors[:3]:
                print(f"  ERROR: {err[:120]}")

    return sessions


def main():
    parser = argparse.ArgumentParser(description="Storyteller V3 Evaluation Harness")
    parser.add_argument("--scenario", type=str, help="Run a specific scenario by name")
    parser.add_argument("--turns", type=int, help="Override max turns for all scenarios")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    parser.add_argument("--output", type=str, default="eval_report.json",
                        help="Output path for JSON report")
    args = parser.parse_args()

    if args.list:
        from eval.golden_scenarios import GOLDEN_SCENARIOS
        print("Available golden scenarios:")
        for s in GOLDEN_SCENARIOS:
            print(f"  {s.name}: {s.campaign}/{s.character}, "
                  f"seed={s.dice_seed}, turns={s.max_turns}, policy={s.policy}")
        return

    sessions = run_golden_scenarios(
        scenario_filter=args.scenario,
        max_turns_override=args.turns,
    )

    if not sessions:
        print("No sessions completed.")
        return

    # Run metrics
    from eval.metrics import run_all_metrics
    from eval.reporter import generate_report, save_report_json

    results: dict[str, list] = {}
    for name, session in sessions.items():
        results[name] = run_all_metrics(session)

    # Print report
    report = generate_report(results, sessions)
    print(f"\n{report}")

    # Save JSON
    output_path = save_report_json(results, sessions, args.output)
    print(f"\nJSON report saved to: {output_path}")


if __name__ == "__main__":
    main()
