# MORPH 2.0 Execution & Architecture Flows

Author: Pratham Kapoor <prathamkapoor027@gmail.com>  
System: Windows 10/11 Local Offline AAC System  
Location: `C:\Pratham\MORPH`

---

## 1. System Architecture & End-to-End Data Pipeline

The MORPH 2.0 pipeline runs entirely locally and offline, ensuring deterministic execution and absolute user privacy. Raw video frames exist solely in volatile memory and are immediately freed after landmark extraction.

```mermaid
flowchart TD
    subgraph Capture [Worker Thread: Capture & Landmarks]
        Webcam[Local Webcam / OpenCV] -->|BGR Frame Packet| MP[MediaPipe Face Landmarker Task]
        MP -->|Face Landmarks & Quality| Validator{Validate Exactly 1 Face?}
        Validator -->|Failed / >1 Face / 0 Face| LostPacket[LandmarkPacket valid=False]
        Validator -->|Success| ValidPacket[LandmarkPacket valid=True]
    end

    subgraph FeaturePipeline [Feature Normalization & Quality]
        ValidPacket --> Extractor[FeatureExtractor]
        NeutralRef[(Active Profile Neutral Baseline)] --> Extractor
        Extractor -->|Scale & Pose Normalized Vector| FeaturePacket[FeaturePacket finite & validated]
        LostPacket --> LostFeature[FeaturePacket valid=False]
    end

    subgraph Recognizer [Personalized Recognition Layer - Condition B]
        FeaturePacket --> Classifier[KNN / Nearest Prototype Matcher]
        ProfileWeights[(Trained Gesture Prototypes)] --> Classifier
        Classifier -->|Similarity Scores & Margin| RecResult[RecognitionResult]
    end

    subgraph IntentFSM [Deterministic Intention Engine - Condition C]
        RecResult --> Engine[IntentEngine State Machine]
        Clock[Monotonic Clock t_ns] --> Engine
        PauseState[User Pause / Mode] --> Engine
        Engine -->|State: CONFIRMED| ConfirmedCmd[ConfirmedCommand UUID]
        Engine -->|State: IDLE / CANDIDATE / COOLDOWN| NoOp[No Command]
    end

    subgraph Dispatch [Sandboxed Action Dispatcher]
        ConfirmedCmd --> AllowList{Action in Allow-List?}
        AllowList -->|Yes| Dispatcher[ActionDispatcher]
        AllowList -->|No| RejectLog[Log Safe Security Rejection]
        Dispatcher -->|Internal Action| NavController[Grid Nav: NEXT / PREV / SELECT / BACK]
        Dispatcher -->|Speech Action| SAPIAdapter[Windows SAPI TTS Adapter]
        Dispatcher -->|Visual Event| EventBus[UI State Bus]
    end
```

---

## 2. Application Lifecycle & UI Navigation Flow

The app starts strictly in the **PAUSED** state. No camera tracking or background processing may trigger commands before explicit user activation.

```mermaid
stateDiagram-v2
    [*] --> S1_Home: Application Launch (Strict PAUSED)
    
    S1_Home --> S0_Onboarding: Start Guided Onboarding
    S0_Onboarding --> S3_Board: Complete 5-Step Wizard
    S0_Onboarding --> S1_Home: Back to Home
    
    S1_Home --> S2_Studio: Setup / Train Gestures
    S2_Studio --> S1_Home: Save & Return
    
    S1_Home --> S3_Board: Open Communication Board
    S3_Board --> S1_Home: Return to Home
    
    S1_Home --> S4_Settings: Adjust Thresholds & Timings
    S4_Settings --> S1_Home: Save & Return
    
    S1_Home --> S5_Monitor: Inspect Tracking Health, Latencies & FPS
    S5_Monitor --> S1_Home: Return
    
    S1_Home --> S6_Lab: Research Replay & A/B/C Benchmarks
    S6_Lab --> S1_Home: Return

    S1_Home --> S7_Eval: Controlled Evaluation Session (Latin Square)
    S7_Eval --> S1_Home: Return

    S1_Home --> S8_Demo: Guided Hackathon Live Demonstration
    S8_Demo --> S1_Home: Return

    state S1_Home {
        PAUSED_STATE --> ACTIVE_STATE: User Clicks "ACTIVATE"
        ACTIVE_STATE --> PAUSED_STATE: User Clicks "PAUSE" or Press Space
    }
```

