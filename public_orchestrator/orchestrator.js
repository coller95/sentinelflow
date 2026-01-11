const clusterLabelEl = document.getElementById('clusterLabel');
const clusterBaseUrlEl = document.getElementById('clusterBaseUrl');
const btnCommissionEl = document.getElementById('btnCommission');
const regStatusEl = document.getElementById('regStatus');

const clusterSelectEl = document.getElementById('clusterSelect');
const btnRefreshClustersEl = document.getElementById('btnRefreshClusters');
const clusterMetaEl = document.getElementById('clusterMeta');

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

let _cachedClusters = [];
let _cachedActions = [];
let _cachedConditions = [];
let _cachedTriggers = [];
let _dupCountByServerUuid = new Map();

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
  const tabs = Array.from(document.querySelectorAll('.orchTabs button'));
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

_tabInit();
refreshClusters(null);
_setManageStatus('Ready.');
