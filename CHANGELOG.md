# Changelog

All notable changes to MORPH 2.0 are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-10-17

### Added
- **M7 Scientific Integrity, Physical Validation & Production Finalization**:
  - **M7.1 Benchmark Duration & Confidence Interval Correction**:
    - Reconciled exact canonical benchmark duration (3,520 frames = 118.050s total; 1.600s ground truth command exposure; 116.450s / 0.032347 hr non-command exposure).
    - Enforced non-command duration invariants and interval merging in `src/morph/evaluation/metrics.py`.
    - Implemented exact two-sided 95% Garwood confidence interval ($[0.00, 114.04]$ FA/hr for $k=0$) and one-sided 95% upper bound ($92.61$ FA/hr).
    - Documented canonical findings in `docs/EXPERIMENT_LOG.md` (EXP-004) and ADR-047.
  - **M7.2 Benchmark Dataset Integrity & Generalization**:
    - Separated calibration enrollment prototypes from held-out evaluation scenarios with realistic scale offsets, yaw/pitch perturbations, and micro-jitter.
    - Implemented zero-leakage invariant assertion ($\min \|v_{eval} - v_{cal}\|_2 > 10^{-4}$, actual min $> 0.001$, mean $> 0.01$).
    - Executed 120-configuration hyperparameter sensitivity sweep across hold duration, refractory cooldown, and similarity margin, confirming optimality of MORPH's 250ms default in `docs/PARAMETER_SENSITIVITY.md` and ADR-048.
  - **M7.3 Physical Optical Sensor & Replay Provenance Trace**:
    - Implemented strongly typed `SourceMode` enum (`PHYSICAL_CAMERA`, `RECORDED_REPLAY`, `SYNTHETIC_FIXTURE`, `CAMERA_UNAVAILABLE`) propagating active sensor provenance to UI telemetry.
    - Conducted 30-frame live optical validation on DirectShow camera index 0 (Integrated Camera), recording shutter/transfer latency (mean 83.5ms, p50 78.0ms) and local CPU MediaPipe Face Landmarker inference latency (mean 14.9ms, p50 15.0ms) with zero frame storage on disk (`docs/PHYSICAL_CAMERA_VALIDATION.md`).
    - Verified 5-stage interactive user journey in `tests/unit/test_end_to_end_journey.py` and ADR-049.
  - **M7.4 Independent Windows Packaging & Bundle Isolation**:
    - Enforced strict model resolution isolation in `src/morph/capture/tracker.py::resolve_model_asset_path`, preventing frozen binaries from falling back to developer checkout paths or working directories.
    - Verified standalone executable relocation independence in `tests/smoke/test_distribution.py::test_distribution_relocation_execution` under isolated temporary directories with `PYTHONPATH` cleared (ADR-050).
  - **M7.5 Accessible Rest Advisor & Continuous Ergonomics (PRD D09)**:
    - Implemented `src/morph/ui/rest_advisor.py::RestAdvisor` monitoring continuous active communication duration.
    - Displayed accessible, non-medical rest notification banner with 1-click safe pause ("Take a Break") and snooze controls.
    - Documented complete Windows Narrator screen reader audit and WCAG 2.1 AAA contrast ratios in `docs/ACCESSIBILITY_AUDIT.md`.
  - **M7.6 Demonstration Reliability & Stage Recovery**:
    - Added dedicated presentation keyboard controls (`Left Arrow`, `Right Arrow`, `R` for reset) and accessible descriptions in `DemoView`.
    - Authored 7-stage live presentation script with verbatim talk track and contingency recovery procedures in `docs/DEMO_GUIDE.md` (ADR-051).
  - **M7.7 Production Security & Threat Model Audit**:
    - Compiled `docs/SECURITY_AUDIT.md` verifying 100% offline network isolation, zero persistent video, sandboxed action dispatch, and SQL parameterization.
  - **M7.8 Release Packaging & Completion Report**:
    - Updated `docs/REQUIREMENT_TRACEABILITY.md` and `flow.md` reflecting 100% milestone completion and honest release readiness classifications.

## [2.0.0] - 2026-10-17

### Added

- **M6.8 Release Engineering & Diagnostics**:
  - Implemented headless CLI self-test (`--headless-check`) in `src/morph/__main__.py` for automated non-GUI smoke validation.
  - Added Windows parent console attachment for CLI flags (`--version`, `--headless-check`, `--doctor`) in windowed executables.
  - Enhanced `scripts/doctor.ps1` with 6 structured health checks, SQLite permissions test, and formatted PASS/WARN/FAIL checklist.
  - Added PyInstaller distribution smoke tests in `tests/smoke/test_distribution.py`.
  - Comprehensive `docs/RELEASE_CHECKLIST.md` detailing all pre-release verification gates.
