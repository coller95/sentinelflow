const appPathEl = document.getElementById('appPath');
const windowTitleEl = document.getElementById('windowTitle');
const statusEl = document.getElementById('status');

const btnLaunch = document.getElementById('btnLaunch');
const btnAttach = document.getElementById('btnAttach');
const btnClose = document.getElementById('btnClose');

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

btnLaunch.addEventListener('click', async () => {
  const app_path = (appPathEl.value || '').trim();
  if (!app_path) {
    setStatus('Enter an app path (or command) first.', 'err');
    return;
  }
  setBusy(true);
  setStatus('Launching...', null);
  try {
    await postJson('/api/app/launch', { app_path });
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
    await postJson('/api/app/attach', { window_title });
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
