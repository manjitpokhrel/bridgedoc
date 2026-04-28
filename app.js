
const state = {
  file: null,
  taskId: null,
  downloadUrl: null,
  downloadFilename: null,
  totalFiles: 0,
  totalSentences: 0,
};

const API_BASE = 'http://localhost:8000';


const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');

dropzone.addEventListener('click', () => fileInput.click());

dropzone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropzone.classList.add('drag-over');
});

dropzone.addEventListener('dragleave', () => {
  dropzone.classList.remove('drag-over');
});

dropzone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropzone.classList.remove('drag-over');
  const files = e.dataTransfer.files;
  if (files.length > 0) handleFile(files[0]);
});

fileInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) handleFile(e.target.files[0]);
});

function handleFile(file) {
  const allowed = ['.pdf', '.docx', '.csv', '.tsv'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();

  if (!allowed.includes(ext)) {
    showError('Unsupported file format. Please upload PDF, DOCX, CSV or TSV.');
    return;
  }

  if (file.size > 1024 * 1024) {
    showError(`File too large (${(file.size / 1024).toFixed(1)}KB). Maximum is 1MB.`);
    return;
  }

  state.file = file;

  const icons = { '.pdf': '📄', '.docx': '📝', '.csv': '📊', '.tsv': '📊' };
  document.getElementById('file-icon').textContent = icons[ext] || '📄';
  document.getElementById('file-name').textContent = file.name;
  document.getElementById('file-meta').textContent =
    `${(file.size / 1024).toFixed(1)} KB · ${ext.toUpperCase()}`;

  document.getElementById('dropzone-inner').style.display = 'none';
  document.getElementById('file-info').style.display = 'block';

  resetOutput();
}

function removeFile() {
  state.file = null;
  state.taskId = null;
  fileInput.value = '';
  document.getElementById('dropzone-inner').style.display = 'block';
  document.getElementById('file-info').style.display = 'none';
  resetOutput();
}

function togglePassword() {
  const input = document.getElementById('api-key');
  input.type = input.type === 'password' ? 'text' : 'password';
}

// ─── TRANSLATION ──────────────────────────────────────────────────────────────
async function startTranslation() {
  const apiKey = document.getElementById('api-key').value.trim();
  const direction = document.getElementById('direction').value;
  const qualityCheck = document.getElementById('quality-check').checked;

  if (!apiKey) { showError('Please enter your TMT API key.'); return; }
  if (!state.file) { showError('Please upload a document first.'); return; }

  setButtonLoading(true);
  showProgress();
  setStep('parse', 'loading');

  try {
    const formData = new FormData();
    formData.append('file', state.file);
    formData.append('direction', direction);
    formData.append('api_key', apiKey);
    formData.append('quality_check', qualityCheck);

    updateProgress(5, 'Sending file to server...');

    const response = await fetch(`${API_BASE}/translate`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Translation failed');
    }

    const taskData = await response.json();
    const taskId = taskData.task_id;
    state.taskId = taskId;

    console.log("Task ID received:", taskId);

    if (!taskId) {
      throw new Error("Server did not return a task ID.");
    }

    await pollProgress(taskId, qualityCheck);

  } catch (err) {
    showError(err.message || 'An unexpected error occurred.');
    setButtonLoading(false);
  }
}

async function pollProgress(taskId, qualityCheck) {
  const pollInterval = 800;

  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/status/${taskId}`);
        const data = await res.json();

        if (data.step === 'parsing') {
          setStep('parse', 'loading');
          updateProgress(data.progress, data.message, data.count);
        } else if (data.step === 'segmenting') {
          setStep('parse', 'done');
          setStep('segment', 'loading');
          updateProgress(data.progress, data.message, data.count);
        } else if (data.step === 'translating') {
          setStep('parse', 'done');
          setStep('segment', 'done');
          setStep('translate', 'loading');
          updateProgress(data.progress, data.message, data.count);
        } else if (data.step === 'rebuilding') {
          setStep('parse', 'done');
          setStep('segment', 'done');
          setStep('translate', 'done');
          setStep('rebuild', 'loading');
          updateProgress(data.progress, data.message, data.count);
        }

        if (data.status === 'complete') {
          setStep('parse', 'done');
          setStep('segment', 'done');
          setStep('translate', 'done');
          setStep('rebuild', 'done');
          updateProgress(100, 'Done!');
          showResult(data, qualityCheck);
          setButtonLoading(false);
          resolve();
        } else if (data.status === 'error') {
          throw new Error(data.message);
        } else {
          setTimeout(poll, pollInterval);
        }
      } catch (err) {
        showError(err.message);
        setButtonLoading(false);
        reject(err);
      }
    };

    poll();
  });
}

// ─── UI STATES ────────────────────────────────────────────────────────────────
function showProgress() {
  hide('idle-state');
  hide('result-state');
  hide('error-state');
  show('progress-state');
  resetSteps();
}

function showResult(data, qualityCheck) {
  hide('progress-state');
  show('result-state');

  const ext = state.file.name.split('.').pop().toUpperCase();
  const statsHtml = `
    ✅ <strong>Translation Complete!</strong><br/>
    📄 Format: ${ext}<br/>
    📊 Sentences processed: ${data.stats?.total_sentences ?? 'N/A'}<br/>
    ✓ Successfully translated: ${data.stats?.translated ?? 'N/A'}<br/>
    ⚠️ Kept original (failed): ${data.stats?.failed ?? 0}<br/>
    ${data.stats?.skipped_columns ? `⏭ Skipped columns: ${data.stats.skipped_columns.join(', ')}` : ''}
    ${data.stats?.warning ? `<br/>⚠️ ${data.stats.warning}` : ''}
  `;
  document.getElementById('result-stats').innerHTML = statsHtml;

  // Quality report
  if (qualityCheck && data.quality) {
    show('quality-report');
    const pct = Math.round(data.quality.average_score * 100);
    document.getElementById('quality-bar').style.width = pct + '%';
    document.getElementById('quality-pct').textContent = pct + '%';

    const flagged = data.quality.flagged_count;
    document.getElementById('quality-flags').textContent =
      flagged > 0
        ? `⚑ ${flagged} sentence(s) flagged for low confidence (score < 40%)`
        : '✓ All sentences passed quality threshold';
  } else {
    hide('quality-report');
  }

  // Download button — uses state.taskId
  const downloadBtn = document.getElementById('download-btn');
  downloadBtn.onclick = () => downloadFile(state.taskId, state.file.name);

  // Update session stats
  state.totalFiles += 1;
  state.totalSentences += data.stats?.total_sentences ?? 0;
  document.getElementById('stat-files').textContent = state.totalFiles;
  document.getElementById('stat-sentences').textContent = state.totalSentences;
}

function showError(message) {
  hide('idle-state');
  hide('progress-state');
  hide('result-state');
  show('error-state');
  document.getElementById('error-message').textContent = message;
  setButtonLoading(false);
}

function resetOutput() {
  hide('progress-state');
  hide('result-state');
  hide('error-state');
  show('idle-state');
}

function resetApp() {
  state.taskId = null;
  resetOutput();
}

// ─── PROGRESS HELPERS ─────────────────────────────────────────────────────────
function updateProgress(pct, label, count) {
  document.getElementById('progress-bar').style.width = pct + '%';
  document.getElementById('progress-label').textContent = label || '';
  document.getElementById('progress-count').textContent = count || '';
}

function setStep(stepName, status) {
  const statusEl = document.getElementById('status-' + stepName);
  if (!statusEl) return;
  const icons = { loading: '🔄', done: '✅', error: '❌', waiting: '⏳' };
  statusEl.textContent = icons[status] || '⏳';
}

function resetSteps() {
  ['parse', 'segment', 'translate', 'rebuild'].forEach(s => setStep(s, 'waiting'));
  updateProgress(0, 'Starting...');
}

// ─── DOWNLOAD ─────────────────────────────────────────────────────────────────
async function downloadFile(taskId, originalName) {
  if (!taskId) {
    alert('No task ID available. Please translate a document first.');
    return;
  }

  try {
    console.log("Downloading task:", taskId);

    const res = await fetch(`${API_BASE}/download/${taskId}`);

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Download failed with status ${res.status}`);
    }

    const blob = await res.blob();

    if (blob.size === 0) {
      throw new Error('Downloaded file is empty');
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'translated_' + originalName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log("Download complete:", blob.size, "bytes");

  } catch (err) {
    alert('Download failed: ' + err.message);
    console.error("Download error:", err);
  }
}

// ─── UTILS ────────────────────────────────────────────────────────────────────
function show(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'block';
}

function hide(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}

function setButtonLoading(loading) {
  const btn = document.getElementById('translate-btn');
  const text = document.getElementById('btn-text');
  const spinner = document.getElementById('btn-spinner');
  btn.disabled = loading;
  text.style.display = loading ? 'none' : 'inline';
  spinner.style.display = loading ? 'inline-block' : 'none';
}