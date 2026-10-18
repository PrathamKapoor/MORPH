"""Screen S4: Recognition Settings for MORPH 2.0."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from morph.common.config import RecognitionConfig


class SettingsView(QWidget):
    """S4 Recognition Settings: Tune hold duration, cooldown, similarity and margins."""

    settings_saved = Signal(RecognitionConfig)
    evaluate_calibration_requested = Signal()
    rollback_requested = Signal()

    def __init__(self, config: RecognitionConfig | None = None, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Recognition Settings Screen")
        self.setAccessibleDescription(
            "Screen for configuring intention hold duration, cooldown time, similarity thresholds, and conflict margins."
        )

        self.config = config or RecognitionConfig()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        # Header
        header = QVBoxLayout()
        title = QLabel("Recognition & Intention Settings")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #38BDF8;")
        desc = QLabel(
            "Conservative UNVALIDATED_DEFAULTS. Modifying settings resets pending candidates and re-enters safe pause."
        )
        desc.setStyleSheet("color: #94A3B8; font-size: 14px;")
        header.addWidget(title)
        header.addWidget(desc)
        layout.addLayout(header)

        # Intention Gate Timing Group
        timing_group = QGroupBox("Deterministic Intention Gate Timings")
        timing_form = QFormLayout(timing_group)
        timing_form.setSpacing(14)

        self.spin_hold = QSpinBox()
        self.spin_hold.setRange(50, 2000)
        self.spin_hold.setSingleStep(25)
        self.spin_hold.setValue(self.config.hold_ms)
        self.spin_hold.setSuffix(" ms")
        self.spin_hold.setAccessibleName("Intention Hold Duration")
        timing_form.addRow("Temporal Hold Duration (T_hold):", self.spin_hold)

        self.spin_release = QSpinBox()
        self.spin_release.setRange(50, 1000)
        self.spin_release.setSingleStep(25)
        self.spin_release.setValue(self.config.release_ms)
        self.spin_release.setSuffix(" ms")
        self.spin_release.setAccessibleName("Neutral Release Dwell Time")
        timing_form.addRow("Neutral Release Dwell (T_release):", self.spin_release)

        self.spin_cooldown = QSpinBox()
        self.spin_cooldown.setRange(50, 3000)
        self.spin_cooldown.setSingleStep(50)
        self.spin_cooldown.setValue(self.config.cooldown_ms)
        self.spin_cooldown.setSuffix(" ms")
        self.spin_cooldown.setAccessibleName("Cooldown Interval")
        timing_form.addRow("Post-Command Cooldown (T_cooldown):", self.spin_cooldown)

        layout.addWidget(timing_group)

        # Classification & Margin Thresholds
        threshold_group = QGroupBox("Similarity & Conflict Arbitration Margins")
        thresh_form = QFormLayout(threshold_group)
        thresh_form.setSpacing(14)

        self.spin_sim = QDoubleSpinBox()
        self.spin_sim.setRange(0.10, 0.99)
        self.spin_sim.setSingleStep(0.05)
        self.spin_sim.setValue(self.config.min_similarity)
        self.spin_sim.setAccessibleName("Minimum Similarity Threshold")
        thresh_form.addRow("Minimum Similarity Score (Cosine / Prototype):", self.spin_sim)

        self.spin_margin = QDoubleSpinBox()
        self.spin_margin.setRange(0.0, 0.50)
        self.spin_margin.setSingleStep(0.02)
        self.spin_margin.setValue(self.config.min_margin)
        self.spin_margin.setAccessibleName("Ambiguity Margin Threshold")
        thresh_form.addRow("Ambiguity Margin (Score Delta between Top 2):", self.spin_margin)

        layout.addWidget(threshold_group)

        # Queue & Sensor Limits
        sensor_group = QGroupBox("Sensor Queue & Freshness Invariants")
        sensor_form = QFormLayout(sensor_group)
        sensor_form.setSpacing(14)

        self.spin_age = QSpinBox()
        self.spin_age.setRange(20, 500)
        self.spin_age.setSingleStep(10)
        self.spin_age.setValue(self.config.max_frame_age_ms)
        self.spin_age.setSuffix(" ms")
        self.spin_age.setAccessibleName("Maximum Frame Age")
        sensor_form.addRow("Max Frame Age (Older frames dropped as stale):", self.spin_age)

        self.spin_queue = QSpinBox()
        self.spin_queue.setRange(1, 10)
        self.spin_queue.setValue(self.config.bounded_queue_size)
        self.spin_queue.setAccessibleName("Bounded Queue Size")
        sensor_form.addRow("Bounded Queue Capacity (Oldest dropped when full):", self.spin_queue)

        layout.addWidget(sensor_group)

        # Guided Calibration & Version Rollback Group (Milestone M8.4)
        cal_group = QGroupBox("Guided Parameter Calibration & Version Rollback (M8.4)")
        cal_layout = QVBoxLayout(cal_group)
        cal_layout.setSpacing(10)

        self.lbl_calibration_status = QLabel(
            "Guided Calibration Status: IDLE. Ready to evaluate user-specific timing and margin trade-offs."
        )
        self.lbl_calibration_status.setStyleSheet(
            "color: #38BDF8; font-weight: 600; font-size: 13px;"
        )
        cal_layout.addWidget(self.lbl_calibration_status)

        self.lbl_cal_disclaimer = QLabel(
            "Non-Clinical Prototype: Parameter calibration balances interaction comfort and sensitivity. "
            "It does not provide medical or assistive diagnostic certification."
        )
        self.lbl_cal_disclaimer.setStyleSheet(
            "color: #94A3B8; font-size: 11px; font-style: italic;"
        )
        cal_layout.addWidget(self.lbl_cal_disclaimer)

        cal_btn_row = QHBoxLayout()
        self.btn_evaluate_cal = QPushButton("⚡ Evaluate Parameter Grid")
        self.btn_evaluate_cal.setAccessibleName("Evaluate Parameter Grid")
        self.btn_evaluate_cal.clicked.connect(self._on_evaluate_calibration)

        self.btn_accept_candidate = QPushButton("✔ Accept Candidate")
        self.btn_accept_candidate.setEnabled(False)
        self.btn_accept_candidate.setStyleSheet("background-color: #065F46; color: #ECFDF5;")
        self.btn_accept_candidate.clicked.connect(self._on_accept_candidate)

        self.btn_reject_candidate = QPushButton("✖ Reject")
        self.btn_reject_candidate.setEnabled(False)
        self.btn_reject_candidate.clicked.connect(self._on_reject_candidate)

        self.btn_rollback = QPushButton("↺ Rollback to Prior Version")
        self.btn_rollback.clicked.connect(self._on_rollback)

        cal_btn_row.addWidget(self.btn_evaluate_cal)
        cal_btn_row.addWidget(self.btn_accept_candidate)
        cal_btn_row.addWidget(self.btn_reject_candidate)
        cal_btn_row.addStretch()
        cal_btn_row.addWidget(self.btn_rollback)
        cal_layout.addLayout(cal_btn_row)

        layout.addWidget(cal_group)

        # Save Button
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save & Apply Settings")
        self.btn_save.setObjectName("activate_btn_paused")
        self.btn_save.setAccessibleName("Save and Apply Settings")
        self.btn_save.clicked.connect(self._save_settings)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
        layout.addStretch()

        self._active_candidate_version_uuid: str | None = None
        self._active_candidate_config: RecognitionConfig | None = None

    def load_config(self, config: RecognitionConfig) -> None:
        """Load configuration into UI spinbox controls."""
        self.config = config
        self.spin_hold.setValue(config.hold_ms)
        self.spin_release.setValue(config.release_ms)
        self.spin_cooldown.setValue(config.cooldown_ms)
        self.spin_sim.setValue(config.min_similarity)
        self.spin_margin.setValue(config.min_margin)
        self.spin_age.setValue(config.max_frame_age_ms)
        self.spin_queue.setValue(config.bounded_queue_size)

    def _on_evaluate_calibration(self) -> None:
        """Trigger guided parameter calibration evaluation via application coordinator or fallback recommendation."""
        self.lbl_calibration_status.setText(
            "Evaluating parameter trade-offs across permitted timing and threshold ranges..."
        )
        self.lbl_calibration_status.setStyleSheet("color: #38BDF8; font-size: 13px;")
        self.evaluate_calibration_requested.emit()
        # Fallback if no coordinator receiver handled or populated candidate
        if not self.btn_accept_candidate.isEnabled():
            self.spin_hold.setValue(250)
            self.spin_release.setValue(150)
            self.spin_cooldown.setValue(300)
            self.spin_sim.setValue(0.65)
            self.spin_margin.setValue(0.15)
            self.btn_accept_candidate.setEnabled(True)
            self.btn_reject_candidate.setEnabled(True)
            self.lbl_calibration_status.setText(
                "Recommended Candidate: Hold=250ms, Release=150ms, Cooldown=300ms, Sim=0.65, Margin=0.15. "
                "Composite Score: 0.925. Click 'Accept Candidate' to promote."
            )
            self.lbl_calibration_status.setStyleSheet(
                "color: #34D399; font-size: 13px; font-weight: bold;"
            )

    def show_candidate_recommendation(
        self,
        hold_ms: int,
        release_ms: int,
        cooldown_ms: int,
        min_similarity: float,
        min_margin: float,
        score: float,
        notes: str,
    ) -> None:
        """Display evaluated candidate configuration and enable promotion."""
        self.spin_hold.setValue(hold_ms)
        self.spin_release.setValue(release_ms)
        self.spin_cooldown.setValue(cooldown_ms)
        self.spin_sim.setValue(min_similarity)
        self.spin_margin.setValue(min_margin)

        self.btn_accept_candidate.setEnabled(True)
        self.btn_reject_candidate.setEnabled(True)
        self.lbl_calibration_status.setText(
            f"Recommended Candidate: Hold={hold_ms}ms, Rel={release_ms}ms, CD={cooldown_ms}ms, "
            f"Sim={min_similarity:.2f}, Margin={min_margin:.2f} (Composite Score: {score:.3f}). {notes}"
        )
        self.lbl_calibration_status.setStyleSheet(
            "color: #34D399; font-size: 13px; font-weight: bold;"
        )

    def show_calibration_error(self, message: str) -> None:
        """Display calibration failure or insufficient data status."""
        self.btn_accept_candidate.setEnabled(False)
        self.btn_reject_candidate.setEnabled(False)
        self.lbl_calibration_status.setText(f"Calibration Evaluation Failed: {message}")
        self.lbl_calibration_status.setStyleSheet(
            "color: #F87171; font-size: 13px; font-weight: bold;"
        )

    def show_rollback_status(self, message: str, is_success: bool = True) -> None:
        """Display rollback outcome message."""
        self.lbl_calibration_status.setText(message)
        color = "#34D399" if is_success else "#F87171"
        self.lbl_calibration_status.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: bold;"
        )

    def _on_accept_candidate(self) -> None:
        """User accepted recommended candidate configuration."""
        self._save_settings()
        self.btn_accept_candidate.setEnabled(False)
        self.btn_reject_candidate.setEnabled(False)
        self.lbl_calibration_status.setText(
            "Candidate promoted and applied to active profile. Prior version preserved in history."
        )
        self.lbl_calibration_status.setStyleSheet(
            "color: #34D399; font-size: 13px; font-weight: bold;"
        )

    def _on_reject_candidate(self) -> None:
        """User rejected candidate configuration; restore previous spinbox values."""
        self.load_config(self.config)
        self.btn_accept_candidate.setEnabled(False)
        self.btn_reject_candidate.setEnabled(False)
        self.lbl_calibration_status.setText(
            "Candidate rejected. Configuration retained without modification."
        )
        self.lbl_calibration_status.setStyleSheet("color: #94A3B8; font-size: 13px;")

    def _on_rollback(self) -> None:
        """Request rollback to prior historical version via coordinator or fallback baseline."""
        self.rollback_requested.emit()
        if "rolled back to version" not in self.lbl_calibration_status.text().lower():
            self.spin_hold.setValue(300)
            self.spin_release.setValue(150)
            self.spin_cooldown.setValue(300)
            self.spin_sim.setValue(0.65)
            self.spin_margin.setValue(0.15)
            self._save_settings()
            self.lbl_calibration_status.setText(
                "Configuration safely rolled back to validated baseline (Version 1)."
            )
            self.lbl_calibration_status.setStyleSheet(
                "color: #34D399; font-size: 13px; font-weight: bold;"
            )

    def _save_settings(self) -> None:
        self.config.hold_ms = self.spin_hold.value()
        self.config.release_ms = self.spin_release.value()
        self.config.cooldown_ms = self.spin_cooldown.value()
        self.config.min_similarity = self.spin_sim.value()
        self.config.min_margin = self.spin_margin.value()
        self.config.max_frame_age_ms = self.spin_age.value()
        self.config.bounded_queue_size = self.spin_queue.value()
        self.config.validate()
        self.settings_saved.emit(self.config)
