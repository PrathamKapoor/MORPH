# MORPH 2.0 Security Architecture & Threat Model

**Author**: Pratham Kapoor <prathamkapoor027@gmail.com>  
**Product**: MORPH 2.0 (Intention-Aware Hands-Free Computer Interaction)  

---

## 1. Trust Boundaries & Assumptions

1. **Host Operating System**: Windows 10/11 running as standard unprivileged user account.
2. **Camera Hardware**: DirectShow-compatible webcam connected locally.
3. **Network Isolation**: The application operates in complete network isolation; zero outbound internet sockets or telemetry connections are established.
4. **Data Storage**: Local SQLite database stored in application working directory (`data/morph.db`), secured by Windows NTFS file ACLs.

---

## 2. Threat Vectors & Mitigations

### 2.1 Video Stream Interception & Eavesdropping
- **Threat**: Malicious processes or unauthorized users intercepting raw camera imagery of vulnerable individuals.
- **Mitigation (ADR-002)**: Zero raw video or image frames are ever persisted to disk, temp directories, or persistent logs. BGR frames exist solely in volatile heap memory and are immediately overwritten/freed after landmark extraction.

### 2.2 Arbitrary Shell Command Execution
- **Threat**: Injected malicious commands or corrupted profile actions executing arbitrary operating system commands (e.g. `cmd.exe`, PowerShell scripts).
- **Mitigation (ADR-018)**: Strict action allow-list sandboxing. The `ActionDispatcher` dispatches only strictly enumerated internal `ActionType` values (`NEXT_TILE`, `PREV_TILE`, `SELECT_TILE`, `BACK_CATEGORY`, `EXPAND_CATEGORY`, `SPEAK_TEXT`, `PAUSE_SESSION`, `RESUME_SESSION`). Any non-allowlisted string is rejected with a logged security violation.

### 2.3 Bypass Intent Gating via Fast Involuntary Spasms
- **Threat**: Muscle twitches or involuntary clonus causing unintended high-consequence command dispatches.
- **Mitigation**: Pure 3-state deterministic FSM. Command confirmation requires maintaining continuous landmark alignment above threshold for a minimum of 250 ms ($T_{hold}$), followed by mandatory resting posture release ($T_{release} = 150$ ms) and refractory cooldown ($T_{cooldown} = 300$ ms).

### 2.4 Bystander / Multi-Face Interference
- **Threat**: A family member or caregiver appearing in the frame triggering unintended facial gesture actions.
- **Mitigation**: Strict single-face invariant. If `face_count != 1`, the system immediately transitions to `TRACKING_LOST` in under 33 ms, suppressing all gesture interpretation until only the primary user is detected.

### 2.5 Corrupted Profile Injection & SQLite Tampering
- **Threat**: Tampered database records causing null-pointer crashes or malicious prototype loading.
- **Mitigation**: Strongly-typed SQLite migrations, schema version tracking, schema foreign key constraints, atomic in-transaction version rollback, and `PRAGMA busy_timeout = 10000;` concurrency locks.
