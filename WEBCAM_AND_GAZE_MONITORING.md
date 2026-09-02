Webcam & Attention Monitoring Documentation
1. Overview

The Capstone Interview Preparation Tool includes an integrated real-time webcam monitoring and attention-monitoring system for interview sessions.

The system provides:

Live webcam monitoring.
Real-time face detection.
478-point facial landmark tracking.
Head-pose detection.
Eye/iris-based attention estimation.
Sustained attention-loss detection.
Face-absence detection.
Visual and audio warnings.

All webcam and attention processing is performed client-side in the browser using MediaPipe Tasks Vision. Webcam frames are not streamed to or processed by the Flask backend.

2. Webcam Video Feed
✅ Implemented

The application uses:

navigator.mediaDevices.getUserMedia()

to request access to the candidate's webcam.

The live video is displayed in the interview monitoring panel in the top-right portion of the interface.

Implementation details
The existing <video> element is reused for monitoring.
The webcam feed is mirrored for a natural camera-preview experience.
Webcam initialization is asynchronous.
Camera initialization does not block the main interview interface.
The webcam is stopped when the interview/session ends.
No second webcam stream is created.
3. Real-Time Face Detection and Facial Landmarks
✅ Implemented

The application uses MediaPipe Tasks Vision Face Landmarker for real-time facial analysis.

The model is stored at:

main_cap/cap/static/models/face_landmarker.task

MediaPipe Tasks Vision is loaded in the browser and FaceLandmarker.detectForVideo() processes frames from the existing webcam video element.

When a face is detected, the system receives 478 facial landmarks.

These landmarks provide the foundation for:

Face-presence detection.
Head-pose estimation.
Eye/iris analysis.
Attention monitoring.
Face presence

The system continuously determines whether a candidate's face is visible.

Conceptually:

Webcam frame
     ↓
Face Landmarker
     ↓
Face detected?
   ↙       ↘
 YES       NO
  ↓         ↓
Continue   Face absence
monitoring detection

A debounce/grace period prevents temporary detection failures from immediately triggering a warning.

4. Head-Pose Detection
✅ Implemented

The application uses the facial transformation information produced by MediaPipe to estimate the candidate's head orientation.

The system tracks:

CENTER
LEFT
RIGHT
UP
DOWN
Head-pose calculation

The facial transformation matrix is used to estimate:

Yaw — horizontal head rotation.
Pitch — vertical head rotation.

The calculated values are smoothed to reduce small frame-to-frame fluctuations.

A threshold/dead-zone prevents small natural movements from continuously changing the detected state.

Expected physical mapping
Candidate movement	System state
Facing normally	HEAD: CENTER
Turning head left	HEAD: LEFT
Turning head right	HEAD: RIGHT
Looking/tilting upward	HEAD: UP
Looking/tilting downward	HEAD: DOWN

Head pose is used as one of the signals for determining sustained attention loss.

5. Eye / Iris Attention Detection
✅ Implemented

The application also uses eye and iris landmarks obtained from MediaPipe to estimate the candidate's general eye-attention direction.

The system does not attempt to provide hardware-level, pixel-perfect eye tracking.

Instead, the eye information is used as an additional signal to determine whether the candidate is generally looking toward the interview screen or looking away.

The internal eye-attention analysis can distinguish between states such as:

CENTER
LEFT
RIGHT
UP
DOWN
UNKNOWN

For attention decisions, these are interpreted primarily as:

Eyes toward screen
        vs.
Eyes away
Why eye attention is used

Head direction and eye direction provide different information.

For example:

Head: CENTER
Eyes: Away

can indicate that the candidate is looking away with their eyes while keeping their head relatively still.

Similarly:

Head: LEFT
Eyes: LEFT/Away

provides stronger evidence that the candidate is looking away from the interview.

Therefore, eye attention is used as a supporting signal, rather than as a standalone warning mechanism.

6. Spectacles and Eye-Detection Robustness

The system is designed to operate with normal spectacles.

