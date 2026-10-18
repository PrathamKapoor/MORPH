"""Benchmark metric calculations: FA/hr, precision, recall, and Poisson confidence intervals (Milestone M7.1)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from morph.common.types import GroundTruthEvent
from morph.evaluation.matching import MatchedPair


def compute_merged_interval_duration_sec(
    intervals: list[tuple[int, int] | Any],
) -> float:
    """Compute total duration of intervals in seconds, deterministically merging any overlaps.

    Args:
        intervals: List of (start_ns, end_ns) timestamp intervals or objects with start_ns/end_ns.

    Returns:
        Total duration in seconds covered by the union of all intervals.
    """
    if not intervals:
        return 0.0

    raw_pairs: list[tuple[int, int]] = []
    for item in intervals:
        if hasattr(item, "start_ns") and hasattr(item, "end_ns"):
            raw_pairs.append((item.start_ns, item.end_ns))
        else:
            s, e = item
            raw_pairs.append((s, e))

    valid_intervals = [(min(s, e), max(s, e)) for s, e in raw_pairs if s != e]
    if not valid_intervals:
        return 0.0

    # Sort intervals by start timestamp
    sorted_intervals = sorted(valid_intervals, key=lambda x: (x[0], x[1]))
    merged: list[tuple[int, int]] = [sorted_intervals[0]]

    for cur_s, cur_e in sorted_intervals[1:]:
        last_s, last_e = merged[-1]
        if cur_s <= last_e:
            # Overlapping or contiguous; merge
            merged[-1] = (last_s, max(last_e, cur_e))
        else:
            merged.append((cur_s, cur_e))

    total_ns = sum(e - s for s, e in merged)
    return total_ns / 1_000_000_000.0


def poisson_rate_ci_95(
    k: int, exposure_hours: float, two_sided: bool = True
) -> tuple[float, float] | None:
    """Calculate exact 95% Poisson confidence interval for event rate lambda = k / exposure_hours.

    Uses the exact Garwood (1936) formulation via Poisson cumulative probabilities.

    Distinction:
    - Two-sided 95% CI (two_sided=True, alpha=0.05, alpha/2=0.025 on each tail):
        For k = 0, mu_lower = 0.0, mu_upper = -ln(0.025) ~= 3.688879.
        For k > 0, mu_lower solves P(X <= k-1 | mu) = 0.975, mu_upper solves P(X <= k | mu) = 0.025.
    - One-sided 95% upper limit (two_sided=False, alpha=0.05 on upper tail):
        For k = 0, mu_lower = 0.0, mu_upper = -ln(0.05) ~= 2.995732 (~3.0/T).
        For k > 0, mu_lower = 0.0, mu_upper solves P(X <= k | mu) = 0.05.

    Returns None if exposure_hours <= 1e-6 or k < 0.
    """
    if exposure_hours <= 1e-6 or k < 0:
        return None

    alpha = 0.05

    if two_sided:
        alpha_lower = alpha / 2.0  # 0.025
        alpha_upper = 1.0 - alpha / 2.0  # 0.975

        # 1. Lower bound for Poisson parameter mu
        if k == 0:
            mu_lower = 0.0
        else:

            def cdf_lower(mu: float) -> float:
                terms = [math.exp(-mu)]
                cur = terms[0]
                for j in range(1, k):
                    cur *= mu / j
                    terms.append(cur)
                return sum(terms)

            low, high = 0.0, float(k)
            for _ in range(80):
                mid = (low + high) / 2.0
                if cdf_lower(mid) > alpha_upper:
                    low = mid
                else:
                    high = mid
            mu_lower = (low + high) / 2.0

        # 2. Upper bound for Poisson parameter mu
        if k == 0:
            mu_upper = -math.log(alpha_lower)  # -ln(0.025) ~= 3.688879
        else:

            def cdf_upper(mu: float) -> float:
                terms = [math.exp(-mu)]
                cur = terms[0]
                for j in range(1, k + 1):
                    cur *= mu / j
                    terms.append(cur)
                return sum(terms)

            low, high = float(k), float(max(10.0, 4.0 * k + 10.0))
            for _ in range(80):
                mid = (low + high) / 2.0
                if cdf_upper(mid) > alpha_lower:
                    low = mid
                else:
                    high = mid
            mu_upper = (low + high) / 2.0

        return (mu_lower / exposure_hours, mu_upper / exposure_hours)
    else:
        # One-sided 95% upper limit
        mu_lower = 0.0
        if k == 0:
            mu_upper = -math.log(alpha)  # -ln(0.05) ~= 2.995732
        else:

            def cdf_onesided(mu: float) -> float:
                terms = [math.exp(-mu)]
                cur = terms[0]
                for j in range(1, k + 1):
                    cur *= mu / j
                    terms.append(cur)
                return sum(terms)

            low, high = float(k), float(max(10.0, 4.0 * k + 10.0))
            for _ in range(80):
                mid = (low + high) / 2.0
                if cdf_onesided(mid) > alpha:
                    low = mid
                else:
                    high = mid
            mu_upper = (low + high) / 2.0

        return (mu_lower / exposure_hours, mu_upper / exposure_hours)


def calculate_benchmark_metrics(
    matched_pairs: list[MatchedPair],
    unmatched_dispatches: list[tuple[str, int]],
    unmatched_gts: list[GroundTruthEvent],
    total_session_duration_sec: float,
    total_intended_duration_sec: float,
    stage_latencies_ms: dict[str, float] | None = None,
    calibration_time_sec: float | None = None,
    gesture_retraining_count: int | None = None,
    task_completion_rate: float | None = None,
    action_correction_count: int | None = None,
    tracking_failure_time_sec: float | None = None,
) -> dict[str, float | int | tuple[float, float] | dict[str, float] | str | None]:
    """Calculate transparent benchmark metrics with exact Poisson confidence intervals.

    Never returns 0.0 for zero denominators; returns None (rendered as N/A in UI).
    Calculates both two-sided 95% Garwood confidence interval and one-sided 95% upper limit.
    Includes True Positives, False Positives, False Negatives, F1 score, and task usability metrics.
    """
    n_matched = len(matched_pairs)
    n_unmatched = len(unmatched_dispatches)
    n_false_negatives = len(unmatched_gts)
    n_total_dispatches = n_matched + n_unmatched
    n_total_intended = n_matched + n_false_negatives

    # Invariant assertions
    if n_matched < 0 or n_unmatched < 0:
        raise ValueError(
            f"Counts must be non-negative: matched={n_matched}, unmatched={n_unmatched}"
        )
    if n_matched > n_total_intended:
        raise ValueError(
            f"Matched count {n_matched} cannot exceed total intended events {n_total_intended}"
        )
    if total_intended_duration_sec < 0.0 or total_session_duration_sec < 0.0:
        raise ValueError("Durations must be non-negative")

    # 1. Non-command duration in seconds and hours
    # Clamped non-command duration: cannot exceed session duration, cannot be negative
    clamped_intended_sec = min(total_session_duration_sec, total_intended_duration_sec)
    non_command_sec = max(0.0, total_session_duration_sec - clamped_intended_sec)
    non_command_hours = non_command_sec / 3600.0

    # 2. Unintended Activations per Non-Command Hour (FA/hr) & Poisson Confidence Intervals
    if non_command_hours > 1e-6:
        fa_per_hour: float | None = float(n_unmatched / non_command_hours)
        ci_two_sided = poisson_rate_ci_95(n_unmatched, non_command_hours, two_sided=True)
        ci_one_sided = poisson_rate_ci_95(n_unmatched, non_command_hours, two_sided=False)

        fa_ci_lower = float(ci_two_sided[0]) if ci_two_sided else None
        fa_ci_upper = float(ci_two_sided[1]) if ci_two_sided else None
        fa_one_sided_upper = float(ci_one_sided[1]) if ci_one_sided else None
    else:
        # Zero denominator -> N/A (None), NOT zero
        fa_per_hour = None
        fa_ci_lower = None
        fa_ci_upper = None
        fa_one_sided_upper = None

    # 3. Recall
    if n_total_intended > 0:
        recall: float | None = float(n_matched / n_total_intended)
    else:
        recall = None

    # 4. Precision
    if n_total_dispatches > 0:
        precision: float | None = float(n_matched / n_total_dispatches)
    else:
        precision = None

    # 5. F1 Score
    if precision is not None and recall is not None:
        denom = precision + recall
        f1_score: float | None = float(2.0 * (precision * recall) / denom) if denom > 0.0 else 0.0
    else:
        f1_score = None

    # 6. Latency Percentiles (P50 and P95)
    if matched_pairs:
        offsets = [p.latency_offset_ms for p in matched_pairs]
        p50_latency: float | None = float(np.percentile(offsets, 50))
        p95_latency: float | None = float(np.percentile(offsets, 95))
    else:
        p50_latency = None
        p95_latency = None

    result: dict[str, Any] = {
        "matched_count": n_matched,
        "true_positives": n_matched,
        "unintended_dispatches": n_unmatched,
        "false_positives": n_unmatched,
        "false_negatives": n_false_negatives,
        "total_dispatches": n_total_dispatches,
        "total_intended_events": n_total_intended,
        "session_duration_sec": total_session_duration_sec,
        "intended_duration_sec": clamped_intended_sec,
        "non_command_duration_sec": non_command_sec,
        "non_command_hours": non_command_hours,
        "false_activations_per_hour": fa_per_hour,
        "false_activations_ci_95_lower": fa_ci_lower,
        "false_activations_ci_95_upper": fa_ci_upper,
        "false_activations_ci_95_one_sided_upper": fa_one_sided_upper,
        "ci_method": "Garwood Poisson exact (two-sided 95% CI and one-sided 95% upper limit)",
        "recall": recall,
        "precision": precision,
        "f1_score": f1_score,
        "latency_p50_ms": p50_latency,
        "latency_p95_ms": p95_latency,
    }

    if stage_latencies_ms:
        result["stage_latencies_ms"] = stage_latencies_ms
    if calibration_time_sec is not None:
        result["calibration_time_sec"] = calibration_time_sec
    if gesture_retraining_count is not None:
        result["gesture_retraining_count"] = gesture_retraining_count
    if task_completion_rate is not None:
        result["task_completion_rate"] = task_completion_rate
    if action_correction_count is not None:
        result["action_correction_count"] = action_correction_count
    if tracking_failure_time_sec is not None:
        result["tracking_failure_time_sec"] = tracking_failure_time_sec

    return result
