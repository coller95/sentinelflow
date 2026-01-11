async function tryLoadAppDefaults() {
    try {
        const defaults = await getJson('/api/app/defaults');
        if (!defaults) return;
        const defaultAppPath = (defaults.defaultAppPath || '').trim();
        const defaultWindowTitle = (defaults.defaultWindowTitle || '').trim();
        if (appPathEl && !((appPathEl.value || '').trim()) && defaultAppPath) {
            appPathEl.value = defaultAppPath;
        }
        if (windowTitleEl && !((windowTitleEl.value || '').trim()) && defaultWindowTitle) {
            windowTitleEl.value = defaultWindowTitle;
        }
    } catch {
        // Ignore: defaults are optional.
    }
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
        setTabsOpen(false);
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
        });
    });
    tryLoadAppDefaults();
});