Webcam-based eye analysis can be affected by:

Glass reflections.
Temporary iris landmark loss.
Blinking.
Small landmark fluctuations.
Partial eye occlusion.

To reduce false detections, the attention system uses both eyes and temporal stability rather than treating a single frame as definitive.

Temporary unreliable eye measurements should not immediately result in an attention warning.

The system prioritizes sustained attention deviation rather than reacting to individual noisy frames.

7. Unified Attention Detection
✅ Implemented

The attention-monitoring system combines multiple signals:

             Webcam
                ↓
        MediaPipe Landmarker
                ↓
      ┌─────────┼─────────┐
      ↓         ↓         ↓
   Face       Head       Eyes
 Presence     Pose     Attention
      └─────────┼─────────┘
                ↓
        Attention Decision
                ↓
          Duration Check
                ↓
        Warning if sustained

The system therefore does not depend on a single frame or a single measurement.

Examples
Face	Head	Eyes	Result
Present	Center	Screen	Normal
Present	Center	Away briefly	Normal
Present	Left	Away	Potential attention loss
Present	Down	Away	Potential attention loss
Absent	—	—	Face-absence state

Brief natural movements are tolerated.

8. Attention Warning System
✅ Implemented

The system uses a duration-based warning mechanism.

A brief glance away should not immediately result in a warning.

Instead, attention deviation must remain sustained for a configured period.

General behavior
Normal attention
      ↓
Brief deviation
      ↓
No warning
      ↓
Sustained deviation
      ↓
Attention warning

The system therefore distinguishes between natural interview behavior and prolonged distraction.

Current behavior
Situation	Result
Looking at screen normally	No warning
Brief glance away	No warning
Brief thinking movement	No warning
Sustained attention deviation	Attention warning
Face completely leaves frame	Face-absence warning
Candidate returns to normal	Warning clears
9. Visual Warning
✅ Implemented

When sustained attention loss is detected, the monitoring interface displays a visual warning.

The attention warning uses messaging such as:

Please return your attention to the screen.

The warning is designed to be integrated into the existing monitoring panel rather than appearing as a browser alert.

The warning:

Appears after sustained attention loss.
Remains visible while the condition continues.
Clears after stable recovery.
Uses debounce/hysteresis to reduce flickering.
Does not react to individual noisy frames.
10. Face-Absence Detection and Warning
✅ Implemented

Face absence is handled separately from normal attention deviation.

If the candidate completely leaves the camera frame and the face remains undetected for the configured duration, the system enters the face-absence state.

This allows the application to distinguish between:

Attention loss

The candidate's face is visible, but they have been looking away for a sustained period.

Face absence

The candidate is no longer visible to the camera.

The monitoring UI can therefore provide an appropriate face-visibility warning without confusing it with ordinary gaze/head movement.

11. Audio Warning
✅ Implemented

The attention-monitoring system supports an audible warning using browser speech synthesis.

The audio warning is triggered only for a sustained attention event rather than continuously.

The system uses cooldown/event logic to prevent repeated speech while the candidate remains distracted.

The general behavior is:

Attention loss detected
        ↓
Visual warning
        ↓
Audio warning
        ↓
Cooldown
        ↓
No repeated audio spam

When the candidate returns to normal attention, the warning state can be cleared and a future sustained attention event can generate a new warning.

12. Warning Recovery and Debouncing
✅ Implemented

The system does not immediately remove a warning from a single good frame.

A short recovery period is required before the warning is cleared.

This prevents behavior such as:

Away
↓
Screen
↓
Away
↓
Screen

from causing the warning UI to rapidly flicker.

The same principle is applied when detecting face presence/absence so that temporary frame drops do not immediately change the monitoring state.

13. Unified Monitoring Interface
✅ Implemented

The webcam monitoring interface is integrated into a single monitoring panel.

The panel provides:

Webcam preview.
Monitoring state.
Head-position information.
Attention/warning state.
Face-presence state when applicable.

