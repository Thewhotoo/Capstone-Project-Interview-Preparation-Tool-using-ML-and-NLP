// Concept Coverage removal (product decision, post-Phase-10) — the
// Performance Snapshot (`rdBuildSnapshot` in templates/index.html) no
// longer renders a Concept Coverage row at all. The honest, sample-size-
// qualified presentation from Phase 10 ("Concept Coverage (1 of 10 turns):
// 0%") was still judged not useful enough to a candidate to keep
// surfacing -- this is a presentation-only removal; concept_analysis.py,
// EvaluationResult.concept_coverage, and concept_coverage_percent are all
// untouched and the backend still computes/sends concept_coverage_pct
// every turn, it simply isn't read into the Snapshot anymore.
//
// Same convention as test_report_coaching.js: no test framework/build step
// exists for this repo's frontend, so this extracts the EXACT function
// source text straight out of templates/index.html (never a hand-copied
// duplicate that could drift) and evaluates it with Node's built-in `vm` +
// `assert` modules only.
//
// Run: node test_report_snapshot.js

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
    extractBlock(src, "const RD_DIM_STRONG = {"),
    extractBlock(src, "const RD_DIM_WEAK_SENTENCE = {"),
    extractBlock(src, "const RD_DIM_ORDER = "),
    extractBlock(src, "const RD_DIM_LABELS = {"),
    extractBlock(src, "function rdBuildSnapshot("),
].join("\n\n");

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(blocks, sandbox);
const { rdBuildSnapshot } = sandbox;

assert.strictEqual(typeof rdBuildSnapshot, "function", "rdBuildSnapshot not extracted");

// ── render-loop source guard ────────────────────────────────────────────
// Directly inspects the real snapshotHtml render line in templates/index.html
// (not a reimplementation) to confirm it still branches on typeof row.value
// before calling .toFixed() and falls back to row.note for non-numeric rows
// -- generic defensive coding, independent of Concept Coverage specifically.
const renderLine = src.slice(
    src.indexOf('<span class="rd-snapshot-value">'),
    src.indexOf("</span>", src.indexOf('<span class="rd-snapshot-value">')),
);
assert.ok(
    renderLine.includes('typeof row.value === "number"'),
    "render loop must branch on typeof row.value before calling toFixed()",
);
assert.ok(
    renderLine.includes("row.note"),
    "render loop must fall back to row.note for non-numeric rows",
);

let passed = 0;
function test(name, fn) {
    fn();
    passed++;
    console.log(`ok - ${name}`);
}

// ── rdBuildSnapshot: Concept Coverage is absent ─────────────────────────────

test("Concept Coverage never appears in the Snapshot, regardless of dimension data", () => {
    const cases = [
        {},
        { technical_accuracy: 0.6, ownership: 0.25 },
        { technical_accuracy: 1.0, technical_depth: 1.0, communication: 1.0, completeness: 1.0, resume_grounding: 1.0 },
    ];
    cases.forEach((dimAverages) => {
        const rows = rdBuildSnapshot(72, dimAverages);
        const conceptRow = rows.find(r => r.label.startsWith("Concept Coverage"));
        assert.strictEqual(conceptRow, undefined, "no row's label may start with 'Concept Coverage'");
    });
});

test("rdBuildSnapshot only takes (avgOverallPct, dimAverages) -- no concept-coverage parameters", () => {
    const src2 = extractBlock(src, "function rdBuildSnapshot(");
    const signature = src2.slice(0, src2.indexOf(")") + 1);
    assert.strictEqual(signature, "function rdBuildSnapshot(avgOverallPct, dimAverages)");
});

test("Overall row is always first and correct", () => {
    const rows = rdBuildSnapshot(72, { technical_accuracy: 0.6, ownership: 0.25 });
    assert.strictEqual(rows[0].label, "Overall");
    assert.strictEqual(rows[0].value, 72);
});

test("every dimension actually scored this session appears -- not a hardcoded subset", () => {
    const dimAverages = { technical_accuracy: 0.6, ownership: 0.25 };
    const rows = rdBuildSnapshot(72, dimAverages);
    const accRow = rows.find(r => r.label === "Technical Accuracy");
    const ownRow = rows.find(r => r.label === "Ownership");
    assert.strictEqual(accRow.value, 60);
    assert.strictEqual(ownRow.value, 25);
});

test("a dimension never scored this session is omitted entirely, never shown as 0%", () => {
    const rows = rdBuildSnapshot(72, { technical_accuracy: 0.6 });
    const testingRow = rows.find(r => r.label === "Testing");
    assert.strictEqual(testingRow, undefined);
});

console.log(`\n${passed} passed`);
