const clusterLabelEl = document.getElementById('clusterLabel');
const clusterBaseUrlEl = document.getElementById('clusterBaseUrl');
const btnCommissionEl = document.getElementById('btnCommission');
const regStatusEl = document.getElementById('regStatus');

const clusterSelectEl = document.getElementById('clusterSelect');
const btnRefreshClustersEl = document.getElementById('btnRefreshClusters');
const clusterMetaEl = document.getElementById('clusterMeta');
const dashboardClustersEl = document.getElementById('dashboardClusters');
const dashboardAssignmentsEl = document.getElementById('dashboardAssignments');
const btnDashboardRefreshEl = document.getElementById('btnDashboardRefresh');
const dashboardClusterCardsEl = document.getElementById('dashboardClusterCards');
const cctvIntervalEl = document.getElementById('cctvInterval');
const btnCctvStartEl = document.getElementById('btnCctvStart');
const btnCctvStopEl = document.getElementById('btnCctvStop');
const cctvStatusEl = document.getElementById('cctvStatus');
const cctvGridEl = document.getElementById('cctvGrid');

const editClusterLabelEl = document.getElementById('editClusterLabel');
const editClusterBaseUrlEl = document.getElementById('editClusterBaseUrl');
const btnClusterSaveEl = document.getElementById('btnClusterSave');
const btnClusterRemoveEl = document.getElementById('btnClusterRemove');

const appLaunchPathEl = document.getElementById('appLaunchPath');
const appAttachTitleEl = document.getElementById('appAttachTitle');
const appLeftEl = document.getElementById('appLeft');
const appTopEl = document.getElementById('appTop');
const appWidthEl = document.getElementById('appWidth');
const appHeightEl = document.getElementById('appHeight');
const btnAppLaunchEl = document.getElementById('btnAppLaunch');
const btnAppAttachEl = document.getElementById('btnAppAttach');
const btnAppCloseEl = document.getElementById('btnAppClose');
const btnCaptureStartEl = document.getElementById('btnCaptureStart');
const btnCaptureStopEl = document.getElementById('btnCaptureStop');

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
let _cctvActive = false;
let _cctvCards = new Map();
let _cctvLayoutKey = '';
let _cctvStreams = new Map();

function _setStatus(text) {
  if (!regStatusEl) return;
  regStatusEl.textContent = String(text ?? '');
}

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
  const v = String(clusterSelectEl?.value || '').trim();
  return v || null;
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

async function _loadDashboardClusterStatus(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  const baseUrl = String(cluster?.baseUrl ?? '').trim();
  const duplicate = _isDuplicateCluster(cluster);

  const info = {
    cluster,
    duplicate,
    baseUrl,
    health: { state: 'unknown', detail: null },
    triggers: { state: 'unknown', total: 0, enabled: 0, met: 0, lastError: null, detail: null },
  };

  if (!baseUrl) {
    info.health = { state: 'no-url', detail: 'No baseUrl' };
    info.triggers = { state: 'unavailable', total: 0, enabled: 0, met: 0, lastError: null, detail: 'No baseUrl' };
    return info;
  }
  if (duplicate) {
    info.health = { state: 'duplicate', detail: 'Duplicate server UUID' };
    info.triggers = { state: 'unavailable', total: 0, enabled: 0, met: 0, lastError: null, detail: 'Duplicate server UUID' };
    return info;
  }

  try {
    await _getJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/server/info`);
    info.health = { state: 'online', detail: null };
  } catch (err) {
    info.health = { state: 'offline', detail: err?.message ?? err };
    info.triggers = { state: 'offline', total: 0, enabled: 0, met: 0, lastError: null, detail: err?.message ?? err };
    return info;
  }

  try {
    const status = await _getJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/triggers/status`);
    const items = status && Array.isArray(status.items) ? status.items : [];
    const enabledCount = items.filter(x => x && x.enabled).length;
    const metCount = items.filter(x => x && x.isMet).length;
    info.triggers = {
      state: 'ok',
      total: items.length,
      enabled: enabledCount,
      met: metCount,
      lastError: status?.lastError ?? null,
      detail: null,
    };
  } catch (err) {
    info.triggers = { state: 'error', total: 0, enabled: 0, met: 0, lastError: null, detail: err?.message ?? err };
  }

  return info;
}

