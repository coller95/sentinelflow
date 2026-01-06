const appPathEl = document.getElementById('appPath');
const windowTitleEl = document.getElementById('windowTitle');
const statusEl = document.getElementById('status');

const windowLeftEl = document.getElementById('windowLeft');
const windowTopEl = document.getElementById('windowTop');
const windowWidthEl = document.getElementById('windowWidth');
const windowHeightEl = document.getElementById('windowHeight');

const btnLaunch = document.getElementById('btnLaunch');
const btnAttach = document.getElementById('btnAttach');
const btnClose = document.getElementById('btnClose');

const btnStartCapture = document.getElementById('btnStartCapture');
const btnStopCapture = document.getElementById('btnStopCapture');
const captureImage = document.getElementById('captureImage');
const captureIntervalEl = document.getElementById('captureInterval');
const roiOverlay = document.getElementById('roiOverlay');

const livePreviewFrameEl = document.getElementById('livePreviewFrame');
const livePreviewViewportEl = document.getElementById('livePreviewViewport');
const btnPanToggle = document.getElementById('btnPanToggle');
const btnZoomOut = document.getElementById('btnZoomOut');
const btnZoomIn = document.getElementById('btnZoomIn');

const keyNameEl = document.getElementById('keyName');
const btnSendKey = document.getElementById('btnSendKey');

const clickXEl = document.getElementById('clickX');
const clickYEl = document.getElementById('clickY');
const btnSendClick = document.getElementById('btnSendClick');

const btnRefreshConditions = document.getElementById('btnRefreshConditions');
const condTableBody = document.getElementById('condTableBody');

const btnRefreshActions = document.getElementById('btnRefreshActions');
const actionTableBody = document.getElementById('actionTableBody');
const btnActionNew = document.getElementById('btnActionNew');
const btnActionDelete = document.getElementById('btnActionDelete');
const btnActionRun = document.getElementById('btnActionRun');
const btnActionSave = document.getElementById('btnActionSave');
const actionNameEl = document.getElementById('actionName');
const actionStepsEl = document.getElementById('actionSteps');
const actionStepListEl = document.getElementById('actionStepList');
const btnActionStepUp = document.getElementById('btnActionStepUp');
const btnActionStepDown = document.getElementById('btnActionStepDown');
const actionStepTypeEl = document.getElementById('actionStepType');
const btnActionAddStep = document.getElementById('btnActionAddStep');
const btnActionRemoveStep = document.getElementById('btnActionRemoveStep');
const actionDelayRowEl = document.getElementById('actionDelayRow');
const actionDelayMsEl = document.getElementById('actionDelayMs');

const btnRefreshTriggers = document.getElementById('btnRefreshTriggers');
const triggerTableBody = document.getElementById('triggerTableBody');
const btnTriggerNew = document.getElementById('btnTriggerNew');
const btnTriggerDelete = document.getElementById('btnTriggerDelete');
const btnTriggerSave = document.getElementById('btnTriggerSave');
const triggerNameEl = document.getElementById('triggerName');
const triggerEnabledEl = document.getElementById('triggerEnabled');
const triggerActionEl = document.getElementById('triggerAction');
const triggerCriteriaBody = document.getElementById('triggerCriteriaBody');
const btnTriggerAddCriteria = document.getElementById('btnTriggerAddCriteria');

const btnRefreshTriggerStatus = document.getElementById('btnRefreshTriggerStatus');
const triggerStatusTableBody = document.getElementById('triggerStatusTableBody');

let _triggerStatusEventSource = null;
let _triggerStatusLastErrorAt = 0;
const _triggerStatusLastFireByUuid = new Map(); // uuid -> lastFireUnix

const btnCondAddRow = document.getElementById('btnCondAddRow');
const btnCondRemoveRow = document.getElementById('btnCondRemoveRow');
const btnCondMoveUp = document.getElementById('btnCondMoveUp');
const btnCondMoveDown = document.getElementById('btnCondMoveDown');
const btnSetFromLive = document.getElementById('btnSetFromLive');
const conditionNameEl = document.getElementById('conditionName');
const conditionTypeEl = document.getElementById('conditionType');
const roiXEl = document.getElementById('roiX');
const roiYEl = document.getElementById('roiY');
const roiWEl = document.getElementById('roiW');
const roiHEl = document.getElementById('roiH');
const templateImageEl = document.getElementById('templateImage');

let selectedConditionUuid = null;
let selectedActionUuid = null;
let selectedTriggerUuid = null;

let _actionKeyCaptureArmed = false;
let _actionClickCaptureArmed = false;
let _actionSteps = [];
let _selectedActionStepIndex = -1;
let _pendingAddKeyboardStep = false;
let _lastLiveSelectedPoint = null; // {x,y} from click-to-fill selection on live view

let _triggerCriteria = [];

let _cachedConditions = null;
let _cachedConditionsAt = 0;

const _triggerComparators = [
  'Equals',
  'NotEquals',
  'GreaterThan',
  'LessThan',
  'GreaterThanOrEqual',
  'LessThanOrEqual',
];

async function _loadActionsForSelect(selectEl, selectedUuid) {
  if (!selectEl) return;
  const items = await getJson('/api/actions');
  const safeItems = Array.isArray(items) ? items : [];
  selectEl.textContent = '';
  for (const a of safeItems) {
    const opt = document.createElement('option');
    opt.value = String(a.uuid ?? '');
    opt.textContent = String(a.name ?? '');
    selectEl.appendChild(opt);
  }
  if (selectedUuid) selectEl.value = String(selectedUuid);
}

async function _loadConditionsForSelect(selectEl, selectedUuid) {
  if (!selectEl) return;
  const safeItems = await _getConditionsCached();
  _fillConditionsSelect(selectEl, safeItems, selectedUuid);
}

async function _getConditionsCached(force = false) {
  const now = Date.now();
  if (!force && Array.isArray(_cachedConditions) && (now - _cachedConditionsAt) < 2000) {
    return _cachedConditions;
  }
  const items = await getJson('/api/conditions');
  _cachedConditions = Array.isArray(items) ? items : [];
  _cachedConditionsAt = now;
  return _cachedConditions;
}

function _fillConditionsSelect(selectEl, items, selectedUuid) {
  if (!selectEl) return;
  const safeItems = Array.isArray(items) ? items : [];
  selectEl.textContent = '';
  for (const c of safeItems) {
    const opt = document.createElement('option');
    opt.value = String(c.uuid ?? '');
    opt.textContent = String(c.name ?? '');
    selectEl.appendChild(opt);
  }
  if (selectedUuid) {
    selectEl.value = String(selectedUuid);
  }
}

function _renderTriggerCriteriaRows() {
  if (!triggerCriteriaBody) return;
  triggerCriteriaBody.textContent = '';

  const rows = Array.isArray(_triggerCriteria) ? _triggerCriteria : [];
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i] || {};
    const tr = document.createElement('tr');

    const tdCond = document.createElement('td');
    const selCond = document.createElement('select');
    selCond.className = 'selectLike';
    tdCond.appendChild(selCond);

    const tdComp = document.createElement('td');
    const selComp = document.createElement('select');
    selComp.className = 'selectLike';
    for (const c of _triggerComparators) {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      selComp.appendChild(opt);
    }
    tdComp.appendChild(selComp);

    const tdExp = document.createElement('td');
    const inpExp = document.createElement('input');
    inpExp.type = 'text';
    inpExp.placeholder = 'Example: 0.8';
    tdExp.appendChild(inpExp);

    const tdDel = document.createElement('td');
    const btnDel = document.createElement('button');
    btnDel.type = 'button';
    btnDel.textContent = 'X';
    tdDel.appendChild(btnDel);

    tr.appendChild(tdCond);
    tr.appendChild(tdComp);
    tr.appendChild(tdExp);
    tr.appendChild(tdDel);

    // Populate and bind.
    if (Array.isArray(_cachedConditions)) {
      _fillConditionsSelect(selCond, _cachedConditions, r.conditionUuid);
      if (!rows[i].conditionUuid) {
        rows[i].conditionUuid = String(selCond.value || '');
      }
    } else {
      _loadConditionsForSelect(selCond, r.conditionUuid).then(() => {
        // If caller didn't explicitly pick a condition UUID, the browser will
        // still default-select the first option. Persist that into state so
        // Save doesn't drop it.
        if (!rows[i].conditionUuid) {
          rows[i].conditionUuid = String(selCond.value || '');
        }
      }).catch(() => {});
    }
    selComp.value = String(r.comparator || 'Equals');
    inpExp.value = (r.expectedValue !== undefined && r.expectedValue !== null) ? String(r.expectedValue) : '';

    selCond.addEventListener('change', () => {
      rows[i].conditionUuid = String(selCond.value || '');
    });
    selComp.addEventListener('change', () => {
      rows[i].comparator = String(selComp.value || 'Equals');
    });
    inpExp.addEventListener('input', () => {
      rows[i].expectedValue = String(inpExp.value || '');
    });
    btnDel.addEventListener('click', () => {
      rows.splice(i, 1);
      _triggerCriteria = rows;
      _renderTriggerCriteriaRows();
    });

    triggerCriteriaBody.appendChild(tr);
  }
}

function _clearTriggerEditor() {
  selectedTriggerUuid = null;
  if (triggerNameEl) triggerNameEl.value = '';
  if (triggerEnabledEl) triggerEnabledEl.checked = false;
  _triggerCriteria = [];
  _renderTriggerCriteriaRows();
}

function _readTriggerCriteriaFromDom() {
  const out = [];
  if (!triggerCriteriaBody) return out;
  const trs = Array.from(triggerCriteriaBody.querySelectorAll('tr'));
  for (const tr of trs) {
    const selects = Array.from(tr.querySelectorAll('select'));
    const inp = tr.querySelector('input');
    const conditionUuid = selects[0] ? String(selects[0].value || '').trim() : '';
    const comparator = selects[1] ? String(selects[1].value || 'Equals') : 'Equals';
    const expectedValue = inp ? String(inp.value || '').trim() : '';
    if (!conditionUuid) continue;
    out.push({ conditionUuid, comparator, expectedValue });
  }
  return out;
}

