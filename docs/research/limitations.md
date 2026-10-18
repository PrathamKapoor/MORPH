# Research Limitations & Readiness Tiers

**Author**: Pratham Kapoor <prathamkapoor027@gmail.com>  
**Project**: MORPH 2.0 (Intention-Aware Hands-Free Computer Interaction)  
**Location**: `C:\Pratham\MORPH`  

---

## 1. Transparent Readiness Tiers

To prevent misleading claims and maintain rigorous scientific integrity, MORPH 2.0 establishes three distinct readiness tiers:

```
+--------------------------------------------------------------------------------+
|                         MORPH 2.0 READINESS TIERS                              |
+--------------------------------------------------------------------------------+
| TIER 1: CORE SYSTEM & INTENTION GATING   | Status: PRODUCTION-READY (RC1)     |
| • 100% Offline local execution           | • 45D feature extraction           |
| • Deterministic 3-state FSM gate         | • Zero video persistence           |
| • Action allowlist sandbox               | • WCAG 2.1 AAA keyboard navigation |
| • SQLite profile version rollback        | • 9-tile AAC Board with SAPI TTS   |
+--------------------------------------------------------------------------------+
| TIER 2: REAL-WORLD EVALUATION SUITE      | Status: VALIDATED INFRASTRUCTURE   |
| • Consented participant onboarding       | • Latin Square trial cueing runner |
| • Ground-truth timestamp event logging   | • Explainable telemetry inspector  |
| • Manifest export & replay benchmark     | • Zero-leakage held-out evaluation |
+--------------------------------------------------------------------------------+
| TIER 3: CLINICAL COHORT TRIALS           | Status: PENDING RECRUITMENT & IRB  |
| • Formal trials with ALS/CP individuals  | • Multi-site motor impairment data |
| • Longitudinal fatigue validation        | • Formal clinical efficacy claims  |
+--------------------------------------------------------------------------------+
```

---

## 2. Research Scope & Disclaimers

1. **Not a Medical Device**:
   MORPH 2.0 is an assistive software engineering and human-computer interaction prototype. It is **not** a certified medical device, diagnostic tool, or emergency call system. It makes no inferences regarding cognitive state, pain, or emotional condition.

2. **Controlled Benchmark Claims vs Live Clinical Efficacy**:
   Reported false activation rates (0.00 FA/hr for Condition C vs 216.4 FA/hr for Condition A) are derived from the canonical 118.05-second benchmark replay challenge (`BenchmarkScenarioSuite`). While synthetic evaluation models realistic perturbations (scale shifts, head rotations, micro-tremors), it does not substitute for longitudinal clinical trials with individuals experiencing severe involuntary spasticity.

3. **Garwood Confidence Limits**:
   Claims of zero false activations in Condition C must always cite the two-sided 95% Garwood Poisson confidence interval ($[0.00, 114.04]$ FA/hr) to account for exposure time limits.

---

## 3. Physical Environmental Limitations

1. **Illumination Extremes**:
   MediaPipe Face Landmarker relies on standard RGB webcam imagery. In extreme low light (<10 lux) or severe backlighting (e.g. seated directly in front of an unshaded window), landmark jitter increases, triggering the fail-closed `TRACKING_LOST` state.
2. **Extreme Head Pose Angles**:
   Head yaw exceeding $\pm 45^\circ$ or pitch exceeding $\pm 30^\circ$ causes self-occlusion of eye/lip landmarks, leading to automatic actuation suppression.
3. **Multi-Face Environment**:
   To prevent malicious or accidental actuation by bystanders or caregivers, the system enforces an `exactly_one_face` invariant. If a second face enters the camera field of view, the system immediately drops to `TRACKING_LOST` in under 33 ms until only the primary user is present.
4. **Facial Muscle Fatigue**:
   Prolonged facial contractions can cause muscle strain. Users must utilize the built-in Rest Advisor to schedule regular pauses during extended communication sessions.
