"""Accessible controlled evaluation session view for real-world research trials (Milestone M8.2).

Provides:
- Anonymized participant identifier management (PART-XXXX)
- Explicit informed consent gating (zero raw video/audio storage disclosure)
- 8 structured task scenarios (intended, neutral, distractors, board, pause/recovery, camera drift, cross-session, recalibration)
- Ground-truth labeling with revision preservation and categorical classification
- Session integrity audit validation gating and zero-residue session deletion
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from morph.common.types import (
    AnnotationSource,
    EvaluationScenario,
    FeaturePacket,
    GroundTruthLabelType,
)
from morph.evaluation.session import EvaluationSession
from morph.evaluation.validator import EvaluationSessionValidator, ValidationResult
from morph.storage.db import DatabaseManager


class EvaluationSessionView(QWidget):
    """View for managing controlled, consented participant evaluation sessions."""

    session_started = Signal(str, str)  # participant_id, session_uuid
    session_completed = Signal(dict)  # session metadata summary
    session_discarded = Signal(str)  # session_uuid
    cue_triggered = Signal(str)  # cue label

    PROTOCOL_STAGES = [
        (
            EvaluationScenario.SCEN_01_INTENDED.value,
            "SCEN-01: Intended Gesture Trials (5 reps x 3s)",
            25,
        ),
        (
            EvaluationScenario.SCEN_02_NEUTRAL.value,
            "SCEN-02: Neutral Resting Baseline (30s)",
            30,
        ),
        (
            EvaluationScenario.SCEN_03_DISTRACTOR.value,
            "SCEN-03: Distractor Tasks (Talking, Coughing, Nodding) (45s)",
            45,
        ),
        (
            EvaluationScenario.SCEN_04_BOARD_TASK.value,
            "SCEN-04: Communication Board Selection Task (60s)",
            60,
        ),
        (
            EvaluationScenario.SCEN_05_PAUSE_RECOVERY.value,
            "SCEN-05: Pause & Tracking Loss Recovery (30s)",
            30,
        ),
        (
            EvaluationScenario.SCEN_06_CAMERA_DRIFT.value,
            "SCEN-06: Head Pose / Camera Angle Change (30s)",
            30,
        ),
        (
            EvaluationScenario.SCEN_07_CROSS_SESSION.value,
            "SCEN-07: Cross-Session Retest (No Retraining) (45s)",
            45,
        ),
        (
            EvaluationScenario.SCEN_08_RECALIBRATION.value,
            "SCEN-08: Recalibration & Profile Comparison (45s)",
            45,
        ),
    ]

    def __init__(self, db: DatabaseManager | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.db = db or DatabaseManager()
        self.session: EvaluationSession | None = None
        self.validator = EvaluationSessionValidator()
        self._active_stage_idx: int = 0
        self._stage_timer = QTimer(self)
        self._stage_timer.timeout.connect(self._on_timer_tick)
        self._stage_seconds_remaining: int = 0
        self._total_recorded_frames: int = 0
        self._active_cue_label: str | None = None
        self._cue_start_ns: int = 0

        self.setAccessibleName("Controlled Evaluation Session Screen")
        self.setAccessibleDescription(
            "Screen for conducting structured, consented accessibility research trials with anonymized participant IDs and automated task cueing."
        )

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # 1. Header
        header = QVBoxLayout()
        title = QLabel("Controlled Evaluation Session Runner")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #38BDF8;")
        desc = QLabel(
            "Conduct structured within-subject evaluation sessions with automated task cueing, "
            "independent ground-truth event logging, revision auditing, and informed consent verification."
        )
        desc.setStyleSheet("color: #94A3B8; font-size: 14px;")
        header.addWidget(title)
        header.addWidget(desc)
        layout.addLayout(header)

        # 2. Participant & Consent Card
        top_row = QHBoxLayout()

        participant_group = QGroupBox("Participant Information")
        p_layout = QVBoxLayout(participant_group)
        p_row = QHBoxLayout()
        p_label = QLabel("Participant ID:")
        p_label.setStyleSheet("font-weight: 600; color: #E2E8F0;")
        self.txt_participant_id = QLineEdit(f"P-{uuid.uuid4().hex[:6].upper()}")

        self.txt_participant_id.setAccessibleName("Participant Identifier")
        self.btn_new_id = QPushButton("Generate ID")
        self.btn_new_id.clicked.connect(self._generate_new_id)
        p_row.addWidget(p_label)
        p_row.addWidget(self.txt_participant_id)
        p_row.addWidget(self.btn_new_id)
        p_layout.addLayout(p_row)
        top_row.addWidget(participant_group, 1)

        consent_group = QGroupBox("Informed Consent Gate (Zero Raw Video Persisted)")
        c_layout = QVBoxLayout(consent_group)
        self.chk_consent = QCheckBox(
            "Participant has signed informed consent. Only mathematical 32-D feature vectors "
            "are stored. Zero raw camera video or audio is ever written to disk or transmitted."
        )
        self.chk_consent.setStyleSheet("color: #E2E8F0; font-size: 13px;")
        self.chk_consent.toggled.connect(self._on_consent_toggled)
        self.lbl_consent_status = QLabel("Consent Status: PENDING")
        self.lbl_consent_status.setStyleSheet("color: #F87171; font-weight: bold; font-size: 13px;")
        c_layout.addWidget(self.chk_consent)
        c_layout.addWidget(self.lbl_consent_status)
        top_row.addWidget(consent_group, 2)
        layout.addLayout(top_row)

        # 3. Protocol Task Runner Card
        runner_group = QGroupBox("Structured Study Protocol Runner (8 Research Scenarios)")
        r_layout = QVBoxLayout(runner_group)

        stage_row = QHBoxLayout()
        stage_lbl = QLabel("Scenario / Stage:")
        stage_lbl.setStyleSheet("font-weight: 600; color: #E2E8F0;")
        self.cmb_stages = QComboBox()
        for _, name, dur in self.PROTOCOL_STAGES:
            self.cmb_stages.addItem(f"{name} ({dur}s)")
        self.cmb_stages.currentIndexChanged.connect(self._on_stage_selected)

        self.lbl_stage_time = QLabel("00:25")
        self.lbl_stage_time.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #38BDF8; padding: 0 12px;"
        )
        stage_row.addWidget(stage_lbl)
        stage_row.addWidget(self.cmb_stages, 1)
        stage_row.addWidget(self.lbl_stage_time)
        r_layout.addLayout(stage_row)

        # Big cue banner
        self.cue_banner = QLabel("Select stage and click 'Start Stage' to begin guided protocol.")
        self.cue_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cue_banner.setStyleSheet(
            "background-color: #1E293B; color: #F8FAFC; border: 2px solid #334155; "
            "border-radius: 8px; font-size: 18px; font-weight: 600; padding: 20px;"
        )
        r_layout.addWidget(self.cue_banner)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #0F172A; border: 1px solid #334155; border-radius: 4px; height: 12px; }"
            "QProgressBar::chunk { background-color: #38BDF8; border-radius: 4px; }"
        )
        r_layout.addWidget(self.progress_bar)

        # Cue Labeling Row
        cue_ctrl_row = QHBoxLayout()
        cue_type_lbl = QLabel("Observation Category:")
        cue_type_lbl.setStyleSheet("font-weight: 600; color: #CBD5E1;")
        self.cmb_label_type = QComboBox()
        for lt in GroundTruthLabelType:
            self.cmb_label_type.addItem(lt.value)

        self.btn_trigger_cue = QPushButton("⚡ Fire / Log Ground-Truth Event")
        self.btn_trigger_cue.setEnabled(False)
        self.btn_trigger_cue.clicked.connect(self._on_fire_manual_cue)

        cue_ctrl_row.addWidget(cue_type_lbl)
        cue_ctrl_row.addWidget(self.cmb_label_type, 1)
        cue_ctrl_row.addWidget(self.btn_trigger_cue)
        r_layout.addLayout(cue_ctrl_row)

        # Control buttons
        btn_row = QHBoxLayout()
        self.btn_start_stage = QPushButton("▶ Start Stage")
        self.btn_start_stage.setObjectName("activate_btn_paused")
        self.btn_start_stage.setEnabled(False)
        self.btn_start_stage.clicked.connect(self._toggle_stage_run)

        self.btn_next_stage = QPushButton("Next Stage ⏭")
        self.btn_next_stage.clicked.connect(self._advance_stage)

        btn_row.addWidget(self.btn_start_stage)
        btn_row.addWidget(self.btn_next_stage)
        btn_row.addStretch()
        r_layout.addLayout(btn_row)
        layout.addWidget(runner_group)

        # 4. Live Ground Truth & Review Table
        events_group = QGroupBox("Independent Ground-Truth Events & Revision Audit")
        e_layout = QVBoxLayout(events_group)

        self.table_events = QTableWidget(0, 8)
        self.table_events.setHorizontalHeaderLabels(
            [
                "Event UUID",
                "Label",
                "Category",
                "Start (s)",
                "End (s)",
                "Dur (ms)",
                "Rev",
                "Reviewed?",
            ]
        )
        self.table_events.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_events.setStyleSheet(
            "QTableWidget { background-color: #1E222A; border: 1px solid #334155; gridline-color: #2D3748; }"
            "QHeaderView::section { background-color: #0F172A; color: #94A3B8; font-weight: bold; padding: 6px; }"
        )
        e_layout.addWidget(self.table_events)

        # Annotation review row
        review_row = QHBoxLayout()
        self.btn_mark_reviewed = QPushButton("✏ Mark as Reviewed / Corrected")
        self.btn_mark_reviewed.clicked.connect(self._on_review_selected_event)
        self.btn_delete_event = QPushButton("✖ Delete Selected Event")
        self.btn_delete_event.clicked.connect(self._on_delete_selected_event)
        review_row.addWidget(self.btn_mark_reviewed)
        review_row.addWidget(self.btn_delete_event)
        review_row.addStretch()
        e_layout.addLayout(review_row)
        layout.addWidget(events_group)

        # 5. Session Actions & Validation Bar
        action_row = QHBoxLayout()
        self.btn_validate_session = QPushButton("✔ Validate Session Integrity")
        self.btn_validate_session.setStyleSheet(
            "background-color: #065F46; color: #ECFDF5; border: 1px solid #10B981; font-weight: bold;"
        )
        self.btn_validate_session.clicked.connect(self._on_validate_session)

        self.btn_export_session = QPushButton("📥 Export Session JSON")
        self.btn_export_session.clicked.connect(self._on_export_session)

        self.btn_discard = QPushButton("🗑 Wipe Session (Zero Residue)")
        self.btn_discard.setStyleSheet(
            "background-color: #7F1D1D; color: #FEE2E2; border-color: #EF4444;"
        )
        self.btn_discard.clicked.connect(self._on_discard_clicked)

        self.lbl_validation_badge = QLabel("Audit Status: UNVALIDATED")
        self.lbl_validation_badge.setStyleSheet(
            "color: #94A3B8; font-weight: bold; padding: 4px 10px;"
        )

        action_row.addWidget(self.btn_validate_session)
        action_row.addWidget(self.btn_export_session)
        action_row.addWidget(self.lbl_validation_badge)
        action_row.addStretch()
        action_row.addWidget(self.btn_discard)
        layout.addLayout(action_row)

    def _generate_new_id(self) -> None:
        self.txt_participant_id.setText(f"P-{uuid.uuid4().hex[:6].upper()}")

    def _on_consent_toggled(self, checked: bool) -> None:
        if checked:
            self.lbl_consent_status.setText("Consent Status: VERIFIED & GRANTED")
            self.lbl_consent_status.setStyleSheet(
                "color: #34D399; font-weight: bold; font-size: 13px;"
            )
            self.btn_start_stage.setEnabled(True)
            if self.session is None:
                p_id = self.txt_participant_id.text().strip() or "ANONYMOUS"
                scenario_code = self.PROTOCOL_STAGES[self._active_stage_idx][0]
                self.session = EvaluationSession(
                    profile_uuid=p_id,
                    consented=True,
                    db=self.db,
                    scenario_id=scenario_code,
                )
                self.session_started.emit(p_id, self.session.session_uuid)
        else:
            self.lbl_consent_status.setText("Consent Status: PENDING")
            self.lbl_consent_status.setStyleSheet(
                "color: #F87171; font-weight: bold; font-size: 13px;"
            )
            self.btn_start_stage.setEnabled(False)
            self.btn_trigger_cue.setEnabled(False)
            if self.session is not None:
                self.session.consented = False

    def _on_stage_selected(self, idx: int) -> None:
        self._active_stage_idx = idx
        dur = self.PROTOCOL_STAGES[idx][2]
        self._stage_seconds_remaining = dur
        self.lbl_stage_time.setText(f"{dur // 60:02d}:{dur % 60:02d}")
        self.progress_bar.setValue(0)
        scenario_code = self.PROTOCOL_STAGES[idx][0]
        if self.session is not None:
            self.session.scenario_id = scenario_code
        self.cue_banner.setText(
            f"Stage selected: {self.PROTOCOL_STAGES[idx][1]}. Click 'Start Stage'."
        )

    def _toggle_stage_run(self) -> None:
        if self._stage_timer.isActive():
            self._stage_timer.stop()
            self.btn_start_stage.setText("▶ Resume Stage")
            self.btn_trigger_cue.setEnabled(False)
            self.cue_banner.setText("Stage paused. Click 'Resume Stage' to continue.")
        else:
            dur = self.PROTOCOL_STAGES[self._active_stage_idx][2]
            if self._stage_seconds_remaining <= 0:
                self._stage_seconds_remaining = dur
            self._stage_timer.start(1000)
            self.btn_start_stage.setText("⏸ Pause Stage")
            self.btn_trigger_cue.setEnabled(True)
            stage_name = self.PROTOCOL_STAGES[self._active_stage_idx][0]
            self._update_cue_display_for_stage(stage_name)

    def _update_cue_display_for_stage(self, stage_code: str) -> None:
        if "INTENDED" in stage_code:
            self.cue_banner.setText(
                "⚡ SCEN-01: Perform intended gesture trials cleanly when prompted."
            )
            self.cue_banner.setStyleSheet(
                "background-color: #1E3A8A; color: #DBEAFE; border: 2px solid #2563EB; font-size: 18px; font-weight: 600; padding: 20px;"
            )
        elif "NEUTRAL" in stage_code:
            self.cue_banner.setText(
                "🟢 SCEN-02: Maintain comfortable neutral resting posture. Zero command triggers expected."
            )
            self.cue_banner.setStyleSheet(
                "background-color: #064E3B; color: #ECFDF5; border: 2px solid #059669; font-size: 18px; font-weight: 600; padding: 20px;"
            )
        elif "DISTRACTOR" in stage_code:
            self.cue_banner.setText(
                "📖 SCEN-03: Engage in talking, coughing, nodding, and reading aloud. Involuntary movements must be gated."
            )
            self.cue_banner.setStyleSheet(
                "background-color: #78350F; color: #FEF3C7; border: 2px solid #D97706; font-size: 18px; font-weight: 600; padding: 20px;"
            )
        elif "BOARD" in stage_code:
            self.cue_banner.setText(
                "💬 SCEN-04: Perform sequential phrase composition on communication board."
            )
            self.cue_banner.setStyleSheet(
                "background-color: #312E81; color: #EDE9FE; border: 2px solid #6366F1; font-size: 18px; font-weight: 600; padding: 20px;"
            )
        elif "PAUSE" in stage_code:
            self.cue_banner.setText(
                "⏸ SCEN-05: Test pause toggle and temporary occlusion tracking recovery."
            )
            self.cue_banner.setStyleSheet(
                "background-color: #4C1D95; color: #EDE9FE; border: 2px solid #7C3AED; font-size: 18px; font-weight: 600; padding: 20px;"
            )
        else:
            self.cue_banner.setText(f"🔬 Active Scenario: {stage_code}. Follow operator cues.")
            self.cue_banner.setStyleSheet(
                "background-color: #1E293B; color: #F8FAFC; border: 2px solid #334155; font-size: 18px; font-weight: 600; padding: 20px;"
            )

    def _on_timer_tick(self) -> None:
        if self._stage_seconds_remaining > 0:
            self._stage_seconds_remaining -= 1
            total_dur = self.PROTOCOL_STAGES[self._active_stage_idx][2]
            elapsed = total_dur - self._stage_seconds_remaining
            pct = int((elapsed / total_dur) * 100)
            self.progress_bar.setValue(pct)
            m = self._stage_seconds_remaining // 60
            s = self._stage_seconds_remaining % 60
            self.lbl_stage_time.setText(f"{m:02d}:{s:02d}")
        else:
            self._stage_timer.stop()
            self.btn_start_stage.setText("▶ Start Stage")
            self.btn_trigger_cue.setEnabled(False)
            self.cue_banner.setText(
                f"Stage completed: {self.PROTOCOL_STAGES[self._active_stage_idx][1]}."
            )
            self.cue_banner.setStyleSheet(
                "background-color: #1E293B; color: #F8FAFC; border: 2px solid #334155; font-size: 18px; font-weight: 600; padding: 20px;"
            )

    def _on_fire_manual_cue(self) -> None:
        """Trigger and log an intentional ground-truth cue event."""
        stage_code = self.PROTOCOL_STAGES[self._active_stage_idx][0]
        label = "Brow Raise"
        if "BOARD" in stage_code:
            label = "Smile / Lip Corner Pull"
        elif "DISTRACTOR" in stage_code:
            label = "None (Distractor)"

        label_type = self.cmb_label_type.currentText()
        now_ns = time.perf_counter_ns()
        if self.session is not None:
            # Displayed cue is a task prompt point-marker, not proof of user movement duration.
            # End timestamp matches start timestamp until independently reviewed/confirmed.
            self.session.add_ground_truth(
                label=label,
                start_ns=now_ns,
                end_ns=now_ns,
                annotator=self.txt_participant_id.text().strip() or "RESEARCHER",
                label_type=label_type,
                notes="Task cue displayed. Actual movement onset/completion pending independent confirmation.",
                annotation_source=AnnotationSource.TASK_PROMPT,
            )
            self._refresh_events_table()
            self.cue_triggered.emit(label)

    def _refresh_events_table(self) -> None:
        """Reload events table from active session."""
        self.table_events.setRowCount(0)
        if self.session is None:
            return

        for evt in self.session.ground_truth_events:
            row = self.table_events.rowCount()
            self.table_events.insertRow(row)
            dur_ms = (evt.end_ns - evt.start_ns) / 1_000_000.0

            self.table_events.setItem(row, 0, QTableWidgetItem(evt.event_uuid[:8]))
            self.table_events.setItem(row, 1, QTableWidgetItem(evt.label))
            self.table_events.setItem(row, 2, QTableWidgetItem(evt.label_type))
            self.table_events.setItem(row, 3, QTableWidgetItem(f"{evt.start_ns / 1e9:.2f}"))
            self.table_events.setItem(row, 4, QTableWidgetItem(f"{evt.end_ns / 1e9:.2f}"))
            self.table_events.setItem(row, 5, QTableWidgetItem(f"{dur_ms:.1f}"))
            self.table_events.setItem(row, 6, QTableWidgetItem(str(evt.revision)))
            self.table_events.setItem(row, 7, QTableWidgetItem("Yes" if evt.is_reviewed else "No"))

    def _on_review_selected_event(self) -> None:
        """Correct or review selected ground-truth event with revision tracking."""
        curr_row = self.table_events.currentRow()
        if (
            curr_row < 0
            or self.session is None
            or curr_row >= len(self.session.ground_truth_events)
        ):
            QMessageBox.information(
                self, "Select Event", "Please select an event row from the table to review."
            )
            return

        evt = self.session.ground_truth_events[curr_row]
        new_type = self.cmb_label_type.currentText()
        updated = self.session.update_ground_truth(
            event_uuid=evt.event_uuid,
            label_type=new_type,
            notes=f"Reviewed by {self.txt_participant_id.text().strip()}",
        )
        if updated:
            self._refresh_events_table()
            QMessageBox.information(
                self,
                "Annotation Updated",
                f"Event {evt.event_uuid[:8]} updated to revision {updated.revision} ({updated.label_type}).",
            )

    def _on_delete_selected_event(self) -> None:
        """Remove an annotation from the active session."""
        curr_row = self.table_events.currentRow()
        if (
            curr_row < 0
            or self.session is None
            or curr_row >= len(self.session.ground_truth_events)
        ):
            return
        evt = self.session.ground_truth_events[curr_row]
        self.session.delete_ground_truth(evt.event_uuid)
        self._refresh_events_table()

    def _on_validate_session(self) -> None:
        """Audit session against research admission criteria."""
        if self.session is None:
            QMessageBox.warning(self, "No Session", "No active session to validate.")
            return

        res: ValidationResult = self.validator.validate_session(self.session)
        if res.is_valid:
            self.lbl_validation_badge.setText("Audit Status: VALID (Admissible)")
            self.lbl_validation_badge.setStyleSheet(
                "color: #34D399; font-weight: bold; background-color: #064E3B; border-radius: 4px; padding: 4px 10px;"
            )
            QMessageBox.information(
                self,
                "Session Admissible",
                f"Session {self.session.session_uuid[:8]} passed all integrity checks!\n"
                f"- Exposure: {res.total_exposure_sec:.1f}s\n"
                f"- Non-command: {res.non_command_exposure_sec:.1f}s\n"
                f"- Intended Events: {res.intended_command_count}",
            )
        else:
            err_text = "\n".join(f"• {e}" for e in res.errors)
            self.lbl_validation_badge.setText(f"Audit Status: REJECTED ({res.exclusion_code})")
            self.lbl_validation_badge.setStyleSheet(
                "color: #F87171; font-weight: bold; background-color: #7F1D1D; border-radius: 4px; padding: 4px 10px;"
            )
            QMessageBox.critical(
                self,
                "Session Rejected",
                f"Session failed admission criteria ({res.exclusion_code}):\n{err_text}",
            )

    def _on_export_session(self) -> None:
        """Export session JSON dictionary without PII."""
        if self.session is None:
            QMessageBox.warning(self, "No Session", "No active session to export.")
            return

        export_dir = Path("exports")
        export_dir.mkdir(parents=True, exist_ok=True)
        fname = f"session_{self.session.participant_id}_{self.session.session_uuid[:8]}.json"
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Evaluation Session JSON",
            str(export_dir / fname),
            "JSON Files (*.json)",
        )
        if out_path:
            p = Path(out_path)
            data = self.session.export_session_dict()
            p.write_text(json.dumps(data, indent=2), encoding="utf-8")
            QMessageBox.information(self, "Session Exported", f"Exported session data to:\n{p}")

    def _advance_stage(self) -> None:
        self._stage_timer.stop()
        if self._active_stage_idx < len(self.PROTOCOL_STAGES) - 1:
            self._active_stage_idx += 1
            self.cmb_stages.setCurrentIndex(self._active_stage_idx)
        else:
            self.cue_banner.setText(
                "All study protocol stages completed. You may now export or save the session."
            )
            self.btn_start_stage.setEnabled(False)
            self.btn_trigger_cue.setEnabled(False)

    def _on_discard_clicked(self) -> None:
        """Confirm wipe with user via modal dialog before discarding."""
        reply = QMessageBox.question(
            self,
            "Confirm Zero-Residue Wipe",
            "Are you sure you want to discard this evaluation session?\n"
            "All volatile feature vectors and database records will be permanently erased.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._discard_session()

    def _discard_session(self) -> None:
        """Immediately wipe recorded session data (zero-residue participant right to withdraw)."""
        self._stage_timer.stop()
        if self.session is not None:
            s_uuid = self.session.session_uuid
            self.session.wipe_session()
            self.session = None
            self.session_discarded.emit(s_uuid)

        self.table_events.setRowCount(0)
        self.chk_consent.setChecked(False)
        self.progress_bar.setValue(0)
        self.lbl_validation_badge.setText("Audit Status: UNVALIDATED")
        self.lbl_validation_badge.setStyleSheet(
            "color: #94A3B8; font-weight: bold; padding: 4px 10px;"
        )
        self.cue_banner.setText("Session discarded and volatile memory wiped cleanly.")
        self.cue_banner.setStyleSheet(
            "background-color: #1E293B; color: #F8FAFC; border: 2px solid #334155; font-size: 18px; font-weight: 600; padding: 20px;"
        )

    def record_incoming_feature(self, packet: FeaturePacket) -> bool:
        """Forward feature packet to active session if recording."""
        if self.session is not None and self._stage_timer.isActive():
            self._total_recorded_frames += 1
            return self.session.record_feature(packet)
        return False