function _applyTriggerToEditor(t) {
  if (!t) return;
  selectedTriggerUuid = String(t.uuid ?? '');
  if (triggerNameEl) triggerNameEl.value = String(t.name ?? '');
  if (triggerEnabledEl) triggerEnabledEl.checked = !!t.enabled;
  if (triggerActionEl) triggerActionEl.value = String(t.action ?? '');
  _triggerCriteria = Array.isArray(t.triggerCiterias) ? t.triggerCiterias.map((c) => ({
    conditionUuid: String(c.conditionUuid ?? ''),
    comparator: String(c.comparator ?? 'Equals'),
    expectedValue: (c.expectedValue !== undefined && c.expectedValue !== null) ? String(c.expectedValue) : '',
  })) : [];
  _renderTriggerCriteriaRows();
}

async function refreshTriggers() {
  if (!triggerTableBody) return;
  const [triggers, actions] = await Promise.all([
    getJson('/api/triggers'),
    getJson('/api/actions'),
  ]);
  const safeItems = Array.isArray(triggers) ? triggers : [];
  const safeActions = Array.isArray(actions) ? actions : [];

  const actionNameByUuid = {};
  for (const a of safeActions) {
    const au = String(a.uuid ?? '');
    if (!au) continue;
    actionNameByUuid[au] = String(a.name ?? au);
  }

  triggerTableBody.textContent = '';
  for (const it of safeItems) {
    const tr = document.createElement('tr');
    tr.dataset.uuid = String(it.uuid ?? '');
    if (selectedTriggerUuid && String(it.uuid) === String(selectedTriggerUuid)) {
      tr.classList.add('selected');
    }

    const tdName = document.createElement('td');
    tdName.textContent = String(it.name ?? '');

    const tdEnabled = document.createElement('td');
    tdEnabled.textContent = it.enabled ? 'Yes' : 'No';

    const tdAction = document.createElement('td');
    const actionUuid = String(it.action ?? '');
    tdAction.textContent = actionNameByUuid[actionUuid] || actionUuid;

    const tdCount = document.createElement('td');
    tdCount.textContent = String(Array.isArray(it.triggerCiterias) ? it.triggerCiterias.length : 0);

    tr.appendChild(tdName);
    tr.appendChild(tdEnabled);
    tr.appendChild(tdAction);
    tr.appendChild(tdCount);

    tr.addEventListener('click', async () => {
      // Ensure selects are populated before applying.
      try {
        await _loadActionsForSelect(triggerActionEl, String(it.action ?? ''));
      } catch { }
      _applyTriggerToEditor(it);
      refreshTriggers().catch(() => {});
    });

    triggerTableBody.appendChild(tr);
  }

  // Also keep action select populated.
  _loadActionsForSelect(triggerActionEl, triggerActionEl ? triggerActionEl.value : '').catch(() => {});
}

function _fmtUnixSeconds(ts) {
  if (ts === null || ts === undefined) return '';
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return '';
  try {
    return new Date(n * 1000).toLocaleString();
  } catch {
    return String(n);
  }
}

function _fmtAgoSeconds(ts) {
  if (ts === null || ts === undefined) return '';
  const n = Number(ts);
  if (!Number.isFinite(n) || n <= 0) return '';
  const now = Date.now() / 1000;
  const dt = now - n;
  if (!Number.isFinite(dt)) return '';
  if (dt < 0) return 'in future';
  if (dt < 1) return 'just now';
  if (dt < 60) return `${dt.toFixed(1)}s ago`;
  if (dt < 3600) return `${(dt / 60).toFixed(1)}m ago`;
  return `${(dt / 3600).toFixed(1)}h ago`;
}

function _renderTriggerStatusFromPayload(payload) {
  if (!triggerStatusTableBody) return;
  const items = payload && Array.isArray(payload.items) ? payload.items : [];

  triggerStatusTableBody.textContent = '';
  for (const it of items) {
    const tr = document.createElement('tr');
    const uuid = String(it.uuid ?? '');
    tr.dataset.uuid = uuid;

    const tdName = document.createElement('td');
    tdName.textContent = String(it.name ?? '');

    const tdEnabled = document.createElement('td');
    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.checked = !!it.enabled;
    tdEnabled.appendChild(chk);

    const tdMet = document.createElement('td');
    tdMet.textContent = it.isMet ? 'Yes' : 'No';

    const tdLogic = document.createElement('td');
    tdLogic.style.whiteSpace = 'pre-line';
    const evalRows = Array.isArray(it.eval) ? it.eval : [];
    if (evalRows.length > 0) {
      for (const r of evalRows) {
        const line = document.createElement('div');
        const name = String(r.conditionName ?? r.conditionUuid ?? '');
        const last = (r.last === null || r.last === undefined) ? '' : String(r.last);
        const cmp = String(r.comparator ?? '');
        const exp = (r.expected === null || r.expected === undefined) ? '' : String(r.expected);
        const ok = !!r.ok;
        line.textContent = `${name}: ${last} ${cmp} ${exp} => ${ok ? 'OK' : 'FAIL'}`;
        tdLogic.appendChild(line);
      }
    } else {
      tdLogic.textContent = '';
    }

    const tdAction = document.createElement('td');
    tdAction.textContent = String(it.actionName ?? it.actionUuid ?? '');

    const tdRunning = document.createElement('td');
    tdRunning.textContent = it.actionIsRunning ? 'Yes' : 'No';

    const tdActionRuns = document.createElement('td');
    tdActionRuns.textContent = String(it.actionRunCount ?? 0);

    const tdFires = document.createElement('td');
    tdFires.textContent = String(it.fireCount ?? 0);

    const tdLastFire = document.createElement('td');
    const lastFireTs = it.lastFireUnix;
    const lastFireAbs = _fmtUnixSeconds(lastFireTs);
    const lastFireAgo = _fmtAgoSeconds(lastFireTs);
    if (lastFireAbs) {
      const d1 = document.createElement('div');
      d1.textContent = lastFireAbs;
      tdLastFire.appendChild(d1);
      if (lastFireAgo) {
        const d2 = document.createElement('div');
        d2.textContent = lastFireAgo;
        tdLastFire.appendChild(d2);
      }
    } else {
      tdLastFire.textContent = '';
    }

    const tdLastDone = document.createElement('td');
    tdLastDone.textContent = _fmtUnixSeconds(it.actionLastCompletedUnix);

    chk.addEventListener('change', async () => {
      const u = String(it.uuid ?? '').trim();
      if (!u) return;
      try {
        await postJson('/api/triggers/set_enabled', { uuid: u, enabled: !!chk.checked });
        // UI will update via SSE; keep this silent.
      } catch (e) {
        setStatus(`Set enabled failed: ${e.message}`, 'err');
        chk.checked = !!it.enabled;
      }
    });

    tr.appendChild(tdName);
    tr.appendChild(tdEnabled);
    tr.appendChild(tdMet);
    tr.appendChild(tdLogic);
    tr.appendChild(tdAction);
    tr.appendChild(tdRunning);
    tr.appendChild(tdActionRuns);
    tr.appendChild(tdFires);
    tr.appendChild(tdLastFire);
    tr.appendChild(tdLastDone);

    // Highlight when trigger just fired.
    const prevFire = _triggerStatusLastFireByUuid.get(uuid);
    const currFire = Number(it.lastFireUnix ?? 0);
    if (uuid && Number.isFinite(currFire) && currFire > 0) {
      if (prevFire !== undefined && Number(prevFire) !== currFire) {
        tr.classList.add('selected');
        setTimeout(() => {
          if (tr && tr.isConnected) tr.classList.remove('selected');
        }, 900);
      }
      _triggerStatusLastFireByUuid.set(uuid, currFire);
    }

    triggerStatusTableBody.appendChild(tr);
  }
}

async function refreshTriggerStatus() {
  if (!triggerStatusTableBody) return;

  const payload = await getJson('/api/triggers/status');
  _renderTriggerStatusFromPayload(payload);
}

function startTriggerStatusSse() {
  stopTriggerStatusSse();

  // Initial snapshot so the table isn't empty until the first seq bump.
  refreshTriggerStatus().catch(() => {});

  try {
    const es = new EventSource('/api/triggers/status/stream');
    _triggerStatusEventSource = es;

    es.addEventListener('status', (ev) => {
      try {
        const payload = JSON.parse(String(ev.data || '{}'));
        _renderTriggerStatusFromPayload(payload);
      } catch {
        // ignore malformed frames
      }
    });

    es.onerror = () => {
      const now = Date.now();
      if (now - _triggerStatusLastErrorAt > 3000) {
        _triggerStatusLastErrorAt = now;
        setStatus('Trigger Status SSE disconnected. Retrying...', 'err');
      }
    };
  } catch (e) {
    setStatus(`Trigger Status SSE failed: ${e.message}`, 'err');
  }
}

function stopTriggerStatusSse() {
  if (_triggerStatusEventSource) {
    try { _triggerStatusEventSource.close(); } catch { }
    _triggerStatusEventSource = null;
  }
}

if (btnRefreshTriggerStatus) {
  btnRefreshTriggerStatus.addEventListener('click', async () => {
    setStatus('Refreshing trigger status...', null);
    try {
      await refreshTriggerStatus();
      setStatus('Trigger status refreshed.', 'ok');
    } catch (e) {
      setStatus(`Refresh trigger status failed: ${e.message}`, 'err');
    }
  });
}

if (btnRefreshTriggers) {
  btnRefreshTriggers.addEventListener('click', async () => {
    setStatus('Refreshing triggers...', null);
    try {
      await _loadActionsForSelect(triggerActionEl, triggerActionEl ? triggerActionEl.value : '');
      await refreshTriggers();
      setStatus('Triggers refreshed.', 'ok');
    } catch (e) {
      setStatus(`Refresh triggers failed: ${e.message}`, 'err');
    }
  });
}

