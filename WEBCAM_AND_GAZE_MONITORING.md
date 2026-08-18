# Webcam & Gaze Attention Monitoring Documentation

## 1. Overview

The Capstone Interview Preparation Tool includes a webcam monitoring feature that displays the candidate's live camera feed and performs real-time face detection during an active interview session.

All detection runs **100% client-side** in the browser using MediaPipe Tasks Vision. No webcam frames are sent to the Flask backend.

---

## 2. Current Implementation Status

### ✅ Feature 1 — Webcam Video Feed

* Uses `navigator.mediaDevices.getUserMedia` to request webcam access.
* Displays the live mirrored webcam feed in the interview monitor panel (top-right).
* Initialization is asynchronous and does not block the interview interface.
* Webcam starts on page load and stops when the session ends.

---

### ✅ Feature 2 — Real-time MediaPipe Face Detection

**Implemented and confirmed working** as of 2026-08-18.

**How it works:**

* The `face_landmarker.task` model (3.6 MB) is loaded from:
  `main_cap/cap/static/models/face_landmarker.task`
* MediaPipe Tasks Vision (`@mediapipe/tasks-vision@0.10.14`) is loaded via dynamic ESM import from jsDelivr CDN (`vision_bundle.mjs`).
* `FaceLandmarker.detectForVideo()` runs every animation frame (~60fps) against the existing `<video>` element.
* Returns 478 facial landmarks per frame when a face is detected.
* **No second webcam stream is created.** The existing `<video>` element is reused.

**UI behavior:**

* 🟢 **Green glowing border** + pulsing green dot + `FACE DETECTED` — face is in frame.
* 🔴 **Red glowing border** + fast pulsing red dot + `NO FACE DETECTED` — face has been absent for >800ms.
* An 800ms debounce prevents flickering between states on brief frame drops.
* GPU delegate is used with automatic CPU fallback.

**Console output (confirmed):**
```
[FaceLandmarker] Initializing...
[FaceLandmarker] MediaPipe module imported OK.
[FaceLandmarker] Fileset resolver ready.
[FaceLandmarker] Model loaded successfully.
[FaceLandmarker] Detection loop started. Waiting for model...
[FaceLandmarker] FACE DETECTED — landmarks: 478
[FaceLandmarker] NO FACE
```

---

## 3. Pending Implementation / Roadmap

### 🔄 3. Eye Gaze Direction Detection

After face landmark tracking is confirmed working, the next step is to estimate the candidate's gaze direction using the landmark positions.

Planned functionality:

* Track the eye center coordinates using key facial landmarks.
* Compute horizontal (X) and vertical (Y) deviation from the camera center.
* Determine whether the candidate is looking toward the screen.
* Detect significant left, right, upward, or downward gaze deviations.
* Combine eye position with head orientation for more reliable attention detection.

Thresholds (planned):
* Horizontal shift > 0.22 (normalized) → looking away
* Vertical shift > 0.20 (normalized) → looking away

---

### 🔄 4. Head Movement and Face-Absence Detection

The system will monitor the candidate's face position and head orientation using the 478 landmarks already being detected.

Planned functionality:

* Detect when the candidate turns significantly away from the screen.
* Detect when the candidate's face leaves the camera frame entirely.
* Display an appropriate on-screen message:

  `👀 Please look into the camera`

* Distinguish brief thinking glances (normal) from sustained look-aways (flagged).

---

### 🔄 5. Attention Warning System

Once gaze and face detection are solid, an attention-warning mechanism will be implemented.

Planned behavior:

* Briefly looking away while thinking → **No warning** (grace period: ~3–4 seconds).
* Continuous gaze deviation for >3 seconds → **Attention warning shown**.
* Face absent for >4 seconds → **Face-absence warning shown**.
* Warning clears only after candidate has returned attention for ~0.5 seconds (debounce, to prevent flicker).

Example:

| Scenario | Behavior |
|---|---|
| Look away for 1–2 seconds | No warning |
| Look away continuously for >3 seconds | ⚠️ Attention warning |
| Face leaves frame for >4 seconds | ⚠️ Face-absence warning |
| Return to camera for 0.5s | Warning clears |

---

### 🔄 6. Attention Metrics and Interview Evaluation

After reliable gaze and attention detection are in place, the system will collect metrics.

Planned metrics:

* Number of attention-loss incidents.
* Duration of each incident.
* Total time looking away.
* Approximate attention/engagement ratio over the session.
* Number of face-absence events.

These metrics will eventually be incorporated into the final interview performance assessment shown on the analytics dashboard.

---

## 4. Backend Status

The current implementation **does not perform backend webcam streaming or video processing**.

* Webcam is accessed entirely browser-side via `navigator.mediaDevices.getUserMedia`.
* Face Landmarker runs entirely browser-side via MediaPipe WASM.
* The Flask backend serves the page and static files only.
* The model file is served as a static asset: `GET /static/models/face_landmarker.task`

---

## 5. Key Files

| File | Role |
|---|---|
| `main_cap/cap/templates/index.html` | All webcam + detection logic |
| `main_cap/cap/app.py` | Flask server (serves page + static files) |
| `main_cap/cap/static/models/face_landmarker.task` | MediaPipe model (3.6 MB) |

---

## 6. Development Progress

| Feature | Status |
|---|---|
| Webcam access | ✅ Done |
| Live webcam display | ✅ Done |
| MediaPipe model loading | ✅ Done |
| Face detection (presence) | ✅ Done |
| Facial landmark tracking (478 pts) | ✅ Done |
| Proctoring-style UI indicator | ✅ Done |
| Eye/iris gaze direction estimation | 🔄 Next |
| Head movement / look-away detection | 🔄 Pending |
| Attention warning system (3–4s timer) | 🔄 Pending |
| Face-absence warning | 🔄 Pending |
| Attention metrics collection | 🔄 Pending |
| Integration with final evaluation | 🔄 Pending |

---

## 7. Next Step

The immediate next development task is **Eye Gaze Direction Detection** — using the 478 landmarks already returned by Face Landmarker to determine where the candidate is looking (toward screen vs. away). This feeds directly into the attention warning system.