### Screen Responsibilities
- **S0 (Onboarding Wizard)**: 5-step guided walkthrough: privacy disclosure, webcam positioning, resting neutral check, 3-gesture calibration, and practice trial.
- **S1 (Home)**: Profile management, activation state toggle, camera/model health summary, route navigation.
- **S2 (Gesture Studio)**: Guided enrollment of resting neutral baseline + 3 gestures (5–10 samples each), ambiguity conflict detector, practice sandbox.
- **S3 (Communication Board)**: High-contrast 2D grid phrase tiles, offline Windows SAPI TTS, direct visual feedback, single-switch auto-scan.
- **S4 (Recognition Settings)**: Adjust $T_{hold}$, $T_{release}$, $T_{cooldown}$, similarity threshold, and ambiguity margins.
- **S5 (Reliability Monitor)**: Processed FPS, capture FPS, stage latencies, FSM badge, hold progress bar, DecisionReason breakdown, and raw vector similarities/distances.
- **S6 (Research Lab)**: Consented session recording, A/B/C replay benchmark with fair event-level debouncing and multi-factor ablations, JSON/CSV exports.
- **S7 (Controlled Evaluation)**: Participant consent gating, anonymized participant ID generation, automated task cueing runner, real-time ground truth event logging, and zero-residue session wipe.
- **S8 (Hackathon Demonstration)**: Automated preflight hardware checks (camera, MediaPipe, SAPI TTS, FSM fail-closed) and 7-stage guided talk-track demonstration.


---

## 3. Gesture Enrollment & Neutral Calibration Flow

To prevent accidental activation, gestures are calibrated relative to the user's natural resting face.

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Facilitator
    participant UI as Studio UI (S2)
    participant Worker as Capture Worker
    participant Norm as Feature Normalizer
    participant Store as SQLite Storage

    User->>UI: Select "Calibrate Neutral Baseline"
    UI->>User: Display "Relax facial muscles for 3 seconds"
    Worker->>Norm: Stream 30-90 neutral landmark frames
    Norm->>Norm: Calculate median rest landmarks & anatomical inter-ocular scale
    Norm->>Store: Save ProfileNeutralSnapshot (UUID, timestamps, vector)
    UI->>User: Confirmation: "Neutral Baseline Saved"

    loop For Gesture 1 to 3 (e.g. Brow Raise, Smile, Cheek Pull)
        User->>UI: Start Recording Gesture K (5 to 10 samples)
        loop Sample 1 to N
            UI->>User: Visual countdown (3... 2... 1... HOLD)
            Worker->>Norm: Capture peak gesture landmark frame
            Norm->>Norm: Normalize relative to neutral baseline & anatomical scale
            UI->>User: Display preview: Accept or Redo sample?
            User->>UI: Confirm sample
        end
        UI->>UI: Compute intra-class variance and cross-gesture separation
    end
    User->>UI: Run Non-Executing Practice Mode
    UI->>Store: Persist trained model snapshot & gesture-to-action bindings
```

---

## 4. Deterministic Intent State Machine Flow (Condition C)

The pure finite-state machine enforces explicit intentionality before any command can be emitted.

```mermaid
stateDiagram-v2
    [*] --> PAUSED

    PAUSED --> IDLE: Explicit User Activation (LIVE Mode)
    IDLE --> PAUSED: User Pause Toggle or Screen Switch
    CANDIDATE --> PAUSED: User Pause Toggle
    COOLDOWN --> PAUSED: User Pause Toggle

    IDLE --> TRACKING_LOST: Face Lost / >1 Face / Stale Frame
    CANDIDATE --> TRACKING_LOST: Face Lost / >1 Face / Stale Frame
    COOLDOWN --> TRACKING_LOST: Face Lost / >1 Face / Stale Frame
    TRACKING_LOST --> IDLE: Re-acquired Single Face (Safe Re-arm, 0 Dispatches)

    IDLE --> CANDIDATE: Classifier Candidate Passes Quality & Margin Checks
    
    state CANDIDATE {
        [*] --> TimingHold
        TimingHold --> ResetToIdle: Candidate Label Changes OR Drops Below Threshold
        TimingHold --> Confirm: Stable Elapsed Time >= T_hold
    }

    CANDIDATE --> IDLE: ResetToIdle
    CANDIDATE --> CONFIRMED: Confirm (Emit exactly 1 ConfirmedCommand)
    
    CONFIRMED --> COOLDOWN: Immediate Transition
    
    state COOLDOWN {
        [*] --> WaitingRelease
        WaitingRelease --> ReadyToArm: Face Returns to Neutral (Release) AND Elapsed >= T_cooldown
    }

    COOLDOWN --> IDLE: ReadyToArm