if (btnTriggerNew) {
  btnTriggerNew.addEventListener('click', async () => {
    _clearTriggerEditor();
    try {
      await _loadActionsForSelect(triggerActionEl, null);
    } catch { }
    setStatus('New trigger.', 'ok');
  });
}

if (btnTriggerAddCriteria) {
  btnTriggerAddCriteria.addEventListener('click', async () => {
    if (!Array.isArray(_triggerCriteria)) _triggerCriteria = [];
    const conds = await _getConditionsCached(true);
    if (!Array.isArray(conds) || conds.length === 0) {
      setStatus('No Conditions available. Add a Condition first.', 'err');
      return;
    }
    const defaultUuid = String(conds[0].uuid ?? '').trim();
    _triggerCriteria.push({ conditionUuid: defaultUuid, comparator: 'Equals', expectedValue: '' });
    _renderTriggerCriteriaRows();
    setStatus('Criteria added.', 'ok');
  });
}

if (btnTriggerSave) {
  btnTriggerSave.addEventListener('click', async () => {
    setStatus('Saving trigger...', null);
    try {
      const name = (triggerNameEl && triggerNameEl.value ? String(triggerNameEl.value) : '').trim();
      if (!name) throw new Error('Name is required');
      const actionUuid = triggerActionEl ? String(triggerActionEl.value || '').trim() : '';
      if (!actionUuid) throw new Error('Action is required');

      const enabled = triggerEnabledEl ? !!triggerEnabledEl.checked : false;

      // Source of truth: read from DOM so async select-population can't drop rows.
      const citerias = _readTriggerCriteriaFromDom();
      _triggerCriteria = citerias;

      const domRowCount = triggerCriteriaBody ? triggerCriteriaBody.querySelectorAll('tr').length : 0;
      if (domRowCount > 0 && citerias.length === 0) {
        throw new Error('Criteria rows exist but no Condition is selected. Create/refresh Conditions first, then select a Condition for each criteria.');
      }

      const payload = { name, enabled, action: actionUuid, triggerCiterias: citerias };
      if (selectedTriggerUuid) payload.uuid = selectedTriggerUuid;

      const res = await postJson('/api/triggers/upsert', payload);
      if (res && res.uuid) selectedTriggerUuid = String(res.uuid);

      await refreshTriggers();
      setStatus('Trigger saved.', 'ok');
    } catch (e) {
      setStatus(`Save trigger failed: ${e.message}`, 'err');
    }
  });
}

if (btnTriggerDelete) {
  btnTriggerDelete.addEventListener('click', async () => {
    if (!selectedTriggerUuid) {
      setStatus('Select a trigger first.', 'err');
      return;
    }
    setStatus('Deleting trigger...', null);
    try {
      await postJson('/api/triggers/remove_uuid', { uuid: selectedTriggerUuid });
      _clearTriggerEditor();
      await refreshTriggers();
      setStatus('Trigger deleted.', 'ok');
    } catch (e) {
      setStatus(`Delete trigger failed: ${e.message}`, 'err');
    }
  });
}

function _setDelayRowVisible(visible) {
  if (!actionDelayRowEl) return;
  actionDelayRowEl.style.display = visible ? '' : 'none';
}

function _getDelayMsFromInput() {
  const raw = actionDelayMsEl ? String(actionDelayMsEl.value || '').trim() : '';
  const ms = Number(raw);
  if (!Number.isFinite(ms) || ms < 0) {
    throw new Error('Delay ms must be a number >= 0');
  }
  return Math.round(ms);
}

function normalizeKeyNameFromEvent(ev) {
  const key = String(ev.key || '');
  const code = String(ev.code || '');

  // Prefer readable names that backend understands.
  if (key.length === 1) {
    // For letters, uppercase; for digits/symbols, keep as-is.
    const ch = key;
    return /^[a-z]$/i.test(ch) ? ch.toUpperCase() : ch;
  }

  // Function keys
  if (/^F\d{1,2}$/i.test(key)) return key.toUpperCase();
  if (/^F\d{1,2}$/i.test(code)) return code.toUpperCase();

  // Common named keys
  const map = {
    Enter: 'Enter',
    Escape: 'Esc',
    Tab: 'Tab',
    ' ': 'Space',
    Spacebar: 'Space',
    Backspace: 'Backspace',
    Delete: 'Delete',
    Insert: 'Insert',
    Home: 'Home',
    End: 'End',
    PageUp: 'PageUp',
    PageDown: 'PageDown',
    ArrowLeft: 'ArrowLeft',
    ArrowRight: 'ArrowRight',
    ArrowUp: 'ArrowUp',
    ArrowDown: 'ArrowDown',
    Shift: ev.location === 2 ? 'RShift' : 'LShift',
    Control: ev.location === 2 ? 'RCtrl' : 'LCtrl',
    Alt: ev.location === 2 ? 'RAlt' : 'LAlt',
  };
  if (map[key]) return map[key];

  // Fallback: use key string.
  return key;
}

function _actionKindOf(step) {
  const raw = step && typeof step === 'object' ? String(step.action ?? '') : '';
  if (!raw) return '';
  if (raw === 'Keyboard') return 'KeyStroke';
  return raw;
}

function _formatStepLabel(step) {
  const kind = _actionKindOf(step);
  const p = step && typeof step === 'object' ? (step.parameters ?? {}) : {};

  if (kind === 'Click') {
    const x = Number(p.x ?? p.xNormalized ?? 0);
    const y = Number(p.y ?? p.yNormalized ?? 0);
    const fx = Number.isFinite(x) ? x : 0;
    const fy = Number.isFinite(y) ? y : 0;
    return `Click at (${fx.toFixed(6)}, ${fy.toFixed(6)})`;
  }

  if (kind === 'KeyStroke') {
    const k = String(p.keyName ?? p.key ?? '').trim();
    const kk = k || '?';
    return `Press "${kk}"`;
  }

  if (kind === 'Delay') {
    let ms = Number(p.ms);
    if (!Number.isFinite(ms)) {
      const seconds = Number(p.seconds);
      ms = Number.isFinite(seconds) ? (seconds * 1000.0) : 0;
    }
    const mm = Math.max(0, Math.round(Number.isFinite(ms) ? ms : 0));
    return `Delay ${mm}ms`;
  }

  return String(kind || 'Step');
}

function _syncHiddenActionStepsTextarea() {
  if (!actionStepsEl) return;
  actionStepsEl.value = safeJsonStringify(_actionSteps);
}

function _selectActionStep(index) {
  const n = Array.isArray(_actionSteps) ? _actionSteps.length : 0;
  if (n <= 0) {
    _selectedActionStepIndex = -1;
  } else {
    _selectedActionStepIndex = Math.max(0, Math.min(n - 1, index));
  }
  _renderActionStepList();
}

function _renderActionStepList() {
  if (!actionStepListEl) return;

  actionStepListEl.textContent = '';
  const steps = Array.isArray(_actionSteps) ? _actionSteps : [];

  for (let i = 0; i < steps.length; i++) {
    const div = document.createElement('div');
    div.className = 'actionStepItem' + (i === _selectedActionStepIndex ? ' selected' : '');
    div.textContent = _formatStepLabel(steps[i]);
    div.addEventListener('click', () => {
      _selectActionStep(i);
    });

    div.addEventListener('dblclick', () => {
      _selectActionStep(i);

      const step = _actionSteps && Array.isArray(_actionSteps) ? _actionSteps[i] : null;
      const kind = _actionKindOf(step);

      if (kind === 'KeyStroke') {
        _pendingAddKeyboardStep = false;
        _actionKeyCaptureArmed = true;
        setStatus('Press a key to edit Keyboard step...', 'ok');
        return;
      }

      if (kind === 'Click') {
        const pt = _lastLiveSelectedPoint;
        if (!pt || !Number.isFinite(pt.x) || !Number.isFinite(pt.y)) {
          alert('No point selected. Click on the live view to select a point first.');
          setStatus('No point selected for Click step.', 'err');
          return;
        }
        step.parameters = step.parameters && typeof step.parameters === 'object' ? step.parameters : {};
        step.parameters.x = Number(pt.x);
        step.parameters.y = Number(pt.y);
        _syncHiddenActionStepsTextarea();
        _renderActionStepList();
        setStatus('Click step updated from selected point.', 'ok');
        return;
      }

      if (kind === 'Delay') {
        if (actionStepTypeEl) actionStepTypeEl.value = 'Delay';
        _setDelayRowVisible(true);
        let currentMs = (step && step.parameters && typeof step.parameters === 'object') ? Number(step.parameters.ms) : NaN;
        if (!Number.isFinite(currentMs)) {
          const sec = (step && step.parameters && typeof step.parameters === 'object') ? Number(step.parameters.seconds) : NaN;
          currentMs = Number.isFinite(sec) ? (sec * 1000.0) : 500;
        }
        if (actionDelayMsEl) {
          actionDelayMsEl.value = String(Math.max(0, Math.round(currentMs)));
          actionDelayMsEl.focus();
          actionDelayMsEl.select();
        }
        setStatus('Edit Delay: change ms and press Enter.', 'ok');
        return;
      }
    });

    actionStepListEl.appendChild(div);
  }
}

function _setActionStepsFromValue(value) {
  const rawSteps = Array.isArray(value) ? value : [];
  const out = [];
  for (const s of rawSteps) {
    if (!s || typeof s !== 'object') continue;
    const kind = _actionKindOf(s);
    if (!kind) continue;
    const parameters = (s.parameters && typeof s.parameters === 'object') ? s.parameters : {};
    if (kind === 'Delay') {
      // Normalize legacy {seconds} into {ms} for consistency.
      const ms = Number(parameters.ms);
      const seconds = Number(parameters.seconds);
      const normalizedMs = Number.isFinite(ms) ? ms : (Number.isFinite(seconds) ? seconds * 1000.0 : 0);
      out.push({ action: kind, parameters: { ms: Math.max(0, Math.round(normalizedMs)) } });
    } else {
      out.push({ action: kind, parameters: { ...parameters } });
    }
  }
  _actionSteps = out;
  _selectedActionStepIndex = out.length ? 0 : -1;
  _renderActionStepList();
  _syncHiddenActionStepsTextarea();
}

