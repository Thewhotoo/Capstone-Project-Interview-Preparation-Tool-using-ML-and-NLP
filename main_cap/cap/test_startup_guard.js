// Double-start / orphan-session fix — startDomainDiscussionFromDashboard()
// / rdStartSession() (templates/index.html) must not be re-entrant.
//
// Real-browser forensic finding (same investigation as
// test_typeline_race.js): the "Enter Resume Discussion" button had no
// disable-on-click and no re-entrancy guard, so a fast double click fired
// rdStartSession() twice -- reproduced live as TWO real, separate backend
// conversations (two distinct conversation_ids from two real
// /api/resume-discussion-v2/start calls), one of them silently orphaned
// forever server-side, in addition to the typewriter race this also caused.
// The fix is a tiny frontend guard (`rdSessionStarting`), reset in
// rdStartSession's own `finally` so success, the `data.error` early return,
// and a thrown/rejected fetch all release it -- a failed startup must never
// permanently lock out a legitimate retry.
//
// No test framework/build step exists for this repo's frontend, so this
// extracts the EXACT source of `rdSessionStarting`'s declaration,
// `startDomainDiscussionFromDashboard`, and `rdStartSession` straight out of
// templates/index.html (never a hand-copied duplicate that could drift) and
// evaluates that exact text with Node's built-in `vm` + `assert` modules,
// supplying minimal stand-ins only for the DOM elements / sibling functions
// those two functions call out to (never reimplementing THEIR logic --
// only the two functions actually under test run their real, shipped code).
//
// Run: node test_startup_guard.js

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const HTML_PATH = path.join(__dirname, "templates", "index.html");
const src = fs.readFileSync(HTML_PATH, "utf8");

function extractBlock(source, startMarker) {
    const start = source.indexOf(startMarker);
    if (start === -1) {
        throw new Error(`Could not find marker: ${startMarker}`);
    }
    const braceIdx = source.indexOf("{", start);
    const semiIdx = source.indexOf(";", start);
    if (semiIdx !== -1 && (braceIdx === -1 || semiIdx < braceIdx)) {
        return source.slice(start, semiIdx + 1);
    }
    let depth = 0, i = braceIdx, seenOpen = false;
    for (; i < source.length; i++) {
        const ch = source[i];
        if (ch === "{") { depth++; seenOpen = true; }
        else if (ch === "}") { depth--; if (seenOpen && depth === 0) { i++; break; } }
    }
    return source.slice(start, i);
}

const blocks = [
    // `let` bindings don't become properties of a vm-contextified sandbox
    // object (only `var`/function declarations do) -- swapping to `var`
    // here is a harness-only transformation so the test can read/reset
    // `sandbox.rdSessionStarting` between assertions; it does not change
    // which line of REAL code runs (still the exact extracted declaration,
    // same initial value, same file), and has no effect on the two
    // functions actually under test.
    extractBlock(src, "let rdSessionStarting = false;").replace("let ", "var "),
    extractBlock(src, "function startDomainDiscussionFromDashboard() {"),
    extractBlock(src, "async function rdStartSession() {"),
].join("\n\n");

function fakeEl() {
    return {
        style: {}, innerHTML: "", textContent: "", children: [],
        classList: { add() {}, remove() {}, contains() { return false; }, toggle() {} },
        appendChild() {},
    };
}