```

---

## 5. Offline Action Dispatch & Communication Flow

All execution routes through the isolated `ActionDispatcher`. No recognition thread or UI event handler executes actions directly.

```mermaid
flowchart LR
    Cmd[ConfirmedCommand] --> Gate[ActionDispatcher.dispatch]
    Gate --> CheckActive{Is System ACTIVE?}
    CheckActive -->|No: PAUSED/PRACTICE/REPLAY| Sink[Record Event in Audit Log - Zero Side Effects]
    CheckActive -->|Yes: LIVE| CheckAllow{Action in Allow-List?}
    CheckAllow -->|No| SecurityAlert[Log Security Rejection]
    CheckAllow -->|Yes: Approved Action| Router{Action Type}
    Router -->|NEXT_TILE| Nav1[Focus Next Tile]
    Router -->|PREVIOUS_TILE| Nav2[Focus Previous Tile]
    Router -->|SELECT_TILE| Nav3[Select Current Tile]
    Router -->|SPEAK_TILE| TTS[Trigger SAPI Local Speech]
    Router -->|PAUSE| PauseApp[Enter Safe PAUSED State]
```

---

## 6. Failure & Safety Suppression Flow

To guarantee safety for users with motor disabilities, MORPH enforces a fail-closed architecture:
1. **Camera Disconnection / Stale Frames**: If frame timestamp delta exceeds 150 ms or camera returns empty frame, state shifts instantly to `TRACKING_LOST`. Any ongoing hold is purged.
2. **Multiple Faces in Frame**: If a caregiver or passerby enters the frame ($N > 1$), all tracking validity drops to `False`. Command emission is strictly blocked.
3. **Ambiguous Classification / Tied Scores**: If the margin between the top two gesture candidates is below `min_margin` ($\Delta < 0.15$), the candidate is rejected with reason `AMBIGUOUS_CONFLICT`.
4. **Out-of-Order Packets**: Packets with monotonic timestamps less than or equal to the previous frame are discarded immediately.
5. **Reconnection / Unpause**: Transitioning from `TRACKING_LOST` or `PAUSED` back to `IDLE` requires a minimum of 200 ms of continuous valid resting neutral tracking before any new candidate can be admitted.

---

## 7. Controlled Research Replay & A/B/C Evaluation Flow

To empirically answer the core research question, evaluation sessions replay recorded feature packets across all three conditions without human bias.

```mermaid
flowchart TD
    Dataset[(Consented Labeled Feature Sequence)] --> Player[Replay Engine]
    GroundTruth[(Annotated Ground Truth Intervals)] --> Evaluator[Metric Evaluator]
    
    Player -->|Identical Raw Feature Vectors| CondA[Condition A: Fixed Anatomical Thresholds]
    Player -->|Identical Raw Feature Vectors| CondB[Condition B: Personalized Matcher, Zero Gate]
    Player -->|Identical Raw Feature Vectors| CondC[Condition C: Personalized Matcher + Intention Gate]

    CondA -->|Dispatched Events A| Evaluator
    CondB -->|Dispatched Events B| Evaluator
    CondC -->|Dispatched Events C| Evaluator

    Evaluator --> Matcher[One-to-One Bipartite Event Matcher]
    Matcher --> Metrics[Calculate Precision, Recall, FA/hr, Latency P50/P95]
    Metrics --> Export[Export Standardized JSON / CSV Reports]
