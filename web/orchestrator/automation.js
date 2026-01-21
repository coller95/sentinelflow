const _automationStorageKey = 'automation.previewClusterUuid';
let _previewCaptureClusterUuid = '';

function _setClusterContext(clusterUuid) {
  const clean = String(clusterUuid || '').trim();
  globalThis.AUTOMATION_CLUSTER_UUID = clean;
  globalThis.APP_API_BASE = clean ? `/api/orchestrator/clusters/${encodeURIComponent(clean)}` : '';
}

function _hasLauncherUi() {
  return !!(appPathEl || windowTitleEl || btnLaunch || btnAttach || appAttachStatusEl);
}

function _isTabActive(tabName) {
  const tab = document.querySelector(`.controlTabs button[data-tab="${tabName}"]`);
  return !!(tab && tab.classList.contains('active'));
}

function _clearLivePreview() {
  if (typeof stopEventSource === 'function') stopEventSource();
  if (captureImage) captureImage.removeAttribute('src');
}

async function _postJson(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : '{}',
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    // ignore
  }
  if (!res.ok) {
    const detail = (data && (data.detail || data.message)) ? (data.detail || data.message) : text;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return data;
}

async function _startPreviewCapture(clusterUuid) {
  const cu = String(clusterUuid || '').trim();
  if (!cu) return;
  await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/capture/start`, { intervalSeconds: 0.5 });
}

async function _stopPreviewCapture(clusterUuid) {
  const cu = String(clusterUuid || '').trim();
  if (!cu) return;
  await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/capture/stop`, {});
}

async function _switchPreviewCluster(nextUuid) {
  const next = String(nextUuid || '').trim();
  // We no longer stop capture on the previous cluster because other clients (or the CCTV grid) might be watching.
  // The backend capture is cheap to keep running.
  
  _previewCaptureClusterUuid = next;
  _setClusterContext(next);
  _clearLivePreview();
  if (typeof setAppAttached === 'function' && _hasLauncherUi()) setAppAttached(false);

  if (next) {
    try {
      // Ensure capture is running on the target (idempotent)
      await _startPreviewCapture(next);
      if (typeof startEventSource === 'function') startEventSource();
    } catch (err) {
      setStatus(`Start capture failed: ${err?.message ?? err}`, 'err');
    }
  }

  if (_isTabActive('conditions')) {
    if (typeof stopConditionsEventSource === 'function') stopConditionsEventSource();
    if (typeof startConditionsEventSource === 'function') startConditionsEventSource();
  }

  if (_isTabActive('triggerStatus')) {
    if (typeof stopTriggerStatusSse === 'function') stopTriggerStatusSse();
    if (typeof startTriggerStatusSse === 'function') startTriggerStatusSse();
  }

  if (typeof refreshConditions === 'function') {
    refreshConditions().catch(() => {});
  }
  if (typeof loadSelectedConditionIntoEditor === 'function') {
    loadSelectedConditionIntoEditor().catch(() => {});
  }
  if (_hasLauncherUi()) {
    if (typeof refreshAppStatus === 'function') {
      refreshAppStatus().catch(() => {});
    }
    if (typeof tryLoadAppDefaults === 'function') {
      tryLoadAppDefaults();
    }
  }
}

async function _loadPreviewClusters() {
  const select = document.getElementById('previewCluster');
  if (!select) return;
  select.textContent = '';

  const noneOpt = document.createElement('option');
  noneOpt.value = '';
  noneOpt.textContent = 'No live preview';
  select.appendChild(noneOpt);

  let clusters = [];
  try {
    const res = await fetch('/api/orchestrator/clusters');
    const data = await res.json();
    clusters = Array.isArray(data?.clusters) ? data.clusters : [];
  } catch (err) {
    setStatus(`Failed to load clusters: ${err?.message ?? err}`, 'err');
  }

  for (const c of clusters) {
    const uuid = String(c?.uuid ?? '').trim();
    if (!uuid) continue;
    const label = String(c?.label ?? uuid).trim();
    const base = String(c?.baseUrl ?? '').trim();
    const opt = document.createElement('option');
    opt.value = uuid;
    opt.textContent = base ? `${label} (${base})` : label;
    select.appendChild(opt);
  }

  const saved = String(localStorage.getItem(_automationStorageKey) || '').trim();
  if (saved && select.querySelector(`option[value="${saved}"]`)) {
    select.value = saved;
  } else {
    select.value = '';
    if (saved) localStorage.removeItem(_automationStorageKey);
  }

  await _switchPreviewCluster(select.value);

  select.addEventListener('change', () => {
    const value = String(select.value || '').trim();
    if (value) {
      localStorage.setItem(_automationStorageKey, value);
    } else {
      localStorage.removeItem(_automationStorageKey);
    }
    _switchPreviewCluster(value).catch(() => {});
  });
}

document.addEventListener('DOMContentLoaded', () => {
  _loadPreviewClusters().catch(() => {});
});

// Remove beforeunload stop listener to prevent killing capture for other users
// window.addEventListener('beforeunload', () => { ... });