function _getActionStepsForSave() {
  if (actionStepListEl) return Array.isArray(_actionSteps) ? _actionSteps : [];
  return parseActionStepsFromEditor();
}

let captureEvents = null;
let conditionsEvents = null;
// Click-to-fill coordinates; send via button.

function setBusy(isBusy) {
  btnLaunch.disabled = isBusy;
  btnAttach.disabled = isBusy;
  btnClose.disabled = isBusy;
}

function setStatus(message, kind) {
  statusEl.textContent = message || '';
  statusEl.classList.remove('ok', 'err');
  if (kind) statusEl.classList.add(kind);
}

function safeJsonStringify(value) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
}

function parseActionStepsFromEditor() {
  const raw = (actionStepsEl && actionStepsEl.value ? String(actionStepsEl.value) : '').trim();
  if (!raw) return [];

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error('Steps must be valid JSON');
  }

  if (!Array.isArray(parsed)) {
    throw new Error('Steps JSON must be an array');
  }

  // Minimal shape validation; backend will validate further.
  for (const s of parsed) {
    if (!s || typeof s !== 'object') throw new Error('Each step must be an object');
    if (!('action' in s)) throw new Error('Each step must have an action');
    if (!('parameters' in s)) s.parameters = {};
  }

  return parsed;
}

function clearActionEditor() {
  selectedActionUuid = null;
  if (actionNameEl) actionNameEl.value = '';
  if (actionStepsEl) actionStepsEl.value = '';
  _actionSteps = [];
  _selectedActionStepIndex = -1;
  _renderActionStepList();
}

function applyActionToEditor(action) {
  if (!action) return;
  selectedActionUuid = String(action.uuid ?? '');
  if (actionNameEl) actionNameEl.value = String(action.name ?? '');
  _setActionStepsFromValue(action.steps ?? []);
}

async function refreshActions() {
  if (!actionTableBody) return;
  const items = await getJson('/api/actions');
  const safeItems = Array.isArray(items) ? items : [];

  actionTableBody.textContent = '';

  for (const it of safeItems) {
    const tr = document.createElement('tr');
    tr.dataset.uuid = String(it.uuid ?? '');
    if (selectedActionUuid && String(it.uuid) === String(selectedActionUuid)) {
      tr.classList.add('selected');
    }

    const tdName = document.createElement('td');
    tdName.textContent = String(it.name ?? '');

    const tdSteps = document.createElement('td');
    const steps = Array.isArray(it.steps) ? it.steps : [];
    tdSteps.textContent = String(steps.length);

    tr.appendChild(tdName);
    tr.appendChild(tdSteps);

    tr.addEventListener('click', () => {
      applyActionToEditor(it);
      refreshActions().catch(() => {});
    });

    actionTableBody.appendChild(tr);
  }
}

if (btnRefreshActions) {
  btnRefreshActions.addEventListener('click', async () => {
    setStatus('Refreshing actions...', null);
    try {
      await refreshActions();
      setStatus('Actions refreshed.', 'ok');
    } catch (e) {
      setStatus(`Refresh actions failed: ${e.message}`, 'err');
    }
  });
}

if (btnActionNew) {
  btnActionNew.addEventListener('click', () => {
    clearActionEditor();
    setStatus('New action.', 'ok');
  });
}

if (btnActionAddStep) {
  btnActionAddStep.addEventListener('click', () => {
    const t = actionStepTypeEl ? String(actionStepTypeEl.value || '') : 'Keyboard';
    const typeNorm = t.trim();
    if (!Array.isArray(_actionSteps)) _actionSteps = [];

    if (typeNorm === 'Keyboard') {
      _actionKeyCaptureArmed = true;
      _pendingAddKeyboardStep = true;
      setStatus('Press a key to add Keyboard step...', 'ok');
      return;
    }

    if (typeNorm === 'Click') {
      const pt = _lastLiveSelectedPoint;
      if (!pt || !Number.isFinite(pt.x) || !Number.isFinite(pt.y)) {
        alert('No point selected. Click on the live view to select a point first.');
        setStatus('No point selected for Click step.', 'err');
        return;
      }
      _actionSteps.push({ action: 'Click', parameters: { x: Number(pt.x), y: Number(pt.y) } });
      _syncHiddenActionStepsTextarea();
      _selectActionStep(_actionSteps.length - 1);
      setStatus('Click step added from selected point.', 'ok');
      return;
    }

    if (typeNorm === 'Delay') {
      let ms;
      try {
        ms = _getDelayMsFromInput();
      } catch (e) {
        alert(e.message);
        return;
      }
      _actionSteps.push({ action: 'Delay', parameters: { ms } });
      _syncHiddenActionStepsTextarea();
      _selectActionStep(_actionSteps.length - 1);
      setStatus('Delay step added.', 'ok');
      return;
    }

    setStatus('Unknown step type.', 'err');
  });
}

if (btnActionRemoveStep) {
  btnActionRemoveStep.addEventListener('click', () => {
    const i = _selectedActionStepIndex;
    if (!Array.isArray(_actionSteps) || i < 0 || i >= _actionSteps.length) {
      setStatus('Select a step first.', 'err');
      return;
    }
    _actionSteps.splice(i, 1);
    _syncHiddenActionStepsTextarea();
    _selectActionStep(Math.min(i, _actionSteps.length - 1));
    setStatus('Step removed.', 'ok');
  });
}

if (btnActionStepUp) {
  btnActionStepUp.addEventListener('click', () => {
    const i = _selectedActionStepIndex;
    if (!Array.isArray(_actionSteps) || i <= 0 || i >= _actionSteps.length) return;
    const tmp = _actionSteps[i - 1];
    _actionSteps[i - 1] = _actionSteps[i];
    _actionSteps[i] = tmp;
    _syncHiddenActionStepsTextarea();
    _selectActionStep(i - 1);
  });
}

if (btnActionStepDown) {
  btnActionStepDown.addEventListener('click', () => {
    const i = _selectedActionStepIndex;
    if (!Array.isArray(_actionSteps) || i < 0 || i >= _actionSteps.length - 1) return;
    const tmp = _actionSteps[i + 1];
    _actionSteps[i + 1] = _actionSteps[i];
    _actionSteps[i] = tmp;
    _syncHiddenActionStepsTextarea();
    _selectActionStep(i + 1);
  });
}

document.addEventListener('keydown', (ev) => {
  if (!_actionKeyCaptureArmed) return;

  // Don't capture while typing in normal inputs unless they explicitly armed capture.
  ev.preventDefault();
  ev.stopPropagation();

  const keyName = normalizeKeyNameFromEvent(ev);
  _actionKeyCaptureArmed = false;

  if (_pendingAddKeyboardStep) {
    _pendingAddKeyboardStep = false;
    if (!Array.isArray(_actionSteps)) _actionSteps = [];
    _actionSteps.push({ action: 'KeyStroke', parameters: { keyName } });
    _syncHiddenActionStepsTextarea();
    _selectActionStep(_actionSteps.length - 1);
    setStatus(`Added Keyboard step: ${keyName}`, 'ok');
    return;
  }

  const i = _selectedActionStepIndex;
  if (!Array.isArray(_actionSteps) || i < 0 || i >= _actionSteps.length) {
    setStatus(`Captured: ${keyName} (no step selected)`, 'ok');
    return;
  }

  const step = _actionSteps[i];
  if (_actionKindOf(step) !== 'KeyStroke') {
    setStatus(`Captured: ${keyName} (select a Keyboard step)`, 'ok');
    return;
  }

  step.parameters = step.parameters && typeof step.parameters === 'object' ? step.parameters : {};
  step.parameters.keyName = keyName;
  _syncHiddenActionStepsTextarea();
  _renderActionStepList();
  setStatus(`Captured: ${keyName}`, 'ok');
}, { capture: true });

if (actionStepTypeEl) {
  const updateDelayVisibility = () => {
    const t = String(actionStepTypeEl.value || '').trim();
    _setDelayRowVisible(t === 'Delay');
    if (t === 'Delay' && actionDelayMsEl) actionDelayMsEl.focus();
  };
  actionStepTypeEl.addEventListener('change', updateDelayVisibility);
  updateDelayVisibility();
}

if (actionDelayMsEl) {
  actionDelayMsEl.addEventListener('keydown', (ev) => {
    if (ev.key !== 'Enter') return;
    ev.preventDefault();
    ev.stopPropagation();

    let ms;
    try {
      ms = _getDelayMsFromInput();
    } catch (e) {
      alert(e.message);
      return;
    }

    const i = _selectedActionStepIndex;
    if (Array.isArray(_actionSteps) && i >= 0 && i < _actionSteps.length && _actionKindOf(_actionSteps[i]) === 'Delay') {
      const step = _actionSteps[i];
      step.parameters = step.parameters && typeof step.parameters === 'object' ? step.parameters : {};
      delete step.parameters.seconds;
      step.parameters.ms = ms;
      _syncHiddenActionStepsTextarea();
      _renderActionStepList();
      setStatus('Delay step updated.', 'ok');
      return;
    }

    // If no Delay step is selected, Enter behaves like Add Step for Delay.
    if (!Array.isArray(_actionSteps)) _actionSteps = [];
    _actionSteps.push({ action: 'Delay', parameters: { ms } });
    _syncHiddenActionStepsTextarea();
    _selectActionStep(_actionSteps.length - 1);
    setStatus('Delay step added.', 'ok');
  });
}

