// Voice input (speech-to-text) -- templates/index.html's VOICE INPUT block:
// one click on, one click off, everything said in between written into the
// answer box after any typed text; restarted when the browser ends a session
// by itself; errors shown; words still arriving after the answer was sent
// are dropped.
//
// Same convention as test_session_integrity.js: extracts the EXACT source of
// the block and runs it in Node's `vm` with a fake SpeechRecognition.
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

class FakeRecognition {
    constructor() { FakeRecognition.last = this; this.starts = 0; this.stops = 0; this.aborts = 0; }
    start() { this.starts++; this.onstart && this.onstart(); }
    stop() { this.stops++; }
    abort() { this.aborts++; }
    // test helpers
    say(parts, resultIndex = 0) {   // parts: [[text, isFinal], ...] = the whole session's results so far
        const results = parts.map(([t, f]) => Object.assign([{ transcript: t }], { isFinal: f }));
        this.onresult({ resultIndex, results });
    }
    end() { this.onend(); }
    fail(error) { this.onerror({ error }); }
}

function setup({ supported = true, typed = "" } = {}) {
    const toasts = [];
    let now = 0;
    const button = {
        style: {}, title: "", attrs: {},
        setAttribute(k, v) { this.attrs[k] = v; },
        classList: { _s: new Set(), toggle(c, on) { on ? this._s.add(c) : this._s.delete(c); }, contains(c) { return this._s.has(c); } },
    };
    const input = { value: typed };
    const states = [];
    const window = supported ? { webkitSpeechRecognition: FakeRecognition } : {};
    const sandbox = {
        window, navigator: { language: "en-IN" }, Date: { now: () => now },
        showToast: (m, type) => toasts.push({ m, type }),
        proctorSuspendBlur() { sandbox.suspended++; }, proctorResumeBlur() { sandbox.suspended--; },
        suspended: 0,
    };
    vm.createContext(sandbox);
    vm.runInContext(block + "\nthis.createVoiceInput = createVoiceInput;", sandbox);
    const voice = sandbox.createVoiceInput({ button, input, onStateChange: (on) => states.push(on) });
    return { voice, rec: FakeRecognition.last, button, input, states, toasts, sandbox,
             advance(ms) { now += ms; } };
}

let passed = 0;
function test(name, fn) { fn(); passed++; console.log("ok -", name); }

test("one click on, one click off; what was said is in the box", () => {
    const t = setup();
    t.voice.toggle();
    assert.strictEqual(t.rec.starts, 1);
    assert.ok(t.button.classList.contains("mic-active"));
    assert.strictEqual(t.rec.continuous, true);
    t.rec.say([["I used", false]]);
    assert.strictEqual(t.input.value, "I used");
    t.rec.say([["I used Redis", true]]);
    t.advance(5000);
    t.voice.toggle();
    assert.strictEqual(t.rec.stops, 1);
    assert.ok(!t.button.classList.contains("mic-active"));
    t.rec.say([["I used Redis", true], ["for caching", true]], 1);   // last words arrive after the click
    t.rec.end();
    assert.strictEqual(t.input.value, "I used Redis for caching");
    assert.strictEqual(t.rec.starts, 1, "not restarted after the user turned it off");
    assert.deepStrictEqual(t.states, [true, false]);
    assert.strictEqual(t.sandbox.suspended, 0);
});

test("keeps text that was already typed", () => {
    const t = setup({ typed: "My project" });
    t.voice.toggle();
    t.rec.say([["used Docker", true]]);
    assert.strictEqual(t.input.value, "My project used Docker");
});

test("restarted when the browser ends the session by itself, text kept", () => {
    const t = setup();
    t.voice.toggle();
    t.rec.say([["first part", true]]);
    t.advance(8000);
    t.rec.end();                       // pause / time limit
    assert.strictEqual(t.rec.starts, 2);
    assert.ok(t.button.classList.contains("mic-active"));
    t.rec.say([["second part", true]]);   // a new session's results start again at 0
    assert.strictEqual(t.input.value, "first part second part");
});

test("no-speech is not an error: it keeps listening", () => {
    const t = setup();
    t.voice.toggle();
    t.advance(8000);
    t.rec.fail("no-speech");
    t.rec.end();
    assert.strictEqual(t.rec.starts, 2);
    assert.strictEqual(t.toasts.length, 0);
});

test("a blocked microphone is reported and turns it off", () => {
    const t = setup();
    t.voice.toggle();
    t.rec.fail("not-allowed");
    t.rec.end();
    assert.strictEqual(t.rec.starts, 1);
    assert.ok(!t.button.classList.contains("mic-active"));
    assert.strictEqual(t.toasts.length, 1);
    assert.match(t.toasts[0].m, /Microphone blocked/);
});

test("ending straight after starting three times stops it with a message", () => {
    const t = setup();
    t.voice.toggle();
    for (let i = 0; i < 3; i++) { t.advance(100); t.rec.end(); }
    assert.strictEqual(t.rec.starts, 3);
    assert.ok(!t.voice.isOn());
    assert.match(t.toasts[0].m, /keeps stopping/);
});

test("after the answer is sent, late words don't land in the empty box", () => {
    const t = setup();
    t.voice.toggle();
    t.rec.say([["my answer", false]]);
    t.voice.stop({ discard: true });
    t.input.value = "";                // the box is cleared when the answer is sent
    t.rec.say([["my answer", true]]);
    t.rec.end();
    assert.strictEqual(t.rec.aborts, 1);
    assert.strictEqual(t.input.value, "");
});

test("a second click while the last stop is finishing doesn't double up", () => {
    const t = setup();
    t.voice.toggle();
    t.voice.toggle();                  // stop requested, browser not ended yet
    t.voice.toggle();
    assert.strictEqual(t.rec.starts, 1);
    assert.ok(!t.voice.isOn());
});

test("browsers without speech recognition hide the mic button", () => {
    const t = setup({ supported: false });
    assert.strictEqual(t.voice, null);
    assert.strictEqual(t.button.style.display, "none");
});

console.log(`\n${passed} passed`);
