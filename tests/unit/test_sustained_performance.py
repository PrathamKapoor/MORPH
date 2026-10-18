"""Unit tests for sustained performance instrumentation, multi-stage telemetry, and percentiles (Milestone M8.1)."""

from __future__ import annotations

from morph.capture.instrumentation import (
    PipelineStageTelemetry,
    SustainedPerformanceTracker,
    compute_percentiles,
)
from scripts.measure_sustained_performance import run_sustained_benchmark


def test_pipeline_stage_telemetry_properties():
    """Verify PipelineStageTelemetry calculates stage deltas in milliseconds correctly."""
    # 1 ms = 1_000_000 ns
    t = PipelineStageTelemetry(
        frame_id=1,
        t_read_start_ns=100_000_000,
        t_capture_ns=182_000_000,  # 82 ms camera read
        t_queue_insert_ns=182_100_000,
        t_queue_remove_ns=182_200_000,  # 0.1 ms queue dwell
        t_infer_start_ns=182_300_000,
        t_infer_end_ns=198_300_000,  # 16 ms inference
        t_features_start_ns=198_400_000,
        t_features_end_ns=198_500_000,  # 0.1 ms features
        t_recog_start_ns=198_550_000,
        t_recog_end_ns=198_600_000,  # 0.05 ms recognition
        t_intent_start_ns=198_650_000,
        t_intent_end_ns=198_700_000,  # 0.05 ms intent
        t_dispatch_start_ns=198_750_000,
        t_dispatch_end_ns=198_760_000,  # 0.01 ms dispatch
        t_ui_ack_ns=199_000_000,  # UI presentation
    )

    assert round(t.camera_read_ms, 2) == 82.0
    assert round(t.queue_dwell_ms, 2) == 0.1
    assert round(t.infer_ms, 2) == 16.0
    assert round(t.features_ms, 2) == 0.1
    assert round(t.recog_ms, 3) == 0.05
    assert round(t.intent_ms, 3) == 0.05
    assert round(t.dispatch_ms, 3) == 0.01
    # sensor_to_decision: t_intent_end (198.7) - t_capture (182.0) = 16.7 ms
    assert round(t.sensor_to_decision_ms, 2) == 16.7
    # total_e2e: t_ui_ack (199.0) - t_read_start (100.0) = 99.0 ms
    assert round(t.total_e2e_ms, 2) == 99.0


def test_compute_percentiles_empty():
    """Verify compute_percentiles handles empty inputs without raising ZeroDivisionError."""
    res = compute_percentiles([])
    assert res["count"] == 0
    assert res["min_ms"] == 0.0
    assert res["mean_ms"] == 0.0
    assert res["p50_ms"] == 0.0
    assert res["p95_ms"] == 0.0
    assert res["max_ms"] == 0.0


def test_compute_percentiles_distribution():
    """Verify compute_percentiles computes standard order statistics correctly."""
    # 100 values from 1.0 to 100.0
    vals = [float(i) for i in range(1, 101)]
    res = compute_percentiles(vals)
    assert res["count"] == 100
    assert res["min_ms"] == 1.0
    assert res["mean_ms"] == 50.5
    assert res["p50_ms"] == 51.0
    assert res["p90_ms"] == 91.0
    assert res["p95_ms"] == 96.0
    assert res["p99_ms"] == 100.0
    assert res["max_ms"] == 100.0


def test_sustained_performance_tracker_summary():
    """Verify SustainedPerformanceTracker aggregates throughput, percentiles, and resources."""
    tracker = SustainedPerformanceTracker(
        session_id="unit_test_session",
        source_mode="SYNTHETIC_FIXTURE",
        device_name="Test Device",
        requested_width=640,
        requested_height=480,
    )

    base_ns = 1_000_000_000
    for i in range(10):
        t_capture = base_ns + i * 33_333_333
        tracker.record_frame_captured(t_capture)
        tracker.record_frame_processed(t_capture + 15_000_000)
        tracker.record_frame_presented(t_capture + 16_000_000)

        tel = PipelineStageTelemetry(
            frame_id=i + 1,
            t_read_start_ns=t_capture - 5_000_000,
            t_capture_ns=t_capture,
            t_queue_insert_ns=t_capture,
            t_queue_remove_ns=t_capture + 500_000,
            t_infer_start_ns=t_capture + 600_000,
            t_infer_end_ns=t_capture + 15_000_000,
            t_features_start_ns=t_capture + 15_100_000,
            t_features_end_ns=t_capture + 15_200_000,
            t_recog_start_ns=t_capture + 15_250_000,
            t_recog_end_ns=t_capture + 15_300_000,
            t_intent_start_ns=t_capture + 15_350_000,
            t_intent_end_ns=t_capture + 15_400_000,
            t_dispatch_start_ns=t_capture + 15_450_000,
            t_dispatch_end_ns=t_capture + 15_460_000,
            t_ui_ack_ns=t_capture + 16_000_000,
        )
        tracker.record_stage_telemetry(tel)

    tracker.record_queue_metrics(queue_depth=1, dropped=0, stale=0, out_of_order=0)
    tracker.sample_resources()
    summary = tracker.compute_summary()

    assert summary["session_id"] == "unit_test_session"
    assert summary["total_frames_captured"] == 10
    assert summary["total_frames_processed"] == 10
    assert summary["total_frames_presented"] == 10
    assert summary["effective_capture_fps"] > 0
    assert "stage_latencies_ms" in summary
    assert summary["stage_latencies_ms"]["landmark_inference"]["count"] == 10
    assert summary["stage_latencies_ms"]["sensor_to_decision"]["count"] == 10
    assert summary["stage_latencies_ms"]["total_end_to_end"]["count"] == 10


def test_run_sustained_benchmark_synthetic():
    """Verify run_sustained_benchmark executes cleanly in synthetic mode."""
    res = run_sustained_benchmark(
        duration_s=0.2,
        mode="synthetic",
        resolution="640x480",
        fps=30,
        session_id="synth_test",
    )
    assert res["session_id"] == "synth_test"
    assert res["source_mode"] == "SYNTHETIC_FIXTURE"
    assert res["total_frames_captured"] > 0
    assert res["total_frames_processed"] > 0
    assert "stage_latencies_ms" in res
