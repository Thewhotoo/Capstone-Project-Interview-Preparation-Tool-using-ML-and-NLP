# 07 — Frontend (`main_cap/cap/templates/index.html`, ~9.5k lines)

One file: inline CSS (lines 11–2558) → markup (2558–3381) → one inline `<script>` (3381–9460) → camera-setup overlay markup (9461+).
Vanilla JS, no framework/build. External: Google Fonts (Inter, Roboto Mono), MediaPipe `@mediapipe/tasks-vision` from jsDelivr (line ~6109), model `static/models/face_landmarker.task`.
Owners: proctoring/webcam = Surya; everything else = Nandu; Round 1 UI touched by Mayuran, tech UI by Ninad.
Line numbers below are approximate (verified at 99bdba9) — grep the function name.

## Top-level containers (markup)
`#auth-container` (2575) · app shell with nav (Home / Sessions / Profile; `#sessions-list-view`, `#session-detail-view`) · `#landing-container` (3125, resume start "vessel" screen) · `#interview-monitor-panel` (3255, camera/attention status) · `#chat-container` (3277, technical round chat) · `#dashboard-container` (3288, candidate briefing) · `#rd-container` (3293, Round 1 workspace) · `#rd-report-container` (3320) · `#round-transition` (between rounds) · `#proctor-overlay` (3361) · `#toast-container` · `#camera-setup-overlay` (9462).

