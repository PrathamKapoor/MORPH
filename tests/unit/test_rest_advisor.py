"""Unit tests for RestAdvisor continuous usage monitoring (PRD Requirement D09)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from morph.common.types import State
from morph.ui.main_window import MainWindow
from morph.ui.rest_advisor import RestAdvisor


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance is initialized for GUI component testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_rest_advisor_initial_state(qapp):
    """Verify rest advisor initialization defaults and idle state."""
    advisor = RestAdvisor(threshold_seconds=1200.0, snooze_seconds=300.0)
    assert advisor.threshold_seconds == 1200.0
    assert advisor.snooze_seconds == 300.0
    assert advisor.active_duration_minutes == 0.0
    assert not advisor.is_alert_active


def test_rest_advisor_accumulation_and_trigger(qapp):
    """Verify active interaction time accumulates and triggers advisory signal."""
    advisor = RestAdvisor(threshold_seconds=100.0, snooze_seconds=20.0)
    received_minutes = []
    advisor.rest_suggested.connect(lambda m: received_minutes.append(m))

    advisor.set_system_active(True)
    advisor.record_activity_delta(45.0)
    assert advisor.active_duration_minutes == pytest.approx(45.0 / 60.0)
    assert len(received_minutes) == 0
    assert not advisor.is_alert_active

    # Advance past 100 seconds threshold
    advisor.record_activity_delta(60.0)
    assert len(received_minutes) == 1
    assert received_minutes[0] == 1  # 105s // 60 = 1 minute
    assert advisor.is_alert_active


def test_rest_advisor_paused_no_accumulation(qapp):
    """Verify no active time accumulates when system is paused."""
    advisor = RestAdvisor(threshold_seconds=100.0)
    advisor.set_system_active(False)
    advisor.record_activity_delta(500.0)
    assert advisor.active_duration_minutes == 0.0
    assert not advisor.is_alert_active


def test_rest_advisor_take_break(qapp):
    """Verify taking a break resets the continuous usage accumulator."""
    advisor = RestAdvisor(threshold_seconds=60.0)
    advisor.set_system_active(True)
    advisor.record_activity_delta(70.0)
    assert advisor.is_alert_active

    advisor.take_break()
    assert not advisor.is_alert_active
    assert advisor.active_duration_minutes == 0.0


def test_rest_advisor_dismiss_snooze(qapp):
    """Verify dismissing the advisory snoozes the alert before re-triggering."""
    advisor = RestAdvisor(threshold_seconds=100.0, snooze_seconds=25.0)
    received = []
    advisor.rest_suggested.connect(lambda m: received.append(m))

    advisor.set_system_active(True)
    advisor.record_activity_delta(110.0)
    assert len(received) == 1
    assert advisor.is_alert_active

    advisor.dismiss()
    assert not advisor.is_alert_active
    # snoozed accumulation should be 100 - 25 = 75.0
    assert advisor.active_duration_minutes == pytest.approx(75.0 / 60.0)

    # 15 seconds delta (total 90s) does not re-trigger
    advisor.record_activity_delta(15.0)
    assert len(received) == 1

    # Another 15 seconds delta (total 105s) re-triggers
    advisor.record_activity_delta(15.0)
    assert len(received) == 2


def test_main_window_rest_advisor_integration(qapp):
    """Verify MainWindow integrates RestAdvisor with accessible banner and take-break action."""
    window = MainWindow()
    assert hasattr(window, "rest_advisor")
    assert window.banner_widget.isHidden()

    # Activate system
    window.set_system_state(State.IDLE)
    assert window.rest_advisor._is_active

    # Advance beyond threshold
    window.rest_advisor.record_activity_delta(1250.0)
    assert not window.banner_widget.isHidden()
    assert "Rest Advisory" in window.lbl_banner_text.text()
    assert not window.btn_banner_action.isHidden()

    # User clicks "Take a Break"
    window.btn_banner_action.click()
    # System must pause and banner must hide
    assert window._state == State.PAUSED
    assert window.banner_widget.isHidden()
    assert window.rest_advisor.active_duration_minutes == 0.0

    window.close()
