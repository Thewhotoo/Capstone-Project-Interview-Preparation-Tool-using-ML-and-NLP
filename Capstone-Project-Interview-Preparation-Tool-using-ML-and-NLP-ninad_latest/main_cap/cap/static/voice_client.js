/* Voice I/O for the interview UI: spoken questions (TTS), spoken answers (raw 16 kHz PCM -> server Whisper),
   tone + reading analysis shown only in the end-of-interview report. Loaded after the main inline script. */
(() => {
  "use strict";
  const API = "/api/voice";
  const $ = (s) => document.querySelector(s);
  const store = {
    get: (k, d) => { try { const v = localStorage.getItem("voice." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
    set: (k, v) => { try { localStorage.setItem("voice." + k, JSON.stringify(v)); } catch { /* private mode */ } },
  };
  const S = {
    stt: false, tts: false, speakOn: store.get("speak", true), autoListen: store.get("auto", false),
    question: "", questionAt: 0, ttsEndAt: 0, audioEl: null, rec: null, ids: [], busy: false,
  };
  const g = (name) => { try { return (0, eval)(`typeof ${name}!=="undefined"?${name}:undefined`); } catch { return undefined; } };
  const sessionId = () => g("rdSessionId") || g("techSessionId") || null;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  /* ───────── Text-to-speech ───────── */
  function stopSpeaking() {
    if (S.audioEl) { S.audioEl.pause(); S.audioEl = null; }
    try { window.speechSynthesis.cancel(); } catch { /* unsupported */ }
  }

  async function speak(text) {
    if (!S.speakOn || !text) return;
    stopSpeaking();
    const token = (speak.token = (speak.token || 0) + 1);
    let done = false;
    if (S.tts) {
      try {
        const res = await fetch(`${API}/tts`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
        if (res.ok && token === speak.token) {
          const url = URL.createObjectURL(await res.blob());
          const a = (S.audioEl = new Audio(url));
          await new Promise((resolve) => { a.onended = a.onerror = resolve; a.play().catch(resolve); });
          URL.revokeObjectURL(url);
          done = true;
        } else if (res.status === 501) S.tts = false;
      } catch { /* fall through to browser voice */ }
    }
    if (!done && token === speak.token && "speechSynthesis" in window) {
      await new Promise((resolve) => {
        const u = new SpeechSynthesisUtterance(text.replace(/\s+/g, " "));
        u.rate = 1.0; u.onend = u.onerror = resolve;
        window.speechSynthesis.speak(u);
      });
    }
    if (token !== speak.token) return;           // superseded by a newer question or by the mic
    S.ttsEndAt = Date.now();
    if (S.autoListen && !S.rec && !S.busy) { const t = activeTarget(); if (t && !t.input.disabled) toggle(t); }
  }

  /* ───────── Recording (AudioWorklet -> 16 kHz mono PCM WAV) ───────── */
  function wavBlob(chunks, rate) {
    const n = chunks.reduce((a, c) => a + c.length, 0), buf = new ArrayBuffer(44 + n * 2), v = new DataView(buf);
    const w = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
    w(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); w(8, "WAVEfmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
    v.setUint16(22, 1, true); v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true);
    v.setUint16(34, 16, true); w(36, "data"); v.setUint32(40, n * 2, true);
    let o = 44;
    for (const c of chunks) for (let i = 0; i < c.length; i++, o += 2) v.setInt16(o, Math.max(-1, Math.min(1, c[i])) * 32767, true);
    return new Blob([buf], { type: "audio/wav" });
  }

  async function openRecorder(onAutoStop) {
    const suspend = typeof g("proctorSuspendBlur") === "function";      // the mic permission prompt steals focus
    if (suspend) proctorSuspendBlur();                                   // eslint-disable-line no-undef
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: false, autoGainControl: false } });
    } finally {
      if (suspend) setTimeout(() => proctorResumeBlur(), 800);          // eslint-disable-line no-undef
    }
    const ctx = new AudioContext({ sampleRate: 16000 });
    const code = "class R extends AudioWorkletProcessor{process(i){const c=i[0][0];if(c)this.port.postMessage(c.slice(0));return true}}registerProcessor('rec',R)";
    await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([code], { type: "application/javascript" })));
    const src = ctx.createMediaStreamSource(stream), node = new AudioWorkletNode(ctx, "rec"), mute = ctx.createGain();
    mute.gain.value = 0; src.connect(node); node.connect(mute).connect(ctx.destination);

    const r = { chunks: [], gaze: { n: 0, away: 0 }, t0: Date.now(), speech: false, lastLoud: Date.now(), floor: [], level: 0 };
    node.port.onmessage = (e) => {
      const c = e.data; r.chunks.push(c);
      let s = 0; for (let i = 0; i < c.length; i++) s += c[i] * c[i];
      const rms = Math.sqrt(s / c.length); r.level = rms;
      if (r.floor.length < 50) { r.floor.push(rms); return; }             // ~0.4 s of ambient noise
      const thr = 3 * [...r.floor].sort((a, b) => a - b)[25] + 0.008;
      if (rms > thr) { r.speech = true; r.lastLoud = Date.now(); }
      else if (r.speech && Date.now() - r.lastLoud > 2500) onAutoStop();  // 2.5 s of silence after speaking
      if (Date.now() - r.t0 > 180000) onAutoStop();
    };
    r.gazeTimer = setInterval(() => {                                      // camera proctor already flags looking away
      const w = $("#gaze-warning"); r.gaze.n++; if (w && w.classList.contains("visible")) r.gaze.away++;
    }, 200);
    r.close = () => { clearInterval(r.gazeTimer); stream.getTracks().forEach((t) => t.stop()); node.disconnect(); ctx.close(); };
    return r;
  }

  /* ───────── Mic toggle for both interview UIs ───────── */
  const TARGETS = {
    rd: { input: () => $("#rd-user-input"), btn: () => $("#rd-mic-btn"), kind: "resume" },
    tech: { input: () => $("#user-input"), btn: () => $("#mic-btn"), kind: "technical" },
  };
  function activeTarget() {
    const flow = g("interviewFlow"), phase = flow && flow.phase;
    const rd = $("#rd-container"), rdShown = rd && rd.offsetParent !== null;
    const t = TARGETS[phase === "technical" ? "tech" : phase === "resume" || rdShown ? "rd" : "tech"];
    return { kind: t.kind, input: t.input(), btn: t.btn() };
  }

  async function toggle(t) {
    if (S.busy || !t.input || t.input.disabled) return;
    if (S.rec) return finish(t);
    stopSpeaking();
    speak.token = (speak.token || 0) + 1;
    try {
      S.rec = await openRecorder(() => S.rec && finish(t));
    } catch (e) {
      t.input.placeholder = "Microphone unavailable: " + (e.message || e.name);
      return;
    }
    S.rec.latency = S.ttsEndAt ? (Date.now() - S.ttsEndAt) / 1000 : (Date.now() - S.questionAt) / 1000;
    t.btn && t.btn.classList.add("mic-active");
    t.input.dataset.ph = t.input.placeholder;
    t.input.placeholder = "Listening… (click the mic to stop)";
  }

  async function finish(t) {
    const r = S.rec; S.rec = null; S.busy = true;
    r.close(); t.btn && t.btn.classList.remove("mic-active");
    t.input.placeholder = "Transcribing…";
    try {
      const form = new FormData();
      form.append("audio", wavBlob(r.chunks, 16000), "answer.wav");
      form.append("context", JSON.stringify({
        kind: t.kind, question: S.question, session_id: sessionId(),
        response_latency_s: Math.max(0, r.latency), gaze_away_ratio: r.gaze.n ? r.gaze.away / r.gaze.n : null,
      }));
      const res = await fetch(`${API}/transcribe`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);
      if (data.text) {
        t.input.value = (t.input.value ? t.input.value.trim() + " " : "") + data.text;
        t.input.dispatchEvent(new Event("input", { bubbles: true }));
        S.ids.push(data.id);
      }
    } catch (e) {
      t.input.placeholder = "Transcription failed: " + e.message;
      await sleep(2500);
    } finally {
      t.input.placeholder = t.input.dataset.ph || "";
      S.busy = false; t.input.focus();
    }
  }

  /* ───────── End-of-interview report card ───────── */
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const LABEL = { likely_reading: ["Likely reading", "#e5534b"], possible_reading: ["Possible reading", "#d29922"], natural_speech: ["Natural speech", "#3fb950"], insufficient_data: ["Too short to assess", "#8b949e"] };

  async function renderReportCard(host) {
    if (!S.ids.length || host.querySelector(".voice-card")) return;
    const ids = [...S.ids];
    let s; try { s = await (await fetch(`${API}/summary`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) })).json(); } catch { return; }
    if (!s.answers) return;
    const rows = s.per_answer.map((a) => { const [l, c] = LABEL[a.label] || LABEL.insufficient_data;
      return `<tr><td>#${a.n}</td><td style="color:${c}">${l}${a.score != null ? ` (${Math.round(a.score * 100)}%)` : ""}</td><td>${esc(a.reasons.join("; ")) || "—"}</td><td>${esc(a.confidence)}</td></tr>`; }).join("");
    const card = document.createElement("section");
    card.className = "voice-card";
    card.style.cssText = "margin:24px auto;max-width:900px;padding:18px 22px;border:1px solid #30363d;border-radius:10px;font-size:.9rem;color:inherit";
    card.innerHTML = `<h3 style="margin:0 0 8px">Voice delivery</h3>
      <div>Spoken answers: <b>${s.answers}</b> · flagged as reading: <b>${s.flagged}</b> · avg pace <b>${s.mean_wpm ?? "–"} wpm</b> (${s.pace ?? "–"}) · pitch <b>${s.pitch_variation ?? "–"}</b> · delivery confidence <b>${s.mean_confidence != null ? Math.round(s.mean_confidence * 100) + "%" : "–"}</b></div>
      ${s.tips.length ? `<ul style="margin:8px 0 0 18px">${s.tips.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}
      <table style="width:100%;margin-top:12px;border-collapse:collapse"><thead><tr style="text-align:left;opacity:.7"><th>Answer</th><th>Verdict</th><th>Why</th><th>Delivery</th></tr></thead><tbody>${rows}</tbody></table>
      <div style="opacity:.6;margin-top:8px;font-size:.78rem">Indicators only, not proof: rehearsed answers and non-native speech can look like reading.</div>`;
    host.appendChild(card);
  }

  /* ───────── Wiring into the existing UI ───────── */
  function patch(name, wrap) {
    const orig = window[name];
    if (typeof orig === "function") window[name] = function (...a) { const r = orig.apply(this, a); try { wrap(a, r); } catch { /* never break the interview */ } return r; };
  }

  function controls() {
    const box = document.createElement("div");
    box.style.cssText = "position:fixed;left:12px;bottom:12px;z-index:50;display:flex;gap:6px;font:12px Inter,sans-serif";
    const mk = (label, key, prop) => {
      const b = document.createElement("button");
      b.style.cssText = "padding:5px 9px;border-radius:14px;border:1px solid #444;background:#161b22;color:#ddd;cursor:pointer";
      const paint = () => { b.textContent = `${label}: ${S[prop] ? "on" : "off"}`; b.style.borderColor = S[prop] ? "#3fb950" : "#444"; };
      b.onclick = () => { S[prop] = !S[prop]; store.set(key, S[prop]); if (!S[prop] && prop === "speakOn") stopSpeaking(); paint(); };
      paint(); return b;
    };
    box.append(mk("🔊 Read questions", "speak", "speakOn"), mk("🎙 Auto-listen", "auto", "autoListen"));
    document.body.appendChild(box);
  }

  async function init() {
    try { const s = await (await fetch(`${API}/status`)).json(); S.stt = !!s.stt; S.tts = !!s.tts; } catch { return; }
    controls();
    if (S.stt) {
      window.toggleMic = () => toggle({ kind: "technical", input: $("#user-input"), btn: $("#mic-btn") });
      window.rdToggleMic = () => toggle({ kind: "resume", input: $("#rd-user-input"), btn: $("#rd-mic-btn") });
      const rdBtn = $("#rd-mic-btn"); if (rdBtn) rdBtn.style.display = "";   // shown even where browser dictation is missing
    }
    patch("startInterviewMode", () => { S.ids = []; });                          // new interview -> new voice record
    // Round 1: the question is typewritten into #rd-question-text.
    patch("typeLine", ([el, text]) => { if (el && el.id === "rd-question-text") { S.question = text; S.questionAt = Date.now(); S.ttsEndAt = 0; speak(text); } });
    // Technical round: prompts arrive through showTechPrompt({kind, text, number}).
    patch("showTechPrompt", ([p]) => {
      S.question = p.text; S.questionAt = Date.now(); S.ttsEndAt = 0;
      speak(p.kind === "question" ? `Question ${p.number}. ${p.text}` : p.text);
    });
    // Reports: attach the voice card when either report container fills.
    for (const sel of ["#rd-report-container", "#dashboard-container"]) {
      const host = $(sel); if (!host) continue;
      new MutationObserver(() => { if (host.querySelector(":scope > *:not(.voice-card)")) renderReportCard(host); })
        .observe(host, { childList: true });
    }
    window.addEventListener("beforeunload", stopSpeaking);
  }

  window.VoiceIO = { speak, stopSpeaking, state: S };
  init();
})();
