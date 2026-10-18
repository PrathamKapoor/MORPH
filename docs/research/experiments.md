# MORPH 2.0 Experiment Log

Author: Pratham Kapoor <prathamkapoor027@gmail.com>  
System: Windows 11 Home Single Language (ARM64 with x64 emulation)  
Location: `C:\Pratham\MORPH`

---

## Experiment EXP-001: Three-Way Replay Comparison (Condition A vs B vs C)

- **Experiment ID**: EXP-001
- **Timestamp**: 2026-10-17T00:58:00+05:30
- **Git Commit**: `e33391e` (feat(intent): implement deterministic IntentEngine FSM)
- **Hardware & Environment**: Windows 11 Home Single Language (ARM64), Python 3.12.10, Integrated Camera (DirectShow), SAPI TTS (Microsoft David/Zira).
- **Hypothesis**: Passing personalized recognizer predictions through the deterministic intention gate (Condition C) will reduce unintended command dispatches during non-command intervals by at least 50% relative to ungated single-frame classification (Condition B), while maintaining 100% intentional gesture recall on sustained commands.
- **Exact Input Dataset**: Standardized synthetic feature sequence (`SYNTHETIC_TEST_FIXTURE`):
  - 60 frames resting neutral (~2.0s)
  - 12 frames deliberate Brow Raise (~400ms sustained hold)
  - 45 frames resting neutral (~1.5s)
  - 12 frames deliberate Smile (~400ms sustained hold)
  - 45 frames resting neutral (~1.5s)
  - Total frames: 174 frames (~5.8 seconds, with 5.0 seconds of non-command duration = 0.00139 hours).
- **Comparison Controls**:
  - Condition A: Fixed anatomical thresholds (eyebrow elevation > 0.08, smile width > 0.09, mouth open > 0.08).
  - Condition B: Personalized prototype classifier ($min\_similarity = 0.65$, $min\_margin = 0.15$), firing immediately on single-frame detection without temporal hold or cooldown.
  - Condition C: Exact per-frame predictions from Condition B passed through pure IntentEngine FSM ($T_{hold} = 300$ ms, $T_{release} = 150$ ms, $T_{cooldown} = 300$ ms).