// One fresh sandbox per test -- fetch is test-controlled (a deferred
// Promise the test resolves/rejects on its own schedule) so the guard's
// exact timing window (before/after the network call settles) is what's
// under test, not real network/timer behavior. Every OTHER collaborator
// (typeLine, sleep, rdRenderStage, rdDisableInput, ...) is a trivial no-op
// stub -- their own real behavior is exercised by their own dedicated
// tests elsewhere (e.g. test_typeline_race.js), not here.
function makeSandbox({ fetchImpl }) {
    const sandbox = {
        console,
        candidateDashboard: fakeEl(), landingContainer: fakeEl(),
        rdHistoryList: fakeEl(), rdHistoryCount: fakeEl(), rdChapterRail: fakeEl(),
        rdStageWrap: fakeEl(), rdContainer: fakeEl(), rdContextHeading: fakeEl(),
        rdQuestionTextEl: fakeEl(),
        rdSeenCategories: [], rdQuestionNum: 0,
        rdSessionId: null, rdTotalQuestions: 12, rdCurrentCategory: "project_overview",
        rdTurnHistory: [],
        document: {
            body: { classList: { add() {}, remove() {} } },
            getElementById: () => fakeEl(),
        },
        setTimeout: (fn) => fn(), // cosmetic-only in these two functions (opacity fade)
        parsedResumeData: { session_id: "profile_test" },
        fetch: fetchImpl,
        setSystemLog() {}, rdDisableInput() {}, rdEnableInput() {},
        rdUpdatePositionLabel() {}, rdUpdateChapterRail() {},
        rdShowStageError() {},
        typeLine: async () => {}, sleep: async () => {}, rdRenderStage: async () => {},
    };
    vm.createContext(sandbox);
    vm.runInContext(blocks, sandbox);
    return sandbox;
}

function flush(ms = 20) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

const OK_RESPONSE = {
    json: async () => ({
        conversation_id: "conv_test", total_questions: 10,
        question: { turn_number: 1, category: "project_overview", text: "Q", project_reference: null },
    }),
};

let passed = 0;
async function test(name, fn) {
    await fn();
    console.log("ok -", name);
    passed++;
}

(async () => {

await test("a single legitimate call starts exactly one session", async () => {
    let fetchCalls = 0;
    const sandbox = makeSandbox({ fetchImpl: async () => { fetchCalls++; return OK_RESPONSE; } });
    sandbox.startDomainDiscussionFromDashboard();
    await flush();
    assert.strictEqual(fetchCalls, 1);
    assert.strictEqual(sandbox.rdSessionStarting, false, "guard must be released once startup completes");
});

await test("a second rapid call while the first is still in flight issues NO second request", async () => {
    let fetchCalls = 0;
    let resolveFetch;
    const pending = new Promise((resolve) => { resolveFetch = resolve; });
    const sandbox = makeSandbox({ fetchImpl: async () => { fetchCalls++; return pending; } });

    sandbox.startDomainDiscussionFromDashboard(); // real click #1 -- fetch fires
    sandbox.startDomainDiscussionFromDashboard(); // real click #2, still in flight -- must be a no-op
    sandbox.startDomainDiscussionFromDashboard(); // a third, for good measure
    assert.strictEqual(fetchCalls, 1, "only ONE backend conversation may ever be created from a rapid double/triple click");

    resolveFetch(OK_RESPONSE);
    await flush();
    assert.strictEqual(sandbox.rdSessionStarting, false);
});

await test("a failed startup (rejected fetch) still releases the guard -- no permanent lockout", async () => {
    let fetchCalls = 0;
    const sandbox = makeSandbox({
        fetchImpl: async () => { fetchCalls++; throw new Error("network down"); },
    });

    sandbox.startDomainDiscussionFromDashboard();
    await flush();
    assert.strictEqual(fetchCalls, 1);
    assert.strictEqual(sandbox.rdSessionStarting, false, "a thrown/rejected fetch must still reach the finally reset");

    // A legitimate retry after the failure must be allowed through.
    sandbox.fetch = async () => { fetchCalls++; return OK_RESPONSE; };
    sandbox.startDomainDiscussionFromDashboard();
    await flush();
    assert.strictEqual(fetchCalls, 2, "the retry after a failed startup must actually reach the network");
});

await test("a backend {error: ...} response (the early-return path) also releases the guard", async () => {
    let fetchCalls = 0;
    const sandbox = makeSandbox({
        fetchImpl: async () => { fetchCalls++; return { json: async () => ({ error: "Candidate Profile not found." }) }; },
    });

    sandbox.startDomainDiscussionFromDashboard();
    await flush();
    assert.strictEqual(sandbox.rdSessionStarting, false, "the data.error early return must still reach the finally reset");

    sandbox.fetch = async () => { fetchCalls++; return OK_RESPONSE; };
    sandbox.startDomainDiscussionFromDashboard();
    await flush();
    assert.strictEqual(fetchCalls, 2);
});

console.log(`\n${passed} passed`);

})();
