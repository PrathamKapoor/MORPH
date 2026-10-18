"""Screen S6: Research Lab for A/B/C comparisons and metrics."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class LabView(QWidget):
    """S6 Research Lab: Consented evaluation, reproducible A/B/C replay, and real metrics."""

    start_session_requested = Signal(bool)  # consent granted
    run_abc_replay_requested = Signal()
    export_json_requested = Signal()
    export_csv_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Research Lab Screen")
        self.setAccessibleDescription(
            "Screen for running fair A/B/C algorithm comparisons, viewing real benchmark metrics, and exporting reproducible research data."
        )

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Header
        header = QVBoxLayout()
        title = QLabel("Research Lab: Controlled A/B/C Comparisons")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #38BDF8;")
        desc = QLabel(
            "Replays identical recorded feature sequences through Condition A (Fixed Thresholds), "
            "Condition B (Personalized Prototype), and Condition C (MORPH Intention Gate)."
        )
        desc.setStyleSheet("color: #94A3B8; font-size: 14px;")
        header.addWidget(title)
        header.addWidget(desc)
        layout.addLayout(header)

        # Consent & Recording Controls Card
        consent_group = QGroupBox("Informed Consent & Recording (F07 / E02)")
        c_layout = QVBoxLayout(consent_group)

        self.chk_consent = QCheckBox(
            "I grant informed consent to record anonymized facial landmark feature sequences locally for accessibility research. (No raw video is ever stored)."
        )
        self.chk_consent.setStyleSheet("font-size: 14px; color: #E2E8F0; padding: 4px;")
        c_layout.addWidget(self.chk_consent)

        btn_row = QHBoxLayout()
        self.btn_session = QPushButton("Record Consented Evaluation Session")
        self.btn_session.clicked.connect(self._toggle_session_recording)
        self.lbl_session_status = QLabel("Session: Inactive")
        self.lbl_session_status.setStyleSheet("color: #94A3B8; font-weight: bold;")
        btn_row.addWidget(self.btn_session)
        btn_row.addWidget(self.lbl_session_status)
        btn_row.addStretch()

        self.btn_replay = QPushButton("▶ Run A/B/C Replay Benchmark")
        self.btn_replay.setObjectName("activate_btn_paused")
        self.btn_replay.clicked.connect(self.run_abc_replay_requested.emit)
        btn_row.addWidget(self.btn_replay)

        c_layout.addLayout(btn_row)
        layout.addWidget(consent_group)

        # A/B/C Comparison Results Table
        table_group = QGroupBox("Controlled Replay Comparison (Condition A vs B vs C)")
        t_layout = QVBoxLayout(table_group)

        self.lbl_table_source = QLabel(
            "Dataset Source: No replay executed yet. Click 'Run A/B/C Replay Benchmark'."
        )
        self.lbl_table_source.setStyleSheet("color: #FBBF24; font-size: 13px; font-style: italic;")
        t_layout.addWidget(self.lbl_table_source)

        self.table = QTableWidget(6, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Condition",
                "Unintended Dispatches",
                "Non-Cmd Hours",
                "FA / Hour",
                "Recall (%)",
                "Precision (%)",
                "Latency P95 (ms)",
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(
            "QTableWidget { background-color: #0F172A; gridline-color: #334155; font-size: 14px; }"
            "QHeaderView::section { background-color: #1E293B; color: #38BDF8; font-weight: bold; padding: 8px; border: 1px solid #334155; }"
        )

        conditions = [
            ("A: Fixed Thresholds (Debounced)", "0", "0.00h", "N/A", "0.0%", "0.0%", "N/A"),
            ("B: Personalized Prototype (Debounced)", "0", "0.00h", "N/A", "0.0%", "0.0%", "N/A"),
            ("C: MORPH 2.0 (Intention Gated)", "0", "0.00h", "N/A", "0.0%", "0.0%", "N/A"),
            ("Ablation 1: No Hold Time (Hold=0ms)", "0", "0.00h", "N/A", "0.0%", "0.0%", "N/A"),
            (
                "Ablation 2: No Release Dwell (Release=0ms)",
                "0",
                "0.00h",
                "N/A",
                "0.0%",
                "0.0%",
                "N/A",
            ),
            ("Ablation 3: No Margin (Margin=0.0)", "0", "0.00h", "N/A", "0.0%", "0.0%", "N/A"),
        ]
        for row, vals in enumerate(conditions):
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter if col > 0 else Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(row, col, item)

        t_layout.addWidget(self.table)
        layout.addWidget(table_group)

        # Export Actions
        export_row = QHBoxLayout()
        lbl_export = QLabel("Export Reproducible Benchmark Evidence:")
        lbl_export.setStyleSheet("color: #94A3B8; font-weight: 600;")
        export_row.addWidget(lbl_export)

        btn_json = QPushButton("Export Benchmark JSON")
        btn_json.clicked.connect(self.export_json_requested.emit)
        btn_csv = QPushButton("Export Events CSV")
        btn_csv.clicked.connect(self.export_csv_requested.emit)

        export_row.addWidget(btn_json)
        export_row.addWidget(btn_csv)
        export_row.addStretch()
        layout.addLayout(export_row)

    def _toggle_session_recording(self) -> None:
        consent = self.chk_consent.isChecked()
        if not consent:
            self.lbl_session_status.setText("Session Blocked: Informed Consent Checkbox Required!")
            self.lbl_session_status.setStyleSheet("color: #F87171; font-weight: bold;")
            return
        self.start_session_requested.emit(True)
        self.lbl_session_status.setText("Session: RECORDING (Consented Landmark Stream)")
        self.lbl_session_status.setStyleSheet("color: #34D399; font-weight: bold;")

    def update_metrics(
        self,
        results_a: dict,
        results_b: dict,
        results_c: dict,
        ablations: dict | None = None,
        is_synthetic: bool = False,
    ) -> None:
        """Populate table with actual computed metrics from replay engine."""
        data = [
            ("A: Fixed Thresholds (Debounced)", results_a),
            ("B: Personalized Prototype (Debounced)", results_b),
            ("C: MORPH 2.0 (Intention Gated)", results_c),
        ]

        if ablations:
            data.extend(
                [
                    ("Ablation 1: No Hold Time (Hold=0ms)", ablations.get("no_hold", {})),
                    ("Ablation 2: No Release Dwell (Release=0ms)", ablations.get("no_release", {})),
                    ("Ablation 3: No Margin (Margin=0.0)", ablations.get("no_margin", {})),
                ]
            )

        for row, (name, res) in enumerate(data):
            if row >= self.table.rowCount():
                break
            self.table.item(row, 0).setText(name)
            self.table.item(row, 1).setText(str(res.get("unintended_dispatches", 0)))
            self.table.item(row, 2).setText(f"{res.get('non_command_hours', 0.0):.3f}h")

            fa_hr = res.get("false_activations_per_hour")
            self.table.item(row, 3).setText("N/A" if fa_hr is None else f"{fa_hr:.2f}")

            rec = res.get("recall")
            self.table.item(row, 4).setText("N/A" if rec is None else f"{rec * 100:.1f}%")

            prec = res.get("precision")
            self.table.item(row, 5).setText("N/A" if prec is None else f"{prec * 100:.1f}%")

            p95 = res.get("latency_p95_ms")
            self.table.item(row, 6).setText("N/A" if p95 is None else f"{p95:.1f} ms")

        source_label = (
            "Synthetic Test Fixture Replay (Not human performance)"
            if is_synthetic
            else "Recorded Consented Participant Session"
        )
        self.lbl_table_source.setText(f"Dataset Source: {source_label}")
        self.lbl_table_source.setStyleSheet("color: #34D399; font-size: 13px; font-weight: bold;")
