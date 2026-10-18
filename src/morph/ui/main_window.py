"""Main application window for MORPH 2.0."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from morph.common.types import State, TrackingHealth
from morph.ui.board_view import BoardView
from morph.ui.demo_view import DemoView
from morph.ui.evaluation_session_view import EvaluationSessionView
from morph.ui.home_view import HomeView
from morph.ui.lab_view import LabView
from morph.ui.monitor_view import MonitorView
from morph.ui.onboarding_view import OnboardingView
from morph.ui.rest_advisor import RestAdvisor
from morph.ui.settings_view import SettingsView
from morph.ui.studio_view import StudioView
from morph.ui.styles import THEME_DARK


class MainWindow(QMainWindow):
    """Accessible main window for MORPH 2.0 with 6 views."""

    pause_requested = Signal()
    resume_requested = Signal()
    profile_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MORPH 2.0 — Accessible Facial Gesture AAC System")
        self.resize(1180, 820)
        self.setMinimumSize(960, 680)
        self.setStyleSheet(THEME_DARK)

        self._state = State.PAUSED
        self._init_ui()
        self._setup_shortcuts()
        self._setup_rest_advisor()

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top Navigation Bar
        nav_bar = QWidget()
        nav_bar.setStyleSheet("background-color: #1A1F29; border-bottom: 2px solid #2D3748;")
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(16, 8, 16, 8)

        app_title = QLabel("MORPH 2.0")
        app_title.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #38BDF8; margin-right: 16px;"
        )
        nav_layout.addWidget(app_title)

        # Tab Navigation Bar
        self.tab_bar = QTabBar()
        self.tab_bar.setAccessibleName("Main Module Navigation Tabs")
        self.tab_bar.addTab("Home")
        self.tab_bar.addTab("Onboarding")
        self.tab_bar.addTab("Studio")
        self.tab_bar.addTab("Board")
        self.tab_bar.addTab("Settings")
        self.tab_bar.addTab("Monitor")
        self.tab_bar.addTab("Research")
        self.tab_bar.addTab("Session")
        self.tab_bar.addTab("Demo")
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        nav_layout.addWidget(self.tab_bar)
        nav_layout.addStretch()

        # Global Safe Pause / Resume Button in Top Right
        self.btn_global_pause = QPushButton("⏸ PAUSED (Press Space)")
        self.btn_global_pause.setObjectName("activate_btn_paused")
        self.btn_global_pause.setAccessibleName("Global Pause State and Toggle")
        self.btn_global_pause.setAccessibleDescription("Toggles between Paused and Live tracking.")
        self.btn_global_pause.clicked.connect(self._toggle_global_pause)
        nav_layout.addWidget(self.btn_global_pause)

        main_layout.addWidget(nav_bar)

        # Accessible Alert & Error Recovery Banner (M5.5)
        self.banner_widget = QWidget()
        self.banner_widget.setVisible(False)
        self.banner_widget.setAccessibleName("System Alert Notification Banner")
        b_layout = QHBoxLayout(self.banner_widget)
        b_layout.setContentsMargins(24, 8, 24, 8)
        self.lbl_banner_text = QLabel("")
        self.lbl_banner_text.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
        self.btn_banner_action = QPushButton("")
        self.btn_banner_action.setVisible(False)
        self.btn_banner_dismiss = QPushButton("✕ Dismiss")
        self._banner_action_callback = None
        self.btn_banner_action.clicked.connect(self._on_banner_action_clicked)
        self.btn_banner_dismiss.clicked.connect(self.hide_banner)
        b_layout.addWidget(self.lbl_banner_text)
        b_layout.addStretch()
        b_layout.addWidget(self.btn_banner_action)
        b_layout.addWidget(self.btn_banner_dismiss)
        main_layout.addWidget(self.banner_widget)

        # Stacked Views Widget
        self.stack = QStackedWidget()
        self.home_view = HomeView()
        self.onboarding_view = OnboardingView()
        self.studio_view = StudioView()
        self.board_view = BoardView()
        self.settings_view = SettingsView()
        self.monitor_view = MonitorView()
        self.lab_view = LabView()
        self.eval_session_view = EvaluationSessionView()
        self.demo_view = DemoView()

        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.onboarding_view)
        self.stack.addWidget(self.studio_view)
        self.stack.addWidget(self.board_view)
        self.stack.addWidget(self.settings_view)
        self.stack.addWidget(self.monitor_view)
        self.stack.addWidget(self.lab_view)
        self.stack.addWidget(self.eval_session_view)
        self.stack.addWidget(self.demo_view)

        main_layout.addWidget(self.stack)

        # Wire navigation requests from Home View buttons
        self.home_view.navigate_requested.connect(self.navigate_to_route)
        self.home_view.activation_toggled.connect(self._on_home_activation_toggled)
        self.home_view.profile_changed.connect(self.profile_changed.emit)
        self.onboarding_view.onboarding_completed.connect(lambda: self.navigate_to_route("board"))
        self.board_view.pause_toggled.connect(self._toggle_global_pause)

    def _on_banner_action_clicked(self) -> None:
        if self._banner_action_callback:
            self._banner_action_callback()

    def show_banner(
        self,
        message: str,
        action_text: str | None = None,
        action_callback=None,
        level: str = "ERROR",
    ) -> None:
        """Display an accessible high-contrast recovery notification banner."""
        self.lbl_banner_text.setText(message)
        self._banner_action_callback = action_callback
        if level == "ERROR":
            self.banner_widget.setStyleSheet(
                "background-color: #7F1D1D; border-bottom: 2px solid #EF4444; padding: 6px;"
            )
        elif level == "WARNING":
            self.banner_widget.setStyleSheet(
                "background-color: #78350F; border-bottom: 2px solid #F59E0B; padding: 6px;"
            )
        else:
            self.banner_widget.setStyleSheet(
                "background-color: #064E3B; border-bottom: 2px solid #10B981; padding: 6px;"
            )

        if action_text and action_callback:
            self.btn_banner_action.setText(action_text)
            self.btn_banner_action.setVisible(True)
        else:
            self.btn_banner_action.setVisible(False)

        self.banner_widget.setVisible(True)

    def hide_banner(self) -> None:
        """Dismiss the recovery banner."""
        self.banner_widget.setVisible(False)
        self.lbl_banner_text.setText("")
        if hasattr(self, "rest_advisor") and self.rest_advisor.is_alert_active:
            self.rest_advisor.dismiss()

    def _setup_rest_advisor(self) -> None:
        """Initialize continuous session rest advisor (PRD D09)."""
        self.rest_advisor = RestAdvisor(threshold_seconds=1200.0, snooze_seconds=300.0, parent=self)
        self.rest_advisor.rest_suggested.connect(self._on_rest_suggested)
        self.rest_advisor.start_monitoring()

    def _on_rest_suggested(self, minutes: int) -> None:
        """Handle continuous interaction rest threshold notification."""

        def take_break():
            self.force_pause()
            self.rest_advisor.take_break()
            self.hide_banner()

        self.show_banner(
            f"Rest Advisory: Continuous interaction for {minutes} min. "
            "Regular breaks help prevent muscle fatigue.",
            action_text="⏸ Take a Break",
            action_callback=take_break,
            level="WARNING",
        )

    def _setup_shortcuts(self) -> None:
        """Global keyboard access: Spacebar or Escape instantly toggles pause."""
        self.shortcut_space = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.shortcut_space.activated.connect(self._toggle_global_pause)

        self.shortcut_esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.shortcut_esc.activated.connect(self.force_pause)

    def _on_tab_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)

    def navigate_to_route(self, route_name: str) -> None:
        route_map = {
            "home": 0,
            "onboarding": 1,
            "studio": 2,
            "board": 3,
            "settings": 4,
            "monitor": 5,
            "lab": 6,
            "research": 6,
            "session": 7,
            "evaluation": 7,
            "eval_session": 7,
            "demo": 8,
            "demonstration": 8,
        }
        idx = route_map.get(route_name.lower(), 0)
        self.tab_bar.setCurrentIndex(idx)

    def set_no_camera_mode(self, enabled: bool = True) -> None:
        """Configure main window and sub-views for no-camera demonstration mode."""
        self._no_camera_mode = enabled
        self.home_view.set_no_camera_mode(enabled)

    def _toggle_global_pause(self) -> None:
        if getattr(self, "_no_camera_mode", False):
            self.force_pause()
            return
        if self._state == State.PAUSED:
            self.set_system_state(State.IDLE)
            self.resume_requested.emit()
        else:
            self.force_pause()

    def force_pause(self) -> None:
        """Unconditional fail-safe pause."""
        self.set_system_state(State.PAUSED)
        self.pause_requested.emit()

    def _on_home_activation_toggled(self, active: bool) -> None:
        if getattr(self, "_no_camera_mode", False):
            self.force_pause()
            return
        if active:
            self.set_system_state(State.IDLE)
            self.resume_requested.emit()
        else:
            self.force_pause()

    def set_system_state(self, state: State) -> None:
        self._state = state
        is_active = state != State.PAUSED and state != State.TRACKING_LOST
        self.home_view.set_active_state(is_active)
        if hasattr(self, "rest_advisor"):
            self.rest_advisor.set_system_active(is_active)

        if state == State.PAUSED:
            self.btn_global_pause.setText("⏸ PAUSED (Press Space)")
            self.btn_global_pause.setObjectName("activate_btn_paused")
        elif state == State.TRACKING_LOST:
            self.btn_global_pause.setText("⚠ TRACKING LOST (Face Occluded)")
            self.btn_global_pause.setObjectName("activate_btn_active")
        else:
            self.btn_global_pause.setText("● ACTIVE (Press Space to Pause)")
            self.btn_global_pause.setObjectName("activate_btn_active")

        self.btn_global_pause.style().unpolish(self.btn_global_pause)
        self.btn_global_pause.style().polish(self.btn_global_pause)

    def update_health(self, health: TrackingHealth) -> None:
        """Distribute health telemetry to Home and Monitor views."""
        self.home_view.update_health(health)
        self.monitor_view.update_health(health)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Ensure clean shutdown on window close."""
        if hasattr(self, "rest_advisor"):
            self.rest_advisor.stop_monitoring()
        self.force_pause()
        event.accept()
