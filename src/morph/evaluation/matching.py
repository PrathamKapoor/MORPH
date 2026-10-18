"""Greedy one-to-one bipartite temporal event matching for evaluation."""

from __future__ import annotations

from typing import NamedTuple

from morph.common.types import GroundTruthEvent


class MatchedPair(NamedTuple):
    ground_truth: GroundTruthEvent
    action_name: str
    dispatched_at_ns: int
    latency_offset_ms: float  # (dispatched_at_ns - ground_truth.end_ns) in ms


def match_events_one_to_one(
    ground_truths: list[GroundTruthEvent],
    dispatches: list[tuple[str, int]],  # (action_name, dispatched_at_ns)
    early_tolerance_ms: float = 100.0,
    late_tolerance_ms: float = 600.0,
    label_mapping: dict[str, str] | None = None,
) -> tuple[list[MatchedPair], list[tuple[str, int]], list[GroundTruthEvent]]:
    """Match dispatched actions to annotated ground truth events using greedy one-to-one temporal matching.

    Guarantees:
    - One dispatched action matches at most one ground truth event.
    - One ground truth event is matched by at most one dispatched action.
    - Preserves negative latency offsets without clamping to zero.
    """
    mapping = label_mapping or {
        "Brow Raise": "NEXT_TILE",
        "Smile / Lip Corner Pull": "SELECT_TILE",
        "Chin Raise / Mouth Open": "PREVIOUS_TILE",
    }

    # Available ground truth pool
    available_gts = list(ground_truths)
    matched_pairs: list[MatchedPair] = []
    unmatched_dispatches: list[tuple[str, int]] = []

    early_tol_ns = int(early_tolerance_ms * 1_000_000)
    late_tol_ns = int(late_tolerance_ms * 1_000_000)

    # Sort dispatches chronologically
    sorted_dispatches = sorted(dispatches, key=lambda d: d[1])

    for action_name, disp_t_ns in sorted_dispatches:
        # Candidate matches in available ground truth
        candidates = []
        for gt in available_gts:
            expected_action = mapping.get(gt.label, gt.label)
            if expected_action == action_name:
                # Check tolerance window around ground truth interval
                if (gt.start_ns - early_tol_ns) <= disp_t_ns <= (gt.end_ns + late_tol_ns):
                    temporal_dist = abs(disp_t_ns - gt.end_ns)
                    candidates.append((temporal_dist, gt))

        if candidates:
            # Pick best match by minimum temporal distance
            candidates.sort(key=lambda c: c[0])
            best_gt = candidates[0][1]
            available_gts.remove(best_gt)

            offset_ms = (disp_t_ns - best_gt.end_ns) / 1_000_000.0
            matched_pairs.append(
                MatchedPair(
                    ground_truth=best_gt,
                    action_name=action_name,
                    dispatched_at_ns=disp_t_ns,
                    latency_offset_ms=offset_ms,
                )
            )
        else:
            unmatched_dispatches.append((action_name, disp_t_ns))

    unmatched_gts = available_gts
    return matched_pairs, unmatched_dispatches, unmatched_gts
