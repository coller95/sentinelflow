async function tryLoadAppDefaults() {
    try {
        const defaults = await getJson('/api/app/defaults');
        if (!defaults) return;
        const defaultAppPath = String(defaults.defaultAppPath ?? '').trim();
        const defaultWindowTitle = String(defaults.defaultWindowTitle ?? '').trim();
        const defaultWindowLeft = Number(defaults.defaultWindowLeft);
        const defaultWindowTop = Number(defaults.defaultWindowTop);
        const defaultWindowWidth = Number(defaults.defaultWindowWidth);
        const defaultWindowHeight = Number(defaults.defaultWindowHeight);
        if (appPathEl) {
            appPathEl.value = defaultAppPath;
        }
        if (windowTitleEl) {
            windowTitleEl.value = defaultWindowTitle;
        }
        if (windowLeftEl && Number.isFinite(defaultWindowLeft)) {
            windowLeftEl.value = String(Math.trunc(defaultWindowLeft));
        }
        if (windowTopEl && Number.isFinite(defaultWindowTop)) {
            windowTopEl.value = String(Math.trunc(defaultWindowTop));
        }
        if (windowWidthEl && Number.isFinite(defaultWindowWidth)) {
            windowWidthEl.value = String(Math.trunc(defaultWindowWidth));
        }
        if (windowHeightEl && Number.isFinite(defaultWindowHeight)) {
            windowHeightEl.value = String(Math.trunc(defaultWindowHeight));
        }
        _lastSavedAppDefaults = _readAppDefaultsFromInputs();
    } catch {
        // Ignore: defaults are optional.
    }
}

let _appDefaultsSaveTimer = null;
let _lastSavedAppDefaults = {
    defaultAppPath: '',
    defaultWindowTitle: '',
    defaultWindowLeft: null,
    defaultWindowTop: null,
    defaultWindowWidth: null,
    defaultWindowHeight: null
};

function _readIntInput(el) {
    const raw = (el && el.value ? String(el.value) : '').trim();
    if (!raw) return null;
    const n = Number(raw);
    if (!Number.isFinite(n)) return null;
    return Math.trunc(n);
}

function _readAppDefaultsFromInputs() {
    return {
        defaultAppPath: String(appPathEl && appPathEl.value ? appPathEl.value : '').trim(),
        defaultWindowTitle: String(windowTitleEl && windowTitleEl.value ? windowTitleEl.value : '').trim(),
        defaultWindowLeft: _readIntInput(windowLeftEl),
        defaultWindowTop: _readIntInput(windowTopEl),
        defaultWindowWidth: _readIntInput(windowWidthEl),
        defaultWindowHeight: _readIntInput(windowHeightEl)
    };
}

function _diffAppDefaults(next, prev) {
    const payload = {};
    if (next.defaultAppPath !== prev.defaultAppPath) payload.defaultAppPath = next.defaultAppPath;
    if (next.defaultWindowTitle !== prev.defaultWindowTitle) payload.defaultWindowTitle = next.defaultWindowTitle;
    if (next.defaultWindowLeft !== null && next.defaultWindowLeft !== prev.defaultWindowLeft) {
        payload.defaultWindowLeft = next.defaultWindowLeft;
    }
    if (next.defaultWindowTop !== null && next.defaultWindowTop !== prev.defaultWindowTop) {
        payload.defaultWindowTop = next.defaultWindowTop;
    }
    if (next.defaultWindowWidth !== null && next.defaultWindowWidth !== prev.defaultWindowWidth) {
        payload.defaultWindowWidth = next.defaultWindowWidth;
    }
    if (next.defaultWindowHeight !== null && next.defaultWindowHeight !== prev.defaultWindowHeight) {
        payload.defaultWindowHeight = next.defaultWindowHeight;
    }
    return payload;
}

async function _saveAppDefaultsNow() {
    const next = _readAppDefaultsFromInputs();
    const payload = _diffAppDefaults(next, _lastSavedAppDefaults);
    const keys = Object.keys(payload);
    if (keys.length === 0) return;
    const res = await postJson('/api/app/defaults', payload);
    const saved = {
        defaultAppPath: String((res && res.defaultAppPath) ?? next.defaultAppPath ?? ''),
        defaultWindowTitle: String((res && res.defaultWindowTitle) ?? next.defaultWindowTitle ?? ''),
        defaultWindowLeft: Number.isFinite(Number(res && res.defaultWindowLeft)) ? Number(res.defaultWindowLeft) : next.defaultWindowLeft,
        defaultWindowTop: Number.isFinite(Number(res && res.defaultWindowTop)) ? Number(res.defaultWindowTop) : next.defaultWindowTop,
        defaultWindowWidth: Number.isFinite(Number(res && res.defaultWindowWidth)) ? Number(res.defaultWindowWidth) : next.defaultWindowWidth,
        defaultWindowHeight: Number.isFinite(Number(res && res.defaultWindowHeight)) ? Number(res.defaultWindowHeight) : next.defaultWindowHeight
    };
    _lastSavedAppDefaults = saved;
}