if (btnActionSave) {
  btnActionSave.addEventListener('click', async () => {
    setStatus('Saving action...', null);
    try {
      const name = (actionNameEl && actionNameEl.value ? String(actionNameEl.value) : '').trim();
      if (!name) throw new Error('Name is required');
      const steps = _getActionStepsForSave();

      const payload = { name, steps };
      if (selectedActionUuid) payload.uuid = selectedActionUuid;

      const res = await postJson('/api/actions/upsert', payload);
      if (res && res.uuid) selectedActionUuid = String(res.uuid);

      await refreshActions();
      setStatus('Action saved.', 'ok');
    } catch (e) {
      setStatus(`Save action failed: ${e.message}`, 'err');
    }
  });
}

if (btnActionDelete) {
  btnActionDelete.addEventListener('click', async () => {
    if (!selectedActionUuid) {
      setStatus('Select an action first.', 'err');
      return;
    }
    setStatus('Deleting action...', null);
    try {
      await postJson('/api/actions/remove_uuid', { uuid: selectedActionUuid });
      clearActionEditor();
      await refreshActions();
      setStatus('Action deleted.', 'ok');
    } catch (e) {
      setStatus(`Delete action failed: ${e.message}`, 'err');
    }
  });
}

if (btnActionRun) {
  btnActionRun.addEventListener('click', async () => {
    if (!selectedActionUuid) {
      setStatus('Select an action first.', 'err');
      return;
    }
    setStatus('Running action...', null);
    try {
      await postJson('/api/actions/run', { uuid: selectedActionUuid });
      setStatus('Action enqueued.', 'ok');
    } catch (e) {
      setStatus(`Run action failed: ${e.message}`, 'err');
    }
  });
}

async function postJson(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : '{}'
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

async function getJson(path) {
  const res = await fetch(path, { method: 'GET' });
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

function readWindowGeometry() {
  const left = Number((windowLeftEl.value || '').trim() || '0');
  const top = Number((windowTopEl.value || '').trim() || '0');
  const width = Number((windowWidthEl.value || '').trim() || '640');
  const height = Number((windowHeightEl.value || '').trim() || '480');

  if (!Number.isFinite(left) || !Number.isFinite(top) || !Number.isFinite(width) || !Number.isFinite(height)) {
    throw new Error('Window geometry must be valid numbers');
  }
  if (width <= 0 || height <= 0) {
    throw new Error('Window width/height must be > 0');
  }

  return {
    left: Math.trunc(left),
    top: Math.trunc(top),
    width: Math.trunc(width),
    height: Math.trunc(height)
  };
}

btnLaunch.addEventListener('click', async () => {
  const app_path = (appPathEl.value || '').trim();
  if (!app_path) {
    setStatus('Enter an app path (or command) first.', 'err');
    return;
  }
  setBusy(true);
  setStatus('Launching...', null);
  try {
    const geo = readWindowGeometry();
    await postJson('/api/app/launch', { app_path, ...geo });
    setStatus('Launch OK.', 'ok');
  } catch (e) {
    setStatus(`Launch failed: ${e.message}`, 'err');
  } finally {
    setBusy(false);
  }
});

btnAttach.addEventListener('click', async () => {
  const window_title = (windowTitleEl.value || '').trim();
  if (!window_title) {
    setStatus('Enter a window title first.', 'err');
    return;
  }
  setBusy(true);
  setStatus('Attaching...', null);
  try {
    const geo = readWindowGeometry();
    await postJson('/api/app/attach', { window_title, ...geo });
    setStatus('Attach OK.', 'ok');
  } catch (e) {
    setStatus(`Attach failed: ${e.message}`, 'err');
  } finally {
    setBusy(false);
  }
});

btnClose.addEventListener('click', async () => {
  setBusy(true);
  setStatus('Closing...', null);
  try {
    await postJson('/api/app/close');
    setStatus('Close OK.', 'ok');
  } catch (e) {
    setStatus(`Close failed: ${e.message}`, 'err');
  } finally {
    setBusy(false);
  }
});

function stopEventSource() {
  if (captureEvents) {
    captureEvents.close();
    captureEvents = null;
  }
}

function stopConditionsEventSource() {
  if (conditionsEvents) {
    conditionsEvents.close();
    conditionsEvents = null;
  }
}

function startEventSource() {
  stopEventSource();
  captureEvents = new EventSource('/api/capture/stream?fmt=jpg&quality=70');

  captureEvents.addEventListener('frame', (ev) => {
    // Directly set the image from SSE payload (base64 jpg).
    captureImage.src = `data:image/jpeg;base64,${ev.data}`;
  });

  captureEvents.onerror = () => {
    // EventSource auto-reconnects; keep UI simple.
    setStatus('Live preview disconnected (retrying)...', 'err');
  };
}

function clamp01(v) {
  if (v < 0) return 0;
  if (v > 1) return 1;
  return v;
}

function read01(el, label) {
  const raw = (el && el.value ? String(el.value) : '').trim();
  const val = Number(raw);
  if (!Number.isFinite(val)) {
    throw new Error(`${label} must be a number`);
  }
  if (val < 0 || val > 1) {
    throw new Error(`${label} must be between 0 and 1`);
  }
  return val;
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.onload = () => resolve(String(reader.result || ''));
    reader.readAsDataURL(file);
  });
}

function getNormalizedPointFromMouseEvent(ev) {
  const rect = (roiOverlay || captureImage).getBoundingClientRect();
    
    const nw = captureImage.naturalWidth;
    const nh = captureImage.naturalHeight;

    if (!nw || !nh || rect.width <= 0 || rect.height <= 0) {
        return { 
            x: clamp01((ev.clientX - rect.left) / rect.width), 
            y: clamp01((ev.clientY - rect.top) / rect.height) 
        };
    }

    const elementRatio = rect.width / rect.height;
    const imageRatio = nw / nh;

    let renderWidth, renderHeight;
    let offsetX = 0;
    let offsetY = 0;

    if (elementRatio > imageRatio) {
        renderHeight = rect.height;
        renderWidth = rect.height * imageRatio;
        offsetX = (rect.width - renderWidth) / 2;
    } else {
        renderWidth = rect.width;
        renderHeight = rect.width / imageRatio;
        offsetY = (rect.height - renderHeight) / 2;
    }

    const clientX = ev.clientX - rect.left;
    const clientY = ev.clientY - rect.top;

    const imageX = clientX - offsetX;
    const imageY = clientY - offsetY;

    const x = clamp01(imageX / renderWidth);
    const y = clamp01(imageY / renderHeight);

    return { x, y };
}

function tryParseRgb(color) {
  const m = String(color || '').match(/rgba?\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([0-9.]+))?\)/i);
  if (!m) return null;
  return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]) };
}

function rgbaFromComputedColor(alpha) {
  const rgb = tryParseRgb(getComputedStyle(document.body).color);
  if (!rgb) return `rgba(255,255,255,${alpha})`;
  return `rgba(${rgb.r},${rgb.g},${rgb.b},${alpha})`;
}

function ensureOverlayCanvasSize() {
  if (!roiOverlay) return;
  const w = Math.max(1, Math.floor(roiOverlay.clientWidth));
  const h = Math.max(1, Math.floor(roiOverlay.clientHeight));
  if (roiOverlay.width !== w) roiOverlay.width = w;
  if (roiOverlay.height !== h) roiOverlay.height = h;
}

function getRenderedImageBox() {
  const rect = (roiOverlay || captureImage).getBoundingClientRect();
  const nw = captureImage.naturalWidth;
  const nh = captureImage.naturalHeight;
  const elementW = rect.width;
  const elementH = rect.height;

  if (!nw || !nh || elementW <= 0 || elementH <= 0) {
    return { renderWidth: elementW, renderHeight: elementH, offsetX: 0, offsetY: 0 };
  }

  const elementRatio = elementW / elementH;
  const imageRatio = nw / nh;

  let renderWidth, renderHeight;
  let offsetX = 0;
  let offsetY = 0;

  if (elementRatio > imageRatio) {
    renderHeight = elementH;
    renderWidth = elementH * imageRatio;
    offsetX = (elementW - renderWidth) / 2;
  } else {
    renderWidth = elementW;
    renderHeight = elementW / imageRatio;
    offsetY = (elementH - renderHeight) / 2;
  }

  return { renderWidth, renderHeight, offsetX, offsetY };
}

function drawOverlayRoi(roi) {
  if (!roiOverlay) return;
  ensureOverlayCanvasSize();
  const ctx = roiOverlay.getContext('2d');
  if (!ctx) return;

  ctx.clearRect(0, 0, roiOverlay.width, roiOverlay.height);
  if (!roi) return;

  const { renderWidth, renderHeight, offsetX, offsetY } = getRenderedImageBox();
  if (renderWidth <= 0 || renderHeight <= 0) return;

  const x1 = offsetX + roi.x * renderWidth;
  const y1 = offsetY + roi.y * renderHeight;
  const x2 = offsetX + (roi.x + roi.w) * renderWidth;
  const y2 = offsetY + (roi.y + roi.h) * renderHeight;

  const left = Math.min(x1, x2);
  const top = Math.min(y1, y2);
  const width = Math.abs(x2 - x1);
  const height = Math.abs(y2 - y1);

  ctx.fillStyle = rgbaFromComputedColor(0.15);
  ctx.strokeStyle = rgbaFromComputedColor(0.9);
  ctx.lineWidth = 1;
  ctx.fillRect(left, top, width, height);
  ctx.strokeRect(left + 1, top + 1, Math.max(0, width - 2), Math.max(0, height - 2));

  if (_activeRoiHandle) {
    ctx.save();
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = rgbaFromComputedColor(0.7);
    ctx.lineWidth = 1;
    ctx.strokeRect(left + 4, top + 4, Math.max(0, width - 8), Math.max(0, height - 8));
    ctx.restore();
  }

  // Handles
  const handleFill = rgbaFromComputedColor(0.85);
  const handleStroke = rgbaFromComputedColor(1.0);
  const activeFill = rgbaFromComputedColor(1.0);
  const size = 6;
  const activeSize = 12;

  function drawHandle(px, py, isActive) {
    const s = isActive ? activeSize : size;
    const x = Math.round(px - s / 2);
    const y = Math.round(py - s / 2);
    ctx.fillStyle = isActive ? activeFill : handleFill;
    ctx.strokeStyle = handleStroke;
    ctx.lineWidth = isActive ? 2 : 1;
    ctx.fillRect(x, y, s, s);
    ctx.strokeRect(x + 0.5, y + 0.5, s - 1, s - 1);
  }

  const midX = left + width / 2;
  const midY = top + height / 2;
  const handles = [
    { key: 'nw', x: left, y: top },
    { key: 'n', x: midX, y: top },
    { key: 'ne', x: left + width, y: top },
    { key: 'w', x: left, y: midY },
    { key: 'e', x: left + width, y: midY },
    { key: 'sw', x: left, y: top + height },
    { key: 's', x: midX, y: top + height },
    { key: 'se', x: left + width, y: top + height },
  ];

  for (const h of handles) {
    drawHandle(h.x, h.y, _activeRoiHandle === h.key);
  }
}

