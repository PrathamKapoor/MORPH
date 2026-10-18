# Environment & Platform Discovery

- **Project**: MORPH 2.0
- **Recorded Date**: 2026-10-17
- **Author**: Pratham Kapoor <prathamkapoor027@gmail.com>
- **Project Root**: `C:\Pratham\MORPH`

---

## 1. Operating System & Hardware

- **Operating System**: Microsoft Windows 11 Home Single Language (Build 26100)
- **Host Architecture**: ARM64
- **Process / Execution Architecture**: ARM64 with Windows 11 AMD64 compatible binary execution
- **Available Disk Space**: ~811 GB free on drive `C:\`
- **CPU Capabilities**: TensorFlow Lite XNNPACK delegate for CPU supported and operational

---

## 2. Camera Hardware & Sensor Capture

- **Device Name**: Integrated Camera
- **Device ID**: `USB\VID_04F2&PID_B83E&MI_00\5&39400099&1&0000`
- **Hardware Status**: OK
- **OpenCV Backend**: DirectShow (`cv2.CAP_DSHOW`)
- **Probed Resolution**: 640 x 480 @ 30 FPS default, configurable up to 1280 x 720 (720p)
- **Verified Capture**: `ret=True`, valid 3-channel BGR frame read verified on hardware

---

## 3. Python Runtime & Virtual Environment

- **Virtual Environment Path**: `C:\Pratham\MORPH\.venv`
- **Python Version**: Python 3.12.10 (tags/v3.12.10:00cf0d5, Feb 4 2025)
- **Pip Version**: 25.0.1
- **Package Installation Mode**: Isolated local `.venv`, local cache at `C:\Pratham\MORPH\.cache\pip`, temporary files at `C:\Pratham\MORPH\.tmp`
- **Core Packages Verified**:
  - `numpy==2.5.4`
  - `opencv-python==5.0.0.93`
  - `PySide6==6.12.0` (Qt 6.12)
  - `mediapipe==1.1.1`
  - `pyttsx3==2.99`
  - `pytest==9.1.1`
  - `ruff==0.17.1`

---

## 4. Model Asset Manifest

- **Model File**: `models/face_landmarker.task`
- **Manifest File**: `models/face_landmarker.task.manifest.json`
- **Source URL**: `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task`
- **File Size**: 3,758,596 bytes
- **SHA-256 Checksum**: `64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff`
- **Model License**: Apache License 2.0 (Google MediaPipe)
- **Execution Mode**: Local offline file inference via `mediapipe.tasks.python.vision.FaceLandmarker`

---

## 5. Local Speech Synthesis (TTS)

- **Engine**: Microsoft Speech API (SAPI 5.4 / System.Speech)
- **Installed Voices**:
  - `Microsoft David Desktop` (Culture: en-US, Gender: Male, Adult)
  - `Microsoft Zira Desktop` (Culture: en-US, Gender: Female, Adult)
- **Offline Status**: 100% offline; zero cloud network dependency for speech output

---

## 6. Git Identity & Repository Configuration

- **Repository Root**: `C:\Pratham\MORPH`
- **Default Branch**: `main`
- **Local User Name**: `PrathamKapoor`
- **Local User Email**: `prathamkapoor027@gmail.com`
- **Use Config Only**: `true` (enforced locally via `git config --local user.useConfigOnly true`)
- **Remote Status**: No remote configured yet; local commits maintained. Remote URL requires explicit verification before push.
