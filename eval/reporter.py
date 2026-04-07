"""Report generation for evaluation harness results.

Outputs human-readable console text and machine-readable JSON.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eval.metrics import MetricResult
    from eval.harness import SessionRecord


def generate_report(
    results: dict[str, list[MetricResult]],
    sessions: dict[str, SessionRecord] | None = None,
) -> str:
    """Generate a human-readable quality report.

    Args:
        results: Mapping of scenario name → list of MetricResult.
        sessions: Optional mapping of scenario name → SessionRecord for context.

    Returns:
        Formatted report string.
    """
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("STORYTELLER V3 — NARRATIVE QUALITY REPORT")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 72)

    total_passed = 0
    total_metrics = 0
    scenario_summaries: list[dict] = []

    for scenario_name, metric_results in results.items():
        lines.append("")
        lines.append(f"--- {scenario_name} ---")

        if sessions and scenario_name in sessions:
            s = sessions[scenario_name]
            lines.append(f"  Turns: {len(s.turns)}  |  Errors: {len(s.errors)}  |  "
                         f"Duration: {s.duration_seconds:.1f}s")

        passed_count = 0
        for mr in metric_results:
            status = "PASS" if mr.passed else "FAIL"
            lines.append(f"  [{status}] {mr.name}: {mr.score:.2f} — {mr.details}")
            if mr.passed:
                passed_count += 1
            total_metrics += 1
            total_passed += int(mr.passed)

        scenario_pass_rate = passed_count / len(metric_results) if metric_results else 0
        lines.append(f"  Summary: {passed_count}/{len(metric_results)} metrics passed "
                     f"({scenario_pass_rate:.0%})")
        scenario_summaries.append({
            "scenario": scenario_name,
            "passed": passed_count,
            "total": len(metric_results),
            "rate": scenario_pass_rate,
        })

    lines.append("")
    lines.append("=" * 72)
    overall_rate = total_passed / total_metrics if total_metrics else 0
    overall_status = "PASS" if overall_rate >= 0.80 else "FAIL"
    lines.append(f"OVERALL: {overall_status} — {total_passed}/{total_metrics} metrics passed "
                 f"({overall_rate:.0%})")
    lines.append("=" * 72)

    return "\n".join(lines)


def save_report_json(
    results: dict[str, list[MetricResult]],
    sessions: dict[str, SessionRecord] | None = None,
    output_path: str | Path = "eval_report.json",
) -> Path:
    """Save results as a structured JSON file for programmatic analysis."""
    output_path = Path(output_path)

    report_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenarios": {},
    }

    for scenario_name, metric_results in results.items():
        scenario_data: dict = {
            "metrics": [],
            "turns": 0,
            "errors": [],
            "duration_seconds": 0.0,
        }
        if sessions and scenario_name in sessions:
            s = sessions[scenario_name]
            scenario_data["turns"] = len(s.turns)
            scenario_data["errors"] = s.errors
            scenario_data["duration_seconds"] = s.duration_seconds

        for mr in metric_results:
            scenario_data["metrics"].append({
                "name": mr.name,
                "score": round(mr.score, 4),
                "passed": mr.passed,
                "details": mr.details,
                "raw_data": mr.raw_data,
            })

        report_data["scenarios"][scenario_name] = scenario_data

    output_path.write_text(json.dumps(report_data, indent=2, default=str), encoding="utf-8")
    return output_path
