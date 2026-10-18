# MORPH 2.0 Architectural Decision Records (ADRs)

Author: Pratham Kapoor <prathamkapoor027@gmail.com>  
System: Windows 10/11 Local Offline AAC System  
Location: `C:\Pratham\MORPH`  
Status: Accepted and Implemented across M0–M5

---

## ADR-001: Offline and Local-Only Execution Architecture
- **Context & Problem**: Assistive communication software processes highly intimate facial video. Cloud inference introduces network latency, availability risks, and severe privacy violations.
- **Decision Made**: The application must execute 100% locally and offline without external network dependencies during runtime.
- **Alternatives Rejected**: Cloud computer vision APIs (rejected: privacy violation, network dependency, variable round-trip latency).
- **Trade-Offs Accepted**: Model selection is constrained to models capable of efficient local CPU inference (MediaPipe Face Landmarker).
- **Verification & Reconsideration**: Verified via offline execution test with network interfaces disabled. Reconsideration only if local compute proves insufficient on supported Windows hardware.

---

## ADR-002: Transient Memory-Only Video Frames
- **Context & Problem**: Persistent raw video storage creates legal, ethical, and privacy vulnerabilities for users in private home/clinical settings.
- **Decision Made**: Webcam frames exist strictly as transient numpy arrays in volatile memory, discarded immediately after landmark inference. No raw video is ever saved to disk.
- **Alternatives Rejected**: Video session recording for post-hoc debugging (rejected: unacceptable privacy liability for AAC users).
- **Trade-Offs Accepted**: Video cannot be re-watched for visual debugging; evaluation relies entirely on extracted landmark/feature streams.
- **Verification & Reconsideration**: Audited via disk write logs; verified zero video files exist outside RAM.

---

## ADR-003: Pure Deterministic Finite-State Machine for Intention Gating
- **Context & Problem**: Accidental command dispatches in AAC can cause distress or unwanted actions. The intention gate must be 100% predictable, testable, and auditable.
- **Decision Made**: Implement the IntentEngine as a pure finite-state machine with injected monotonic timestamps, tracking state, and classifier inputs.
- **Alternatives Rejected**: End-to-end recurrent neural networks or heuristic leaky integrators (rejected: non-deterministic, hard to audit, prone to drift).
- **Trade-Offs Accepted**: Requires explicit state definitions (PAUSED, TRACKING_LOST, IDLE, CANDIDATE, CONFIRMED, COOLDOWN).
- **Verification & Reconsideration**: Comprehensive unit test suite testing all boundary transitions and timestamp jitter.

---

## ADR-004: Centralized Sandboxed ActionDispatcher with Strict Allow-Listing
- **Context & Problem**: Unauthorized or arbitrary OS actions triggered by misclassification could modify files or execute harmful commands.
- **Decision Made**: All execution side-effects flow strictly through a singleton `ActionDispatcher` enforcing a static typed allow-list: `NEXT_TILE`, `PREVIOUS_TILE`, `SELECT_TILE`, `SPEAK_TILE`, `BACK`, `PAUSE`.
- **Alternatives Rejected**: Direct UI button click triggering or allowing arbitrary shell execution (rejected: severe safety vulnerability).
- **Trade-Offs Accepted**: Adding new actions requires explicit code changes and enum updates.
- **Verification & Reconsideration**: Integration tests demonstrating rejection of any non-allow-listed action identifier.

---

## ADR-005: Three-Way Controlled A/B/C Experimental Replay Methodology
- **Context & Problem**: Prior literature claims intention gating improvements without fair, identical-input comparisons against simpler baselines.
- **Decision Made**: Replay identical saved feature sequences through:
  - **A**: Fixed generic anatomical motion thresholds.
  - **B**: Personalized recognizer firing immediately upon candidate detection.
  - **C**: Identical predictions from B passed through the deterministic intention gate.
- **Alternatives Rejected**: Testing conditions on live human trials on separate days (rejected: introduces confounding muscular fatigue and variance).
- **Trade-Offs Accepted**: Requires deterministic feature recording with informed consent.
- **Verification & Reconsideration**: Unit test verifying Condition B and Condition C receive bit-exact identical classifier scores per frame.

---

## ADR-006: Fixed Relative Normalization via Inter-Ocular Distance and Rest Baseline
- **Context & Problem**: Facial landmark coordinates vary with user distance from camera, head orientation, and individual anatomy.
- **Decision Made**: Normalize all geometric landmark displacements relative to the user's recorded resting neutral baseline, scaled by inter-ocular distance.
- **Alternatives Rejected**: Absolute pixel displacement (rejected: scales with user distance to webcam); raw uncalibrated blendshapes (rejected: inconsistent across lighting).
- **Trade-Offs Accepted**: Requires a guided neutral rest calibration step before training gestures.
- **Verification & Reconsideration**: Verified via scale-invariance unit tests across synthetic camera distances.

---

## ADR-007: MediaPipe Face Landmarker Task API on Local Worker Thread
- **Context & Problem**: Computer vision inference on the UI thread causes dropped frames and unresponsive user interface.
- **Decision Made**: Run MediaPipe Face Landmarker inside a dedicated Python worker thread communicating via thread-safe bounded queues.
- **Alternatives Rejected**: Synchronous UI thread capture (rejected: freezes UI); multiprocessing (rejected: IPC overhead on Windows for video buffers).
- **Trade-Offs Accepted**: Requires thread synchronization and graceful shutdown management.
- **Verification & Reconsideration**: Verified GUI remains responsive (>30 FPS) while capture worker runs under load.

---

## ADR-008: PySide6 (Qt for Python) for Windows-Native Accessible UI
- **Context & Problem**: The app requires clean layout, robust keyboard accessibility, high-contrast themes, and high-DPI Windows scaling.
- **Decision Made**: Build the user interface using PySide6 (Qt 6 for Python).
- **Alternatives Rejected**: Tkinter (rejected: poor styling, inadequate accessibility); Electron (rejected: heavy resource overhead, Chromium complexity).
- **Trade-Offs Accepted**: Dependency footprint of PySide6 wheels (~150MB).
- **Verification & Reconsideration**: Verified keyboard navigation, tab focus, and DPI scaling on Windows.

---

## ADR-009: SQLite Local Database with Versioned Migrations
- **Context & Problem**: User profiles, gesture calibrations, and audit events require persistent, structured, atomic local storage.
- **Decision Made**: Use local SQLite database (`data/morph.db`) with an explicit migration manager and transactional writes.
- **Alternatives Rejected**: Plain JSON files (rejected: risk of file corruption on sudden power loss/crash); client-server databases (rejected: overkill for offline local app).
- **Trade-Offs Accepted**: Requires schema definitions and migration scripts.
- **Verification & Reconsideration**: Transaction rollback tests and migration consistency tests.

---

## ADR-010: Windows SAPI for Local Text-to-Speech Output
- **Context & Problem**: Communication board requires immediate spoken output without internet access.
- **Decision Made**: Use native Windows Speech API (SAPI via `System.Speech` or `pyttsx3`/local COM adapter) for zero-latency speech synthesis.
- **Alternatives Rejected**: Cloud TTS APIs (rejected: violates offline requirement); heavy neural TTS models (rejected: high memory/CPU burden).
- **Trade-Offs Accepted**: Voice quality depends on installed Windows system voices.
- **Verification & Reconsideration**: Verified speech generation on Microsoft David/Zira voices with fallback handling.

---

## ADR-011: Bounded Ring-Buffer Frame Queue with Oldest-Frame Dropping
- **Context & Problem**: Slower hardware may experience processing backlog, leading to stale command execution seconds after user movement.
- **Decision Made**: Use a bounded queue of size 2; when full, drop the oldest frame and increment a drop counter. Discard frames older than 100 ms.
- **Alternatives Rejected**: Unbounded FIFO queue (rejected: creates latency lag and delayed trigger disasters).
- **Trade-Offs Accepted**: Dropped frames reduce processed FPS under heavy CPU load, but maintain fresh temporal alignment.
- **Verification & Reconsideration**: Latency and drop rate measured in Reliability Monitor under artificial CPU stress.