function _pillForHealth(state) {
  switch (state) {
    case 'online':
      return { text: 'online', cls: 'ok' };
    case 'offline':
      return { text: 'offline', cls: 'bad' };
    case 'duplicate':
      return { text: 'duplicate', cls: 'warn' };
    case 'no-url':
      return { text: 'no url', cls: 'warn' };
    default:
      return { text: 'unknown', cls: '' };
  }
}

async function _dashboardProxyAction(cluster, label, fn) {
  const name = _clusterLabel(cluster);
  _setManageStatus(`${label}: ${name}...`);
  try {
    await fn();
    _setManageStatus(`${label}: ${name} OK.`);
  } catch (err) {
    _setManageStatus(`${label}: ${name} failed: ${err?.message ?? err}`);
  }
}

function _buildDashboardClusterCard(info) {
  const cluster = info.cluster || {};
  const card = document.createElement('div');
  card.className = 'clusterCard';
  if (String(cluster.uuid ?? '') === String(_selectedClusterUuid() ?? '')) {
    card.classList.add('isSelected');
  }

  const header = document.createElement('div');
  header.className = 'clusterHeader';
  const title = document.createElement('div');
  title.className = 'clusterTitle';
  title.textContent = _clusterLabel(cluster);
  const healthPill = document.createElement('span');
  const pillInfo = _pillForHealth(info.health?.state);
  healthPill.className = `clusterPill ${pillInfo.cls}`;
  healthPill.textContent = pillInfo.text;
  header.appendChild(title);
  header.appendChild(healthPill);

  const meta = document.createElement('div');
  meta.className = 'clusterMeta';
  const baseUrl = String(cluster.baseUrl ?? '').trim();
  const uuid = String(cluster.uuid ?? '').trim();
  meta.textContent = `${uuid}${baseUrl ? ` | ${baseUrl}` : ''}`;

  const triggers = document.createElement('div');
  triggers.className = 'clusterMeta';
  if (info.triggers?.state === 'ok') {
    triggers.textContent = `Triggers: ${info.triggers.total} total / ${info.triggers.enabled} enabled / ${info.triggers.met} met`;
  } else {
    const reason = info.triggers?.detail ? ` (${_shortenText(info.triggers.detail)})` : '';
    triggers.textContent = `Triggers: ${info.triggers?.state || 'unknown'}${reason}`;
  }

  const error = document.createElement('div');
  error.className = 'clusterMeta';
  const errText = info.triggers?.lastError ? _shortenText(info.triggers.lastError) : '';
  error.textContent = errText ? `Last error: ${errText}` : '';

  const actions = document.createElement('div');
  actions.className = 'buttons clusterActions';

  const selectBtn = document.createElement('button');
  selectBtn.type = 'button';
  selectBtn.textContent = 'Select';
  selectBtn.addEventListener('click', () => {
    if (!clusterSelectEl) return;
    clusterSelectEl.value = String(cluster.uuid ?? '');
    _setClusterEditorFromSelected();
    _loadAppDefaultsForSelectedCluster();
    _applyDuplicateUiState();
  });
  actions.appendChild(selectBtn);

  const canProxy = Boolean(info.baseUrl) && !info.duplicate;
  const captureStartBtn = document.createElement('button');
  captureStartBtn.type = 'button';
  captureStartBtn.textContent = 'Capture Start';
  captureStartBtn.disabled = !canProxy;
  captureStartBtn.addEventListener('click', () => {
    _dashboardProxyAction(cluster, 'Capture start', () =>
      _postProxy(cluster.uuid, '/api/orchestrator/clusters/{uuid}/capture/start', { intervalSeconds: 1.0 })
    );
  });
  actions.appendChild(captureStartBtn);

  const captureStopBtn = document.createElement('button');
  captureStopBtn.type = 'button';
  captureStopBtn.textContent = 'Capture Stop';
  captureStopBtn.disabled = !canProxy;
  captureStopBtn.addEventListener('click', () => {
    _dashboardProxyAction(cluster, 'Capture stop', () =>
      _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cluster.uuid)}/capture/stop`, {})
    );
  });
  actions.appendChild(captureStopBtn);

  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.textContent = 'Close App';
  closeBtn.disabled = !canProxy;
  closeBtn.addEventListener('click', () => {
    _dashboardProxyAction(cluster, 'Close app', () =>
      _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cluster.uuid)}/app/close`, {})
    );
  });
  actions.appendChild(closeBtn);

  card.appendChild(header);
  card.appendChild(meta);
  card.appendChild(triggers);
  if (error.textContent) {
    card.appendChild(error);
  }
  card.appendChild(actions);

  return card;
}

