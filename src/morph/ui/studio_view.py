"""Screen S2: Gesture Studio View for calibration, enrollment, and practice."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from morph.common.types import RecognitionResult


class StudioView(QWidget):
    """S2 Gesture Studio: Calibration, 3-gesture enrollment (5-10 samples), practice mode."""

    calibrate_neutral_requested = Signal()
    record_sample_requested = Signal(str)  # gesture label
    redo_sample_requested = Signal(str)
    practice_toggled = Signal(bool)
    save_profile_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Gesture Studio Screen")
        self.setAccessibleDescription(
            "Screen for calibrating neutral rest baseline, training up to 3 gestures, and practicing without executing actions."
        )

        self._in_practice = False
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Title
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Gesture Studio (Calibration & Practice)")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #38BDF8;")
        desc = QLabel(
            "Guided neutral calibration, 5–10 sample enrollment for up to 3 gestures, and non-executing practice sandbox."
        )
        desc.setStyleSheet("color: #94A3B8; font-size: 14px;")
        title_box.addWidget(title)
        title_box.addWidget(desc)
        header.addLayout(title_box)
        header.addStretch()

        self.practice_badge = QLabel("Mode: Studio Setup")
        self.practice_badge.setStyleSheet(
            "background-color: #1E293B; color: #94A3B8; border: 1px solid #475569; padding: 6px 12px; border-radius: 6px; font-weight: bold;"
        )
        header.addWidget(self.practice_badge)
        layout.addLayout(header)

        # Step 1: Neutral Baseline Calibration Card
        neutral_box = QGroupBox("Step 1: Neutral Rest Baseline")
        n_layout = QHBoxLayout(neutral_box)
        self.lbl_neutral_status = QLabel(
            "Neutral Baseline: Not Calibrated. Please relax your facial muscles and look naturally at the camera."
        )
        self.lbl_neutral_status.setStyleSheet("color: #CBD5E1; font-size: 14px;")
        self.btn_neutral = QPushButton("Calibrate Rest Baseline (3s)")
        self.btn_neutral.setAccessibleName("Calibrate Neutral Rest Baseline")
        self.btn_neutral.setAccessibleDescription("Calibrates rest baseline for 3 seconds.")
        self.btn_neutral.clicked.connect(self.calibrate_neutral_requested.emit)
        n_layout.addWidget(self.lbl_neutral_status)
        n_layout.addStretch()
        n_layout.addWidget(self.btn_neutral)
        layout.addWidget(neutral_box)

        # Step 2: 3-Gesture Enrollment Grid
        gest_box = QGroupBox("Step 2: Train Up To 3 Facial Movements (5–10 Samples Each)")
        g_grid = QGridLayout(gest_box)
        g_grid.setSpacing(14)

        self.gesture_rows: list[dict] = []
        default_gestures = [
            ("Brow Raise", "NEXT_TILE", "Raise both eyebrows comfortably"),
            ("Smile / Lip Corner Pull", "SELECT_TILE", "Slight smile or pull corners of lips"),
            ("Chin Raise / Mouth Open", "PREVIOUS_TILE", "Gently open mouth or lift chin"),
        ]

        for i, (g_name, action_default, hint) in enumerate(default_gestures):
            lbl_name = QLabel(
                f"<b>Gesture {i + 1}: {g_name}</b><br><small style='color:#94A3B8'>{hint}</small>"
            )
            lbl_name.setTextFormat(Qt.RichText)

            lbl_count = QLabel("0 / 10 samples")
            lbl_count.setStyleSheet("color: #FBBF24; font-weight: bold;")

            progress = QProgressBar()
            progress.setRange(0, 10)
            progress.setValue(0)
            progress.setFixedWidth(140)

            btn_record = QPushButton("Capture Sample")
            btn_record.setAccessibleName(f"Capture Sample for Gesture {i + 1}")
            btn_record.clicked.connect(
                lambda _, name=g_name: self.record_sample_requested.emit(name)
            )

            btn_redo = QPushButton("Redo")
            btn_redo.setAccessibleName(f"Redo Sample for Gesture {i + 1}")
            btn_redo.clicked.connect(lambda _, name=g_name: self.redo_sample_requested.emit(name))

            combo_action = QComboBox()
            combo_action.addItems(
                ["NEXT_TILE", "PREVIOUS_TILE", "SELECT_TILE", "SPEAK_TILE", "BACK", "PAUSE"]
            )
            combo_action.setCurrentText(action_default)
            combo_action.setAccessibleName(f"Action mapping for Gesture {i + 1}")

            g_grid.addWidget(lbl_name, i, 0)
            g_grid.addWidget(lbl_count, i, 1)
            g_grid.addWidget(progress, i, 2)
            g_grid.addWidget(btn_record, i, 3)
            g_grid.addWidget(btn_redo, i, 4)
            g_grid.addWidget(combo_action, i, 5)

            self.gesture_rows.append(
                {
                    "name": g_name,
                    "count_label": lbl_count,
                    "progress": progress,
                    "record_btn": btn_record,
                    "redo_btn": btn_redo,
                    "action_combo": combo_action,
                    "sample_count": 0,
                }
            )

        layout.addWidget(gest_box)

        # Step 2.5: Conflict & Ambiguity Warning Card (M5.1)
        self.conflict_box = QGroupBox("⚠️ Gesture Collision & Ambiguity Diagnostics")
        self.conflict_box.setVisible(False)
        c_layout = QVBoxLayout(self.conflict_box)
        self.lbl_conflict_title = QLabel("")
        self.lbl_conflict_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.lbl_conflict_desc = QLabel("")
        self.lbl_conflict_desc.setWordWrap(True)
        self.lbl_conflict_desc.setStyleSheet("font-size: 13px; line-height: 1.4;")
        self.lbl_conflict_recom = QLabel("")
        self.lbl_conflict_recom.setWordWrap(True)
        self.lbl_conflict_recom.setStyleSheet(
            "font-size: 13px; font-style: italic; color: #E2E8F0;"
        )
        c_layout.addWidget(self.lbl_conflict_title)
        c_layout.addWidget(self.lbl_conflict_desc)
        c_layout.addWidget(self.lbl_conflict_recom)
        layout.addWidget(self.conflict_box)

        # Step 3: Non-Executing Practice Sandbox
        practice_box = QGroupBox("Step 3: Non-Executing Practice Sandbox (Zero Real Side Effects)")
        p_layout = QVBoxLayout(practice_box)
        p_desc = QLabel(
            "Test movements with real-time feedback. Practice Mode runs classifier scores without triggering any speech or navigation."
        )
        p_desc.setStyleSheet("color: #94A3B8; font-size: 13px;")
        p_layout.addWidget(p_desc)

        feedback_layout = QHBoxLayout()
        self.btn_practice = QPushButton("Start Practice Mode")
        self.btn_practice.setAccessibleName("Toggle Non-Executing Practice Mode")
        self.btn_practice.clicked.connect(self._toggle_practice)
        feedback_layout.addWidget(self.btn_practice)

        self.lbl_practice_feedback = QLabel(
            "Practice Status: Inactive. Click 'Start Practice Mode' to test."
        )
        self.lbl_practice_feedback.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #CBD5E1;"
        )
        feedback_layout.addWidget(self.lbl_practice_feedback)
        feedback_layout.addStretch()
        p_layout.addLayout(feedback_layout)
        layout.addWidget(practice_box)

        # Footer Actions
        footer = QHBoxLayout()
        self.btn_save = QPushButton("💾 Save Trained Profile")
        self.btn_save.setObjectName("activate_btn_paused")
        self.btn_save.setAccessibleName("Save Profile to SQLite Database")
        self.btn_save.setMinimumHeight(48)
        self.btn_save.clicked.connect(self.save_profile_requested.emit)
        footer.addStretch()
        footer.addWidget(self.btn_save)
        layout.addLayout(footer)

    def _toggle_practice(self) -> None:
        self._in_practice = not self._in_practice
        if self._in_practice:
            self.btn_practice.setText("Stop Practice Mode")
            self.practice_badge.setText("Mode: PRACTICE SANDBOX (No Real Commands)")
            self.practice_badge.setStyleSheet(
                "background-color: #064E3B; color: #34D399; border: 1px solid #059669; padding: 6px 12px; border-radius: 6px; font-weight: bold;"
            )
            self.lbl_practice_feedback.setText(
                "Practice Status: Running. Perform a movement to view recognition scores."
            )
        else:
            self.btn_practice.setText("Start Practice Mode")
            self.practice_badge.setText("Mode: Studio Setup")
            self.practice_badge.setStyleSheet(
                "background-color: #1E293B; color: #94A3B8; border: 1px solid #475569; padding: 6px 12px; border-radius: 6px; font-weight: bold;"
            )
            self.lbl_practice_feedback.setText("Practice Status: Inactive.")
        self.practice_toggled.emit(self._in_practice)

    def update_sample_count(self, gesture_name: str, count: int) -> None:
        for row in self.gesture_rows:
            if row["name"] == gesture_name:
                row["sample_count"] = count
                row["count_label"].setText(f"{count} / 10 samples")
                row["progress"].setValue(min(count, 10))
                if count >= 5:
                    row["count_label"].setStyleSheet("color: #34D399; font-weight: bold;")
                break

    def update_practice_result(self, result: RecognitionResult) -> None:
        """Update live recognition scores in Practice Mode."""
        if not self._in_practice:
            return
        if result.accepted_candidate_or_none:
            score = result.label_scores.get(result.accepted_candidate_or_none, 0.0)
            self.lbl_practice_feedback.setText(
                f"Candidate: <b>{result.accepted_candidate_or_none}</b> (Similarity: {score:.2f}) [Simulated Output Only]"
            )
            self.lbl_practice_feedback.setStyleSheet("color: #38BDF8; font-size: 15px;")
        else:
            self.lbl_practice_feedback.setText(
                f"Status: Neutral / Unknown (Reason: {result.reject_reason})"
            )
            self.lbl_practice_feedback.setStyleSheet("color: #94A3B8; font-size: 14px;")

    def show_conflict_warning(
        self, title: str, description: str, recommendation: str, is_strong: bool
    ) -> None:
        """Display actionable gesture collision warning card."""
        self.conflict_box.setVisible(True)
        if is_strong:
            self.conflict_box.setStyleSheet(
                "QGroupBox { background-color: #450A0A; border: 2px solid #EF4444; border-radius: 8px; margin-top: 10px; font-weight: bold; color: #FCA5A5; }"
            )
            self.lbl_conflict_title.setText(f"🚨 STRONG CONFLICT: {title}")
            self.lbl_conflict_title.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #F87171;"
            )
        else:
            self.conflict_box.setStyleSheet(
                "QGroupBox { background-color: #451A03; border: 2px solid #F59E0B; border-radius: 8px; margin-top: 10px; font-weight: bold; color: #FDE68A; }"
            )
            self.lbl_conflict_title.setText(f"⚠️ POTENTIAL CONFLICT: {title}")
            self.lbl_conflict_title.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #FBBF24;"
            )

        self.lbl_conflict_desc.setText(description)
        self.lbl_conflict_recom.setText(f"<b>Recommendation:</b> {recommendation}")

    def clear_conflict_warning(self) -> None:
        """Hide collision warning card when gestures are distinct or reset."""
        self.conflict_box.setVisible(False)
        self.lbl_conflict_title.setText("")
        self.lbl_conflict_desc.setText("")
        self.lbl_conflict_recom.setText("")
