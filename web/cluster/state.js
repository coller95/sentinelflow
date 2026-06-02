// --- State Import/Export ---

async function refreshStatePath() {
    if (!statePathEl) return;
    const data = await getJson('/api/state/path');
    statePathEl.value = String((data && data.path) ? data.path : '');
}

function _stringifyState(obj) {
    try {
        return JSON.stringify(obj, null, 2);
    } catch {
        return '';
    }
}

async function exportStateToEditor() {
    if (!stateJsonEl) return;
    const includeUuid = stateIncludeServerUuidEl ? !!stateIncludeServerUuidEl.checked : false;
    const data = await getJson(`/api/state/export?includeServerUuid=${includeUuid ? 'true' : 'false'}`);
    stateJsonEl.value = _stringifyState(data);
    return data;
}

function _parseStateEditorJson() {
    const raw = stateJsonEl ? String(stateJsonEl.value || '').trim() : '';
    if (!raw) throw new Error('State JSON is empty');
    let parsed;
    try {
        parsed = JSON.parse(raw);
    } catch {
        throw new Error('State JSON is not valid JSON');
    }
    if (!parsed || typeof parsed !== 'object') {
        throw new Error('State JSON must be an object');
    }
    return parsed;
}

async function importStateFromEditor() {
    const parsed = _parseStateEditorJson();
    const keepServerUuid = stateKeepServerUuidEl ? !!stateKeepServerUuidEl.checked : true;
    await postJson('/api/state/import', { state: parsed, keepServerUuid });
}

function _downloadText(filename, text) {
    const blob = new Blob([text], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

function _stampForFilename() {
    const d = new Date();
    const iso = d.toISOString().replace(/[:.]/g, '-');
    return iso;
}

async function downloadStateJson() {
    let text = stateJsonEl ? String(stateJsonEl.value || '').trim() : '';
    if (!text) {
        const data = await exportStateToEditor();
        text = _stringifyState(data);
    }
    if (!text) throw new Error('No state JSON to download');
    _downloadText(`sentinelflow-state-${_stampForFilename()}.json`, text);
}

function _readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(new Error('Failed to read file'));
        reader.onload = () => resolve(String(reader.result || ''));
        reader.readAsText(file);
    });
}

async function loadStateFileIntoEditor(file) {
    if (!stateJsonEl) return;
    const text = await _readFileAsText(file);
    stateJsonEl.value = String(text || '');
}

if (btnStatePath) {
    btnStatePath.addEventListener('click', async () => {
        setStatus('Refreshing state path...', null);
        try {
            await refreshStatePath();
            setStatus('State path loaded.', 'ok');
        } catch (e) {
            setStatus(`State path failed: ${e.message}`, 'err');
        }
    });
}

if (btnStateReload) {
    btnStateReload.addEventListener('click', async () => {
        setStatus('Reloading state from disk...', null);
        try {
            await postJson('/api/state/reload');
            setStatus('State reloaded.', 'ok');
        } catch (e) {
            setStatus(`Reload failed: ${e.message}`, 'err');
        }
    });
}

if (btnStateExport) {
    btnStateExport.addEventListener('click', async () => {
        setStatus('Exporting state...', null);
        try {
            await exportStateToEditor();
            setStatus('State exported.', 'ok');
        } catch (e) {
            setStatus(`Export failed: ${e.message}`, 'err');
        }
    });
}

if (btnStateDownload) {
    btnStateDownload.addEventListener('click', async () => {
        setStatus('Preparing download...', null);
        try {
            await downloadStateJson();
            setStatus('Download ready.', 'ok');
        } catch (e) {
            setStatus(`Download failed: ${e.message}`, 'err');
        }
    });
}

if (btnStateImport) {
    btnStateImport.addEventListener('click', async () => {
        setStatus('Importing state...', null);
        try {
            await importStateFromEditor();
            if (typeof refreshConditions === 'function') refreshConditions().catch(() => {});
            if (typeof refreshActions === 'function') refreshActions().catch(() => {});
            if (typeof refreshTriggers === 'function') refreshTriggers().catch(() => {});
            if (typeof tryLoadAppDefaults === 'function') {
                tryLoadAppDefaults().catch(() => {});
            }
            setStatus('State imported.', 'ok');
        } catch (e) {
            setStatus(`Import failed: ${e.message}`, 'err');
        }
    });
}

if (stateFileEl) {
    stateFileEl.addEventListener('change', async () => {
        const file = stateFileEl.files && stateFileEl.files[0];
        if (!file) return;
        setStatus('Loading file...', null);
        try {
            await loadStateFileIntoEditor(file);
            setStatus('File loaded into editor.', 'ok');
        } catch (e) {
            setStatus(`File load failed: ${e.message}`, 'err');
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    refreshStatePath().catch(() => {});
});
