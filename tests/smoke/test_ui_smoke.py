"""Smoke tests for PySide6 user interface and accessibility properties."""

import os

import pytest
from PySide6.QtWidgets import QApplication

# Run headless Qt in test environment
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from morph.common.types import State
from morph.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_main_window_creation_and_routes(qapp):
    win = MainWindow()
    assert win is not None
    assert win.stack.count() == 9

    # Verify initial state is strictly PAUSED
    assert win._state == State.PAUSED
    assert "PAUSED" in win.btn_global_pause.text()

    # Verify route navigation
    routes = [
        "home",
        "onboarding",
        "studio",
        "board",
        "settings",
        "monitor",
        "lab",
        "session",
        "demo",
    ]
    for idx, r in enumerate(routes):
        win.navigate_to_route(r)
        assert win.stack.currentIndex() == idx

    # Accessibility properties check
    assert win.home_view.accessibleName() != ""
    assert win.onboarding_view.accessibleName() != ""
    assert win.studio_view.accessibleName() != ""
    assert win.board_view.accessibleName() != ""
    assert win.settings_view.accessibleName() != ""
    assert win.monitor_view.accessibleName() != ""
    assert win.lab_view.accessibleName() != ""
    assert win.eval_session_view.accessibleName() != ""
    assert win.demo_view.accessibleName() != ""

    # Test error recovery banner
    win.show_banner("Tracking lost: face occluded", "Retry", lambda: None, level="WARNING")
    assert not win.banner_widget.isHidden()
    assert "face occluded" in win.lbl_banner_text.text()
    win.hide_banner()
    assert win.banner_widget.isHidden()

    # Test global pause toggle
    win._toggle_global_pause()
    assert win._state == State.IDLE
    win.force_pause()
    assert win._state == State.PAUSED


def test_board_view_tile_navigation(qapp):
    win = MainWindow()
    board = win.board_view
    assert len(board.tiles) == 9

    initial_idx = board.current_index
    board.navigate_next()
    assert board.current_index == (initial_idx + 1) % 9

    board.navigate_previous()
    assert board.current_index == initial_idx

    spoken = board.select_current()
    assert spoken != ""
    assert spoken in board.spoken_banner.text()


def test_evaluation_session_view_lifecycle(qapp):
    win = MainWindow()
    view = win.eval_session_view

    # Verify participant ID and consent gating
    assert view.txt_participant_id.text().startswith("P-")
    assert view.btn_start_stage.isEnabled() is False

    # Grant consent
    view.chk_consent.setChecked(True)
    assert view.btn_start_stage.isEnabled() is True
    assert view.session is not None
    assert view.session.consented is True

    # Start stage and fire manual cue
    view._toggle_stage_run()
    assert view._stage_timer.isActive() is True
    assert view.btn_trigger_cue.isEnabled() is True

    view._on_fire_manual_cue()
    assert len(view.session.ground_truth_events) == 1
    assert view.table_events.rowCount() == 1

    # Discard / wipe session
    view._discard_session()
    assert view.session is None
    assert view.table_events.rowCount() == 0
    assert view.chk_consent.isChecked() is False
    assert view.btn_start_stage.isEnabled() is False


def test_demo_view_stages_and_preflight(qapp):
    win = MainWindow()
    demo = win.demo_view

    # Verify preflight diagnostics run
    results = demo.run_preflight_checks()
    assert "fsm" in results
    assert results["fsm"] is True
    assert "model" in results
    assert "db" in results
    assert "benchmark" in results

    # Verify 10 stages navigation
    assert len(demo.DEMO_STAGES) == 10
    assert demo._current_stage_idx == 0
    assert "Stage 1" in demo.lbl_stage_title.text()

    # Step through all 10 stages
    for step in range(1, 10):
        demo._next_stage()
        assert demo._current_stage_idx == step

    assert demo._current_stage_idx == 9
    assert demo.btn_next_step.isEnabled() is False

    # Previous and Reset
    demo._prev_stage()
    assert demo._current_stage_idx == 8
    demo._reset_demo()
    assert demo._current_stage_idx == 0
    assert "Stage 1" in demo.lbl_stage_title.text()
