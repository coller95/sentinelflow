const addClusterLabelEl = document.getElementById('addClusterLabel');
const addClusterBaseUrlEl = document.getElementById('addClusterBaseUrl');
const btnAddClusterEl = document.getElementById('btnAddCluster');
const btnDashboardRefreshEl = document.getElementById('btnDashboardRefresh');
const cctvGridEl = document.getElementById('cctvGrid');

const manageStatusEl = document.getElementById('manageStatus');

const btnActionsFetchEl = document.getElementById('btnActionsFetch');
const actionsListEl = document.getElementById('actionsList');
const actionsSelectEl = document.getElementById('actionsSelect');
const actionRunUuidEl = document.getElementById('actionRunUuid');
const btnActionRunEl = document.getElementById('btnActionRun');
const btnActionRemoveEl = document.getElementById('btnActionRemove');
const actionUpsertBodyEl = document.getElementById('actionUpsertBody');
const btnActionUpsertEl = document.getElementById('btnActionUpsert');

const btnConditionsFetchEl = document.getElementById('btnConditionsFetch');
const btnConditionsStatusEl = document.getElementById('btnConditionsStatus');
const conditionsListEl = document.getElementById('conditionsList');
const conditionsSelectEl = document.getElementById('conditionsSelect');
const conditionsOpEl = document.getElementById('conditionsOp');
const conditionsBodyEl = document.getElementById('conditionsBody');
const btnConditionsSendEl = document.getElementById('btnConditionsSend');

const btnTriggersFetchEl = document.getElementById('btnTriggersFetch');
const btnTriggersStatusEl = document.getElementById('btnTriggersStatus');
const triggersListEl = document.getElementById('triggersList');
const triggersSelectEl = document.getElementById('triggersSelect');
const triggerEnabledEl = document.getElementById('triggerEnabled');
const btnTriggerApplyEnabledEl = document.getElementById('btnTriggerApplyEnabled');
const btnTriggerRemoveEl = document.getElementById('btnTriggerRemove');
const triggersOpEl = document.getElementById('triggersOp');
const triggersBodyEl = document.getElementById('triggersBody');
const btnTriggersSendEl = document.getElementById('btnTriggersSend');

const btnConfigsFetchEl = document.getElementById('btnConfigsFetch');
const btnAssignmentsFetchEl = document.getElementById('btnAssignmentsFetch');
const configsSelectEl = document.getElementById('configsSelect');
const configsListEl = document.getElementById('configsList');
const configNameEl = document.getElementById('configName');
const configDescriptionEl = document.getElementById('configDescription');
const configTagsEl = document.getElementById('configTags');
const configContentEl = document.getElementById('configContent');
const btnConfigCreateEl = document.getElementById('btnConfigCreate');
const btnConfigUpdateEl = document.getElementById('btnConfigUpdate');
const btnConfigRemoveEl = document.getElementById('btnConfigRemove');
const btnConfigSnapshotEl = document.getElementById('btnConfigSnapshot');
const configApplyTargetsEl = document.getElementById('configApplyTargets');
const configApplyDryRunEl = document.getElementById('configApplyDryRun');
const btnConfigApplyEl = document.getElementById('btnConfigApply');
const configAssignmentsEl = document.getElementById('configAssignments');

const btnScreensLayoutsFetchEl = document.getElementById('btnScreensLayoutsFetch');
const btnScreensAssignmentsFetchEl = document.getElementById('btnScreensAssignmentsFetch');
const screensLayoutSelectEl = document.getElementById('screensLayoutSelect');
const screensLayoutsListEl = document.getElementById('screensLayoutsList');
const screenLayoutNameEl = document.getElementById('screenLayoutName');
const screenLayoutDescriptionEl = document.getElementById('screenLayoutDescription');
const screenLayoutScreensEl = document.getElementById('screenLayoutScreens');
const btnScreenLayoutCreateEl = document.getElementById('btnScreenLayoutCreate');
const btnScreenLayoutUpdateEl = document.getElementById('btnScreenLayoutUpdate');
const btnScreenLayoutRemoveEl = document.getElementById('btnScreenLayoutRemove');
const screenAssignClusterEl = document.getElementById('screenAssignCluster');
const screenAssignLabelEl = document.getElementById('screenAssignLabel');
const screenAssignHintEl = document.getElementById('screenAssignHint');
const btnScreenAssignEl = document.getElementById('btnScreenAssign');
const btnScreenUnassignEl = document.getElementById('btnScreenUnassign');
const screenApplyTargetsEl = document.getElementById('screenApplyTargets');
const screenApplyWindowTitleEl = document.getElementById('screenApplyWindowTitle');
const screenApplyAllEl = document.getElementById('screenApplyAll');
const screenApplyDryRunEl = document.getElementById('screenApplyDryRun');
const btnScreenApplyEl = document.getElementById('btnScreenApply');
const screenAssignmentsEl = document.getElementById('screenAssignments');

let _cachedClusters = [];
let _cachedActions = [];
let _cachedConditions = [];
let _cachedTriggers = [];
let _cachedConfigs = [];
let _cachedLayouts = [];
let _dupCountByServerUuid = new Map();
let _cctvCards = new Map();
let _cctvLayoutKey = '';
let _cctvStreams = new Map();
let _appDefaultsCache = new Map();

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

async function _getJson(url) {
  const res = await fetch(url, { method: 'GET' });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const detail = data && typeof data === 'object' ? (data.detail ?? null) : null;
    throw new Error(detail ? String(detail) : `HTTP ${res.status}`);
  }
  return data;
}

async function _postJson(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!res.ok) {
    const detail = data && typeof data === 'object' ? (data.detail ?? null) : null;
    throw new Error(detail ? String(detail) : `HTTP ${res.status}`);
  }

  return data;
}