---

## ADR-012: Fail-Closed Exactly-One-Face Requirement
- **Context & Problem**: Multiple faces in view (caregivers, family members) can confuse facial tracking and cause unintended actions.
- **Decision Made**: Require exactly 1 detected face. If 0 faces or >1 faces are detected, tracking validity is immediately set to False and state shifts to `TRACKING_LOST`.
- **Alternatives Rejected**: Nearest face tracking (rejected: dangerous ambiguity if caregiver leans in).
- **Trade-Offs Accepted**: User must ensure single-face webcam framing.
- **Verification & Reconsideration**: Multi-face test fixtures confirming complete command suppression.

---

## ADR-013: Re-Arm Neutral Dwell Requirement after Tracking Recovery
- **Context & Problem**: When tracking recovers after occlusion, a user mid-movement could trigger an instant accidental command.
- **Decision Made**: Entering `IDLE` from `TRACKING_LOST` or `PAUSED` requires a minimum 200 ms dwell in valid neutral state before admitting candidates.
- **Alternatives Rejected**: Immediate candidate evaluation on first frame of recovered tracking (rejected: creates false triggers on face re-entry).
- **Trade-Offs Accepted**: Negligible 200 ms re-acquisition delay.
- **Verification & Reconsideration**: State machine transition test verifying no command emits on the first valid frame after recovery.

---

## ADR-014: Microsecond Monotonic Timestamps for All Internal Timing
- **Context & Problem**: System wall clock adjustments (NTP sync, timezone changes) can jump backward or forward, corrupting state machine timers.
- **Decision Made**: Use `time.monotonic_ns()` for all state machine transitions, hold timers, cooldowns, and latency benchmarks.
- **Alternatives Rejected**: `time.time()` (rejected: non-monotonic, susceptible to clock jumps).
- **Trade-Offs Accepted**: Timestamps are relative to machine boot time; UTC timestamps are only used for human-readable audit logs.
- **Verification & Reconsideration**: Unit tests with negative wall clock jumps verifying zero timer malfunction.

---

## ADR-015: Separate Practice Mode with NoOpActionSink
- **Context & Problem**: Users need to test movements without accidentally speaking phrases or changing settings during onboarding.
- **Decision Made**: Studio includes a dedicated Practice Mode using `NoOpActionSink` which logs would-be triggers without executing any side effects.
- **Alternatives Rejected**: Live testing during enrollment (rejected: accidental speech and confusion for new users).
- **Trade-Offs Accepted**: Requires clear UI visual distinction between Practice Mode and Live Mode.
- **Verification & Reconsideration**: Automated tests verifying zero TTS calls during Practice Mode.

---

## ADR-016: Explicit Unknown and Ambiguity Margin Rejection in Classifier
- **Context & Problem**: Classifiers often assign arbitrary high confidence to unseen inputs if forced into multi-class softmax.
- **Decision Made**: The classifier computes distance to gesture prototypes and explicitly outputs `UNKNOWN` if distance exceeds threshold, or `AMBIGUOUS` if margin between top 2 labels is < 0.15.
- **Alternatives Rejected**: Uncalibrated 1-vs-rest without margin check (rejected: causes frequent misclassifications).
- **Trade-Offs Accepted**: Non-distinct gestures will be rejected with an instructional explanation.
- **Verification & Reconsideration**: Tested against synthetic ambiguous and outlier feature vectors.

---

## ADR-017: Maximum Three Active Gestures in MVP / V1 Scope
- **Context & Problem**: Enrolling too many facial gestures increases cognitive load, collision probability, and classifier confusion.
- **Decision Made**: Limit active gesture vocabulary to at most three distinct user-selected movements in V1 (e.g., Brow Raise, Left Wink, Mouth Open).
- **Alternatives Rejected**: Unconstrained gesture count (rejected: exponentially degrades accuracy and increases enrollment fatigue).
- **Trade-Offs Accepted**: Limits communication board navigation to Next, Previous, Select (or Back via dwell/combo).
- **Verification & Reconsideration**: Usability testing on 3-gesture vocabulary efficiency.

---

## ADR-018: 5 to 10 Sample Guided Enrollment with Held-Out Test Set
- **Context & Problem**: Deep learning models require thousands of samples; users with disabilities fatigue quickly.
- **Decision Made**: Use 5–10 high-quality deliberate samples per gesture, with the final 2 samples automatically held out for local validation.
- **Alternatives Rejected**: Single-shot template matching (rejected: too noisy); 50+ sample datasets (rejected: severe user fatigue).
- **Trade-Offs Accepted**: Requires clear visual pacing during enrollment.
- **Verification & Reconsideration**: Held-out validation score calculation without data leakage.

---

## ADR-019: One-to-One Bipartite Event Matching for Evaluation Metrics
- **Context & Problem**: A single prolonged command dispatch could naively be counted as matching multiple ground truth events.
- **Decision Made**: Implement greedy one-to-one bipartite temporal matching between ground truth intentional events and dispatched command events within a tolerance window ($\pm 500$ ms).
- **Alternatives Rejected**: Many-to-one or window-overlap matching (rejected: falsely inflates precision and recall).
- **Trade-Offs Accepted**: Spurious double-fires are penalized as both false activations and lower precision.
- **Verification & Reconsideration**: Verified against hand-calculated synthetic event sequences.

---

## ADR-020: Unintended Activations Per Non-Command Hour Metric Definition
- **Context & Problem**: False alarm rates must be normalized by time spent in natural, non-command behavior.
- **Decision Made**: Define $FA/hr = \frac{N_{unmatched\_actions}}{T_{non\_command\_hours}}$. If $T_{non\_command\_hours} = 0$, return `N/A`, never `0.0`.
- **Alternatives Rejected**: False alarms per total session time (rejected: distorts metric if session is mostly active commands).
- **Trade-Offs Accepted**: Requires precise ground-truth annotation of non-command intervals.
- **Verification & Reconsideration**: Verified on edge cases with zero non-command duration.

---

## ADR-021: Non-Clamped Latency Breakdown Reporting
- **Context & Problem**: Clamping negative latency offsets (when an algorithm fires prematurely before user gesture finishes) conceals early firing bugs.
- **Decision Made**: Record raw un-clamped $t_{dispatch} - t_{gesture\_end}$. Separately record capture-to-inference, inference-to-gate, and gate-to-dispatch timings.
- **Alternatives Rejected**: Clamping latency to $\ge 0$ ms (rejected: distorts true timing distributions).
- **Trade-Offs Accepted**: Reporting P50 and P95 requires filtering out invalid/unmatched events.
- **Verification & Reconsideration**: Unit test verifying negative latency preservation on premature triggers.

---

## ADR-022: Separate Informed Consent for Feature Sequence Recording
- **Context & Problem**: Basic AAC use must not be contingent on participating in research data recording.
- **Decision Made**: Research feature sequence recording requires explicit, granular opt-in consent. Normal communication runs without saving any sequences.
- **Alternatives Rejected**: Bundled mandatory recording (rejected: unethical privacy violation).
- **Trade-Offs Accepted**: Research dataset size is smaller and strictly opt-in.
- **Verification & Reconsideration**: UI consent dialog verification and test proving no files written when consent is denied.

---

## ADR-023: Local Complete Data Deletion Facility
- **Context & Problem**: Users must have the right to permanently erase all biometric calibrations, profiles, and logs from their device.
- **Decision Made**: Provide a one-click "Delete All Local Data" function that securely purges SQLite databases, profile directories, and logs.
- **Alternatives Rejected**: Manual file deletion instructions (rejected: error-prone for non-technical users).
- **Trade-Offs Accepted**: Deletion is irreversible; requires confirmation modal.
- **Verification & Reconsideration**: Verified via file system and SQLite inspection after deletion trigger.

---

## ADR-024: Fail-Safe Global Pause Shortcut and Startup Paused State
- **Context & Problem**: An AAC user or caregiver must have an immediate, unconditional way to stop unwanted actions if the system misbehaves.
- **Decision Made**: Spacebar / Escape acts as an instant global pause toggle. The application starts strictly in `PAUSED` state upon launch and profile switch.
- **Alternatives Rejected**: Auto-activating on launch (rejected: dangerous if user is unprepared).
- **Trade-Offs Accepted**: User must perform one explicit activation click or keypress to begin.
- **Verification & Reconsideration**: State machine and UI tests verifying startup state is always PAUSED.

