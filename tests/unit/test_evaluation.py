"""Unit tests for evaluation matching, metrics calculation, and A/B/C replay."""

import tempfile

from morph.common.types import FeaturePacket, GroundTruthEvent, LandmarkPacket
from morph.evaluation.exporter import export_benchmark_csv, export_benchmark_json
from morph.evaluation.matching import match_events_one_to_one
from morph.evaluation.metrics import (
    calculate_benchmark_metrics,
    compute_merged_interval_duration_sec,
    poisson_rate_ci_95,
)
from morph.evaluation.replay import ReplayEngine
from morph.evaluation.session import EvaluationSession
from morph.features.normalizer import FeatureExtractor
from morph.recognition.recognizer_a import BaselineRecognizerA
from morph.recognition.recognizer_b import PersonalizedRecognizerB
from tests.fixtures.synthetic_faces import (
    create_synthetic_brow_raise_landmarks,
    create_synthetic_neutral_landmarks,
)


def test_one_to_one_matching_and_unclamped_latency():
    gts = [
        GroundTruthEvent(
            label="Brow Raise",
            start_ns=1_000_000_000,
            end_ns=1_500_000_000,
            annotator="test",
            session_id="s1",
        ),
        GroundTruthEvent(
            label="Smile / Lip Corner Pull",
            start_ns=3_000_000_000,
            end_ns=3_500_000_000,
            annotator="test",
            session_id="s1",
        ),
    ]

    # Dispatch 1: Matches Brow Raise, fires 50ms before end (negative latency -50ms!)
    # Dispatch 2: Duplicate dispatch for Brow Raise (must NOT match; 1-to-1 matching rule)
    # Dispatch 3: Matches Smile, fires 100ms after end (+100ms latency)
    # Dispatch 4: Spurious dispatch during non-command time
    dispatches = [
        ("NEXT_TILE", 1_450_000_000),  # early trigger: 1.45s - 1.50s = -50 ms
        ("NEXT_TILE", 1_480_000_000),  # duplicate: should remain unmatched
        ("SELECT_TILE", 3_600_000_000),  # 3.60s - 3.50s = +100 ms
        ("NEXT_TILE", 5_000_000_000),  # spurious false activation
    ]

    matched, unmatched_disp, unmatched_gt = match_events_one_to_one(gts, dispatches)

    assert len(matched) == 2
    assert len(unmatched_disp) == 2
    assert len(unmatched_gt) == 0

    # Verify negative latency offset was preserved
    assert abs(matched[0].latency_offset_ms - (-50.0)) < 1e-3
    assert abs(matched[1].latency_offset_ms - 100.0) < 1e-3


def test_metrics_calculation_zero_denominators_na():
    # Case 1: Session with zero non-command hours (all time was command time)
    metrics_zero_non_cmd = calculate_benchmark_metrics(
        matched_pairs=[],
        unmatched_dispatches=[],
        unmatched_gts=[],
        total_session_duration_sec=10.0,
        total_intended_duration_sec=10.0,
    )
    # Must be None (rendered as N/A in UI), NOT 0.0
    assert metrics_zero_non_cmd["false_activations_per_hour"] is None
    assert metrics_zero_non_cmd["recall"] is None
    assert metrics_zero_non_cmd["precision"] is None

    # Case 2: Session with 1 false alarm over 0.5 hours non-command time -> FA/hr = 2.0
    matched_fake = []
    unmatched_fake = [("NEXT_TILE", 1000)]
    metrics_valid = calculate_benchmark_metrics(
        matched_pairs=matched_fake,
        unmatched_dispatches=unmatched_fake,
        unmatched_gts=[],
        total_session_duration_sec=1800.0,
        total_intended_duration_sec=0.0,
    )
    assert metrics_valid["false_activations_per_hour"] == 2.0


