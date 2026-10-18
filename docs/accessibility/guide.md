# MORPH 2.0 Accessible Interaction & User Guide

**Author**: Pratham Kapoor <prathamkapoor027@gmail.com>  
**Product**: MORPH 2.0 (Intention-Aware Hands-Free Computer Interaction)  

---

## 1. Principles of Accessible Interaction

MORPH 2.0 is designed for users with significant motor limitations resulting from ALS, cerebral palsy, spinal cord injuries, or muscular dystrophy. Interaction requires voluntary control over 1 to 3 distinct facial or head movements.

### Key Interaction Safeguards:
1. **Zero Unintentional Actuation**: The deterministic intention engine requires holding a gesture for 250 ms before confirmation, eliminating accidental triggers from quick twitches or conversational speech.
2. **Mandatory Rest Phase**: After every confirmed command, the user must return to their resting posture for 150 ms before another command can be accepted.
3. **Emergency Caregiver Overrides**: Caregivers can press **Spacebar** or **Escape** at any moment to immediately lock the system into the fail-closed `PAUSED` state.

---

## 2. Choosing Personal Gestures

When setting up a profile, select 2 or 3 gestures that are comfortable to produce repeatedly without muscle strain:

- **Brow Raise**: Raising both eyebrows upward (suitable for primary selection or "Next Tile").
- **Smile / Lip Corner Pull**: Pulling lips outward or smiling (suitable for confirmation or "Select").
- **Mouth Open / Jaw Drop**: Dropping the lower jaw slightly (suitable for "Previous Tile" or "Speak Phrase").
- **Cheek Twitch / Asymmetric Sneer**: Subtle unilateral movement if bilateral control is impaired.

> [!TIP]
> Ensure the chosen gestures produce distinct landmark movements. The built-in gesture conflict analyzer will automatically warn you if two gestures are too geometrically similar.

---

## 3. Communication Board Operation

The communication board features 9 high-contrast phrase tiles arranged in a 3x3 grid:

```
+--------------------+--------------------+--------------------+
|     1. Yes         |      2. No         |    3. Thank You    |
+--------------------+--------------------+--------------------+
| 4. Please Help Me  |  5. I Am In Pain   |    6. Need Water   |
+--------------------+--------------------+--------------------+
|  7. Adjust Seating |  8. More Options   |     9. Emergency   |
+--------------------+--------------------+--------------------+
```

### Rotary Navigation:
- **NEXT_TILE**: Advances the active selection ring clockwise.
- **PREV_TILE**: Moves the selection ring counter-clockwise.
- **SELECT_TILE**: Utters the selected phrase through Windows SAPI speech synthesis.
- **BACK / EXPAND**: Accesses sub-categories or returns to top-level phrases.

---

## 4. Continuous Session Rest Advisor

Sustained facial muscle contractions can cause fatigue. MORPH includes an automated, non-medical Rest Advisor:

- **20-Minute Advisory**: When active communication time reaches 20 minutes, an amber rest advisory banner appears recommending a 2-minute break.
- **Smart Activity Tracking**: Time spent holding gestures or in `PAUSED` / `TRACKING_LOST` states does not accumulate toward fatigue time.
- **Caregiver Controls**: 1-click **Take Break** and **Snooze (5 min)** buttons allow immediate session pacing.

---

## 5. Keyboard Navigation (WCAG 2.1 AAA)

For facilitators or switch-access users:
- **Tab / Shift+Tab**: Navigates sequentially across all actionable UI elements.
- **Visible Focus Rectangles**: 2px high-contrast cyan outline on every focused widget.
- **Enter / Space**: Activates buttons and toggles.
- **F1 - F6**: Quick navigation shortcuts to Home, Studio, Board, Settings, Monitor, and Lab views.
- **Spacebar / Escape**: Instant Emergency Stop / Global Pause.