let _roiDrag = null; // {start:{x,y}, current:{x,y}, roi:{x,y,w,h}}
let _lastRoi = null;
let _activeRoiHandle = null; // 'nw'|'n'|'ne'|'w'|'e'|'sw'|'s'|'se'|'move'|null

let _liveZoom = 1.0;
let _livePan = { x: 0, y: 0 };
let _panMode = false;
let _panDrag = null; // { sx, sy, startPanX, startPanY }

function clamp(v, lo, hi) {
  return Math.min(hi, Math.max(lo, v));
}

function applyLiveViewTransform() {
  if (!livePreviewFrameEl || !livePreviewViewportEl) return;

  const rect = livePreviewFrameEl.getBoundingClientRect();
  const frameW = rect.width;
  const frameH = rect.height;
  if (!(frameW > 0 && frameH > 0)) return;

  const scale = _liveZoom;
  const viewportW = frameW * scale;
  const viewportH = frameH * scale;

  // Center + pan offsets.
  const baseLeft = (frameW - viewportW) / 2;
  const baseTop = (frameH - viewportH) / 2;

  let left = baseLeft + _livePan.x;
  let top = baseTop + _livePan.y;

  const minLeft = frameW - viewportW;
  const minTop = frameH - viewportH;

  // Clamp so you can't pan past edges and reveal empty space.
  left = clamp(left, minLeft, 0);
  top = clamp(top, minTop, 0);

  // Store back normalized pan relative to centered base.
  _livePan.x = left - baseLeft;
  _livePan.y = top - baseTop;

  livePreviewViewportEl.style.width = `${scale * 100}%`;
  livePreviewViewportEl.style.height = `${scale * 100}%`;
  livePreviewViewportEl.style.left = `${left}px`;
  livePreviewViewportEl.style.top = `${top}px`;

  ensureOverlayCanvasSize();
  if (_lastRoi) drawOverlayRoi(_lastRoi);
}

function setPanMode(enabled) {
  _panMode = !!enabled;
  if (livePreviewFrameEl) {
    livePreviewFrameEl.classList.toggle('panMode', _panMode);
    livePreviewFrameEl.classList.remove('panning');
  }
  if (btnPanToggle) btnPanToggle.classList.toggle('primary', _panMode);
  _panDrag = null;
}

function zoomBy(factor) {
  const prev = _liveZoom;
  const next = clamp(prev * factor, 1.0, 8.0);
  if (next === prev) return;

  // Keep pan roughly proportional to the zoom change.
  const ratio = next / prev;
  _livePan.x *= ratio;
  _livePan.y *= ratio;
  _liveZoom = next;
  applyLiveViewTransform();
}

if (btnPanToggle) {
  btnPanToggle.addEventListener('click', () => {
    setPanMode(!_panMode);
  });
}

if (btnZoomIn) {
  btnZoomIn.addEventListener('click', () => {
    zoomBy(1.25);
  });
}

if (btnZoomOut) {
  btnZoomOut.addEventListener('click', () => {
    zoomBy(1 / 1.25);
  });
}

function setRoiInputsFromNormalized(roi) {
  if (!roiXEl || !roiYEl || !roiWEl || !roiHEl) return;
  roiXEl.value = roi.x.toFixed(3);
  roiYEl.value = roi.y.toFixed(3);
  roiWEl.value = roi.w.toFixed(3);
  roiHEl.value = roi.h.toFixed(3);
}

function finalizeRoiOrClick(startPt, endPt) {
  const x = Math.min(startPt.x, endPt.x);
  const y = Math.min(startPt.y, endPt.y);
  const w = Math.abs(endPt.x - startPt.x);
  const h = Math.abs(endPt.y - startPt.y);

  // Treat tiny drags as clicks (keeps existing click-to-fill behavior).
  if (w < 0.005 && h < 0.005) {
    clickXEl.value = startPt.x.toFixed(3);
    clickYEl.value = startPt.y.toFixed(3);
    _lastLiveSelectedPoint = { x: Number(startPt.x), y: Number(startPt.y) };
    setStatus(`Selected (${startPt.x.toFixed(3)}, ${startPt.y.toFixed(3)})`, 'ok');
    return;
  }

  const roi = { x, y, w, h };
  _lastRoi = roi;
  _activeRoiHandle = 'se';
  setRoiInputsFromNormalized(roi);
  drawOverlayRoi(roi);
  setStatus(`ROI set: (${x.toFixed(3)}, ${y.toFixed(3)}) ${w.toFixed(3)}×${h.toFixed(3)}`, 'ok');
}

function getOverlayLocalPoint(ev) {
  const rect = (roiOverlay || captureImage).getBoundingClientRect();
  return { x: ev.clientX - rect.left, y: ev.clientY - rect.top, rect };
}

function getRoiPixelRect(roi) {
  const { renderWidth, renderHeight, offsetX, offsetY } = getRenderedImageBox();
  const left = offsetX + roi.x * renderWidth;
  const top = offsetY + roi.y * renderHeight;
  const width = roi.w * renderWidth;
  const height = roi.h * renderHeight;
  return { left, top, width, height, renderWidth, renderHeight, offsetX, offsetY };
}

function pickHandleFromPointer(ev, roi) {
  if (!roiOverlay || !roi) return null;
  ensureOverlayCanvasSize();
  const ctx = roiOverlay.getContext('2d');
  if (!ctx) return null;

  const { x: px, y: py } = getOverlayLocalPoint(ev);
  const r = getRoiPixelRect(roi);
  const left = r.left;
  const top = r.top;
  const right = r.left + r.width;
  const bottom = r.top + r.height;

  const midX = (left + right) / 2;
  const midY = (top + bottom) / 2;

  const candidates = [
    { key: 'nw', x: left, y: top },
    { key: 'n', x: midX, y: top },
    { key: 'ne', x: right, y: top },
    { key: 'w', x: left, y: midY },
    { key: 'e', x: right, y: midY },
    { key: 'sw', x: left, y: bottom },
    { key: 's', x: midX, y: bottom },
    { key: 'se', x: right, y: bottom },
  ];

  const threshold = 10;
  let best = null;
  let bestD2 = Infinity;
  for (const c of candidates) {
    const dx = px - c.x;
    const dy = py - c.y;
    const d2 = dx * dx + dy * dy;
    if (d2 < bestD2) {
      bestD2 = d2;
      best = c;
    }
  }

  if (best && bestD2 <= threshold * threshold) return best.key;

  // If inside the ROI but not near a handle, allow moving the ROI with arrows.
  if (px >= left && px <= right && py >= top && py <= bottom) return 'move';
  return null;
}

function normalizeRoi(roi) {
  const nw = captureImage.naturalWidth || 0;
  const nh = captureImage.naturalHeight || 0;
  const minW = nw > 0 ? (1 / nw) : 0.001;
  const minH = nh > 0 ? (1 / nh) : 0.001;

  let x = Number(roi.x);
  let y = Number(roi.y);
  let w = Number(roi.w);
  let h = Number(roi.h);

  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(w) || !Number.isFinite(h)) {
    return { x: 0, y: 0, w: minW, h: minH };
  }

  w = Math.max(w, minW);
  h = Math.max(h, minH);
  x = Math.max(0, x);
  y = Math.max(0, y);

  if (x + w > 1) w = 1 - x;
  if (y + h > 1) h = 1 - y;

  w = Math.max(w, minW);
  h = Math.max(h, minH);

  if (x + w > 1) x = 1 - w;
  if (y + h > 1) y = 1 - h;

  x = clamp01(x);
  y = clamp01(y);
  w = Math.max(minW, Math.min(1 - x, w));
  h = Math.max(minH, Math.min(1 - y, h));

  return { x, y, w, h };
}

function nudgeRoi(handle, dx, dy) {
  if (!_lastRoi) return;
  let { x, y, w, h } = _lastRoi;

  switch (handle) {
    case 'move':
      x += dx; y += dy;
      break;
    case 'n':
      y += dy; h -= dy;
      break;
    case 's':
      h += dy;
      break;
    case 'w':
      x += dx; w -= dx;
      break;
    case 'e':
      w += dx;
      break;
    case 'nw':
      x += dx; w -= dx;
      y += dy; h -= dy;
      break;
    case 'ne':
      w += dx;
      y += dy; h -= dy;
      break;
    case 'sw':
      x += dx; w -= dx;
      h += dy;
      break;
    case 'se':
      w += dx;
      h += dy;
      break;
  }

  const roi = normalizeRoi({ x, y, w, h });
  _lastRoi = roi;
  setRoiInputsFromNormalized(roi);
  drawOverlayRoi(roi);
}

const roiEventTarget = roiOverlay || captureImage;

