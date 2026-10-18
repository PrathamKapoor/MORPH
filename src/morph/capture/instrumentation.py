"""Performance instrumentation and runtime telemetry for MORPH 2.0."""

from __future__ import annotations

import collections
import contextlib
import time
from dataclasses import dataclass
from typing import Any

try:
    import win32process

    _HAS_WIN32 = True
except ImportError:
    _HAS_WIN32 = False


@dataclass(frozen=True)
class PerformanceSnapshot:
    """Immutable point-in-time snapshot of system performance metrics."""

    fps_capture: float
    fps_processed: float
    latency_landmark_ms: float
    latency_features_ms: float
    latency_recognition_ms: float
    latency_intent_ms: float
    latency_e2e_ms: float
    queue_depth: int
    dropped_frames: int
    stale_frames: int
    out_of_order_frames: int
    memory_working_set_mb: float
    peak_memory_mb: float


@dataclass
class PipelineStageTelemetry:
    """Microsecond timestamps and latencies across all pipeline stages for a single frame."""

    frame_id: int
    t_read_start_ns: int = 0
    t_capture_ns: int = 0
    t_queue_insert_ns: int = 0
    t_queue_remove_ns: int = 0
    t_infer_start_ns: int = 0
    t_infer_end_ns: int = 0
    t_features_start_ns: int = 0
    t_features_end_ns: int = 0
    t_recog_start_ns: int = 0
    t_recog_end_ns: int = 0
    t_intent_start_ns: int = 0
    t_intent_end_ns: int = 0
    t_dispatch_start_ns: int = 0
    t_dispatch_end_ns: int = 0
    t_ui_ack_ns: int = 0

    @property
    def camera_read_ms(self) -> float:
        """Blocking time spent inside camera driver read."""
        if self.t_capture_ns > self.t_read_start_ns > 0:
            return (self.t_capture_ns - self.t_read_start_ns) / 1_000_000.0
        return 0.0

    @property
    def queue_dwell_ms(self) -> float:
        """Time frame spent waiting in worker queue."""
        if self.t_queue_remove_ns > self.t_queue_insert_ns > 0:
            return (self.t_queue_remove_ns - self.t_queue_insert_ns) / 1_000_000.0
        return 0.0

    @property
    def infer_ms(self) -> float:
        """MediaPipe Face Landmarker inference execution time."""
        if self.t_infer_end_ns > self.t_infer_start_ns > 0:
            return (self.t_infer_end_ns - self.t_infer_start_ns) / 1_000_000.0
        return 0.0

    @property
    def features_ms(self) -> float:
        """Feature extraction and neutral baseline normalization time."""
        if self.t_features_end_ns > self.t_features_start_ns > 0:
            return (self.t_features_end_ns - self.t_features_start_ns) / 1_000_000.0
        return 0.0

    @property
    def recog_ms(self) -> float:
        """Personalized classification time."""
        if self.t_recog_end_ns > self.t_recog_start_ns > 0:
            return (self.t_recog_end_ns - self.t_recog_start_ns) / 1_000_000.0
        return 0.0

    @property
    def intent_ms(self) -> float:
        """Deterministic intention gating state machine step time."""
        if self.t_intent_end_ns > self.t_intent_start_ns > 0:
            return (self.t_intent_end_ns - self.t_intent_start_ns) / 1_000_000.0
        return 0.0

    @property
    def dispatch_ms(self) -> float:
        """Action dispatcher execution time."""
        if self.t_dispatch_end_ns > self.t_dispatch_start_ns > 0:
            return (self.t_dispatch_end_ns - self.t_dispatch_start_ns) / 1_000_000.0
        return 0.0

    @property
    def sensor_to_decision_ms(self) -> float:
        """Latency from hardware optical delivery to intention decision."""
        if self.t_intent_end_ns > self.t_capture_ns > 0:
            return (self.t_intent_end_ns - self.t_capture_ns) / 1_000_000.0
        return 0.0

    @property
    def total_e2e_ms(self) -> float:
        """Total latency from camera read initiation through decision/dispatch."""
        end = self.t_ui_ack_ns or self.t_dispatch_end_ns or self.t_intent_end_ns
        if end > self.t_read_start_ns > 0:
            return (end - self.t_read_start_ns) / 1_000_000.0
        return 0.0


