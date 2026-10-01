// UI-presentation fix — remove the redundant "The Debrief" heading from the
// final report. The debrief PARAGRAPH (`rd-debrief-text`, built server-side
// by `rdBuildDebrief` and threaded through unchanged) stays exactly as-is;
// only the visible section-title heading directly above it is removed, since
// the paragraph itself already reads as prose without needing a label.
//
// Same convention as test_report_answer_honesty.js / test_report_coaching.js
// / test_report_confidence.js / test_report_snapshot.js: no test
// framework/build step exists for this repo's frontend, so this asserts
// directly against the real markup in templates/index.html rather than a
// hand-copied duplicate that could drift.
//
// Run: node test_report_debrief_heading.js

const fs = require("fs");
const path = require("path");
const assert = require("assert");

const HTML_PATH = path.join(__dirname, "templates", "index.html");
const src = fs.readFileSync(HTML_PATH, "utf8");

let passed = 0;
function test(name, fn) {
    fn();
    console.log("ok -", name);
    passed++;
}

test("the report body no longer renders a 'The Debrief' section-title heading", () => {
    assert.ok(
        !src.includes('<div class="rd-section-title">The Debrief</div>'),
        "the redundant 'The Debrief' heading must be removed from the report body",
    );
    assert.ok(
        !/rd-report-body["'][^]{0,40}The Debrief/.test(src),
        "no residual 'The Debrief' heading should remain immediately inside rd-report-body",
    );
});

test("the debrief paragraph itself still renders, unchanged", () => {
    assert.ok(
        src.includes(
            '<p class="rd-debrief-text">${esc((data.debrief_text && data.debrief_text.trim()) || '
            + '"This was a steady discussion without one section clearly pulling ahead of the rest.")}</p>',
        ),
        "the debrief paragraph's render expression must be byte-for-byte unchanged -- only the heading above it was removed",
    );
});

test("other report section-title headings are untouched", () => {
    assert.ok(src.includes('<div class="rd-section-title">Performance Snapshot</div>'),
        "Performance Snapshot heading must remain");
    assert.ok(src.includes("Before Your Next Interview"),
        "Before Your Next Interview heading must remain");
    assert.ok(src.includes("How Each Topic Went"),
        "How Each Topic Went heading must remain");
});

console.log(`\n${passed} passed`);
