// A2 production cutover -- canonical (four-dimension) result rendering.
//
// Verifies that templates/index.html's resume-discussion report correctly
// renders A2's four canonical dimensions (technical_correctness,
// depth_specificity, relevance_completeness, grounding_ownership)
// ALONGSIDE the pre-existing legacy dimension rendering (never replacing
// it -- rollback to the legacy HeuristicEvaluator/deployed_model/ must
// still render correctly).
//
// Same extraction technique as test_startup_guard.js: this pulls the EXACT
// source of the real constants/functions straight out of
// templates/index.html (never a hand-copied duplicate that could drift)
// and evaluates that exact text with Node's built-in `vm` + `assert`
// modules -- no test framework/build step exists for this repo's frontend
// (see test_startup_guard.js's own comment).
//
// Run: node test_canonical_dimension_rendering.js

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
    extractBlock(src, "function esc(str) {"),
    extractBlock(src, "function rdDimScore(evaluation, name) {").replace("function ", "var rdDimScore = function "),
    extractBlock(src, "function rdMetricBoxHtml(label, value) {").replace("function ", "var rdMetricBoxHtml = function "),
    extractBlock(src, "function rdHasCanonicalDims(item) {").replace("function ", "var rdHasCanonicalDims = function "),
    extractBlock(src, "const RD_DIM_STRONG = {").replace("const ", "var "),
    extractBlock(src, "const RD_DIM_WEAK_SENTENCE = {").replace("const ", "var "),
    extractBlock(src, "const RD_DIM_ORDER = Object.keys(RD_DIM_STRONG);").replace("const ", "var "),
    extractBlock(src, "const RD_DIM_LABELS = {").replace("const ", "var "),
].join("\n\n");

const sandbox = { console };
vm.createContext(sandbox);
vm.runInContext(blocks, sandbox);

const CANONICAL_DIMS = [
    "technical_correctness", "depth_specificity", "relevance_completeness", "grounding_ownership",
];
const LEGACY_DIMS = [
    "technical_accuracy", "technical_depth", "communication", "completeness", "resume_grounding",
];

function test(name, fn) {
    try {
        fn();
        console.log(`PASS: ${name}`);
    } catch (e) {
        console.error(`FAIL: ${name}`);
        console.error(e);
        process.exitCode = 1;
    }
}

test("all four canonical dimensions present in RD_DIM_STRONG", () => {
    CANONICAL_DIMS.forEach((d) => assert.ok(sandbox.RD_DIM_STRONG[d], `missing ${d} in RD_DIM_STRONG`));
});

test("all four canonical dimensions present in RD_DIM_WEAK_SENTENCE", () => {
    CANONICAL_DIMS.forEach((d) => assert.ok(sandbox.RD_DIM_WEAK_SENTENCE[d], `missing ${d} in RD_DIM_WEAK_SENTENCE`));
});

test("all four canonical dimensions present in RD_DIM_LABELS with the exact display names", () => {
    assert.strictEqual(sandbox.RD_DIM_LABELS.technical_correctness, "Technical Correctness");
    assert.strictEqual(sandbox.RD_DIM_LABELS.depth_specificity, "Depth & Specificity");
    assert.strictEqual(sandbox.RD_DIM_LABELS.relevance_completeness, "Relevance & Completeness");
    assert.strictEqual(sandbox.RD_DIM_LABELS.grounding_ownership, "Grounding & Ownership");
});

test("canonical dimensions are included in RD_DIM_ORDER (drives the Performance Snapshot)", () => {
    CANONICAL_DIMS.forEach((d) => assert.ok(sandbox.RD_DIM_ORDER.includes(d), `${d} missing from RD_DIM_ORDER`));
});

test("legacy dimensions are STILL present, unremoved (rollback safety)", () => {
    LEGACY_DIMS.forEach((d) => {
        assert.ok(sandbox.RD_DIM_STRONG[d], `legacy ${d} missing from RD_DIM_STRONG -- legacy support was removed`);
        assert.ok(sandbox.RD_DIM_WEAK_SENTENCE[d], `legacy ${d} missing from RD_DIM_WEAK_SENTENCE`);
        assert.ok(sandbox.RD_DIM_LABELS[d], `legacy ${d} missing from RD_DIM_LABELS`);
        assert.ok(sandbox.RD_DIM_ORDER.includes(d), `legacy ${d} missing from RD_DIM_ORDER`);
    });
});

test("rdDimScore finds a canonical dimension by exact name", () => {
    const evaluation = {
        dimensions: [
            { name: "technical_correctness", raw_score: 0.75 },
            { name: "depth_specificity", raw_score: 0.5 },
            { name: "relevance_completeness", raw_score: 1.0 },
            { name: "grounding_ownership", raw_score: 0.25 },
        ],
    };
    assert.strictEqual(sandbox.rdDimScore(evaluation, "technical_correctness"), 0.75);
    assert.strictEqual(sandbox.rdDimScore(evaluation, "depth_specificity"), 0.5);
    assert.strictEqual(sandbox.rdDimScore(evaluation, "relevance_completeness"), 1.0);
    assert.strictEqual(sandbox.rdDimScore(evaluation, "grounding_ownership"), 0.25);
});

test("rdDimScore returns null for a dimension not present this turn (never 0)", () => {
    const evaluation = { dimensions: [{ name: "technical_correctness", raw_score: 0.75 }] };
    assert.strictEqual(sandbox.rdDimScore(evaluation, "depth_specificity"), null);
});

test("rdHasCanonicalDims is true when a canonical evaluation is present", () => {
    const item = {
        technical_correctness: 0.75, depth_specificity: 0.5,
        relevance_completeness: 1.0, grounding_ownership: null,
    };
    assert.strictEqual(sandbox.rdHasCanonicalDims(item), true);
});

test("rdHasCanonicalDims is false for a legacy-only (no canonical fields scored) turn", () => {
    const item = {
        technical_correctness: null, depth_specificity: null,
        relevance_completeness: null, grounding_ownership: null,
    };
    assert.strictEqual(sandbox.rdHasCanonicalDims(item), false);
});

test("rdMetricBoxHtml renders the canonical label and percentage for a real score", () => {
    const html = sandbox.rdMetricBoxHtml("Grounding & Ownership", 0.75);
    assert.ok(html.includes("Grounding &amp; Ownership"), `label not rendered: ${html}`);
    assert.ok(html.includes("75%"), `percentage not rendered: ${html}`);
});

test("rdMetricBoxHtml renders nothing (not '0%') for a null canonical score", () => {
    assert.strictEqual(sandbox.rdMetricBoxHtml("Grounding & Ownership", null), "");
});

if (process.exitCode !== 1) {
    console.log("\nAll canonical dimension rendering tests passed.");
}