The monitoring interface is intended to appear as part of the AI interviewer rather than as a separate developer/debugging interface.

14. Client-Side Processing Architecture

All webcam analysis currently occurs in the browser.

The processing pipeline is:

Browser Webcam
      ↓
<video> element
      ↓
MediaPipe Face Landmarker
      ↓
478 Facial Landmarks
      ↓
┌──────────────┬───────────────┬───────────────┐
│              │               │
Face         Head Pose      Eye Attention
Detection
│              │               │
└──────────────┴───────────────┘
               ↓
       Attention Decision
               ↓
      Warning / Monitoring UI
               ↓
        Optional Audio

No continuous webcam video is sent to the Flask backend.

15. Backend Status
✅ Current architecture

The Flask backend is not responsible for webcam streaming or video processing.

The backend primarily:

Serves the application.
Serves static assets.
Provides the MediaPipe model as a static resource.

The MediaPipe model is served from:

/static/models/face_landmarker.task

The actual webcam processing remains client-side.

16. Key Files
File	Responsibility
main_cap/cap/templates/index.html	Webcam, MediaPipe, face detection, head pose, eye attention, warning system and monitoring UI
main_cap/cap/app.py	Flask server and application/static-file serving
main_cap/cap/static/models/face_landmarker.task	MediaPipe Face Landmarker model
17. Current Development Status

Feature	Status
Webcam access	✅ Complete
Live webcam display	✅ Complete
MediaPipe model loading	✅ Complete
Face detection/presence	✅ Complete
478-point facial landmark tracking	✅ Complete
Facial transformation matrix	✅ Complete
Head direction — Center	✅ Complete
Head direction — Left/Right	✅ Complete
Head direction — Up/Down	✅ Complete
Eye/iris attention estimation	✅ Implemented
Per-user gaze adaptation	✅ Implemented
Gaze smoothing/hysteresis	✅ Implemented
Sustained attention detection	✅ Complete
Attention warning	✅ Complete
Face-absence detection	✅ Complete
Face-absence warning	✅ Complete
Visual warning	✅ Complete
Audio warning	✅ Complete
Warning cooldown	✅ Complete
Recovery/debounce	✅ Complete
Unified monitoring UI	✅ Complete
Active liveness verification	✅ Implemented
Randomized periodic liveness	✅ Implemented
No-blink soft liveness trigger	✅ Implemented
Attention-loss metrics	✅ Implemented
Final evaluation integration	🔄 Dashboard presentation

18. Attention Evaluation Metrics

The real-time monitoring system records session-level attention information for the final interview evaluation. These metrics are analytics only and do not control gaze detection, warning thresholds, calibration or liveness.

The system tracks:

- Total monitoring duration.
- Valid monitoring duration.
- Approximate on-screen/attentive duration.
- Approximate Away duration.
- Number of attention-warning events.
- Number of face-absence events.
- Number of successful liveness challenges.
- Number of failed liveness challenges.
- Optional duration of individual Away episodes.

Suggested calculations:

Attention Loss % =
(Away Time / Valid Monitoring Time) × 100

Attention Score =
max(0, 100 - Attention Loss %)

At interview completion, the derived metrics should be sent through the existing Flask/session flow so the final evaluation dashboard can display the candidate's attention score and supporting statistics.

Example final dashboard data:

Attention Score:       91%
Attention Loss:         9%
Attention Warnings:     2
Face Absence Events:    1
Liveness Passed:        3
Liveness Failed:        0

The Flask backend should receive/store the derived session metrics. Continuous raw webcam video does not need to be uploaded.

19. Active Liveness Verification

The project uses active liveness verification rather than attempting to prove liveness from continuous facial movement.

A static-face watchdog is intentionally excluded because ordinary MediaPipe facial landmarks cannot reliably distinguish a genuinely still person from a still photograph or a rigidly moved phone.

Initial liveness

At the beginning of the interview, the system requests a randomized two-action challenge, for example:

"Blink once AND turn your head slightly LEFT."

