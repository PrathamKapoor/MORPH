"""Unit tests verifying dataset integrity, holdout isolation, and zero-leakage guarantees (Milestone M7.2)."""

from __future__ import annotations

import numpy as np
import pytest

from morph.common.types import EvaluationScenario, FeaturePacket, LandmarkPacket
from morph.evaluation.independence import DatasetIndependenceAuditor
from morph.evaluation.replay import ReplayEngine
from morph.recognition.recognizer_a import BaselineRecognizerA
from morph.recognition.recognizer_b import PersonalizedRecognizerB
from tests.fixtures.benchmark_scenarios import BenchmarkScenarioSuite, verify_zero_leakage
from tests.fixtures.synthetic_faces import (
    create_synthetic_held_out_landmarks,
)


def test_zero_leakage_between_calibration_and_evaluation():
    """Verify that no benchmark evaluation vector is identical to any calibration prototype vector."""
    suite = BenchmarkScenarioSuite()
    stream, gts, intervals = suite.build_full_challenge_stream()
    cal_prototypes = suite.get_calibration_prototypes()

    # 1. Assert calibration prototypes are populated for all 3 gestures
    assert len(cal_prototypes) == 3
    for _name, vecs in cal_prototypes.items():
        assert len(vecs) == 5
        for v in vecs:
            assert v is not None
            assert len(v) == 32
            assert np.all(np.isfinite(v))

    # 2. Run zero leakage audit
    leakage = verify_zero_leakage(cal_prototypes, stream, tolerance=1e-4)

    assert leakage["zero_leakage_passed"] is True
    # The minimum Euclidean distance across all 3,520 frames must be strictly positive
    assert leakage["min_euclidean_distance"] > 0.001
    assert leakage["mean_euclidean_distance"] > 0.01
    assert leakage["evaluated_frames"] > 3400
    assert leakage["calibration_prototypes"] == 15


def test_zero_leakage_detects_synthetic_leakage():
    """Verify that verify_zero_leakage raises an error or fails if identical vectors are leaked."""
    suite = BenchmarkScenarioSuite()
    cal_prototypes = suite.get_calibration_prototypes()

    # Leak a calibration prototype directly into an evaluation stream packet
    leaked_vector = cal_prototypes["Brow Raise"][0].copy()
    leaked_packet = FeaturePacket(
        frame_id=1,
        t_ns=1_000_000_000,
        feature_schema_version="v1.0",
        vector=leaked_vector,
        valid=True,
        quality=1.0,
    )

    leakage = verify_zero_leakage(cal_prototypes, [leaked_packet], tolerance=1e-4)
    # Must fail zero leakage check
    assert leakage["zero_leakage_passed"] is False
    assert leakage["min_euclidean_distance"] < 1e-6


def test_zero_leakage_empty_inputs_handling():
    """Verify verify_zero_leakage raises ValueError on empty collections."""
    with pytest.raises(ValueError, match="Calibration prototype collection is empty"):
        verify_zero_leakage({}, [FeaturePacket(1, 1000, "v1", np.zeros(32), True, 1.0)])

    suite = BenchmarkScenarioSuite()
    cal = suite.get_calibration_prototypes()
    with pytest.raises(ValueError, match="Evaluation stream contains no valid"):
        verify_zero_leakage(cal, [])


def test_held_out_generalization_alignment():
    """Verify that held-out variants with scale, pose, and noise still generalize to prototype."""
    suite = BenchmarkScenarioSuite()
    cal = suite.get_calibration_prototypes()

    rec_b = PersonalizedRecognizerB(min_similarity=0.65, min_margin=0.15)
    rec_b.fit(cal)

    # Test held-out Brow Raise with physiological shift
    held_out_brow = create_synthetic_held_out_landmarks(
        "brow_raise",
        scale_offset=-0.02,
        yaw_offset=0.005,
        pitch_offset=-0.003,
        intensity=0.95,
        seed=777,
    )
    pkt_held_out = suite.extractor.extract(
        LandmarkPacket(
            frame_id=1,
            t_ns=1_000_000_000,
            face_count=1,
            normalized_landmarks=held_out_brow,
            valid=True,
        )
    )

    res = rec_b.predict(pkt_held_out)

    # Generalization test: correctly classifies Brow Raise with high similarity and ample margin
    assert res.accepted_candidate_or_none == "Brow Raise"
    assert res.label_scores[res.best_label] >= 0.70
    assert (res.label_scores[res.best_label] - res.label_scores[res.second_label]) >= 0.15