def compute_percentiles(values: list[float] | collections.deque[float]) -> dict[str, float | int]:
    """Compute sample count, min, mean, P50, P90, P95, P99, and max for latency values."""
    if not values:
        return {
            "count": 0,
            "min_ms": 0.0,
            "mean_ms": 0.0,
            "p50_ms": 0.0,
            "p90_ms": 0.0,
            "p95_ms": 0.0,
            "p99_ms": 0.0,
            "max_ms": 0.0,
        }
    sorted_v = sorted(values)
    n = len(sorted_v)

    def pct(p: float) -> float:
        idx = int(p * n)
        return float(sorted_v[min(idx, n - 1)])

    return {
        "count": n,
        "min_ms": float(sorted_v[0]),
        "mean_ms": float(sum(sorted_v) / n),
        "p50_ms": pct(0.50),
        "p90_ms": pct(0.90),
        "p95_ms": pct(0.95),
        "p99_ms": pct(0.99),
        "max_ms": float(sorted_v[-1]),
    }


class SustainedPerformanceTracker:
    """Long-run sustained performance and multi-stage latency tracker for empirical benchmarking."""

    def __init__(
        self,
        session_id: str = "sustained_benchmark",
        source_mode: str = "PHYSICAL_CAMERA",
        device_name: str = "Unknown",
        requested_width: int = 640,
        requested_height: int = 480,
        backend_name: str = "DSHOW",
    ) -> None:
        import os

        self.session_id = session_id
        self.source_mode = source_mode
        self.device_name = device_name
        self.requested_width = requested_width
        self.requested_height = requested_height
        self.backend_name = backend_name
        self.negotiated_width = requested_width
        self.negotiated_height = requested_height
        self.negotiated_fps = 30.0

        self.start_wall_time = time.time()
        self.start_monotonic_ns = time.monotonic_ns()
        self.end_monotonic_ns = 0

        # Stage latency lists
        self.camera_read_latencies: list[float] = []
        self.queue_dwell_latencies: list[float] = []
        self.infer_latencies: list[float] = []
        self.features_latencies: list[float] = []
        self.recog_latencies: list[float] = []
        self.intent_latencies: list[float] = []
        self.dispatch_latencies: list[float] = []
        self.sensor_to_decision_latencies: list[float] = []
        self.total_e2e_latencies: list[float] = []

        # Event timestamps
        self.capture_timestamps: list[int] = []
        self.processed_timestamps: list[int] = []
        self.presented_timestamps: list[int] = []

        # Queue tracking
        self.queue_occupancies: list[int] = []
        self.dropped_frames: int = 0
        self.stale_frames: int = 0
        self.out_of_order_frames: int = 0

        # Resource tracking
        self._last_process_time = time.process_time()
        self._last_perf_counter = time.perf_counter()
        self.cpu_samples_single_core: list[float] = []
        self.cpu_samples_system_norm: list[float] = []
        self.memory_samples_mb: list[float] = []
        self.peak_memory_mb: float = 0.0
        self.num_cores = os.cpu_count() or 1

    def record_stage_telemetry(self, t: PipelineStageTelemetry) -> None:
        """Record a completed frame's stage breakdown."""
        if t.camera_read_ms > 0:
            self.camera_read_latencies.append(t.camera_read_ms)
        if t.t_queue_insert_ns > 0 and t.t_queue_remove_ns >= t.t_queue_insert_ns:
            self.queue_dwell_latencies.append(t.queue_dwell_ms)
        if t.infer_ms > 0:
            self.infer_latencies.append(t.infer_ms)
        if t.features_ms > 0:
            self.features_latencies.append(t.features_ms)
        if t.recog_ms > 0:
            self.recog_latencies.append(t.recog_ms)
        if t.intent_ms > 0:
            self.intent_latencies.append(t.intent_ms)
        if t.t_dispatch_start_ns > 0 and t.t_dispatch_end_ns >= t.t_dispatch_start_ns:
            self.dispatch_latencies.append(t.dispatch_ms)
        if t.sensor_to_decision_ms > 0:
            self.sensor_to_decision_latencies.append(t.sensor_to_decision_ms)
        if t.total_e2e_ms > 0:
            self.total_e2e_latencies.append(t.total_e2e_ms)

    def record_frame_captured(self, timestamp_ns: int) -> None:
        """Record camera arrival event."""
        self.capture_timestamps.append(timestamp_ns)

    def record_frame_processed(self, timestamp_ns: int) -> None:
        """Record pipeline completion event."""
        self.processed_timestamps.append(timestamp_ns)

    def record_frame_presented(self, timestamp_ns: int) -> None:
        """Record UI presentation event."""
        self.presented_timestamps.append(timestamp_ns)

    def record_queue_metrics(
        self, queue_depth: int, dropped: int = 0, stale: int = 0, out_of_order: int = 0
    ) -> None:
        """Record buffer state."""
        self.queue_occupancies.append(queue_depth)
        self.dropped_frames = dropped
        self.stale_frames = stale
        self.out_of_order_frames = out_of_order

    def sample_resources(self) -> tuple[float, float]:
        """Sample process CPU % and WorkingSet memory MB."""
        now_proc = time.process_time()
        now_wall = time.perf_counter()
        d_proc = now_proc - self._last_process_time
        d_wall = now_wall - self._last_perf_counter
        self._last_process_time = now_proc
        self._last_perf_counter = now_wall

        single_cpu = (d_proc / d_wall * 100.0) if d_wall > 0 else 0.0
        sys_cpu = single_cpu / self.num_cores
        self.cpu_samples_single_core.append(single_cpu)
        self.cpu_samples_system_norm.append(sys_cpu)

        mem_mb = 0.0
        if _HAS_WIN32:
            try:
                info = win32process.GetProcessMemoryInfo(-1)
                mem_mb = info.get("WorkingSetSize", 0) / (1024.0 * 1024.0)
            except Exception:
                mem_mb = 0.0
        if mem_mb > self.peak_memory_mb:
            self.peak_memory_mb = mem_mb
        if mem_mb > 0:
            self.memory_samples_mb.append(mem_mb)

        return single_cpu, mem_mb

    def finish(self) -> None:
        """Mark completion timestamp."""
        self.end_monotonic_ns = time.monotonic_ns()

    def calculate_throughput_fps(self, timestamps: list[int]) -> float:
        """Calculate effective sustained FPS over entire recording duration."""
        if len(timestamps) < 2:
            return 0.0
        elapsed_sec = (timestamps[-1] - timestamps[0]) / 1_000_000_000.0
        if elapsed_sec <= 0:
            return 0.0
        return (len(timestamps) - 1) / elapsed_sec

    def compute_summary(self) -> dict[str, Any]:
        """Generate comprehensive benchmark report dictionary."""
        import statistics

        if self.end_monotonic_ns == 0:
            self.finish()

        elapsed_sec = (self.end_monotonic_ns - self.start_monotonic_ns) / 1_000_000_000.0

        fps_capture = self.calculate_throughput_fps(self.capture_timestamps)
        fps_processed = self.calculate_throughput_fps(self.processed_timestamps)
        fps_presented = self.calculate_throughput_fps(self.presented_timestamps)

        mean_cpu_single = (
            statistics.mean(self.cpu_samples_single_core) if self.cpu_samples_single_core else 0.0
        )
        mean_cpu_sys = (
            statistics.mean(self.cpu_samples_system_norm) if self.cpu_samples_system_norm else 0.0
        )
        mean_mem = statistics.mean(self.memory_samples_mb) if self.memory_samples_mb else 0.0
        mean_queue = statistics.mean(self.queue_occupancies) if self.queue_occupancies else 0.0
        max_queue = max(self.queue_occupancies) if self.queue_occupancies else 0

        return {
            "session_id": self.session_id,
            "source_mode": self.source_mode,
            "device_name": self.device_name,
            "backend_name": self.backend_name,
            "resolution": f"{self.negotiated_width}x{self.negotiated_height}",
            "elapsed_seconds": round(elapsed_sec, 3),
            "total_frames_captured": len(self.capture_timestamps),
            "total_frames_processed": len(self.processed_timestamps),
            "total_frames_presented": len(self.presented_timestamps),
            "effective_capture_fps": round(fps_capture, 2),
            "effective_processed_fps": round(fps_processed, 2),
            "effective_presented_fps": round(fps_presented, 2),
            "queue_metrics": {
                "mean_occupancy": round(mean_queue, 2),
                "max_occupancy": max_queue,
                "dropped_frames": self.dropped_frames,
                "stale_frames": self.stale_frames,
                "out_of_order_frames": self.out_of_order_frames,
            },
            "resource_utilization": {
                "cpu_single_core_pct_mean": round(mean_cpu_single, 2),
                "cpu_system_normalized_pct_mean": round(mean_cpu_sys, 2),
                "num_cores": self.num_cores,
                "memory_working_set_mb_mean": round(mean_mem, 2),
                "memory_peak_mb": round(self.peak_memory_mb, 2),
            },
            "stage_latencies_ms": {
                "camera_read_blocking": compute_percentiles(self.camera_read_latencies),
                "queue_dwell": compute_percentiles(self.queue_dwell_latencies),
                "landmark_inference": compute_percentiles(self.infer_latencies),
                "feature_extraction": compute_percentiles(self.features_latencies),
                "recognition": compute_percentiles(self.recog_latencies),
                "intent_decision": compute_percentiles(self.intent_latencies),
                "dispatch": compute_percentiles(self.dispatch_latencies),
                "sensor_to_decision": compute_percentiles(self.sensor_to_decision_latencies),
                "total_end_to_end": compute_percentiles(self.total_e2e_latencies),
            },
        }