def test_replay_engine_abc_comparison():
    neutral_lm = create_synthetic_neutral_landmarks()
    eye_dist = 0.30
    extractor = FeatureExtractor(neutral_lm, eye_dist)

    brow_proto = extractor.extract(
        LandmarkPacket(
            frame_id=1,
            t_ns=1000,
            face_count=1,
            normalized_landmarks=create_synthetic_brow_raise_landmarks(),
            valid=True,
        )
    ).vector

    rec_b = PersonalizedRecognizerB(min_similarity=0.65, min_margin=0.15)
    rec_b.fit({"Brow Raise": [brow_proto] * 5})
    rec_a = BaselineRecognizerA()

    replay = ReplayEngine(rec_a=rec_a, rec_b=rec_b)

    # Stream:
    # 30 frames of neutral
    # 15 frames of Brow Raise (hold for 450 ms >= 300 ms hold)
    # 30 frames of neutral
    stream: list[FeaturePacket] = []
    t_base = 1_000_000_000

    f_id = 0
    for _ in range(30):
        f_id += 1
        stream.append(
            extractor.extract(
                LandmarkPacket(
                    frame_id=f_id,
                    t_ns=t_base + f_id * 30_000_000,
                    face_count=1,
                    normalized_landmarks=neutral_lm,
                    valid=True,
                )
            )
        )

    brow_start = t_base + (f_id + 1) * 30_000_000
    brow_lm = create_synthetic_brow_raise_landmarks()
    for _ in range(15):
        f_id += 1
        stream.append(
            extractor.extract(
                LandmarkPacket(
                    frame_id=f_id,
                    t_ns=t_base + f_id * 30_000_000,
                    face_count=1,
                    normalized_landmarks=brow_lm,
                    valid=True,
                )
            )
        )
    brow_end = t_base + f_id * 30_000_000

    for _ in range(30):
        f_id += 1
        stream.append(
            extractor.extract(
                LandmarkPacket(
                    frame_id=f_id,
                    t_ns=t_base + f_id * 30_000_000,
                    face_count=1,
                    normalized_landmarks=neutral_lm,
                    valid=True,
                )
            )
        )

    # Add a 2-frame (60ms) involuntary twitch that tests hold time gating
    for _ in range(2):
        f_id += 1
        stream.append(
            extractor.extract(
                LandmarkPacket(
                    frame_id=f_id,
                    t_ns=t_base + f_id * 30_000_000,
                    face_count=1,
                    normalized_landmarks=brow_lm,
                    valid=True,
                )
            )
        )

    for _ in range(30):
        f_id += 1
        stream.append(
            extractor.extract(
                LandmarkPacket(
                    frame_id=f_id,
                    t_ns=t_base + f_id * 30_000_000,
                    face_count=1,
                    normalized_landmarks=neutral_lm,
                    valid=True,
                )
            )
        )

    gts = [
        GroundTruthEvent(
            label="Brow Raise",
            start_ns=brow_start,
            end_ns=brow_end,
            annotator="test",
            session_id="s1",
        )
    ]

    report = replay.run_replay(stream, gts, is_synthetic=True)

    # Condition C (intention gated) should confirm exactly 1 command for the sustained gesture and reject the 60ms twitch!
    cond_c = report["condition_c"]
    assert cond_c["matched_count"] == 1
    assert cond_c["unintended_dispatches"] == 0
    assert cond_c["recall"] == 1.0
    assert cond_c["precision"] == 1.0

    # In Condition B (debounced without hold gating), the 60ms twitch triggers a false activation!
    cond_b = report["condition_b"]
    assert cond_b["matched_count"] == 1
    assert cond_b["unintended_dispatches"] >= 1
    assert cond_b["precision"] < 1.0

    # Verify ablations are computed
    assert "ablations" in report
    assert "no_hold" in report["ablations"]
    assert "no_release" in report["ablations"]
    assert "no_margin" in report["ablations"]

    # Export report test
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = export_benchmark_json(report, export_dir=tmpdir)
        csv_path = export_benchmark_csv(report, export_dir=tmpdir)
        assert json_path.exists()
        assert csv_path.exists()


def test_consented_session_privacy():
    session_no_consent = EvaluationSession(profile_uuid="p1", consented=False)
    pkt = FeaturePacket(
        frame_id=1, t_ns=1000, feature_schema_version="v1", vector=None, valid=False, quality=0.0
    )

    # Must reject recording when consent is False
    assert session_no_consent.record_feature(pkt) is False
    assert len(session_no_consent.recorded_features) == 0

    session_consented = EvaluationSession(profile_uuid="p1", consented=True)
    assert session_consented.record_feature(pkt) is True
    assert len(session_consented.recorded_features) == 1


def test_compute_merged_interval_duration_sec():
    # Empty intervals
    assert compute_merged_interval_duration_sec([]) == 0.0

    # Disjoint intervals: [1.0s, 2.0s] and [3.0s, 4.0s] -> 2.0s
    disjoint = [(1_000_000_000, 2_000_000_000), (3_000_000_000, 4_000_000_000)]
    assert abs(compute_merged_interval_duration_sec(disjoint) - 2.0) < 1e-6

    # Overlapping intervals: [1.0s, 3.0s] and [2.0s, 4.0s] -> [1.0s, 4.0s] = 3.0s (NOT 4.0s)
    overlapping = [(1_000_000_000, 3_000_000_000), (2_000_000_000, 4_000_000_000)]
    assert abs(compute_merged_interval_duration_sec(overlapping) - 3.0) < 1e-6

    # Fully nested intervals: [1.0s, 5.0s] and [2.0s, 3.0s] -> 4.0s
    nested = [(1_000_000_000, 5_000_000_000), (2_000_000_000, 3_000_000_000)]
    assert abs(compute_merged_interval_duration_sec(nested) - 4.0) < 1e-6


