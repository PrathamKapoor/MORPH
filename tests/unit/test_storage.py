"""Unit tests for SQLite storage, migrations, and profile management."""

import tempfile
from pathlib import Path

import numpy as np

from morph.storage.db import DatabaseManager
from morph.storage.profiles import ProfileStore
from morph.storage.schema import SCHEMA_VERSION


def test_database_initialization_and_migration():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_morph.db"
        db = DatabaseManager(db_path)
        assert db_path.exists()

        # Check schema_version table
        ver = db.fetch_one("SELECT MAX(version) as ver FROM schema_version;")
        assert ver is not None
        assert ver["ver"] == SCHEMA_VERSION
        assert ver["ver"] >= 2


def test_profile_creation_and_switching():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = DatabaseManager(Path(tmpdir) / "test.db")
        store = ProfileStore(db)

        # Auto-create default
        p1 = store.get_or_create_default_profile()
        assert p1 is not None

        # Create second profile
        p2 = store.create_profile("Alice ALS Profile", "Caregiver assisted")
        assert p2 != p1

        # Switch active profile
        store.set_active_profile(p2)
        active_p = store.get_or_create_default_profile()
        assert active_p == p2

        profiles = store.list_profiles()
        assert len(profiles) == 2


def test_neutral_baseline_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = DatabaseManager(Path(tmpdir) / "test.db")
        store = ProfileStore(db)
        pid = store.get_or_create_default_profile()

        # Synthetic landmarks (478, 3)
        landmarks = np.ones((478, 3), dtype=np.float64) * 0.5
        landmarks[33] = [0.3, 0.4, 0.0]
        landmarks[263] = [0.6, 0.4, 0.0]
        eye_dist = 0.30

        store.save_neutral_baseline(pid, landmarks, eye_dist, 10_000)

        retrieved = store.get_neutral_baseline(pid)
        assert retrieved is not None
        ret_lm, ret_dist = retrieved
        assert ret_lm.shape == (478, 3)
        assert np.allclose(ret_lm, landmarks)
        assert abs(ret_dist - eye_dist) < 1e-6


def test_gesture_samples_and_held_out_partition():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = DatabaseManager(Path(tmpdir) / "test.db")
        store = ProfileStore(db)
        pid = store.get_or_create_default_profile()

        g_uuid = store.add_gesture_class(pid, "Brow Raise", "NEXT_TILE")

        # Add 5 training samples and 2 held-out samples
        vec = np.ones(32, dtype=np.float64) * 0.2
        for i in range(5):
            store.add_gesture_sample(
                g_uuid, vec, is_held_out=False, ordinal=i + 1, quality=0.9, created_at_ns=1000 + i
            )
        for i in range(2):
            store.add_gesture_sample(
                g_uuid, vec, is_held_out=True, ordinal=6 + i, quality=0.95, created_at_ns=2000 + i
            )

        train_samples = store.get_gesture_samples(g_uuid, held_out=False)
        assert len(train_samples) == 5

        held_out_samples = store.get_gesture_samples(g_uuid, held_out=True)
        assert len(held_out_samples) == 2

        all_samples = store.get_gesture_samples(g_uuid, held_out=None)
        assert len(all_samples) == 7

        # Redo / delete samples
        store.delete_gesture_samples(g_uuid)
        assert len(store.get_gesture_samples(g_uuid)) == 0


def test_model_snapshot_save_and_reload():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = DatabaseManager(Path(tmpdir) / "test.db")
        store = ProfileStore(db)
        pid = store.get_or_create_default_profile()

        weights = {"Brow Raise": [0.1] * 32, "Smile": [0.2] * 32}
        thresholds = {"min_similarity": 0.70, "min_margin": 0.15}

        store.save_model_snapshot(pid, "prototype-v1", weights, thresholds)

        snapshot = store.get_latest_model_snapshot(pid)
        assert snapshot is not None
        assert snapshot["model_type"] == "prototype-v1"
        assert "Brow Raise" in snapshot["weights"]
        assert snapshot["thresholds"]["min_similarity"] == 0.70