function _selectedClusterUuid() {
  return null;
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

function _findByUuid(items, uuid) {
  const u = String(uuid || '');
  return (Array.isArray(items) ? items : []).find(x => String(x?.uuid ?? '') === u) || null;
}

function _parseJsonFromTextArea(el) {
  const raw = String(el?.value || '').trim();
  if (!raw) return null;
  return JSON.parse(raw);
}

function _parseTagsInput(raw) {
  return String(raw || '')
    .split(',')
    .map(s => s.trim())
    .filter(s => s.length > 0);
}

function _tagsToString(tags) {
  return (Array.isArray(tags) ? tags : []).map(s => String(s || '').trim()).filter(Boolean).join(', ');
}

function _parseUuidList(raw) {
  const items = String(raw || '').split(/[\s,]+/);
  const out = [];
  const seen = new Set();
  for (const item of items) {
    const v = String(item || '').trim();
    if (!v || seen.has(v)) continue;
    out.push(v);
    seen.add(v);
  }
  return out;
}

function _fmtClusterMeta(c) {
  if (!c) return '';
  const label = c.label ? String(c.label) : '';
  const uuid = c.uuid ? String(c.uuid) : '';
  const serverUuid = c.serverUuid ? String(c.serverUuid) : '';
  const baseUrl = c.baseUrl ? String(c.baseUrl) : '';
  const dupCount = _dupCountByServerUuid.get(serverUuid || uuid) || 0;
  const dupTag = dupCount > 1 ? ` | DUPLICATE x${dupCount}` : '';
  return `${label} | ${uuid}${serverUuid ? ` | ${serverUuid}` : ''}${baseUrl ? ` | ${baseUrl}` : ''}${dupTag}`;
}

function _serverUuidOf(cluster) {
  return String(cluster?.serverUuid ?? cluster?.uuid ?? '').trim();
}

function _isDuplicateCluster(cluster) {
  const su = _serverUuidOf(cluster);
  if (!su) return false;
  return (_dupCountByServerUuid.get(su) || 0) > 1;
}

function _shortenText(text, maxLen = 120) {
  const raw = String(text ?? '');
  if (!raw || raw.length <= maxLen) return raw;
  return `${raw.slice(0, maxLen - 3)}...`;
}

function _clusterLabel(cluster) {
  return String(cluster?.label ?? cluster?.uuid ?? '').trim() || 'Cluster';
}

async function _appLaunchCluster(cluster, appPath, geometry) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate server UUID detected.');
  const app_path = String(appPath || '').trim();
  if (!app_path) return _setManageStatus('App path is required.');
  const payload = geometry || _defaultGeometryPayload();
  _setManageStatus(`Launching app on ${_clusterLabel(cluster)}...`);
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/app/launch', { app_path, ...payload });
    _setManageStatus(`App launched on ${_clusterLabel(cluster)}.`);
  } catch (err) {
    _setManageStatus(`Launch failed: ${err?.message ?? err}`);
  }
}

async function _appAttachCluster(cluster, windowTitle, geometry) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate server UUID detected.');
  const window_title = String(windowTitle || '').trim();
  if (!window_title) return _setManageStatus('Window title is required.');
  const payload = geometry || _defaultGeometryPayload();
  _setManageStatus(`Attaching app on ${_clusterLabel(cluster)}...`);
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/app/attach', { window_title, ...payload });
    _setManageStatus(`App attached on ${_clusterLabel(cluster)}.`);
  } catch (err) {
    _setManageStatus(`Attach failed: ${err?.message ?? err}`);
  }
}

async function _appCloseCluster(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate server UUID detected.');
  _setManageStatus(`Closing app on ${_clusterLabel(cluster)}...`);
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/app/close`, {});
    _setManageStatus(`App closed on ${_clusterLabel(cluster)}.`);
  } catch (err) {
    _setManageStatus(`Close failed: ${err?.message ?? err}`);
  }
}

async function _removeCluster(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return;
  if (!confirm(`Remove cluster ${_clusterLabel(cluster)} (${cu})?`)) return;
  _setManageStatus(`Removing ${_clusterLabel(cluster)}...`);
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/remove`, {});
    _closeCctvStream(cu);
    _setManageStatus(`Removed ${_clusterLabel(cluster)}.`);
    await refreshClusters();
  } catch (err) {
    _setManageStatus(`Remove failed: ${err?.message ?? err}`);
  }
}

async function dashboardRefresh() {
  _setManageStatus('Refreshing dashboard...');
  await refreshClusters();
  _setManageStatus('Dashboard updated.');
}

function _cctvPillInfo(state) {
  switch (state) {
    case 'live':
      return { text: 'live', cls: 'ok' };
    case 'stopped':
      return { text: 'stopped', cls: 'warn' };
    case 'no-url':
      return { text: 'no url', cls: 'warn' };
    case 'duplicate':
      return { text: 'duplicate', cls: 'warn' };
    case 'offline':
      return { text: 'offline', cls: 'bad' };
    case 'no-capture':
      return { text: 'no capture', cls: 'warn' };
    case 'error':
      return { text: 'error', cls: 'bad' };
    default:
      return { text: 'idle', cls: '' };
  }
}

function _intervalSecondsFromInput(el, fallback = 0.5) {
  const raw = String(el?.value || '').trim();
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return Math.max(0.1, n);
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

function _computeImageNormalized(imgEl, ev) {
  const rect = imgEl.getBoundingClientRect();
  const clickX = ev.clientX - rect.left;
  const clickY = ev.clientY - rect.top;
  if (rect.width <= 0 || rect.height <= 0) return null;

  const naturalW = imgEl.naturalWidth || 0;
  const naturalH = imgEl.naturalHeight || 0;
  if (naturalW > 0 && naturalH > 0) {
    const scale = Math.min(rect.width / naturalW, rect.height / naturalH);
    const drawnW = naturalW * scale;
    const drawnH = naturalH * scale;
    const offsetX = (rect.width - drawnW) / 2;
    const offsetY = (rect.height - drawnH) / 2;
    const dx = clickX - offsetX;
    const dy = clickY - offsetY;
    if (dx < 0 || dy < 0 || dx > drawnW || dy > drawnH) {
      return null;
    }
    return { x: dx / drawnW, y: dy / drawnH };
  }

  return { x: clickX / rect.width, y: clickY / rect.height };
}

async function _sendCctvClick(cluster, imgEl, ev) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return;
  if (!cluster?.baseUrl) return _setManageStatus('Cluster baseUrl is not set.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate server UUID detected.');

  const norm = _computeImageNormalized(imgEl, ev);
  if (!norm) return;

  const x = Math.max(0, Math.min(1, Number(norm.x)));
  const y = Math.max(0, Math.min(1, Number(norm.y)));

  _setManageStatus(`Sending click to ${_clusterLabel(cluster)}...`);
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/control/click', { x, y });
    _setManageStatus(`Click sent to ${_clusterLabel(cluster)} (${x.toFixed(3)}, ${y.toFixed(3)}).`);
  } catch (err) {
    _setManageStatus(`Click failed: ${err?.message ?? err}`);
  }
}

