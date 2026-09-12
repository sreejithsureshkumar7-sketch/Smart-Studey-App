const API_BASE = ""; // same-origin; change if backend runs on a different host

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const chooseFileBtn = document.getElementById("chooseFileBtn");
const fileNameEl = document.getElementById("fileName");
const uploadStatus = document.getElementById("uploadStatus");
const uploadCard = document.getElementById("uploadCard");
const summaryCard = document.getElementById("summaryCard");
const summaryText = document.getElementById("summaryText");
const goQuizBtn = document.getElementById("goQuizBtn");
const uploadAnotherBtn = document.getElementById("uploadAnotherBtn");
const navQuiz = document.getElementById("navQuiz");
const navDashboard = document.getElementById("navDashboard");

let currentDocId = null;

chooseFileBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) handleFile(fileInput.files[0]);
});

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  })
);

["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
  })
);

dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

uploadAnotherBtn.addEventListener("click", () => {
  summaryCard.classList.add("hidden");
  uploadCard.classList.remove("hidden");
  uploadStatus.innerHTML = "";
  fileNameEl.textContent = "";
});

async function handleFile(file) {
  if (file.type !== "application/pdf") {
    uploadStatus.innerHTML = `<p style="color:#C1502E;">Please choose a PDF file.</p>`;
    return;
  }

  fileNameEl.textContent = file.name;
  uploadStatus.innerHTML = `<p>Uploading and reading your PDF… this can take a moment.</p>`;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/api/upload`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();

    if (!res.ok) {
      uploadStatus.innerHTML = `<p style="color:#C1502E;">${data.error || "Upload failed"}</p>`;
      return;
    }

    currentDocId = data.doc_id;
    uploadStatus.innerHTML = "";
    summaryText.textContent = data.summary;
    uploadCard.classList.add("hidden");
    summaryCard.classList.remove("hidden");

    goQuizBtn.href = `quiz.html?doc_id=${currentDocId}`;
    navQuiz.href = `quiz.html?doc_id=${currentDocId}`;
    navDashboard.href = `dashboard.html?doc_id=${currentDocId}`;
  } catch (err) {
    uploadStatus.innerHTML = `<p style="color:#C1502E;">Network error: ${err.message}</p>`;
  }
}
