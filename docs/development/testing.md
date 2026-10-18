# MORPH 2.0 Manual Test Plan & Clinical Pilot Protocol

Author: Pratham Kapoor <prathamkapoor027@gmail.com>  
System: Windows 10/11 Local Offline AAC System  
Location: `C:\Pratham\MORPH`

---

## 1. Preflight System Health Check

| Step | Action | Expected Result | Pass/Fail |
|:---:|:---|:---|:---:|
| 1.1 | Open PowerShell at `C:\Pratham\MORPH` and run `.\scripts\doctor.ps1` | All 5 checks pass: Python, packages, model SHA-256, SAPI voices, camera status | [ ] |
| 1.2 | Disconnect internet / enable Airplane Mode | System executes normally without network prompts or errors | [ ] |
| 1.3 | Launch app: `.\scripts\run.ps1` | App window opens with dark high-contrast theme; initial state is PAUSED | [ ] |

---

## 2. Onboarding & Neutral Calibration Flow

| Step | Action | Expected Result | Pass/Fail |
|:---:|:---|:---|:---:|
| 2.1 | Navigate to **Studio** tab via Tab key or mouse | Studio screen displays Step 1 (Neutral), Step 2 (3 Gestures), Step 3 (Practice) | [ ] |
| 2.2 | Sit naturally, relax facial muscles, click "Calibrate Rest Baseline (3s)" | Status updates to "Neutral Baseline: Calibrated and active" | [ ] |
| 2.3 | Test 0-face detection: cover camera with hand | Badge displays "No Face Detected"; calibration/capture paused safely | [ ] |
| 2.4 | Test multi-face detection: facilitator leans into view ($N=2$) | Badge displays "Multiple Faces Detected"; tracking validity drops | [ ] |

---

## 3. Gesture Enrollment & Practice Sandbox

| Step | Action | Expected Result | Pass/Fail |
|:---:|:---|:---|:---:|
| 3.1 | For Gesture 1 ("Brow Raise"): Click "Capture Sample" 5 to 10 times | Sample counter increments to 5/10; progress bar turns green | [ ] |
| 3.2 | Click "Redo" on Gesture 1 | Samples clear; prompt resets to 0/10 samples cleanly | [ ] |
| 3.3 | Click "Start Practice Mode" in Step 3 | Badge switches to green "PRACTICE SANDBOX"; perform movements | [ ] |
| 3.4 | Perform Brow Raise in Practice Mode | Practice status displays "Candidate: Brow Raise (Similarity: 0.9X) [Simulated Only]"; NO speech is emitted | [ ] |
| 3.5 | Click "Save Trained Profile" | Profile snapshot, prototypes, and thresholds saved to `data/morph.db` | [ ] |

---

## 4. Live Communication Board Execution

| Step | Action | Expected Result | Pass/Fail |
|:---:|:---|:---|:---:|
| 4.1 | Return to **Home** and click large "ACTIVATE MORPH" button | Badge changes to green "LIVE TRACKING ACTIVE" | [ ] |
| 4.2 | Navigate to **Board** tab | 9 high-contrast phrase tiles visible; first tile highlighted | [ ] |
| 4.3 | Perform deliberate Brow Raise and hold for $\ge 300$ ms | Confirmed command emitted; focus advances to next phrase tile | [ ] |
| 4.4 | Hold Brow Raise continuously for 2 seconds | Exactly ONE navigation step occurs; NO repeated navigation while held | [ ] |
| 4.5 | Release to neutral for $\ge 150$ ms, then perform Brow Raise again | Next tile focuses successfully after cooldown | [ ] |
| 4.6 | Perform Smile / Lip Pull and hold $\ge 300$ ms | "SELECT_TILE" triggered; tile flashes green and speaks phrase via Windows SAPI | [ ] |
| 4.7 | Press Spacebar or Escape on keyboard | Immediate fail-safe pause: badge displays "PAUSED"; all gesture commands suppressed | [ ] |

---

## 5. Controlled Research Replay & Exports

| Step | Action | Expected Result | Pass/Fail |
|:---:|:---|:---|:---:|
| 5.1 | Navigate to **Research** tab | Consent checkbox and A/B/C comparison table visible | [ ] |
| 5.2 | Click "Run A/B/C Replay Benchmark" | Replay executes across A, B, and C; table populates with genuine counts, FA/hr, recall, precision, latency | [ ] |
| 5.3 | Inspect Condition C vs Condition B | Condition C exhibits significantly lower unintended dispatches than Condition B | [ ] |
| 5.4 | Click "Export Benchmark JSON" and "Export Events CSV" | Checksummed JSON and CSV files created under `C:\Pratham\MORPH\exports\` | [ ] |