function _ensureCctvCards() {
  if (!cctvGridEl) return;
  const clusters = Array.isArray(_cachedClusters) ? _cachedClusters : [];
  const key = clusters.map(c => `${String(c?.uuid ?? '')}|${String(c?.label ?? '')}|${String(c?.baseUrl ?? '')}|${String(c?.serverUuid ?? '')}`).join('|');
  if (key === _cctvLayoutKey) return;
  _cctvLayoutKey = key;

  const activeSet = new Set(clusters.map(c => String(c?.uuid ?? '')));
  for (const [cu] of _cctvStreams.entries()) {
    if (!activeSet.has(cu)) {
      _closeCctvStream(cu);
    }
  }

  cctvGridEl.textContent = '';
  _cctvCards = new Map();

  if (clusters.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'clusterEmpty';
    empty.textContent = 'No clusters registered yet.';
    cctvGridEl.appendChild(empty);
    return;
  }

  for (const cluster of clusters) {
    const card = document.createElement('div');
    card.className = 'cctvCard';

    const header = document.createElement('div');
    header.className = 'cctvHeader';

    const title = document.createElement('div');
    title.className = 'cctvTitle';
    title.textContent = _clusterLabel(cluster);

    const pill = document.createElement('span');
    const initialState = !cluster?.baseUrl ? 'no-url' : (_isDuplicateCluster(cluster) ? 'duplicate' : 'idle');
    const pillInfo = _cctvPillInfo(initialState);
    pill.className = `clusterPill ${pillInfo.cls}`;
    pill.textContent = pillInfo.text;

    header.appendChild(title);
    header.appendChild(pill);

    const meta = document.createElement('div');
    meta.className = 'cctvMeta';
    const baseUrl = String(cluster.baseUrl ?? '').trim();
    meta.textContent = `${cluster.uuid}${baseUrl ? ` | ${baseUrl}` : ''}`;

    const img = document.createElement('img');
    img.className = 'cctvImage';
    img.alt = `${_clusterLabel(cluster)} capture`;
    img.addEventListener('click', (ev) => {
      _sendCctvClick(cluster, img, ev);
    });

    const status = document.createElement('div');
    status.className = 'cctvMeta';
    status.textContent = pillInfo.text;

    const controls = document.createElement('div');
    controls.className = 'cctvControls';

    const appPathRow = document.createElement('div');
    appPathRow.className = 'row';
    const appPathLabel = document.createElement('label');
    appPathLabel.textContent = 'App path';
    const appPathInput = document.createElement('input');
    appPathInput.type = 'text';
    appPathInput.placeholder = 'C:\\Apps\\MyApp.exe';
    appPathRow.appendChild(appPathLabel);
    appPathRow.appendChild(appPathInput);

    const titleRow = document.createElement('div');
    titleRow.className = 'row';
    const titleLabel = document.createElement('label');
    titleLabel.textContent = 'Window title';
    const titleInput = document.createElement('input');
    titleInput.type = 'text';
    titleInput.placeholder = 'Exact window title';
    titleRow.appendChild(titleLabel);
    titleRow.appendChild(titleInput);

    const geomRow = document.createElement('div');
    geomRow.className = 'row';
    const geomLabel = document.createElement('label');
    geomLabel.textContent = 'Window position/size';
    const geomInputs = document.createElement('div');
    geomInputs.className = 'buttons cctvGeom';
    const leftInput = document.createElement('input');
    leftInput.type = 'number';
    leftInput.placeholder = 'left';
    const topInput = document.createElement('input');
    topInput.type = 'number';
    topInput.placeholder = 'top';
    const widthInput = document.createElement('input');
    widthInput.type = 'number';
    widthInput.placeholder = 'width';
    const heightInput = document.createElement('input');
    heightInput.type = 'number';
    heightInput.placeholder = 'height';
    geomInputs.appendChild(leftInput);
    geomInputs.appendChild(topInput);
    geomInputs.appendChild(widthInput);
    geomInputs.appendChild(heightInput);
    geomRow.appendChild(geomLabel);
    geomRow.appendChild(geomInputs);

    const actionRow = document.createElement('div');
    actionRow.className = 'buttons cctvActions';

    const canProxy = Boolean(cluster?.baseUrl) && !_isDuplicateCluster(cluster);
    const launchBtn = document.createElement('button');
    launchBtn.type = 'button';
    launchBtn.textContent = 'Launch';
    launchBtn.disabled = !canProxy;
    launchBtn.addEventListener('click', () => {
      const geometry = _geometryPayloadFromInputs(leftInput, topInput, widthInput, heightInput);
      _appLaunchCluster(cluster, appPathInput.value, geometry);
    });
    actionRow.appendChild(launchBtn);

    const attachBtn = document.createElement('button');
    attachBtn.type = 'button';
    attachBtn.textContent = 'Attach';
    attachBtn.disabled = !canProxy;
    attachBtn.addEventListener('click', () => {
      const geometry = _geometryPayloadFromInputs(leftInput, topInput, widthInput, heightInput);
      _appAttachCluster(cluster, titleInput.value, geometry);
    });
    actionRow.appendChild(attachBtn);

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.textContent = 'Close';
    closeBtn.disabled = !canProxy;
    closeBtn.addEventListener('click', () => _appCloseCluster(cluster));
    actionRow.appendChild(closeBtn);

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.textContent = 'Remove';
    removeBtn.addEventListener('click', () => _removeCluster(cluster));
    actionRow.appendChild(removeBtn);

    const intervalRow = document.createElement('div');
    intervalRow.className = 'row';
    const intervalLabel = document.createElement('label');
    intervalLabel.textContent = 'Capture interval (seconds)';
    const intervalInput = document.createElement('input');
    intervalInput.type = 'number';
    intervalInput.min = '0.1';
    intervalInput.step = '0.1';
    intervalInput.value = '0.5';
    intervalRow.appendChild(intervalLabel);
    intervalRow.appendChild(intervalInput);

    const captureRow = document.createElement('div');
    captureRow.className = 'buttons cctvActions';
    const captureStartBtn = document.createElement('button');
    captureStartBtn.type = 'button';
    captureStartBtn.textContent = 'Start Capture';
    captureStartBtn.disabled = !canProxy;
    captureStartBtn.addEventListener('click', () => {
      const interval = _intervalSecondsFromInput(intervalInput, 0.5);
      _captureStartCluster(cluster, interval);
    });
    captureRow.appendChild(captureStartBtn);

    const captureStopBtn = document.createElement('button');
    captureStopBtn.type = 'button';
    captureStopBtn.textContent = 'Stop Capture';
    captureStopBtn.disabled = !canProxy;
    captureStopBtn.addEventListener('click', () => _captureStopCluster(cluster));
    captureRow.appendChild(captureStopBtn);

    for (const el of [appPathInput, titleInput, leftInput, topInput, widthInput, heightInput, intervalInput]) {
      if (!el) continue;
      el.disabled = !canProxy;
    }

    _loadAppDefaultsForCluster(cluster, {
      appPathEl: appPathInput,
      titleEl: titleInput,
      leftEl: leftInput,
      topEl: topInput,
      widthEl: widthInput,
      heightEl: heightInput,
    });

    controls.appendChild(appPathRow);
    controls.appendChild(titleRow);
    controls.appendChild(geomRow);
    controls.appendChild(actionRow);
    controls.appendChild(intervalRow);
    controls.appendChild(captureRow);

    card.appendChild(header);
    card.appendChild(meta);
    card.appendChild(img);
    card.appendChild(status);
    card.appendChild(controls);

    cctvGridEl.appendChild(card);
    _cctvCards.set(String(cluster.uuid ?? ''), {
      imgEl: img,
      statusEl: status,
      pillEl: pill,
    });
  }
}