async function _renderDashboardCards() {
  if (!dashboardClusterCardsEl) return;
  const clusters = Array.isArray(_cachedClusters) ? _cachedClusters : [];
  dashboardClusterCardsEl.textContent = '';

  if (clusters.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'clusterEmpty';
    empty.textContent = 'No clusters registered yet.';
    dashboardClusterCardsEl.appendChild(empty);
    return;
  }

  const tasks = clusters.map(c => _loadDashboardClusterStatus(c));
  const results = await Promise.all(tasks);
  for (const info of results) {
    dashboardClusterCardsEl.appendChild(_buildDashboardClusterCard(info));
  }
}

async function dashboardRefresh() {
  _setManageStatus('Refreshing dashboard...');
  await refreshClusters(_selectedClusterUuid());
  await _renderDashboardCards();
  _setManageStatus('Dashboard updated.');
}

function _setCctvStatus(text) {
  if (!cctvStatusEl) return;
  cctvStatusEl.textContent = String(text ?? '');
}

function _cctvIntervalSeconds() {
  const raw = String(cctvIntervalEl?.value || '').trim();
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return 0.5;
  return Math.max(0.1, n);
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

function _ensureCctvCards() {
  if (!cctvGridEl) return;
  const clusters = Array.isArray(_cachedClusters) ? _cachedClusters : [];
  const key = clusters.map(c => String(c?.uuid ?? '')).join('|');
  if (key === _cctvLayoutKey) return;
  _cctvLayoutKey = key;

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
    const pillInfo = _cctvPillInfo('idle');
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

    const status = document.createElement('div');
    status.className = 'cctvMeta';
    status.textContent = 'Idle';

    card.appendChild(header);
    card.appendChild(meta);
    card.appendChild(img);
    card.appendChild(status);

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
    if (!_cctvActive) return;
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

function _closeAllCctvStreams() {
  for (const [cu, stream] of _cctvStreams.entries()) {
    stream.close();
    _cctvStreams.delete(cu);
  }
}

function _syncCctvStreams() {
  if (!_cctvActive) return;
  const clusters = Array.isArray(_cachedClusters) ? _cachedClusters : [];
  const activeSet = new Set(clusters.map(c => String(c?.uuid ?? '')));

  for (const [cu] of _cctvStreams.entries()) {
    if (!activeSet.has(cu)) {
      _closeCctvStream(cu);
    }
  }

  for (const cluster of clusters) {
    const cu = String(cluster?.uuid ?? '').trim();
    if (!cu) continue;
    if (!cluster?.baseUrl) {
      _updateCctvCardState(cu, 'no-url', '');
      continue;
    }
    if (_isDuplicateCluster(cluster)) {
      _updateCctvCardState(cu, 'duplicate', '');
      continue;
    }
    _startCctvStream(cluster);
  }
}

async function cctvStart() {
  _ensureCctvCards();
  const clusters = Array.isArray(_cachedClusters) ? _cachedClusters : [];
  if (clusters.length === 0) {
    _setCctvStatus('No clusters available.');
    return;
  }
  const interval = _cctvIntervalSeconds();
  _setCctvStatus('Starting CCTV (SSE)...');
  _cctvActive = true;
  _closeAllCctvStreams();

  const tasks = clusters.map(async (c) => {
    if (!c?.baseUrl || _isDuplicateCluster(c)) return;
    try {
      await _postProxy(c.uuid, '/api/orchestrator/clusters/{uuid}/capture/start', { intervalSeconds: interval });
    } catch (err) {
      _updateCctvCardState(c.uuid, 'error', '');
    }
  });
  await Promise.all(tasks);
  _syncCctvStreams();
  _setCctvStatus(`Running at ${interval}s interval (SSE).`);
}

async function cctvStop() {
  _cctvActive = false;
  _closeAllCctvStreams();
  const clusters = Array.isArray(_cachedClusters) ? _cachedClusters : [];
  _setCctvStatus('Stopping CCTV...');
  const tasks = clusters.map(async (c) => {
    if (!c?.baseUrl || _isDuplicateCluster(c)) return;
    try {
      await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(c.uuid)}/capture/stop`, {});
    } catch {
      // Best-effort stop.
    }
  });
  await Promise.all(tasks);
  _setCctvStatus('Stopped.');
  for (const c of clusters) {
    _updateCctvCardState(c.uuid, 'stopped', '');
  }
}

function _selectedClusterIsDuplicate() {
  const cu = _selectedClusterUuid();
  const selected = (Array.isArray(_cachedClusters) ? _cachedClusters : []).find(
    x => String(x?.uuid ?? '') === String(cu)
  ) || null;
  if (!selected) return false;
  const su = _serverUuidOf(selected);
  if (!su) return false;
  return (_dupCountByServerUuid.get(su) || 0) > 1;
}

function _setProxyControlsEnabled(enabled) {
  const items = [
    btnAppLaunchEl,
    btnAppAttachEl,
    btnAppCloseEl,
    btnCaptureStartEl,
    btnCaptureStopEl,
    btnActionsFetchEl,
    btnActionRunEl,
    btnActionRemoveEl,
    btnActionUpsertEl,
    btnConditionsFetchEl,
    btnConditionsStatusEl,
    btnConditionsSendEl,
    btnTriggersFetchEl,
    btnTriggersStatusEl,
    btnTriggersSendEl,
    btnTriggerApplyEnabledEl,
    btnTriggerRemoveEl,
  ];
  for (const el of items) {
    if (!el) continue;
    el.disabled = !enabled;
  }
}

function _applyDuplicateUiState() {
  const isDup = _selectedClusterIsDuplicate();
  _setProxyControlsEnabled(!isDup);
  if (isDup) {
    _setManageStatus('Duplicate server UUID detected. Resolve duplicates to enable proxy actions.');
  }
}

function _setClusterEditorFromSelected() {
  const cu = _selectedClusterUuid();
  const selected = (Array.isArray(_cachedClusters) ? _cachedClusters : []).find(x => String(x?.uuid ?? '') === String(cu)) || null;
  if (clusterMetaEl) clusterMetaEl.textContent = _fmtClusterMeta(selected);
  if (!selected) {
    if (editClusterLabelEl) editClusterLabelEl.value = '';
    if (editClusterBaseUrlEl) editClusterBaseUrlEl.value = '';
    return;
  }
  if (editClusterLabelEl) editClusterLabelEl.value = String(selected.label ?? '');
  if (editClusterBaseUrlEl) editClusterBaseUrlEl.value = String(selected.baseUrl ?? '');
}

async function _loadAppDefaultsForSelectedCluster() {
  const cu = _selectedClusterUuid();
  if (!cu) return;
  if (_selectedClusterIsDuplicate()) return;

  try {
    const data = await _getJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/app/defaults`);
    const d = (data && typeof data === 'object') ? data : {};

    const defaultAppPath = String(d.defaultAppPath ?? d.appPath ?? d.path ?? '');
    const defaultWindowTitle = String(d.defaultWindowTitle ?? d.programName ?? d.windowTitle ?? '');

    if (appLaunchPathEl) appLaunchPathEl.value = defaultAppPath;
    if (appAttachTitleEl) appAttachTitleEl.value = defaultWindowTitle;
  } catch (err) {
    // Not fatal; cluster might be offline or older version.
    _setManageStatus(`App defaults unavailable: ${err?.message ?? err}`);
  }
}

async function refreshClusters(selectUuid = null) {
  if (!clusterSelectEl) return;
  _setManageStatus('Loading clusters...');
  try {
    const resp = await _getJson('/api/orchestrator/clusters');
    const clusters = resp && Array.isArray(resp.clusters) ? resp.clusters : [];
    _cachedClusters = clusters;
    if (dashboardClustersEl) _fillTextArea(dashboardClustersEl, resp);
    _dupCountByServerUuid = new Map();
    for (const c of clusters) {
      const su = _serverUuidOf(c);
      if (!su) continue;
      _dupCountByServerUuid.set(su, (_dupCountByServerUuid.get(su) || 0) + 1);
    }

    clusterSelectEl.textContent = '';
    for (const c of clusters) {
      const su = _serverUuidOf(c);
      const dupCount = su ? (_dupCountByServerUuid.get(su) || 0) : 0;
      const opt = document.createElement('option');
      opt.value = String(c.uuid ?? '');
      const baseLabel = String(c.label ?? c.uuid ?? '');
      opt.textContent = dupCount > 1 ? `${baseLabel} [DUP x${dupCount}]` : baseLabel;
      clusterSelectEl.appendChild(opt);
    }

    if (selectUuid) {
      clusterSelectEl.value = String(selectUuid);
    }

    _setClusterEditorFromSelected();
    await _loadAppDefaultsForSelectedCluster();
    _setManageStatus('Ready.');
    _applyDuplicateUiState();
    _ensureCctvCards();
    if (_cctvActive) {
      _syncCctvStreams();
    }
  } catch (err) {
    _setManageStatus(`Failed to load clusters: ${err?.message ?? err}`);
  }
}

async function saveSelectedCluster() {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');

  const label = String(editClusterLabelEl?.value || '').trim();
  const baseUrl = String(editClusterBaseUrlEl?.value || '').trim();
  if (!label) return _setManageStatus('Label is required.');

  _setManageStatus('Saving cluster...');
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/update`, {
      label,
      baseUrl: baseUrl, // allow empty string to clear baseUrl
    });
    _setManageStatus('Saved.');
    await refreshClusters(cu);
  } catch (err) {
    _setManageStatus(`Save failed: ${err?.message ?? err}`);
  }
}

async function removeSelectedCluster() {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');

  _setManageStatus('Removing cluster...');
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/remove`, {});
    _setManageStatus('Removed.');
    await refreshClusters(null);
  } catch (err) {
    _setManageStatus(`Remove failed: ${err?.message ?? err}`);
  }
}

