# Webcam & Attention Monitoring Documentation

## 1. Overview

The Capstone Interview Preparation Tool includes an integrated real-time webcam monitoring, pre-interview verification, and candidate attention-tracking system for automated interview sessions.

The system provides:
- Pre-interview camera setup check and environment validation.
- Live webcam monitoring during active interview sessions.
- Real-time face detection and 478-point facial landmark tracking.
- Multi-face / second-person presence detection.
- Head-pose estimation (Yaw & Pitch).
- Eye/iris gaze attention direction estimation.
- Sustained attention-loss and face-absence detection.
- Visual status indicators and context-aware audio warnings.
- Microphone-aware silent warning suppression during voice answer recording.
- Real-time attention score computation and session evaluation metrics.

All video frames and computer vision algorithms are processed **100% client-side** in the browser using MediaPipe Tasks Vision. Raw webcam feeds are never transmitted or stored on the backend server.

---

## 2. Pre-Interview Camera Setup Check

Before an interview begins, the application executes a mandatory pre-interview camera check overlay (`showCameraSetup()`) to verify hardware and positioning.

```
       [ Start Interview Clicked ]
                   │
                   ▼
     ┌───────────────────────────┐
     │ Pre-Interview Setup Modal │
     └─────────────┬─────────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼
   [ BLOCKING CHECKS ]   [ WARNING CHECKS ]
   • Camera Available    • Face Centered
   • Face Detected       • Distance / Scale
   • Single Face Only    • Room Lighting
          │                 │
          ▼                 ▼
   Must Pass to      Suggestions Only
   Enable Continue   (Continue Allowed)
```

### Checklist & Verification Rules

| Check | DOM Element ID | Category | Logic & Thresholds | Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **Camera Available** | `#csc-camera` | **BLOCKING** | Requests `getUserMedia({ video: true })` | Fails if camera is missing or access denied. Disables "Continue Interview". |
| **Face Detected** | `#csc-face` | **BLOCKING** | `faceLandmarks.length >= 1` | Fails if candidate is out of view. Disables "Continue Interview". |
| **One Face Only** | `#csc-one` | **BLOCKING** | `faceLandmarks.length === 1` | Fails if multiple people are in frame. Disables "Continue Interview". |
| **Face Centered** | `#csc-center` | **WARNING** | Normalized bounding center within $\pm 0.28$ of frame center | Warning (`⚠️`) if face is off-center. Candidate may still continue. |
| **Distance & Visibility** | `#csc-dist` | **WARNING** | Face area ratio between $4.5\%$ and $55\%$ of frame; edges uncropped | Warning (`⚠️`) if candidate is too far, too close, or cropped. |
| **Lighting Adequate** | `#csc-light` | **WARNING** | Samples face & frame pixel luminance ($Y = 0.299R + 0.587G + 0.114B$) | Warning (`⚠️`) if mean luminance $< 65/255$. Hidden if unmeasurable. |

### User Instructions & State Handling
- **Blocking Failures:** "Continue Interview" remains disabled until camera is available and exactly one face is detected.
- **Warning-Only Conditions:** If only warnings remain (e.g., low light or slightly off-center), the system enables "Continue Interview" and displays:
  > *"You can continue now — items marked ⚠️ are suggestions, not requirements."*
- **Cleanup (`_csTeardown`):** Stops temporary setup webcam streams so the main interview gaze-monitoring system cleanly acquires its stream upon start.

---

## 3. Second-Person & Multi-Face Detection

The face tracking pipeline continuously monitors the number of faces detected in the webcam frame (`faces.length`).

```
                    Webcam Frame
                         │
                         ▼
             MediaPipe FaceLandmarker
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
      faces.length === 1      faces.length > 1
             │                       │
             ▼                       ▼
     Normal Candidate       [ SECOND-PERSON DETECTED ]
     Gaze Monitoring        • Visual warning triggered
                            • Candidate gaze pinned to faces[0]
                            • Second person's gaze ignored
```

### Key Technical Rules:
1. **Primary Candidate Isolation:** The system treats `faces[0]` as the primary candidate. The landmarks of secondary faces (`faces[1]`, etc.) are explicitly ignored for gaze coordinates, preventing another person from driving the candidate's gaze metrics.
2. **Visual & Audio Alert:** When `faces.length > 1`, the system immediately flags a security warning state (`"Multiple faces detected in frame"`).
3. **Session Scoring Impact:** Prolonged second-person presence triggers face-absence/integrity warning counters in `attentionMetrics`.

---

## 4. Microphone-Aware Silent Warnings During Voice Answers

To ensure high-quality voice answer recording and prevent audio feedback corruption during Speech-to-Text (STT), the warning system monitors candidate microphone activity (`isRecordingAudio`).

```
              Attention / Gaze Deviation Detected
                               │
                               ▼
                   Is Candidate Recording Voice?
                   (isRecordingAudio === true)
                               │
                      ┌────────┴────────┐
                      ▼                 ▼
                     YES                NO
                      │                 │
                      ▼                 ▼
             [ SILENT WARNING ]    [ DUAL WARNING ]
             • Visual Banner ONLY  • Visual Banner
             • TTS Muted           • Spoken TTS Warning
```

### Implementation Details:
- **Speech Synthesis Suppression:** When `isRecordingAudio` is `true`, spoken text-to-speech alerts (`speechSynthesis.speak()`) are strictly suppressed.
- **Transcript Protection:** Suppressing spoken warnings during active voice answer recording prevents the microphone from capturing synthesized interviewer warning audio and corrupting the candidate's spoken answer transcript.
- **Visual Continuity:** On-screen visual alert banners remain active so the candidate receives immediate feedback without audio interference.
- **Non-Recording Behavior:** When the microphone is idle (not recording), both visual and spoken TTS audio warnings operate normally.

