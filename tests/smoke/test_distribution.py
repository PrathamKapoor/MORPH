"""Distribution smoke tests verifying PyInstaller build integrity and real directory relocation."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_distribution_directory_structure():
    """Verify packaged directory structure contains executable and bundled assets."""
    dist_dir = Path("dist/morph")
    if not dist_dir.exists():
        pytest.skip("Packaged distribution dist/morph does not exist")

    exe_path = dist_dir / "morph.exe"
    assert exe_path.exists(), f"morph.exe not found at {exe_path}"
    assert exe_path.is_file(), f"{exe_path} is not a file"

    # Verify bundled model asset exists either in _internal/models or models
    internal_model = dist_dir / "_internal" / "models" / "face_landmarker.task"
    root_model = dist_dir / "models" / "face_landmarker.task"
    assert internal_model.exists() or root_model.exists(), (
        f"Bundled face_landmarker.task not found in {internal_model} or {root_model}"
    )


def test_distribution_zero_developer_residue():
    """Verify distribution contains zero .git, source control, or raw video capture residue."""
    dist_dir = Path("dist/morph")
    if not dist_dir.exists():
        pytest.skip("Packaged distribution dist/morph does not exist")

    prohibited_patterns = [".git", ".pytest_cache", ".ruff_cache", "__pycache__"]
    prohibited_extensions = [".mp4", ".avi", ".mov", ".mkv", ".webm"]

    for root, dirs, files in os.walk(dist_dir):
        for d in dirs:
            for p in prohibited_patterns:
                assert p not in d.lower(), (
                    f"Prohibited directory '{d}' found in distribution: {root}"
                )
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            assert ext not in prohibited_extensions, (
                f"Prohibited media capture '{f}' found in distribution: {root}"
            )


def test_distribution_headless_and_version_execution():
    """Verify packaged binary executes with --version and --headless-check without crashing."""
    exe_path = Path("dist/morph/morph.exe")
    if not exe_path.exists():
        pytest.skip("Packaged binary dist/morph/morph.exe does not exist")

    # 1. Test --version
    res_ver = subprocess.run(
        [str(exe_path), "--version"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert res_ver.returncode == 0, f"Binary --version exited with code {res_ver.returncode}"

    # 2. Test --headless-check
    res_headless = subprocess.run(
        [str(exe_path), "--headless-check"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res_headless.returncode == 0, (
        f"Binary --headless-check exited with code {res_headless.returncode}"
    )


def test_distribution_relocation_execution(tmp_path):
    """Verify packaged binary executes in an isolated directory without repository assets."""
    dist_dir = Path("dist/morph")
    if not dist_dir.exists():
        pytest.skip("Packaged distribution dist/morph does not exist")

    # Physically copy dist/morph to an isolated directory outside repo tree
    relocated_dir = tmp_path / "morph_relocated"
    shutil.copytree(dist_dir, relocated_dir)
    exe_path = relocated_dir / "morph.exe"
    assert exe_path.exists(), f"Relocated morph.exe not found at {exe_path}"

    # Clear PYTHONPATH from environment to ensure zero reliance on repository source tree
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    res = subprocess.run(
        [str(exe_path), "--headless-check"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert res.returncode == 0, (
        f"Relocated headless check failed with code {res.returncode}.\n"
        f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    )
    combined = res.stdout + res.stderr
    assert "MORPH_HEADLESS_CHECK_PASSED" in combined
