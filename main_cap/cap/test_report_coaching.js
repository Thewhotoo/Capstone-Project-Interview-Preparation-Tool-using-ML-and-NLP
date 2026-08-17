// Phase 9 regression test — coaching presentation (`rdBuildNextSteps` /
// `rdBuildDebrief` in templates/index.html).
//
// No test framework/build step exists for this repo's frontend (plain
// Flask-served <script> block, no package.json/jest). Per the approved
// Phase 9 plan, this adds the smallest deterministic test around the real
// helper logic rather than introducing a new framework: it extracts the
// EXACT function/constant source text for RD_DIM_STRONG, RD_DIM_WEAK_SENTENCE,
// RD_GAP_CLAUSE, RD_ADVICE_BY_GAP, rdBuildNextSteps and rdBuildDebrief
// straight out of templates/index.html (never a hand-copied duplicate that
// could drift from the shipped code) and evaluates that exact text with
// Node's built-in `vm` + `assert` modules only.
//
// Run: node test_report_coaching.js

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const HTML_PATH = path.join(__dirname, "templates", "index.html");
const src = fs.readFileSync(HTML_PATH, "utf8");

// Extract the source text of a `const NAME = { ... };` or
// `function name(...) { ... }` declaration by brace-counting from its
// start marker to the matching closing brace -- exact source, not a
// reimplementation.
function extractBlock(source, startMarker) {
    const start = source.indexOf(startMarker);
    if (start === -1) {
        throw new Error(`Could not find marker: ${startMarker}`);
    }
    let depth = 0;
    let i = start;
    let seenOpen = false;
    for (; i < source.length; i++) {
        const ch = source[i];
        if (ch === "{") { depth++; seenOpen = true; }
        else if (ch === "}") {
            depth--;
            if (seenOpen && depth === 0) { i++; break; }
        }
    }
    return source.slice(start, i);
}

const blocks = [
    extractBlock(src, "const RD_DIM_STRONG = {"),
    extractBlock(src, "const RD_DIM_WEAK_SENTENCE = {"),
    extractBlock(src, "const RD_GAP_CLAUSE = {"),
    extractBlock(src, "const RD_ADVICE_BY_GAP = {"),
    extractBlock(src, "function rdBuildNextSteps("),
    extractBlock(src, "function rdBuildDebrief("),
].join("\n\n");

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(blocks, sandbox);
const { rdBuildNextSteps, rdBuildDebrief } = sandbox;

assert.strictEqual(typeof rdBuildNextSteps, "function", "rdBuildNextSteps not extracted");
assert.strictEqual(typeof rdBuildDebrief, "function", "rdBuildDebrief not extracted");

// ── fixtures ─────────────────────────────────────────────────────────────

const REGISTRY_CONCEPTS = ["ASGI", "async request handling", "dependency injection"];
const NO_GAPS = [];
const EXAMPLE_GAP = [{ category: "example", explanation: "x", severity: 0.5 }];
const TRADEOFF_GAP = [{ category: "tradeoff", explanation: "x", severity: 0.7 }];

let passed = 0;
function test(name, fn) {
    fn();
    passed++;
    console.log(`ok - ${name}`);
}

// ── rdBuildNextSteps ─────────────────────────────────────────────────────

test("rdBuildNextSteps: no signature param accepts registry concepts anymore (4-arg signature)", () => {
    assert.strictEqual(rdBuildNextSteps.length, 4);
});

test("rdBuildNextSteps: reasoning-gap advice still fires (example)", () => {
    const steps = rdBuildNextSteps([], EXAMPLE_GAP, null, null);
    assert.ok(steps.some(s => s.includes("concrete example")), "expected example coaching line");
});

test("rdBuildNextSteps: tradeoff project-specific line still fires", () => {
    const steps = rdBuildNextSteps([], TRADEOFF_GAP, "Weak Project", "Strong Project");
    assert.ok(steps.some(s => s.includes("Weak Project") && s.includes("alternatives")));
});

test("rdBuildNextSteps: never mentions registry-only concepts (ASGI/DI/routing) regardless of gaps", () => {
    const steps = rdBuildNextSteps(["Something"], EXAMPLE_GAP, "A", "B");
    const joined = steps.join(" ");
    REGISTRY_CONCEPTS.forEach(c => assert.ok(!joined.includes(c), `must not contain "${c}"`));
    assert.ok(!joined.includes("Review "), 'must not contain the old "Review ..." coaching line');
});

test("rdBuildNextSteps: no reasoning gaps + recommendedTopics present -> topics fallback still appears", () => {
    const steps = rdBuildNextSteps(["React", "FastAPI"], NO_GAPS, null, null);
    assert.ok(steps.length > 0, "expected fallback steps from recommendedTopics");
    assert.ok(steps[0].includes("React"), "expected recommendedTopics fallback to name the topic");
});

test("rdBuildNextSteps: no reasoning gaps + no recommendedTopics -> empty steps handled safely (no throw)", () => {
    const steps = rdBuildNextSteps([], NO_GAPS, null, null);
    assert.strictEqual(steps.length, 0);
});

// ── rdBuildDebrief ───────────────────────────────────────────────────────

test("rdBuildDebrief: signature no longer takes a missingConcepts parameter (6-arg signature)", () => {
    assert.strictEqual(rdBuildDebrief.length, 6);
});

test("rdBuildDebrief: never claims registry-only concepts 'never came up'", () => {
    const text = rdBuildDebrief("adequate", {}, EXAMPLE_GAP, "Strong Project", "Weak Project", []);
    REGISTRY_CONCEPTS.forEach(c => assert.ok(!text.includes(c), `debrief must not contain "${c}"`));
    assert.ok(!text.includes("never came up"), 'must not contain the old "never came up" sentence');
});

test("rdBuildDebrief: reasoning-gap growth sentence still present", () => {
    const text = rdBuildDebrief("adequate", {}, EXAMPLE_GAP, "Strong Project", "Weak Project", []);
    assert.ok(text.length > 0);
});

console.log(`\n${passed} passed`);
