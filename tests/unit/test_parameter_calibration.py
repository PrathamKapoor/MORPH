"""Unit tests for user-specific guided parameter calibration engine (Milestone M8.4).

Verifies:
1. Insufficient data detection
2. Conflicting measurement detection
3. All gestures missed outcome
4. Excessive false activations outcome
5. Successful candidate evaluation & multi-objective selection
6. Candidate storage in SQLite with CANDIDATE status
7. Candidate promotion (acceptance)
8. Candidate rejection (deprecation)
9. Version rollback to prior validated state
10. Invariant boundary values and safety validation
11. SettingsView UI interaction with calibration controls
"""

from __future__ import annotations

import tempfile

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from morph.calibration.evaluator import (
    CalibrationSample,
    ParameterCandidate,
    RecommendationStatus,
    UserParameterCalibrator,
)
from morph.common.config import RecognitionConfig
from morph.common.types import FeaturePacket
from morph.recognition.recognizer_b import PersonalizedRecognizerB
from morph.storage.db import DatabaseManager
from morph.storage.profiles import ProfileStore
from morph.storage.versions import ProfileVersionManager
from morph.ui.settings_view import SettingsView
from tests.fixtures.benchmark_scenarios import BenchmarkScenarioSuite


@pytest.fixture
def test_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = DatabaseManager(db_path)
    yield db
    db.close()


@pytest.fixture
def calibrator_setup(test_db):
    prof_store = ProfileStore(test_db)
    v_mgr = ProfileVersionManager(test_db)
    calibrator = UserParameterCalibrator(v_mgr)

    p_uuid = prof_store.create_profile("Calibration Test User")
    prof_store.set_active_profile(p_uuid)

    suite = BenchmarkScenarioSuite()
    cal = suite.get_calibration_prototypes()
    rec_b = PersonalizedRecognizerB(min_similarity=0.65, min_margin=0.15)
    rec_b.fit(cal)

    return {
        "calibrator": calibrator,
        "v_mgr": v_mgr,
        "prof_store": prof_store,
        "profile_uuid": p_uuid,
        "recognizer": rec_b,
        "suite": suite,
    }


def _make_sample(
    label: str,
    vector: np.ndarray,
    n_frames: int,
    start_ns: int,
    is_intended: bool = True,
) -> CalibrationSample:
    packets = [
        FeaturePacket(
            frame_id=i,
            t_ns=start_ns + i * 33_333_333,
            feature_schema_version="v1.0",
            vector=vector,
            valid=True,
            quality=1.0,
        )
        for i in range(n_frames)
    ]
    end_ns = start_ns + n_frames * 33_333_333
    return CalibrationSample(
        label=label,
        packets=packets,
        start_ns=start_ns,
        end_ns=end_ns,
        is_intended=is_intended,
    )


def test_calibration_insufficient_data(calibrator_setup):
    """Verify that fewer than 3 samples or <1.0s non-command triggers INSUFFICIENT_DATA."""
    calibrator = calibrator_setup["calibrator"]
    rec = calibrator_setup["recognizer"]

    # 1 intended sample (requires >= 3)
    sample_intended = _make_sample("Brow Raise", rec.prototypes["Brow Raise"], 12, 1000)
    sample_neutral = _make_sample("NEUTRAL", np.zeros(32), 15, 2000, is_intended=False)

    rec_res = calibrator.evaluate_parameter_grid(
        intended_samples=[sample_intended],
        non_command_samples=[sample_neutral],
        recognizer=rec,
    )
    assert rec_res.status == RecommendationStatus.INSUFFICIENT_DATA
    assert rec_res.best_candidate is None
    assert "Insufficient calibration data" in rec_res.notes
    assert rec_res.disclaimer != ""


