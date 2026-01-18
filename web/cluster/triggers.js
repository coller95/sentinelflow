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

let _triggerStatusHoverPaused = false;
let _triggerStatusQueuedPayload = null;

function _makePlaceholderName(prefix) {
    const stamp = new Date().toISOString().slice(0, 19).replace('T', ' ').replace(/:/g, '-');
    return `${prefix} ${stamp}`;
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
        btnDel.textContent = 'Delete';
        tdDel.appendChild(btnDel);
        tr.appendChild(tdCond);
        tr.appendChild(tdComp);
        tr.appendChild(tdExp);
        tr.appendChild(tdDel);

        if (Array.isArray(_cachedConditions)) {
            _fillConditionsSelect(selCond, _cachedConditions, r.conditionUuid);
            if (!rows[i].conditionUuid) {
                rows[i].conditionUuid = String(selCond.value || '');
            }
        } else {
            _loadConditionsForSelect(selCond, r.conditionUuid).then(() => {
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
    if (triggerDisableOnFireEl) triggerDisableOnFireEl.checked = false;
    if (triggerRetriggerMsEl) triggerRetriggerMsEl.value = '0';
    if (triggerCriteriaModeEl) triggerCriteriaModeEl.value = 'All';
    if (triggerActionEl) triggerActionEl.value = '';
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
    if (triggerDisableOnFireEl) triggerDisableOnFireEl.checked = !!t.disableOnFire;
    if (triggerRetriggerMsEl) triggerRetriggerMsEl.value = String(t.retriggerMs ?? 0);
    if (triggerCriteriaModeEl) triggerCriteriaModeEl.value = String(t.criteriaMode ?? 'All');
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
            const uuid = String(it.uuid ?? '');
            if (selectedTriggerUuid && uuid && String(selectedTriggerUuid) === uuid) {
                _clearTriggerEditor();
                refreshTriggers().catch(() => {});
                return;
            }
            try {
                await _loadActionsForSelect(triggerActionEl, String(it.action ?? ''));
            } catch { }
            _applyTriggerToEditor(it);
            refreshTriggers().catch(() => {});
        });
        triggerTableBody.appendChild(tr);
    }
    _loadActionsForSelect(triggerActionEl, triggerActionEl ? triggerActionEl.value : '').catch(() => {});
}

async function moveSelectedTrigger(direction) {
    if (!selectedTriggerUuid) throw new Error('Select a trigger first');
    await postJson('/api/triggers/move', { uuid: selectedTriggerUuid, direction });
}

function _renderTriggerStatusFromPayload(payload) {
    if (!triggerStatusTableBody) return;
    const items = payload && Array.isArray(payload.items) ? payload.items : [];
    triggerStatusTableBody.textContent = '';
    for (const it of items) {
        const tr = document.createElement('tr');
        const uuid = String(it.uuid ?? '');
        tr.dataset.uuid = uuid;
        const tdEnabled = document.createElement('td');
        tdEnabled.classList.add('stickyEnabled');
        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.checked = !!it.enabled;
        tdEnabled.appendChild(chk);
        const tdName = document.createElement('td');
        tdName.textContent = String(it.name ?? '');
        const tdMet = document.createElement('td');
        tdMet.textContent = it.isMet ? 'Yes' : 'No';
        const tdRetrigger = document.createElement('td');
        tdRetrigger.textContent = String(it.retriggerMs ?? 0);
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
            } catch (e) {
                setStatus(`Set enabled failed: ${e.message}`, 'err');
                chk.checked = !!it.enabled;
            }
        });
        tr.appendChild(tdEnabled);
        tr.appendChild(tdName);
        tr.appendChild(tdRetrigger);
        tr.appendChild(tdMet);
        tr.appendChild(tdLogic);
        tr.appendChild(tdAction);
        tr.appendChild(tdRunning);
        tr.appendChild(tdActionRuns);
        tr.appendChild(tdFires);
        tr.appendChild(tdLastFire);
        tr.appendChild(tdLastDone);

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

function _renderTriggerStatusMaybe(payload) {
    if (_triggerStatusHoverPaused) {
        _triggerStatusQueuedPayload = payload;
        return;
    }
    _triggerStatusQueuedPayload = null;
    _renderTriggerStatusFromPayload(payload);
}

function _setTriggerStatusHoverPaused(paused) {
    _triggerStatusHoverPaused = paused;
    if (!paused && _triggerStatusQueuedPayload) {
        const payload = _triggerStatusQueuedPayload;
        _triggerStatusQueuedPayload = null;
        _renderTriggerStatusFromPayload(payload);
    }
}

