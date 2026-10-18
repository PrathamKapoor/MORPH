"""Automated test suite verifying benchmark metric integrity invariants (Milestone M7.1)."""

from __future__ import annotations

import json
import tempfile

import pytest

from morph.common.types import GroundTruthEvent
from morph.evaluation.exporter import export_benchmark_csv, export_benchmark_json
from morph.evaluation.matching import MatchedPair, match_events_one_to_one
from morph.evaluation.metrics import (
    calculate_benchmark_metrics,
    compute_merged_interval_duration_sec,
    poisson_rate_ci_95,
)


def test_invariant_merged_interval_duration():
    """Verify compute_merged_interval_duration_sec handles disjoint, overlapping, and nested intervals."""
    # Disjoint intervals: [1.0s, 2.0s] (1.0s) and [3.0s, 5.0s] (2.0s) -> 3.0s
    disjoint_gts = [
        GroundTruthEvent("A", 1_000_000_000, 2_000_000_000, "a", "s"),
        GroundTruthEvent("B", 3_000_000_000, 5_000_000_000, "a", "s"),
    ]
    assert abs(compute_merged_interval_duration_sec(disjoint_gts) - 3.0) < 1e-6

    # Overlapping intervals: [1.0s, 3.0s] and [2.0s, 4.0s] -> [1.0s, 4.0s] = 3.0s (not 4.0s)
    overlap_gts = [
        GroundTruthEvent("A", 1_000_000_000, 3_000_000_000, "a", "s"),
        GroundTruthEvent("B", 2_000_000_000, 4_000_000_000, "a", "s"),
    ]
    assert abs(compute_merged_interval_duration_sec(overlap_gts) - 3.0) < 1e-6

    # Fully nested: [1.0s, 5.0s] contains [2.0s, 3.0s] -> [1.0s, 5.0s] = 4.0s
    nested_gts = [
        GroundTruthEvent("A", 1_000_000_000, 5_000_000_000, "a", "s"),
        GroundTruthEvent("B", 2_000_000_000, 3_000_000_000, "a", "s"),
    ]
    assert abs(compute_merged_interval_duration_sec(nested_gts) - 4.0) < 1e-6

    # Also test tuple inputs
    tuple_intervals = [(1_000_000_000, 2_000_000_000), (3_000_000_000, 4_500_000_000)]
    assert abs(compute_merged_interval_duration_sec(tuple_intervals) - 2.5) < 1e-6

    # Empty list
    assert compute_merged_interval_duration_sec([]) == 0.0


def test_invariant_one_to_one_bipartite_matching():
    """Verify each prediction matches <= 1 ground truth event and each GT matches <= 1 dispatch."""
    gts = [
        GroundTruthEvent("Brow Raise", 1000, 2000, "annotator", "s1"),
        GroundTruthEvent("Smile / Lip Corner Pull", 4000, 5000, "annotator", "s1"),
    ]
    # Two identical dispatches at 1500 (both within Brow Raise window)
    dispatches = [("NEXT_TILE", 1500), ("NEXT_TILE", 1600)]

    matched, unmatched_disp, unmatched_gt = match_events_one_to_one(gts, dispatches)

    # Invariant: exactly 1 dispatch matched, the second is marked unmatched (FP)
    assert len(matched) == 1
    assert matched[0].ground_truth.label == "Brow Raise"
    assert len(unmatched_disp) == 1
    assert unmatched_disp[0] == ("NEXT_TILE", 1600)
    # The Smile was never triggered -> 1 unmatched GT (FN)
    assert len(unmatched_gt) == 1
    assert unmatched_gt[0].label == "Smile / Lip Corner Pull"


def test_invariant_precision_recall_counts_agreement():
    """Verify precision = TP / (TP + FP) and recall = TP / (TP + FN) agree exactly with raw counts."""
    # 3 TP, 2 FP (unmatched dispatches), 1 FN (unmatched GT)
    pairs = [
        MatchedPair(
            GroundTruthEvent("A", 1000, 2000, "a", "s"),
            "NEXT_TILE",
            1500,
            0.0,
        ),
        MatchedPair(
            GroundTruthEvent("B", 3000, 4000, "a", "s"),
            "SELECT_TILE",
            3500,
            0.0,
        ),
        MatchedPair(
            GroundTruthEvent("C", 5000, 6000, "a", "s"),
            "PREVIOUS_TILE",
            5500,
            0.0,
        ),
    ]
    unmatched_disp = [("NEXT_TILE", 7000), ("NEXT_TILE", 8000)]
    unmatched_gt = [GroundTruthEvent("D", 9000, 10000, "a", "s")]

    metrics = calculate_benchmark_metrics(
        matched_pairs=pairs,
        unmatched_dispatches=unmatched_disp,
        unmatched_gts=unmatched_gt,
        total_session_duration_sec=20.0,
        total_intended_duration_sec=4.0,
    )

    # Raw counts
    tp = metrics["matched_count"]
    fp = metrics["unintended_dispatches"]
    fn = len(unmatched_gt)
    total_disp = metrics["total_dispatches"]
    total_intended = metrics["total_intended_events"]

    assert tp == 3
    assert fp == 2
    assert total_disp == tp + fp  # 5
    assert total_intended == tp + fn  # 4

    # Precision, recall & F1 formulas
    assert abs(metrics["precision"] - (tp / (tp + fp))) < 1e-6
    assert abs(metrics["recall"] - (tp / (tp + fn))) < 1e-6
    assert abs(metrics["precision"] - 0.60) < 1e-6
    assert abs(metrics["recall"] - 0.75) < 1e-6
    assert metrics["true_positives"] == 3
    assert metrics["false_positives"] == 2
    assert metrics["false_negatives"] == 1
    assert abs(metrics["f1_score"] - (2 * 0.6 * 0.75 / (0.6 + 0.75))) < 1e-6


