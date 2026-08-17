# Webcam & Gaze Attention Monitoring Documentation

## 1. Overview
The Capstone Interview Preparation Tool includes an integrated real-time video monitoring interface during active interview sessions. This system provides video feedback and an attention monitoring framework.

---

## 2. Current Implementation Status

### ✅ Implemented Features:
1. **Webcam Video Stream**:
   - `navigator.mediaDevices.getUserMedia` integration with fallback handling.
   - Live mirrored camera feed displayed in the top-right monitoring panel (`#interview-monitor-panel`).
   - Seamless loading with non-blocking async initialization (does not block resume upload or question flow).
   - Session lifecycle handling (auto-starts on session initialization, clean shutdown when session ends).

2. **Backend Serving Configuration**:
   - Flask application configured with static assets routing (`static_folder="static"` in `app.py`).
   - MediaPipe Face Landmarker model asset storage in `static/models/face_landmarker.task`.

3. **Attention Warning UI**:
   - Animated visual warning banner (`#gaze-warning`) with pulsing highlight styling (`@keyframes gazeWarnPulse`).
   - Multi-tier alert text support:
     - `👀 Please focus on the screen`
     - `👀 Please look at the screen`

---

## 3. Pending Implementation / Roadmap

### 🔄 Eye Gaze & Attention Warning Detection (To Be Fully Implemented):
While the webcam feed and warning UI components are in place, real-time gaze detection and attention warning logic require further enhancements:

1. **Robust Face Landmarker & Iris Tracking**:
   - Load and stabilize client-side landmark tracking using MediaPipe Vision Tasks / TensorFlow.js or OpenCV.js.
   - Extract iris/pupil coordinates relative to eye corner boundaries (inner and outer canthi) to compute precise gaze vectors.

2. **Look-Away & Thinking Heuristics (Generalized Tolerance)**:
   - **Thinking Glances**: Natural brief look-aways (e.g., looking up or to the side while formulating thoughts) should be permitted within a calibrated grace period (~3.0 to 4.0 seconds).
   - **Prolonged Distraction**: Sustained gaze deviations (> 4.0s) or absence from camera view should trigger the visual warning notification.
   - **Debouncing & Hysteresis**: Ensure warning dismissals require sustained re-focus (~0.5s) to eliminate rapid UI flickering.

3. **Metrics & Interview Evaluation Reporting**:
   - Track total attention loss incidents during an interview.
   - Feed engagement score/attention ratio into final candidate performance assessment.

---

## 4. Key Files Involved
- **Frontend Template & Gaze Scripts**: `main_cap/cap/templates/index.html`
- **Flask Server Backend**: `main_cap/cap/app.py`
- **Model Storage**: `main_cap/cap/static/models/face_landmarker.task`