```

---

## 8. Safe Personalization, Posture Drift & Rollback Flow

Cross-session anatomical drift and lighting shifts are handled through non-medical, explainable calibration checks and atomic versioning.

```mermaid
flowchart TD
    SessionStart[Session Start / Neutral Baseline Probe] --> Drift[DriftDetector.assess_neutral_drift]
    Drift --> StatusCheck{Drift Status?}
    StatusCheck -->|STABLE: <8% shift| Green[System Ready: IDLE]
    StatusCheck -->|MODERATE_DRIFT: 8-16% shift| Warn[Show Non-Medical Advice Banner: Recheck Seating / Lighting]
    StatusCheck -->|SEVERE_DRIFT: >16% shift| Alert[Show Warning Banner: Fast 1-2s Recalibration Recommended]
    
    Alert --> Recalibrate[Run Quick Recalibration]
    Recalibrate --> CreateCandidate[ProfileVersionManager.create_version: CANDIDATE]
    CreateCandidate --> UserVerify[User Evaluates Practice Trial]
    UserVerify -->|Accepted| Promote[Promote to VALIDATED Snapshot]
    UserVerify -->|Rejected / Worse| Rollback[Atomic Rollback to Prior VALIDATED Version]
```

---

## 9. Accessible Error Recovery & Safety Notification Flow

Instead of modal popups that steal screen reader focus, non-blocking high-contrast banners provide actionable recovery steps.

```mermaid
flowchart LR
    Event[Fault Event: Camera Disconnect / Multi-Face / Drift] --> Banner[MainWindow.show_banner]
    Banner --> AccessibleAttr[Set accessibleName & High-Contrast Style]
    Banner --> ActionButton{Action Required?}
    ActionButton -->|Yes: e.g. Recalibrate / Retry| Handler[Execute Recovery Callback: Navigate or Reset]
    ActionButton -->|No| Dismiss[User Clicks Dismiss or Presses Esc]
```

---

## 10. Controlled Real-World Study & Live Demonstration Flows

### 10.1 Real-World Study Execution Flow
```mermaid
flowchart TD
    Consent[Informed Consent Dialog] -->|Granted| GenID[Generate Anonymized Participant UUID]
    GenID --> Order[Assign Balanced Latin Square Condition Order]
    Order --> Cues[Automated Task Cue Runner: 6 Phrase Prompts]
    Cues --> Logger[Event Logger: Monotonic Ground Truth + Dispatches]
    Logger --> Wiping{Session Complete?}
    Wiping -->|Yes: Export| Exporter[Export Non-PII Metrics JSON / CSV]
    Wiping -->|Yes: Purge| ZeroWipe[Zero-Residue In-Memory Data Wipe]
```

### 10.2 Safe Live Demonstration Flow
```mermaid
flowchart LR
    Launch[Open Live Demo View] --> Preflight[Automated Preflight Diagnostics]
    Preflight --> CheckCam{DirectShow Camera?}
    Preflight --> CheckModel{MediaPipe Asset?}
    Preflight --> CheckTTS{SAPI Voices?}
    Preflight --> CheckFSM{FSM Initial PAUSED?}
    
    CheckCam & CheckModel & CheckTTS & CheckFSM --> Ready[All Systems PASS: Green Indicators]
    Ready --> Stages[7 Guided Stages: Talk-Track, Visual Proofs, Fail-Closed Override]
```

---

## 11. Rest Advisor & Continuous Session Ergonomics Flow (Milestone M7)

To prevent facial muscle strain or fatigue during extended communication sessions (PRD D09), `RestAdvisor` runs a non-medical continuous duration monitor:

```mermaid
flowchart TD
    StateChange[FSM State Changed] --> IsActive{Is System ACTIVE?}
    IsActive -->|Yes: State != PAUSED| Accumulate[Accumulate Active Seconds Delta]
    IsActive -->|No: PAUSED / TRACKING_LOST| Freeze[Freeze Accumulation Timer]
    
    Accumulate --> CheckThresh{Active Time >= 20 min?}
    CheckThresh -->|No| Continue[Continue Normal Tracking]
    CheckThresh -->|Yes & Not Alerted| Alert[Emit rest_suggested: Show Non-Medical Warning Banner]
    
    Alert --> UserChoice{User Action}
    UserChoice -->|Take a Break| Break[Force Safe PAUSED State, Reset Counter to 0, Hide Banner]
    UserChoice -->|Dismiss| Snooze[Snooze 5 min: Set Counter to 15 min, Hide Banner]
    UserChoice -->|Spacebar / Esc| ManualPause[Enter Safe PAUSED State]
