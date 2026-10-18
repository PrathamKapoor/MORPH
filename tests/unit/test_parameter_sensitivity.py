"""Unit tests verifying hyperparameter sensitivity analysis and report generation (Milestone M7.2)."""

from __future__ import annotations

import json
from pathlib import Path

from morph.evaluation.sensitivity import (
    export_sensitivity_report,
    run_parameter_sensitivity_sweep,
)
from tests.fixtures.benchmark_scenarios import BenchmarkScenarioSuite


def test_parameter_sensitivity_sweep_execution(tmp_path: Path):
    """Verify execution of full hyperparameter grid sweep and export of reports."""
    suite = BenchmarkScenarioSuite()
    stream, gts, intervals = suite.build_full_challenge_stream()
    cal = suite.get_calibration_prototypes()

    results = run_parameter_sensitivity_sweep(
        feature_stream=stream,
        ground_truth_events=gts,
        prototypes=cal,
        hold_times_ms=[150, 200, 250, 300, 350, 400],
        cooldowns_ms=[150, 200, 300, 500],
        margins=[0.05, 0.10, 0.15, 0.20, 0.25],
    )

    # 6 hold times * 4 cooldowns * 5 margins = 120 configurations
    assert results["metadata"]["total_evaluated_combinations"] == 120
    assert len(results["all_combinations"]) == 120

    # Verify 1-D slices
    assert len(results["hold_sweep"]) == 6
    assert len(results["cooldown_sweep"]) == 4
    assert len(results["margin_sweep"]) == 5

    # Check baseline point in hold sweep (hold=250ms, cooldown=300ms, margin=0.15)
    baseline_run = next(r for r in results["hold_sweep"] if r["hold_ms"] == 250)
    assert baseline_run["matched_count"] == 4
    assert baseline_run["recall"] == 1.0
    assert baseline_run["unintended_dispatches"] == 0
    assert baseline_run["precision"] == 1.0
    assert baseline_run["false_activations_per_hour"] == 0.0

    # Test report export in temporary directory
    json_path = tmp_path / "parameter_sensitivity.json"
    md_path = tmp_path / "PARAMETER_SENSITIVITY.md"

    p_json, p_md = export_sensitivity_report(results, json_path, md_path)
    assert p_json.exists()
    assert p_md.exists()

    # Verify JSON structure
    loaded_json = json.loads(p_json.read_text(encoding="utf-8"))
    assert loaded_json["metadata"]["total_evaluated_combinations"] == 120

    # Verify Markdown formatting
    md_text = p_md.read_text(encoding="utf-8")
    assert "# MORPH 2.0 — Hyperparameter Sensitivity Analysis Report" in md_text
    assert "Hold Duration Sensitivity" in md_text
    assert "250 ms" in md_text


def test_twitch_vulnerability_boundary():
    """Verify that shortening hold duration to <= 120ms admits false activations on involuntary twitches."""
    suite = BenchmarkScenarioSuite()
    stream, gts, _ = suite.build_full_challenge_stream()
    cal = suite.get_calibration_prototypes()

    # Compare short hold (60ms <= 120ms twitch) vs safe hold (250ms)
    sweep_twitch = run_parameter_sensitivity_sweep(
        feature_stream=stream,
        ground_truth_events=gts,
        prototypes=cal,
        hold_times_ms=[60, 250],
        cooldowns_ms=[300],
        margins=[0.15],
    )

    run_60ms = next(r for r in sweep_twitch["all_combinations"] if r["hold_ms"] == 60)
    run_250ms = next(r for r in sweep_twitch["all_combinations"] if r["hold_ms"] == 250)

    # 60ms hold is breached by the 120ms involuntary smile twitch -> at least 1 false activation
    assert run_60ms["unintended_dispatches"] >= 1
    assert run_60ms["precision"] < 1.0
    assert run_60ms["false_activations_per_hour"] > 0.0

    # 250ms hold completely suppresses the 120ms twitch -> 0 false activations
    assert run_250ms["unintended_dispatches"] == 0
    assert run_250ms["precision"] == 1.0
    assert run_250ms["false_activations_per_hour"] == 0.0


def test_confirmation_latency_monotonicity():
    """Verify that confirmation latency increases strictly monotonically with hold duration."""
    suite = BenchmarkScenarioSuite()
    stream, gts, _ = suite.build_full_challenge_stream()
    cal = suite.get_calibration_prototypes()

    hold_values = [150, 200, 250, 300, 350]
    sweep = run_parameter_sensitivity_sweep(
        feature_stream=stream,
        ground_truth_events=gts,
        prototypes=cal,
        hold_times_ms=hold_values,
        cooldowns_ms=[300],
        margins=[0.15],
    )

    latencies = [r["latency_p50_ms"] for r in sweep["hold_sweep"]]
    for i in range(len(latencies) - 1):
        assert latencies[i] < latencies[i + 1], f"Expected {latencies[i]} < {latencies[i + 1]}"
