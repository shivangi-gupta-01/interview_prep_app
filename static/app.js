// ---------- Tab switching ----------
const sidebar = document.getElementById("sidebar");
const menuButton = document.getElementById("menuButton");
const sidebarBackdrop = document.getElementById("sidebarBackdrop");

function closeSidebar() {
  sidebar?.classList.remove("mobile-open");
  sidebarBackdrop?.classList.add("hidden");
  menuButton?.setAttribute("aria-expanded", "false");
}

menuButton?.addEventListener("click", () => {
  const isOpen = sidebar.classList.toggle("mobile-open");
  sidebarBackdrop?.classList.toggle("hidden", !isOpen);
  menuButton.setAttribute("aria-expanded", String(isOpen));
});
sidebarBackdrop?.addEventListener("click", closeSidebar);

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.add("hidden"));
    btn.classList.add("active");
    document.getElementById("panel-" + btn.dataset.tab).classList.remove("hidden");
    closeSidebar();
  });
});

// ---------- Health check ----------
fetch("/api/health")
  .then((r) => r.json())
  .then((d) => {
    document.getElementById("apiStatus").textContent = `online (${d.model})`;
  })
  .catch(() => {
    document.getElementById("apiStatus").textContent = "offline — check GEMINI_API_KEY";
    document.querySelector(".dot").classList.add("err");
  });

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function showLoading(container) {
  container.innerHTML = `<div class="loading"><span class="spinner"></span> Working on it…</div>`;
}

function showError(container, msg) {
  container.innerHTML = `<div class="error-box">⚠ ${escapeHtml(getFriendlyError(msg))}</div>`;
}

function getFriendlyError(message) {
  const text = String(message || "").toLowerCase();
  if (text.includes("quota") || text.includes("resourceexhausted") || text.includes("429")) return "Gemini quota exhausted. Please try again later or check your billing plan.";
  if (text.includes("gemini_api_key") || text.includes("not configured")) return "AI service is not configured.";
  if (text.includes("timeout") || text.includes("timed out")) return "The AI service took too long to respond.";
  if (text.includes("resume") && text.includes("provide")) return "Please upload a resume or paste its text.";
  if (text.includes("file") && (text.includes("type") || text.includes("large"))) return "Please check the resume file type and size.";
  if (text.includes("extract")) return "Could not read that resume file.";
  if (text.includes("failed") || text.includes("request failed")) return "The request could not be completed.";
  return "Something went wrong. Please try again.";
}

async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

async function postForm(url, formData) {
  const res = await fetch(url, { method: "POST", body: formData });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

// =========================================================
// TAB 1: Interview question generation
// =========================================================
const interviewForm = document.getElementById("interviewForm");
const interviewResults = document.getElementById("interviewResults");

interviewForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showLoading(interviewResults);
  const fd = new FormData(interviewForm);
  const payload = {
    role: fd.get("role"),
    skills: (fd.get("skills") || "").split(",").map((s) => s.trim()).filter(Boolean),
    job_description: fd.get("job_description") || null,
    experience_level: fd.get("experience_level"),
    question_mix: fd.get("question_mix"),
    num_questions: parseInt(fd.get("num_questions"), 10),
    company: fd.get("company") || null,
  };
  try {
    const data = await postJSON("/api/interview/questions", payload);
    renderInterviewSet(data);
  } catch (err) {
    showError(interviewResults, err.message);
  }
});

