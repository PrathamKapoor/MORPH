"""Screen S5: Reliability & Tracking Health Monitor for MORPH 2.0 (Milestone M6.5).

Provides:
- Real-time pipeline performance telemetry (capture FPS, processed FPS, latency breakdowns, memory)
- Explainable FSM state inspector (active candidate, hold progress bar, structured decision reasons)
- Geometric distance & alignment inspector (cosine similarities, prototype Euclidean distances)
- Finite state transition history log with detailed rejection reasons
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from morph.capture.instrumentation import PerformanceSnapshot
from morph.common.types import IntentTransition, State, TrackingHealth


class MonitorView(QWidget):
    """S5 Reliability Monitor: Real-time telemetry, queue drops, and transition history."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAccessibleName("Reliability Monitor Screen")
        self.setAccessibleDescription(
            "Screen for monitoring camera FPS, processed FPS, dropped frames, tracking validity, "
            "explainable FSM intention states, and geometric classifier distances."
        )

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # 1. Header
        header = QVBoxLayout()
        title = QLabel("Reliability & Health Monitor")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #38BDF8;")
        disclaimer = QLabel(
            "⚠ Note: Landmark tracking availability does NOT equal recognition accuracy. "
            "Accurate recognition depends on resting baseline calibration and gesture stability."
        )
        disclaimer.setStyleSheet("color: #FBBF24; font-size: 13px; font-style: italic;")
        header.addWidget(title)
        header.addWidget(disclaimer)
        layout.addLayout(header)

        # 2. Metrics Telemetry Cards Grid
        grid_frame = QFrame()
        grid = QGridLayout(grid_frame)
        grid.setSpacing(14)

        self.card_proc_fps = self._create_metric_card("Processed FPS", "0.0 FPS")
        self.card_cap_fps = self._create_metric_card("Camera Capture FPS", "0.0 FPS")
        self.card_faces = self._create_metric_card("Tracked Faces", "0 Faces")
        self.card_drops = self._create_metric_card("Queue Drops (Backlog)", "0 frames")
        self.card_stale = self._create_metric_card("Stale Frames (>100ms)", "0 frames")
        self.card_reason = self._create_metric_card("Last Block Reason", "None")
        self.card_lat_e2e = self._create_metric_card("E2E Pipeline Latency", "0.0 ms")
        self.card_lat_stages = self._create_metric_card("Stage Breakdown", "LM: 0.0ms | Rec: 0.0ms")
        self.card_mem = self._create_metric_card("Memory Working Set", "0.0 MB")

        grid.addWidget(self.card_proc_fps, 0, 0)
        grid.addWidget(self.card_cap_fps, 0, 1)
        grid.addWidget(self.card_faces, 0, 2)
        grid.addWidget(self.card_drops, 1, 0)
        grid.addWidget(self.card_stale, 1, 1)
        grid.addWidget(self.card_reason, 1, 2)
        grid.addWidget(self.card_lat_e2e, 2, 0)
        grid.addWidget(self.card_lat_stages, 2, 1)
        grid.addWidget(self.card_mem, 2, 2)

        layout.addWidget(grid_frame)

        # 3. Explainable Live Recognition & Intention Gate Inspector (M6.5)
        inspector_group = QGroupBox("Explainable Intention Gate & Geometric Distance Inspector")
        i_layout = QVBoxLayout(inspector_group)

        # Top row: State badge, candidate, decision reason
        i_top_row = QHBoxLayout()

        state_box = QVBoxLayout()
        state_title = QLabel("Current FSM State:")
        state_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        self.lbl_fsm_state = QLabel("PAUSED")
        self.lbl_fsm_state.setStyleSheet(
            "background-color: #064E3B; color: #ECFDF5; border: 1px solid #059669; "
            "border-radius: 6px; font-size: 15px; font-weight: 700; padding: 4px 12px;"
        )
        self.lbl_fsm_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        state_box.addWidget(state_title)
        state_box.addWidget(self.lbl_fsm_state)
        i_top_row.addLayout(state_box)

        reason_box = QVBoxLayout()
        reason_title = QLabel("Last Decision Reason:")
        reason_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        self.lbl_decision_reason = QLabel("REJECTED_PAUSED")
        self.lbl_decision_reason.setStyleSheet(
            "color: #F87171; font-size: 14px; font-weight: bold;"
        )
        reason_box.addWidget(reason_title)
        reason_box.addWidget(self.lbl_decision_reason)
        i_top_row.addLayout(reason_box, 1)

        candidate_box = QVBoxLayout()
        cand_title = QLabel("Active Candidate:")
        cand_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        self.lbl_candidate = QLabel("None")
        self.lbl_candidate.setStyleSheet("color: #38BDF8; font-size: 14px; font-weight: bold;")
        candidate_box.addWidget(cand_title)
        candidate_box.addWidget(self.lbl_candidate)
        i_top_row.addLayout(candidate_box, 1)

        i_layout.addLayout(i_top_row)

        # Hold progress bar row
        hold_row = QHBoxLayout()
        hold_lbl = QLabel("Hold Duration Confirmation:")
        hold_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        self.progress_hold = QProgressBar()
        self.progress_hold.setRange(0, 100)
        self.progress_hold.setValue(0)
        self.progress_hold.setTextVisible(True)
        self.progress_hold.setFormat("%v% (0 / 250 ms)")
        self.progress_hold.setStyleSheet(
            "QProgressBar { background-color: #0F172A; border: 1px solid #334155; border-radius: 4px; height: 16px; font-size: 11px; text-align: center; color: #FFFFFF; }"
            "QProgressBar::chunk { background-color: #38BDF8; border-radius: 4px; }"
        )
        hold_row.addWidget(hold_lbl)
        hold_row.addWidget(self.progress_hold, 1)
        i_layout.addLayout(hold_row)

        # Geometric Alignment & Distance Table
        dist_disclaimer = QLabel(
            "ℹ Scientific Clarification: Values below represent raw cosine similarities (directional alignment) "
            "and Euclidean feature distances against stored prototype vectors. They are geometric distance metrics, NOT probabilities."
        )
        dist_disclaimer.setStyleSheet(
            "color: #94A3B8; font-size: 11px; font-style: italic; margin-top: 4px;"
        )
        i_layout.addWidget(dist_disclaimer)

        self.table_distances = QTableWidget(0, 5)
        self.table_distances.setHorizontalHeaderLabels(
            ["Gesture Class", "Cosine Similarity", "Distance (L2)", "Threshold", "Runner-Up Margin"]
        )
        self.table_distances.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_distances.setStyleSheet(
            "QTableWidget { background-color: #0F172A; border: 1px solid #334155; gridline-color: #1E293B; font-size: 13px; }"
            "QHeaderView::section { background-color: #1A1F29; color: #94A3B8; font-weight: bold; padding: 4px; }"
        )
        i_layout.addWidget(self.table_distances)

        layout.addWidget(inspector_group)

        # 4. Transition History Log
        log_group = QGroupBox("State Machine & Safety Transition Log")
        log_layout = QVBoxLayout(log_group)

        self.list_transitions = QListWidget()
        self.list_transitions.setAccessibleName("State Machine Transition Log")
        self.list_transitions.setStyleSheet(
            "background-color: #0F172A; color: #CBD5E1; border: 1px solid #334155; border-radius: 6px; font-family: monospace; font-size: 13px;"
        )
        log_layout.addWidget(self.list_transitions)

        btn_clear = QPushButton("Clear Transition Log")
        btn_clear.clicked.connect(self.list_transitions.clear)
        log_layout.addWidget(btn_clear)

        layout.addWidget(log_group)

    def _create_metric_card(self, title: str, initial_value: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            "background-color: #1A1F29; border: 1px solid #2D3748; border-radius: 8px; padding: 14px;"
        )
        vbox = QVBoxLayout(card)
        vbox.setSpacing(6)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #94A3B8; font-size: 13px; font-weight: 600;")
        lbl_val = QLabel(initial_value)
        lbl_val.setStyleSheet("color: #38BDF8; font-size: 20px; font-weight: 700;")
        lbl_val.setObjectName("val_label")

        vbox.addWidget(lbl_title)
        vbox.addWidget(lbl_val)
        card.val_label = lbl_val  # attach reference
        return card

    def update_health(self, health: TrackingHealth) -> None:
        """Update live telemetry metrics."""
        sm_str = (
            health.source_mode.value
            if hasattr(health.source_mode, "value")
            else str(health.source_mode)
        )
        self.card_proc_fps.val_label.setText(f"{health.processed_fps:.1f} FPS")
        self.card_cap_fps.val_label.setText(f"{health.capture_fps:.1f} FPS [{sm_str}]")
        self.card_faces.val_label.setText(f"{health.face_count} Faces")
        self.card_drops.val_label.setText(f"{health.dropped_frames} dropped")
        self.card_stale.val_label.setText(f"{health.stale_frames} stale")

        reason = health.last_block_reason or f"Normal ({sm_str})"
        self.card_reason.val_label.setText(reason)

    def update_performance(self, perf: PerformanceSnapshot) -> None:
        """Update latency, queue, and memory performance telemetry."""
        self.card_lat_e2e.val_label.setText(f"{perf.latency_e2e_ms:.1f} ms")
        self.card_lat_stages.val_label.setText(
            f"LM: {perf.latency_landmark_ms:.1f}ms | Feat: {perf.latency_features_ms:.1f}ms | Rec: {perf.latency_recognition_ms:.1f}ms"
        )
        self.card_mem.val_label.setText(
            f"{perf.memory_working_set_mb:.1f} MB (Peak: {perf.peak_memory_mb:.1f} MB)"
        )

    def update_recognition_state(
        self,
        fsm_state: State | str,
        decision_reason: str,
        candidate_label: str | None,
        hold_elapsed_ms: float,
        hold_target_ms: float = 250.0,
        scores: dict[str, float] | None = None,
        threshold: float = 0.65,
        runner_up_margin: float = 0.15,
    ) -> None:
        """Update explainable intention gate inspection and geometric distance table."""
        # 1. Update State Badge
        state_str = str(fsm_state.value if isinstance(fsm_state, State) else fsm_state).upper()
        self.lbl_fsm_state.setText(state_str)
        if state_str in ("IDLE", "CONFIRMED"):
            self.lbl_fsm_state.setStyleSheet(
                "background-color: #064E3B; color: #ECFDF5; border: 1px solid #059669; "
                "border-radius: 6px; font-size: 15px; font-weight: 700; padding: 4px 12px;"
            )
        elif state_str == "CANDIDATE":
            self.lbl_fsm_state.setStyleSheet(
                "background-color: #1E3A8A; color: #DBEAFE; border: 1px solid #2563EB; "
                "border-radius: 6px; font-size: 15px; font-weight: 700; padding: 4px 12px;"
            )
        elif state_str in ("COOLDOWN", "TRACKING_LOST"):
            self.lbl_fsm_state.setStyleSheet(
                "background-color: #78350F; color: #FEF3C7; border: 1px solid #D97706; "
                "border-radius: 6px; font-size: 15px; font-weight: 700; padding: 4px 12px;"
            )
        else:  # PAUSED
            self.lbl_fsm_state.setStyleSheet(
                "background-color: #7F1D1D; color: #FEE2E2; border: 1px solid #EF4444; "
                "border-radius: 6px; font-size: 15px; font-weight: 700; padding: 4px 12px;"
            )

        # 2. Decision Reason & Candidate
        self.lbl_decision_reason.setText(decision_reason)
        if "ACCEPTED" in decision_reason or "CONFIRMED" in decision_reason:
            self.lbl_decision_reason.setStyleSheet(
                "color: #34D399; font-size: 14px; font-weight: bold;"
            )
        elif "PAUSED" in decision_reason or "TRACKING_LOSS" in decision_reason:
            self.lbl_decision_reason.setStyleSheet(
                "color: #F87171; font-size: 14px; font-weight: bold;"
            )
        else:
            self.lbl_decision_reason.setStyleSheet(
                "color: #FBBF24; font-size: 14px; font-weight: bold;"
            )

        self.lbl_candidate.setText(candidate_label or "None")

        # 3. Hold Progress Bar
        pct = int(min(100.0, max(0.0, (hold_elapsed_ms / max(1.0, hold_target_ms)) * 100.0)))
        self.progress_hold.setValue(pct)
        self.progress_hold.setFormat(f"{pct}% ({hold_elapsed_ms:.0f} / {hold_target_ms:.0f} ms)")

        # 4. Geometric Distance Table
        if scores:
            self.table_distances.setRowCount(len(scores))
            sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            for row, (label, sim) in enumerate(sorted_items):
                # Euclidean distance on unit sphere d = sqrt(2 - 2*sim)
                l2_dist = math.sqrt(max(0.0, 2.0 - 2.0 * sim))
                self.table_distances.setItem(row, 0, QTableWidgetItem(label))
                self.table_distances.setItem(row, 1, QTableWidgetItem(f"{sim:.3f}"))
                self.table_distances.setItem(row, 2, QTableWidgetItem(f"{l2_dist:.3f}"))
                self.table_distances.setItem(row, 3, QTableWidgetItem(f">= {threshold:.2f}"))
                self.table_distances.setItem(row, 4, QTableWidgetItem(f">= {runner_up_margin:.2f}"))

    def append_transition(self, trans: IntentTransition) -> None:
        """Log state transition."""
        label_str = f" [{trans.label_or_none}]" if trans.label_or_none else ""
        item_text = (
            f"Frame #{trans.frame_id:05d} | {trans.before.value} -> {trans.after.value}{label_str} "
            f"| Reason: {trans.reason}"
        )
        self.list_transitions.addItem(item_text)
        self.list_transitions.scrollToBottom()