def test_poisson_confidence_intervals():
    # Zero exposure or negative counts
    assert poisson_rate_ci_95(0, 0.0) is None
    assert poisson_rate_ci_95(-1, 1.0) is None

    # Two-sided 95% Garwood CI for zero count: lower bound 0.0, upper bound -ln(0.025)/T ~= 3.688879/T
    ci_zero_2sided = poisson_rate_ci_95(0, 1.0, two_sided=True)
    assert ci_zero_2sided is not None
    assert ci_zero_2sided[0] == 0.0
    assert abs(ci_zero_2sided[1] - 3.688879) < 0.001

    # One-sided 95% upper limit for zero count: upper bound -ln(0.05)/T ~= 2.995732/T (~3.0/T)
    ci_zero_1sided = poisson_rate_ci_95(0, 1.0, two_sided=False)
    assert ci_zero_1sided is not None
    assert ci_zero_1sided[0] == 0.0
    assert abs(ci_zero_1sided[1] - 2.995732) < 0.001

    # Count = 5 over 0.5 hours -> rate = 10.0, CI strictly brackets 10.0
    ci_five = poisson_rate_ci_95(5, 0.5, two_sided=True)
    assert ci_five is not None
    assert ci_five[0] < 10.0 < ci_five[1]
    assert abs(ci_five[0] - 3.247) < 0.1
    assert abs(ci_five[1] - 23.337) < 0.1


def test_expanded_20_scenario_benchmark_suite():
    from tests.fixtures.benchmark_scenarios import BenchmarkScenarioSuite, verify_zero_leakage

    suite = BenchmarkScenarioSuite()
    stream, gts, intervals = suite.build_full_challenge_stream()

    # Verify all 20 scenarios are generated
    assert len(intervals) == 20
    assert len(stream) > 3400  # Includes 3000 frames of long exposure + 400 frames of challenges
    assert (
        len(gts) == 4
    )  # 4 intentional ground-truth commands (Brow Raise x2, Smile x1, Mouth Open x1)

    # Isolated calibration prototypes (distinct enrollment trials)
    cal_prototypes = suite.get_calibration_prototypes()

    # Assert zero data leakage between calibration prototypes and evaluation benchmark
    leakage = verify_zero_leakage(cal_prototypes, stream)
    assert leakage["zero_leakage_passed"] is True
    assert leakage["min_euclidean_distance"] > 0.001

    rec_b = PersonalizedRecognizerB(min_similarity=0.65, min_margin=0.15)
    rec_b.fit(cal_prototypes)
    rec_a = BaselineRecognizerA()

    replay = ReplayEngine(rec_a=rec_a, rec_b=rec_b)
    report = replay.run_replay(
        stream, gts, is_synthetic=True, dataset_version="20-scenario-suite-v1"
    )

    # In Condition C (IntentEngine FSM), involuntary twitches, head motion, and blends are suppressed
    assert "condition_c" in report
    cond_c = report["condition_c"]
    assert cond_c["matched_count"] == 4
    assert cond_c["recall"] == 1.0
    assert cond_c["unintended_dispatches"] == 0
    assert cond_c["false_activations_per_hour"] == 0.0
    # Exact Poisson 95% CI upper bound for 0 events over non-command hours
    assert cond_c["false_activations_ci_95_lower"] == 0.0
    assert cond_c["false_activations_ci_95_upper"] is not None
    assert cond_c["false_activations_ci_95_upper"] > 0.0

    # In Condition B and Condition A, unmitigated twitches and blends generate false alarms
    cond_b = report["condition_b"]
    assert cond_b["unintended_dispatches"] > 0
    assert cond_b["false_activations_per_hour"] > 0.0
    assert cond_b["false_activations_ci_95_lower"] is not None
    assert cond_b["false_activations_ci_95_lower"] > 0.0

    cond_a = report["condition_a"]
    assert cond_a["unintended_dispatches"] >= cond_b["unintended_dispatches"]
    assert cond_a["false_activations_per_hour"] >= cond_b["false_activations_per_hour"]
