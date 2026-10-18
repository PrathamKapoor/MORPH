"""Screen S1: Home View for MORPH 2.0."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from morph.common.types import TrackingHealth


class HomeView(QWidget):
    """S1 Home Screen: Profile selection, status summary, and large activation toggle."""

    navigate_requested = Signal(str)  # route name
    activation_toggled = Signal(bool)  # True = LIVE, False = PAUSED
    profile_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Home Screen")
        self.setAccessibleDescription(
            "Main dashboard displaying tracking status, profile selection, and application control."
        )

        self._is_active = False
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        # 1. Header Banner
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("MORPH 2.0")
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: #38BDF8;")
        subtitle = QLabel(
            "Accessible Facial Gesture AAC System with Deterministic Intention Gating"
        )
        subtitle.setStyleSheet("font-size: 15px; color: #94A3B8;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        self.status_badge = QLabel("⏸ SYSTEM PAUSED (Safe State)")
        self.status_badge.setObjectName("header_status_paused")
        self.status_badge.setAccessibleName("System State")
        self.status_badge.setAccessibleDescription(
            "Current state is Paused. No commands will be emitted."
        )
        header.addWidget(self.status_badge)
        layout.addLayout(header)

        # 2. Main Action Card
        card = QFrame()
        card.setStyleSheet(
            "background-color: #1A1F29; border: 2px solid #2A3342; border-radius: 12px; padding: 24px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)

        # Profile selection
        prof_layout = QHBoxLayout()
        prof_label = QLabel("Active User Profile:")
        prof_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.profile_combo = QComboBox()
        self.profile_combo.setAccessibleName("User Profile Selector")
        self.profile_combo.setAccessibleDescription(
            "Select the active gesture calibration profile."
        )
        self.profile_combo.setStyleSheet(
            "QComboBox { background-color: #0F172A; border: 2px solid #334155; border-radius: 6px; padding: 8px 16px; color: #F8FAFC; font-size: 15px; min-width: 220px; }"
            "QComboBox::drop-down { border: none; }"
        )
        self.profile_combo.addItem("Default User Profile (Active)")
        self.profile_combo.currentIndexChanged.connect(self._on_profile_index_changed)
        prof_layout.addWidget(prof_label)
        prof_layout.addWidget(self.profile_combo)
        prof_layout.addStretch()
        card_layout.addLayout(prof_layout)

        # Large Activate / Pause Toggle Button
        self.toggle_btn = QPushButton("▶ ACTIVATE MORPH (Start Live Tracking)")
        self.toggle_btn.setObjectName("activate_btn_paused")
        self.toggle_btn.setAccessibleName("Activate or Pause Live Tracking Toggle")
        self.toggle_btn.setAccessibleDescription(
            "Press to start or pause live gesture tracking. Keyboard shortcut: Spacebar."
        )
        self.toggle_btn.setMinimumHeight(64)
        self.toggle_btn.clicked.connect(self._on_toggle_clicked)
        card_layout.addWidget(self.toggle_btn)

        # Safety disclaimer
        safety_note = QLabel(
            "⚠ Safety Invariant: MORPH always boots in the PAUSED state. Commands are suppressed during head movement until intention hold is verified."
        )
        safety_note.setStyleSheet("font-size: 13px; color: #64748B; font-style: italic;")
        safety_note.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(safety_note)

        layout.addWidget(card)

        # 3. Status Overview & Sensor Telemetry
        status_group = QGroupBox("Live Sensor & System Health")
        grid = QGridLayout(status_group)
        grid.setSpacing(12)

        self.lbl_camera = QLabel("Camera Sensor: Probing...")
        self.lbl_face = QLabel("Face Tracking: Searching for face...")
        self.lbl_fps = QLabel("Processed FPS: 0.0 FPS")
        self.lbl_drops = QLabel("Queue Status: 0 drops / 0 stale")

        for lbl in (self.lbl_camera, self.lbl_face, self.lbl_fps, self.lbl_drops):
            lbl.setStyleSheet("font-size: 14px; color: #CBD5E1; padding: 4px;")

        grid.addWidget(self.lbl_camera, 0, 0)
        grid.addWidget(self.lbl_face, 0, 1)
        grid.addWidget(self.lbl_fps, 1, 0)
        grid.addWidget(self.lbl_drops, 1, 1)
        layout.addWidget(status_group)

        # 4. Navigation Quick Links
        nav_group = QGroupBox("Navigation & Modules")
        nav_layout = QHBoxLayout(nav_group)
        nav_layout.setSpacing(12)

        screens = [
            (
                "onboarding",
                "🚀 Guided Onboarding Wizard",
                "Step-by-step first launch setup and calibration tutorial",
            ),
            (
                "studio",
                "🎨 Gesture Studio",
                "Calibrate neutral baseline and train up to 3 gestures",
            ),
            ("board", "💬 Communication Board", "High-contrast phrase grid with offline speech"),
            (
                "settings",
                "⚙ Recognition Settings",
                "Tune hold, cooldown, and similarity thresholds",
            ),
            ("monitor", "📊 Reliability Monitor", "Live FPS, queue drops, and transition history"),
            ("lab", "🧪 Research Lab", "A/B/C baseline comparison and metric exports"),
        ]

        for route, text, desc in screens:
            btn = QPushButton(text)
            btn.setAccessibleName(text)
            btn.setAccessibleDescription(desc)
            btn.setToolTip(desc)
            btn.setMinimumHeight(52)
            btn.clicked.connect(lambda _, r=route: self.navigate_requested.emit(r))
            nav_layout.addWidget(btn)

        layout.addWidget(nav_group)
        layout.addStretch()

    def _on_toggle_clicked(self) -> None:
        self.set_active_state(not self._is_active)
        self.activation_toggled.emit(self._is_active)

    def _on_profile_index_changed(self, index: int) -> None:
        p_uuid = self.profile_combo.itemData(index)
        if p_uuid:
            self.profile_changed.emit(str(p_uuid))
        else:
            self.profile_changed.emit(self.profile_combo.currentText())

    def set_profiles(self, profiles: list[dict[str, Any]], active_uuid: str) -> None:
        """Populate profile selector combo with available profiles."""
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        selected_idx = 0
        for idx, p in enumerate(profiles):
            is_active = p.get("profile_uuid") == active_uuid
            name = p.get("name", "Unknown Profile")
            label = f"{name} ({'Active' if is_active else 'Available'})"
            self.profile_combo.addItem(label, userData=p.get("profile_uuid"))
            if is_active:
                selected_idx = idx
        if profiles:
            self.profile_combo.setCurrentIndex(selected_idx)
        self.profile_combo.blockSignals(False)

    def set_active_state(self, active: bool) -> None:
        self._is_active = active
        if active:
            self.toggle_btn.setText("⏸ PAUSE MORPH (Stop Live Tracking)")
            self.toggle_btn.setObjectName("activate_btn_active")
            self.status_badge.setText("● LIVE TRACKING ACTIVE")
            self.status_badge.setObjectName("header_status_active")
            self.status_badge.setAccessibleDescription(
                "Live tracking is active. Deliberate gestures will trigger actions."
            )
        else:
            self.toggle_btn.setText("▶ ACTIVATE MORPH (Start Live Tracking)")
            self.toggle_btn.setObjectName("activate_btn_paused")
            self.status_badge.setText("⏸ SYSTEM PAUSED (Safe State)")
            self.status_badge.setObjectName("header_status_paused")
            self.status_badge.setAccessibleDescription(
                "Current state is Paused. No commands will be emitted."
            )

        # Re-apply stylesheet to update badge and button colors
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def update_health(self, health: TrackingHealth) -> None:
        """Update live telemetry metrics displayed on home screen."""
        sm_text = (
            health.source_mode.value
            if hasattr(health.source_mode, "value")
            else str(health.source_mode)
        )
        if health.camera_connected:
            self.lbl_camera.setText(f"Camera Sensor: Connected [{sm_text}]")
        else:
            self.lbl_camera.setText(f"Camera Sensor: Blocked [{sm_text}]")

        if health.face_count == 1:
            self.lbl_face.setText("Face Tracking: 1 Face Locked (Valid)")
            self.lbl_face.setStyleSheet("color: #34D399; font-size: 14px;")
        elif health.face_count == 0:
            self.lbl_face.setText("Face Tracking: No Face Detected (Safe Hold)")
            self.lbl_face.setStyleSheet("color: #F87171; font-size: 14px;")
        else:
            self.lbl_face.setText(
                f"Face Tracking: Multiple Faces ({health.face_count}) - Suppressed"
            )
            self.lbl_face.setStyleSheet("color: #F87171; font-size: 14px;")

        self.lbl_fps.setText(
            f"Processed: {health.processed_fps:.1f} FPS | Capture: {health.capture_fps:.1f} FPS"
        )
        self.lbl_drops.setText(
            f"Queue: {health.dropped_frames} dropped | {health.stale_frames} stale"
        )
