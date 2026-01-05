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

let captureEvents = null;

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

function startEventSource() {
  stopEventSource();
  captureEvents = new EventSource('/api/capture/events');

  captureEvents.addEventListener('frame', () => {
    // Cache-bust so the browser doesn't reuse the previous image.
    captureImage.src = `/api/capture/latest?fmt=jpg&ts=${Date.now()}`;
  });

  captureEvents.onerror = () => {
    // EventSource auto-reconnects; keep UI simple.
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

window.addEventListener('beforeunload', () => {
  stopEventSource();
});