async function refreshTriggerStatus() {
    if (!triggerStatusTableBody) return;
    const payload = await getJson('/api/triggers/status');
    _renderTriggerStatusFromPayload(payload);
}

function startTriggerStatusSse() {
    stopTriggerStatusSse();
    _triggerStatusQueuedPayload = null;
    _triggerStatusHoverPaused = !!(triggerStatusHoverTarget && triggerStatusHoverTarget.matches(':hover'));
    refreshTriggerStatus().catch(() => {});
    try {
        const es = new EventSource('/api/triggers/status/stream');
        _triggerStatusEventSource = es;
        es.addEventListener('status', (ev) => {
            try {
                const payload = JSON.parse(String(ev.data || '{}'));
                _renderTriggerStatusMaybe(payload);
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

const triggerStatusHoverTarget = triggerStatusTableBody ? triggerStatusTableBody.closest('.condTableWrap') : null;
if (triggerStatusHoverTarget) {
    triggerStatusHoverTarget.addEventListener('mouseenter', () => {
        _setTriggerStatusHoverPaused(true);
    });
    triggerStatusHoverTarget.addEventListener('mouseleave', () => {
        _setTriggerStatusHoverPaused(false);
    });
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
        setStatus('Creating trigger...', null);
        try {
            const actions = await getJson('/api/actions');
            const safeActions = Array.isArray(actions) ? actions : [];
            const actionUuid = safeActions.length ? String(safeActions[0].uuid ?? '').trim() : '';
            if (!actionUuid) throw new Error('Create an action first');
            const name = _makePlaceholderName('New Trigger');
            const payload = {
                name,
                enabled: false,
                retriggerMs: 0,
                disableOnFire: false,
                criteriaMode: 'All',
                action: actionUuid,
                triggerCiterias: [],
            };
            const res = await postJson('/api/triggers/upsert', payload);
            const uuid = res && res.uuid ? String(res.uuid) : '';
            if (!uuid) throw new Error('Trigger created without uuid');
            await _loadActionsForSelect(triggerActionEl, actionUuid);
            _applyTriggerToEditor({
                uuid,
                name,
                enabled: false,
                retriggerMs: 0,
                disableOnFire: false,
                criteriaMode: 'All',
                action: actionUuid,
                triggerCiterias: [],
            });
            await refreshTriggers();
            setStatus('New trigger created.', 'ok');
        } catch (e) {
            setStatus(`Create trigger failed: ${e.message}`, 'err');
        }
    });
}

if (btnTriggerMoveUp) {
    btnTriggerMoveUp.addEventListener('click', async () => {
        setStatus('Moving trigger up...', null);
        try {
            await moveSelectedTrigger('up');
            await refreshTriggers();
            setStatus('Trigger moved.', 'ok');
        } catch (e) {
            setStatus(`Move failed: ${e.message}`, 'err');
        }
    });
}

if (btnTriggerMoveDown) {
    btnTriggerMoveDown.addEventListener('click', async () => {
        setStatus('Moving trigger down...', null);
        try {
            await moveSelectedTrigger('down');
            await refreshTriggers();
            setStatus('Trigger moved.', 'ok');
        } catch (e) {
            setStatus(`Move failed: ${e.message}`, 'err');
        }
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
            const disableOnFire = triggerDisableOnFireEl ? !!triggerDisableOnFireEl.checked : false;
            let retriggerMs = 0;
            if (triggerRetriggerMsEl) {
                const n = Number(triggerRetriggerMsEl.value);
                if (!Number.isFinite(n) || n < 0) throw new Error('Retrigger (ms) must be a non-negative number');
                retriggerMs = Math.floor(n);
            }
            const criteriaMode = triggerCriteriaModeEl ? String(triggerCriteriaModeEl.value || 'All') : 'All';
            const citerias = _readTriggerCriteriaFromDom();
            _triggerCriteria = citerias;
            const domRowCount = triggerCriteriaBody ? triggerCriteriaBody.querySelectorAll('tr').length : 0;
            if (domRowCount > 0 && citerias.length === 0) {
                throw new Error('Criteria rows exist but no Condition is selected. Create/refresh Conditions first, then select a Condition for each criteria.');
            }
            const payload = { name, enabled, retriggerMs, disableOnFire, criteriaMode, action: actionUuid, triggerCiterias: citerias };
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
