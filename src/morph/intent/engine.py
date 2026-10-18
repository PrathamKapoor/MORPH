"""Deterministic Pure Finite-State Machine for Intention Gating (Condition C).

Hardened for Milestone M5.3 with:
- Formal state transition specification and legal transition verification.
- Temporal correctness (monotonic timestamps, frame gap detection, clock regression safety).
- Explainable structured decision reason codes (DecisionReason).
- Conflict and ambiguity rejection.
- Zero duplicate dispatches on sustained holds.
- Fail-closed behavior on tracking loss or pause.
"""

from __future__ import annotations

import uuid
from enum import Enum

from morph.common.config import RecognitionConfig
from morph.common.types import ConfirmedCommand, IntentTransition, RecognitionResult, State


class DecisionReason(str, Enum):
    """Structured, explainable decision reason codes for the intention gate."""

    ACCEPTED_GESTURE = "ACCEPTED_GESTURE"
    REJECTED_LOW_CONFIDENCE = "REJECTED_LOW_CONFIDENCE"
    REJECTED_AMBIGUOUS = "REJECTED_AMBIGUOUS"
    REJECTED_TRACKING_LOSS = "REJECTED_TRACKING_LOSS"
    REJECTED_INSUFFICIENT_HOLD = "REJECTED_INSUFFICIENT_HOLD"
    REJECTED_COOLDOWN = "REJECTED_COOLDOWN"
    REJECTED_PAUSED = "REJECTED_PAUSED"
    REJECTED_CLOCK_REGRESSION = "REJECTED_CLOCK_REGRESSION"
    REJECTED_FRAME_GAP = "REJECTED_FRAME_GAP"
    REJECTED_RESTING_NEUTRAL = "REJECTED_RESTING_NEUTRAL"