function renderInterviewSet(data) {
  const cards = data.questions
    .map((q) => {
      return `
      <div class="card" data-qid="${q.id}">
        <div class="card-top">
          <div class="card-tags">
            <span class="tag ${q.category}">${q.category.replace("_", " ")}</span>
            <span class="tag ${q.difficulty}">${q.difficulty}</span>
          </div>
        </div>
        <div class="card-q">${escapeHtml(q.question)}</div>
        <div class="card-sub"><b>Why asked:</b> ${escapeHtml(q.why_asked)}</div>
        <div class="card-sub"><b>A strong answer covers:</b></div>
        <ul class="bullets">${q.what_good_answer_covers.map((b) => `<li>${escapeHtml(b)}</li>`).join("")}</ul>
        ${q.follow_ups.length ? `<div class="card-sub"><b>Likely follow-ups:</b></div><ul class="bullets">${q.follow_ups.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>` : ""}
        <div class="card-actions">
          <button class="link-btn" onclick="toggleAnswerBox(this, ${q.id})">Practice this answer →</button>
        </div>
        <div class="answer-box" id="answer-${q.id}" style="display:none">
          <textarea rows="4" placeholder="Type your answer here…" data-question="${escapeHtml(q.question)}" data-category="${q.category}"></textarea>
          <button class="btn ghost" style="margin-top:8px" onclick="evaluateAnswer(this, ${q.id}, '${escapeHtml(data.role)}')">Get feedback</button>
          <div class="eval-result" id="eval-${q.id}"></div>
        </div>
      </div>`;
    })
    .join("");

  interviewResults.innerHTML = `
    <div class="summary-line">${escapeHtml(data.focus_summary)}</div>
    ${cards}
  `;
}

window.toggleAnswerBox = function (btn, qid) {
  const box = document.getElementById("answer-" + qid);
  box.style.display = box.style.display === "none" ? "block" : "none";
};

window.evaluateAnswer = async function (btn, qid, role) {
  const box = document.getElementById("answer-" + qid);
  const textarea = box.querySelector("textarea");
  const evalDiv = document.getElementById("eval-" + qid);
  if (!textarea.value.trim()) {
    evalDiv.innerHTML = `<div class="error-box">Write an answer first.</div>`;
    return;
  }
  evalDiv.innerHTML = `<div class="loading"><span class="spinner"></span> Scoring…</div>`;
  try {
    const data = await postJSON("/api/interview/evaluate", {
      question: textarea.dataset.question,
      answer: textarea.value,
      role: role || null,
      category: textarea.dataset.category,
    });
    evalDiv.innerHTML = `
      <div class="eval-score">${data.score}<span style="font-size:13px;color:var(--paper-dim)">/100</span></div>
      <div class="card-sub"><b>Strengths:</b></div>
      <ul class="bullets">${data.strengths.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>
      <div class="card-sub"><b>Gaps:</b></div>
      <ul class="bullets">${data.gaps.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>
      ${data.star_check ? `<div class="card-sub"><b>STAR check:</b> ${escapeHtml(data.star_check)}</div>` : ""}
      <div class="card-sub" style="margin-top:8px"><b>Stronger version:</b></div>
      <div style="font-size:13.5px;white-space:pre-wrap">${escapeHtml(data.improved_answer)}</div>
    `;
  } catch (err) {
    evalDiv.innerHTML = `<div class="error-box">⚠ ${escapeHtml(getFriendlyError(err.message))}</div>`;
  }
};

// =========================================================
// TAB 2: Resume scenarios
// =========================================================
const scenarioForm = document.getElementById("scenarioForm");
const scenarioResults = document.getElementById("scenarioResults");

scenarioForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showLoading(scenarioResults);
  const fd = new FormData(scenarioForm);
  const file = fd.get("file");
  if (!(file && file.size > 0)) fd.delete("file");
  if (!fd.get("resume_text")) fd.delete("resume_text");
  try {
    const data = await postForm("/api/resume/scenarios", fd);
    renderScenarios(data);
  } catch (err) {
    showError(scenarioResults, err.message);
  }
});