def test_invariant_exposure_bounds_and_zero_denominator():
    """Verify exposure cannot exceed session duration, and 0 exposure produces None (N/A)."""
    # Negative duration raises ValueError
    with pytest.raises(ValueError):
        calculate_benchmark_metrics([], [], [], -5.0, 0.0)

    with pytest.raises(ValueError):
        calculate_benchmark_metrics([], [], [], 10.0, -2.0)

    # Intended duration exceeding total duration is safely clamped
    metrics_clamped = calculate_benchmark_metrics([], [], [], 10.0, 15.0)
    assert metrics_clamped["intended_duration_sec"] == 10.0
    assert metrics_clamped["non_command_duration_sec"] == 0.0
    assert metrics_clamped["false_activations_per_hour"] is None
    assert metrics_clamped["false_activations_ci_95_lower"] is None
    assert metrics_clamped["false_activations_ci_95_upper"] is None


def test_invariant_poisson_ci_monotonicity_and_exact_bounds():
    """Verify Garwood Poisson 95% CI bounds satisfy exact theoretical limits."""
    t_hr = 0.5  # 30 minutes

    # 1. Zero observed events (k = 0)
    ci_0 = poisson_rate_ci_95(0, t_hr, two_sided=True)
    assert ci_0 is not None
    lower_0, upper_0 = ci_0
    assert lower_0 == 0.0
    # Exact two-sided upper bound for k=0 is -ln(0.025)/T ~= 3.688879 / T
    assert abs(upper_0 - (3.688879 / t_hr)) < 1e-3

    # One-sided 95% upper limit for k=0 is -ln(0.05)/T ~= 2.995732 / T
    ci_0_onesided = poisson_rate_ci_95(0, t_hr, two_sided=False)
    assert abs(ci_0_onesided[1] - (2.995732 / t_hr)) < 1e-3

    # 2. Positive event counts: CI must strictly bracket point estimate lambda
    for k in [1, 5, 20, 50]:
        rate = k / t_hr
        ci = poisson_rate_ci_95(k, t_hr, two_sided=True)
        assert ci is not None
        low, high = ci
        assert 0.0 < low < rate < high
        assert high - low > 0.0


def test_invariant_json_csv_export_reproducibility():
    """Verify exported JSON and CSV reports reproduce in-memory calculations exactly."""
    metrics = {
        "matched_count": 4,
        "unintended_dispatches": 1,
        "total_dispatches": 5,
        "total_intended_events": 4,
        "session_duration_sec": 120.0,
        "intended_duration_sec": 1.6,
        "non_command_duration_sec": 118.4,
        "non_command_hours": 118.4 / 3600.0,
        "false_activations_per_hour": 1.0 / (118.4 / 3600.0),
        "false_activations_ci_95_lower": 0.05,
        "false_activations_ci_95_upper": 150.0,
        "recall": 1.0,
        "precision": 0.8,
        "latency_p50_ms": 250.0,
        "latency_p95_ms": 280.0,
    }

    report = {
        "condition_a": metrics,
        "condition_b": metrics,
        "condition_c": metrics,
        "metadata": {
            "dataset_version": "test-v1",
            "total_frames": 3600,
            "session_duration_sec": 120.0,
            "non_command_hours": 118.4 / 3600.0,
        },
    }

    with tempfile.TemporaryDirectory() as td:
        json_path = export_benchmark_json(report, td)
        csv_path = export_benchmark_csv(report, td)

        assert json_path.exists()
        assert csv_path.exists()

        # Check JSON fidelity
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert loaded["results"]["condition_c"]["matched_count"] == 4
        assert loaded["results"]["condition_c"]["unintended_dispatches"] == 1
        assert abs(loaded["results"]["condition_c"]["precision"] - 0.8) < 1e-6
        assert loaded["results"]["metadata"]["total_frames"] == 3600

        # Check CSV content contains metric headers and correct condition values
        csv_text = csv_path.read_text(encoding="utf-8")
        assert (
            "Condition,Unintended_Dispatches,Non_Command_Hours,FA_Per_Hour,Recall,Precision"
            in csv_text
        )
        assert "C_MORPH_Intention_Gated,1," in csv_text
