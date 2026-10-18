"""Rest and fatigue advisor monitoring continuous active interaction time (PRD Requirement D09)."""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal


class RestAdvisor(QObject):
    """Monitors continuous active communication duration and emits non-medical fatigue advisories.

    PRD D09 Requirement:
    Non-medical, polite rest suggestions when continuous interaction exceeds duration threshold
    to prevent facial muscle strain or fatigue.
    """

    rest_suggested = Signal(int)  # active_duration_minutes
    rest_dismissed = Signal()

    def __init__(
        self,
        threshold_seconds: float = 1200.0,  # 20 minutes default
        snooze_seconds: float = 300.0,  # 5 minutes snooze
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.threshold_seconds = threshold_seconds
        self.snooze_seconds = snooze_seconds
        self._active_accumulated_seconds: float = 0.0
        self._is_active: bool = False
        self._last_tick_time: float | None = None
        self._alert_shown: bool = False

        self._timer = QTimer(self)
        self._timer.setInterval(1000)  # tick every 1 second
        self._timer.timeout.connect(self._on_tick)

    def start_monitoring(self) -> None:
        """Start the background 1-second monitoring timer."""
        self._last_tick_time = time.monotonic()
        self._timer.start()

    def stop_monitoring(self) -> None:
        """Stop monitoring timer."""
        self._timer.stop()
        self._last_tick_time = None

    def set_system_active(self, is_active: bool) -> None:
        """Update active state (True if tracking/interacting, False if paused/lost)."""
        now = time.monotonic()
        if self._is_active and self._last_tick_time is not None:
            self._active_accumulated_seconds += max(0.0, now - self._last_tick_time)
        self._is_active = is_active
        self._last_tick_time = now

    def record_activity_delta(self, seconds: float) -> None:
        """Directly advance active interaction time (useful for deterministic tests)."""
        if self._is_active:
            self._active_accumulated_seconds += max(0.0, seconds)
            self._check_threshold()

    def _on_tick(self) -> None:
        now = time.monotonic()
        if self._is_active and self._last_tick_time is not None:
            delta = max(0.0, now - self._last_tick_time)
            self._active_accumulated_seconds += delta
            self._check_threshold()
        self._last_tick_time = now

    def _check_threshold(self) -> None:
        if not self._alert_shown and self._active_accumulated_seconds >= self.threshold_seconds:
            self._alert_shown = True
            minutes = max(1, int(self._active_accumulated_seconds // 60))
            self.rest_suggested.emit(minutes)

    def take_break(self) -> None:
        """User accepted rest break: reset continuous active time and alert state."""
        self._active_accumulated_seconds = 0.0
        self._alert_shown = False
        self.rest_dismissed.emit()

    def dismiss(self) -> None:
        """User dismissed alert: snooze for snooze_seconds before alerting again."""
        self._active_accumulated_seconds = max(0.0, self.threshold_seconds - self.snooze_seconds)
        self._alert_shown = False
        self.rest_dismissed.emit()

    @property
    def active_duration_minutes(self) -> float:
        return self._active_accumulated_seconds / 60.0

    @property
    def is_alert_active(self) -> bool:
        return self._alert_shown
