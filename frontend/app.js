const API_BASE = "";

const form = document.getElementById("job-form");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const dzFilename = document.getElementById("dz-filename");
const dzText = dropzone.querySelector(".dz-text");
const submitBtn = document.getElementById("submit-btn");
const formCard = document.getElementById("form-card");
const progressCard = document.getElementById("progress-card");
const stepList = document.getElementById("step-list");
const resultBlock = document.getElementById("result-block");
const resultSuccess = document.getElementById("result-success");
const resultError = document.getElementById("result-error");
const errorDetail = document.getElementById("error-detail");
const downloadLink = document.getElementById("download-link");
const resetBtn = document.getElementById("reset-btn");

const STEP_ORDER = [
  ["ingestion", "Reading uploaded document"],
  ["classification", "Identifying company and report sections"],
  ["financial_table", "Extracting financial tables"],
  ["narrative", "Writing narrative and highlights"],
  ["chart_data", "Preparing chart data"],
  ["metrics", "Computing derived ratios"],
  ["reconciliation", "Reconciling figures against the source"],
  ["assembly", "Assembling report data"],
  ["render", "Rendering PDF"],
];

function setFile(file) {
  if (!file) return;
  dropzone.classList.add("has-file");
  dzText.hidden = true;
  dzFilename.hidden = false;
  dzFilename.textContent = file.name;
}

fileInput.addEventListener("change", () => setFile(fileInput.files[0]));

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
  if (file) {
    fileInput.files = e.dataTransfer.files;
    setFile(file);
  }
});

function buildStepList() {
  stepList.innerHTML = "";
  STEP_ORDER.forEach(([key, label], i) => {
    const li = document.createElement("li");
    li.className = "step-item pending";
    li.dataset.step = key;
    li.style.animationDelay = `${i * 40}ms`;
    li.innerHTML = `<div class="step-dot"></div><div class="step-label">${label}</div><div class="step-detail"></div>`;
    stepList.appendChild(li);
  });
}

function updateStep(step, status, detail) {
  const li = stepList.querySelector(`[data-step="${step}"]`);
  if (!li) return;
  li.classList.remove("pending", "running", "done", "failed");
  li.classList.add(status);
  const dot = li.querySelector(".step-dot");
  dot.textContent = status === "done" ? "✓" : status === "failed" ? "!" : "";
  li.querySelector(".step-detail").textContent = detail || "";
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const companyName = document.getElementById("company-name").value.trim();
  const file = fileInput.files[0];
  if (!companyName) {
    document.getElementById("company-name").focus();
    return;
  }
  if (!file) {
    dropzone.classList.add("drag-over");
    setTimeout(() => dropzone.classList.remove("drag-over"), 400);
    return;
  }

  submitBtn.disabled = true;

  const fd = new FormData();
  fd.append("company_name", companyName);
  fd.append("file", file);

  let jobId;
  try {
    const res = await fetch(`${API_BASE}/api/jobs`, { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
    jobId = (await res.json()).job_id;
  } catch (err) {
    submitBtn.disabled = false;
    alert(err.message);
    return;
  }

  formCard.hidden = true;
  progressCard.hidden = false;
  buildStepList();

  const es = new EventSource(`${API_BASE}/api/jobs/${jobId}/events`);
  es.onmessage = (msg) => {
    const event = JSON.parse(msg.data);
    if (event.step === "_complete") {
      es.close();
      resultBlock.hidden = false;
      resultSuccess.hidden = false;
      downloadLink.href = `${API_BASE}/api/jobs/${jobId}/download`;
      resetBtn.hidden = false;
      return;
    }
    if (event.step === "_error") {
      es.close();
      resultBlock.hidden = false;
      resultError.hidden = false;
      errorDetail.textContent = event.detail || "Unknown error";
      resetBtn.hidden = false;
      return;
    }
    updateStep(event.step, event.status, event.detail);
  };
  es.onerror = () => {
    // EventSource auto-retries; nothing to do here beyond letting it reconnect.
  };
});

resetBtn.addEventListener("click", () => {
  form.reset();
  dropzone.classList.remove("has-file");
  dzText.hidden = false;
  dzFilename.hidden = true;
  submitBtn.disabled = false;
  progressCard.hidden = true;
  resultBlock.hidden = true;
  resultSuccess.hidden = true;
  resultError.hidden = true;
  formCard.hidden = false;
});