```

---

## 12. Sustained Multi-Stage Performance Measurement & Telemetry Flow (Milestone M8.1)

Decouples optical camera driver wait from computational inference and intention gating via nanosecond-precision `PipelineStageTelemetry`:

```mermaid
flowchart TD
    subgraph OpticalSensor ["Hardware & Driver (Optical Integration)"]
        T0["t_read_start (Driver Entry)"] --> CamRead["cv2.VideoCapture.read() (Sensor Shutter Wait ~82ms)"]
        CamRead --> T1["t_capture (Monotonic Arrival)"]
    end

    subgraph BoundedQueue ["Bounded Queue Subsystem"]
        T1 --> T_qin["t_queue_insert"]
        T_qin --> RingBuf["Bounded Deque (Max Depth: 3)"]
        RingBuf --> T_qout["t_queue_remove (< 2 us)"]
    end

    subgraph ComputePipeline ["Zero-Wait Compute Engine (~17 ms Total)"]
        T_qout --> T_inf0["t_infer_start"]
        T_inf0 --> MP["MediaPipe FaceLandmarker (~15.9 ms)"]
        MP --> T_inf1["t_infer_end"]
        
        T_inf1 --> T_feat0["t_feat_start"]
        T_feat0 --> Norm["FeatureExtractor & Baseline (~0.07 ms)"]
        Norm --> T_feat1["t_feat_end"]
        
        T_feat1 --> T_rec0["t_recog_start"]
        T_rec0 --> Rec["Personalized Classifier (~0.02 ms)"]
        Rec --> T_rec1["t_recog_end"]
        
        T_rec1 --> T_int0["t_intent_start"]
        T_int0 --> FSM["Deterministic Intent Engine (~0.02 ms)"]
        FSM --> T_int1["t_intent_end"]
    end

    subgraph DispatchPresentation ["Sandboxed Dispatch & UI Presentation"]
        T_int1 --> T_disp0["t_dispatch_start"]
        T_disp0 --> Sink["Sandboxed Action Sink (< 1 us)"]
        Sink --> T_disp1["t_dispatch_end"]
        T_disp1 --> T_ui["t_ui_ack"]
    end
```

---

## 13. User-Specific Guided Parameter Calibration & Rollback Architecture (M8.4)

Balances sensitivity, false-activation rejection, latency, and holding comfort with atomic SQLite version control:

```mermaid
flowchart TD
    subgraph DataIngestion ["Practice Calibration Data"]
        S_int["Intended Gesture Samples (>= 3 required)"]
        S_rest["Non-Command Resting Rest (>= 1.0s required)"]
    end

    subgraph Gatekeeper ["Admission & Conflict Gate"]
        S_int & S_rest --> SuffCheck{"Data Sufficiency & Conflict Check"}
        SuffCheck -- "< 3 samples or < 1.0s" --> S_insuff["Status: INSUFFICIENT_DATA (Zero Guesswork)"]
        SuffCheck -- "Non-command sim >= 0.85" --> S_conf["Status: CONFLICTING_DATA (Neutral Overlap)"]
        SuffCheck -- "Valid Data" --> GridEval["Permitted Parameter Grid (T_hold, T_rel, T_cd, Sim, Margin)"]
    end

    subgraph ObjectiveOptimization ["Multi-Objective Optimization Engine"]
        GridEval --> SimEngine["Replay Across IntentEngine & PersonalizedRecognizerB"]
        SimEngine --> Metrics["Compute Recall, FA Count, Latency, Comfort"]
        Metrics --> CompScore["Composite = 0.40*Rec + 0.35*(1-FA) + 0.15*Comfort + 0.10*Lat"]
        CompScore --> BestCand["Select Optimal Viable Candidate (Status: RECOMMENDED)"]
    end

    subgraph UserGateRollback ["Zero-Silent-Update Decision & SQLite Rollback"]
        BestCand --> CandStore["Store in profile_versions (Status: CANDIDATE)"]
        CandStore --> UIReview["SettingsView Review & Disclaimer"]
        UIReview -- "User Clicks Accept" --> Promote["Atomic Promotion (Status: VALIDATED) & Active Table Sync"]
        UIReview -- "User Clicks Reject" --> Deprecate["Candidate Deprecated (Status: DEPRECATED)"]
        Promote -. "If Tiring in AAC Use" .-> Rollback["Atomic Version Rollback to Prior Validated Snapshot"]
    end
```




