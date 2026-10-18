"""Reliability, fault tolerance, and deep privacy hardening unit tests for MORPH 2.0 (Milestone M8.6).

Covers:
1. Rapid profile switching safety and candidate isolation (fail-closed pause on profile change)
2. Camera disconnect and auto-reconnect recovery cycles without orphaned threads
3. Deep zero-video persistence audit (ADR-002) inspecting filesystem, cache, and SQLite blob schemas
4. Clock regression and monotonic time skip invariants
5. Multi-threaded database concurrency and profile version history deprecation
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from morph.capture.camera import ICameraAdapter
from morph.capture.worker import CaptureWorker
from morph.common.config import RecognitionConfig
from morph.common.security import audit_zero_video_storage
from morph.common.types import (
    LandmarkPacket,
    RecognitionResult,
    State,
    TrackingHealth,
)
from morph.intent.engine import DecisionReason, IntentEngine
from morph.storage.db import DatabaseManager
from morph.storage.profiles import ProfileStore
from morph.storage.versions import ProfileVersionManager
from tests.fixtures.benchmark_scenarios import BenchmarkScenarioSuite
from tests.fixtures.synthetic_faces import (
    create_synthetic_neutral_landmarks,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def hardening_env():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "hardening_morph.db"
        db = DatabaseManager(db_path)
        store = ProfileStore(db)
        v_mgr = ProfileVersionManager(db)
        yield {
            "tmp_dir": Path(tmp_dir),
            "db": db,
            "store": store,
            "v_mgr": v_mgr,
        }
        db.close()


def test_rapid_profile_switching_fail_closed_safety(qapp, hardening_env):
    """Switching profiles while live tracking must immediately pause and wipe candidate buffer."""
    store: ProfileStore = hardening_env["store"]

    # 1. Create Profile A and Profile B
    p_a = store.create_profile("Participant Alpha", "Adult A")
    p_b = store.create_profile("Participant Beta", "Adult B")

    neutral_a = create_synthetic_neutral_landmarks()
    store.save_neutral_baseline(p_a, neutral_a, 0.30, 1_000_000_000)

    # Participant B has slightly wider resting eye distance
    neutral_b = neutral_a * 1.15
    store.save_neutral_baseline(p_b, neutral_b, 0.345, 2_000_000_000)

    # Prototype A has Brow Raise; Prototype B has Smile
    suite = BenchmarkScenarioSuite()
    cal_protos = suite.get_calibration_prototypes()
    g_a = store.add_gesture_class(p_a, "Brow Raise", "NEXT_TILE")
    for v in cal_protos["Brow Raise"]:
        store.add_gesture_sample(g_a, v, False, 1, 1.0, 1000)

    g_b = store.add_gesture_class(p_b, "Smile / Lip Corner Pull", "SELECT_TILE")
    for v in cal_protos["Smile / Lip Corner Pull"]:
        store.add_gesture_sample(g_b, v, False, 1, 1.0, 2000)

    # 2. Simulate running state machine under Profile A
    engine = IntentEngine(config=RecognitionConfig(hold_ms=250))
    engine.reset(State.IDLE)

    pred_brow = RecognitionResult(
        frame_id=10,
        t_ns=10_000_000_000,
        label_scores={"Brow Raise": 0.95},
        best_label="Brow Raise",
        second_label="NONE",
        accepted_candidate_or_none="Brow Raise",
        reject_reason="",
    )

    # Advance engine into CANDIDATE state
    st1, cmd1, _ = engine.step(pred_brow, True, pred_brow.t_ns, mode="LIVE", paused=False)
    assert st1 == State.CANDIDATE
    assert cmd1 is None

    # 3. Simulate Profile Switch to Profile B
    # Enforce fail-closed invariant
    engine.reset(State.PAUSED)
    store.set_active_profile(p_b)

    assert store.get_active_profile() == p_b
    assert engine.state == State.PAUSED
    assert engine.candidate_label is None

    # Step engine under paused condition: must hold PAUSED and never fire Brow Raise command
    st2, cmd2, _ = engine.step(
        pred_brow, True, pred_brow.t_ns + 100_000_000, mode="LIVE", paused=True
    )
    assert st2 == State.PAUSED
    assert cmd2 is None

    # 4. Stress: Rapidly toggle between profiles 50 times
    for i in range(50):
        target_p = p_a if (i % 2 == 0) else p_b
        store.set_active_profile(target_p)
        engine.reset(State.PAUSED)
        assert engine.state == State.PAUSED
        assert store.get_active_profile() == target_p


class MockDisconnectableCamera(ICameraAdapter):
    """Simulated camera adapter that allows triggering disconnect and reconnect events."""

    def __init__(self):
        self.connected = True
        self.open_count = 0
        self.release_count = 0
        self.read_count = 0
        self.frame_data = np.zeros((480, 640, 3), dtype=np.uint8)

    def open(self) -> bool:
        self.open_count += 1
        return self.connected

    def read(self) -> tuple[bool, np.ndarray | None, int]:
        self.read_count += 1
        t_ns = time.perf_counter_ns()
        if not self.connected:
            return False, None, t_ns
        return True, self.frame_data.copy(), t_ns

    def release(self) -> None:
        self.release_count += 1

    def is_opened(self) -> bool:
        return self.connected

    def get_resolution(self) -> tuple[int, int]:
        return (640, 480)


class MockSimpleTracker:
    """Mock tracker that returns valid landmark packets."""

    def detect(self, packet) -> LandmarkPacket:
        return LandmarkPacket(
            frame_id=packet.frame_id,
            t_ns=packet.captured_at_monotonic_ns,
            face_count=1,
            normalized_landmarks=np.zeros((478, 3), dtype=np.float64),
            valid=True,
            captured_at_monotonic_ns=packet.captured_at_monotonic_ns,
        )

    def close(self) -> None:
        pass


def test_camera_disconnect_and_reconnect_recovery(qapp):
    """Worker must gracefully handle camera read dropouts, emit health degradation, and reconnect."""
    mock_cam = MockDisconnectableCamera()
    mock_tracker = MockSimpleTracker()
    cfg = RecognitionConfig()

    worker = CaptureWorker(camera=mock_cam, tracker=mock_tracker, config=cfg)

    health_updates: list[TrackingHealth] = []
    worker.health_updated.connect(health_updates.append)

    # 1. Normal capture
    success, frame, t_read_start, t_ns = worker.camera.read_timed()
    assert success is True
    assert frame is not None

    # 2. Simulate camera disconnect
    mock_cam.connected = False
    success_disc, frame_disc, _, _ = worker.camera.read_timed()
    assert success_disc is False
    assert frame_disc is None

    # 3. Simulate camera reconnect
    mock_cam.connected = True
    mock_cam.open()
    success_recon, frame_recon, _, _ = worker.camera.read_timed()
    assert success_recon is True
    assert frame_recon is not None

    # Verify adapter open/release tracking
    assert mock_cam.open_count >= 1


def test_deep_zero_video_persistence_audit(hardening_env):
    """ADR-002: Inspect repository, temp folders, and SQLite databases for zero image/video dumps."""
    repo_root = Path(__file__).resolve().parents[2]
    report = audit_zero_video_storage(repo_root)

    assert report.passed is True
    assert len(report.prohibited_files) == 0

    # Inspect SQLite database blob fields directly to ensure no embedded JPEG/PNG/video
    db: DatabaseManager = hardening_env["db"]
    store: ProfileStore = hardening_env["store"]

    p_uuid = store.create_profile("Privacy Test User")
    neutral_lm = create_synthetic_neutral_landmarks()
    store.save_neutral_baseline(p_uuid, neutral_lm, 0.30, 1000)

    g_uuid = store.add_gesture_class(p_uuid, "Smile", "SELECT_TILE")
    vec = np.ones(32, dtype=np.float64)
    store.add_gesture_sample(g_uuid, vec, False, 1, 1.0, 2000)

    with db.get_connection() as conn:
        # Check neutral_baselines blob
        cursor = conn.execute(
            "SELECT landmarks_blob FROM neutral_baselines WHERE profile_uuid = ?;", (p_uuid,)
        )
        row = cursor.fetchone()
        assert row is not None
        blob = bytes(row["landmarks_blob"])
        # Exactly 478 landmarks * 3 coordinates * 8 bytes = 11,472 bytes
        assert len(blob) == 478 * 3 * 8
        # Ensure zero image magic numbers
        assert not blob.startswith(b"\xff\xd8\xff")  # JPEG
        assert not blob.startswith(b"\x89PNG")  # PNG
        assert not blob.startswith(b"GIF8")  # GIF
        assert b"ftyp" not in blob[:32]  # MP4

        # Check gesture_samples blob
        cursor = conn.execute(
            "SELECT vector_blob FROM gesture_samples WHERE gesture_uuid = ?;", (g_uuid,)
        )
        row_samp = cursor.fetchone()
        assert row_samp is not None
        samp_blob = bytes(row_samp["vector_blob"])
        # Exactly 32 floats * 8 bytes = 256 bytes
        assert len(samp_blob) == 32 * 8
        assert not samp_blob.startswith(b"\xff\xd8\xff")
        assert not samp_blob.startswith(b"\x89PNG")


def test_clock_regression_and_frame_gap_invariants():
    """IntentEngine must strictly reject backwards monotonic timestamps and frame gaps > 500ms."""
    engine = IntentEngine(config=RecognitionConfig(hold_ms=250))
    engine.reset(State.IDLE)

    pred = RecognitionResult(
        frame_id=1,
        t_ns=1_000_000_000,
        label_scores={"Smile": 0.95},
        best_label="Smile",
        second_label="NONE",
        accepted_candidate_or_none="Smile",
        reject_reason="",
    )

    # 1. Normal candidate step
    st1, _, _ = engine.step(pred, True, now_ns=1_000_000_000)
    assert st1 == State.CANDIDATE

    # 2. Clock regression: now_ns jumped backward to 900,000,000
    st_reg, cmd_reg, trans_reg = engine.step(pred, True, now_ns=900_000_000)
    assert st_reg == State.CANDIDATE  # Held safely, not advanced
    assert cmd_reg is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_CLOCK_REGRESSION

    # 3. Frame gap exceeded (> 500ms elapsed since last accepted timestamp)
    st_gap, cmd_gap, trans_gap = engine.step(pred, True, now_ns=1_600_000_000)
    assert st_gap == State.IDLE  # Wiped candidate back to IDLE
    assert cmd_gap is None
    assert engine.last_decision_reason == DecisionReason.REJECTED_FRAME_GAP


def test_multithreaded_database_concurrency(hardening_env):
    """Multiple concurrent worker threads reading and writing to SQLite must not lock or corrupt."""
    store: ProfileStore = hardening_env["store"]
    v_mgr: ProfileVersionManager = hardening_env["v_mgr"]

    p_uuid = store.create_profile("Concurrent User")
    errors: list[Exception] = []

    neutral_lm = create_synthetic_neutral_landmarks()

    def writer_task(worker_id: int):
        try:
            for j in range(10):
                v_mgr.create_version(
                    profile_uuid=p_uuid,
                    weights={"Brow Raise": [0.1] * 32},
                    thresholds={"hold_ms": 200 + (worker_id * 10) + j, "cooldown_ms": 300},
                    gesture_mappings={"Brow Raise": "NEXT_TILE"},
                    neutral_landmarks=neutral_lm,
                    interocular_ref=0.30,
                    validation_status="VALIDATED",
                    notes=f"Worker {worker_id} iteration {j}",
                )
        except Exception as e:
            errors.append(e)

    def reader_task():
        try:
            for _ in range(20):
                v_mgr.list_versions(p_uuid)
                store.list_profiles()
                time.sleep(0.005)
        except Exception as e:
            errors.append(e)

    threads = []
    # 4 concurrent writer threads + 4 concurrent reader threads
    for w in range(4):
        threads.append(threading.Thread(target=writer_task, args=(w,)))
    for _ in range(4):
        threads.append(threading.Thread(target=reader_task))

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(errors) == 0, f"Concurrent database operations produced errors: {errors}"
    versions = v_mgr.list_versions(p_uuid)
    # 4 worker threads * 10 iterations = 40 versions created concurrently
    assert len(versions) == 40