function _updateCctvCardState(clusterUuid, state, detail) {
  const entry = _cctvCards.get(String(clusterUuid));
  if (!entry) return;
  const pillInfo = _cctvPillInfo(state);
  entry.pillEl.className = `clusterPill ${pillInfo.cls}`;
  entry.pillEl.textContent = pillInfo.text;
  const detailText = detail ? ` ${detail}` : '';
  entry.statusEl.textContent = `${pillInfo.text}${detailText}`;
}

function _startCctvStream(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu || _cctvStreams.has(cu)) return;

  const url = `/api/orchestrator/clusters/${encodeURIComponent(cu)}/capture/stream?fmt=jpg&quality=70`;
  const stream = new EventSource(url);
  _cctvStreams.set(cu, stream);

  stream.addEventListener('frame', (ev) => {
    const payload = String(ev?.data || '').trim();
    if (!payload) return;
    const entry = _cctvCards.get(cu);
    if (!entry) return;
    entry.imgEl.src = `data:image/jpeg;base64,${payload}`;
    _updateCctvCardState(cu, 'live', '');
  });

  stream.addEventListener('error', () => {
    if (!_cctvStreams.has(cu)) return;
    _updateCctvCardState(cu, 'offline', '');
  });
}

function _closeCctvStream(clusterUuid) {
  const cu = String(clusterUuid ?? '').trim();
  const stream = _cctvStreams.get(cu);
  if (stream) {
    stream.close();
  }
  _cctvStreams.delete(cu);
}

async function _captureStartCluster(cluster, intervalSeconds) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (!cluster?.baseUrl) return _setManageStatus('Cluster baseUrl is not set.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate server UUID detected.');
  const interval = Math.max(0.1, Number(intervalSeconds) || 0.5);
  _setManageStatus(`Starting capture on ${_clusterLabel(cluster)}...`);
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/capture/start', { intervalSeconds: interval });
    _startCctvStream(cluster);
    _updateCctvCardState(cu, 'live', 'starting');
    _setManageStatus(`Capture started on ${_clusterLabel(cluster)}.`);
  } catch (err) {
    _updateCctvCardState(cu, 'error', '');
    _setManageStatus(`Start capture failed: ${err?.message ?? err}`);
  }
}

async function _captureStopCluster(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (!cluster?.baseUrl) return _setManageStatus('Cluster baseUrl is not set.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate server UUID detected.');
  _setManageStatus(`Stopping capture on ${_clusterLabel(cluster)}...`);
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/capture/stop`, {});
  } catch (err) {
    _setManageStatus(`Stop capture failed: ${err?.message ?? err}`);
  }
  _closeCctvStream(cu);
  _updateCctvCardState(cu, 'stopped', '');
  _setManageStatus(`Capture stopped on ${_clusterLabel(cluster)}.`);
}

function _selectedClusterIsDuplicate() {
  return false;
}

async function refreshClusters() {
  _setManageStatus('Loading clusters...');
  try {
    const resp = await _getJson('/api/orchestrator/clusters');
    const clusters = resp && Array.isArray(resp.clusters) ? resp.clusters : [];
    _cachedClusters = clusters;
    _dupCountByServerUuid = new Map();
    _appDefaultsCache = new Map();
    for (const c of clusters) {
      const su = _serverUuidOf(c);
      if (!su) continue;
      _dupCountByServerUuid.set(su, (_dupCountByServerUuid.get(su) || 0) + 1);
    }
    _ensureCctvCards();
    _setManageStatus('Ready.');
  } catch (err) {
    _setManageStatus(`Failed to load clusters: ${err?.message ?? err}`);
  }
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

function _tabInit() {
  const tabs = Array.from(document.querySelectorAll('.orchTabs--main button'));
  for (const b of tabs) {
    b.addEventListener('click', () => {
      const name = String(b.getAttribute('data-tab') || '');
      for (const bb of tabs) bb.classList.toggle('active', bb === b);
      const panels = Array.from(document.querySelectorAll('.orchPanel'));
      for (const p of panels) {
        p.classList.toggle('active', p.id === `tab-${name}`);
      }
    });
  }
}

function _subTabInit() {
  const navs = Array.from(document.querySelectorAll('.orchSubTabs'));
  for (const nav of navs) {
    const buttons = Array.from(nav.querySelectorAll('button'));
    if (buttons.length === 0) continue;

    const scope = nav.closest('.orchPanel') || nav.parentElement || document;
    const panels = Array.from(scope.querySelectorAll('.orchSubPanel'));

    for (const b of buttons) {
      b.addEventListener('click', () => {
        const targetId = String(b.getAttribute('data-panel') || '').trim();
        if (!targetId) return;

        for (const bb of buttons) bb.classList.toggle('active', bb === b);
        for (const p of panels) {
          p.classList.toggle('active', p.id === targetId);
        }
      });
    }
  }
}

async function _postProxy(clusterUuid, path, bodyObj) {
  const url = String(path).replace('{uuid}', encodeURIComponent(String(clusterUuid)));
  return await _postJson(url, { body: bodyObj ?? {} });
}

async function actionsFetch() {
  const cu = _selectedClusterUuid();
  if (!cu) {
    _setManageStatus('Select a cluster first.');
    return;
  }
  if (_selectedClusterIsDuplicate()) {
    _setManageStatus('Duplicate server UUID detected.');
    return;
  }
  _setManageStatus('Fetching actions...');
  try {
    const data = await _getJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/actions`);
    _cachedActions = Array.isArray(data) ? data : [];
    _fillTextArea(actionsListEl, data);
    _fillSelect(actionsSelectEl, _cachedActions, 'uuid', 'name', null);
    if (_cachedActions.length > 0) {
      const first = _cachedActions[0];
      if (actionsSelectEl) actionsSelectEl.value = String(first.uuid ?? '');
      if (actionRunUuidEl) actionRunUuidEl.value = String(first.uuid ?? '');
      if (actionUpsertBodyEl) _fillTextArea(actionUpsertBodyEl, first);
    }
    _setManageStatus('Actions loaded.');
  } catch (err) {
    _setManageStatus(`Fetch failed: ${err?.message ?? err}`);
  }
}

