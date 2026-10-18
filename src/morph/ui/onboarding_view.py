"""Screen S0 / Onboarding: Accessible first-launch guided setup wizard (M5.5).

Guides new users through:
1. System Overview & Privacy Guarantee (100% offline, volatile memory frames).
2. Camera & Posture Placement.
3. Guided Resting Neutral Calibration (3-second countdown).
4. Personalized 3-Gesture Training with conflict detection.
5. Non-Executing Practice Sandbox.
6. Safe Launch into Communication Board (starts in PAUSED state).
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class OnboardingView(QWidget):
    """Step-by-step onboarding wizard for accessible first-launch onboarding."""

    onboarding_completed = Signal()
    request_neutral_calibration = Signal()
    request_capture_sample = Signal(str)  # gesture name
    request_practice_mode = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Onboarding Wizard")
        self.setAccessibleDescription(
            "Guided step-by-step setup wizard for first-time MORPH 2.0 calibration."
        )

        self._current_step = 0
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(20)

        # Wizard Step Header
        self.step_label = QLabel("Step 1 of 5: Welcome to MORPH 2.0")
        self.step_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #38BDF8; letter-spacing: 1px;"
        )
        layout.addWidget(self.step_label)

        # Wizard Stack
        self.wizard_stack = QStackedWidget()

        # Page 1: Welcome & Safety Invariants
        p1 = QWidget()
        l1 = QVBoxLayout(p1)
        l1.setSpacing(16)
        t1 = QLabel("Accessible Facial Movement AAC with Deterministic Intention Gating")
        t1.setStyleSheet("font-size: 22px; font-weight: bold; color: #F8FAFC;")
        d1 = QLabel(
            "MORPH 2.0 enables reliable computer interaction using up to three subtle, personally "
            "comfortable facial movements.\n\n"
            "Key Safety & Privacy Guarantees:\n"
            "• 100% Local & Offline: All computer vision and speech run locally on your device.\n"
            "• Transient Memory Only: Video frames exist strictly in volatile RAM and are never written to disk.\n"
            "• Deterministic Intention Gating: Accidental commands are prevented by requiring sustained holds "
            "and continuous neutral release before rearming.\n"
            "• Fail-Closed Safety: The system always starts in a PAUSED state to prevent unintended activations."
        )
        d1.setWordWrap(True)
        d1.setStyleSheet("font-size: 15px; color: #CBD5E1; line-height: 1.6;")
        l1.addWidget(t1)
        l1.addWidget(d1)
        l1.addStretch()
        self.wizard_stack.addWidget(p1)

        # Page 2: Camera & Seating Alignment
        p2 = QWidget()
        l2 = QVBoxLayout(p2)
        l2.setSpacing(16)
        t2 = QLabel("Camera Placement & Posture Alignment")
        t2.setStyleSheet("font-size: 22px; font-weight: bold; color: #F8FAFC;")
        d2 = QLabel(
            "Positioning Instructions:\n"
            "1. Distance: Sit approximately 50 to 70 cm (arm's length) from the webcam.\n"
            "2. Angle: Place the camera at eye level, facing you directly.\n"
            "3. Lighting: Ensure your face is evenly illuminated. Avoid bright backlights or windows behind you.\n"
            "4. Multi-Face Protection: Ensure only one face is visible in the camera frame.\n\n"
            "When ready, proceed to calibrate your resting posture."
        )
        d2.setWordWrap(True)
        d2.setStyleSheet("font-size: 15px; color: #CBD5E1; line-height: 1.6;")
        l2.addWidget(t2)
        l2.addWidget(d2)
        l2.addStretch()
        self.wizard_stack.addWidget(p2)

        # Page 3: Resting Neutral Calibration
        p3 = QWidget()
        l3 = QVBoxLayout(p3)
        l3.setSpacing(16)
        t3 = QLabel("Calibrate Resting Neutral Posture")
        t3.setStyleSheet("font-size: 22px; font-weight: bold; color: #F8FAFC;")
        d3 = QLabel(
            "Resting neutral is your natural baseline posture when you are not trying to execute a command.\n\n"
            "Instructions:\n"
            "• Relax your facial muscles, jaw, and eyebrows completely.\n"
            "• Look naturally at the screen.\n"
            "• Click 'Calibrate Neutral Rest (3s)' and hold completely relaxed until the countdown finishes."
        )
        d3.setWordWrap(True)
        d3.setStyleSheet("font-size: 15px; color: #CBD5E1; line-height: 1.6;")
        self.btn_calib = QPushButton("Calibrate Neutral Rest (3s)")
        self.btn_calib.setObjectName("activate_btn_paused")
        self.btn_calib.clicked.connect(self.request_neutral_calibration.emit)
        self.calib_status = QLabel("Status: Ready to calibrate")
        self.calib_status.setStyleSheet("color: #FBBF24; font-size: 14px; font-weight: bold;")
        l3.addWidget(t3)
        l3.addWidget(d3)
        l3.addWidget(self.btn_calib)
        l3.addWidget(self.calib_status)
        l3.addStretch()
        self.wizard_stack.addWidget(p3)

        # Page 4: 3-Gesture Training Overview
        p4 = QWidget()
        l4 = QVBoxLayout(p4)
        l4.setSpacing(16)
        t4 = QLabel("Train Your 3 Personally Comfortable Movements")
        t4.setStyleSheet("font-size: 22px; font-weight: bold; color: #F8FAFC;")
        d4 = QLabel(
            "Default recommended gesture vocabulary:\n"
            "1. Brow Raise -> Navigates to Next tile\n"
            "2. Smile / Lip Corner Pull -> Selects & Speaks the focused tile\n"
            "3. Mouth Open / Chin Drop -> Navigates to Previous tile\n\n"
            "You can record 5 to 10 samples for each movement in the Gesture Studio.\n"
            "The system will automatically alert you if two gestures are too similar."
        )
        d4.setWordWrap(True)
        d4.setStyleSheet("font-size: 15px; color: #CBD5E1; line-height: 1.6;")
        l4.addWidget(t4)
        l4.addWidget(d4)
        l4.addStretch()
        self.wizard_stack.addWidget(p4)

        # Page 5: Safe Launch into Communication Board
        p5 = QWidget()
        l5 = QVBoxLayout(p5)
        l5.setSpacing(16)
        t5 = QLabel("Setup Complete — Safe Launch")
        t5.setStyleSheet("font-size: 22px; font-weight: bold; color: #34D399;")
        d5 = QLabel(
            "You are ready to use the MORPH 2.0 Communication Board!\n\n"
            "Remember:\n"
            "• Fail-Closed: The application launches in the PAUSED state.\n"
            "• Press Spacebar or click the top-right button to Resume.\n"
            "• Hold an intended gesture for ~250ms to activate a tile.\n"
            "• Return to neutral rest to release and prepare for the next command.\n"
            "• Press Spacebar or Escape at any time to pause instantly."
        )
        d5.setWordWrap(True)
        d5.setStyleSheet("font-size: 15px; color: #CBD5E1; line-height: 1.6;")
        l5.addWidget(t5)
        l5.addWidget(d5)
        l5.addStretch()
        self.wizard_stack.addWidget(p5)

        layout.addWidget(self.wizard_stack)

        # Navigation Buttons (Back, Next, Finish)
        nav_buttons = QHBoxLayout()
        self.btn_back = QPushButton("← Back")
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self._prev_step)

        self.btn_next = QPushButton("Next →")
        self.btn_next.clicked.connect(self._next_step)

        nav_buttons.addWidget(self.btn_back)
        nav_buttons.addStretch()
        nav_buttons.addWidget(self.btn_next)
        layout.addLayout(nav_buttons)

    def _next_step(self) -> None:
        if self._current_step < self.wizard_stack.count() - 1:
            self._current_step += 1
            self.wizard_stack.setCurrentIndex(self._current_step)
            self._update_nav()
        else:
            self.onboarding_completed.emit()

    def _prev_step(self) -> None:
        if self._current_step > 0:
            self._current_step -= 1
            self.wizard_stack.setCurrentIndex(self._current_step)
            self._update_nav()

    def _update_nav(self) -> None:
        total = self.wizard_stack.count()
        self.step_label.setText(
            f"Step {self._current_step + 1} of {total}: {self._get_step_title()}"
        )
        self.btn_back.setEnabled(self._current_step > 0)
        if self._current_step == total - 1:
            self.btn_next.setText("Launch Communication Board 🚀")
            self.btn_next.setStyleSheet(
                "background-color: #065F46; border: 2px solid #10B981; font-weight: bold;"
            )
        else:
            self.btn_next.setText("Next →")
            self.btn_next.setStyleSheet("")

    def _get_step_title(self) -> str:
        titles = [
            "Welcome & Safety Guarantees",
            "Camera & Posture Alignment",
            "Resting Neutral Calibration",
            "3-Gesture Training Overview",
            "Safe Launch into Board",
        ]
        return titles[self._current_step] if self._current_step < len(titles) else "Setup"
