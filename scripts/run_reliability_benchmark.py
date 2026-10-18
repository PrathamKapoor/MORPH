"""Multi-Scenario Holdout Independence & Reliability Benchmark Runner (Milestone M8.3).

Executes reproducible A/B/C comparisons across:
1. Full 20-Scenario Challenge Suite
2. All 8 Structured Research Protocol Scenarios (EvaluationScenario)
3. 6-Rule Dataset Independence & Holdout Audit

Generates transparent empirical tables with Garwood Poisson 95% CIs and F1 scores,
exporting JSON results to research/benchmarks/reliability_benchmark_results.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def run_benchmark() -> dict[str, Any]:
    from morph.common.types import EvaluationScenario
    from morph.evaluation.independence import DatasetIndependenceAuditor
    from morph.evaluation.replay import ReplayEngine
    from morph.recognition.recognizer_a import BaselineRecognizerA
    from morph.recognition.recognizer_b import PersonalizedRecognizerB
    from tests.fixtures.benchmark_scenarios import BenchmarkScenarioSuite

    suite = BenchmarkScenarioSuite()
    cal_prototypes = suite.get_calibration_prototypes()
    cal_seeds = suite.get_calibration_seeds()
    eval_seeds = suite.get_evaluation_seeds()

    # 1. Dataset Independence Audit
    full_stream, full_gts, _ = suite.build_full_challenge_stream()
    auditor = DatasetIndependenceAuditor(tolerance=1e-4)
    audit_res = auditor.audit(
        calibration_prototypes=cal_prototypes,
        evaluation_stream=full_stream,
        calibration_seeds=cal_seeds,
        evaluation_seeds=eval_seeds,
        calibration_session_id="ENROLL-SESSION-CANONICAL",
        evaluation_session_id="EVAL-SESSION-EXP005",
        calibration_time_range_ns=(1_000_000_000, 3_500_000_000),
        evaluation_time_range_ns=(10_000_000_000, 130_000_000_000),
        shared_normalization_basis=False,
    )

    rec_b = PersonalizedRecognizerB(min_similarity=0.65, min_margin=0.15)
    rec_b.fit(cal_prototypes)
    rec_a = BaselineRecognizerA()

    replay = ReplayEngine(rec_a=rec_a, rec_b=rec_b)

    # 2. Full 20-Scenario Benchmark
    full_report = replay.run_replay(
        full_stream,
        full_gts,
        is_synthetic=True,
        dataset_version="EXP-005-CHALLENGE-SUITE-V2",
    )

    # 3. Eight Protocol Scenarios Benchmarks
    scenarios_reports: dict[str, Any] = {}
    for scen in EvaluationScenario:
        s_stream, s_gts, s_dur = suite.build_scenario_stream(scen)
        s_rep = replay.run_replay(
            s_stream,
            s_gts,
            session_duration_sec=s_dur,
            is_synthetic=True,
            dataset_version=f"EXP-005-{scen.name}",
        )
        scenarios_reports[scen.value] = {
            "duration_sec": s_dur,
            "frames": len(s_stream),
            "intended_events": len(s_gts),
            "condition_a": s_rep["condition_a"],
            "condition_b": s_rep["condition_b"],
            "condition_c": s_rep["condition_c"],
        }

    benchmark_output = {
        "benchmark_id": "EXP-005-RELIABILITY-V1",
        "timestamp_utc": "2026-10-17T21:25:00Z",
        "dataset_independence_audit": audit_res.to_dict(),
        "overall_challenge_suite": full_report,
        "eight_protocol_scenarios": scenarios_reports,
    }

    # Save to research/benchmarks/reliability_benchmark_results.json
    out_dir = Path("research/benchmarks")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "reliability_benchmark_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_output, f, indent=2)

    return benchmark_output


if __name__ == "__main__":
    results = run_benchmark()
    audit = results["dataset_independence_audit"]
    print("=" * 60)
    print("MORPH 2.0 -- RELIABILITY & HOLDOUT BENCHMARK (M8.3)")
    print("=" * 60)
    print(f"Holdout Independence Audit Passed: {audit['is_independent']}")
    print(f"Passed Rules: {audit['passed_rules']}")
    print(f"Min Euclidean Distance: {audit['min_euclidean_distance']:.5f}")
    print("\n--- 20-Scenario Challenge Suite Comparison ---")
    ov = results["overall_challenge_suite"]
    for c_key in ["condition_a", "condition_b", "condition_c"]:
        c = ov[c_key]
        print(
            f"[{c_key.upper()}] TP={c['true_positives']} FP={c['false_positives']} "
            f"FN={c['false_negatives']} Recall={c['recall']:.2f} Precision={c['precision']:.2f} "
            f"F1={c['f1_score']:.2f} FA/hr={c['false_activations_per_hour']:.2f} "
            f"95% CI=[{c['false_activations_ci_95_lower']}, {c['false_activations_ci_95_upper']}]"
        )
    print("=" * 60)
