"""SQLite database schema and versioned migrations for MORPH 2.0."""

SCHEMA_VERSION = 1

MIGRATION_V1 = """
-- Version 1: Initial schema for profiles, neutral calibrations, gestures, and evaluation

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    profile_uuid TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS neutral_baselines (
    neutral_uuid TEXT PRIMARY KEY,
    profile_uuid TEXT NOT NULL,
    landmarks_blob BLOB NOT NULL,
    interocular_ref REAL NOT NULL,
    created_at_ns INTEGER NOT NULL,
    FOREIGN KEY(profile_uuid) REFERENCES profiles(profile_uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gesture_classes (
    gesture_uuid TEXT PRIMARY KEY,
    profile_uuid TEXT NOT NULL,
    name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY(profile_uuid) REFERENCES profiles(profile_uuid) ON DELETE CASCADE,
    UNIQUE(profile_uuid, name)
);

CREATE TABLE IF NOT EXISTS gesture_samples (
    sample_uuid TEXT PRIMARY KEY,
    gesture_uuid TEXT NOT NULL,
    vector_blob BLOB NOT NULL,
    is_held_out INTEGER NOT NULL DEFAULT 0,
    sample_ordinal INTEGER NOT NULL,
    quality_score REAL NOT NULL,
    created_at_ns INTEGER NOT NULL,
    FOREIGN KEY(gesture_uuid) REFERENCES gesture_classes(gesture_uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trained_models (
    model_uuid TEXT PRIMARY KEY,
    profile_uuid TEXT NOT NULL,
    model_type TEXT NOT NULL,
    weights_json TEXT NOT NULL,
    threshold_config_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY(profile_uuid) REFERENCES profiles(profile_uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evaluation_sessions (
    session_uuid TEXT PRIMARY KEY,
    profile_uuid TEXT NOT NULL,
    consented INTEGER NOT NULL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY(profile_uuid) REFERENCES profiles(profile_uuid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evaluation_events (
    event_uuid TEXT PRIMARY KEY,
    session_uuid TEXT NOT NULL,
    label TEXT NOT NULL,
    start_ns INTEGER NOT NULL,
    end_ns INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    FOREIGN KEY(session_uuid) REFERENCES evaluation_sessions(session_uuid) ON DELETE CASCADE
);
"""

SCHEMA_VERSION = 2

MIGRATION_V2 = """
-- Version 2: Profile versioning and rollback history (PRD D07 / M5.2)

CREATE TABLE IF NOT EXISTS profile_versions (
    version_uuid TEXT PRIMARY KEY,
    profile_uuid TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    feature_schema_version TEXT NOT NULL,
    weights_json TEXT NOT NULL,
    threshold_config_json TEXT NOT NULL,
    gesture_mappings_json TEXT NOT NULL,
    neutral_landmarks_blob BLOB NOT NULL,
    interocular_ref REAL NOT NULL,
    validation_status TEXT NOT NULL, -- 'VALIDATED', 'CANDIDATE', 'DEPRECATED'
    created_at_utc TEXT NOT NULL,
    notes TEXT DEFAULT '',
    FOREIGN KEY(profile_uuid) REFERENCES profiles(profile_uuid) ON DELETE CASCADE,
    UNIQUE(profile_uuid, version_number)
);
"""