class PerformanceMonitor:
    """Tracks latency across pipeline stages, throughput, queues, and memory usage."""

    def __init__(self, window_size: int = 60) -> None:
        self.window_size = window_size
        self._stage_latencies: dict[str, collections.deque[float]] = {
            "landmark": collections.deque(maxlen=window_size),
            "features": collections.deque(maxlen=window_size),
            "recognition": collections.deque(maxlen=window_size),
            "intent": collections.deque(maxlen=window_size),
            "dispatch": collections.deque(maxlen=window_size),
            "end_to_end": collections.deque(maxlen=window_size),
        }
        self._capture_timestamps = collections.deque(maxlen=window_size)
        self._processed_timestamps = collections.deque(maxlen=window_size)
        self._queue_depth: int = 0
        self._dropped_frames: int = 0
        self._stale_frames: int = 0
        self._out_of_order_frames: int = 0
        self._peak_memory_mb: float = 0.0

    @contextlib.contextmanager
    def measure_stage(self, stage_name: str):
        """Context manager to measure execution time of a pipeline stage in milliseconds."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            self.record_stage_latency(stage_name, elapsed_ms)

    def record_stage_latency(self, stage_name: str, duration_ms: float) -> None:
        """Record latency for a specific stage."""
        if stage_name not in self._stage_latencies:
            self._stage_latencies[stage_name] = collections.deque(maxlen=self.window_size)
        self._stage_latencies[stage_name].append(duration_ms)

    def record_capture_event(self, timestamp_ns: int) -> None:
        """Record when a frame was acquired from the camera."""
        self._capture_timestamps.append(timestamp_ns)

    def record_process_event(self, timestamp_ns: int) -> None:
        """Record when a frame was successfully processed by the pipeline."""
        self._processed_timestamps.append(timestamp_ns)

    def update_queue_metrics(
        self,
        queue_depth: int,
        dropped: int = 0,
        stale: int = 0,
        out_of_order: int = 0,
    ) -> None:
        """Update buffer and dropped frame statistics."""
        self._queue_depth = queue_depth
        self._dropped_frames = dropped
        self._stale_frames = stale
        self._out_of_order_frames = out_of_order

    def get_stage_mean_latency(self, stage_name: str) -> float:
        """Get rolling average latency in milliseconds for a stage."""
        dq = self._stage_latencies.get(stage_name)
        if not dq or len(dq) == 0:
            return 0.0
        return sum(dq) / len(dq)

    def get_stage_p95_latency(self, stage_name: str) -> float:
        """Get 95th percentile latency in milliseconds for a stage."""
        dq = self._stage_latencies.get(stage_name)
        if not dq or len(dq) == 0:
            return 0.0
        sorted_lat = sorted(dq)
        idx = int(0.95 * len(sorted_lat))
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    def calculate_fps(self, timestamps: collections.deque[int]) -> float:
        """Calculate frames per second from rolling timestamps."""
        if len(timestamps) < 2:
            return 0.0
        elapsed_sec = (timestamps[-1] - timestamps[0]) / 1_000_000_000.0
        if elapsed_sec <= 0:
            return 0.0
        return (len(timestamps) - 1) / elapsed_sec

    def get_memory_mb(self) -> float:
        """Get current process working set size in megabytes."""
        mem_mb = 0.0
        if _HAS_WIN32:
            try:
                info = win32process.GetProcessMemoryInfo(-1)
                mem_mb = info.get("WorkingSetSize", 0) / (1024.0 * 1024.0)
            except Exception:
                mem_mb = 0.0
        if mem_mb > self._peak_memory_mb:
            self._peak_memory_mb = mem_mb
        return mem_mb

    def snapshot(self) -> PerformanceSnapshot:
        """Capture current telemetry metrics."""
        current_mem = self.get_memory_mb()
        return PerformanceSnapshot(
            fps_capture=self.calculate_fps(self._capture_timestamps),
            fps_processed=self.calculate_fps(self._processed_timestamps),
            latency_landmark_ms=self.get_stage_mean_latency("landmark"),
            latency_features_ms=self.get_stage_mean_latency("features"),
            latency_recognition_ms=self.get_stage_mean_latency("recognition"),
            latency_intent_ms=self.get_stage_mean_latency("intent"),
            latency_e2e_ms=self.get_stage_mean_latency("end_to_end"),
            queue_depth=self._queue_depth,
            dropped_frames=self._dropped_frames,
            stale_frames=self._stale_frames,
            out_of_order_frames=self._out_of_order_frames,
            memory_working_set_mb=current_mem,
            peak_memory_mb=self._peak_memory_mb,
        )

    def reset(self) -> None:
        """Reset rolling metrics."""
        for dq in self._stage_latencies.values():
            dq.clear()
        self._capture_timestamps.clear()
        self._processed_timestamps.clear()
        self._dropped_frames = 0
        self._stale_frames = 0
        self._out_of_order_frames = 0