function _numOrDefault(el, d) {
  const raw = String(el?.value ?? '').trim();
  if (!raw) return d;
  const n = Number(raw);
  return Number.isFinite(n) ? Math.floor(n) : d;
}

function _appGeometryPayload() {
  return {
    left: _numOrDefault(appLeftEl, 0),
    top: _numOrDefault(appTopEl, 0),
    width: _numOrDefault(appWidthEl, 640),
    height: _numOrDefault(appHeightEl, 480),
  };
}

async function appLaunch() {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  const app_path = String(appLaunchPathEl?.value || '').trim();
  if (!app_path) return _setManageStatus('App path is required.');
  _setManageStatus('Launching app on cluster...');
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/app/launch', { app_path, ..._appGeometryPayload() });
    _setManageStatus('App launched.');
  } catch (err) {
    _setManageStatus(`Launch failed: ${err?.message ?? err}`);
  }
}

async function appAttach() {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  const window_title = String(appAttachTitleEl?.value || '').trim();
  if (!window_title) return _setManageStatus('Window title is required.');
  _setManageStatus('Attaching app window on cluster...');
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/app/attach', { window_title, ..._appGeometryPayload() });
    _setManageStatus('App attached.');
  } catch (err) {
    _setManageStatus(`Attach failed: ${err?.message ?? err}`);
  }
}