function renderScenarios(data) {
  const highlights = `
    <div class="card">
      <div class="card-sub"><b>Resume highlights detected:</b></div>
      <ul class="bullets">${data.resume_highlights.map((h) => `<li>${escapeHtml(h)}</li>`).join("")}</ul>
    </div>`;

  const cards = data.scenarios
    .map(
      (s) => `
      <div class="card">
        <div class="card-tags"><span class="tag situational">based on your resume</span></div>
        <div class="card-sub" style="margin-top:8px"><b>Grounded in:</b> ${escapeHtml(s.based_on)}</div>
        <div class="card-q">${escapeHtml(s.scenario_question)}</div>
        <div class="card-sub"><b>Hints:</b></div>
        <ul class="bullets">${s.hints.map((h) => `<li>${escapeHtml(h)}</li>`).join("")}</ul>
        <div class="card-sub"><b>Ideal structure:</b></div>
        <ul class="bullets">${s.ideal_structure.map((h) => `<li>${escapeHtml(h)}</li>`).join("")}</ul>
      </div>`
    )
    .join("");

  scenarioResults.innerHTML = highlights + cards;
}

// =========================================================
// TAB 3: ATS score + optimize
// =========================================================
const atsForm = document.getElementById("atsForm");
const atsResults = document.getElementById("atsResults");
const optimizeBtn = document.getElementById("optimizeBtn");
let lastAtsPayload = null;
let lastAtsReport = null;

atsForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showLoading(atsResults);
  optimizeBtn.disabled = true;
  const fd = new FormData(atsForm);
  const file = fd.get("file");
  if (!(file && file.size > 0)) fd.delete("file");
  if (!fd.get("resume_text")) fd.delete("resume_text");

  // stash for the optimize step
  lastAtsPayload = {
    file: file && file.size > 0 ? file : null,
    resumeText: fd.get("resume_text") || "",
    jobDescription: fd.get("job_description") || "",
  };

  try {
    const data = await postForm("/api/ats/score", fd);
    renderAtsReport(data);
    lastAtsReport = data;
    optimizeBtn.disabled = false;
  } catch (err) {
    showError(atsResults, err.message);
    lastAtsPayload = null;
    lastAtsReport = null;
  }
});

optimizeBtn.addEventListener("click", async () => {
  if (!lastAtsPayload || !lastAtsReport) return;
  optimizeBtn.disabled = true;
  const container = document.createElement("div");
  container.innerHTML = `<div class="loading"><span class="spinner"></span> Rewriting your resume…</div>`;
  atsResults.appendChild(container);
  try {
    const fd = new FormData();
    if (lastAtsPayload.file) fd.append("file", lastAtsPayload.file);
    if (lastAtsPayload.resumeText) fd.append("resume_text", lastAtsPayload.resumeText);
    if (lastAtsPayload.jobDescription) fd.append("job_description", lastAtsPayload.jobDescription);
    fd.append("ats_report", JSON.stringify(lastAtsReport));
    const data = await postForm("/api/ats/optimize", fd);
    container.outerHTML = renderAtsOptimize(data);
  } catch (err) {
    container.innerHTML = `<div class="error-box">⚠ ${escapeHtml(getFriendlyError(err.message))}</div>`;
  } finally {
    optimizeBtn.disabled = false;
  }
});

// =========================================================
// TAB 4: Natural-language agent
// =========================================================
const agentForm = document.getElementById("agentForm");
const agentResults = document.getElementById("agentResults");

agentForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  showLoading(agentResults);
  const fd = new FormData(agentForm);
  try {
    const data = await postJSON("/api/agent/chat", {
      message: fd.get("message"),
      resume_text: fd.get("resume_text") || null,
      job_description: fd.get("job_description") || null,
    });
    agentResults.innerHTML = `<div class="card"><div class="tag situational">${escapeHtml(data.action)}</div><div class="agent-answer">${escapeHtml(data.answer)}</div></div>`;
  } catch (err) {
    showError(agentResults, err.message);
  }
});

function scoreColor(score) {
  if (score >= 80) return "var(--green)";
  if (score >= 55) return "var(--amber)";
  return "var(--red)";
}