## Script sections (function → purpose)
| ~Line | Area | Key functions |
|---|---|---|
| 3400 | Attention metrics | `createAttentionMetrics`, `computeAttentionScore` (100 −4/warning −6/face-absent −5/liveness fail −min(20, 0.25/s away)), `attentionSnapshot` (sent on /end) |
| 3454 | Round 1 state vars | `rdSessionId`, `rdQuestionNum`, `rdTurnHistory`, … |
| 3600 | Status UI | `setFaceStatus`, `setHeadStatus`, `updateGazeIndicator`, camera quality (`camFaceSharpness`, `camImagePoor`) |
| 3688–3800 | Helpers | `showToast`, `esc` (XSS escape — use it for any server text in innerHTML), `nonEmptyStrings`, `categorizeSkills` |
| 3797 | Candidate briefing | `showCandidateDashboard`, `render*Card`, `runBriefingSequence`, `startDomainDiscussionFromDashboard` |
| 4163 | **Session integrity** | `showInterviewRules`, `acceptInterviewRules`, `proctorArm` (waits for camera permission), `proctorOn{VisibilityChange,Blur,Focus,FullscreenChange,Clipboard,Keydown}`, `proctorViolation(type)` (first violation ⇒ terminate), `proctorIntegrityPayload`, `proctorSuspendBlur` (mic prompt), `PROCTOR_BLUR_GRACE_MS = 1500` |
| 4504 | Round 1 workspace | `rdUpdateChapterRail`, `rdArchiveTurn`, `rdToggleHistory` |
| 4581 | Voice input | `createVoiceInput` (MediaRecorder → POST `/api/transcribe`; 5-min cap), `rdToggleMic`, `toggleMic` |
| 4778–5050 | Round 1 I/O | `rdHandleSubmission`, `rdStartSession` (POST start), `rdHandleReply` (POST reply; network error keeps answer for resend), `rdTriggerReport` (POST end; `rdEnding` guard) |
| 5056 | **Interview flow** | `interviewFlow {mode full|technical, phase resume|between|technical|ended}`, `startInterviewMode`, `interview*` hooks used by proctoring, `showRoundTransition`, `beginRound2`, `terminateBetweenRounds`, `startTechnicalRound`, `finishTechnicalRound`, `combineAttention`, `showFinalResults` |
| 5246 | Round 1 report | `rdBuildReportFromV2` (v2 payload → report), `rdOverallGrade` (.80/.60/.40/.25), `rdBuildDebrief`, `rdBuildNextSteps`, `rdBuildTopics`, `rdBuildSnapshot`, `rdMergeRegrades` (end-of-session LLM re-grades over live scores; count mismatch keeps live), `rdRound2Html`, `rdAttentionHtml`, `rdRenderReport` (also combined mode), `rdCombinedVerdict`. Phrase banks at ~5308 |
| 6105 | MediaPipe | `ensureGazeLandmarkerReady`, `initializeGazeMonitoring` (getUserMedia first, then model), `stopGazeMonitoring` |
| 6305 | Gaze geometry | `computeSingleEyeGaze`, `combineEyeGaze` |
| 6387–6440 | Constants | head yaw/pitch ±26°, `HEAD_PITCH_SIGN = -1`; gaze X .44 / Y .60, hysteresis .10, 5 confirm frames, min conf .35; fusion head .35 / gaze .55 / agree bonus .10, away > .50, ok < .34; calibration 15 samples/2–5 s; caution 3.5 s, warning 8.5 s, face-absent 7.5 s, cooldown 45 s |
| 6447 | Audio warning | `speakAttentionWarning` (muted while either mic records) |
| 6509 | State machine | `setAttentionState` (single cooldown gate) |
| 6575–7350 | Detection loop | `startGazeDetectionLoop`: second-face detection, liveness (head-turn left/right only; blink code kept but disabled; 12 s timeout, ≥13° yaw × 5 frames), passive static-face watchdog, no-face handling |
| 7361–7700 | Resume start screen | `setSystemLog`, `typeLine` (rAF typewriter), `useSavedResume`, `uploadResume`, `buildCandidateProfile` |
| 7700 | **Auth** | `authBootstrap` (GET /api/auth/me), `requestMediaPermissions`, `enterApp`, login, 3-step signup (`validateSignupStep`, `setSignupResumeFile`), photo, profile menu, `logout` |
| 8214 | **App shell** | `showAppScreen`, `setActiveNavTab`, `fetchJson`, `loadHome` (+ `renderHomeStats`, `renderTrend`, `renderFocus`), `loadSessions`, `openSession`, `openHistoricalReport`, `showTechnicalDetail`, `loadProfile`, resume list/make-current/delete, `confirmDeleteAccount` |
| 8821 | Chat helpers | `resetInterview`, `addMessage`, `showTyping` |
| 8919 | Technical round | `techQuestionCardHtml`, `showTechPrompt`, `beginTechInterview` (POST start), `handleSubmission` (POST answer), `endTechInterview` (POST end) |
| 9204–9460 | Camera setup check | `_cs*` helpers, `showCameraSetup` — blocks only on no camera / no face / >1 face; lighting/blur warn only |

## Flow (Full Interview)
Home → resume screen (saved resume or upload) → briefing → camera setup → rules (full screen requested on click) → Round 1 (10 q) → `/end` → round transition (still full screen, still armed) → Round 2 (8 q) → `/end` → combined results (releases full screen). A violation anywhere ⇒ terminate whole interview; partial results still shown.

## Frontend tests (`main_cap/cap/test_*.js`, run `node file`)
Each test reads index.html, brace-matches a named `function X(` and runs it in `vm`. So **renaming/changing signatures of these breaks tests**: `rdMergeRegrades`, report confidence/coaching/snapshot/debrief/answer-honesty helpers, session integrity, startup guard, typeline race, tech interview UI, voice input.
Files: test_report_{answer_honesty,coaching,confidence,debrief_heading,regrade_merge,snapshot}.js, test_session_integrity.js, test_startup_guard.js, test_tech_interview_ui.js, test_typeline_race.js, test_voice_input.js.

## Gotchas
- Proctoring is client-side only; backend trusts the sanitised integrity record.
- Webcam needs HTTPS or localhost.
- Spoken warnings are disabled during dictation so the mic doesn't transcribe them.
- `TEMPLATES_AUTO_RELOAD` is on, so an edit shows on the next page load.
