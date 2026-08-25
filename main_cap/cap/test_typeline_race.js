// Typewriter race fix — typeLine() (templates/index.html) must be
// self-cancelling per DOM element.
//
// Real-browser forensic finding (Coaching Note / UI-spacing investigation,
// item 2): typeLine() had no cancellation mechanism, so a second call on the
// SAME element before a prior call finished raced two independent tick
// chains onto the same el.textContent, producing permanently garbled,
// interleaved question text -- reproduced live by double-clicking "Enter
// Resume Discussion" (two rdStartSession() calls, both typing onto the same
// #rd-question-text element). Confirmed: the corruption never self-corrects
// once triggered (the settled DOM text stays wrong forever), and the
// backend's own response text was always correct -- this is purely a
// frontend rendering race, not a question-generation bug.
//
// No test framework/build step exists for this repo's frontend, so this
// extracts typeLine()'s EXACT source text out of templates/index.html
// (never a hand-copied duplicate that could drift) and evaluates it with
// Node's built-in `vm` + `assert` modules, driving its `setTimeout` calls
// through a controlled fake queue -- real per-character timer delays would
// make the async race untestable/flaky; draining a queue in an explicitly
// chosen order is what lets this deterministically reproduce "a second
// invocation starts while the first is mid-animation."
//
// Run: node test_typeline_race.js

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
    let depth = 0, i = start, seenOpen = false;
    for (; i < source.length; i++) {
        const ch = source[i];
        if (ch === "{") { depth++; seenOpen = true; }
        else if (ch === "}") { depth--; if (seenOpen && depth === 0) { i++; break; } }
    }
    return source.slice(start, i);
}

const typeLineSrc = extractBlock(src, "function typeLine(el, text) {");

// A fresh sandbox + fake element per test: `setTimeout` pushes onto `queue`
// instead of actually waiting, so the test drives the exact interleaving.
function makeSandbox() {
    const queue = [];
    const sandbox = {
        setTimeout: (cb) => { queue.push(cb); return queue.length; },
        Math, Promise, console,
    };
    vm.createContext(sandbox);
    vm.runInContext(typeLineSrc, sandbox);
    return { typeLine: sandbox.typeLine, queue };
}

function makeEl() {
    return { textContent: "", classList: { add() {}, remove() {} } };
}

function drainAll(queue, maxSteps = 100000) {
    let steps = 0;
    while (queue.length && steps++ < maxSteps) {
        const cb = queue.shift();
        cb();
    }
    if (steps >= maxSteps) throw new Error("drainAll exceeded maxSteps -- possible infinite loop");
}

let passed = 0;
async function test(name, fn) {
    await fn();
    console.log("ok -", name);
    passed++;
}

(async () => {

await test("single invocation types the full text, in order, and resolves", async () => {
    const { typeLine, queue } = makeSandbox();
    const el = makeEl();
    const p = typeLine(el, "Hello there");
    drainAll(queue);
    await p; // must resolve -- an uninterrupted single call always completes
    assert.strictEqual(el.textContent, "Hello there");
});

await test("a second invocation on the same element supersedes the first mid-animation", async () => {
    const { typeLine, queue } = makeSandbox();
    const el = makeEl();

    const p1 = typeLine(el, "First question that is fairly long");
    // Let the first call tick a few more characters -- simulates the real
    // race: the second call starts while the first is genuinely mid-type.
    for (let k = 0; k < 4 && queue.length; k++) queue.shift()();
    assert.ok(el.textContent.length > 0 && "First question that is fairly long".startsWith(el.textContent),
        "sanity check: first call really is mid-animation, textContent is a clean prefix so far");

    const p2 = typeLine(el, "Second question, totally different text");
    drainAll(queue);
    await p2; // the superseded call's promise must NOT be awaited -- it never resolves, by design

    assert.strictEqual(el.textContent, "Second question, totally different text",
        "final text must be exactly the newest (second) invocation's text");
    assert.ok(!el.textContent.includes("First"),
        "no fragment of the first (superseded) text may remain");
});

await test("the superseded call's own promise never resolves (halts its whole calling chain)", async () => {
    const { typeLine, queue } = makeSandbox();
    const el = makeEl();

    const p1 = typeLine(el, "Superseded");
    queue.shift()(); // one tick in
    typeLine(el, "Winner"); // supersedes p1
    drainAll(queue);

    let p1Settled = false;
    p1.then(() => { p1Settled = true; });
    await new Promise((resolve) => setTimeout(resolve, 0)); // real macrotask flush
    assert.strictEqual(p1Settled, false,
        "a superseded typeLine() call must never resolve -- that's what stops its caller from proceeding to the next await");
});

await test("three rapid invocations on the same element: only the last one's text survives", async () => {
    const { typeLine, queue } = makeSandbox();
    const el = makeEl();

    typeLine(el, "Alpha alpha alpha");
    queue.shift()();
    typeLine(el, "Beta beta beta");
    queue.shift()();
    const p3 = typeLine(el, "Gamma gamma gamma");
    drainAll(queue);
    await p3;

    assert.strictEqual(el.textContent, "Gamma gamma gamma");
    assert.ok(!el.textContent.includes("Alpha") && !el.textContent.includes("Beta"));
});

await test("two DIFFERENT elements each get their own independent, uninterrupted animation", async () => {
    const { typeLine, queue } = makeSandbox();
    const elA = makeEl();
    const elB = makeEl();

    const pA = typeLine(elA, "Question about project A");
    const pB = typeLine(elB, "Question about project B");
    drainAll(queue);
    await Promise.all([pA, pB]);

    assert.strictEqual(elA.textContent, "Question about project A");
    assert.strictEqual(elB.textContent, "Question about project B");
});

console.log(`\n${passed} passed`);

})();