---

## ADR-025: Fixed-Threshold Baseline Condition A Specification
- **Context & Problem**: Need an honest, fair baseline representing standard off-the-shelf threshold triggers without personalization.
- **Decision Made**: Condition A uses fixed normalized geometric displacement thresholds (e.g., brow displacement > 0.08 normalized units) with basic noise suppression so it is not unfairly crippled.
- **Alternatives Rejected**: A strawman baseline with 0 threshold (rejected: unscientific and dishonest).
- **Trade-Offs Accepted**: Requires tuning standard anatomical thresholds for common gestures.
- **Verification & Reconsideration**: Documented in `docs/EXPERIMENT_PROTOCOL.md` and benchmarked.

---

## ADR-026: Nearest Prototype / KNN Classifier for Condition B Baseline
- **Context & Problem**: Condition B must represent state-of-the-art personalized few-shot classification without temporal intention gating.
- **Decision Made**: Condition B uses nearest prototype (centroid with cosine/euclidean distance) or k-NN ($k=3$) with distance threshold, firing immediately on first frame detection.
- **Alternatives Rejected**: Deep neural network retraining (rejected: too slow for 10-second calibration on local CPU).
- **Trade-Offs Accepted**: Single-frame classification is vulnerable to momentary facial twitches.
- **Verification & Reconsideration**: Evaluated directly against Condition C in replay harness.

---

## ADR-027: Prohibition of Shell, Dynamic Eval, and Arbitrary Macros
- **Context & Problem**: Security risks in assistive tech often arise from scripting bridges allowing arbitrary command injection.
- **Decision Made**: Strict prohibition of `eval()`, `exec()`, subprocess shell invocation, or dynamic code execution in user profiles or action dispatch.
- **Alternatives Rejected**: Allowing user-written Python action scripts (rejected: unacceptable security hazard).
- **Trade-Offs Accepted**: Advanced automation requires pre-compiled internal actions.
- **Verification & Reconsideration**: Codebase scan and security tests verifying zero dynamic execution.

---

## ADR-028: PyInstaller One-Folder Distribution Packaging
- **Context & Problem**: The research prototype must be distributable as a standalone Windows application without requiring manual Python installation by clinicians.
- **Decision Made**: Package using PyInstaller in one-folder mode (`dist/morph/morph.exe`) bundling the local MediaPipe task asset and licenses.
- **Alternatives Rejected**: Requiring user git-clone and pip install (rejected: inaccessible for non-technical clinical evaluators).
- **Trade-Offs Accepted**: Distribution bundle size is ~200MB.
- **Verification & Reconsideration**: Build verification script and offline launch smoke test.

---

## ADR-029: Screen Reader Accessibility through Accessible Names and Roles
- **Context & Problem**: Users with visual or dual impairments need screen reader announcements for phrase selection and tracking status.
- **Decision Made**: Set explicit `accessibleName` and `accessibleDescription` on all Qt widgets and communication tiles.
- **Alternatives Rejected**: Visual-only indicators (rejected: inaccessible).
- **Trade-Offs Accepted**: Requires maintaining accessibility attributes alongside UI styling.
- **Verification & Reconsideration**: Automated inspection of widget accessibility properties in test suite.

---

## ADR-030: Separation of Synthetic Benchmark Fixtures from Clinical Validation
- **Context & Problem**: Using synthetic unit test fixtures to claim real clinical accessibility validation is scientifically fraudulent.
- **Decision Made**: All automated test fixtures are explicitly labeled `SYNTHETIC_TEST_FIXTURE`. Clinical claims require documented human subject trials with ethical approval.
- **Alternatives Rejected**: Claiming algorithm is "clinically validated" based solely on developer tests (rejected: strictly prohibited).
- **Trade-Offs Accepted**: README and reports must honestly state that developer benchmarks are exploratory engineering tests.
- **Verification & Reconsideration**: Traceability documentation audits.

---

## ADR-031: Proactive Gesture Collision and Ambiguity Detection Service
- **Context & Problem**: When users train up to three personalized gestures, two movements (e.g. mouth opening vs chin raise) may yield highly correlated normalized displacement vectors, resulting in frequent misclassifications or ambiguity rejections during operation.
- **Decision Made**: Implement `GestureConflictDetector` to analyze pairwise cosine similarity and Euclidean distance on normalized 32-D vectors during enrollment. Classify severity into `NONE` (<0.70), `POTENTIAL` (0.70–0.85), `STRONG` (>=0.85), and `INSUFFICIENT_DATA` (<3 samples). Display actionable recommendations in `StudioView` without automatically deleting either gesture.
- **Alternatives Rejected**: Silent automatic rejection/deletion of gestures (rejected: disempowers user; reduces agency); uncalibrated probability estimates (rejected: cosine similarity on unit sphere is geometrically meaningful and directly matches recognizer math).
- **Trade-Offs Accepted**: Users must review warnings and make informed trade-offs or practice in sandbox mode.
- **Verification & Reconsideration**: Tested across identical, distinct, and noisy synthetic gesture samples in `tests/unit/test_conflict.py`.

---

## ADR-032: Cross-Session Calibration Drift Detection and Immutable Version Rollback
- **Context & Problem**: When launching a saved profile across sessions, physical camera placement or user posture variations shift normalized baseline coordinates. Blindly using an outdated baseline causes recognition failures or unwanted activations. Unsupervised retraining on unverified live frames risks corrupting working profiles.
- **Decision Made**: Implement `DriftDetector` and `ProfileVersionManager`:
  1. Compare session-start neutral frames against reference neutral landmarks scaled by $D_{eye}$.
  2. Classify status into `STABLE` (<8% shift), `MODERATE_DRIFT` (8–16%), and `SEVERE_DRIFT` (>=16% or rest posture overlaps a gesture prototype).
  3. Strictly prohibit clinical or diagnostic claims: explanations explicitly cite camera angle, distance, or posture.
  4. Store recalibrations as immutable version snapshots in SQLite `profile_versions`. New recalibrations begin as `CANDIDATE` and require explicit user validation before promotion.
  5. Provide atomic rollback to any prior validated version.
- **Alternatives Rejected**: Continuous automatic background retraining on unlabeled runtime frames (rejected: severe risk of model degradation and silent failure).
- **Trade-Offs Accepted**: Requires a 1–2 second neutral posture check at session start when drift is suspected.
- **Verification & Reconsideration**: Unit tests in `tests/unit/test_adaptation.py` verifying drift classification, non-medical messaging invariants, and atomic rollbacks.

---

## ADR-033: Formal Transition Specification, Temporal Correctness, and Structured Reason Codes in IntentEngine
- **Context & Problem**: Intention gating must not depend on fixed frame rates, must withstand camera starvation or jitter, must avoid rearming without returning to neutral, and must provide transparent explainability for rejected or accepted commands.
- **Decision Made**:
  1. Formalize legal state transitions between `PAUSED`, `TRACKING_LOST`, `IDLE`, `CANDIDATE`, `CONFIRMED`, `COOLDOWN`.
  2. Implement strict monotonic timestamp checks: clock regressions (`now_ns < last_now_ns`) are safely dropped with `REJECTED_CLOCK_REGRESSION`.
  3. Frame gaps exceeding 500ms cancel active candidates with `REJECTED_FRAME_GAP` to prevent stale executions across stream interruptions.
  4. Ambient neutral release dwell ($T_{release} = 150$ms) and cooldown ($T_{cooldown} = 300$ms) must both be satisfied before re-arming to `IDLE`.
  5. Structured reason codes (`DecisionReason`) record the exact cause for every frame decision.
- **Alternatives Rejected**: Ad-hoc counter-based debounce without formal states (rejected: prone to race conditions and double dispatches).
- **Trade-Offs Accepted**: Intent state machine requires discrete timestamped steps.
- **Verification & Reconsideration**: Verified across all edge cases in `tests/unit/test_intent_hardening.py` and `tests/unit/test_intent_engine.py`.

