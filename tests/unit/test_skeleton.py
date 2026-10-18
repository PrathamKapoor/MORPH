"""Unit tests for M0 skeleton, normative files, Git configuration, and models."""

import hashlib
import json
import subprocess
from pathlib import Path


def test_normative_files_exist():
    root = Path(__file__).resolve().parents[2]
    normative_files = [
        "README.md",
        "pyproject.toml",
        "CHANGELOG.md",
        "constraints.txt",
        ".gitignore",
        ".gitattributes",
        ".editorconfig",
    ]
    for filename in normative_files:
        path = root / filename
        assert path.exists(), f"Required file missing: {filename}"
        assert path.stat().st_size > 50, f"File appears too small/empty: {filename}"


def test_docs_exist():
    root = Path(__file__).resolve().parents[2]
    doc_files = [
        "docs/architecture/overview.md",
        "docs/architecture/flow.md",
        "docs/architecture/decisions.md",
        "docs/architecture/requirements.md",
        "docs/research/methodology.md",
        "docs/research/experiments.md",
        "docs/research/benchmarks.md",
        "docs/research/limitations.md",
        "docs/accessibility/audit.md",
        "docs/accessibility/guide.md",
        "docs/security/privacy.md",
        "docs/security/threat_model.md",
        "docs/development/testing.md",
        "docs/development/building.md",
        "docs/development/troubleshooting.md",
    ]
    for filename in doc_files:
        path = root / filename
        assert path.exists(), f"Required doc missing: {filename}"
        assert path.stat().st_size > 100, f"Doc appears too small/empty: {filename}"


def test_model_asset_and_manifest():
    root = Path(__file__).resolve().parents[2]
    model_path = root / "models" / "face_landmarker.task"
    manifest_path = root / "models" / "face_landmarker.task.manifest.json"

    assert model_path.exists(), "Model asset face_landmarker.task missing!"
    assert manifest_path.exists(), "Model manifest missing!"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    with open(model_path, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    assert sha256 == manifest["sha256"], f"Checksum mismatch: {sha256} vs {manifest['sha256']}"
    assert manifest["task_type"] == "FaceLandmarker"


def test_git_local_config():
    root = Path(__file__).resolve().parents[2]
    name = subprocess.check_output(
        ["git", "config", "--local", "user.name"], cwd=root, text=True
    ).strip()
    email = subprocess.check_output(
        ["git", "config", "--local", "user.email"], cwd=root, text=True
    ).strip()
    use_config = subprocess.check_output(
        ["git", "config", "--local", "user.useConfigOnly"], cwd=root, text=True
    ).strip()

    assert name == "PrathamKapoor", f"Expected PrathamKapoor, got {name}"
    assert email == "prathamkapoor027@gmail.com", (
        f"Expected prathamkapoor027@gmail.com, got {email}"
    )
    assert use_config == "true", f"Expected true, got {use_config}"