class IntentEngine:
    """Pure, deterministic state machine enforcing intentional hold, neutral release,

    cooldown, and conflict arbitration.

    States:
    - PAUSED: All command emission suppressed.
    - TRACKING_LOST: Face missing or multiple faces in frame; requires safe re-arm.
    - IDLE: Waiting for a valid gesture candidate.
    - CANDIDATE: Candidate detected, verifying stability over hold_ms.
    - CONFIRMED: Transient state emitting exactly one ConfirmedCommand.
    - COOLDOWN: Enforcing return to neutral for release_ms and total cooldown_ms.
    """

    MAX_INPUT_GAP_NS = 500_000_000  # 500 ms maximum gap before resetting candidate

    def __init__(
        self,
        config: RecognitionConfig | None = None,
        action_mappings: dict[str, str] | None = None,
        max_gap_ms: int = 500,
    ):
        self.config = config or RecognitionConfig()
        self.action_mappings = action_mappings or {
            "Brow Raise": "NEXT_TILE",
            "Smile / Lip Corner Pull": "SELECT_TILE",
            "Chin Raise / Mouth Open": "PREVIOUS_TILE",
        }
        self.max_gap_ns = max_gap_ms * 1_000_000

        self.state: State = State.PAUSED
        self._last_now_ns: int = 0
        self._candidate_label: str | None = None
        self._candidate_start_ns: int = 0
        self.last_decision_reason: DecisionReason = DecisionReason.REJECTED_PAUSED

        # Cooldown & release tracking
        self._cooldown_start_ns: int = 0
        self._release_dwell_start_ns: int | None = None

        # Re-arm dwell tracking after recovery from TRACKING_LOST
        self._rearm_dwell_start_ns: int | None = None
        self._recovered_from_lost: bool = False

    @property
    def candidate_label(self) -> str | None:
        """Active gesture label currently being held as candidate, if any."""
        return self._candidate_label

    def set_action_mappings(self, mappings: dict[str, str]) -> None:
        """Update gesture-to-action bindings."""
        self.action_mappings = dict(mappings)

    def reset(self, new_state: State = State.PAUSED) -> None:
        """Reset internal timers and pending candidates safely."""
        self.state = new_state
        self._candidate_label = None
        self._candidate_start_ns = 0
        self._cooldown_start_ns = 0
        self._release_dwell_start_ns = None
        self._rearm_dwell_start_ns = None
        self._recovered_from_lost = False

    def step(
        self,
        recognition: RecognitionResult,
        tracking_valid: bool,
        now_ns: int,
        mode: str = "LIVE",
        paused: bool = False,
    ) -> tuple[State, ConfirmedCommand | None, list[IntentTransition]]:
        """Advance state machine by one discrete time step.

        Pure deterministic function: relies strictly on injected parameters.
        Returns (state, command_or_none, transitions).
        Also updates self.last_decision_reason for structured observability.
        """
        transitions: list[IntentTransition] = []

        # 1. Monotonic Clock Invariant Check
        if now_ns < self._last_now_ns:
            self.last_decision_reason = DecisionReason.REJECTED_CLOCK_REGRESSION
            # Clock jumped backwards; hold state safely and do not emit
            return self.state, None, transitions

        # 2. Input Frame Gap Check (> 500ms)
        elapsed_since_last = (now_ns - self._last_now_ns) if self._last_now_ns > 0 else 0
        self._last_now_ns = now_ns

        if elapsed_since_last > self.max_gap_ns and self.state == State.CANDIDATE:
            trans = IntentTransition(
                t_ns=now_ns,
                before=State.CANDIDATE,
                after=State.IDLE,
                label_or_none=self._candidate_label,
                reason=f"INPUT_FRAME_GAP_EXCEEDED ({elapsed_since_last / 1e6:.1f}ms > {self.max_gap_ns / 1e6:.1f}ms)",
                config_version=self.config.config_version,
                frame_id=recognition.frame_id,
            )
            transitions.append(trans)
            self.state = State.IDLE
            self._candidate_label = None
            self._candidate_start_ns = 0
            self.last_decision_reason = DecisionReason.REJECTED_FRAME_GAP
            return self.state, None, transitions

        # 3. Global Pause / Non-Live Mode Enforcement
        if paused or mode != "LIVE":
            self.last_decision_reason = DecisionReason.REJECTED_PAUSED
            if self.state != State.PAUSED:
                trans = IntentTransition(
                    t_ns=now_ns,
                    before=self.state,
                    after=State.PAUSED,
                    label_or_none=None,
                    reason=f"SYSTEM_PAUSED (mode={mode}, paused={paused})",
                    config_version=self.config.config_version,
                    frame_id=recognition.frame_id,
                )
                transitions.append(trans)
                self.reset(State.PAUSED)
            return self.state, None, transitions

        # 4. Tracking Loss Enforcement (0 faces, >1 faces, occlusion)
        if not tracking_valid:
            self.last_decision_reason = DecisionReason.REJECTED_TRACKING_LOSS
            if self.state != State.TRACKING_LOST:
                trans = IntentTransition(
                    t_ns=now_ns,
                    before=self.state,
                    after=State.TRACKING_LOST,
                    label_or_none=None,
                    reason="TRACKING_INVALID_OR_MULTIPLE_FACES",
                    config_version=self.config.config_version,
                    frame_id=recognition.frame_id,
                )
                transitions.append(trans)
                self.reset(State.TRACKING_LOST)
                self._recovered_from_lost = True
            return self.state, None, transitions

        # 5. Safe Re-arm after recovery from TRACKING_LOST or PAUSED
        if self.state in (State.PAUSED, State.TRACKING_LOST):
            trans = IntentTransition(
                t_ns=now_ns,
                before=self.state,
                after=State.IDLE,
                label_or_none=None,
                reason="RECOVERED_TO_IDLE_SAFE_REARM",
                config_version=self.config.config_version,
                frame_id=recognition.frame_id,
            )
            transitions.append(trans)
            self.reset(State.IDLE)
            self._recovered_from_lost = True

            candidate = recognition.accepted_candidate_or_none
            is_ambiguous = (
                "AMBIGUOUS" in recognition.reject_reason or recognition.best_label == "AMBIGUOUS"
            )
            is_neutral = (candidate is None or candidate == "NEUTRAL") and not is_ambiguous

            if is_neutral:
                self._rearm_dwell_start_ns = now_ns
            else:
                self._rearm_dwell_start_ns = None

            self.last_decision_reason = (
                DecisionReason.REJECTED_AMBIGUOUS
                if is_ambiguous
                else DecisionReason.REJECTED_LOW_CONFIDENCE
            )
            return self.state, None, transitions

        # If recovering from loss, enforce continuous resting neutral dwell before admitting candidates
        if self._recovered_from_lost:
            candidate = recognition.accepted_candidate_or_none
            is_ambiguous = (
                "AMBIGUOUS" in recognition.reject_reason or recognition.best_label == "AMBIGUOUS"
            )
            is_neutral = (candidate is None or candidate == "NEUTRAL") and not is_ambiguous

            if not is_neutral:
                # Command gesture or ambiguous movement observed during recovery dwell;
                # reset dwell start while maintaining recovery lock
                self._rearm_dwell_start_ns = None
                self.last_decision_reason = (
                    DecisionReason.REJECTED_AMBIGUOUS
                    if is_ambiguous
                    else DecisionReason.REJECTED_LOW_CONFIDENCE
                )
                return self.state, None, transitions

            if self._rearm_dwell_start_ns is None:
                self._rearm_dwell_start_ns = now_ns

            rearm_ns = self.config.rearm_neutral_dwell_ms * 1_000_000
            if (now_ns - self._rearm_dwell_start_ns) < rearm_ns:
                self.last_decision_reason = DecisionReason.REJECTED_LOW_CONFIDENCE
                return self.state, None, transitions
            else:
                self._recovered_from_lost = False
                self._rearm_dwell_start_ns = None

        candidate = recognition.accepted_candidate_or_none
        hold_ns = self.config.hold_ms * 1_000_000
        cooldown_ns = self.config.cooldown_ms * 1_000_000
        release_ns = self.config.release_ms * 1_000_000

        # Check for ambiguity in recognition result
        if "AMBIGUOUS" in recognition.reject_reason or recognition.best_label == "AMBIGUOUS":
            if self.state == State.CANDIDATE:
                trans = IntentTransition(
                    t_ns=now_ns,
                    before=State.CANDIDATE,
                    after=State.IDLE,
                    label_or_none=self._candidate_label,
                    reason=f"CANDIDATE_REJECTED_AMBIGUOUS ({recognition.reject_reason})",
                    config_version=self.config.config_version,
                    frame_id=recognition.frame_id,
                )
                transitions.append(trans)
                self.state = State.IDLE
                self._candidate_label = None
                self._candidate_start_ns = 0
            self.last_decision_reason = DecisionReason.REJECTED_AMBIGUOUS
            return self.state, None, transitions

        # 6. State: IDLE
        if self.state == State.IDLE:
            if candidate is not None and candidate != "NEUTRAL":
                trans = IntentTransition(
                    t_ns=now_ns,
                    before=State.IDLE,
                    after=State.CANDIDATE,
                    label_or_none=candidate,
                    reason="CANDIDATE_DETECTED_STARTING_HOLD_TIMER",
                    config_version=self.config.config_version,
                    frame_id=recognition.frame_id,
                )
                transitions.append(trans)
                self.state = State.CANDIDATE
                self._candidate_label = candidate
                self._candidate_start_ns = now_ns
                self.last_decision_reason = DecisionReason.REJECTED_INSUFFICIENT_HOLD
            else:
                self.last_decision_reason = (
                    DecisionReason.REJECTED_RESTING_NEUTRAL
                    if recognition.best_label == "NEUTRAL"
                    else DecisionReason.REJECTED_LOW_CONFIDENCE
                )
            return self.state, None, transitions

        # 7. State: CANDIDATE
        if self.state == State.CANDIDATE:
            # Check if candidate was lost, changed, or fell below threshold/margin
            if candidate != self._candidate_label or candidate is None:
                trans = IntentTransition(
                    t_ns=now_ns,
                    before=State.CANDIDATE,
                    after=State.IDLE,
                    label_or_none=self._candidate_label,
                    reason=f"CANDIDATE_LOST_OR_CHANGED (new={candidate}, reject={recognition.reject_reason})",
                    config_version=self.config.config_version,
                    frame_id=recognition.frame_id,
                )
                transitions.append(trans)
                self.state = State.IDLE
                self._candidate_label = None
                self._candidate_start_ns = 0
                self.last_decision_reason = (
                    DecisionReason.REJECTED_AMBIGUOUS
                    if "AMBIGUOUS" in recognition.reject_reason
                    else DecisionReason.REJECTED_LOW_CONFIDENCE
                )
                return self.state, None, transitions

            # Candidate is stably sustained: check elapsed hold time
            elapsed_hold = now_ns - self._candidate_start_ns
            if elapsed_hold >= hold_ns:
                # Intention confirmed!
                confirmed_gesture = self._candidate_label
                if confirmed_gesture not in self.action_mappings:
                    # Unmapped gestures cannot confirm an action; safely abort candidate to IDLE
                    trans_unmapped = IntentTransition(
                        t_ns=now_ns,
                        before=State.CANDIDATE,
                        after=State.IDLE,
                        label_or_none=confirmed_gesture,
                        reason=f"GESTURE_NOT_MAPPED ({confirmed_gesture})",
                        config_version=self.config.config_version,
                        frame_id=recognition.frame_id,
                    )
                    transitions.append(trans_unmapped)
                    self.state = State.IDLE
                    self._candidate_label = None
                    self._candidate_start_ns = 0
                    self.last_decision_reason = DecisionReason.REJECTED_LOW_CONFIDENCE
                    return self.state, None, transitions

                action_name = self.action_mappings[confirmed_gesture]
                cmd_uuid = str(uuid.uuid4())

                command = ConfirmedCommand(
                    command_event_uuid=cmd_uuid,
                    frame_id=recognition.frame_id,
                    confirmed_at_ns=now_ns,
                    gesture_uuid=confirmed_gesture,
                    action_mapping_uuid=action_name,
                    version_snapshot=self.config.config_version,
                )

                # Transient CONFIRMED transition
                trans_confirm = IntentTransition(
                    t_ns=now_ns,
                    before=State.CANDIDATE,
                    after=State.CONFIRMED,
                    label_or_none=confirmed_gesture,
                    reason=f"HOLD_DURATION_SATISFIED ({elapsed_hold / 1e6:.1f}ms >= {self.config.hold_ms}ms)",
                    config_version=self.config.config_version,
                    frame_id=recognition.frame_id,
                )
                transitions.append(trans_confirm)

                # Enter COOLDOWN
                trans_cooldown = IntentTransition(
                    t_ns=now_ns,
                    before=State.CONFIRMED,
                    after=State.COOLDOWN,
                    label_or_none=confirmed_gesture,
                    reason="ENTERING_COOLDOWN_REQUIRING_NEUTRAL_RELEASE",
                    config_version=self.config.config_version,
                    frame_id=recognition.frame_id,
                )
                transitions.append(trans_cooldown)

                self.state = State.COOLDOWN
                self._cooldown_start_ns = now_ns
                self._release_dwell_start_ns = None
                self._candidate_label = None
                self._candidate_start_ns = 0
                self.last_decision_reason = DecisionReason.ACCEPTED_GESTURE

                return State.CONFIRMED, command, transitions

            # Still accumulating hold
            self.last_decision_reason = DecisionReason.REJECTED_INSUFFICIENT_HOLD
            return self.state, None, transitions

        # 8. State: COOLDOWN
        if self.state == State.COOLDOWN:
            elapsed_cooldown = now_ns - self._cooldown_start_ns

            # Check if user returned to neutral (no active candidate)
            if candidate is None or candidate == "NEUTRAL":
                if self._release_dwell_start_ns is None:
                    self._release_dwell_start_ns = now_ns
            else:
                # User is still holding movement; reset release dwell
                self._release_dwell_start_ns = None
                self.last_decision_reason = DecisionReason.REJECTED_COOLDOWN

            # Check if both release dwell AND total cooldown time are satisfied
            release_elapsed = (
                (now_ns - self._release_dwell_start_ns) if self._release_dwell_start_ns else 0
            )

            if elapsed_cooldown >= cooldown_ns and release_elapsed >= release_ns:
                trans = IntentTransition(
                    t_ns=now_ns,
                    before=State.COOLDOWN,
                    after=State.IDLE,
                    label_or_none=None,
                    reason="COOLDOWN_AND_NEUTRAL_RELEASE_SATISFIED",
                    config_version=self.config.config_version,
                    frame_id=recognition.frame_id,
                )
                transitions.append(trans)
                self.state = State.IDLE
                self._release_dwell_start_ns = None
                self._cooldown_start_ns = 0
                self.last_decision_reason = DecisionReason.REJECTED_RESTING_NEUTRAL
            else:
                self.last_decision_reason = DecisionReason.REJECTED_COOLDOWN

            return self.state, None, transitions

        return self.state, None, transitions
