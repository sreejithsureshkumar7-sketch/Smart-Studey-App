const API_BASE = "";

const params = new URLSearchParams(window.location.search);
const docId = params.get("doc_id");

const docTitle = document.getElementById("docTitle");
const emptyState = document.getElementById("emptyState");
const dashboardContent = document.getElementById("dashboardContent");
const overallAccuracy = document.getElementById("overallAccuracy");
const quizzesTaken = document.getElementById("quizzesTaken");
const weakCount = document.getElementById("weakCount");
const topicBars = document.getElementById("topicBars");
const examDateInput = document.getElementById("examDateInput");
const generatePlanBtn = document.getElementById("generatePlanBtn");
const planOutput = document.getElementById("planOutput");
const goTakeQuiz = document.getElementById("goTakeQuiz");
const navQuiz = document.getElementById("navQuiz");

let historyChart = null;

if (navQuiz) navQuiz.href = `quiz.html?doc_id=${docId}`;
if (goTakeQuiz) goTakeQuiz.href = `quiz.html?doc_id=${docId}`;

// default exam date input to 7 days from now
const defaultDate = new Date();
defaultDate.setDate(defaultDate.getDate() + 7);
examDateInput.value = defaultDate.toISOString().split("T")[0];

async function loadDashboard() {
  if (!docId) {
    dashboardContent.innerHTML = `<p style="color:#C1502E;">No document selected.</p>`;
    dashboardContent.classList.remove("hidden");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/dashboard/${docId}`);
    const data = await res.json();

    if (!res.ok) {
      dashboardContent.innerHTML = `<p style="color:#C1502E;">${data.error}</p>`;
      dashboardContent.classList.remove("hidden");
      return;
    }

    docTitle.textContent = `Progress — ${data.document.filename}`;

    const hasAttempts = data.attempt_history.length > 0;
    if (!hasAttempts) {
      emptyState.classList.remove("hidden");
      return;
    }

    dashboardContent.classList.remove("hidden");
    renderStats(data);
    renderTopicBars(data.topic_stats);
    renderHistoryChart(data.attempt_history);
  } catch (err) {
    dashboardContent.innerHTML = `<p style="color:#C1502E;">Network error: ${err.message}</p>`;
    dashboardContent.classList.remove("hidden");
  }
}

function renderStats(data) {
  overallAccuracy.textContent = `${data.analysis.overall_accuracy}%`;
  quizzesTaken.textContent = data.attempt_history.length;
  weakCount.textContent = data.analysis.weak.length;
}

function renderTopicBars(topicStats) {
  const entries = Object.entries(topicStats).sort((a, b) => a[1].accuracy - b[1].accuracy);

  topicBars.innerHTML = entries
    .map(([topic, stats]) => {
      const isWeak = stats.accuracy < 60;
      return `
      <div class="topic-bar-row">
        <div class="name">${escapeHtml(topic)}</div>
        <div class="topic-bar-track">
          <div class="topic-bar-fill ${isWeak ? "weak" : "strong"}" style="width:${stats.accuracy}%"></div>
        </div>
        <div class="pct">${stats.accuracy}%</div>
      </div>
    `;
    })
    .join("");
}

function renderHistoryChart(history) {
  const ctx = document.getElementById("historyChart").getContext("2d");
  const labels = history.map((h, i) => `Attempt ${i + 1}`);
  const scores = history.map((h) => Math.round((h.score / h.total) * 100));

  if (historyChart) historyChart.destroy();
  historyChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Score %",
          data: scores,
          borderColor: "#2C5F6F",
          backgroundColor: "rgba(44, 95, 111, 0.12)",
          fill: true,
          tension: 0.25,
          pointBackgroundColor: "#2C5F6F",
        },
      ],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: { y: { min: 0, max: 100, ticks: { callback: (v) => v + "%" } } },
    },
  });
}

generatePlanBtn.addEventListener("click", async () => {
  generatePlanBtn.disabled = true;
  generatePlanBtn.textContent = "Building plan…";
  planOutput.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE}/api/study-plan/${docId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exam_date: examDateInput.value }),
    });
    const data = await res.json();

    if (!res.ok) {
      planOutput.innerHTML = `<p style="color:#C1502E;">${data.error}</p>`;
      return;
    }

    renderPlan(data);
  } catch (err) {
    planOutput.innerHTML = `<p style="color:#C1502E;">Network error: ${err.message}</p>`;
  } finally {
    generatePlanBtn.disabled = false;
    generatePlanBtn.textContent = "Generate plan";
  }
});

function renderPlan(plan) {
  const daysHtml = (plan.days || [])
    .map(
      (d) => `
    <div class="plan-day">
      <h3>${escapeHtml(d.day)} <span style="font-weight:400; font-size:0.8rem; color:#5B6169;">(${d.duration_minutes || 60} min)</span></h3>
      <div class="focus">Focus: ${(d.focus_topics || []).map(escapeHtml).join(", ")}</div>
      <ul>${(d.tasks || []).map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ul>
    </div>
  `
    )
    .join("");

  const tipsHtml = (plan.tips || []).length
    ? `<h3>Tips</h3><ul>${plan.tips.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ul>`
    : "";

  planOutput.innerHTML = `
    <p style="margin-bottom:16px;">${plan.days_until_exam} day(s) until your exam.</p>
    ${daysHtml}
    ${tipsHtml}
  `;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

loadDashboard();