function renderAtsReport(data) {
  const c = scoreColor(data.overall_score);
  const circumference = 2 * Math.PI * 62;
  const offset = circumference * (1 - data.overall_score / 100);

  const dial = `
    <div class="dial-wrap">
      <svg width="150" height="150" viewBox="0 0 150 150">
        <circle cx="75" cy="75" r="62" fill="none" stroke="var(--panel-raised)" stroke-width="12" />
        <circle cx="75" cy="75" r="62" fill="none" stroke="${c}" stroke-width="12"
          stroke-linecap="round" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"
          transform="rotate(-90 75 75)" />
      </svg>
      <div class="dial-score"><span class="num">${data.overall_score}</span><span class="lbl">ATS score</span></div>
    </div>`;

  const catRows = data.category_scores
    .map(
      (cat) => `
      <div class="cat-row">
        <span>${escapeHtml(cat.name)}</span>
        <div class="cat-bar-track"><div class="cat-bar-fill" style="width:${cat.score}%;background:${scoreColor(cat.score)}"></div></div>
        <span style="font-family:var(--mono);font-size:12px;text-align:right">${cat.score}</span>
      </div>
      <ul class="bullets cat-findings">${cat.findings.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>
    `
    )
    .join("");

  const matched = data.matched_keywords.map((k) => `<span class="kw matched">${escapeHtml(k)}</span>`).join("");
  const missing = data.missing_keywords.map((k) => `<span class="kw missing">${escapeHtml(k)}</span>`).join("");

  atsResults.innerHTML = `
    <div class="ats-summary">
      ${dial}
      <div>
        <div class="verdict">${escapeHtml(data.verdict)}</div>
        ${catRows}
      </div>
    </div>

    <div class="card">
      <div class="card-sub"><b>Quick wins</b> (do these first):</div>
      <ul class="bullets">${data.quick_wins.map((q) => `<li>${escapeHtml(q)}</li>`).join("")}</ul>
      ${data.formatting_issues.length ? `<div class="card-sub" style="margin-top:10px"><b>Formatting / parsing risks:</b></div><ul class="bullets">${data.formatting_issues.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>` : ""}
    </div>

    <div class="card">
      <div class="card-sub"><b>Matched keywords</b></div>
      <div class="kw-group">${matched || '<span class="card-sub">None detected</span>'}</div>
      <div class="card-sub" style="margin-top:10px"><b>Missing keywords</b></div>
      <div class="kw-group">${missing || '<span class="card-sub">None — great coverage</span>'}</div>
    </div>
  `;
}

function renderAtsOptimize(data) {
  const sections = data.rewritten_sections
    .map(
      (s) => `
      <div class="section-block">
        <h4>${escapeHtml(s.section)}</h4>
        <div class="reason">${escapeHtml(s.reason)}</div>
        <div class="diff">
          <div>
            <div class="diff-col-label">Before</div>
            <div class="diff-old">${escapeHtml(s.original)}</div>
          </div>
          <div>
            <div class="diff-col-label">After</div>
            <div class="diff-new">${escapeHtml(s.rewritten)}</div>
          </div>
        </div>
      </div>`
    )
    .join("");

  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <div class="card">
      <div class="summary-line">Projected ATS score after rewrite: ${data.projected_score}/100</div>
    </div>
    ${sections}
    <div class="section-block">
      <h4>Full rewritten resume (plain text)</h4>
      <div class="full-resume">${escapeHtml(data.full_rewritten_resume)}</div>
      <button class="btn ghost" style="margin-top:12px" onclick="downloadResume(this)">Download as .txt</button>
    </div>
  `;
  wrapper.querySelector(".full-resume").dataset.raw = data.full_rewritten_resume;
  return wrapper.outerHTML.replace(
    '<button class="btn ghost" style="margin-top:12px" onclick="downloadResume(this)">',
    `<button class="btn ghost" style="margin-top:12px" onclick="downloadResume(this)" data-resume="${encodeURIComponent(data.full_rewritten_resume)}">`
  );
}

window.downloadResume = function (btn) {
  const text = decodeURIComponent(btn.dataset.resume);
  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "optimized_resume.txt";
  a.click();
  URL.revokeObjectURL(url);
};