or:

"Blink once AND turn your head slightly RIGHT."

Both actions are verified using the existing MediaPipe landmarks. After successful verification, the system immediately returns to normal webcam, gaze and attention monitoring.

Occasional liveness

During a longer interview, another randomized liveness challenge can occur approximately every 3–5 minutes.

Rules:

- Randomize the actual interval rather than using a predictable exact time.
- Enforce a hard minimum cooldown of approximately 60–90 seconds.
- Allow one reasonable retry after a failed challenge.
- Do not repeatedly trigger challenges while the same challenge is active.
- Do not block the MediaPipe frame-processing loop.
- After passing, immediately return to normal monitoring.

A typical 15–20 minute interview should therefore have only a few liveness checks, not constant challenges.

No-blink soft trigger

Blink detection can provide an additional lightweight trigger for an active liveness check.

If a valid face remains visible and no reliable blink has been detected for a considerable period, the system may request an active liveness challenge.

The flow is:

Face visible
    ↓
Normal monitoring
    ↓
Extended period with no detected blink
    ↓
Soft liveness trigger
    ↓
"Blink once + turn head LEFT/RIGHT"
    ↓
PASS → Normal monitoring
FAIL → One retry → Normal monitoring

No detected blink must NOT directly mean "fake face". Real candidates naturally have different blink rates and can go several seconds without blinking. Therefore, the no-blink condition is only a soft trigger; the active challenge is the actual liveness verification.

The no-blink timer should reset after a reliable blink and after successful liveness verification.

20. Separation of Attention and Liveness

Liveness remains a separate state from attention monitoring.

                    WEBCAM
                       ↓
                MediaPipe Landmarker
                       ↓
                 478 Landmarks
                       ↓
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
   Face Presence    Head Pose      Eye Gaze
        │              │              │
        │              │         Attention State
        │              │              ↓
        │              │       Sustained Away?
        │              │          ↓         ↓
        │              │         NO         YES
        │              │          ↓          ↓
        │              │       NORMAL   VISUAL + AUDIO
        │              │
        │          Liveness Challenge
        │              ↓
        └────────→ Session Metrics
                       ↓
                 Final Dashboard

Head pose is not simply combined with eye-gaze coordinates to decide attention. Head movement used to satisfy a liveness challenge must not automatically become Gaze: Away.

Likewise, a gaze warning must not automatically start a liveness challenge.

21. Final System Flow

The complete webcam monitoring and evaluation flow is:

                  CANDIDATE WEBCAM
                         ↓
                    VIDEO STREAM
                         ↓
               MEDIAPIPE FACE LANDMARKER
                         ↓
                    478 LANDMARKS
                         ↓
        ┌────────────────┼────────────────┐
        ↓                ↓                ↓
 FACE PRESENCE       HEAD POSE        EYE ATTENTION
        │                │                │
        │                │                ↓
        │                │          ATTENTION STATE
        │                │                ↓
        │                │       Sustained Away?
        │                │          ↙          ↘
        │                │        NO            YES
        │                │        ↓              ↓
        │                │     NORMAL      VISUAL + AUDIO
        │
        │             ACTIVE LIVENESS
        │                ↓
        │        Blink + Head Challenge
        │                ↓
        └────────────→ SESSION METRICS
                         ↓
                  FLASK / SESSION FLOW
                         ↓
                 FINAL EVALUATION
                         ↓
                  ATTENTION DASHBOARD

Engineering constraints

- Reuse the existing webcam stream.
- Reuse the existing MediaPipe Face Landmarker.
- Reuse the existing processFrame/requestAnimationFrame loop.
- Do not create a second webcam stream.
- Do not create a second animation loop.
- Do not create competing attention or liveness state machines.
- Keep eye gaze and head pose logically separate.
- Do not let liveness permanently block webcam processing.
- Do not use lack of movement as proof of spoofing.
- Do not classify a candidate as fake solely because they did not blink.
- Keep liveness occasional and non-annoying.
