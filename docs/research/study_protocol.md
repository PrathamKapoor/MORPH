# MORPH 2.0: Controlled Real-World Accessibility Evaluation Protocol

**Document ID**: `MORPH-STUDY-2026-01`  
**Version**: `1.0.0`  
**Date**: October 2026  
**Principal Investigator**: Pratham Kapoor (`prathamkapoor027@gmail.com`)  
**Project**: MORPH 2.0 (Intention-Gated Hands-Free AAC Interaction)  
**Location**: `C:\Pratham\MORPH`  

---

## 1. Executive Summary & Research Objectives

The MORPH 2.0 system provides offline, webcam-based, hands-free computer interaction for individuals with severe physical and speech impairments. By coupling personalized facial movement classifiers with a deterministic intention state machine (Condition C), MORPH aims to eliminate involuntary or conversational false activations without degrading communication efficiency.

### 1.1 Primary Research Objective
To evaluate whether deterministic intention gating (**Condition C**) significantly reduces unintended command activations per non-command hour ($FA/hr$) compared to conventional debounced personalized classification (**Condition B**) and generic fixed-threshold gating (**Condition A**) during representative computer interaction tasks by participants with motor impairments.

### 1.2 Secondary Research Objectives
1. **Recall (Sensitivity)**: Measure the proportion of deliberate, cued facial gestures successfully confirmed and dispatched as AAC actions.
2. **Confirmation Latency**: Quantify the temporal latency between intentional gesture onset and command execution across conditions.
3. **Functional Throughput**: Evaluate task completion time ($TCT$) and words/characters per minute ($WPM$) during structured communication board phrase generation.
4. **Cognitive & Physical Burden**: Quantify perceived workload using the NASA-TLX scale and physical fatigue using the Borg CR10 scale.
5. **System Usability**: Assess overall subjective usability using the System Usability Scale (SUS).

---

## 2. Ethical Standards & Privacy Safeguards

### 2.1 Institutional Ethics & Vulnerable Populations
Participants in this study may present with severe motor impairments arising from progressive neuromuscular disorders. The protocol strictly follows Declaration of Helsinki principles for medical research involving human subjects:
- **Participant Autonomy**: Informed consent is obtained directly from the participant via accessible communication methods (eye gaze, head movement, or legal proxy where speech is impaired).
- **Zero Coercion**: Participation is entirely voluntary. Participants may pause, skip tasks, take rest breaks, or terminate participation at any moment without justification or penalty.
- **Immediate Data Erasure**: Participants retain absolute data sovereignty. A single click on the "Discard / Wipe Session" control permanently wipes all recorded feature data from volatile memory and local storage.

### 2.2 Strict Zero-Video Privacy Invariant
- **No Video Persistence**: Raw RGB camera frames reside exclusively in volatile circular memory buffers (`deque(maxlen=2)`) during active inference and are overwritten frame-by-frame. No video files (`.mp4`, `.avi`, `.mov`) or raw image frames (`.png`, `.jpg`) are ever written to disk, cached, or persisted.
- **Numerical-Only Telemetry**: Only anonymized 32-dimensional scale-invariant normalized geometric displacement vectors, landmark confidence scores, and ground-truth event timestamps are stored in the local SQLite database (`data/morph.db`).
- **Complete Offline Isolation**: The software operates entirely locally on the host machine without network sockets, telemetry beacons, cloud dependencies, or remote data transmission.

---

## 3. Participant Selection & Eligibility

### 3.1 Inclusion Criteria
1. Adults aged 18 years or older.
2. Diagnosed motor impairment affecting upper extremity dexterity and natural speech production, including but not limited to:
   - Amyotrophic Lateral Sclerosis (ALS)
   - Cerebral Palsy (spastic, dyskinetic, or ataxic)
   - High-level Spinal Cord Injury (C1–C5 tetraplegia)
   - Brainstem Stroke (Locked-In Syndrome / severe dysarthria)
   - Muscular Dystrophy
3. Preserved voluntary control of at least one to three distinct facial or head movements (e.g., brow elevation, sustained smile, mouth opening, chin drop, head turn).
4. Normal or corrected-to-normal visual acuity sufficient to perceive computer display elements.
5. Cognitive ability to comprehend task instructions and provide informed consent (or assent with legally authorized representative).

