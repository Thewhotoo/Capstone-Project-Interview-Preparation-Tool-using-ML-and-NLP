// Technical Interview frontend (templates/index.html, "Technical Interview:
// shared report pieces" through handleSubmission): the chat runs on
// /api/tech-interview/*, shows follow-ups and clarifications as their own
// turns, shows no scores live, and the report cards escape everything.
//
// Same convention as test_session_integrity.js: the EXACT source block is
// extracted from index.html and run with Node's `vm`, stubbing the DOM,
// fetch and the sibling helpers it calls.
//
// Run: node test_tech_interview_ui.js

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const src = fs.readFileSync(path.join(__dirname, "templates", "index.html"), "utf8");
const START = "// ─── Technical Interview: shared report pieces ───";
const END = 'inputField.addEventListener("keydown"';
const startIdx = src.indexOf(START);
const endIdx = src.indexOf(END, startIdx);
if (startIdx === -1 || endIdx === -1) throw new Error("Technical Interview block not found");
const block = src.slice(startIdx, endIdx);

function helper(name) {
    const i = src.indexOf(`function ${name}(`);
    if (i === -1) throw new Error(`${name} not found`);
    let depth = 0;
    for (let j = src.indexOf("{", i); j < src.length; j++) {
        if (src[j] === "{") depth++;
        else if (src[j] === "}" && --depth === 0) return src.slice(i, j + 1);
    }
    throw new Error(`${name} not closed`);
}

function makeSandbox(responses) {
    const calls = [];
    const sb = {
        messages: [], toasts: [], finished: 0, armed: 0,
        interviewFlow: { mode: "technical", phase: "technical" },
        techSessionId: null, techPrompt: null,
        inputField: { value: "", disabled: false },
        messagesDiv: { lastElementChild: null },
        dashboardContainer: { innerHTML: "", style: {} },
        console: { error() {} },
    };
    sb.addMessage = (text, sender) => { sb.messages.push({ text, sender }); };
    sb.enableInput = () => { sb.inputField.disabled = false; };
    sb.disableInput = () => { sb.inputField.disabled = true; };
    sb.showTyping = sb.hideTyping = () => {};
    sb.sleep = () => Promise.resolve();
    sb.finishTechnicalRound = () => { sb.finished++; };
    sb.proctorArm = () => { sb.armed++; };
    sb.showToast = (msg) => sb.toasts.push(msg);
    sb.setSystemLog = () => {};
    sb.fetchJson = async (url, options) => {
        calls.push({ url, body: options && options.body ? JSON.parse(options.body) : null });
        const next = responses.shift();
        if (next instanceof Error) throw next;
        return next;
    };
    sb.calls = calls;
    vm.createContext(sb);
    vm.runInContext(`${helper("esc")}\n${helper("pct")}\n${block.replace(/^(\s*)(let|const) /gm, "$1var ")}`, sb);
    return sb;
}

const q = (n, kind = "question", text = `Question ${n}?`) => ({
    number: n, total: 2, kind, text, subject: "os", subject_label: "Operating Systems",
    topic: "Paging", difficulty: "easy", question_id: `os.q${n}`,
});

(async () => {
    // start → follow-up → next question → finished
    const sb = makeSandbox([
        { session: { id: 7 }, prompt: q(1) },
        { prompt: q(1, "followup", "What about the TLB?"), finished: false },
        { prompt: q(2), finished: false },
        { prompt: null, finished: true },
    ]);
    await sb.beginTechInterview();
    assert.deepStrictEqual(sb.calls[0], { url: "/api/tech-interview/start", body: { mode: "standalone" } });
    assert.strictEqual(sb.techSessionId, 7);
    assert.strictEqual(sb.armed, 1);
    assert.ok(sb.messages[0].text.includes("Q1/2"));

    for (const answer of ["paging splits memory", "it caches translations", "second answer"]) {
        sb.inputField.value = answer;
        await sb.handleSubmission();
    }
    assert.strictEqual(sb.calls[1].url, "/api/tech-interview/7/answer");
    assert.deepStrictEqual(sb.calls[1].body, { answer: "paging splits memory" });
    const bot = sb.messages.filter((m) => m.sender === "bot").map((m) => m.text);
    assert.ok(bot[1].includes("Follow-up") && bot[1].includes("What about the TLB?"));
    assert.ok(bot[2].includes("Q2/2"));
    assert.ok(!bot.some((t) => /\d+%|score/i.test(t)), "no scores are shown during the interview");
    assert.strictEqual(sb.finished, 1);

    // Round 2 asks for the round2 mode; a failed start ends the round
    const round2 = makeSandbox([new Error("down")]);
    round2.interviewFlow.mode = "full";
    await round2.beginTechInterview();
    assert.strictEqual(round2.calls[0].body.mode, "round2");
    assert.strictEqual(round2.finished, 1);
    assert.strictEqual(round2.techSessionId, null);

    // a failed answer is restored to the input, not lost
    const flaky = makeSandbox([{ session: { id: 3 }, prompt: q(1) }, new Error("timeout")]);
    await flaky.beginTechInterview();
    flaky.inputField.value = "my answer";
    await flaky.handleSubmission();
    assert.strictEqual(flaky.inputField.value, "my answer");
    assert.strictEqual(flaky.inputField.disabled, false);
    assert.strictEqual(flaky.toasts.length, 1);

    // the report card shows points and follow-ups, escaped
    const card = sb.techQuestionCardHtml({
        number: 1, subject_label: "OS", topic: "Paging", difficulty: "easy", score: 0.5,
        question: "What is <b>paging</b>?", answer: "<script>x</script>",
        covered: ["splits memory"], partial: [], missing: ["uses a page table"],
        exchanges: [{ kind: "followup", prompt: "And the table?", answer: "no idea", verdict: "missing" }],
        reference_answer: "Paging divides memory into frames.",
    }, 0);
    assert.ok(!card.includes("<script>") && card.includes("&lt;script&gt;"));
    assert.ok(card.includes('class="covered"') && card.includes('class="missing"'));
    assert.ok(card.includes("not recovered") && card.includes("50%") && card.includes("Model answer"));
    assert.strictEqual(sb.techGradeLabel(0.85), "Excellent");
    assert.strictEqual(sb.techGradeLabel(0.3), "Weak");

    // the standalone report renders with and without answered questions
    const attention = { sessionMs: 60000, totalDeviationMs: 0, attentionScore: 90, totalWarnings: 0,
                        faceAbsentWarnings: 0, livenessRechecks: 0, livenessFailures: 0 };
    sb.triggerDashboard({ questions: [], averageScore: null, summary: null, attention, integrity: null });
    assert.ok(sb.dashboardContainer.innerHTML.includes("No questions were answered"));
    sb.triggerDashboard({
        questions: [{ number: 1, subject_label: "OS", topic: "Paging", difficulty: "easy", score: 0.9,
                      question: "Q", answer: "A", covered: ["x"], partial: [], missing: [], exchanges: [] }],
        averageScore: 0.9, attention, integrity: { terminated: false },
        summary: { questions_planned: 10, by_subject: { OS: 0.9 }, weak_topics: [] },
    });
    assert.ok(sb.dashboardContainer.innerHTML.includes("BY SUBJECT") && sb.dashboardContainer.innerHTML.includes("/ 10"));

    console.log("test_tech_interview_ui.js: all passed");
})().catch((err) => { console.error(err); process.exit(1); });