function queueAppDefaultsSave() {
    if (_appDefaultsSaveTimer) {
        clearTimeout(_appDefaultsSaveTimer);
    }
    _appDefaultsSaveTimer = setTimeout(() => {
        _appDefaultsSaveTimer = null;
        _saveAppDefaultsNow().catch(() => {});
    }, 350);
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

function startEventSource() {
    stopEventSource();
    captureEvents = new EventSource('/api/capture/stream?fmt=jpg&quality=70');
    captureEvents.addEventListener('frame', (ev) => {
        captureImage.src = `data:image/jpeg;base64,${ev.data}`;
    });
    captureEvents.onerror = () => {
        setStatus('Live preview disconnected (retrying)...', 'err');
    };
}

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

window.addEventListener('beforeunload', () => {
    stopEventSource();
    stopConditionsEventSource();
    stopTriggerStatusSse();
});

document.addEventListener("DOMContentLoaded", () => {
    const tabToggleBtn = document.getElementById("btnToggleTabs");
    const controlWorkspace = document.querySelector(".controlWorkspace");
    const setOverlayForTab = (target) => {
        if (typeof setLiveOverlayMode !== 'function') return;
        if (target === 'conditions') {
            setLiveOverlayMode('roi');
            return;
        }
        if (target === 'input' || target === 'actions') {
            setLiveOverlayMode('click');
            return;
        }
        setLiveOverlayMode('none');
    };
    const setTabsOpen = (open) => {
        if (!controlWorkspace || !tabToggleBtn) return;
        if (open) {
            controlWorkspace.classList.add("tabsOpen");
            tabToggleBtn.setAttribute("aria-expanded", "true");
            tabToggleBtn.setAttribute("aria-label", "Hide tabs");
            tabToggleBtn.textContent = "<";
        } else {
            controlWorkspace.classList.remove("tabsOpen");
            tabToggleBtn.setAttribute("aria-expanded", "false");
            tabToggleBtn.setAttribute("aria-label", "Show tabs");
            tabToggleBtn.textContent = ">";
        }
    };
    if (tabToggleBtn && controlWorkspace) {
        setTabsOpen(true);
        tabToggleBtn.addEventListener("click", () => {
            const isOpen = controlWorkspace.classList.contains("tabsOpen");
            setTabsOpen(!isOpen);
        });
    }
    const tabs = document.querySelectorAll(".controlTabs button");
    const panels = document.querySelectorAll(".tabPanel");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const target = tab.dataset.tab;
            tabs.forEach(t => t.classList.remove("active"));
            panels.forEach(p => p.classList.remove("active"));
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
                _loadActionsForSelect(triggerActionEl, triggerActionEl ? triggerActionEl.value : '').catch(() => {});
                refreshTriggers().catch(() => {});
            }
            setOverlayForTab(target);
        });
    });
    const activeTab = document.querySelector(".controlTabs button.active");
    if (activeTab) {
        const target = activeTab.dataset.tab;
        setOverlayForTab(target);
    }
    tryLoadAppDefaults();
    _lastSavedAppDefaults = _readAppDefaultsFromInputs();
    if (appPathEl) {
        appPathEl.addEventListener('input', queueAppDefaultsSave);
        appPathEl.addEventListener('change', queueAppDefaultsSave);
    }
    if (windowTitleEl) {
        windowTitleEl.addEventListener('input', queueAppDefaultsSave);
        windowTitleEl.addEventListener('change', queueAppDefaultsSave);
    }
    if (windowLeftEl) {
        windowLeftEl.addEventListener('input', queueAppDefaultsSave);
        windowLeftEl.addEventListener('change', queueAppDefaultsSave);
    }
    if (windowTopEl) {
        windowTopEl.addEventListener('input', queueAppDefaultsSave);
        windowTopEl.addEventListener('change', queueAppDefaultsSave);
    }
    if (windowWidthEl) {
        windowWidthEl.addEventListener('input', queueAppDefaultsSave);
        windowWidthEl.addEventListener('change', queueAppDefaultsSave);
    }
    if (windowHeightEl) {
        windowHeightEl.addEventListener('input', queueAppDefaultsSave);
        windowHeightEl.addEventListener('change', queueAppDefaultsSave);
    }
});