### 3.2 Exclusion Criteria
1. History of photosensitive epilepsy or seizure disorders triggered by computer displays.
2. Inability to maintain comfortable upright or supported seated posture for 30 minutes.
3. Acute medical instability, severe unmanaged pain, or respiratory distress.
4. Involuntary or continuous facial dystonia that precludes establishing a resting neutral baseline.

---

## 4. Experimental Design & Counterbalancing

### 4.1 Within-Subject Repeated Measures
To control for inter-individual anatomical variation, disease etiology, and movement amplitude, the study employs a **within-subject repeated-measures design**. Every participant evaluates all three interaction conditions:
- **Condition A (Fixed-Threshold Baseline)**: Population-average anatomical displacement thresholds with onset debounce.
- **Condition B (Personalized Prototype Baseline)**: User-calibrated prototype distance classifier with conventional release-to-rearm debouncing (no temporal hold or release dwell gating).
- **Condition C (Full MORPH Intention Gate)**: Identical personalized classifier predictions passed through the pure deterministic IntentEngine FSM ($T_{hold} = 250$ms, $T_{release} = 150$ms, $T_{cooldown} = 300$ms).

### 4.2 Latin Square Counterbalancing
To eliminate confounding ordering effects, practice bias, and muscular fatigue, the presentation order of the three conditions is systematically counterbalanced across participants using a $3 \times 3$ balanced Latin Square:

| Participant ID | Block 1 | Block 2 | Block 3 |
|:---|:---:|:---:|:---:|
| **P-001, P-004, P-007...** | Condition A | Condition B | Condition C |
| **P-002, P-005, P-008...** | Condition B | Condition C | Condition A |
| **P-003, P-006, P-009...** | Condition C | Condition A | Condition B |

---

## 5. Study Procedure & Task Protocol

The complete session duration is approximately **45 to 60 minutes**, organized into seven sequential phases:

```
[Phase 1: Consent & Setup] (10 min)
         │
         ▼
[Phase 2: Calibration & Enrollment] (5 min)
         │
         ▼
[Phase 3: Conflict Check & Mapping] (3 min)
         │
         ▼
[Phase 4: Practice Sandbox] (5 min)
         │
         ▼
[Phase 5: Counterbalanced Test Blocks] (20 min)
   ├── Block 1 (Assigned Condition)
   │     ├── Task 1: Resting Baseline (30s)
   │     ├── Task 2: Targeted Cued Trials (5 reps x 3 gestures)
   │     ├── Task 3: Functional AAC Phrase Composition (3 phrases)
   │     └── Task 4: Conversational Distractor (60s)
   ├── Rest Break (2 min)
   ├── Block 2 (Assigned Condition - same 4 tasks)
   ├── Rest Break (2 min)
   └── Block 3 (Assigned Condition - same 4 tasks)
         │
         ▼
[Phase 6: Subjective Usability Questionnaires] (10 min)
   ├── NASA-TLX (Workload)
   ├── Borg CR10 (Fatigue)
   └── System Usability Scale (SUS)
         │
         ▼
[Phase 7: Debriefing & Local Data Verification] (5 min)
```

### 5.1 Experimental Tasks per Block

1. **Task 1: Resting Baseline Task (30 seconds)**
   - *Instruction*: Maintain comfortable, natural resting posture. Do not perform any command movements.
   - *Objective*: Measure pure baseline false activation rate during zero-command rest.

2. **Task 2: Targeted Cued Gesture Task (5 trials $\times$ 3 gestures = 15 trials)**
   - *Instruction*: An accessible audiovisual countdown prompts the participant: "Ready... 3... 2... 1... [Gesture Name]!"
   - *Execution*: Participant performs the cued gesture and holds comfortably until confirmed.
   - *Objective*: Measure intentional recall, true positive dispatch count, and confirmation latency.

3. **Task 3: Functional AAC Phrase Composition (3 targeted phrases)**
   - *Phrases*:
     - Target 1: `"I NEED WATER"` (3 selections)
     - Target 2: `"PLEASE HELP"` (2 selections)
     - Target 3: `"YES THANK YOU"` (3 selections)
   - *Objective*: Measure functional task completion time ($TCT$), selection errors, and unintended navigation actions during active communication.