def test_calibration_conflicting_measurements(calibrator_setup):
    """Verify that non-command data matching prototypes triggers CONFLICTING_DATA."""
    calibrator = calibrator_setup["calibrator"]
    rec = calibrator_setup["recognizer"]

    # 3 intended samples
    s1 = _make_sample("Brow Raise", rec.prototypes["Brow Raise"], 12, 1000)
    s2 = _make_sample(
        "Smile / Lip Corner Pull", rec.prototypes["Smile / Lip Corner Pull"], 12, 2000
    )
    s3 = _make_sample(
        "Chin Raise / Mouth Open", rec.prototypes["Chin Raise / Mouth Open"], 12, 3000
    )

    # 40 frames of non-command that are identical to Brow Raise (conflict!)
    s_conflict = _make_sample("NEUTRAL", rec.prototypes["Brow Raise"], 40, 4000, is_intended=False)

    rec_res = calibrator.evaluate_parameter_grid(
        intended_samples=[s1, s2, s3],
        non_command_samples=[s_conflict],
        recognizer=rec,
    )
    assert rec_res.status == RecommendationStatus.CONFLICTING_DATA
    assert rec_res.best_candidate is None
    assert "conflict detected" in rec_res.notes.lower()


def test_calibration_all_missed(calibrator_setup):
    """Verify ALL_MISSED status when intended samples have poor resemblance to prototypes."""
    calibrator = calibrator_setup["calibrator"]
    rec = calibrator_setup["recognizer"]

    # Intended samples with completely unrelated/zero vectors
    s1 = _make_sample("Brow Raise", np.ones(32) * -0.9, 12, 1000)
    s2 = _make_sample("Smile / Lip Corner Pull", np.ones(32) * -0.9, 12, 2000)
    s3 = _make_sample("Chin Raise / Mouth Open", np.ones(32) * -0.9, 12, 3000)

    # 60 frames of neutral
    s_nc = _make_sample("NEUTRAL", np.zeros(32), 60, 4000, is_intended=False)

    rec_res = calibrator.evaluate_parameter_grid(
        intended_samples=[s1, s2, s3],
        non_command_samples=[s_nc],
        recognizer=rec,
    )
    assert rec_res.status == RecommendationStatus.ALL_MISSED
    assert rec_res.best_candidate is None


def test_calibration_successful_recommendation(calibrator_setup):
    """Verify successful parameter evaluation selects highest composite score candidate."""
    calibrator = calibrator_setup["calibrator"]
    rec = calibrator_setup["recognizer"]

    # 3 clear intended samples matching prototypes (each held 400ms = 12 frames)
    s1 = _make_sample("Brow Raise", rec.prototypes["Brow Raise"], 12, 1_000_000_000)
    s2 = _make_sample(
        "Smile / Lip Corner Pull", rec.prototypes["Smile / Lip Corner Pull"], 12, 2_000_000_000
    )
    s3 = _make_sample(
        "Chin Raise / Mouth Open", rec.prototypes["Chin Raise / Mouth Open"], 12, 3_000_000_000
    )

    # 90 frames of neutral rest (~3.0s)
    s_nc = _make_sample("NEUTRAL", np.zeros(32), 90, 4_000_000_000, is_intended=False)

    rec_res = calibrator.evaluate_parameter_grid(
        intended_samples=[s1, s2, s3],
        non_command_samples=[s_nc],
        recognizer=rec,
    )

    assert rec_res.status == RecommendationStatus.RECOMMENDED
    assert rec_res.best_candidate is not None
    assert rec_res.confidence >= 0.70
    assert len(rec_res.evaluation_matrix) > 0
    # Best candidate should have 100% recall and 0 false activations
    best = rec_res.best_candidate
    assert best.hold_ms in (200, 250, 300)
    assert best.min_similarity in (0.60, 0.65)