function _onActionSelected() {
  const uuid = String(actionsSelectEl?.value || '').trim();
  const item = _findByUuid(_cachedActions, uuid);
  if (actionRunUuidEl) actionRunUuidEl.value = uuid;
  if (item && actionUpsertBodyEl) {
    _fillTextArea(actionUpsertBodyEl, item);
  }
}

async function actionRunRemove(kind) {
  const cu = _selectedClusterUuid();
  const actionUuid = String(actionRunUuidEl?.value || '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  if (!actionUuid) return _setManageStatus('Action UUID is required.');
  const endpoint = kind === 'run'
    ? `/api/orchestrator/clusters/${encodeURIComponent(cu)}/actions/run`
    : `/api/orchestrator/clusters/${encodeURIComponent(cu)}/actions/remove_uuid`;
  _setManageStatus(kind === 'run' ? 'Running action...' : 'Removing action...');
  try {
    await _postJson(endpoint, { body: { uuid: actionUuid } });
    _setManageStatus('OK.');
    await actionsFetch();
  } catch (err) {
    _setManageStatus(`Failed: ${err?.message ?? err}`);
  }
}

async function actionUpsert() {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  let payload;
  try {
    payload = _parseJsonFromTextArea(actionUpsertBodyEl);
  } catch (err) {
    return _setManageStatus(`Invalid JSON: ${err?.message ?? err}`);
  }
  if (!payload || typeof payload !== 'object') return _setManageStatus('Payload is required.');
  _setManageStatus('Upserting action...');
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/actions/upsert`, { body: payload });
    _setManageStatus('OK.');
    await actionsFetch();
  } catch (err) {
    _setManageStatus(`Failed: ${err?.message ?? err}`);
  }
}

async function conditionsFetch(kind) {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  const url = kind === 'status'
    ? `/api/orchestrator/clusters/${encodeURIComponent(cu)}/conditions/status`
    : `/api/orchestrator/clusters/${encodeURIComponent(cu)}/conditions`;
  _setManageStatus(kind === 'status' ? 'Fetching condition status...' : 'Fetching conditions...');
  try {
    const data = await _getJson(url);
    if (kind === 'list') {
      _cachedConditions = Array.isArray(data) ? data : [];
      _fillSelect(conditionsSelectEl, _cachedConditions, 'uuid', 'name', null);
      if (_cachedConditions.length > 0 && conditionsSelectEl) {
        conditionsSelectEl.value = String(_cachedConditions[0].uuid ?? '');
      }
      _onConditionSelected();
    }
    _fillTextArea(conditionsListEl, data);
    _setManageStatus('Loaded.');
  } catch (err) {
    _setManageStatus(`Failed: ${err?.message ?? err}`);
  }
}

function _onConditionSelected() {
  const uuid = String(conditionsSelectEl?.value || '').trim();
  const item = _findByUuid(_cachedConditions, uuid);
  if (!item) return;

  const op = String(conditionsOpEl?.value || '');
  if (op.includes('/set_from_live')) {
    const payload = {
      uuid: String(item.uuid ?? ''),
      name: String(item.name ?? ''),
      type: String(item.type ?? ''),
      roi: item.roi ?? null,
      templateFromLive: false,
    };
    _fillTextArea(conditionsBodyEl, payload);
  } else if (op.includes('/move')) {
    _fillTextArea(conditionsBodyEl, { uuid: String(item.uuid ?? ''), direction: 'up' });
  } else if (op.includes('/remove_uuid')) {
    _fillTextArea(conditionsBodyEl, { uuid: String(item.uuid ?? '') });
  }
}

async function conditionsSend() {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  const op = String(conditionsOpEl?.value || '').trim();
  if (!op) return _setManageStatus('Pick an operation.');

  let payload;
  try {
    payload = _parseJsonFromTextArea(conditionsBodyEl);
  } catch (err) {
    return _setManageStatus(`Invalid JSON: ${err?.message ?? err}`);
  }
  if (!payload || typeof payload !== 'object') return _setManageStatus('Payload is required.');

  _setManageStatus('Sending condition request...');
  try {
    await _postProxy(cu, op, payload);
    _setManageStatus('OK.');
    await conditionsFetch('list');
  } catch (err) {
    _setManageStatus(`Failed: ${err?.message ?? err}`);
  }
}

async function triggersFetch(kind) {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  const url = kind === 'status'
    ? `/api/orchestrator/clusters/${encodeURIComponent(cu)}/triggers/status`
    : `/api/orchestrator/clusters/${encodeURIComponent(cu)}/triggers`;
  _setManageStatus(kind === 'status' ? 'Fetching trigger status...' : 'Fetching triggers...');
  try {
    const data = await _getJson(url);
    if (kind === 'list') {
      _cachedTriggers = Array.isArray(data) ? data : [];
      _fillSelect(triggersSelectEl, _cachedTriggers, 'uuid', 'name', null);
      if (_cachedTriggers.length > 0 && triggersSelectEl) {
        triggersSelectEl.value = String(_cachedTriggers[0].uuid ?? '');
      }
      _onTriggerSelected();
    }
    _fillTextArea(triggersListEl, data);
    _setManageStatus('Loaded.');
  } catch (err) {
    _setManageStatus(`Failed: ${err?.message ?? err}`);
  }
}

function _onTriggerSelected() {
  const uuid = String(triggersSelectEl?.value || '').trim();
  const item = _findByUuid(_cachedTriggers, uuid);
  if (!item) return;
  if (triggerEnabledEl) triggerEnabledEl.checked = Boolean(item.enabled);

  const op = String(triggersOpEl?.value || '');
  if (op.includes('/set_enabled')) {
    _fillTextArea(triggersBodyEl, { uuid: String(item.uuid ?? ''), enabled: Boolean(item.enabled) });
  } else if (op.includes('/remove_uuid')) {
    _fillTextArea(triggersBodyEl, { uuid: String(item.uuid ?? '') });
  } else if (op.includes('/upsert')) {
    _fillTextArea(triggersBodyEl, item);
  }
}

async function triggerApplyEnabled() {
  const cu = _selectedClusterUuid();
  const tu = String(triggersSelectEl?.value || '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  if (!tu) return _setManageStatus('Select a trigger first.');
  const enabled = Boolean(triggerEnabledEl?.checked);
  _setManageStatus('Applying enabled...');
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/triggers/set_enabled`, { body: { uuid: tu, enabled } });
    _setManageStatus('OK.');
    await triggersFetch('list');
  } catch (err) {
    _setManageStatus(`Failed: ${err?.message ?? err}`);
  }
}

