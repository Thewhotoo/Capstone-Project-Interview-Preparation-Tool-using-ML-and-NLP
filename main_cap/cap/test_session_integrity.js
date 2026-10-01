// Session integrity (full screen, no tab/window switch, no copy/cut/paste)
// for the Resume Discussion -- templates/index.html's SESSION INTEGRITY
// block. Zero-tolerance policy: once armed, the FIRST violation terminates
// the session exactly once; nothing counts before arming or after a
// normal disarm; a short window blur within the grace period is forgiven.
//
// Same convention as test_startup_guard.js: no test framework/build step
// exists for this repo's frontend, so this extracts the EXACT source of the
// whole SESSION INTEGRITY block out of templates/index.html and evaluates it
// with Node's built-in `vm` + `assert` modules, stubbing only the DOM and
// the sibling functions it calls out to.
//
// Run: node test_session_integrity.js

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const HTML_PATH = path.join(__dirname, "templates", "index.html");
const src = fs.readFileSync(HTML_PATH, "utf8");

const START = "// ─── SESSION INTEGRITY";
const END = "// ─── RESUME DISCUSSION — workspace helpers";
const startIdx = src.indexOf(START);
const endIdx = src.indexOf(END, startIdx);
if (startIdx === -1 || endIdx === -1) throw new Error("SESSION INTEGRITY block not found");
// `let`/`const` bindings aren't visible as sandbox properties -- swap to
// `var` (harness-only) so tests can read proctorState / rdEnding.
const block = src.slice(startIdx, endIdx).replace(/^(\s*)(let|const) /gm, "$1var ");

function fakeEl() {
    return {
        style: {}, innerHTML: "", textContent: "", disabled: false, onclick: null,
        classList: {
            _set: new Set(),
            add(c) { this._set.add(c); }, remove(c) { this._set.delete(c); },
            contains(c) { return this._set.has(c); },
            toggle(c, on) { (on === undefined ? !this._set.has(c) : on) ? this._set.add(c) : this._set.delete(c); },
        },
    };
}

function makeSandbox() {
    const docListeners = {};
    const winListeners = {};
    const timers = [];
    const elements = {};
    const calls = { triggerReport: 0, disableInput: 0, exitFullscreen: 0 };

    const document = {
        hidden: false,
        fullscreenElement: {},          // start already in full screen
        _focused: true,
        hasFocus() { return this._focused; },
        documentElement: { requestFullscreen: async () => {} },
        exitFullscreen() { calls.exitFullscreen++; document.fullscreenElement = null; return Promise.resolve(); },
        getElementById(id) { return (elements[id] = elements[id] || fakeEl()); },
        addEventListener(t, fn) { (docListeners[t] = docListeners[t] || new Set()).add(fn); },
        removeEventListener(t, fn) { docListeners[t] && docListeners[t].delete(fn); },
    };
    const window = {
        addEventListener(t, fn) { (winListeners[t] = winListeners[t] || new Set()).add(fn); },
        removeEventListener(t, fn) { winListeners[t] && winListeners[t].delete(fn); },
    };

    const sandbox = {
        console, document, window, navigator: {}, Object, Math, Date,
        setTimeout(fn, ms) { const t = { fn, ms, cleared: false }; timers.push(t); return t; },
        clearTimeout(t) { if (t) t.cleared = true; },
        sleep: async () => {},
        esc: (s) => String(s),
        _cameraInitializing: false,
        rdSessionStarting: false, rdMicSuspending: false,
        // INTERVIEW FLOW hooks the block calls (their real, round-specific
        // versions live outside this block) -- stand-ins for an interview in
        // progress at question 3.
        interviewSessionActive: () => true,
        interviewCurrentTurn: () => 3,
        interviewRoundLabel: () => "Round 1 (Resume Discussion)",
        interviewDisableInput() { calls.disableInput++; },
        interviewResumeInput() {},
        interviewStopMic() {},
        interviewTerminate() { calls.triggerReport++; },
        startInterviewMode() {},
    };
    vm.createContext(sandbox);
    vm.runInContext(block, sandbox);

    const fire = (target, type, event = {}) => {
        const set = (target === "window" ? winListeners : docListeners)[type];
        const e = Object.assign({ type, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } }, event);
        if (set) [...set].forEach(fn => fn(e));
        return e;
    };
    const runTimers = () => timers.splice(0).forEach(t => { if (!t.cleared) t.fn(); });
    return { sandbox, document, fire, runTimers, calls, docListeners, winListeners };
}

let passed = 0;
async function test(name, fn) {
    await fn();
    console.log("ok -", name);
    passed++;
}

