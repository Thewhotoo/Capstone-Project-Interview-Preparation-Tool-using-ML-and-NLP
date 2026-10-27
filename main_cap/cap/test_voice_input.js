// Voice input -- templates/index.html's VOICE INPUT block: one click starts
// recording, the next stops it; the recording is sent to /api/transcribe and
// the text is added to the answer box after anything typed; sending while
// recording finishes the text first; a sent answer drops anything in flight;
// errors are shown.
//
// Same convention as test_session_integrity.js: extracts the EXACT source of
// the block and runs it in Node's `vm` with a fake microphone, MediaRecorder
// and server.
//
// Run: node test_voice_input.js

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const src = fs.readFileSync(path.join(__dirname, "templates", "index.html"), "utf8");
const START = "// ─── VOICE INPUT (speech-to-text)";
const END = "// Round 1 composer.";
const startIdx = src.indexOf(START);
const endIdx = src.indexOf(END, startIdx);
if (startIdx === -1 || endIdx === -1) throw new Error("VOICE INPUT block not found");
const block = src.slice(startIdx, endIdx);

const settle = async () => { for (let i = 0; i < 10; i++) await new Promise((r) => setImmediate(r)); };

function setup({ typed = "", supported = true, micError = null, reply = { ok: true, body: { text: "I used Redis" } } } = {}) {
    const toasts = [], states = [], requests = [];
    let now = 0, interval = null;
    const tracks = [{ stopped: false, stop() { this.stopped = true; } }];
    const button = {
        style: {}, title: "", attrs: {},
        setAttribute(k, v) { this.attrs[k] = v; },
        classList: { _s: new Set(), toggle(c, on) { on ? this._s.add(c) : this._s.delete(c); }, contains(c) { return this._s.has(c); } },
    };
    const input = { value: typed };

    class FakeRecorder {
        static isTypeSupported(t) { return t === "audio/webm;codecs=opus"; }
        constructor(stream, opts) { FakeRecorder.last = this; this.mimeType = opts && opts.mimeType; this.state = "inactive"; }
        start() { this.state = "recording"; }
        stop() { this.state = "inactive"; this.ondataavailable({ data: { size: 1200 } }); this.onstop(); }
    }
    const sandbox = {
        window: supported ? { MediaRecorder: FakeRecorder } : {},
        MediaRecorder: FakeRecorder,
        navigator: {
            mediaDevices: {
                getUserMedia: async () => { if (micError) { const e = new Error(micError); e.name = micError; throw e; } return { getTracks: () => tracks }; },
            },
        },
        Blob: class { constructor(parts, opts) { this.size = parts.reduce((n, p) => n + p.size, 0); this.type = opts.type; } },
        FormData: class { constructor() { this.fields = {}; } append(k, v) { this.fields[k] = v; } },
        fetch: async (url, opts) => {
            requests.push({ url, body: opts.body });
            return { ok: reply.ok, json: async () => reply.body };
        },
        Date: { now: () => now },
        setInterval: (fn) => (interval = fn), clearInterval: () => (interval = null),
        showToast: (m, type) => toasts.push({ m, type }),
        proctorSuspendBlur() { sandbox.suspended++; }, proctorResumeBlur() { sandbox.suspended--; },
        suspended: 0,
        String,
    };
    vm.createContext(sandbox);
    vm.runInContext(block + "\nthis.createVoiceInput = createVoiceInput;", sandbox);
    const voice = sandbox.createVoiceInput({ button, input, onStateChange: (s, sec) => states.push([s, sec]),
                                             onTextChange: () => states.push(["text"]) });
    return {
        voice, button, input, states, toasts, requests, tracks, sandbox,
        recorder: () => FakeRecorder.last,
        tick(ms) { now += ms; if (interval) interval(); },
    };
}

let passed = 0;
async function test(name, fn) { await fn(); passed++; console.log("ok -", name); }