async function triggerRemoveSelected() {
  const cu = _selectedClusterUuid();
  const tu = String(triggersSelectEl?.value || '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  if (!tu) return _setManageStatus('Select a trigger first.');
  _setManageStatus('Removing trigger...');
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/triggers/remove_uuid`, { body: { uuid: tu } });
    _setManageStatus('OK.');
    await triggersFetch('list');
  } catch (err) {
    _setManageStatus(`Failed: ${err?.message ?? err}`);
  }
}

async function triggersSend() {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  const op = String(triggersOpEl?.value || '').trim();
  if (!op) return _setManageStatus('Pick an operation.');

  let payload;
  try {
    payload = _parseJsonFromTextArea(triggersBodyEl);
  } catch (err) {
    return _setManageStatus(`Invalid JSON: ${err?.message ?? err}`);
  }
  if (!payload || typeof payload !== 'object') return _setManageStatus('Payload is required.');

  _setManageStatus('Sending trigger request...');
  try {
    await _postProxy(cu, op, payload);
    _setManageStatus('OK.');
    await triggersFetch('list');
  } catch (err) {
    _setManageStatus(`Failed: ${err?.message ?? err}`);
  }
}

function _selectedConfigUuid() {
  const v = String(configsSelectEl?.value || '').trim();
  return v || null;
}

function _fillConfigFields(config) {
  if (configNameEl) configNameEl.value = String(config?.name ?? '');
  if (configDescriptionEl) configDescriptionEl.value = String(config?.description ?? '');
  if (configTagsEl) configTagsEl.value = _tagsToString(config?.tags ?? []);
  if (configContentEl) {
    if (config && typeof config === 'object' && config.content) {
      _fillTextArea(configContentEl, config.content);
    } else {
      configContentEl.value = '';
    }
  }
}

async function _loadSelectedConfig() {
  const cfg = _selectedConfigUuid();
  if (!cfg) {
    _fillConfigFields(null);
    return;
  }
  try {
    const data = await _getJson(`/api/orchestrator/configs/${encodeURIComponent(cfg)}`);
    const config = data && typeof data === 'object' ? data.config : null;
    _fillConfigFields(config);
  } catch (err) {
    _setManageStatus(`Config load failed: ${err?.message ?? err}`);
  }
}

async function configsFetch(selectUuid = null) {
  _setManageStatus('Loading configs...');
  try {
    const data = await _getJson('/api/orchestrator/configs');
    const configs = data && Array.isArray(data.configs) ? data.configs : [];
    _cachedConfigs = configs;
    _fillTextArea(configsListEl, data);
    _fillSelect(configsSelectEl, configs, 'uuid', 'name', selectUuid);
    if (!selectUuid && configs.length > 0 && configsSelectEl) {
      configsSelectEl.value = String(configs[0].uuid ?? '');
    }
    await _loadSelectedConfig();
    _setManageStatus('Configs loaded.');
  } catch (err) {
    _setManageStatus(`Failed to load configs: ${err?.message ?? err}`);
  }
}

async function configCreate() {
  const name = String(configNameEl?.value || '').trim();
  if (!name) return _setManageStatus('Config name is required.');
  const description = String(configDescriptionEl?.value || '').trim();
  const tags = _parseTagsInput(configTagsEl?.value || '');
  let content = null;
  try {
    content = _parseJsonFromTextArea(configContentEl);
  } catch (err) {
    return _setManageStatus(`Invalid JSON: ${err?.message ?? err}`);
  }
  _setManageStatus('Creating config...');
  try {
    const resp = await _postJson('/api/orchestrator/configs/create', {
      name,
      description,
      tags,
      content,
    });
    const cfg = resp && resp.config ? resp.config : null;
    _setManageStatus('Config created.');
    await configsFetch(cfg?.uuid ?? null);
    await configAssignmentsFetch();
  } catch (err) {
    _setManageStatus(`Create failed: ${err?.message ?? err}`);
  }
}

async function configUpdate() {
  const cfg = _selectedConfigUuid();
  if (!cfg) return _setManageStatus('Select a config first.');
  const name = String(configNameEl?.value || '').trim();
  if (!name) return _setManageStatus('Config name is required.');
  const description = String(configDescriptionEl?.value || '').trim();
  const tags = _parseTagsInput(configTagsEl?.value || '');
  let content = null;
  try {
    content = _parseJsonFromTextArea(configContentEl);
  } catch (err) {
    return _setManageStatus(`Invalid JSON: ${err?.message ?? err}`);
  }

  const payload = { name, description, tags };
  if (content !== null) {
    payload.content = content;
  }

  _setManageStatus('Updating config...');
  try {
    await _postJson(`/api/orchestrator/configs/${encodeURIComponent(cfg)}/update`, payload);
    _setManageStatus('Config updated.');
    await configsFetch(cfg);
    await configAssignmentsFetch();
  } catch (err) {
    _setManageStatus(`Update failed: ${err?.message ?? err}`);
  }
}

async function configRemove() {
  const cfg = _selectedConfigUuid();
  if (!cfg) return _setManageStatus('Select a config first.');
  _setManageStatus('Removing config...');
  try {
    await _postJson(`/api/orchestrator/configs/${encodeURIComponent(cfg)}/remove`, {});
    _setManageStatus('Config removed.');
    await configsFetch(null);
    await configAssignmentsFetch();
  } catch (err) {
    _setManageStatus(`Remove failed: ${err?.message ?? err}`);
  }
}

async function configSnapshot() {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  const name = String(configNameEl?.value || '').trim();
  if (!name) return _setManageStatus('Config name is required.');
  const description = String(configDescriptionEl?.value || '').trim();
  const tags = _parseTagsInput(configTagsEl?.value || '');
  _setManageStatus('Snapshotting cluster config...');
  try {
    const resp = await _postJson('/api/orchestrator/configs/from_cluster', {
      clusterUuid: cu,
      name,
      description,
      tags,
    });
    const cfg = resp && resp.config ? resp.config : null;
    _setManageStatus('Snapshot created.');
    await configsFetch(cfg?.uuid ?? null);
    await configAssignmentsFetch();
  } catch (err) {
    _setManageStatus(`Snapshot failed: ${err?.message ?? err}`);
  }
}

async function configApply() {
  const cfg = _selectedConfigUuid();
  if (!cfg) return _setManageStatus('Select a config first.');

  const targets = _parseUuidList(configApplyTargetsEl?.value || '');
  const dryRun = Boolean(configApplyDryRunEl?.checked);
  const payload = { dryRun };

  if (targets.length === 0) {
    const cu = _selectedClusterUuid();
    if (!cu) return _setManageStatus('Select a cluster or enter target UUIDs.');
    if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
    payload.clusterUuid = cu;
  } else {
    payload.clusterUuids = targets;
  }

  _setManageStatus(dryRun ? 'Dry run apply...' : 'Applying config...');
  try {
    const resp = await _postJson(`/api/orchestrator/configs/${encodeURIComponent(cfg)}/apply`, payload);
    _setManageStatus('Config applied.');
    _fillTextArea(configAssignmentsEl, resp);
    if (!dryRun) await configAssignmentsFetch();
  } catch (err) {
    _setManageStatus(`Apply failed: ${err?.message ?? err}`);
  }
}

async function configAssignmentsFetch() {
  _setManageStatus('Loading assignments...');
  try {
    const data = await _getJson('/api/orchestrator/configs/assignments');
    _fillTextArea(configAssignmentsEl, data);
    _setManageStatus('Assignments loaded.');
  } catch (err) {
    _setManageStatus(`Assignments failed: ${err?.message ?? err}`);
  }
}

function _selectedLayoutUuid() {
  const v = String(screensLayoutSelectEl?.value || '').trim();
  return v || null;
}

function _fillLayoutFields(layout) {
  if (screenLayoutNameEl) screenLayoutNameEl.value = String(layout?.name ?? '');
  if (screenLayoutDescriptionEl) screenLayoutDescriptionEl.value = String(layout?.description ?? '');
  if (screenLayoutScreensEl) {
    if (layout && typeof layout === 'object' && layout.screens) {
      _fillTextArea(screenLayoutScreensEl, layout.screens);
    } else {
      screenLayoutScreensEl.value = '';
    }
  }

  const labels = Array.isArray(layout?.screens) ? layout.screens.map(s => s?.label).filter(Boolean) : [];
  if (screenAssignHintEl) {
    screenAssignHintEl.textContent = labels.length > 0 ? `Available labels: ${labels.join(', ')}` : '';
  }
  if (screenAssignLabelEl && !String(screenAssignLabelEl.value || '').trim() && labels.length > 0) {
    screenAssignLabelEl.value = String(labels[0]);
  }
}

async function _loadSelectedLayout() {
  const layoutUuid = _selectedLayoutUuid();
  if (!layoutUuid) {
    _fillLayoutFields(null);
    return;
  }
  try {
    const data = await _getJson(`/api/orchestrator/screens/layouts/${encodeURIComponent(layoutUuid)}`);
    const layout = data && typeof data === 'object' ? data.layout : null;
    _fillLayoutFields(layout);
  } catch (err) {
    _setManageStatus(`Layout load failed: ${err?.message ?? err}`);
  }
}

async function screensLayoutsFetch(selectUuid = null) {
  _setManageStatus('Loading layouts...');
  try {
    const data = await _getJson('/api/orchestrator/screens/layouts');
    const layouts = data && Array.isArray(data.layouts) ? data.layouts : [];
    _cachedLayouts = layouts;
    _fillTextArea(screensLayoutsListEl, data);
    _fillSelect(screensLayoutSelectEl, layouts, 'uuid', 'name', selectUuid);
    if (!selectUuid && layouts.length > 0 && screensLayoutSelectEl) {
      screensLayoutSelectEl.value = String(layouts[0].uuid ?? '');
    }
    await _loadSelectedLayout();
    _setManageStatus('Layouts loaded.');
  } catch (err) {
    _setManageStatus(`Layouts failed: ${err?.message ?? err}`);
  }
}

async function screenLayoutCreate() {
  const name = String(screenLayoutNameEl?.value || '').trim();
  if (!name) return _setManageStatus('Layout name is required.');
  const description = String(screenLayoutDescriptionEl?.value || '').trim();
  let screens = [];
  try {
    const parsed = _parseJsonFromTextArea(screenLayoutScreensEl);
    if (parsed === null) {
      screens = [];
    } else if (Array.isArray(parsed)) {
      screens = parsed;
    } else {
      return _setManageStatus('Screens JSON must be an array.');
    }
  } catch (err) {
    return _setManageStatus(`Invalid JSON: ${err?.message ?? err}`);
  }

  _setManageStatus('Creating layout...');
  try {
    const resp = await _postJson('/api/orchestrator/screens/layouts/create', {
      name,
      description,
      screens,
    });
    const layout = resp && resp.layout ? resp.layout : null;
    _setManageStatus('Layout created.');
    await screensLayoutsFetch(layout?.uuid ?? null);
    await screensAssignmentsFetch();
  } catch (err) {
    _setManageStatus(`Create failed: ${err?.message ?? err}`);
  }
}

async function screenLayoutUpdate() {
  const layoutUuid = _selectedLayoutUuid();
  if (!layoutUuid) return _setManageStatus('Select a layout first.');
  const name = String(screenLayoutNameEl?.value || '').trim();
  if (!name) return _setManageStatus('Layout name is required.');
  const description = String(screenLayoutDescriptionEl?.value || '').trim();
  let screens = null;
  try {
    const parsed = _parseJsonFromTextArea(screenLayoutScreensEl);
    if (parsed === null) {
      screens = null;
    } else if (Array.isArray(parsed)) {
      screens = parsed;
    } else {
      return _setManageStatus('Screens JSON must be an array.');
    }
  } catch (err) {
    return _setManageStatus(`Invalid JSON: ${err?.message ?? err}`);
  }

  const payload = { name, description };
  if (screens !== null) payload.screens = screens;

  _setManageStatus('Updating layout...');
  try {
    await _postJson(`/api/orchestrator/screens/layouts/${encodeURIComponent(layoutUuid)}/update`, payload);
    _setManageStatus('Layout updated.');
    await screensLayoutsFetch(layoutUuid);
    await screensAssignmentsFetch();
  } catch (err) {
    _setManageStatus(`Update failed: ${err?.message ?? err}`);
  }
}

async function screenLayoutRemove() {
  const layoutUuid = _selectedLayoutUuid();
  if (!layoutUuid) return _setManageStatus('Select a layout first.');
  _setManageStatus('Removing layout...');
  try {
    await _postJson(`/api/orchestrator/screens/layouts/${encodeURIComponent(layoutUuid)}/remove`, {});
    _setManageStatus('Layout removed.');
    await screensLayoutsFetch(null);
    await screensAssignmentsFetch();
  } catch (err) {
    _setManageStatus(`Remove failed: ${err?.message ?? err}`);
  }
}

async function screensAssignmentsFetch() {
  _setManageStatus('Loading screen assignments...');
  try {
    const data = await _getJson('/api/orchestrator/screens/assignments');
    _fillTextArea(screenAssignmentsEl, data);
    _setManageStatus('Assignments loaded.');
  } catch (err) {
    _setManageStatus(`Assignments failed: ${err?.message ?? err}`);
  }
}

async function screenAssign() {
  const layoutUuid = _selectedLayoutUuid();
  if (!layoutUuid) return _setManageStatus('Select a layout first.');
  const screenLabel = String(screenAssignLabelEl?.value || '').trim();
  if (!screenLabel) return _setManageStatus('Screen label is required.');

  const clusterUuid = String(screenAssignClusterEl?.value || '').trim() || _selectedClusterUuid();
  if (!clusterUuid) return _setManageStatus('Select a cluster or enter a UUID.');

  _setManageStatus('Assigning layout...');
  try {
    await _postJson('/api/orchestrator/screens/assign', {
      clusterUuid,
      layoutUuid,
      screenLabel,
    });
    _setManageStatus('Assigned.');
    await screensAssignmentsFetch();
  } catch (err) {
    _setManageStatus(`Assign failed: ${err?.message ?? err}`);
  }
}

async function screenUnassign() {
  const clusterUuid = String(screenAssignClusterEl?.value || '').trim() || _selectedClusterUuid();
  if (!clusterUuid) return _setManageStatus('Select a cluster or enter a UUID.');
  _setManageStatus('Removing assignment...');
  try {
    await _postJson('/api/orchestrator/screens/unassign', { clusterUuid });
    _setManageStatus('Assignment removed.');
    await screensAssignmentsFetch();
  } catch (err) {
    _setManageStatus(`Unassign failed: ${err?.message ?? err}`);
  }
}

async function screenApply() {
  const applyAll = Boolean(screenApplyAllEl?.checked);
  const dryRun = Boolean(screenApplyDryRunEl?.checked);
  const windowTitle = String(screenApplyWindowTitleEl?.value || '').trim();
  const targets = _parseUuidList(screenApplyTargetsEl?.value || '');
  const payload = { applyAll, dryRun };

  if (windowTitle) payload.windowTitle = windowTitle;

  if (!applyAll) {
    if (targets.length === 0) {
      const cu = _selectedClusterUuid();
      if (!cu) return _setManageStatus('Select a cluster or enter target UUIDs.');
      payload.clusterUuid = cu;
    } else {
      payload.clusterUuids = targets;
    }
  }

  _setManageStatus(dryRun ? 'Dry run apply layout...' : 'Applying layout...');
  try {
    const resp = await _postJson('/api/orchestrator/screens/apply', payload);
    _setManageStatus('Layout applied.');
    _fillTextArea(screenAssignmentsEl, resp);
  } catch (err) {
    _setManageStatus(`Apply failed: ${err?.message ?? err}`);
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

if (btnActionsFetchEl) btnActionsFetchEl.addEventListener('click', () => actionsFetch());
if (btnActionRunEl) btnActionRunEl.addEventListener('click', () => actionRunRemove('run'));
if (btnActionRemoveEl) btnActionRemoveEl.addEventListener('click', () => actionRunRemove('remove'));
if (btnActionUpsertEl) btnActionUpsertEl.addEventListener('click', () => actionUpsert());
if (actionsSelectEl) actionsSelectEl.addEventListener('change', () => _onActionSelected());

if (btnConditionsFetchEl) btnConditionsFetchEl.addEventListener('click', () => conditionsFetch('list'));
if (btnConditionsStatusEl) btnConditionsStatusEl.addEventListener('click', () => conditionsFetch('status'));
if (btnConditionsSendEl) btnConditionsSendEl.addEventListener('click', () => conditionsSend());
if (conditionsSelectEl) conditionsSelectEl.addEventListener('change', () => _onConditionSelected());
if (conditionsOpEl) conditionsOpEl.addEventListener('change', () => _onConditionSelected());

if (btnTriggersFetchEl) btnTriggersFetchEl.addEventListener('click', () => triggersFetch('list'));
if (btnTriggersStatusEl) btnTriggersStatusEl.addEventListener('click', () => triggersFetch('status'));
if (btnTriggersSendEl) btnTriggersSendEl.addEventListener('click', () => triggersSend());
if (triggersSelectEl) triggersSelectEl.addEventListener('change', () => _onTriggerSelected());
if (triggersOpEl) triggersOpEl.addEventListener('change', () => _onTriggerSelected());
if (btnTriggerApplyEnabledEl) btnTriggerApplyEnabledEl.addEventListener('click', () => triggerApplyEnabled());
if (btnTriggerRemoveEl) btnTriggerRemoveEl.addEventListener('click', () => triggerRemoveSelected());

if (btnConfigsFetchEl) btnConfigsFetchEl.addEventListener('click', () => configsFetch(_selectedConfigUuid()));
if (btnAssignmentsFetchEl) btnAssignmentsFetchEl.addEventListener('click', () => configAssignmentsFetch());
if (configsSelectEl) configsSelectEl.addEventListener('change', () => _loadSelectedConfig());
if (btnConfigCreateEl) btnConfigCreateEl.addEventListener('click', () => configCreate());
if (btnConfigUpdateEl) btnConfigUpdateEl.addEventListener('click', () => configUpdate());
if (btnConfigRemoveEl) btnConfigRemoveEl.addEventListener('click', () => configRemove());
if (btnConfigSnapshotEl) btnConfigSnapshotEl.addEventListener('click', () => configSnapshot());
if (btnConfigApplyEl) btnConfigApplyEl.addEventListener('click', () => configApply());

if (btnScreensLayoutsFetchEl) btnScreensLayoutsFetchEl.addEventListener('click', () => screensLayoutsFetch(_selectedLayoutUuid()));
if (btnScreensAssignmentsFetchEl) btnScreensAssignmentsFetchEl.addEventListener('click', () => screensAssignmentsFetch());
if (screensLayoutSelectEl) screensLayoutSelectEl.addEventListener('change', () => _loadSelectedLayout());
if (btnScreenLayoutCreateEl) btnScreenLayoutCreateEl.addEventListener('click', () => screenLayoutCreate());
if (btnScreenLayoutUpdateEl) btnScreenLayoutUpdateEl.addEventListener('click', () => screenLayoutUpdate());
if (btnScreenLayoutRemoveEl) btnScreenLayoutRemoveEl.addEventListener('click', () => screenLayoutRemove());
if (btnScreenAssignEl) btnScreenAssignEl.addEventListener('click', () => screenAssign());
if (btnScreenUnassignEl) btnScreenUnassignEl.addEventListener('click', () => screenUnassign());
if (btnScreenApplyEl) btnScreenApplyEl.addEventListener('click', () => screenApply());

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