(async () => {

await test("nothing is enforced before the session is armed", async () => {
    const { fire, calls, sandbox } = makeSandbox();
    const e = fire("document", "paste");
    assert.strictEqual(e.defaultPrevented, false);
    assert.strictEqual(calls.triggerReport, 0);
    assert.strictEqual(sandbox.proctorState.terminated, false);
});

await test("a tab switch terminates the session exactly once", async () => {
    const { sandbox, document, fire, calls } = makeSandbox();
    await sandbox.proctorArm();
    assert.strictEqual(sandbox.proctorState.armed, true);

    document.hidden = true;
    fire("document", "visibilitychange");
    fire("document", "visibilitychange");   // duplicate event must not double-count
    assert.strictEqual(calls.triggerReport, 1);
    assert.strictEqual(sandbox.proctorState.terminated, true);
    assert.strictEqual(sandbox.proctorState.armed, false, "listeners must be removed on termination");

    const payload = sandbox.proctorIntegrityPayload();
    assert.strictEqual(payload.terminated, true);
    assert.strictEqual(payload.type, "tab_switch");
    assert.strictEqual(payload.at_turn, 3);
});

await test("copy, cut and paste are blocked and terminate the session", async () => {
    for (const type of ["copy", "cut", "paste"]) {
        const { sandbox, fire, calls } = makeSandbox();
        await sandbox.proctorArm();
        const e = fire("document", type);
        assert.strictEqual(e.defaultPrevented, true, `${type} must be blocked`);
        assert.strictEqual(calls.triggerReport, 1);
        assert.strictEqual(sandbox.proctorIntegrityPayload().type, type);
    }
});

await test("Ctrl+V / Cmd+C shortcuts are blocked up front", async () => {
    const { sandbox, fire } = makeSandbox();
    await sandbox.proctorArm();
    const e = fire("document", "keydown", { key: "v", ctrlKey: true });
    assert.strictEqual(e.defaultPrevented, true);
    assert.strictEqual(sandbox.proctorIntegrityPayload().type, "paste");

    const mac = makeSandbox();
    await mac.sandbox.proctorArm();
    mac.fire("document", "keydown", { key: "C", metaKey: true });
    assert.strictEqual(mac.sandbox.proctorIntegrityPayload().type, "copy");
});

await test("ordinary typing is not a violation", async () => {
    const { sandbox, fire, calls } = makeSandbox();
    await sandbox.proctorArm();
    const e = fire("document", "keydown", { key: "v" });
    assert.strictEqual(e.defaultPrevented, false);
    assert.strictEqual(calls.triggerReport, 0);
});

await test("leaving full screen terminates the session", async () => {
    const { sandbox, document, fire, calls } = makeSandbox();
    await sandbox.proctorArm();
    document.fullscreenElement = null;
    fire("document", "fullscreenchange");
    assert.strictEqual(calls.triggerReport, 1);
    assert.strictEqual(sandbox.proctorIntegrityPayload().type, "fullscreen_exit");
});

await test("a brief window blur within the grace period is forgiven", async () => {
    const { sandbox, document, fire, runTimers, calls } = makeSandbox();
    await sandbox.proctorArm();
    document._focused = false;
    fire("window", "blur");
    document._focused = true;
    fire("window", "focus");
    runTimers();
    assert.strictEqual(calls.triggerReport, 0);
});

await test("a sustained window blur (Alt+Tab) terminates after the grace period", async () => {
    const { sandbox, document, fire, runTimers, calls } = makeSandbox();
    await sandbox.proctorArm();
    document._focused = false;
    fire("window", "blur");
    assert.strictEqual(calls.triggerReport, 0, "must not fire before the grace period elapses");
    runTimers();
    assert.strictEqual(calls.triggerReport, 1);
    assert.strictEqual(sandbox.proctorIntegrityPayload().type, "window_switch");
});

await test("a blur while a permission prompt is pending is not a violation", async () => {
    const { sandbox, document, fire, runTimers, calls } = makeSandbox();
    await sandbox.proctorArm();
    sandbox.proctorSuspendBlur();
    document._focused = false;
    fire("window", "blur");
    runTimers();
    assert.strictEqual(calls.triggerReport, 0);
    sandbox.proctorResumeBlur();
    assert.strictEqual(sandbox.proctorState.blurSuspended, 0);
});

await test("losing full screen during a permission prompt asks to re-enter instead of terminating", async () => {
    const { sandbox, document, fire, calls } = makeSandbox();
    await sandbox.proctorArm();
    sandbox.proctorSuspendBlur();
    document.fullscreenElement = null;
    fire("document", "fullscreenchange");
    assert.strictEqual(calls.triggerReport, 0);
    assert.strictEqual(sandbox.proctorState.terminated, false);
    assert.strictEqual(sandbox.proctorState.armed, false);
    assert.ok(document.getElementById("proctor-overlay").classList.contains("show"));
});

await test("arming while not in full screen asks to re-enter instead of arming", async () => {
    const { sandbox, document } = makeSandbox();
    document.fullscreenElement = null;
    await sandbox.proctorArm();
    assert.strictEqual(sandbox.proctorState.armed, false);
    assert.ok(document.getElementById("proctor-overlay").classList.contains("show"));
});

await test("after a normal disarm (session completed), nothing counts", async () => {
    const { sandbox, document, fire, calls, docListeners, winListeners } = makeSandbox();
    await sandbox.proctorArm();
    sandbox.proctorDisarm({ exitFullscreen: true });
    assert.strictEqual(calls.exitFullscreen, 1);
    fire("document", "fullscreenchange");
    document.hidden = true;
    fire("document", "visibilitychange");
    fire("document", "paste");
    assert.strictEqual(calls.triggerReport, 0);
    assert.strictEqual(sandbox.proctorIntegrityPayload().terminated, false);
    const remaining = [...Object.values(docListeners), ...Object.values(winListeners)].reduce((n, s) => n + s.size, 0);
    assert.strictEqual(remaining, 0, "every listener must be removed on disarm");
});

await test("proctorReset clears a terminated state for a fresh session", async () => {
    const { sandbox, fire } = makeSandbox();
    await sandbox.proctorArm();
    fire("document", "paste");
    assert.strictEqual(sandbox.proctorState.terminated, true);
    sandbox.proctorReset();
    assert.strictEqual(sandbox.proctorState.terminated, false);
    assert.strictEqual(sandbox.rdEnding, false);
    // JSON round-trip: the payload is built inside the vm sandbox, and its
    // Object prototype differs from this realm's, which deepStrictEqual rejects.
    assert.deepStrictEqual(JSON.parse(JSON.stringify(sandbox.proctorIntegrityPayload())), { terminated: false });
});

console.log(`\n${passed} passed`);

})().catch((err) => {
    console.error(err);
    process.exit(1);
});
