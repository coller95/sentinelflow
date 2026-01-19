const addClusterLabelEl = document.getElementById('addClusterLabel');
const addClusterBaseUrlEl = document.getElementById('addClusterBaseUrl');
const btnAddClusterEl = document.getElementById('btnAddCluster');
const btnDashboardRefreshEl = document.getElementById('btnDashboardRefresh');
const cctvGridEl = document.getElementById('cctvGrid');

const manageStatusEl = document.getElementById('manageStatus');

function _setManageStatus(text) {
  if (!manageStatusEl) return;
  manageStatusEl.textContent = String(text ?? '');
}

function _pretty(obj) {
  try {
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(obj ?? '');
  }
}

function _fillTextArea(el, obj) {
  if (!el) return;
  el.value = _pretty(obj);
}

function _fillSelect(el, items, valueKey, labelKey, selectedValue) {
  if (!el) return;
  el.textContent = '';
  const safeItems = Array.isArray(items) ? items : [];

  if (safeItems.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '(none)';
    el.appendChild(opt);
    return;
  }

  for (const it of safeItems) {
    const opt = document.createElement('option');
    opt.value = String(it?.[valueKey] ?? '');
    opt.textContent = String(it?.[labelKey] ?? it?.[valueKey] ?? '');
    el.appendChild(opt);
  }
  if (selectedValue) {
    el.value = String(selectedValue);
  }
}

function _serverUuidOf(cluster) {
  return String(cluster?.uuid ?? '').trim();
}

function _isDuplicateCluster(cluster) {
  const su = _serverUuidOf(cluster);
  if (!su) return false;
  return (_dupCountByServerUuid.get(su) || 0) > 1;
}

function _clusterLabel(cluster) {
  return String(cluster?.label ?? cluster?.uuid ?? '').trim() || 'Cluster';
}

async function dashboardRefresh() {
  _setManageStatus('Refreshing dashboard...');
  await refreshClusters();
  _setManageStatus('Dashboard updated.');
}

function _tryParseJson(raw) {
  const text = String(raw || '').trim();
  if (!text) return null;
  return JSON.parse(text);
}

function _setPreviewLines(el, lines) {
  if (!el) return;
  el.value = Array.isArray(lines) ? lines.join('\n') : '';
}

function _floatFromInput(el, fallback = 0) {
  const raw = String(el?.value || '').trim();
  if (!raw) return fallback;
  const n = Number(raw);
  return Number.isFinite(n) ? n : fallback;
}

async function _loadAppDefaultsForCluster(cluster, inputs) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu || !cluster?.baseUrl || _isDuplicateCluster(cluster)) return;

  const cached = _appDefaultsCache.get(cu);
  if (cached) {
    _applyAppDefaultsToInputs(cached, inputs);
    return;
  }

  try {
    const data = await _getJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/app/defaults`);
    if (data && typeof data === 'object') {
      _appDefaultsCache.set(cu, data);
      _applyAppDefaultsToInputs(data, inputs);
    }
  } catch (err) {
    // Best-effort; defaults are optional.
    console.warn(`Defaults unavailable for ${_clusterLabel(cluster)}:`, err);
  }
}

function _applyAppDefaultsToInputs(data, inputs) {
  if (!data || typeof data !== 'object' || !inputs) return;
  const appPath = String(data.defaultAppPath ?? data.appPath ?? data.path ?? '');
  const windowTitle = String(data.defaultWindowTitle ?? data.programName ?? data.windowTitle ?? '');
  const left = data.defaultWindowLeft ?? data.left;
  const top = data.defaultWindowTop ?? data.top;
  const width = data.defaultWindowWidth ?? data.width;
  const height = data.defaultWindowHeight ?? data.height;

  if (inputs.appPathEl) inputs.appPathEl.value = appPath;
  if (inputs.titleEl) inputs.titleEl.value = windowTitle;
  if (inputs.leftEl && Number.isFinite(Number(left))) inputs.leftEl.value = String(Math.floor(Number(left)));
  if (inputs.topEl && Number.isFinite(Number(top))) inputs.topEl.value = String(Math.floor(Number(top)));
  if (inputs.widthEl && Number.isFinite(Number(width))) inputs.widthEl.value = String(Math.floor(Number(width)));
  if (inputs.heightEl && Number.isFinite(Number(height))) inputs.heightEl.value = String(Math.floor(Number(height)));
}

function _numOrDefault(el, d) {
  const raw = String(el?.value ?? '').trim();
  if (!raw) return d;
  const n = Number(raw);
  return Number.isFinite(n) ? Math.floor(n) : d;
}

function _defaultGeometryPayload() {
  return { left: 0, top: 0, width: 640, height: 480 };
}

function _geometryPayloadFromInputs(leftEl, topEl, widthEl, heightEl) {
  return {
    left: _numOrDefault(leftEl, 0),
    top: _numOrDefault(topEl, 0),
    width: _numOrDefault(widthEl, 640),
    height: _numOrDefault(heightEl, 480),
  };
}

async function refreshClusters() {
  _setManageStatus('Loading clusters...');
  try {
    const resp = await _getJson('/api/orchestrator/clusters');
    const clusters = resp && Array.isArray(resp.clusters) ? resp.clusters : [];
    _cachedClusters = clusters;
    _dupCountByServerUuid = new Map();
    _appDefaultsCache = new Map();
    _appStatusCache = new Map();
    for (const c of clusters) {
      const su = _serverUuidOf(c);
      if (!su) continue;
      _dupCountByServerUuid.set(su, (_dupCountByServerUuid.get(su) || 0) + 1);
    }
    if (typeof _ensureCctvCards === 'function') {
      _ensureCctvCards();
    }
    _setManageStatus('Ready.');
  } catch (err) {
    _setManageStatus(`Failed to load clusters: ${err?.message ?? err}`);
  }
}

async function commissionCluster() {
  const label = String(addClusterLabelEl?.value || '').trim();
  const baseUrl = String(addClusterBaseUrlEl?.value || '').trim();

  if (!baseUrl) {
    _setManageStatus('Cluster address is required (IP:port or http://host:port).');
    return;
  }

  _setManageStatus('Registering cluster...');

  const payload = { baseUrl, label: label ? label : null };

  try {
    const result = await _postJson('/api/orchestrator/clusters/commission_from_url', payload);
    const cluster = result && result.cluster ? result.cluster : null;
    if (cluster && cluster.uuid) {
      _setManageStatus(`Registered: ${cluster.label} (${cluster.uuid}).`);
    } else {
      _setManageStatus('Registered.');
    }
    await refreshClusters();
  } catch (err) {
    _setManageStatus(`Register failed: ${err?.message ?? err}`);
  }
}

if (btnAddClusterEl) {
  btnAddClusterEl.addEventListener('click', () => {
    commissionCluster();
  });
}

if (btnDashboardRefreshEl) {
  btnDashboardRefreshEl.addEventListener('click', () => {
    dashboardRefresh();
  });
}

for (const el of [addClusterLabelEl, addClusterBaseUrlEl]) {
  if (!el) continue;
  el.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      commissionCluster();
    }
  });
}

dashboardRefresh();
_setManageStatus('Ready.');
