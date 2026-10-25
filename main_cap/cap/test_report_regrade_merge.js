// rdMergeRegrades (templates/index.html): end-of-session LLM re-grades overlay the
// live per-turn scores in the report, keeping per-turn extras; any count mismatch
// keeps the live scores. Same extraction convention as test_report_confidence.js.
// Run: node test_report_regrade_merge.js

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const src = fs.readFileSync(path.join(__dirname, "templates", "index.html"), "utf8");
const start = src.indexOf("function rdMergeRegrades(");
let depth = 0, i = src.indexOf("{", start), seen = false;
for (; i < src.length; i++) {
    if (src[i] === "{") { depth++; seen = true; }
    else if (src[i] === "}") { depth--; if (seen && depth === 0) { i++; break; } }
}
const ctx = {};
vm.runInNewContext(src.slice(start, i) + "\nthis.rdMergeRegrades = rdMergeRegrades;", ctx);

const history = [
    { question: "q1", evaluation: { overall_score: 0.5, grade: "adequate", coaching_note: "keep" } },
    { question: "q2 (unanswered)", evaluation: null },
    { question: "q3", evaluation: { overall_score: 0.4, grade: "weak" } },
];

const merged = ctx.rdMergeRegrades(history, [
    { overall_score: 0.8, grade: "good", reasoning: "llm" },
    { overall_score: 0.4, grade: "weak" },
]);
assert.strictEqual(merged[0].evaluation.overall_score, 0.8);
assert.strictEqual(merged[0].evaluation.coaching_note, "keep");
assert.strictEqual(merged[0].evaluation.llm_regraded, true);
assert.strictEqual(merged[1].evaluation, null);
assert.strictEqual(merged[2], history[2]);                       // unchanged score -> same object
assert.strictEqual(history[0].evaluation.overall_score, 0.5);    // input not mutated

const mismatch = ctx.rdMergeRegrades(history, [{ overall_score: 0.9 }]);
assert.strictEqual(mismatch, history);

console.log("test_report_regrade_merge.js: all assertions passed");