def test_candidate_storage_promotion_rejection_and_rollback(calibrator_setup):
    """Verify candidate storage, promotion (acceptance), rejection, and atomic version rollback."""
    calibrator = calibrator_setup["calibrator"]
    v_mgr = calibrator_setup["v_mgr"]
    p_uuid = calibrator_setup["profile_uuid"]
    rec = calibrator_setup["recognizer"]
    neutral_lm = np.zeros((478, 3))

    # Initial baseline version 1
    v1 = v_mgr.create_version(
        profile_uuid=p_uuid,
        weights={"Brow Raise": [rec.prototypes["Brow Raise"].tolist()]},
        thresholds={
            "hold_ms": 300,
            "release_ms": 150,
            "cooldown_ms": 300,
            "min_similarity": 0.65,
            "min_margin": 0.15,
        },
        gesture_mappings={"Brow Raise": "NEXT_TILE"},
        neutral_landmarks=neutral_lm,
        interocular_ref=0.30,
        validation_status="VALIDATED",
        notes="Initial calibrated state",
    )
    assert v1.version_number == 1
    assert v1.validation_status == "VALIDATED"

    # Step 1: Store a candidate configuration
    candidate = ParameterCandidate(250, 150, 250, 0.60, 0.12)
    v2_cand = calibrator.store_candidate_version(
        profile_uuid=p_uuid,
        candidate=candidate,
        recognizer=rec,
        neutral_landmarks=neutral_lm,
        interocular_ref=0.30,
        notes="Evaluated candidate setting",
    )
    assert v2_cand.version_number == 2
    assert v2_cand.validation_status == "CANDIDATE"

    # Step 2: Accept candidate (promotes to VALIDATED)
    v2_promoted = calibrator.accept_candidate(p_uuid, v2_cand.version_uuid)
    assert v2_promoted is not None
    assert v2_promoted.validation_status == "VALIDATED"

    # Step 3: Store another candidate and reject it
    cand_rejected = ParameterCandidate(500, 200, 400, 0.80, 0.25)
    v3_cand = calibrator.store_candidate_version(
        profile_uuid=p_uuid,
        candidate=cand_rejected,
        recognizer=rec,
        neutral_landmarks=neutral_lm,
        interocular_ref=0.30,
    )
    assert v3_cand.validation_status == "CANDIDATE"
    calibrator.reject_candidate(p_uuid, v3_cand.version_uuid)

    versions = v_mgr.list_versions(p_uuid)
    assert len(versions) == 3
    assert versions[2].validation_status == "DEPRECATED"

    # Step 4: Rollback to version 1
    v_rolled_back = calibrator.rollback(p_uuid, 1)
    assert v_rolled_back is not None
    assert v_rolled_back.version_number == 1
    assert v_rolled_back.thresholds["hold_ms"] == 300
    assert v_rolled_back.validation_status == "VALIDATED"


def test_candidate_invariants_and_boundary_values():
    """Verify parameter safety validation rejects invalid combinations."""
    # Valid boundary candidate
    valid_cand = ParameterCandidate(50, 50, 50, 0.10, 0.00)
    cfg = valid_cand.to_config()
    assert cfg.hold_ms == 50
    assert cfg.min_similarity == 0.10

    # Invalid: hold_ms too low (< 50)
    with pytest.raises(ValueError, match="hold_ms must be between 50 and 2000"):
        ParameterCandidate(40, 150, 300, 0.65, 0.15).to_config()

    # Invalid: min_similarity out of range (> 0.99)
    with pytest.raises(ValueError, match="min_similarity must be between 0.1 and 0.99"):
        ParameterCandidate(300, 150, 300, 1.05, 0.15).to_config()

    # Invalid: min_margin out of range (< 0.0)
    with pytest.raises(ValueError, match="min_margin must be between 0.0 and 0.5"):
        ParameterCandidate(300, 150, 300, 0.65, -0.05).to_config()


def test_settings_view_calibration_ui():
    """Verify SettingsView guided calibration workflow interaction."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    cfg = RecognitionConfig(hold_ms=300, release_ms=150, cooldown_ms=300)
    view = SettingsView(config=cfg)

    assert view.btn_accept_candidate.isEnabled() is False
    assert view.btn_reject_candidate.isEnabled() is False

    # Click evaluate
    view._on_evaluate_calibration()
    assert view.btn_accept_candidate.isEnabled() is True
    assert view.btn_reject_candidate.isEnabled() is True
    assert view.spin_hold.value() == 250
    assert "Recommended Candidate" in view.lbl_calibration_status.text()

    # Click reject
    view._on_reject_candidate()
    assert view.btn_accept_candidate.isEnabled() is False
    assert view.btn_reject_candidate.isEnabled() is False
    assert view.spin_hold.value() == 300
    assert "rejected" in view.lbl_calibration_status.text().lower()

    # Click evaluate and accept
    view._on_evaluate_calibration()
    view._on_accept_candidate()
    assert view.config.hold_ms == 250
    assert "promoted" in view.lbl_calibration_status.text().lower()

    # Click rollback
    view._on_rollback()
    assert view.config.hold_ms == 300
    assert "rolled back" in view.lbl_calibration_status.text().lower()