---

## ADR-034: Fair Debounced Event-Level Comparison Baseline and Multi-Factor Ablation Protocol
- **Context & Problem**: Evaluating Condition B by dispatching on every matching video frame artificially degrades the baseline, creating a strawman comparison. A realistic assistive recognizer implements basic debouncing. To prove the true value of intention gating, Condition B must represent a fair debounced event trigger.
- **Decision Made**:
  1. Condition B uses `ConventionalDebouncedDispatcher`: triggers once upon threshold crossing from neutral, and suppresses duplicate firings while held.
  2. Condition C uses identical personalized predictions with the full IntentEngine FSM.
  3. Include systematic ablations: No Hold ($T_{hold}=0$), No Release ($T_{rel}=0$), and No Margin ($min\_margin=0$).
  4. Use standardized non-command exposure time in hours for FA/hr calculation, explicitly marking 0 denominators as undefined (`N/A`).
  5. Label synthetic test benchmarks explicitly as synthetic fixtures; require human participant trials for clinical claims.
- **Alternatives Rejected**: Frame-by-frame baseline evaluation (rejected: scientifically indefensible); dividing by arbitrary wall-clock execution constants (rejected: distorts true false alarm rate).
- **Verification & Reconsideration**: EXP-002 in `docs/EXPERIMENT_LOG.md` and automated tests in `tests/unit/test_evaluation.py`.

---

## ADR-035: Accessible First-Launch Onboarding Wizard, Error Recovery Banners, and Screen Reader Contracts
- **Context & Problem**: Motor-impaired users configuring an alternative input system face a bootstrapping barrier if setup requires precise mouse manipulation. Furthermore, silent failures or technical stack traces cause confusion.
- **Decision Made**:
  1. Implement `OnboardingView` guiding first-time users through privacy guarantees, posture alignment, rest calibration, 3-gesture training, and practice before launching into the communication board.
  2. Implement a global accessible recovery notification banner in `MainWindow` with explicit recovery action buttons for tracking loss, camera disconnects, or posture drift.
  3. Enforce WCAG 2.1 AA keyboard tab orders, 3px high-contrast focus rings (`#38BDF8`), and explicit screen reader attributes (`accessibleName`, `accessibleDescription`) across all widgets.
- **Alternatives Rejected**: Modal popup error dialogs that steal keyboard focus (rejected: disorienting for screen-reader users); silent error logging without UI feedback (rejected: unacceptable usability barrier).
- **Trade-Offs Accepted**: Requires keeping accessibility attributes synchronized with UI code updates.
- **Verification & Reconsideration**: Audited in `docs/MANUAL_VALIDATION_CHECKLIST.md` and automated in `tests/smoke/test_ui_smoke.py`.

---

## ADR-036: Pipeline Performance Instrumentation, Telemetry Telemetry, and 20-Point Extended Fault Injection Suite
- **Context & Problem**: To guarantee real-time safety and responsiveness on heterogeneous Windows hardware without memory leaks or frame stalling, the system requires granular telemetry for every stage and verification under severe edge cases.
- **Decision Made**:
  1. Implement `PerformanceMonitor` measuring rolling capture FPS, processing FPS, stage latencies (landmark, feature extraction, recognition, intent gating, dispatch, end-to-end), queue depth, dropped frames, stale frames, and working set memory usage.
  2. Integrate telemetry cards into `MonitorView` (S5 screen) and wire real-time monitoring into `MorphApplication`.
  3. Expand fault injection suite to cover 20 distinct failure modes in `tests/unit/test_extended_faults.py`: camera disconnect mid-stream, frame starvation / buffer overflow, out-of-order timestamps, clock regressions, rapid pause/resume cycles (>= 50), two faces in frame, missing face / tracking loss, corrupted NaN/Inf landmarks, missing model file, SQLite transaction lock & rollback, worker thread stop cleanup, slow inference stale-frame purge, identical timestamps, database schema mismatch, TTS engine failure fallback, bounded queue purge, long-duration 1,000-frame memory stability (< 15MB delta), rapid re-initialization flood (50 cycles), unauthorized action rejection, and sudden posture drift recalibration advice.
- **Alternatives Rejected**: Ad-hoc timing prints in console (rejected: not actionable for runtime health telemetry); relying on unit happy paths alone without negative fault-injection coverage (rejected: violates fail-closed safety requirement).
- **Trade-Offs Accepted**: Minimal CPU overhead (<0.1ms per frame) for timestamp recording and circular buffer updates.
- **Verification & Reconsideration**: Verified with 20 passing unit tests in `tests/unit/test_extended_faults.py` and integration in `src/morph/app.py`.

---

## ADR-037: Action Sandboxing, Path Sanitization, Structured Log Rotation, and Offline Privacy Enforcement
- **Context & Problem**: To guarantee patient privacy and host OS integrity, MORPH 2.0 must enforce strict offline boundaries (zero network egress), zero raw video persistence on disk, action sandboxing (no arbitrary process spawning), traversal-proof exports, and bounded log rotation.
- **Decision Made**:
  1. Implement `morph.common.security` with `audit_zero_video_storage()` verifying no video containers (`.mp4`, `.avi`, `.mov`, `.mkv`) are persisted on disk; camera frames exist exclusively in volatile memory buffers (`deque(maxlen=2)`).
  2. Implement `sanitize_export_path()` to validate all user or programmatic export targets against directory traversal attacks (`../`, device roots).
  3. Validate all dispatched commands against immutable `ActionType` allow-list; reject unauthorized strings with `SECURITY_REJECTION_ACTION_NOT_IN_ALLOW_LIST`.
  4. Implement `morph.common.logging` using `RotatingFileHandler` capped at 5MB per log file with 3 backups, emitting single-line structured JSON logs.
- **Alternatives Rejected**: Standard unrestricted file logging without rotation (rejected: unbounded disk growth risk); dynamic shell execution for external TTS or macros (rejected: severe remote code execution vulnerability).
- **Trade-Offs Accepted**: Export locations are restricted to safe directory hierarchies.
- **Verification & Reconsideration**: Audited and verified by 8 unit tests in `tests/unit/test_security_audit.py` and monkeypatched network isolation checks.

---

## ADR-038: Windows Packaging, Diagnostics Verification, Requirement Traceability & Release Gate Hardening
- **Context & Problem**: MORPH 2.0 must be distributable as a standalone Windows application containing its neural task assets (`face_landmarker.task`), offline TTS integration, and local SQLite databases without external Python runtime dependencies or internet connectivity.
- **Decision Made**:
  1. Implement automated one-folder packaging via PyInstaller bundling all dependencies, Qt plugins, and model assets into `dist/morph/`.
  2. Implement automated diagnostic validation via `scripts/doctor.ps1` verifying Python environment, core modules, MediaPipe task asset SHA-256 integrity, local SAPI TTS voices, and hardware camera DirectShow capture.
  3. Enforce strict requirement traceability accounting for all 56 PRD requirements (A01–A09, B01–B09, C01–C10, D01–D09, E01–E10, F01–F09) in `docs/REQUIREMENT_TRACEABILITY.md`.
- **Alternatives Rejected**: Web or electron wrapper (rejected: violation of offline safety and high latency overhead); shipping unverified binaries without checksum verification (rejected: violation of research reproducibility).
- **Trade-Offs Accepted**: Distribution folder size ~150MB due to PySide6 Qt dynamic libraries and MediaPipe dependencies.
- **Verification & Reconsideration**: Verified via `scripts/doctor.ps1` passing all 5 checks, clean PyInstaller packaging, and comprehensive requirement traceability.

---

