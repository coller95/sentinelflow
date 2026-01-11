function _setDelayRowVisible(visible) {
    if (!actionDelayRowEl) return;
    actionDelayRowEl.style.display = visible ? '' : 'none';
}

function _makePlaceholderName(prefix) {
    const stamp = new Date().toISOString().slice(0, 19).replace('T', ' ').replace(/:/g, '-');
    return `${prefix} ${stamp}`;
}

function _getDelayMsFromInput() {
    const raw = actionDelayMsEl ? String(actionDelayMsEl.value || '').trim() : '';
    const ms = Number(raw);
    if (!Number.isFinite(ms) || ms < 0) {
        throw new Error('Delay ms must be a number >= 0');
    }
    return Math.round(ms);
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
        const parameters = (s.parameters && typeof s.parameters === 'object') ? parameters : {};
        if (kind === 'Delay') {
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
            const uuid = String(it.uuid ?? '');
            if (selectedActionUuid && uuid && String(selectedActionUuid) === uuid) {
                clearActionEditor();
                refreshActions().catch(() => {});
                return;
            }
            applyActionToEditor(it);
            refreshActions().catch(() => {});
        });
        actionTableBody.appendChild(tr);
    }
}

async function moveSelectedAction(direction) {
    if (!selectedActionUuid) throw new Error('Select an action first');
    await postJson('/api/actions/move', { uuid: selectedActionUuid, direction });
}

document.addEventListener('keydown', (ev) => {
    if (!_actionKeyCaptureArmed) return;
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

        if (!Array.isArray(_actionSteps)) _actionSteps = [];
        _actionSteps.push({ action: 'Delay', parameters: { ms } });
        _syncHiddenActionStepsTextarea();
        _selectActionStep(_actionSteps.length - 1);
        setStatus('Delay step added.', 'ok');
    });
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
    btnActionNew.addEventListener('click', async () => {
        setStatus('Creating action...', null);
        try {
            const name = _makePlaceholderName('New Action');
            const payload = { name, steps: [] };
            const res = await postJson('/api/actions/upsert', payload);
            const uuid = res && res.uuid ? String(res.uuid) : '';
            if (!uuid) throw new Error('Action created without uuid');
            applyActionToEditor({ uuid, name, steps: [] });
            await refreshActions();
            setStatus('New action created.', 'ok');
        } catch (e) {
            setStatus(`Create action failed: ${e.message}`, 'err');
        }
    });
}

if (btnActionMoveUp) {
    btnActionMoveUp.addEventListener('click', async () => {
        setStatus('Moving action up...', null);
        try {
            await moveSelectedAction('up');
            await refreshActions();
            setStatus('Action moved.', 'ok');
        } catch (e) {
            setStatus(`Move failed: ${e.message}`, 'err');
        }
    });
}

if (btnActionMoveDown) {
    btnActionMoveDown.addEventListener('click', async () => {
        setStatus('Moving action down...', null);
        try {
            await moveSelectedAction('down');
            await refreshActions();
            setStatus('Action moved.', 'ok');
        } catch (e) {
            setStatus(`Move failed: ${e.message}`, 'err');
        }
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
        setStatus('Step deleted.', 'ok');
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