- **M6.7 Concurrency, Bounded Queue & Stress Testing**:
  - Implemented `src/morph/capture/queue.py::BoundedFrameQueue` with condition variable synchronization and drop-oldest frame backpressure.
  - 10,000-frame sustained pipeline stress test verifying zero crashes and memory stability (<25MB RAM growth).
  - Multi-threaded producer-consumer backpressure and deadlock avoidance test suite.
  - Deep privacy audit verifying zero raw video persistence across repository and OS temp directories.
  - SQLite WAL mode concurrency stress test with 8 concurrent reader and writer threads across user profile versions.
  - Rapid state toggle thrashing test ensuring `State.PAUSED` fail-closed invariant across 100 rapid cycles.
- **M6.6 Safe Live Demonstration Mode**:
  - Implemented `src/morph/ui/demo_view.py` with automated preflight diagnostics and 7-stage guided demonstration script.
  - Dedicated `"demo"` route and tab in `src/morph/ui/main_window.py` with talk-track cues.
- **M6.5 Explainable Live Diagnostics & Telemetry**:
  - Implemented `LiveIntentionGateInspector` and `LiveDistanceInspector` in `src/morph/ui/monitor_view.py`.
  - Displayed real-time FSM state badges, hold progress percentage bars, structured `DecisionReason` explanations, and raw cosine similarities / Euclidean feature distances with explicit scientific disclaimers.
- **M6.4 Accessible UI Polishing & Windows Narrator Audit**:
  - Updated `docs/MANUAL_VALIDATION_CHECKLIST.md` with WCAG AAA color contrast audits, $\ge 48\times 48$ touch target metrics, and live Windows Narrator screen reader test scripts.
  - Enhanced accessible labels, accessible names, and tab order throughout all views.
- **M6.3 Controlled Real-World Testing Infrastructure**:
  - Implemented `src/morph/ui/evaluation_session_view.py` with participant consent gating, unique ID generation, automated task cueing runner, real-time ground truth event logging, and zero-residue session wiping.
  - Authored `docs/REAL_WORLD_STUDY_PROTOCOL.md` defining a Latin Square within-subject design, Poisson false activation rate metrics, NASA-TLX, Borg CR10, and SUS usability evaluation protocols.
- **M6.2 Multi-Modal Baseline Correction & Synthetic Challenge Suite**:
  - Expanded `RecognizerA` to evaluate 32-dim geometric distance vectors and 52-dim blendshape features.
  - Implemented exact Garwood Poisson 95% confidence intervals with zero-count upper bound $3.0/T$ in `src/morph/evaluation/metrics.py`.
  - Created 20-scenario synthetic challenge suite (`tests/fixtures/benchmark_scenarios.py`) covering micro-twitches, sustained expressions, tracking loss, multi-face presence, and ambient lighting changes.
  - Recorded Experiment EXP-003 proving Condition C achieves 0 false activations (100% precision) compared to Condition A (7 FA, 216.4 FA/hr) and Condition B (4 FA, 123.7 FA/hr).
- **M6.1 End-to-End User Workflows Integration Suite**:
  - Authored `tests/integration/test_user_workflows.py` covering all 5 core user journeys: first-time onboarding, returning user practice/live, distribution drift detection & atomic rollback, tracking loss mid-gesture recovery, and cross-session restart persistence.
- **M5 Reliability, Adaptive Personalization & Hardening**:
  - Profile versioning manager (`src/morph/storage/versions.py`) with immutable snapshots and atomic rollback.
  - Distribution drift detection engine (`src/morph/adaptation/drift.py`) monitoring feature centroid deviation.
  - Non-medical fatigue warning dialogs with accessible guidance and automated recalibration triggers.
  - Fault injection testing (`tests/unit/test_fault_injection.py`) verifying camera disconnection recovery, corrupted database recovery, and offline network isolation.
- **M0–M4 Core Architecture**:
  - Pure mathematical FSM `IntentEngine` with micro-twitch rejection and fail-closed initial state.
  - MediaPipe 478-landmark tracking with DirectShow backend and synthetic fallback.
  - Interocular scale-invariant feature normalization and personalized cosine similarity classifier.
  - Accessible 9-tile communication board with local Windows SAPI TTS speech output.
  - Deterministic evaluation replay engine with A/B/C condition comparison.
  - Local SQLite storage with WAL mode and schema migration management.