## ADR-039: End-to-End Multi-Component Integration Verification and User Workflow Validation
- **Context & Problem**: Individual components (tracker, normalizer, recognizer, intent engine, dispatcher, database, profile versions) had high unit test coverage, but complete end-to-end user workflows spanning the full lifecycle required integrated automated verification across realistic user journeys.
- **Decision Made**:
  1. Implement `tests/integration/test_user_workflows.py` covering 5 complete user journeys:
     - **Workflow 1**: First-time user onboarding, calibration, 3-gesture training, geometric conflict check, communication board navigation, and safe pause suppression.
     - **Workflow 2**: Returning user loading validated profile, start-of-session drift check, practice trial dispatch sandboxing via `NoOpActionSink`, and live execution.
     - **Workflow 3**: Distribution shift detection, non-medical advice generation, candidate profile creation, unsatisfactory candidate evaluation, and atomic rollback to validated version.
     - **Workflow 4**: Mid-gesture tracking loss fail-close abort, re-arming conditions, and safe recovery to `IDLE`.
     - **Workflow 5**: Profile, gesture mapping, and version history persistence across application restart cycles.
  2. Maintain strict interface compatibility: `ProfileStore.get_profile_gestures` aliased to `get_gesture_classes`, explicit `GestureConflictDetector.check_all_pairs()`, and unified keyword arguments for immutable data structures.
- **Alternatives Rejected**: Manual manual-only testing of workflows (rejected: non-reproducible, prone to silent regressions); mocking the state machine in workflow tests (rejected: fails to verify real deterministic FSM transitions).
- **Trade-Offs Accepted**: Integration tests take ~7.3 seconds due to comprehensive temporal frame streaming across all 5 journeys.
- **Verification & Reconsideration**: Verified with 5 passing integration tests in `tests/integration/test_user_workflows.py`, running alongside all 97 existing unit tests (total 102 passing tests).

---

## ADR-040: Standardized Fixed-Baseline Compatibility, 20-Scenario Challenge Suite, and Exact Poisson Confidence Intervals
- **Context & Problem**: Condition A (`BaselineRecognizerA`) required rigorous multi-modal vector evaluation (checking geometric displacement and blendshapes). Short benchmark durations generated volatile rate estimates without uncertainty quantification.
- **Decision Made**:
  1. Update `BaselineRecognizerA` to evaluate both geometric displacement and blendshape indicators in the 32-D feature vector.
  2. Implement `poisson_rate_ci_95` in `src/morph/evaluation/metrics.py` computing exact Garwood Poisson 95% confidence intervals, with mathematical handling of zero-event counts using upper bound $-ln(0.05)/T \approx 3.0/T$.
  3. Expand synthetic benchmarks to 20 distinct challenge scenarios in `tests/fixtures/benchmark_scenarios.py` (rest, blinks, 60ms twitch, 120ms twitch, 3 deliberate holds, ambiguous blend, rapid pulse, yaw, pitch, roll, two-face occlusion, lighting drift, dropped frame burst, duplicate timestamps, clock regression, NaN corruption, scale reduction, and 3,000-frame conversational rest).
  4. Instrument stage latencies across video acquisition, inference, feature extraction, prototype classification, intent gating, and action dispatch.
- **Alternatives Rejected**: Assuming asymptotic Gaussian confidence intervals (rejected: invalid for near-zero or small event counts); arbitrarily inflating synthetic exposure times without statistical bounds (rejected: unscientific).
- **Trade-Offs Accepted**: Exact root-finding for Poisson CDF adds minimal calculation overhead (<0.1ms per benchmark run).
- **Verification & Reconsideration**: Verified in `tests/unit/test_evaluation.py` and logged in `docs/EXPERIMENT_LOG.md` (EXP-003).

---

## ADR-041: Controlled Evaluation Session Runner and Real-World Accessibility Study Protocol
- **Context & Problem**: Moving from synthetic benchmark validation to rigorous human research requires an accessible, privacy-preserving study session runner and an auditable, ethics-compliant study protocol for participants with motor impairments.
- **Decision Made**:
  1. Author `docs/REAL_WORLD_STUDY_PROTOCOL.md` defining a counterbalanced $3 \times 3$ Latin Square within-subject design, ethical safeguards, participant eligibility, 4 experimental task blocks, quantitative rate analysis via exact Poisson CIs, and subjective instruments (NASA-TLX, Borg CR10, SUS).
  2. Implement `src/morph/ui/evaluation_session_view.py` with anonymized participant identifier generation, explicit informed consent gating (disclosing zero raw video/audio persistence), guided stage runner with cued audiovisual prompts, manual/automated ground-truth timestamp recording, and instantaneous zero-residue session erasure.
  3. Integrate `EvaluationSessionView` into `MainWindow` navigation stack under route `"session"`.
- **Alternatives Rejected**: Relying on informal manual testing without synchronized ground-truth event logging (rejected: non-reproducible, untraceable); storing participant webcam recordings for post-hoc annotation (rejected: severe violation of patient privacy and zero-video storage invariant).
- **Trade-Offs Accepted**: Requires researcher or participant to acknowledge consent checkbox before trial recording can be initialized.
- **Verification & Reconsideration**: Verified via UI smoke lifecycle tests in `tests/smoke/test_ui_smoke.py::test_evaluation_session_view_lifecycle`.

---

## ADR-042: Accessible Interface Polishing, Motor Ergonomics, and Screen Reader Validation
- **Context & Problem**: To ensure accessibility compliance for users with motor impairments, touch targets must meet the $48\times 48$ px standard, high-contrast color ratios must exceed WCAG AAA (>7:1), focus rings must be visible, and screen reader announcements must accurately verbalize all interactive states.
- **Decision Made**:
  1. Enforce minimum $48\times 48$ px interactive targets across all views, with communication board tiles sized at $180\times 100$ px and global pause button at $220\times 52$ px.
  2. Maintain WCAG AAA contrast ratios (14.8:1 text contrast) and strict color independence using unicode symbols and explicit text labels.
  3. Expand `docs/MANUAL_VALIDATION_CHECKLIST.md` with complete 10-point screen reader audit, keyboard navigation matrix, touch target specifications, and live Windows Narrator step-by-step test script.
- **Alternatives Rejected**: Standard desktop button sizes (<32px) (rejected: inaccessible for motor tremor or touch interaction); color-only state badges (rejected: inaccessible for color vision deficiency).
- **Trade-Offs Accepted**: Larger buttons require careful grid spacing and scrolling support on compact displays.
- **Verification & Reconsideration**: Verified in `tests/smoke/test_ui_smoke.py` and audited in `docs/MANUAL_VALIDATION_CHECKLIST.md`.

---

## ADR-043: Explainable Live Diagnostics, FSM Decision Inspection, and Scientific Distance Telemetry
- **Context & Problem**: Accessibility practitioners and researchers require full transparency into why a gesture was accepted, delayed, or rejected. Mislabelling geometric distance metrics as "probabilities" introduces scientific inaccuracy.
- **Decision Made**:
  1. Enhance `MonitorView` (Screen S5) with a dedicated **Explainable Intention Gate & Geometric Distance Inspector**.
  2. Implement real-time FSM state badge (`IDLE`, `CANDIDATE`, `CONFIRMED`, `COOLDOWN`, `PAUSED`, `TRACKING_LOST`), active candidate display, hold timer progress bar (`X ms / 250 ms`), and structured decision reason enum strings (`DecisionReason.REJECTED_INSUFFICIENT_HOLD`, `REJECTED_AMBIGUOUS`, etc.).
  3. Display raw cosine similarities and Euclidean feature distances with explicit scientific disclaimers clarifying that values represent vector alignment and distance metrics, NOT statistical probabilities.
- **Alternatives Rejected**: Hiding classifier internals behind a binary pass/fail indicator (rejected: opaque, prevents debugging); presenting cosine similarity as a "confidence percentage" (rejected: statistically misleading).
- **Trade-Offs Accepted**: Additional UI elements in Monitor view require modular card layout.
- **Verification & Reconsideration**: Verified via `MonitorView.update_recognition_state()` in unit tests and manual inspection.

---

