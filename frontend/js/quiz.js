const API_BASE = "";

const params = new URLSearchParams(window.location.search);
const docId = params.get("doc_id");

const loadingState = document.getElementById("loadingState");
const quizForm = document.getElementById("quizForm");
const quizProgress = document.getElementById("quizProgress");
const questionsContainer = document.getElementById("questionsContainer");
const resultsCard = document.getElementById("resultsCard");
const scoreText = document.getElementById("scoreText");
const feedbackList = document.getElementById("feedbackList");
const goDashboardBtn = document.getElementById("goDashboardBtn");
const navDashboard = document.getElementById("navDashboard");

let currentQuizId = null;
let currentQuestions = [];

if (navDashboard) navDashboard.href = `dashboard.html?doc_id=${docId}`;
goDashboardBtn.href = `dashboard.html?doc_id=${docId}`;

async function loadQuiz() {
  if (!docId) {
    loadingState.innerHTML = `<p style="color:#C1502E;">No document selected. Go back and upload a PDF first.</p>`;
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/generate-quiz/${docId}?count=5`);
    const data = await res.json();

    if (!res.ok) {
      loadingState.innerHTML = `<p style="color:#C1502E;">${data.error || "Could not generate quiz"}</p>`;
      return;
    }

    currentQuizId = data.quiz_id;
    currentQuestions = data.questions;
    renderQuiz();
  } catch (err) {
    loadingState.innerHTML = `<p style="color:#C1502E;">Network error: ${err.message}</p>`;
  }
}

function renderQuiz() {
  quizProgress.textContent = `${currentQuestions.length} questions`;
  questionsContainer.innerHTML = currentQuestions
    .map(
      (q, idx) => `
    <div class="question-block">
      <div class="q-topic">${escapeHtml(q.topic)}</div>
      <div class="q-text">${idx + 1}. ${escapeHtml(q.question)}</div>
      ${q.options
        .map(
          (opt, i) => `
        <label class="option" data-question="${q.id}" data-value="${escapeAttr(opt)}">
          <input type="radio" name="q_${q.id}" value="${escapeAttr(opt)}" />
          <span>${escapeHtml(opt)}</span>
        </label>
      `
        )
        .join("")}
    </div>
  `
    )
    .join("");

  // highlight selection
  questionsContainer.querySelectorAll(".option").forEach((optEl) => {
    optEl.addEventListener("click", () => {
      const qid = optEl.dataset.question;
      questionsContainer
        .querySelectorAll(`.option[data-question="${qid}"]`)
        .forEach((el) => el.classList.remove("selected"));
      optEl.classList.add("selected");
      optEl.querySelector("input").checked = true;
    });
  });

  loadingState.classList.add("hidden");
  quizForm.classList.remove("hidden");
}

quizForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const answers = currentQuestions.map((q) => {
    const checked = quizForm.querySelector(`input[name="q_${q.id}"]:checked`);
    return { question_id: q.id, selected: checked ? checked.value : null };
  });

  const submitBtn = document.getElementById("submitQuizBtn");
  submitBtn.disabled = true;
  submitBtn.textContent = "Submitting…";

  try {
    const res = await fetch(`${API_BASE}/api/submit-quiz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quiz_id: currentQuizId, doc_id: Number(docId), answers }),
    });
    const data = await res.json();

    if (!res.ok) {
      alert(data.error || "Submission failed");
      submitBtn.disabled = false;
      submitBtn.textContent = "Submit answers";
      return;
    }

    showResults(data);
  } catch (err) {
    alert("Network error: " + err.message);
    submitBtn.disabled = false;
    submitBtn.textContent = "Submit answers";
  }
});

function showResults(data) {
  quizForm.classList.add("hidden");
  resultsCard.classList.remove("hidden");
  scoreText.textContent = `You scored ${data.score} out of ${data.total}.`;

  feedbackList.innerHTML = data.feedback
    .map((f) => {
      const q = currentQuestions.find((q) => q.id === f.question_id);
      return `
      <div class="question-block">
        <div class="q-topic">${escapeHtml(f.topic)}</div>
        <div class="q-text">${escapeHtml(q ? q.question : "")}</div>
        <div class="option ${f.is_correct ? "correct" : "incorrect"}">
          Your answer: ${escapeHtml(f.selected || "(no answer)")}
        </div>
        ${!f.is_correct ? `<div class="option correct">Correct answer: ${escapeHtml(f.correct)}</div>` : ""}
      </div>
    `;
    })
    .join("");
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function escapeAttr(str) {
  return escapeHtml(str).replace(/"/g, "&quot;");
}

loadQuiz();