async function appClose() {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  _setManageStatus('Closing app on cluster...');
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/app/close`, {});
    _setManageStatus('App closed.');
  } catch (err) {
    _setManageStatus(`Close failed: ${err?.message ?? err}`);
  }
}

async function captureStart() {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  _setManageStatus('Starting capture on cluster...');
  try {
    // Use the cluster default interval (1s) unless you later add an input.
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/capture/start', { intervalSeconds: 1.0 });
    _setManageStatus('Capture started.');
  } catch (err) {
    _setManageStatus(`Start capture failed: ${err?.message ?? err}`);
  }
}

async function captureStop() {
  const cu = _selectedClusterUuid();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_selectedClusterIsDuplicate()) return _setManageStatus('Duplicate server UUID detected.');
  _setManageStatus('Stopping capture on cluster...');
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/capture/stop`, {});
    _setManageStatus('Capture stopped.');
  } catch (err) {
    _setManageStatus(`Stop capture failed: ${err?.message ?? err}`);
  }
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
    if (dashboardAssignmentsEl) _fillTextArea(dashboardAssignmentsEl, data);
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
  const label = String(clusterLabelEl?.value || '').trim();
  const baseUrl = String(clusterBaseUrlEl?.value || '').trim();

  if (!baseUrl) {
    _setStatus('Cluster address is required (IP:port or http://host:port).');
    return;
  }

  _setStatus('Registering...');

  const payload = { baseUrl, label: label ? label : null };

  try {
    const result = await _postJson('/api/orchestrator/clusters/commission_from_url', payload);
    const cluster = result && result.cluster ? result.cluster : null;
    if (cluster && cluster.uuid) {
      _setStatus(`Registered: ${cluster.label} (${cluster.uuid})`);
      await refreshClusters(String(cluster.uuid));
    } else {
      _setStatus('Registered.');
      await refreshClusters(_selectedClusterUuid());
    }
  } catch (err) {
    _setStatus(`Failed: ${err?.message ?? err}`);
  }
}