## ADR-044: Safe Hackathon Live Demonstration Workflow and Automated Preflight Checks
- **Context & Problem**: Demonstrating an accessibility research system in live hackathon and evaluation settings requires foolproof, predictable operation, instant hardware preflight verification, and a structured script that guides evaluators through core technical differentiators without risking unexpected state crashes.
- **Decision Made**:
  1. Implement `src/morph/ui/demo_view.py` with automated preflight diagnostics testing camera sensor (DirectShow / synthetic fallback), MediaPipe `face_landmarker.task` file presence (3.7MB), local Windows SAPI TTS voice availability, and FSM fail-closed initial safety invariant.
  2. Implement a 7-stage guided demonstration script with accompanying verbal talk-track guidance:
     - Stage 1: The Problem — Conventional Baseline Failures (200+ FA/hr)
     - Stage 2: Calibrated Neutral Resting Posture (5s scale-invariant baseline)
     - Stage 3: 3-Gesture Enrollment & Geometric Conflict Matrix (cosine separation)
     - Stage 4: Intention Gating Proof (60ms twitch rejection vs. 250ms hold confirmation)
     - Stage 5: Hands-Free Communication Board Navigation & Offline SAPI Speech
     - Stage 6: Posture Shift Detection, Non-Medical Advice & Atomic Rollback
     - Stage 7: Fail-Closed Safety & Emergency Spacebar/Esc Override
  3. Integrate `DemoView` into `MainWindow` navigation stack under route `"demo"`.
- **Alternatives Rejected**: Ad-hoc unguided demonstrations (rejected: high risk of skipping critical technical proofs or hitting uncalibrated states); mock video playback pretending to be live interaction (rejected: violates research integrity).
- **Trade-Offs Accepted**: Demonstration mode requires dedicated view footprint.
- **Verification & Reconsideration**: Verified via UI smoke tests in `tests/smoke/test_ui_smoke.py::test_demo_view_stages_and_preflight`.

---

## ADR-045: Pipeline Concurrency, Bounded Queue Backpressure, and Long-Duration Stress Resilience
- **Context & Problem**: Real-time gesture interaction pipelines (video capture, landmark inference, feature extraction, intention gating, UI dispatch, SQLite logging) are prone to race conditions, thread starvation, unbounded memory growth, and state corruption under sustained operation or rapid mode switching.
- **Decision Made**:
  1. Implement `src/morph/capture/queue.py::BoundedFrameQueue` using thread-safe synchronization (`threading.Condition`), strict capacity limits (e.g. 2 frames), and drop-oldest backpressure policy to guarantee zero producer deadlock and minimal processing latency.
  2. Implement 10,000-frame sustained pipeline stress testing verifying zero uncaught exceptions and memory stability (<25MB working set growth over 5.5 minutes of continuous 30 FPS processing).
  3. Validate multi-threaded SQLite database concurrency under simultaneous reader and writer workloads across independent profile version transactions, ensuring WAL mode atomicity and zero data corruption.
  4. Implement automated deep privacy audits inspecting repository working directories and OS temporary locations to guarantee zero persisted raw video or frame dump files.
  5. Validate state machine thrashing resilience across 100 rapid pause/resume cycles, ensuring the fail-closed invariant (`State.PAUSED`) is strictly maintained with zero spurious command dispatches.
- **Alternatives Rejected**: Unbounded frame queues (rejected: causes memory ballooning and pipeline latency lag if inference slows down); dropping newest frames (rejected: stale frames must never take precedence over current user posture).
- **Trade-Offs Accepted**: Drop-oldest frame shedding discards intermediate frames under high system load, which is mathematically preferable to delayed actuation in real-time assistive interfaces.
- **Verification & Reconsideration**: Verified via `tests/unit/test_stress_concurrency.py` (5 passed stress and concurrency tests).

---

## ADR-046: Release Packaging Verification, Headless Self-Test, and Automated Health Diagnostics
- **Context & Problem**: Distributing MORPH 2.0 as a production-grade, offline Windows desktop application requires verifiable packaging (`morph.exe`), reliable asset bundling (MediaPipe model task), automated pre-release health diagnostics, zero developer file leakage, and non-GUI automated verification capability.
- **Decision Made**:
  1. Implement a headless self-test flag (`--headless-check`) in `src/morph/__main__.py` with parent console attachment (`ctypes.windll.kernel32.AttachConsole(-1)`), validating model loading, SQLite database schema initialization, IntentEngine invariants, and action allow-lists without requiring a GUI window.
  2. Implement resilient multi-environment model resolution (`src/morph/capture/tracker.py::resolve_model_asset_path`), resolving `face_landmarker.task` across PyInstaller frozen bundles (`sys._MEIPASS`, `_internal/models`), repo roots, and working directories.
  3. Enhance `scripts/doctor.ps1` with 6 structured diagnostic checks (64-bit Python runtime, dependency integrity, model SHA-256 checksum match, Windows SAPI TTS voices, DirectShow camera backend with synthetic fallback, SQLite transactions) and a clean PASS/WARN/FAIL checklist.
  4. Implement `tests/smoke/test_distribution.py` verifying executable generation, bundled model existence, zero developer residue (`.git`, raw video captures), and execution of `--version` and `--headless-check`.
  5. Finalize `docs/RELEASE_CHECKLIST.md` and `CHANGELOG.md` covering all milestones M0 through M6.
- **Alternatives Rejected**: Relying solely on manual UI checks (rejected: error-prone and non-automatable); omitting headless diagnostics (rejected: prevents automated packaging verification).
- **Trade-Offs Accepted**: PyInstaller one-folder distribution requires a multi-megabyte bundle to achieve 100% offline self-containment with PySide6, OpenCV, and MediaPipe.
- **Verification & Reconsideration**: Verified via `scripts/doctor.ps1` (6/6 PASS), `scripts/package.ps1` (build SUCCESSFUL), and `tests/smoke/test_distribution.py` (3 passed tests).

---

## ADR-047: Canonical Time Exposure Definitions and Two-Sided Garwood Poisson Confidence Intervals
- **Context & Problem**: In Milestone M6, benchmark documentation cited 3,420 frames and 114 seconds informally, whereas `BenchmarkScenarioSuite` generated 3,520 frames spanning $t=1.000$s to $t=119.050$s ($T_{total} = 118.050$s). Ground truth commands occupied $4 \times 0.400 = 1.600$s, yielding valid non-command exposure $T_{non\_command} = 116.450$s ($0.032347$ hours). Comparing 116.45s to the informal 114s created an apparent paradox where non-command exposure seemed to exceed total duration. Furthermore, the Poisson confidence interval for zero events was referenced without distinguishing one-sided 95% upper confidence limits ($-\ln(0.05)/T \approx 2.996/T = 92.61$ FA/hr) from two-sided 95% Garwood intervals ($-\ln(0.025)/T \approx 3.689/T = 114.04$ FA/hr).
- **Decision Made**:
  1. Formulate and enforce strict mathematical invariant assertions in `src/morph/evaluation/metrics.py`:
     - $0 \le T_{intended} \le T_{total}$
     - $0 \le T_{non\_command} \le T_{total}$
     - $T_{non\_command} = T_{total} - T_{intended}$
     - $TP, FP, FN, TN_{approx} \ge 0$
  2. Implement `compute_merged_interval_duration_sec` in `metrics.py` and integrate it into `replay.py` to merge overlapping ground-truth command intervals before summation, mathematically preventing double-counting or negative non-command exposure.
  3. Update `poisson_rate_ci_95` to compute both the canonical two-sided 95% Garwood confidence interval (via exact Chi-Square quantiles / Poisson CDF root finding with $\alpha=0.05$, yielding $[0.00, 3.688879/T]$ for zero events) and the one-sided 95% upper limit ($2.995732/T$).
  4. Add unit tests in `tests/unit/test_metric_invariants.py` verifying exposure invariants, one-to-one bipartite matching, Poisson rate monotonicity, and JSON/CSV export reproducibility.
  5. Supersede EXP-003 with EXP-004 in `docs/EXPERIMENT_LOG.md` recording audited canonical durations and exact two-sided Garwood intervals.
- **Alternatives Rejected**: Relying on approximate frame counts instead of precise timestamp arithmetic (rejected: causes discrepancies); labeling one-sided upper limits as two-sided intervals (rejected: scientifically inaccurate).
- **Trade-Offs Accepted**: Two-sided Garwood interval upper bound for $k=0$ is higher (114.04 FA/hr vs 92.61 FA/hr for $T=116.45$s), reflecting conservative statistical honesty for short observation durations.
- **Verification & Reconsideration**: Verified via `tests/unit/test_metric_invariants.py` (5 tests passing) and `tests/unit/test_evaluation.py` (7 tests passing).