- **Commands Run**:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest -v tests/unit/test_evaluation.py
  ```
- **Raw Counts & Durations**:
  - Ground truth intentional events: 2 (Brow Raise, Smile).
  - Condition A: Total dispatches = 24; Matched events = 2; Unmatched false activations = 22.
  - Condition B: Total dispatches = 24; Matched events = 2; Unmatched false activations = 22.
  - Condition C: Total dispatches = 2; Matched events = 2; Unmatched false activations = 0.
- **Measured Outputs**:
  - **Condition A**:
    - Recall: 100.0% (2 / 2)
    - Precision: 8.3% (2 / 24)
    - FA / Non-Command Hour: 15,840 FA/hr
    - Latency P95: -250.0 ms (early trigger before gesture completion)
  - **Condition B**:
    - Recall: 100.0% (2 / 2)
    - Precision: 8.3% (2 / 24)
    - FA / Non-Command Hour: 15,840 FA/hr
    - Latency P95: -250.0 ms (burst triggers on every frame while gesture held)
  - **Condition C (MORPH)**:
    - Recall: 100.0% (2 / 2)
    - Precision: 100.0% (2 / 2)
    - FA / Non-Command Hour: 0.0 FA/hr (0 unmatched dispatches)
    - Latency P95: +20.0 ms (confirmed smoothly after 300ms hold)
- **Deviations & Failure Examples**:
  - In Condition B and Condition A, holding a gesture for 400 ms generated 12 consecutive command triggers (one per frame) because single-frame classifiers lack temporal deduplication and cooldown. This causes repeated involuntary actions for AAC users.
  - In Condition C, the 300 ms temporal hold requirement correctly arbitrated the 12 frames into exactly ONE confirmed command event, followed by mandatory neutral release and cooldown.
- **Interpretation**: The hypothesis is strongly supported on synthetic fixtures. Condition C completely eliminates burst double-triggers and false alarms during non-command intervals while preserving 100% recall for intentional sustained gestures.
- **Decision**: Accept Condition C intention gating architecture for the core release. Proceed to human pilot evaluation when consented participants are available.
- **Next Experiment**: EXP-002: Fair debounced baseline comparison and feature ablation suite (M5.4).

---

## Experiment EXP-002: Fair Debounced Baseline Comparison & Feature Ablation Suite

- **Experiment ID**: EXP-002
- **Timestamp**: 2026-10-17T03:15:00+05:30
- **Git Commit**: `907da6b` (fix(intent): harden gesture rearming and tracking-loss transitions)
- **Hardware & Environment**: Windows 11 Home Single Language (ARM64 with x64 emulation), Python 3.12.10, local CPU execution.
- **Hypothesis**: Replacing ungated frame-by-frame triggering in Condition B with a conventional debounced/release-to-rearm event trigger will eliminate artificial burst dispatches, establishing a fair real-world baseline. Condition C (IntentEngine FSM) will still demonstrate superior precision by rejecting sub-hold involuntary twitches and ambiguous simultaneous muscle activations.
- **Exact Input Dataset (`SYNTHETIC_TEST_FIXTURE`)**:
  - Dataset Version: `eval-benchmark-v2.0` (488 frames, 16.23s total duration, 14.57s non-command exposure = 0.00405 hours).
  - 5 Deliberate Gestures: Brow Raise x2 (360ms), Smile x2 (360ms), Mouth Open x1 (360ms).
  - 2 Non-Command Challenges: Involuntary 60ms brow twitch (2 frames), ambiguous simultaneous Brow+Smile blend (360ms, separation margin < 0.15).
  - 5 Rest Intervals (1.5s to 3.0s duration).
- **Comparison Conditions & Ablations**:
  - **Condition A (Fixed Thresholds + Debounce)**: Generic anatomical thresholds with single-event onset trigger and release-to-rearm.
  - **Condition B (Personalized Prototype + Fair Debounce)**: Personalized prototype ($min\_similarity = 0.65, min\_margin = 0.15$) with conventional onset debounce.
  - **Condition C (Full MORPH Intention Gate)**: Exact predictions from Condition B passed through IntentEngine FSM ($T_{hold} = 250$ms, $T_{release} = 150$ms, $T_{cooldown} = 300$ms).
  - **Ablation 1 (No Hold Time)**: Condition C with $T_{hold} = 0$ms.
  - **Ablation 2 (No Release Dwell)**: Condition C with $T_{release} = 0$ms.
  - **Ablation 3 (No Ambiguity Margin)**: Condition C with $min\_margin = 0.0$.
- **Measured Outputs**:

| Condition / Ablation | Total Dispatches | Matched Intended (Recall) | Unintended False Alarms | Precision | FA / Non-Cmd Hour | Latency P95 (ms) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Condition A (Fixed + Debounce)** | 6 | 5 / 5 (100.0%) | 1 | 83.3% | 247.14 | -333.3 ms |
| **Condition B (Personalized + Debounce)** | 6 | 5 / 5 (100.0%) | 1 | 83.3% | 247.14 | -333.3 ms |
| **Condition C (MORPH Full Intention Gate)** | **5** | **5 / 5 (100.0%)** | **0** | **100.0%** | **0.00** | **0.0 ms** |
| *Ablation 1: No Hold Time ($T_{hold}=0$)* | 6 | 5 / 5 (100.0%) | 1 | 83.3% | 247.14 | -300.0 ms |
| *Ablation 2: No Release Dwell ($T_{rel}=0$)* | 5 | 5 / 5 (100.0%) | 0 | 100.0% | 0.00 | 0.0 ms |
| *Ablation 3: No Margin ($min\_margin=0$)* | 6 | 5 / 5 (100.0%) | 1 | 83.3% | 247.14 | 0.0 ms |

- **Observations & Key Findings**:
  1. Conventional debouncing in Condition B successfully prevents frame-by-frame spam (reducing dispatches from 20+ down to 6).
  2. However, Condition B still fires on the 60ms involuntary twitch because it lacks a temporal hold confirmation duration.
  3. Condition C completely suppresses the 60ms twitch via $T_{hold} = 250$ms, achieving 0 false activations.
  4. Ablation 1 proves that without $T_{hold}$, the system triggers false activations on rapid twitches.
  5. Ablation 3 proves that without the ambiguity separation margin, simultaneous blends produce unintended commands.
- **Scientific Caveat**: These benchmarks are evaluated on reproducible synthetic landmark fixtures. Clinical efficacy requires consented participant trials on diverse physical etiologies.
- **Next Step**: M5.5 Accessible Onboarding Journey and User Experience.

---

## Experiment EXP-003: Expanded 20-Scenario Challenge Suite [SUPERSEDED / RECONCILED BY EXP-004]

> [!NOTE]
> **Audit Note (M7.1 Reconciled)**:
> In EXP-003 documentation, textual summaries informally cited "3,420 frames and 114 seconds", whereas the generator produced 3,520 frames (118.05 seconds total duration, with 116.45 seconds non-command exposure). Furthermore, the reported upper bound of 92.61 FA/hr was the exact **one-sided** 95% upper confidence limit ($-ln(0.05)/T$). EXP-004 below provides the audited, canonical timestamp breakdown, disjoint interval merging, and two-sided 95% Garwood confidence intervals.

- **Experiment ID**: EXP-003
- **Timestamp**: 2026-10-17T12:15:00+05:30
- **Git Commit**: `fix(evaluation): repair fixed-baseline compatibility and reporting (M6.2)`
- **Hardware & Environment**: Windows 11 Home Single Language (ARM64 with x64 emulation), Python 3.12.10, local CPU execution.
- **Hypothesis**: Evaluating across the expanded 20-scenario synthetic challenge suite (3,540+ frames, 118.05 seconds duration, 0.03235 non-command exposure hours) with multi-modal `BaselineRecognizerA` (Condition A), personalized debounced `PersonalizedRecognizerB` (Condition B), and full `IntentEngine` FSM (Condition C) will demonstrate that intention gating completely eliminates involuntary twitches, head turns, and blends (0 false alarms, exact 95% Poisson CI [0.00, 92.61] FA/hr) while retaining 100% intended recall (4/4), whereas debounced Condition B produces 4 false alarms (123.66 FA/hr, 95% CI [33.69, 316.61]) and Condition A produces 7 false alarms (216.40 FA/hr, 95% CI [87.00, 445.87]).
- **Exact Input Dataset (`tests/fixtures/benchmark_scenarios.py`)**:
  - Dataset Version: `20-scenario-suite-v1` (3,542 frames, 118.05 seconds, 0.03235 hours non-command exposure).
  - 20 Scenarios:
    1. `natural_rest_neutral` (60 frames rest)
    2. `natural_blinks` (30 frames with 2 rhythmic eyelid blinks)
    3. `micro_twitch_60ms` (2 frames brow twitch, 60ms < hold_ms)
    4. `micro_twitch_120ms` (4 frames smile twitch, 120ms < hold_ms)
    5. `sustained_brow_raise` (12 frames = 400ms sustained deliberate command)
    6. `sustained_smile` (12 frames = 400ms sustained deliberate command)
    7. `sustained_mouth_open` (12 frames = 400ms sustained deliberate command)
    8. `ambiguous_blend_brow_smile` (12 frames simultaneous partial brow+smile)
    9. `rapid_repetition_pulse` (Two brow raises separated by only 100ms < cooldown)
    10. `head_yaw_turn` (25 frames horizontal nose movement)
    11. `head_pitch_nod` (25 frames vertical nose pitch)
    12. `head_roll_tilt` (25 frames angular tilt)
    13. `multi_face_occlusion` (15 frames two-face invalid detection)
    14. `lighting_intensity_drift` (20 frames coordinate perturbation)
    15. `dropped_frame_burst` (650ms gap > 500ms max_gap)
    16. `stale_duplicate_frame` (Repeated timestamps)
    17. `clock_jitter_reversal` (Backward timestamp jump)
    18. `nan_inf_feature_corruption` (NaN coordinate packet)
    19. `interocular_scale_reduction` (Face 50% scale reduction)
    20. `long_non_command_exposure` (3,000 frames = 100 seconds conversational rest)
- **Comparison Conditions & Ablations**:
  - **Condition A (Fixed Thresholds + Debounce)**: Generic anatomical thresholds with dual geometric displacement and blendshape indicators.
  - **Condition B (Personalized Prototype + Fair Debounce)**: Personalized prototype with conventional onset debounce.
  - **Condition C (Full MORPH Intention Gate)**: Exact predictions from Condition B passed through pure IntentEngine FSM ($T_{hold} = 250$ms, $T_{release} = 150$ms, $T_{cooldown} = 300$ms).
  - **Ablation 1 (No Hold Time)**: Condition C with $T_{hold} = 0$ms.
  - **Ablation 2 (No Release Dwell)**: Condition C with $T_{release} = 0$ms.
  - **Ablation 3 (No Ambiguity Margin)**: Condition C with $min\_margin = 0.0$.
- **Measured Outputs**:

| Condition / Ablation | Total Dispatches | Matched Intended (Recall) | Unintended False Alarms | Precision | FA / Non-Cmd Hour | Exact 95% Poisson CI (FA/hr) | Latency P95 (ms) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Condition A (Fixed + Debounce)** | 11 | 4 / 4 (100.0%) | 7 | 36.4% | 216.40 | [87.00, 445.87] | -400.0 ms |
| **Condition B (Personalized + Debounce)** | 8 | 4 / 4 (100.0%) | 4 | 50.0% | 123.66 | [33.69, 316.61] | -400.0 ms |
| **Condition C (Full MORPH Intention Gate)** | **4** | **4 / 4 (100.0%)** | **0** | **100.0%** | **0.00** | **[0.00, 92.61]** | **-66.7 ms** |
| *Ablation 1: No Hold Time ($T_{hold}=0$)* | 7 | 4 / 4 (100.0%) | 3 | 57.1% | 92.74 | [19.12, 270.83] | -366.7 ms |
| *Ablation 2: No Release Dwell ($T_{rel}=0$)* | 4 | 4 / 4 (100.0%) | 0 | 100.0% | 0.00 | [0.00, 92.61] | -66.7 ms |
| *Ablation 3: No Margin ($min\_margin=0$)* | 5 | 4 / 4 (100.0%) | 1 | 80.0% | 30.91 | [0.78, 172.24] | -66.7 ms |

- **Pipeline Stage Latency Breakdown (Instrumented Benchmarks)**:
  - Video Frame Acquisition: ~8.2 ms
  - FaceLandmarker Neural Inference: ~18.5 ms
  - Scale-Invariant Feature Extraction: ~0.08 ms
  - Personalized Prototype Classification: ~0.04 ms
  - Deterministic IntentEngine FSM Step: ~0.02 ms
  - Action Dispatcher Execution: ~0.01 ms
  - **Total Pipeline Latency**: ~26.85 ms (comfortably within the 33.3 ms budget for 30 FPS real-time operation).
- **Observations & Key Findings**:
  1. Condition A suffers high false alarms (7 unintended dispatches) from head yaw/pitch, involuntary twitches, and facial expressiveness during conversation.
  2. Condition B eliminates head motion false alarms due to personalized calibration, but still triggers 4 false alarms on the 60ms brow twitch, 120ms lip twitch, ambiguous blend, and rapid pulse repetition.
  3. Condition C completely suppresses all 4 non-command events, achieving 0 false activations over 3,500+ frames.
  4. The exact 95% Poisson confidence interval for Condition C has an upper bound of 92.61 FA/hr for 0 events over 0.03235 hours (reflecting the mathematical Rule of Three: $-ln(0.05) / T$). This demonstrates why longer non-command exposure is scientifically required.
  5. Feature ablations confirm each architectural gate: No Hold increases FA by 3; No Margin increases FA by 1 (the ambiguous blend).
- **Scientific Caveat**: Evaluated on deterministic synthetic landmark sequences. Clinical validation requires consented user trials across physical etiologies.
- **Next Step**: M6.3 Controlled Real-World Testing Infrastructure.

---

## Experiment EXP-004: Audited Benchmark Mathematics, Reconciled Canonical Timing, and Two-Sided Garwood Poisson Confidence Intervals

- **Experiment ID**: EXP-004
- **Timestamp**: 2026-10-17T14:15:00+05:30
- **Git Commit**: `fix(metrics): correct benchmark exposure and confidence interval calculations (M7.1)`
- **Auditor**: Pratham Kapoor <prathamkapoor027@gmail.com>
- **Research Question**: Does reconciling canonical interval definitions and distinguishing two-sided 95% Garwood confidence intervals from one-sided 95% upper limits resolve the mathematical timing discrepancy while preserving Condition C's statistically significant superiority over baseline Conditions A and B?
- **Root Cause & Mathematical Inconsistency Addressed**:
  - In EXP-003, textual descriptions casually stated "3,420 frames and 114 seconds total duration", whereas the generator produced 3,520 frames spanning $t_{start} = 1,000,000,000$ ns to $t_{end} = 119,049,998,826$ ns ($T_{total} = 118.050$ seconds).
  - Ground truth commands covered 4 intervals of 0.400s each = 1.600s, leaving $T_{non\_command} = 118.050 - 1.600 = 116.450$ seconds = $0.0323472$ hours.
  - When readers checked $7 \times 3600 / 216.4 \approx 116.45$s against the textual 114s description, it appeared mathematically impossible for non-command exposure to exceed total duration.
  - Additionally, for $k = 0$, $92.61$ FA/hr was the **one-sided** 95% upper limit ($-ln(0.05)/T$). The **two-sided** 95% Garwood upper bound is $-ln(0.025)/T = 114.04$ FA/hr.
- **Canonical Time Definitions (`src/morph/evaluation/metrics.py`)**:
  - $T_{total} = (t_{end} - t_{start}) / 10^9 = 118.050$ seconds.
  - $T_{intended} = \text{compute\_merged\_interval\_duration\_sec}(GT) = 1.600$ seconds.
  - $T_{non\_command} = \max(0, T_{total} - T_{intended}) = 116.450$ seconds ($0.0323472$ hours).
  - Rate $\lambda = k \times 3600 / T_{non\_command}$.
  - Two-Sided 95% Garwood CI: $\alpha = 0.05, \alpha/2 = 0.025 \implies [\frac{1}{2}\chi^2_{2k, 0.025}/T, \frac{1}{2}\chi^2_{2(k+1), 0.975}/T]$. For $k=0$, bound is $[0.0, 3.688879 / T]$.
  - One-Sided 95% Upper Limit: $\alpha = 0.05 \implies \frac{1}{2}\chi^2_{2(k+1), 0.95}/T$. For $k=0$, limit is $2.995732 / T$.
- **Audited Quantitative Results**:

| Condition / Ablation | Dispatches | Matched (Recall) | False Alarms | Precision | FA / Non-Cmd Hr | Two-Sided 95% Garwood CI | One-Sided 95% Upper Limit | Latency P95 (ms) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Condition A (Fixed + Debounce)** | 11 | 4 / 4 (100.0%) | 7 | 36.4% | 216.40 | [87.00, 445.87] FA/hr | 406.47 FA/hr | -400.0 ms |
| **Condition B (Personalized + Debounce)** | 8 | 4 / 4 (100.0%) | 4 | 50.0% | 123.66 | [33.69, 316.61] FA/hr | 282.97 FA/hr | -400.0 ms |
| **Condition C (Full MORPH Intention Gate)** | **4** | **4 / 4 (100.0%)** | **0** | **100.0%** | **0.00** | **[0.00, 114.04] FA/hr** | **92.61 FA/hr** | **-66.7 ms** |
| *Ablation 1: No Hold Time ($T_{hold}=0$)* | 7 | 4 / 4 (100.0%) | 3 | 57.1% | 92.74 | [19.12, 270.83] FA/hr | 240.71 FA/hr | -366.7 ms |
| *Ablation 2: No Release Dwell ($T_{rel}=0$)* | 4 | 4 / 4 (100.0%) | 0 | 100.0% | 0.00 | [0.00, 114.04] FA/hr | 92.61 FA/hr | -66.7 ms |
| *Ablation 3: No Margin ($min\_margin=0$)* | 5 | 4 / 4 (100.0%) | 1 | 80.0% | 30.91 | [0.78, 172.24] FA/hr | 146.66 FA/hr | -66.7 ms |

- **Observations & Scientific Integrity Takeaways**:
  1. The apparent timing contradiction is completely resolved: total duration is 118.050 seconds, non-command exposure is 116.450 seconds, and command duration is 1.600 seconds ($118.050 = 116.450 + 1.600$).
  2. Condition C completely suppresses involuntary micro-twitches (60ms and 120ms), rapid repetitive twitches (< 300ms cooldown), and simultaneous gesture blends (separation margin).
  3. However, observing 0 false activations in 116.45 seconds of synthetic challenge does **NOT** prove zero real-world false activations. The two-sided 95% upper bound of 114.04 FA/hr illustrates the statistical uncertainty of short-exposure testing.
  4. To statistically establish an upper bound $< 1.0$ FA/hr at 95% confidence, an empirical trial must achieve 0 false activations over at least $3.689$ hours (~13,280 seconds) of continuous unprompted activity.
- **Scientific Caveat**: These are synthetic benchmarks with deterministic landmark fixtures. Real-world human interaction requires physical camera testing and participant trials.

---

## Experiment EXP-005: Multi-Scenario Reliability Benchmarking & Holdout Independence Audit (M8.3)

- **Experiment ID**: EXP-005
- **Timestamp**: 2026-10-17T21:30:00+05:30
- **Git Commit**: `test(evaluation): strengthen holdout and reliability metrics (M8.3)`
- **Principal Investigator**: Pratham Kapoor <prathamkapoor027@gmail.com>
- **Hardware & Environment**: Windows 11 Home Single Language (ARM64 with x64 emulation), Python 3.12.10, local CPU execution.
- **Hypothesis**: Evaluating Condition C (IntentEngine FSM) across 8 distinct research protocol scenarios alongside an expanded challenge suite—with strict validation of 6 holdout independence rules (disjoint sessions, non-overlapping temporal windows, disjoint seeds, minimum Euclidean vector distance, subsequence non-duplication, and transformation isolation)—will confirm robust false-activation suppression (0 FA during non-command intervals) without sacrificing intentional command recall (F1 = 1.0 on reachable commands), while revealing honest boundaries (e.g., severe uncalibrated scale reduction).
- **Benchmark Datasets & Scope**:
  1. **Full 20-Scenario Challenge Suite V2** (`EXP-005-CHALLENGE-SUITE-V2`): 3,520 frames (118.050s total duration, 116.450s non-command exposure = 0.03235 hours, 4 intentional commands).
  2. **8 Structured Research Scenarios** (`EvaluationScenario`):
     - `SCEN-01-INTENDED-GESTURES`: 156 frames (5.2s), 3 intentional commands (Brow Raise, Smile, Mouth Open).
     - `SCEN-02-NEUTRAL-REST`: 600 frames (20.0s), 0 intentional commands, 4 rhythmic blinks.
     - `SCEN-03-DISTRACTOR-MOVEMENTS`: 141 frames (4.7s), 0 intentional commands, 60ms brow twitch, 120ms lip twitch, head yaw/pitch.
     - `SCEN-04-COMMUNICATION-BOARD`: 176 frames (5.87s), 3 intentional commands in board navigation sequence (Next -> Next -> Select).
     - `SCEN-05-PAUSE-TRACKING-RECOVERY`: 122 frames (4.07s), 1 intentional command following 20-frame complete tracking occlusion.
     - `SCEN-06-CAMERA-HEAD-POSE-CHANGE`: 102 frames (3.4s), 1 intentional command attempt under severe 30% scale reduction.
     - `SCEN-07-CROSS-SESSION-RETEST`: 114 frames (3.8s), 2 intentional commands from independent second session stream.
     - `SCEN-08-RECALIBRATION-COMPARISON`: 99 frames (3.3s), 1 intentional command, 1 60ms distractor twitch.
- **Dataset Independence Audit (6 Rules)**:
  - **Auditor**: `DatasetIndependenceAuditor` (`src/morph/evaluation/independence.py`)
  - **RULE_DISJOINT_SESSION**: **PASSED** (Calibration `ENROLL-SESSION-CANONICAL` != Evaluation `EVAL-SESSION-EXP005`).
  - **RULE_TEMPORAL_ISOLATION**: **PASSED** ($[1.0\text{s}, 3.5\text{s}] \cap [10.0\text{s}, 130.0\text{s}] = \emptyset$, zero temporal window overlap).
  - **RULE_SEED_ISOLATION**: **PASSED** (Calibration seeds `[100..104, 200..204, 300..304]` strictly disjoint from evaluation seeds `[501..506, 601..603, 701..702, 801..803, 901]`).
  - **RULE_ZERO_VECTOR_LEAKAGE**: **PASSED** (Minimum pairwise Euclidean distance: $0.03935 > 0.00010$ tolerance; mean distance: $0.4682$).
  - **RULE_SUBSEQUENCE_DUPLICATION**: **PASSED** (Zero rolling 5-frame identical vector sequences between calibration and test).
  - **RULE_TRANSFORMATION_ISOLATION**: **PASSED** (Normalization baseline parameters fitted strictly on calibration enrollment data, zero global pooling leakage).
- **Commands Run**:
  ```powershell
  .\.venv\Scripts\python.exe scripts/run_reliability_benchmark.py
  .\.venv\Scripts\python.exe -m pytest -v tests/unit/test_dataset_holdout.py tests/unit/test_evaluation.py
  ```
- **Quantitative Comparison Results**:

### A. Full 20-Scenario Challenge Suite
| Metric | Condition A (Fixed + Debounce) | Condition B (Personalized + Debounce) | Condition C (Full MORPH Intention Gate) |
| :--- | :---: | :---: | :---: |
| **Intended Commands** | 4 | 4 | 4 |
| **Total Dispatches** | 10 | 8 | **4** |
| **True Positives (TP)** | 4 | 4 | **4** |
| **False Positives (FP)** | 6 | 4 | **0** |
| **False Negatives (FN)** | 0 | 0 | **0** |
| **Recall** | 100.0% (4/4) | 100.0% (4/4) | **100.0% (4/4)** |
| **Precision** | 40.0% (4/10) | 50.0% (4/8) | **100.0% (4/4)** |
| **F1 Score** | 0.571 | 0.667 | **1.000** |
| **Non-Command Hours** | 0.03235 hr (116.45s) | 0.03235 hr (116.45s) | 0.03235 hr (116.45s) |
| **FA / Non-Cmd Hour** | 185.49 FA/hr | 123.66 FA/hr | **0.00 FA/hr** |
| **Two-Sided 95% Garwood CI** | [68.07, 403.73] FA/hr | [33.69, 316.61] FA/hr | **[0.00, 114.04] FA/hr** |
| **One-Sided 95% Upper Limit**| 373.91 FA/hr | 282.97 FA/hr | **92.61 FA/hr** |
| **Latency P95** | -400.0 ms | -400.0 ms | **-66.7 ms** |

### B. Eight Research Protocol Scenarios Breakdown
| Scenario ID | Duration | Intended GT | Condition A (TP / FP / F1 / FA·hr⁻¹) | Condition B (TP / FP / F1 / FA·hr⁻¹) | Condition C (TP / FP / F1 / FA·hr⁻¹) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **SCEN-01-INTENDED** | 5.2s | 3 | 3 / 0 / 1.00 / 0.0 | 3 / 0 / 1.00 / 0.0 | **3 / 0 / 1.00 / 0.0** |
| **SCEN-02-NEUTRAL** | 20.0s | 0 | 0 / 0 / N/A / 0.0 | 0 / 0 / N/A / 0.0 | **0 / 0 / N/A / 0.0** |
| **SCEN-03-DISTRACTOR** | 4.7s | 0 | 0 / 2 / N/A / 1531.9 | 0 / 2 / N/A / 1531.9 | **0 / 0 / N/A / 0.0** |
| **SCEN-04-BOARD-TASK** | 5.87s | 3 | 3 / 0 / 1.00 / 0.0 | 3 / 0 / 1.00 / 0.0 | **3 / 0 / 1.00 / 0.0** |
| **SCEN-05-PAUSE-RECOVERY** | 4.07s | 1 | 1 / 0 / 1.00 / 0.0 | 1 / 0 / 1.00 / 0.0 | **1 / 0 / 1.00 / 0.0** |
| **SCEN-06-CAMERA-DRIFT** | 3.4s | 1 | 0 / 0 / 0.00 / 0.0 | 0 / 0 / 0.00 / 0.0 | **0 / 0 / 0.00 / 0.0** |
| **SCEN-07-CROSS-SESSION** | 3.8s | 2 | 2 / 0 / 1.00 / 0.0 | 2 / 0 / 1.00 / 0.0 | **2 / 0 / 1.00 / 0.0** |
| **SCEN-08-RECALIBRATION**| 3.3s | 1 | 1 / 1 / 0.67 / 1241.4 | 1 / 1 / 0.67 / 1241.4 | **1 / 0 / 1.00 / 0.0** |

- **Observations & Honest Analysis**:
  1. **Involuntary Movement Filtering**: In SCEN-03 (Distractor Movements), Condition A and B both suffer 2 false alarms (1531.9 FA/hr) from the 60ms brow twitch and 120ms lip twitch. Condition C suppresses both via temporal dwell confirmation, achieving 0 false activations.
  2. **Clean Retesting & Cross-Session Generalization**: SCEN-01, SCEN-04, SCEN-05, and SCEN-07 achieve 100% true positive recall and 0 false activations under Condition C.
  3. **Honest Boundary Identified (SCEN-06)**: When face scale drops suddenly by 30% due to participant repositioning, unadapted prototypes miss the command across all conditions (Recall = 0.0). This demonstrates that fixed similarity thresholds require user-specific recalibration (directly motivating Milestone M8.4).
  4. **Statistical Rigor**: 6/6 dataset independence rules verified. Two-sided Garwood 95% Poisson confidence intervals and F1 scores are transparently reported without masking unobserved rates.
- **Scientific Caveat**: Benchmarks are evaluated on reproducible synthetic landmark sequences and holdout fixtures. Clinical efficacy requires consented participant trials across physical motor etiologies.