if (btnCommissionEl) {
  btnCommissionEl.addEventListener('click', () => {
    commissionCluster();
  });
}

if (btnRefreshClustersEl) {
  btnRefreshClustersEl.addEventListener('click', () => {
    refreshClusters(_selectedClusterUuid());
  });
}

if (btnDashboardRefreshEl) {
  btnDashboardRefreshEl.addEventListener('click', () => {
    dashboardRefresh();
    configAssignmentsFetch();
  });
}

if (btnCctvStartEl) btnCctvStartEl.addEventListener('click', () => cctvStart());
if (btnCctvStopEl) btnCctvStopEl.addEventListener('click', () => cctvStop());

if (clusterSelectEl) {
  clusterSelectEl.addEventListener('change', () => {
    _setClusterEditorFromSelected();
    _loadAppDefaultsForSelectedCluster();
    _applyDuplicateUiState();
  });
}

if (btnClusterSaveEl) btnClusterSaveEl.addEventListener('click', () => saveSelectedCluster());
if (btnClusterRemoveEl) btnClusterRemoveEl.addEventListener('click', () => removeSelectedCluster());
if (btnAppLaunchEl) btnAppLaunchEl.addEventListener('click', () => appLaunch());
if (btnAppAttachEl) btnAppAttachEl.addEventListener('click', () => appAttach());
if (btnAppCloseEl) btnAppCloseEl.addEventListener('click', () => appClose());
if (btnCaptureStartEl) btnCaptureStartEl.addEventListener('click', () => captureStart());
if (btnCaptureStopEl) btnCaptureStopEl.addEventListener('click', () => captureStop());

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

for (const el of [clusterLabelEl, clusterBaseUrlEl]) {
  if (!el) continue;
  el.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      commissionCluster();
    }
  });
}

_setStatus('Ready.');
_setCctvStatus('Stopped.');

_tabInit();
_subTabInit();
dashboardRefresh();
screensLayoutsFetch(null);
screensAssignmentsFetch();
configsFetch(null);
configAssignmentsFetch();
_setManageStatus('Ready.');
