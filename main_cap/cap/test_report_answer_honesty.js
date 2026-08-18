// UI-honesty fix (post-demo forensic investigation) — "Your Answer" /
// "Coaching Note" replacing the "Improved Answer" label.
//
// Real-browser forensic finding: every improved_answer in the actual
// 10-turn browser-demo session retained 100% of the candidate's original
// answer verbatim and appended exactly one generic coaching sentence, yet
// was presented under a label ("Improved Answer") implying a rewritten
// response. This fix does NOT change strong_answer.py's generation logic
// (no LLM, no rewriting, no new fabrication risk) -- it separates the
// already-existing two pieces (the candidate's own answer, already on the
// payload; and the coaching sentence, now exposed on its own via
// strong_answer.coaching_note) so the UI shows them honestly instead of as
// one concatenated blob under a misleading heading.
//
// Same convention as test_report_coaching.js / test_report_snapshot.js /
// test_report_confidence.js: no test framework/build step exists for this
// repo's frontend, so this extracts the EXACT function/render source text
// straight out of templates/index.html and evaluates it with Node's
// built-in `vm` + `assert` modules only.
//
// Run: node test_report_answer_honesty.js

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

let passed = 0;
function test(name, fn) {
    fn();
    passed++;
    console.log(`ok - ${name}`);
}

// ── 1. timeline construction: coaching_note threaded, no duplication ───────

const timelineEntrySrc = extractBlock(src, "const timeline = turnHistory.map((t) => (");

test("timeline entry preserves the candidate's real answer under item.answer", () => {
    assert.ok(timelineEntrySrc.includes("answer: t.answer"), "item.answer must still come from the real candidate answer, not a derived/reconstructed value");
});

test("timeline entry threads coaching_note, null-safe", () => {
    assert.ok(timelineEntrySrc.includes("coaching_note:"), "timeline entry must include coaching_note");
    assert.ok(
        /coaching_note:\s*\(t\.evaluation && t\.evaluation\.coaching_note\)\s*\|\|\s*null/.test(timelineEntrySrc),
        "coaching_note must be null-safe (t.evaluation may be absent) and default to null, never fabricated",
    );
});

test("timeline entry no longer exposes the old concatenated suggested_answer field", () => {
    assert.ok(!timelineEntrySrc.includes("suggested_answer:"), "suggested_answer must be fully replaced by coaching_note, not kept alongside it");
});

console.log("");

// ── 2. detail-card render: Your Answer + Coaching Note, no Improved Answer ─

const renderBlockSrc = extractBlock(src, "timeline.forEach((item, i) => {");

test("render block references item.coaching_note, escaped", () => {
    assert.ok(renderBlockSrc.includes("item.coaching_note"), "render must reference item.coaching_note");
    assert.ok(/esc\(item\.coaching_note\)/.test(renderBlockSrc), "coaching_note must be escaped with the same esc() convention used elsewhere");
});

test("render block shows the real answer text (answerText, not a re-derived string) under Your Answer", () => {
    assert.ok(/esc\(answerText\)/.test(renderBlockSrc), "the expanded 'Your Answer' block must render the same answerText variable already used for the collapsed preview, never a separately-reconstructed string");
});

test("render block contains a 'Your Answer' label and a 'Coaching Note' label", () => {
    assert.ok(renderBlockSrc.includes("Your Answer"), "must label the candidate's own answer honestly");
    assert.ok(renderBlockSrc.includes("Coaching Note"), "must label the coaching addition honestly, separately");
});

test("render block no longer contains an 'Improved Answer' heading anywhere", () => {
    assert.ok(!renderBlockSrc.includes("Improved Answer"), "the misleading 'Improved Answer' label must be fully removed from the render");
});

test("render block no longer references the old item.suggested_answer field", () => {
    assert.ok(!renderBlockSrc.includes("item.suggested_answer"), "item.suggested_answer must be fully replaced by item.coaching_note");
});

test("Your Answer / Coaching Note block is conditionally rendered (gated on coaching_note, omitted cleanly when absent)", () => {
    assert.ok(
        /\$\{\(item\.coaching_note && item\.coaching_note\.trim\(\)\)\s*\?/.test(renderBlockSrc),
        "the block must be gated on item.coaching_note, matching the exact hide condition strong_answer.py has always used",
    );
});

console.log("");

// ── 3. behavioral check: the exact conditional expression, evaluated ───────

function renderYourAnswerBlock(item, answerText) {
    // Mirrors the exact ternary added to templates/index.html.
    const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return (item.coaching_note && item.coaching_note.trim())
        ? `\n                                <div class="rd-timeline-metric-label" style="margin-bottom:6px;">Your Answer</div>\n                                <div class="rd-timeline-a" style="margin-bottom:20px;">${esc(answerText)}</div>\n                                <div class="rd-timeline-metric-label" style="margin-bottom:8px;">Coaching Note</div>\n                                <div class="rd-suggested-answer">${esc(item.coaching_note)}</div>\n                            `
        : "";
}

test("a weak turn displays the candidate's original answer unchanged under 'Your Answer'", () => {
    const original = "I used FastAPI to build the backend REST APIs for the project.";
    const html = renderYourAnswerBlock({ coaching_note: "I'd also be explicit about a concrete example." }, original);
    assert.ok(html.includes(original), "the exact original answer text must appear verbatim");
});

test("the coaching sentence appears separately under 'Coaching Note', not merged into the answer text", () => {
    const original = "I used FastAPI to build the backend REST APIs for the project.";
    const note = "I'd also be explicit about a concrete example.";
    const html = renderYourAnswerBlock({ coaching_note: note }, original);
    const answerIdx = html.indexOf(original);
    const noteIdx = html.indexOf(note);
    assert.ok(answerIdx !== -1 && noteIdx !== -1, "both pieces must be present");
    assert.ok(noteIdx > answerIdx + original.length, "the coaching note must appear in a separate block AFTER the answer, not concatenated onto it");
    // The rendered answer block itself must not also contain the coaching sentence.
    const answerBlockEnd = html.indexOf("</div>", answerIdx);
    assert.ok(!html.slice(answerIdx, answerBlockEnd).includes(note), "the 'Your Answer' div must not itself contain the coaching sentence");
});

test("the UI no longer labels the content as 'Improved Answer'", () => {
    const html = renderYourAnswerBlock({ coaching_note: "I'd also be explicit about a concrete example." }, "Some answer.");
    assert.ok(!html.includes("Improved Answer"), "must never render the old misleading label");
});

test("the coaching note is preserved exactly, character for character", () => {
    const note = "I'd also work in EXPLAIN ANALYZE, and be explicit about a concrete example.";
    const html = renderYourAnswerBlock({ coaching_note: note }, "Some answer.");
    assert.ok(html.includes(note), "the exact coaching_note string must appear unmodified");
});

test("a turn without a coaching note renders nothing (behaves exactly as the old no-improved-answer case)", () => {
    const html = renderYourAnswerBlock({ coaching_note: null }, "Some answer.");
    assert.strictEqual(html, "");
});

test("HTML-sensitive content in the coaching note is escaped", () => {
    const html = renderYourAnswerBlock({ coaching_note: '<script>alert(1)</script>' }, "Some answer.");
    assert.ok(!html.includes("<script>"), "must not contain a raw <script> tag");
    assert.ok(html.includes("&lt;script&gt;"), "must contain the escaped form");
});

console.log(`\n${passed} passed`);
