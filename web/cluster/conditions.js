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

function _automationClusterQuery() {
    const cu = String(globalThis.AUTOMATION_CLUSTER_UUID || '').trim();
    if (!cu) return '';
    return `?clusterUuid=${encodeURIComponent(cu)}`;
}

function _automationClusterUuid() {
    return String(globalThis.AUTOMATION_CLUSTER_UUID || '').trim();
}

function _makePlaceholderName(prefix) {
    const stamp = new Date().toISOString().slice(0, 19).replace('T', ' ').replace(/:/g, '-');
    return `${prefix} ${stamp}`;
}

function _readOptional01(el, fallback) {
    const raw = (el && el.value ? String(el.value) : '').trim();
    const val = Number(raw);
    if (!Number.isFinite(val)) return fallback;
    return clamp01(val);
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

async function refreshConditions() {
    if (!condTableBody) return;
    const payload = await getJson(`/api/conditions/status${_automationClusterQuery()}`);
    const items = coerceConditionStatusItems(payload);
    _renderConditionsTable(items);
}

let _conditionEditorLoadSeq = 0;
let _conditionsLastItems = [];
let _conditionsHoverPaused = false;
let _conditionsQueuedPayload = null;

function _renderConditionsTable(items) {
    if (!condTableBody) return;
    condTableBody.textContent = '';
    const safeItems = Array.isArray(items) ? items : [];
    _conditionsLastItems = safeItems;
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
        condTableBody.appendChild(tr);
    }
}

function _renderConditionsMaybe(items) {
    if (_conditionsHoverPaused) {
        _conditionsQueuedPayload = items;
        return;
    }
    _conditionsQueuedPayload = null;
    _renderConditionsTable(items);
}

function _setConditionsHoverPaused(paused) {
    _conditionsHoverPaused = paused;
    if (!paused && _conditionsQueuedPayload) {
        const payload = _conditionsQueuedPayload;
        _conditionsQueuedPayload = null;
        _renderConditionsTable(payload);
    }
}

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
    renderLiveOverlay();
}

function applyConditionItemToEditor(item) {
    if (!item) return;
    if (conditionNameEl) conditionNameEl.value = String(item.name ?? '');
    if (conditionTypeEl) conditionTypeEl.value = String(item.type ?? 'ImageMatchRoi');
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
    renderLiveOverlay();
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
    conditionsEvents = new EventSource(apiPath(`/api/conditions/stream${_automationClusterQuery()}`));
    conditionsEvents.addEventListener('status', (ev) => {
        try {
            const payload = JSON.parse(ev.data || '{}');
            const items = coerceConditionStatusItems(payload);
            if (!Array.isArray(items)) return;
            _renderConditionsMaybe(items);
        } catch {
            // ignore
        }
    });
}

function stopConditionsEventSource() {
    if (conditionsEvents) {
        conditionsEvents.close();
        conditionsEvents = null;
    }
}

if (condTableBody && !condTableBody.dataset.clickBound) {
    condTableBody.dataset.clickBound = '1';
    condTableBody.addEventListener('click', (ev) => {
        const target = ev.target;
        if (!(target instanceof Element)) return;
        const row = target.closest('tr');
        if (!row || !condTableBody.contains(row)) return;
        const uuid = String(row.dataset.uuid || '').trim();
        if (!uuid) return;
        if (selectedConditionUuid && String(selectedConditionUuid) === uuid) {
            selectedConditionUuid = null;
            clearSelectedConditionEditor();
            _renderConditionsTable(_conditionsLastItems);
            return;
        }
        selectedConditionUuid = uuid;
        _renderConditionsTable(_conditionsLastItems);
        loadSelectedConditionIntoEditor().catch(() => {});
    });
}