roiEventTarget.addEventListener('mousedown', (ev) => {
  if (ev.button !== 0) return;
  try {
    if (_actionClickCaptureArmed) {
      const pt = getNormalizedPointFromMouseEvent(ev);
      _actionClickCaptureArmed = false;

      const i = _selectedActionStepIndex;
      if (!Array.isArray(_actionSteps) || i < 0 || i >= _actionSteps.length) {
        setStatus('Captured click (no step selected).', 'ok');
      } else {
        const step = _actionSteps[i];
        if (_actionKindOf(step) !== 'Click') {
          setStatus('Captured click (select a Click step).', 'ok');
        } else {
          step.parameters = step.parameters && typeof step.parameters === 'object' ? step.parameters : {};
          step.parameters.x = Number(pt.x);
          step.parameters.y = Number(pt.y);
          _syncHiddenActionStepsTextarea();
          _renderActionStepList();
          setStatus(`Captured click: (${pt.x.toFixed(6)}, ${pt.y.toFixed(6)})`, 'ok');
        }
      }

      ev.preventDefault();
      ev.stopPropagation();
      return;
    }

    if (_panMode) {
      _panDrag = {
        sx: ev.clientX,
        sy: ev.clientY,
        startPanX: _livePan.x,
        startPanY: _livePan.y,
      };
      if (livePreviewFrameEl) livePreviewFrameEl.classList.add('panning');
      ev.preventDefault();
      return;
    }

    if (_lastRoi && roiOverlay) {
      const picked = pickHandleFromPointer(ev, _lastRoi);
      if (picked) {
        _activeRoiHandle = picked;
        _roiDrag = null;
        roiOverlay.focus();
        drawOverlayRoi(_lastRoi);
        setStatus(`ROI handle selected: ${picked}`, 'ok');
        ev.preventDefault();
        return;
      }
    }

    _activeRoiHandle = null;
    const pt = getNormalizedPointFromMouseEvent(ev);
    _roiDrag = { start: pt, current: pt };
    drawOverlayRoi({ x: pt.x, y: pt.y, w: 0, h: 0 });
  } catch {
    // ignore
  }
});

roiEventTarget.addEventListener('mousemove', (ev) => {
  if (_panDrag) {
    const dx = ev.clientX - _panDrag.sx;
    const dy = ev.clientY - _panDrag.sy;
    _livePan.x = _panDrag.startPanX + dx;
    _livePan.y = _panDrag.startPanY + dy;
    applyLiveViewTransform();
    ev.preventDefault();
    return;
  }
  if (!_roiDrag) return;
  try {
    const pt = getNormalizedPointFromMouseEvent(ev);
    _roiDrag.current = pt;
    const x = Math.min(_roiDrag.start.x, pt.x);
    const y = Math.min(_roiDrag.start.y, pt.y);
    const w = Math.abs(pt.x - _roiDrag.start.x);
    const h = Math.abs(pt.y - _roiDrag.start.y);
    drawOverlayRoi({ x, y, w, h });
  } catch {
    // ignore
  }
});

function endDrag(ev) {
  if (_panDrag) {
    _panDrag = null;
    if (livePreviewFrameEl) livePreviewFrameEl.classList.remove('panning');
    return;
  }
  if (!_roiDrag) return;
  try {
    const pt = getNormalizedPointFromMouseEvent(ev);
    finalizeRoiOrClick(_roiDrag.start, pt);
  } catch (e) {
    setStatus(`ROI select failed: ${e.message}`, 'err');
  } finally {
    _roiDrag = null;
  }
}

roiEventTarget.addEventListener('mouseup', endDrag);
roiEventTarget.addEventListener('mouseleave', (ev) => {
  // If the user drags out, finalize at last known point.
  if (_roiDrag) endDrag(ev);
});

captureImage.addEventListener('load', () => {
  applyLiveViewTransform();
  ensureOverlayCanvasSize();
  if (_lastRoi) drawOverlayRoi(_lastRoi);
});

window.addEventListener('resize', () => {
  applyLiveViewTransform();
  ensureOverlayCanvasSize();
  if (_lastRoi) drawOverlayRoi(_lastRoi);
});

document.addEventListener('keydown', (ev) => {
  if (!_lastRoi || !_activeRoiHandle) return;
  const tag = (document.activeElement && document.activeElement.tagName) ? document.activeElement.tagName.toLowerCase() : '';
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

  const nw = captureImage.naturalWidth || 0;
  const nh = captureImage.naturalHeight || 0;
  const stepX = nw > 0 ? (1 / nw) : 0.001;
  const stepY = nh > 0 ? (1 / nh) : 0.001;
  const mult = ev.shiftKey ? 10 : 1;

  let dx = 0;
  let dy = 0;

  if (ev.key === 'ArrowLeft') dx = -stepX * mult;
  else if (ev.key === 'ArrowRight') dx = stepX * mult;
  else if (ev.key === 'ArrowUp') dy = -stepY * mult;
  else if (ev.key === 'ArrowDown') dy = stepY * mult;
  else return;

  nudgeRoi(_activeRoiHandle, dx, dy);
  ev.preventDefault();
});

btnStartCapture.addEventListener('click', async () => {
  setStatus('Starting capture...', null);
  try {
    const raw = (captureIntervalEl.value || '').trim();
    const intervalSeconds = raw ? Number(raw) : 1;
    if (!Number.isFinite(intervalSeconds) || intervalSeconds <= 0) {
      throw new Error('Refresh interval must be a number > 0');
    }

    await postJson('/api/capture/start', { intervalSeconds });
    startEventSource();
    setStatus('Capture started (SSE).', 'ok');
  } catch (e) {
    setStatus(`Start capture failed: ${e.message}`, 'err');
  }
});

btnStopCapture.addEventListener('click', async () => {
  setStatus('Stopping capture...', null);
  try {
    await postJson('/api/capture/stop');
    stopEventSource();
    captureImage.removeAttribute('src');
    setStatus('Capture stopped.', 'ok');
  } catch (e) {
    setStatus(`Stop capture failed: ${e.message}`, 'err');
  }
});

async function sendKeyOnce() {
  const keyName = (keyNameEl.value || '').trim();
  if (!keyName) {
    throw new Error('Enter a key name first');
  }
  await postJson('/api/control/key', { keyName });
}

btnSendKey.addEventListener('click', async () => {
  setStatus('Sending key...', null);
  try {
    await sendKeyOnce();
    setStatus('Key enqueued.', 'ok');
  } catch (e) {
    setStatus(`Send key failed: ${e.message}`, 'err');
  }
});

keyNameEl.addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter') {
    ev.preventDefault();
    btnSendKey.click();
  }
});

window.addEventListener('beforeunload', () => {
  stopEventSource();
  stopConditionsEventSource();
});

function readClickXY() {
  const x = Number((clickXEl.value || '').trim());
  const y = Number((clickYEl.value || '').trim());
  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    throw new Error('Click X/Y must be numbers');
  }
  if (x < 0 || x > 1 || y < 0 || y > 1) {
    throw new Error('Click X/Y must be between 0 and 1');
  }
  return { x, y };
}

btnSendClick.addEventListener('click', async () => {
  setStatus('Sending click...', null);
  try {
    const pt = readClickXY();
    await postJson('/api/control/click', pt);
    setStatus('Click enqueued.', 'ok');
  } catch (e) {
    setStatus(`Send click failed: ${e.message}`, 'err');
  }
});

async function refreshConditions() {
  if (!condTableBody) return;

  const payload = await getJson('/api/conditions/status');
  const items = coerceConditionStatusItems(payload);

  condTableBody.textContent = '';

  const safeItems = Array.isArray(items) ? items : [];
  for (const it of safeItems) {
    const tr = document.createElement('tr');
    tr.dataset.uuid = String(it.uuid ?? '');
    if (selectedConditionUuid && String(it.uuid) === String(selectedConditionUuid)) {
      tr.classList.add('selected');
    }

    const tdName = document.createElement('td');
    tdName.textContent = String(it.name ?? '');

    const tdType = document.createElement('td');
    tdType.textContent = String(it.type ?? '');

    const tdTpl = document.createElement('td');
    const tplImg = document.createElement('img');
    tplImg.className = 'thumb';
    if (it.templateThumbBase64) {
      tplImg.src = `data:image/jpeg;base64,${it.templateThumbBase64}`;
    }
    tdTpl.appendChild(tplImg);

    const tdCrop = document.createElement('td');
    const cropImg = document.createElement('img');
    cropImg.className = 'thumb';
    if (it.cropThumbBase64) {
      cropImg.src = `data:image/jpeg;base64,${it.cropThumbBase64}`;
    }
    tdCrop.appendChild(cropImg);

    const tdLast = document.createElement('td');
    tdLast.textContent = (it.last === null || it.last === undefined) ? '' : String(it.last);

    tr.appendChild(tdName);
    tr.appendChild(tdType);
    tr.appendChild(tdTpl);
    tr.appendChild(tdCrop);
    tr.appendChild(tdLast);

    tr.addEventListener('click', () => {
      selectedConditionUuid = String(it.uuid ?? '');
      refreshConditions().catch(() => {});
      loadSelectedConditionIntoEditor().catch(() => {});
    });

    condTableBody.appendChild(tr);
  }
}

function coerceConditionStatusItems(payload) {
  // New shape: { order: [uuid...], byUuid: {uuid: {...}} }
  // Old shape: [ {...}, {...} ]
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== 'object') return [];

  const byUuid = (payload.byUuid && typeof payload.byUuid === 'object') ? payload.byUuid : null;
  if (!byUuid) return [];

  const order = Array.isArray(payload.order) ? payload.order.map(String) : Object.keys(byUuid);

  const out = [];
  for (const uuid of order) {
    const it = byUuid[uuid];
    if (!it) continue;
    // Ensure uuid is present for render/selection logic.
    out.push({ uuid: String(uuid), ...(typeof it === 'object' ? it : {}) });
  }
  return out;
}

let _conditionEditorLoadSeq = 0;

function clearSelectedConditionEditor() {
  if (conditionNameEl) conditionNameEl.value = '';
  if (conditionTypeEl) conditionTypeEl.value = 'ImageMatchRoi';
  if (templateImageEl) templateImageEl.value = '';

  if (roiXEl) roiXEl.value = '0';
  if (roiYEl) roiYEl.value = '0';
  if (roiWEl) roiWEl.value = '0';
  if (roiHEl) roiHEl.value = '0';

  _lastRoi = null;
  _activeRoiHandle = null;
  drawOverlayRoi(null);
}