4. **Task 4: Conversational Distractor Task (60 seconds)**
   - *Instruction*: Participant reads a standard passage aloud (or listens and responds to open conversational prompts from the researcher).
   - *Objective*: Measure false activation susceptibility during natural speech, head nodding, laughter, and involuntary facial twitches.

---

## 6. Quantitative & Qualitative Metrics

### 6.1 Quantitative Performance Metrics
1. **Recall (Sensitivity)**:
   $$\text{Recall} = \frac{N_{\text{matched intentional dispatches}}}{N_{\text{total intended ground-truth events}}}$$
2. **False Activations per Non-Command Hour ($FA/hr$)**:
   $$\text{FA/hr} = \frac{N_{\text{unintended dispatches}}}{T_{\text{non-command hours}}}$$
3. **Exact 95% Poisson Confidence Interval**:
   Computed using the Garwood exact formulation via `poisson_rate_ci_95()`. For zero false activation observations ($k=0$), upper bound is:
   $$\lambda_{U} = \frac{-\ln(0.05)}{T_{\text{non-command}}} \approx \frac{2.996}{T_{\text{non-command}}}$$
4. **Latency Offset (ms)**:
   Temporal delta between intentional ground-truth gesture completion and software action dispatch:
   $$\Delta t = t_{\text{dispatch}} - t_{\text{gt\_end}}$$
   Reported as median (P50) and 95th percentile (P95).
5. **Task Completion Time ($TCT$)**:
   Total seconds required to compose each standardized AAC communication target.

### 6.2 Qualitative & Usability Metrics
1. **NASA-TLX (Task Load Index)**: 6 subscales scored 0–100: Mental Demand, Physical Demand, Temporal Demand, Performance, Effort, and Frustration.
2. **Borg CR10 Scale**: Single-item physical exertion score from 0 ("Nothing at all") to 10 ("Extremely strong / maximal").
3. **System Usability Scale (SUS)**: Standard 10-item questionnaire scored 0–100, where scores $> 68$ represent above-average usability.
4. **Semi-Structured Interview**: Open-ended qualitative feedback regarding comfort, confidence, fatigue, and perceived safety.

---

## 7. Statistical Analysis Plan

- **Sample Size & Statistical Power**: A sample size of $N = 12$ participants provides $>85\%$ statistical power ($\alpha = 0.05$, two-tailed) to detect a $50\%$ reduction in $FA/hr$ between Condition B and Condition C, assuming Poisson-distributed false event rates with baseline $\lambda \ge 30\text{ FA/hr}$.
- **Rate Comparison**: Differences in $FA/hr$ across conditions analyzed using non-parametric **Wilcoxon signed-rank tests** (paired across participants) with Holm-Bonferroni correction for multiple comparisons.
- **Latency & Usability**: Repeated-measures analysis of variance (RM-ANOVA) or Friedman test for non-normal distributions (NASA-TLX, SUS, Borg scores).
- **Missing Data Handling**: If a participant cannot complete a task due to acute fatigue, that block is marked `INCOMPLETE` with logged reason; available complete blocks are preserved without imputation.

---

## 8. Safety, Fatigue Management & Fail-Closed Controls

1. **Ergonomic Safety**: Ambient lighting is calibrated to prevent glare; camera position is set perpendicular to the participant's resting eye line at 50–70 cm distance.
2. **Mandatory Rest Pauses**: A mandatory 2-minute rest pause separates every test block, with additional participant-requested breaks accommodated without time limits.
3. **Instant Safe Pause**: The participant or caregiver can instantly pause the system via:
   - Voice command `"PAUSE"`
   - Keyboard spacebar / Esc key
   - Enrolled pause gesture
   - Offscreen camera obstruction (triggers fail-closed `TRACKING_LOST` state in $<33$ ms).

---

## 9. Appendix: Informed Consent Script & Participant Notice

> *"You are invited to take part in an accessibility research evaluation of MORPH 2.0. This application helps individuals communicate hands-free using comfortable facial and head movements.*  
> *During this study, you will try three different software settings to navigate a communication board. We will measure how reliably the software detects your movements and whether it avoids accidental clicks.*  
> *IMPORTANT PRIVACY NOTICE: Your camera stream is processed strictly in temporary computer memory. No camera video, pictures, or voice recordings are ever saved to the computer or sent over the internet. Only numerical movement measurements are stored.*  
> *You can take breaks, stop, or completely delete your data at any time without giving a reason."*