const conditionsHoverTarget = condTableBody ? condTableBody.closest('.condTableWrap') : null;
if (conditionsHoverTarget) {
    conditionsHoverTarget.addEventListener('mouseenter', () => {
        _setConditionsHoverPaused(true);
    });
    conditionsHoverTarget.addEventListener('mouseleave', () => {
        _setConditionsHoverPaused(false);
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
    const clusterUuid = _automationClusterUuid();
    const templateFromLive = !file && !!clusterUuid;
    const payload = {
        name,
        type,
        roi: { xNormalized, yNormalized, widthNormalized, heightNormalized },
        templateImageBase64,
        templateFromLive,
    };
    if (clusterUuid) payload.clusterUuid = clusterUuid;
    const res = await postJson('/api/conditions', payload);
    return res;
}

async function createConditionPlaceholder() {
    const name = _makePlaceholderName('New Condition');
    const type = (conditionTypeEl && conditionTypeEl.value ? conditionTypeEl.value : 'ImageMatchRoi');
    let xNormalized = _readOptional01(roiXEl, 0.1);
    let yNormalized = _readOptional01(roiYEl, 0.1);
    let widthNormalized = _readOptional01(roiWEl, 0.2);
    let heightNormalized = _readOptional01(roiHEl, 0.1);
    if (widthNormalized <= 0) widthNormalized = 0.2;
    if (heightNormalized <= 0) heightNormalized = 0.1;

    if (conditionNameEl) conditionNameEl.value = name;
    if (conditionTypeEl) conditionTypeEl.value = type;
    _lastRoi = { x: xNormalized, y: yNormalized, w: widthNormalized, h: heightNormalized };
    _activeRoiHandle = null;
    setRoiInputsFromNormalized(_lastRoi);
    renderLiveOverlay();

    const clusterUuid = _automationClusterUuid();
    const payload = {
        name,
        type,
        roi: { xNormalized, yNormalized, widthNormalized, heightNormalized },
        templateImageBase64: null,
        templateFromLive: true,
    };
    if (clusterUuid) payload.clusterUuid = clusterUuid;

    const res = await postJson('/api/conditions', payload);
    return res;
}

if (btnCondAddRow) {
    btnCondAddRow.addEventListener('click', async () => {
        setStatus('Creating condition...', null);
        try {
            const res = await createConditionPlaceholder();
            if (res && res.uuid) {
                selectedConditionUuid = String(res.uuid);
            }
            await refreshConditions();
            await loadSelectedConditionIntoEditor();
            setStatus('New condition created.', 'ok');
        } catch (e) {
            setStatus(`Create condition failed: ${e.message}`, 'err');
        }
    });
}

if (btnCondClone) {
    btnCondClone.addEventListener('click', async () => {
        setStatus('Cloning condition...', null);
        try {
            if (!selectedConditionUuid) throw new Error('Select a row first');
            const state = await getJson('/api/state/export');
            const conditions = Array.isArray(state?.conditions) ? state.conditions : [];
            const source = conditions.find((it) => String(it?.uuid ?? '') === String(selectedConditionUuid));
            if (!source) throw new Error('Selected condition not found');

            const baseName = String(source.name ?? 'Condition').trim() || 'Condition';
            const name = `${baseName} (copy)`;
            const type = String(source.type ?? 'ImageMatchRoi');
            const roiRaw = (source && typeof source.roi === 'object') ? source.roi : {};
            let xNormalized = Number(roiRaw?.xNormalized ?? 0.1);
            let yNormalized = Number(roiRaw?.yNormalized ?? 0.1);
            let widthNormalized = Number(roiRaw?.widthNormalized ?? 0.2);
            let heightNormalized = Number(roiRaw?.heightNormalized ?? 0.1);
            if (!Number.isFinite(xNormalized)) xNormalized = 0.1;
            if (!Number.isFinite(yNormalized)) yNormalized = 0.1;
            if (!Number.isFinite(widthNormalized) || widthNormalized <= 0) widthNormalized = 0.2;
            if (!Number.isFinite(heightNormalized) || heightNormalized <= 0) heightNormalized = 0.1;

            const templateImageBase64 = typeof source.templateImageBase64 === 'string' ? source.templateImageBase64 : null;
            const payload = {
                name,
                type,
                roi: { xNormalized, yNormalized, widthNormalized, heightNormalized },
                templateImageBase64,
                templateFromLive: false,
            };
            const res = await postJson('/api/conditions', payload);
            if (res && res.uuid) {
                selectedConditionUuid = String(res.uuid);
            }
            await refreshConditions();
            await loadSelectedConditionIntoEditor();
            setStatus('Condition cloned.', 'ok');
        } catch (e) {
            setStatus(`Clone condition failed: ${e.message}`, 'err');
        }
    });
}

if (btnCondRemoveRow) {
    btnCondRemoveRow.addEventListener('click', async () => {
        setStatus('Deleting condition...', null);
        try {
            if (!selectedConditionUuid) throw new Error('Select a row first');
            await postJson('/api/conditions/remove_uuid', { uuid: selectedConditionUuid });
            selectedConditionUuid = null;
            await refreshConditions();
            clearSelectedConditionEditor();
            setStatus('Condition deleted.', 'ok');
        } catch (e) {
            setStatus(`Delete condition failed: ${e.message}`, 'err');
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
            const clusterUuid = _automationClusterUuid();
            const templateFromLive = !file && !!clusterUuid;
            const payload = {
                uuid: selectedConditionUuid,
                name,
                type,
                roi: { xNormalized, yNormalized, widthNormalized, heightNormalized },
                templateImageBase64,
                templateFromLive,
            };
            if (clusterUuid) payload.clusterUuid = clusterUuid;
            await postJson('/api/conditions/set_from_live', payload);
            await refreshConditions();
            setStatus('Updated.', 'ok');
        } catch (e) {
            setStatus(`Set failed: ${e.message}`, 'err');
        }
    });
}