function applyConditionItemToEditor(item) {
  if (!item) return;

  if (conditionNameEl) conditionNameEl.value = String(item.name ?? '');
  if (conditionTypeEl) conditionTypeEl.value = String(item.type ?? 'ImageMatchRoi');

  // Security restriction: browsers won't allow setting a file input programmatically.
  // Clear any previously chosen file so it's not accidentally reused.
  if (templateImageEl) templateImageEl.value = '';

  const roiDto = item.roi || {};
  const roi = {
    x: Number(roiDto.xNormalized ?? 0),
    y: Number(roiDto.yNormalized ?? 0),
    w: Number(roiDto.widthNormalized ?? 0),
    h: Number(roiDto.heightNormalized ?? 0),
  };

  _lastRoi = roi;
  _activeRoiHandle = null;
  setRoiInputsFromNormalized(roi);
  drawOverlayRoi(roi);
}

async function loadSelectedConditionIntoEditor() {
  const uuid = selectedConditionUuid;
  if (!uuid) {
    clearSelectedConditionEditor();
    return;
  }

  const seq = ++_conditionEditorLoadSeq;
  const items = await getJson('/api/conditions');
  if (seq !== _conditionEditorLoadSeq) return;

  const safeItems = Array.isArray(items) ? items : [];
  const found = safeItems.find((it) => String(it.uuid ?? '') === String(uuid));
  if (!found) {
    clearSelectedConditionEditor();
    return;
  }
  applyConditionItemToEditor(found);
}

function startConditionsEventSource() {
  stopConditionsEventSource();
  if (!condTableBody) return;

  conditionsEvents = new EventSource('/api/conditions/stream');

  conditionsEvents.addEventListener('status', (ev) => {
    try {
      const payload = JSON.parse(ev.data || '{}');
      const items = coerceConditionStatusItems(payload);
      if (!Array.isArray(items)) return;

      // Render using the same logic as refreshConditions, but without a fetch.
      condTableBody.textContent = '';
      for (const it of items) {
        const tr = document.createElement('tr');
        tr.dataset.uuid = String(it.uuid ?? '');
        if (selectedConditionUuid && String(it.uuid) === String(selectedConditionUuid)) {
          tr.classList.add('selected');
        }

        const tdName = document.createElement('td');
        tdName.textContent = String(it.name ?? '');

        const tdType = document.createElement('td');
        tdType.textContent = String(it.type ?? '');

        const tdTpl = document.createElement('td');
        const tplImg = document.createElement('img');
        tplImg.className = 'thumb';
        if (it.templateThumbBase64) {
          tplImg.src = `data:image/jpeg;base64,${it.templateThumbBase64}`;
        }
        tdTpl.appendChild(tplImg);

        const tdCrop = document.createElement('td');
        const cropImg = document.createElement('img');
        cropImg.className = 'thumb';
        if (it.cropThumbBase64) {
          cropImg.src = `data:image/jpeg;base64,${it.cropThumbBase64}`;
        }
        tdCrop.appendChild(cropImg);

        const tdLast = document.createElement('td');
        tdLast.textContent = (it.last === null || it.last === undefined) ? '' : String(it.last);

        tr.appendChild(tdName);
        tr.appendChild(tdType);
        tr.appendChild(tdTpl);
        tr.appendChild(tdCrop);
        tr.appendChild(tdLast);

        tr.addEventListener('click', () => {
          selectedConditionUuid = String(it.uuid ?? '');
          // Selection highlight will show on the next SSE update; force a quick render now.
          try {
            const rows = condTableBody.querySelectorAll('tr');
            rows.forEach(r => r.classList.remove('selected'));
            tr.classList.add('selected');
          } catch {
            // ignore
          }

          loadSelectedConditionIntoEditor().catch(() => {});
        });

        condTableBody.appendChild(tr);
      }
    } catch {
      // ignore
    }
  });
}

if (btnRefreshConditions) {
  btnRefreshConditions.addEventListener('click', async () => {
    setStatus('Refreshing conditions...', null);
    try {
      await refreshConditions();
      await loadSelectedConditionIntoEditor();
      await _getConditionsCached(true);
      setStatus('Conditions refreshed.', 'ok');
    } catch (e) {
      setStatus(`Refresh conditions failed: ${e.message}`, 'err');
    }
  });
}

async function addConditionFromInputs() {
  const name = (conditionNameEl && conditionNameEl.value ? conditionNameEl.value : '').trim();
  if (!name) throw new Error('Name is required');

  const type = (conditionTypeEl && conditionTypeEl.value ? conditionTypeEl.value : 'ImageMatchRoi');
  const xNormalized = read01(roiXEl, 'ROI X');
  const yNormalized = read01(roiYEl, 'ROI Y');
  const widthNormalized = read01(roiWEl, 'ROI W');
  const heightNormalized = read01(roiHEl, 'ROI H');
  if (widthNormalized <= 0 || heightNormalized <= 0) {
    throw new Error('ROI W/H must be > 0');
  }

  let templateImageBase64 = null;
  const file = templateImageEl && templateImageEl.files && templateImageEl.files.length ? templateImageEl.files[0] : null;
  if (file) {
    templateImageBase64 = await fileToDataUrl(file);
  }

  const templateFromLive = !file;

  const res = await postJson('/api/conditions', {
    name,
    type,
    roi: { xNormalized, yNormalized, widthNormalized, heightNormalized },
    templateImageBase64,
    templateFromLive,
  });

  return res;
}

if (btnCondAddRow) {
  btnCondAddRow.addEventListener('click', async () => {
    setStatus('Adding condition...', null);
    try {
      const res = await addConditionFromInputs();
      if (res && res.uuid) {
        selectedConditionUuid = String(res.uuid);
      }
      await refreshConditions();
      await loadSelectedConditionIntoEditor();
      setStatus('Condition added.', 'ok');
    } catch (e) {
      setStatus(`Add condition failed: ${e.message}`, 'err');
    }
  });
}

if (btnCondRemoveRow) {
  btnCondRemoveRow.addEventListener('click', async () => {
    setStatus('Removing condition...', null);
    try {
      if (!selectedConditionUuid) throw new Error('Select a row first');
      await postJson('/api/conditions/remove_uuid', { uuid: selectedConditionUuid });
      selectedConditionUuid = null;
      await refreshConditions();
      clearSelectedConditionEditor();
      setStatus('Condition removed.', 'ok');
    } catch (e) {
      setStatus(`Remove condition failed: ${e.message}`, 'err');
    }
  });
}

async function moveSelected(direction) {
  if (!selectedConditionUuid) throw new Error('Select a row first');
  await postJson('/api/conditions/move', { uuid: selectedConditionUuid, direction });
}

if (btnCondMoveUp) {
  btnCondMoveUp.addEventListener('click', async () => {
    setStatus('Moving up...', null);
    try {
      await moveSelected('up');
      await refreshConditions();
      await loadSelectedConditionIntoEditor();
      setStatus('Moved.', 'ok');
    } catch (e) {
      setStatus(`Move failed: ${e.message}`, 'err');
    }
  });
}

if (btnCondMoveDown) {
  btnCondMoveDown.addEventListener('click', async () => {
    setStatus('Moving down...', null);
    try {
      await moveSelected('down');
      await refreshConditions();
      await loadSelectedConditionIntoEditor();
      setStatus('Moved.', 'ok');
    } catch (e) {
      setStatus(`Move failed: ${e.message}`, 'err');
    }
  });
}

if (btnSetFromLive) {
  btnSetFromLive.addEventListener('click', async () => {
    setStatus('Setting selected condition...', null);
    try {
      if (!selectedConditionUuid) throw new Error('Select a row first');

      const name = (conditionNameEl && conditionNameEl.value ? conditionNameEl.value : '').trim();
      const type = (conditionTypeEl && conditionTypeEl.value ? conditionTypeEl.value : 'ImageMatchRoi');

      const xNormalized = read01(roiXEl, 'ROI X');
      const yNormalized = read01(roiYEl, 'ROI Y');
      const widthNormalized = read01(roiWEl, 'ROI W');
      const heightNormalized = read01(roiHEl, 'ROI H');
      if (widthNormalized <= 0 || heightNormalized <= 0) {
        throw new Error('ROI W/H must be > 0');
      }

      let templateImageBase64 = null;
      const file = templateImageEl && templateImageEl.files && templateImageEl.files.length ? templateImageEl.files[0] : null;
      if (file) {
        templateImageBase64 = await fileToDataUrl(file);
      }
      const templateFromLive = !file;

      await postJson('/api/conditions/set_from_live', {
        uuid: selectedConditionUuid,
        name,
        type,
        roi: { xNormalized, yNormalized, widthNormalized, heightNormalized },
        templateImageBase64,
        templateFromLive,
      });

      await refreshConditions();
      setStatus('Updated.', 'ok');
    } catch (e) {
      setStatus(`Set failed: ${e.message}`, 'err');
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
    const tabs = document.querySelectorAll(".controlTabs button");
    const panels = document.querySelectorAll(".tabPanel");

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const target = tab.dataset.tab;

            // deactivate all tabs
            tabs.forEach(t => t.classList.remove("active"));
            panels.forEach(p => p.classList.remove("active"));

            // activate selected
            tab.classList.add("active");
            document.getElementById(`tab-${target}`).classList.add("active");

            if (target === 'conditions') {
              startConditionsEventSource();
              refreshConditions()
                .then(() => loadSelectedConditionIntoEditor())
                .catch(() => {});
            } else {
              stopConditionsEventSource();
            }

            if (target === 'triggerStatus') {
              startTriggerStatusSse();
            } else {
              stopTriggerStatusSse();
            }

            if (target === 'actions') {
              refreshActions().catch(() => {});
            }

            if (target === 'triggers') {
              // Populate selects and list.
              _loadActionsForSelect(triggerActionEl, triggerActionEl ? triggerActionEl.value : '').catch(() => {});
              refreshTriggers().catch(() => {});
            }
        });
    });
});