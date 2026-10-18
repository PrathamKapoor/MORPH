# MORPH 2.0 Live Hackathon Demonstration & Presentation Guide

**Author**: Pratham Kapoor <prathamkapoor027@gmail.com>  
**System**: Windows 10/11 Local Offline AAC System  
**Location**: `C:\Pratham\MORPH\docs\DEMO_GUIDE.md`  
**Milestone**: M8.7 Live Demonstration Finalization & Stage Recovery

---

## 1. Demonstration Setup & Preflight Checklist

### 1.1 Hardware & Environment Requirements
- **Host Machine**: Windows 10 or 11 (64-bit x64 or ARM64).
- **Camera Sensor**: Integrated webcam or external USB webcam (DirectShow compatible, 640x480 @ 30 FPS).
- **Audio Output**: Internal speakers or headphones for Windows SAPI TTS speech output.
- **Lighting**: Standard ambient room lighting (avoid direct high-intensity backlighting).

### 1.2 Quick Launch & Diagnostics
Execute preflight health check before presenting:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\doctor.ps1
```
Ensure all 6 checks return `[PASS]`.

Launch MORPH 2.0:
```powershell
.\.venv\Scripts\python.exe -m morph
# Or run packaged standalone executable:
.\dist\morph\morph.exe
```

Navigate to the **Demo** tab in the top navigation bar (or press `Ctrl+Tab` to route `"demo"`).
Verify automated preflight diagnostics cards:
1. `Camera Sensor`: DirectShow Hardware Active (or Synthetic Replay Fallback)
2. `MediaPipe Task Asset`: Verified Present (3.7MB checksum match)
3. `Offline Windows SAPI TTS`: Local Voices Available
4. `FSM Initial State`: Fail-Closed PAUSED State Guaranteed
5. `SQLite Storage`: Active (Schema v2)
6. `Benchmark Replay Suite`: 3-Prototype Protocol Ready

---

## 2. 10-Part Guided Demonstration Script

### Stage 1: The Problem — Conventional Baseline Failures
- **Visual Display**: Research Lab baseline comparison table (Condition A vs. Condition B vs. Condition C).
- **Presenter Talk Track**:
  > *"Traditional webcam accessibility switches trigger immediately whenever facial movement crosses an arbitrary threshold. For people living with ALS, cerebral palsy, or spinal muscular atrophy, involuntary twitches, micro-spasms, and conversational speech cause relentless accidental commands—over 200 false activations per hour. Users are forced to spend more time undoing mistakes than communicating. MORPH 2.0 solves this fundamental flaw with deterministic intention gating."*
- **Action**: Press **Right Arrow** to advance to Stage 2.

---

### Stage 2: Calibrated Neutral Resting Posture & Scale Invariance
- **Visual Display**: Active neutral mesh visualization and scale calibration telemetry.
- **Presenter Talk Track**:
  > *"Every human face and resting posture is distinct. Rather than relying on rigid population averages, MORPH begins by capturing a 5-second resting neutral mesh. All subsequent facial movements are computed as scale-invariant relative displacements normalized by the user's inter-ocular distance. Whether the user sits close to the camera or leans back, the system maintains consistent geometric sensitivity without false triggers."*
- **Action**: Press **Right Arrow** to advance to Stage 3.

---

### Stage 3: 3-Gesture Enrollment & Geometric Conflict Check
- **Visual Display**: 3-gesture calibration cards with pairwise cosine similarity separation matrix.
- **Presenter Talk Track**:
  > *"The user trains up to three personally comfortable facial movements—for example, Brow Raise, Smile, and Mouth Open. As each gesture is trained, MORPH computes directional cosine similarities across all prototypes. If two movements share overlapping muscle synergies—such as a squint and a cheek twitch—the conflict matrix warns the user before live tracking begins, guaranteeing clear geometric separation."*
- **Action**: Press **Right Arrow** to advance to Stage 4.

---

### Stage 4: Intention Gating Proof — Involuntary Twitch Rejection
- **Visual Display**: FSM state transition badge (`IDLE` $\rightarrow$ `CANDIDATE` $\rightarrow$ `CONFIRMED` $\rightarrow$ `COOLDOWN`) and hold duration progress bar.
- **Presenter Talk Track**:
  > *"Here is the core technical breakthrough. Notice what happens when an involuntary twitch or fleeting facial expression occurs: the candidate threshold is crossed, but because the 250ms hold requirement is not satisfied, the state machine resets cleanly to IDLE with exactly zero commands dispatched. Now watch a deliberate 300ms hold: the intention gate confirms the command smoothly and enters a refractory cooldown, preventing accidental double-clicks."*
- **Action**: Press **Right Arrow** to advance to Stage 5.

---

### Stage 5: Hands-Free Communication Board & Offline SAPI TTS
- **Visual Display**: High-contrast 3x3 AAC phrase board with green focus flash and spoken banner.
- **Presenter Talk Track**:
  > *"In live communication mode, confirmed gestures navigate the phrase grid. Gesture 1 advances the selection, Gesture 2 moves backward, and Gesture 3 speaks the selected phrase. Spoken audio is generated entirely offline via native Windows SAPI speech synthesis. There is zero cloud dependency, zero network latency, and zero persistent video recording on disk."*
- **Action**: Press **Right Arrow** to advance to Stage 6.

---

### Stage 6: Multi-Objective Parameter Calibration & Guided Exploration
- **Visual Display**: Parameter exploration score card balancing recall (40%), false activation protection (35%), comfort (15%), and latency (10%).
- **Presenter Talk Track**:
  > *"No two users have the same muscle endurance or holding comfort. MORPH provides guided multi-objective parameter exploration. Users test candidates in a safe sandbox before promoting them to active tracking. If a user prefers quicker actuation, MORPH calculates the exact trade-off against false activation risk."*
- **Action**: Press **Right Arrow** to advance to Stage 7.

---

### Stage 7: Profile Version History & Instant Atomic Rollback
- **Visual Display**: Immutable profile version history in SQLite and 1-click Rollback button.
- **Presenter Talk Track**:
  > *"Every recalibration creates an immutable version snapshot in SQLite. If a newly chosen hold duration proves fatiguing during extended use, the user or caregiver rolls back to the prior validated baseline with a single click. Historical versions are never silently overwritten."*
- **Action**: Press **Right Arrow** to advance to Stage 8.

---

### Stage 8: Continuous Session Ergonomics & Rest Advisory
- **Visual Display**: Session duration tracker and polite amber rest advisory banner.
- **Presenter Talk Track**:
  > *"Sustained facial muscle contractions can cause muscle strain. MORPH tracks active communication duration, automatically pausing accumulation during holds or tracking loss, and politely displays a non-medical rest advisory at 20 minutes with 1-click break and snooze controls."*
- **Action**: Press **Right Arrow** to advance to Stage 9.

---

### Stage 9: Fail-Closed Safety & Emergency Keyboard Overrides
- **Visual Display**: Red tracking-lost indicator and instant pause override.
- **Presenter Talk Track**:
  > *"Above all, MORPH is engineered for safety. If the user turns away, multiple faces enter the webcam frame, or the lens is covered, the system transitions to TRACKING_LOST in under 33 milliseconds, immediately suppressing all command output. Furthermore, a caregiver or user can press the Spacebar or Escape key at any moment to lock the system into the fail-closed PAUSED state."*
- **Action**: Press **Right Arrow** to advance to Stage 10.

---

### Stage 10: Scientific Evaluation & Empirical Benchmark Reproduction
- **Visual Display**: ReplayEngine empirical benchmark results showing 0.00 FA/hr with Garwood 95% CI and JSON export.
- **Presenter Talk Track**:
  > *"Unlike prototypes with unverified claims, MORPH provides auditable reproducibility. Running the 118-second synthetic challenge through ReplayEngine reproduces 100% recall with exactly 0.00 FA/hr (Garwood 95% CI [0.0, 114.0] FA/hr), backed by strict holdout independence rules and public dataset manifests."*
- **Action**: Conclude presentation or press **R** to restart from Stage 1.

---

## 3. Keyboard Shortcuts & Recovery Controls

| Shortcut Key | Action | Context |
|---|---|---|
| **Spacebar** | Toggle Live Tracking / Pause | Global (works anywhere in the app) |
| **Escape** | Emergency Stop & Dismiss Banners | Global fail-safe |
| **Right Arrow** | Next Demonstration Stage | Demo View |
| **Left Arrow** | Previous Demonstration Stage | Demo View |
| **R** | Reset Demonstration to Stage 1 | Demo View |
| **Ctrl+Tab** | Traverse Navigation Tabs | Global |

---

## 4. Live Presentation Contingency Plan

### Contingency A: Physical Camera Sensor Disconnect or Driver Glitch
- **Symptom**: Camera preflight indicates blocked or unavailable.
- **Recovery**: MORPH automatically falls back to the built-in synthetic replay adapter (`SimulatedCameraAdapter`). To explicitly launch in demo mode without camera hardware:
  ```powershell
  .\.venv\Scripts\python.exe -m morph --no-camera
  ```
- All state transitions, twitch rejection proofs, and board navigation work deterministically under synthetic fixtures.

### Contingency B: Windows Audio Muted or SAPI TTS Glitch
- **Symptom**: Speech audio is inaudible in the presentation hall.
- **Recovery**: The communication board features visual feedback:
  - Spoken phrase is prominently displayed in the on-screen spoken banner.
  - The activated phrase tile flashes vibrant green (`#10B981`) for 300ms upon dispatch.

### Contingency C: User Fatigue or Session Drift
- **Symptom**: Presenter needs a break or resting baseline drifts.
- **Recovery**: Press **Spacebar** to pause. The built-in `RestAdvisor` supports 1-click break tracking, and the Gesture Studio allows 5-second baseline recalibration with atomic rollback safety.
