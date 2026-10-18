"""Expanded 20-Scenario Synthetic Benchmark Challenge Suite for MORPH 2.0 (Milestone M6.2).

Re-exported from morph.evaluation.fixtures for backward compatibility with test suite.
All landmark and feature streams are explicitly labeled SYNTHETIC_FIXTURE.
Not human clinical or biometric data.
"""

from __future__ import annotations

from morph.evaluation.fixtures import (
    BenchmarkScenarioSuite,
    verify_zero_leakage,
)

__all__ = [
    "BenchmarkScenarioSuite",
    "verify_zero_leakage",
]