---

## 5. Real-Time Face & Gaze Tracking Architecture

### 478-Point Facial Landmark Processing
MediaPipe Tasks Vision processes live `<video>` frames to generate 478 3D facial landmarks.

```
       Webcam Stream ──► MediaPipe Landmarker ──► 478 Landmarks
                                                       │
               ┌───────────────────────┬───────────────┴───────────────┐
               ▼                       ▼                               ▼
       Face Presence Bounding     Head Pose Vector             Eye & Iris Landmarks
       • Bounding box area      • Yaw (Horizontal)           • Left/Right Iris Centers
       • Frame edge margins     • Pitch (Vertical)           • Eye Aspect Ratio (EAR)
```

### Head Pose & Gaze Estimation
- **Head Orientation (Yaw & Pitch):** Calculated from landmark transformations to detect head turns (LEFT, RIGHT, UP, DOWN).
- **Eye Gaze Vector:** Iris center position relative to eye corners determines whether gaze is directed at the screen or away.
- **Temporal Debouncing:** Frame results pass through a temporal hysteresis filter to prevent single-frame glitches or blinks from triggering false warnings.

---

## 6. Real-Time Attention Evaluation & Session Metrics

Session attention data is accumulated client-side in the `attentionMetrics` structure:

```javascript
let attentionMetrics = {
    sessionStartedAt: null,
    totalWarnings: 0,
    faceAbsentWarnings: 0,
    totalDeviationMs: 0,
    livenessRechecks: 0,
    livenessFailures: 0
};
```

### Score Computation Formula
At the end of an interview session, the final attention score ($0 - 100\%$) is derived dynamically:

$$\text{Attention Score} = \max\left(0, 100 - (\text{Total Warnings} \times 4) - (\text{Face Absent Warnings} \times 6) - (\text{Liveness Failures} \times 5)\right)$$

### Dashboard Presentation
Derived metrics are rendered directly in the post-interview summary dashboard:
- **Attention Score %**
- **Sustained Attention Warnings**
- **Face-Not-Visible Warnings**
- **Liveness Re-checks & Failures**

---

## 7. Current System Architecture Summary

```
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                           CLIENT BROWSER (UI)                               │
 │                                                                             │
 │  ┌───────────────────────┐      ┌────────────────────────────────────────┐  │
 │  │ Pre-Interview Check   │ ───► │ Main Interview Session                 │  │
 │  │ • Camera & Face Check │      │ • 478-Point Landmark Tracking          │  │
 │  │ • Bounding & Lighting │      │ • Head Pose & Iris Gaze Estimation     │  │
 │  └───────────────────────┘      │ • Multi-Face Detection                 │  │
 │                                 │ • STT-Aware Silent Warnings            │  │
 │                                 │ • Session Metrics Accumulator          │  │
 │                                 └───────────────────┬────────────────────┘  │
 └─────────────────────────────────────────────────────│───────────────────────┘
                                                       │ Post-Session Summary
                                                       ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                           FLASK BACKEND (API)                               │
 │ • Serves index.html template                                                │
 │ • Evaluates answer responses & resume intelligence                          │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Current Implementation Matrix

| Component | Status | Description |
| :--- | :---: | :--- |
| **Webcam Stream Acquisition** | ✅ Implemented | Asynchronous `getUserMedia()` stream management. |
| **Pre-Interview Camera Check** | ✅ Implemented | Modal overlay verifying camera, face presence, single face, centering, scale, and lighting before interview start. |
| **478 Facial Landmarks** | ✅ Implemented | MediaPipe Tasks Vision FaceLandmarker pipeline. |
| **Head Pose Tracking** | ✅ Implemented | Yaw/Pitch orientation calculation (CENTER, LEFT, RIGHT, UP, DOWN). |
| **Iris Gaze Estimation** | ✅ Implemented | Iris landmark deviation measurement for screen focus detection. |
| **Second-Person Detection** | ✅ Implemented | Multi-face detection (`faces.length > 1`) triggering visual warning while keeping primary gaze bound to candidate (`faces[0]`). |
| **Silent Voice Warnings** | ✅ Implemented | Mutes TTS audio warnings while microphone/STT recording is active (`isRecordingAudio`). |
| **Attention Loss Warnings** | ✅ Implemented | Visual banners and audio alerts triggered after sustained deviation. |
| **Face Absence Detection** | ✅ Implemented | Flagged when candidate face leaves camera frame. |
| **Active Liveness Verification**| ✅ Implemented | Blink and head movement verification challenges. |
| **Session Metrics & Dashboard**| ✅ Implemented | Real-time score calculation and post-interview metric presentation. |

---

## 9. Current Technical Limitations

1. **Browser Hardware Dependencies:** Face tracking performance relies on client CPU/GPU capabilities for canvas frame rendering.
2. **Extreme Low Light:** While lighting luminance checks warn candidates during pre-interview setup, severe dark environments may reduce landmark precision.
3. **Webcam Angle Offset:** Extreme side camera angles (e.g., secondary external monitor setups) can increase baseline yaw, requiring candidates to face their primary laptop display.

Future Improvements
1. Improve Attention Score accuracy
Tune thresholds/weighting so normal thinking and brief glances aren't over-penalized.
2. Host MediaPipe locally
Remove dependency on the jsDelivr CDN for better reliability/offline support.
3. Improve glasses/reflection handling
Reduce false gaze warnings caused by glasses and lighting/reflections.
4. Practice vs Mock Assessment modes
Practice: lenient, coaching-focused, camera optional.
Mock Assessment: stricter monitoring, camera required, attention included in reports.