---

## ADR-048: Benchmark Dataset Integrity, Held-Out Generalization, and Hyperparameter Sensitivity Sweeps
- **Context & Problem**: Evaluating an accessibility intent classifier on the exact vector instances used during calibration introduces severe data leakage, inflating measured precision and masking real-world generalization failure. Furthermore, setting system hyperparameters (hold duration, refractory cooldown, classification margin) without empirical sensitivity sweeps leaves trade-offs uncharacterized.
- **Decision Made**:
  1. Separate calibration enrollment trials from held-out evaluation scenarios in `tests/fixtures/benchmark_scenarios.py` and `tests/fixtures/synthetic_faces.py`. Calibration prototypes use simulated enrollment poses with canonical baseline scale, while evaluation sequences feature held-out physiological shifts (scale offsets, subtle yaw/pitch angles, natural timing variance, micro-jitter).
  2. Implement `verify_zero_leakage` computing pairwise Euclidean distance matrices between all valid evaluation vectors and calibration prototype vectors, enforcing a zero-leakage invariant ($\min \|v_{eval} - v_{cal}\|_2 > 10^{-4}$).
  3. Implement `src/morph/evaluation/sensitivity.py` executing a 120-configuration sweep across hold times (150–400ms), refractory cooldowns (150–500ms), and classification margins (0.05–0.25), exporting telemetry to `research/benchmarks/parameter_sensitivity.json` and human-readable analysis to `docs/PARAMETER_SENSITIVITY.md`.
  4. Confirm that hold times $\le 120$ms breach involuntary twitch immunity thresholds, while hold times $\ge 150$ms robustly reject twitches, validating the optimality of MORPH 2.0's 250ms default.
  5. Add automated unit tests in `tests/unit/test_dataset_holdout.py` and `tests/unit/test_parameter_sensitivity.py`.
- **Alternatives Rejected**: Reusing identical prototypes in both calibration and evaluation (rejected: invalidates generalization claims); omitting sensitivity analysis (rejected: unsupported engineering defaults).
- **Trade-Offs Accepted**: Held-out perturbations introduce realistic cosine similarity variance (~0.85–0.95 vs. 1.00), faithfully modeling real-world human motor variance.
- **Verification & Reconsideration**: Verified via `tests/unit/test_dataset_holdout.py` (4 passed tests), `tests/unit/test_parameter_sensitivity.py` (3 passed tests), `research/benchmarks/parameter_sensitivity.json`, and `docs/PARAMETER_SENSITIVITY.md`.

---

## ADR-049: Explicit Optical Sensor Source Modes and Physical Camera Validation Trace
- **Context & Problem**: To prevent misleading claims about live webcam interaction vs. synthetic fixtures or replay streams, the architecture must explicitly tag and expose the active input sensor provenance. Furthermore, the physical optical capture path (DirectShow, exposure latency, MediaPipe landmarker inference on local CPU) must be directly validated and auditable without violating the transient zero-video persistence privacy invariant.
- **Decision Made**:
  1. Define a strongly typed `SourceMode` enum in `src/morph/common/types.py`: `PHYSICAL_CAMERA`, `RECORDED_REPLAY`, `SYNTHETIC_FIXTURE`, `CAMERA_UNAVAILABLE`.
  2. Embed `source_mode` directly in `TrackingHealth`, `ICameraAdapter`, `OpenCVCameraAdapter`, and `SimulatedCameraAdapter`.
  3. Ensure `CaptureWorker` propagates the active `source_mode` through UI health signals, with visual provenance indicators in `HomeView` and `MonitorView`.
  4. Implement `scripts/validate_physical_camera.py` executing 30-frame live optical validation on DirectShow camera index 0 (Integrated Camera), capturing shutter/transfer latency (mean 83.5ms, p50 78.0ms, p95 110.0ms) and local MediaPipe inference latency (mean 14.9ms, p50 15.0ms, p95 31.5ms) with zero frame storage on disk, exporting `docs/PHYSICAL_CAMERA_VALIDATION.md`.
  5. Validate the complete 5-stage interactive user journey (enrollment, neutral calibration, AAC board navigation, Windows SAPI TTS, spacebar emergency stop) in `tests/unit/test_end_to_end_journey.py` and source mode telemetry in `tests/unit/test_physical_camera_source_mode.py`.
- **Alternatives Rejected**: Undifferentiated camera feeds where synthetic fixtures and live cameras look identical in telemetry (rejected: obscures validation provenance); storing raw validation video clips for debugging (rejected: breaches ADR-002 privacy invariant).
- **Trade-Offs Accepted**: Live optical capture requires DirectShow device initialization and adds non-deterministic frame interval jitter (~33–110ms), handled cleanly via thread-safe bounded queues.
- **Verification & Reconsideration**: Verified via `scripts/validate_physical_camera.py`, `docs/PHYSICAL_CAMERA_VALIDATION.md`, `tests/unit/test_physical_camera_source_mode.py` (3 tests), and `tests/unit/test_end_to_end_journey.py` (5 tests).

---

## ADR-050: Strict Asset Resolution Isolation in Frozen Bundles and Independent Packaging Verification
- **Context & Problem**: In desktop software packaging, if asset resolution logic falls back to developer checkout paths or current working directories when bundled assets are missing, packaging tests will falsely pass in development environments while failing catastrophically on end-user machines.
- **Decision Made**:
  1. Modify `src/morph/capture/tracker.py::resolve_model_asset_path` so that when `getattr(sys, "frozen", False)` is True, it strictly searches only the PyInstaller bundle paths (`sys._MEIPASS` or `Path(sys.executable).parent / "_internal" / "models"` / `models`).
  2. If the model asset is missing from the frozen bundle, immediately raise `FileNotFoundError` with explicit diagnostic messages, strictly preventing silent fallback to developer source trees or current working directory relative paths.
  3. Rebuild the standalone Windows distribution via `scripts/package.ps1` with verified one-folder output `dist/morph/`.
  4. Implement `test_distribution_relocation_execution` in `tests/smoke/test_distribution.py`, executing `morph.exe --headless-check` in an isolated temporary directory with `PYTHONPATH` cleared from the environment, verifying true relocation independence.
  5. Add unit tests in `tests/unit/test_camera_tracker.py` validating that frozen simulation enforces bundle isolation and rejects missing assets without developer fallback.
- **Alternatives Rejected**: Permitting fallback to `C:\Pratham\MORPH` in production binaries (rejected: creates false confidence in dev while failing on target machines); requiring users to manually configure model paths (rejected: poor accessibility UX).
- **Trade-Offs Accepted**: Bundled model asset must be packaged in `--add-data "models;models"`, increasing bundle size by ~3.7MB, which is negligible for modern desktop systems.
- **Verification & Reconsideration**: Verified via `tests/unit/test_camera_tracker.py` (6 tests passing) and `tests/smoke/test_distribution.py` (4 tests passing, including isolated relocation check).

---