(async () => {
    await test("one click records, the next turns it into text in the box", async () => {
        const t = setup();
        t.voice.toggle();
        await settle();
        assert.strictEqual(t.voice.state(), "recording");
        assert.ok(t.button.classList.contains("mic-active"));
        assert.strictEqual(t.recorder().mimeType, "audio/webm;codecs=opus");
        t.tick(3000);
        assert.deepStrictEqual(t.states.at(-1), ["recording", 3]);
        t.voice.toggle();
        await settle();
        assert.strictEqual(t.requests.length, 1);
        assert.strictEqual(t.requests[0].url, "/api/transcribe");
        assert.strictEqual(t.requests[0].body.fields.audio.size, 1200);
        assert.strictEqual(t.input.value, "I used Redis");
        assert.strictEqual(t.voice.state(), "off");
        assert.ok(t.tracks[0].stopped, "microphone released");
        assert.ok(t.states.some(([s]) => s === "transcribing"));
        assert.strictEqual(t.sandbox.suspended, 0);
    });

    await test("adds to text that was already typed", async () => {
        const t = setup({ typed: "My project" });
        t.voice.toggle(); await settle();
        t.voice.toggle(); await settle();
        assert.strictEqual(t.input.value, "My project I used Redis");
    });

    await test("Send while recording: finishes the text, then sends", async () => {
        const t = setup();
        let sentWith = null;
        t.voice.toggle(); await settle();
        t.voice.whenIdle(() => { sentWith = t.input.value; });
        t.voice.whenIdle(() => { throw new Error("sent twice"); });   // second press while waiting
        await settle();
        assert.strictEqual(sentWith, "I used Redis");
    });

    await test("a discarded recording never reaches the server or the box", async () => {
        const t = setup();
        t.voice.toggle(); await settle();
        t.voice.stop({ discard: true });
        await settle();
        assert.strictEqual(t.requests.length, 0);
        assert.strictEqual(t.input.value, "");
        assert.strictEqual(t.voice.state(), "off");
        assert.ok(t.tracks[0].stopped);
    });

    await test("text arriving after the answer was sent is dropped", async () => {
        const t = setup();
        t.voice.toggle(); await settle();
        t.voice.toggle();                       // stop -> transcription request in flight
        t.voice.stop({ discard: true });        // answer sent meanwhile
        t.input.value = "";
        await settle();
        assert.strictEqual(t.input.value, "");
    });

    await test("a blocked microphone is reported", async () => {
        const t = setup({ micError: "NotAllowedError" });
        t.voice.toggle(); await settle();
        assert.strictEqual(t.voice.state(), "off");
        assert.match(t.toasts[0].m, /Microphone blocked/);
        assert.strictEqual(t.sandbox.suspended, 0);
    });

    await test("no microphone is reported", async () => {
        const t = setup({ micError: "NotFoundError" });
        t.voice.toggle(); await settle();
        assert.match(t.toasts[0].m, /No microphone found/);
    });

    await test("a server error is shown and the box is untouched", async () => {
        const t = setup({ typed: "keep me", reply: { ok: false, body: { error: "The recording couldn't be read." } } });
        t.voice.toggle(); await settle();
        t.voice.toggle(); await settle();
        assert.strictEqual(t.input.value, "keep me");
        assert.match(t.toasts[0].m, /couldn't be read/);
        assert.strictEqual(t.voice.state(), "off");
    });

    await test("silence: a message, no text", async () => {
        const t = setup({ reply: { ok: true, body: { text: "" } } });
        t.voice.toggle(); await settle();
        t.voice.toggle(); await settle();
        assert.strictEqual(t.input.value, "");
        assert.match(t.toasts[0].m, /No speech/);
    });

    await test("stops by itself at 5 minutes and still transcribes", async () => {
        const t = setup();
        t.voice.toggle(); await settle();
        t.tick(300 * 1000);
        await settle();
        assert.match(t.toasts[0].m, /5 minutes/);
        assert.strictEqual(t.input.value, "I used Redis");
    });

    await test("clicks while transcribing are ignored", async () => {
        const t = setup();
        t.voice.toggle(); await settle();
        t.voice.toggle();                       // now transcribing
        t.voice.toggle();
        await settle();
        assert.strictEqual(t.requests.length, 1);
        assert.strictEqual(t.voice.state(), "off");
    });

    await test("browsers that can't record hide the mic button", async () => {
        const t = setup({ supported: false });
        assert.strictEqual(t.voice, null);
        assert.strictEqual(t.button.style.display, "none");
    });

    console.log(`\n${passed} passed`);
})().catch((e) => { console.error(e); process.exit(1); });
