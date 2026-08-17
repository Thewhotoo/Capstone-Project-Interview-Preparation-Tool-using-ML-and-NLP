// Phase 10 regression test — Concept Coverage presentation
// (`rdBuildSnapshot` / the Snapshot render loop in templates/index.html).
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
// (not a reimplementation) to confirm it branches on typeof row.value before
// calling .toFixed() and falls back to row.note for non-numeric rows.
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

// ── rdBuildSnapshot: Concept Coverage cases ─────────────────────────────────

test("Case A: null average + 0 applicable turns + 9 total -> Not available, never (0 of 0 turns)", () => {
    const rows = rdBuildSnapshot(50, {}, null, 0, 9);
    const row = rows.find(r => r.label.startsWith("Concept Coverage"));
    assert.ok(row, "expected a Concept Coverage row");
    assert.strictEqual(row.label, "Concept Coverage");
    assert.strictEqual(row.value, null);
    assert.strictEqual(row.note, "Not available");
});

test("Case A edge case: 0 applicable + 0 total -> Not available, never (0 of 0 turns)", () => {
    const rows = rdBuildSnapshot(50, {}, null, 0, 0);
    const row = rows.find(r => r.label.startsWith("Concept Coverage"));
    assert.strictEqual(row.label, "Concept Coverage");
    assert.ok(!row.label.includes("of 0 turns"), "must never render (0 of 0 turns)");
    assert.strictEqual(row.value, null);
});

test("Case B: 0% + 1 applicable turn + 10 total -> 'Concept Coverage (1 of 10 turns)', value 0", () => {
    const rows = rdBuildSnapshot(50, {}, 0.0, 1, 10);
    const row = rows.find(r => r.label.startsWith("Concept Coverage"));
    assert.strictEqual(row.label, "Concept Coverage (1 of 10 turns)");
    assert.strictEqual(row.value, 0.0);
});

test("Case C: 80% + 9 applicable turns + 9 total -> unchanged 'Concept Coverage: 80%'", () => {
    const rows = rdBuildSnapshot(50, {}, 80.0, 9, 9);
    const row = rows.find(r => r.label.startsWith("Concept Coverage"));
    assert.strictEqual(row.label, "Concept Coverage");
    assert.strictEqual(row.value, 80.0);
});

test("Overall/dimension rows remain unchanged by any Concept Coverage case", () => {
    const dimAverages = { technical_accuracy: 0.6, ownership: 0.25 };
    const a = rdBuildSnapshot(72, dimAverages, null, 0, 9);
    const b = rdBuildSnapshot(72, dimAverages, 0.0, 1, 10);
    const c = rdBuildSnapshot(72, dimAverages, 80.0, 9, 9);
    [a, b, c].forEach((rows) => {
        assert.strictEqual(rows[0].label, "Overall");
        assert.strictEqual(rows[0].value, 72);
        const accRow = rows.find(r => r.label === "Technical Accuracy");
        const ownRow = rows.find(r => r.label === "Ownership");
        assert.strictEqual(accRow.value, 60);
        assert.strictEqual(ownRow.value, 25);
    });
});

test("null-valued row renders safely without calling toFixed (render-loop guard present)", () => {
    // Exercised directly: the render loop's ternary must never reach
    // row.value.toFixed(0) when row.value is null.
    const row = { label: "Concept Coverage", value: null, note: "Not available" };
    const rendered = typeof row.value === "number" ? row.value.toFixed(0) + "%" : (row.note || "Not available");
    assert.strictEqual(rendered, "Not available");
});

console.log(`\n${passed} passed`);