## ADR-051: Continuous Interaction Rest Advisor, Accessible Narrator Support, and Demonstration Stage Recovery
- **Context & Problem**: Individuals using facial gesture AAC software are susceptible to muscular fatigue and strain during prolonged communication sessions (PRD D09). Without an automatic, non-intrusive reminder system, fatigue can degrade user comfort and trigger involuntary twitches. Furthermore, live hackathon demonstrations require reliable stage navigation and immediate recovery controls (keyboard stage shortcuts, reset, fail-closed pause) without risking stuck UI states.
- **Decision Made**:
  1. Implement `src/morph/ui/rest_advisor.py::RestAdvisor` monitoring continuous active communication time. When continuous interaction reaches 20 minutes (configurable), trigger an accessible, non-medical rest notification banner: "Rest Advisory: Continuous interaction for X min. Regular breaks help prevent muscle fatigue. [Take a Break] [Dismiss]".
  2. Selecting "Take a Break" immediately executes a safe fail-closed pause (`State.PAUSED`), resets the active duration accumulator, and dismisses the banner. Selecting "Dismiss" snoozes the alert for 5 minutes.
  3. Ensure active time accumulation automatically freezes whenever the system is in `PAUSED` or `TRACKING_LOST` states, preventing false fatigue alerts while resting.
  4. Enhance `DemoView` with dedicated keyboard presentation controls (`Right Arrow` for Next Stage, `Left Arrow` for Previous Stage, `R` for Reset, alongside global `Spacebar` / `Escape` overrides), plus accessible descriptions for screen readers.
  5. Document Windows Narrator audit procedures, keyboard traversal, and WCAG 2.1 AAA color contrast ratios in `docs/ACCESSIBILITY_AUDIT.md`.
  6. Provide verbatim stage scripts, talking tracks, and contingency recovery protocols in `docs/DEMO_GUIDE.md`.
- **Alternatives Rejected**: Intrusive modal pop-ups that block the screen (rejected: disruptive to AAC users); diagnosing medical muscle fatigue (rejected: violates non-medical ethical boundary).
- **Trade-Offs Accepted**: A top notification banner takes minimal vertical space (~40px) when active, dismissible with one click or Escape.
- **Verification & Reconsideration**: Verified via `tests/unit/test_rest_advisor.py` (6 tests passing), `tests/smoke/test_ui_smoke.py` (4 tests passing), `docs/ACCESSIBILITY_AUDIT.md`, and `docs/DEMO_GUIDE.md`.

---

## ADR-052: Microsecond Multi-Stage Pipeline Telemetry, Hardware Optical Separation, and Sustained Empirical Performance Benchmarking
- **Context & Problem**: Preliminary physical camera validation tested 30 frames and reported ~83.5 ms capture latency and ~14.9 ms inference, leaving unresolved whether effective frame rate was bottlenecked by MediaPipe inference, bounded queue contention, UI presentation, or camera driver shutter wait. Furthermore, standard `time.monotonic_ns()` on Windows relies on `GetTickCount64()` with a 15.625 ms tick interval, quantizing microsecond-scale stages (feature extraction, recognition, intent state machine) to zero.
- **Decision Made**:
  1. Migrate all internal stage timing from `time.monotonic_ns()` to `time.perf_counter_ns()`, delivering true 100-nanosecond precision via Windows `QueryPerformanceCounter` (QPC).
  2. Implement `src/morph/capture/instrumentation.py::PipelineStageTelemetry` capturing decoupled timestamps across every stage: camera driver read start (`t_read_start`), sensor delivery (`t_capture`), queue insertion (`t_queue_insert`), queue retrieval (`t_queue_remove`), MediaPipe inference (`t_infer_start`/`end`), feature extraction (`t_features_start`/`end`), recognition (`t_recog_start`/`end`), intent evaluation (`t_intent_start`/`end`), action dispatch (`t_dispatch_start`/`end`), and UI acknowledgment (`t_ui_ack`).
  3. Implement `SustainedPerformanceTracker` providing exact sample counts ($N$), min, mean, P50, P90, P95, P99, and max metrics for all pipeline stages, tracking throughput (FPS), queue occupancy, frame drop/stale counts, single-core process CPU %, system-normalized CPU %, and working set RAM MB.
  4. Develop `scripts/measure_sustained_performance.py` supporting configurable test durations (e.g. 60s, 900s), capture resolutions (`640x480`, `1280x720`), capture backends (`dshow`, `msmf`), and comparative execution modes (`physical`, `capture_only`, `inference_only`, `synthetic`).
  5. Execute 60-second empirical physical test ($N=600$ physical frames) on DirectShow Camera 0 and export `research/benchmarks/sustained_performance.json` and `docs/PHYSICAL_PERFORMANCE_REPORT.md`.
- **Alternatives Rejected**: Combining independently averaged stage latencies to represent end-to-end latency (rejected: scientifically inaccurate under concurrency); conflating camera sensor exposure with software computation (rejected: misidentifies hardware shutter pacing as algorithmic inefficiency); persisting video frames to disk for post-run analysis (rejected: strictly prohibited by ADR-002 privacy invariant).
- **Trade-Offs Accepted**: A physical optical sensor operating under indoor auto-exposure delivers ~10 FPS (P50 read blocking ~82.08 ms). The pipeline gracefully accommodates this pacing without dropping frames or building queue latency. Decoupled inference-only replay demonstrates the algorithmic pipeline operates at 39.28 FPS.
- **Verification & Reconsideration**: Verified via 60-second live physical run ($N=600$ frames): MediaPipe P50 = 15.91 ms (P95 = 19.89 ms), Feature Extraction P95 = 0.085 ms, Recognition P95 = 0.025 ms, Intent Decision P95 = 0.022 ms, Sensor-to-Decision P95 = 20.36 ms, Queue Occupancy = 1 frame (0 dropped, 0 stale, 0 out-of-order), single-core CPU = 26.4% (3.3% system-normalized across 8 cores), Working Set RAM = 186.75 MB mean / 187.39 MB peak. Documented in `docs/PHYSICAL_PERFORMANCE_REPORT.md` and `research/benchmarks/sustained_performance.json`.

---

## ADR-053: User-Specific Guided Parameter Calibration with Multi-Objective Trade-Off Balancing and Version Rollback
- **Context & Problem**: The default intention gating parameters ($T_{hold} = 300\text{ ms}$, $T_{release} = 150\text{ ms}$, $T_{cooldown} = 300\text{ ms}$, similarity threshold $= 0.65$, margin $= 0.15$) were conservatively selected based on synthetic sensitivity studies. However, individuals with diverse motor etiologies exhibit varying contraction amplitudes, involuntary twitch durations, and fatigue thresholds. Static universal parameters lead to either excessive holding fatigue (for quick, low-stamina users) or accidental activations (for spasticity-prone users).
- **Decision Made**:
  1. Implement `src/morph/calibration/evaluator.py::UserParameterCalibrator` providing guided parameter evaluation over a permitted search grid ($T_{hold} \in [150, 600]\text{ ms}$, $T_{release} \in [100, 300]\text{ ms}$, $T_{cooldown} \in [200, 600]\text{ ms}$, similarity $\in [0.50, 0.85]$, margin $\in [0.05, 0.30]$).
  2. Evaluate candidates against user-recorded practice samples using a multi-objective composite objective function balancing sensitivity, false activation penalty, user holding comfort, and latency: $\text{Composite} = 0.40 \cdot \text{Recall} + 0.35 \cdot (1 - \text{FA\_Penalty}) + 0.15 \cdot \text{Comfort} + 0.10 \cdot \text{Latency\_Factor}$.
  3. Enforce data sufficiency checks ($\ge 3$ intended samples and $\ge 1.0\text{ s}$ non-command exposure required; else `INSUFFICIENT_DATA`), feature conflict detection (`CONFLICTING_DATA`), and global failure classifications (`ALL_MISSED`, `EXCESSIVE_FALSE_ACTIVATIONS`).
  4. Preserve zero silent updates: parameter sets are stored in SQLite `profile_versions` with status `CANDIDATE` and require explicit user acceptance via `SettingsView` before promotion to `VALIDATED`.
  5. Provide instant atomic version rollback to prior validated snapshots via `ProfileVersionManager.rollback_to_version()`.
  6. Include mandatory non-clinical research prototype disclaimers across UI, code, and documentation.
- **Alternatives Rejected**: Automating silent threshold adjustments based on live unlabeled streaming (rejected: risks runaway drift and unexpected command changes); optimizing solely for zero false alarms (rejected: favors infinite hold time and 0% recall); medicalizing parameter calibration (rejected: violates non-clinical research boundaries).
- **Trade-Offs Accepted**: Users must spend ~30 seconds recording practice gestures and neutral rest to obtain personalized recommendations.
- **Verification & Reconsideration**: Verified via `tests/unit/test_parameter_calibration.py` (7 tests passing), `docs/PARAMETER_CALIBRATION_REPORT.md`, and integration in `SettingsView`.







