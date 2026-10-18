"""Evaluation, fair A/B/C replay harness, and metrics engine."""

from morph.evaluation.independence import (
    DatasetIndependenceAuditor,
    IndependenceAuditResult,
)
from morph.evaluation.matching import match_events_one_to_one
from morph.evaluation.metrics import calculate_benchmark_metrics
from morph.evaluation.replay import ReplayEngine
from morph.evaluation.session import EvaluationSession
from morph.evaluation.validator import EvaluationSessionValidator, ValidationResult

__all__ = [
    "DatasetIndependenceAuditor",
    "EvaluationSession",
    "EvaluationSessionValidator",
    "IndependenceAuditResult",
    "ReplayEngine",
    "ValidationResult",
    "calculate_benchmark_metrics",
    "match_events_one_to_one",
]