def test_auditor_all_six_rules_pass():
    """Verify DatasetIndependenceAuditor passes when all 6 independence rules are respected."""
    suite = BenchmarkScenarioSuite()
    cal = suite.get_calibration_prototypes()
    stream, _, _ = suite.build_full_challenge_stream()

    auditor = DatasetIndependenceAuditor(tolerance=1e-4)
    res = auditor.audit(
        calibration_prototypes=cal,
        evaluation_stream=stream,
        calibration_seeds=suite.get_calibration_seeds(),
        evaluation_seeds=suite.get_evaluation_seeds(),
        calibration_session_id="SESSION_CALIBRATION_001",
        evaluation_session_id="SESSION_EVALUATION_002",
        calibration_time_range_ns=(1_000_000_000, 3_000_000_000),
        evaluation_time_range_ns=(10_000_000_000, 120_000_000_000),
        shared_normalization_basis=False,
    )

    assert res.is_independent is True
    assert len(res.violated_rules) == 0
    assert len(res.passed_rules) == 6
    assert res.min_euclidean_distance > 0.001


def test_auditor_detects_violations():
    """Verify DatasetIndependenceAuditor flags session, temporal, seed, and normalization leakage."""
    suite = BenchmarkScenarioSuite()
    cal = suite.get_calibration_prototypes()
    stream, _, _ = suite.build_full_challenge_stream()
    auditor = DatasetIndependenceAuditor(tolerance=1e-4)

    # 1. Session collision
    res_sess = auditor.audit(
        calibration_prototypes=cal,
        evaluation_stream=stream,
        calibration_session_id="IDENTICAL_SESSION",
        evaluation_session_id="IDENTICAL_SESSION",
    )
    assert res_sess.is_independent is False
    assert auditor.RULE_DISJOINT_SESSION in res_sess.violated_rules

    # 2. Temporal overlap
    res_time = auditor.audit(
        calibration_prototypes=cal,
        evaluation_stream=stream,
        calibration_time_range_ns=(1000, 5000),
        evaluation_time_range_ns=(4000, 8000),
    )
    assert res_time.is_independent is False
    assert auditor.RULE_TEMPORAL_ISOLATION in res_time.violated_rules
    assert res_time.temporal_overlap_ns == 1000

    # 3. Seed collision
    res_seed = auditor.audit(
        calibration_prototypes=cal,
        evaluation_stream=stream,
        calibration_seeds=[100, 101, 102],
        evaluation_seeds=[102, 103, 104],
    )
    assert res_seed.is_independent is False
    assert auditor.RULE_SEED_ISOLATION in res_seed.violated_rules
    assert 102 in res_seed.colliding_seeds

    # 4. Transformation leakage
    res_norm = auditor.audit(
        calibration_prototypes=cal,
        evaluation_stream=stream,
        shared_normalization_basis=True,
    )
    assert res_norm.is_independent is False
    assert auditor.RULE_TRANSFORMATION_ISOLATION in res_norm.violated_rules


def test_eight_research_scenarios_generation_and_replay():
    """Verify that all 8 EvaluationScenario streams generate and evaluate properly."""
    suite = BenchmarkScenarioSuite()
    cal = suite.get_calibration_prototypes()

    rec_b = PersonalizedRecognizerB(min_similarity=0.65, min_margin=0.15)
    rec_b.fit(cal)
    rec_a = BaselineRecognizerA()
    replay = ReplayEngine(rec_a=rec_a, rec_b=rec_b)

    for scen in EvaluationScenario:
        stream, gts, dur = suite.build_scenario_stream(scen)
        assert len(stream) > 0
        assert dur > 0.0

        rep = replay.run_replay(
            stream,
            gts,
            session_duration_sec=dur,
            is_synthetic=True,
            dataset_version=f"TEST-{scen.name}",
        )
        assert "condition_a" in rep
        assert "condition_b" in rep
        assert "condition_c" in rep
        assert "true_positives" in rep["condition_c"]
        assert "false_positives" in rep["condition_c"]
        assert "false_negatives" in rep["condition_c"]
        assert "f1_score" in rep["condition_c"]

    # Specifically check distractor scenario: Condition C must have 0 false activations
    dist_stream, dist_gts, dist_dur = suite.build_scenario_stream(
        EvaluationScenario.SCEN_03_DISTRACTOR
    )
    dist_rep = replay.run_replay(
        dist_stream, dist_gts, session_duration_sec=dist_dur, is_synthetic=True
    )
    assert dist_rep["condition_c"]["false_positives"] == 0
    assert dist_rep["condition_b"]["false_positives"] > 0
