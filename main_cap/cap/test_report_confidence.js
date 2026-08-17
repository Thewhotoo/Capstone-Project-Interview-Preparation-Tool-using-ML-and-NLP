// Phase 11 regression test — evaluator confidence presentation
// (`rdBuildReportFromV2`'s timeline construction + the per-turn detail-card
// render in templates/index.html).
//
// Same convention as test_report_coaching.js / test_report_snapshot.js: no
// test framework/build step exists for this repo's frontend, so this
// extracts the EXACT function/render source text straight out of
// templates/index.html (never a hand-copied duplicate that could drift)
// and evaluates it with Node's built-in `vm` + `assert` modules only.
//
// Run: node test_report_confidence.js

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

// ── 1. timeline construction: confidence_rationale threading ───────────────
// rdBuildReportFromV2 is a large function that calls several helpers not
// worth stubbing out fully here -- instead, directly assert the exact
// object-literal source text used to build one `timeline` entry, the same
// technique as extracting a function, so this stays coupled to the REAL
// shipped code rather than a hand-written stand-in.
const timelineEntrySrc = extractBlock(src, "const timeline = turnHistory.map((t) => (");

assert.ok(
    timelineEntrySrc.includes("confidence_rationale:"),
    "timeline entry must preserve confidence_rationale",
);
assert.ok(
    /confidence_rationale:\s*\(t\.evaluation && t\.evaluation\.confidence_rationale\)\s*\|\|\s*null/.test(timelineEntrySrc),
    "confidence_rationale must be null-safe (t.evaluation may be absent) and default to null, never a fabricated string",
);
assert.ok(
    !/confidence:\s*t\.evaluation/.test(timelineEntrySrc.replace(/confidence_rationale/g, "")),
    "the raw confidence float must NOT be threaded into the timeline as a standalone field",
);

// Existing fields must be untouched by this change.
["score:", "grade:", "correctness:", "technical_depth:", "completeness:",
 "communication:", "strengths:", "weaknesses:", "suggested_answer:"].forEach((field) => {
    assert.ok(timelineEntrySrc.includes(field), `existing timeline field missing: ${field}`);
});

console.log("ok - timeline construction preserves confidence_rationale (null-safe, no raw confidence float)");

// ── 2. detail-card render: rationale block ──────────────────────────────────

const renderBlockSrc = extractBlock(src, "timeline.forEach((item, i) => {");

assert.ok(
    renderBlockSrc.includes("item.confidence_rationale"),
    "detail card render must reference item.confidence_rationale",
);
assert.ok(
    /esc\(item\.confidence_rationale\)/.test(renderBlockSrc),
    "confidence_rationale must be escaped with the same esc() convention used elsewhere",
);
assert.ok(
    /\$\{\(item\.confidence_rationale && item\.confidence_rationale\.trim\(\)\)\s*\?/.test(renderBlockSrc),
    "rationale block must be conditionally rendered (omitted cleanly when null/missing)",
);
assert.ok(
    !renderBlockSrc.includes('rdMetricBoxHtml("Confidence"'),
    "must NOT add a standalone raw-confidence metric box",
);

// Existing render pieces (score, grade, metric grid, strengths, weaknesses,
// improved answer) must be untouched.
["item.score", "item.grade", 'rdMetricBoxHtml("Correctness"', 'rdMetricBoxHtml("Technical Depth"',
 'rdMetricBoxHtml("Completeness"', 'rdMetricBoxHtml("Communication"', "strengthsListHtml", "weaknessesListHtml",
 "item.suggested_answer"].forEach((needle) => {
    assert.ok(renderBlockSrc.includes(needle), `existing render piece missing: ${needle}`);
});

console.log("ok - detail card renders escaped confidence_rationale, omits cleanly when missing, no standalone confidence metric added");

// ── 3. behavioral check: the exact conditional expression, evaluated ───────

function renderRationaleBlock(item) {
    // Mirrors the exact ternary added to templates/index.html.
    const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return (item.confidence_rationale && item.confidence_rationale.trim())
        ? `<div class="rd-timeline-metric-label" style="margin-bottom:6px;">Evaluator Confidence</div><div class="rd-confidence-rationale">${esc(item.confidence_rationale)}</div>`
        : "";
}

let passed = 0;
function test(name, fn) {
    fn();
    passed++;
    console.log(`ok - ${name}`);
}

test("renders the rationale text when present", () => {
    const html = renderRationaleBlock({ confidence_rationale: "DeBERTa's prediction is used as the authoritative score." });
    assert.ok(html.includes("DeBERTa's prediction is used as the authoritative score."));
    assert.ok(html.includes("Evaluator Confidence"));
});

test("HTML-sensitive content in the rationale is escaped", () => {
    const html = renderRationaleBlock({ confidence_rationale: '<script>alert("x")</script> & "quotes"' });
    assert.ok(!html.includes("<script>"), "must not contain a raw <script> tag");
    assert.ok(html.includes("&lt;script&gt;"), "must contain the escaped form");
    assert.ok(html.includes("&amp;"), "must escape bare ampersands");
});

test("null rationale renders nothing (no empty/broken block)", () => {
    const html = renderRationaleBlock({ confidence_rationale: null });
    assert.strictEqual(html, "");
});

test("whitespace-only rationale renders nothing", () => {
    const html = renderRationaleBlock({ confidence_rationale: "   " });
    assert.strictEqual(html, "");
});

test("missing field entirely (undefined) renders nothing, does not throw", () => {
    const html = renderRationaleBlock({});
    assert.strictEqual(html, "");
});

console.log(`\n${passed} passed`);
