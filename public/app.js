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

const keyNameEl = document.getElementById('keyName');
const btnSendKey = document.getElementById('btnSendKey');

const clickXEl = document.getElementById('clickX');
const clickYEl = document.getElementById('clickY');
const btnSendClick = document.getElementById('btnSendClick');

const btnRefreshConditions = document.getElementById('btnRefreshConditions');
const condTableBody = document.getElementById('condTableBody');

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

let selectedConditionIndex = null;

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
  ctx.lineWidth = _activeRoiHandle ? 3 : 2;
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
  ensureOverlayCanvasSize();
  if (_lastRoi) drawOverlayRoi(_lastRoi);
});

window.addEventListener('resize', () => {
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
  const items = await getJson('/api/conditions/status');

  condTableBody.textContent = '';

  const safeItems = Array.isArray(items) ? items : [];
  for (const it of safeItems) {
    const tr = document.createElement('tr');
    tr.dataset.index = String(it.index);
    if (selectedConditionIndex !== null && Number(it.index) === Number(selectedConditionIndex)) {
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
      selectedConditionIndex = Number(it.index);
      refreshConditions().catch(() => {});
    });

    condTableBody.appendChild(tr);
  }
}

function startConditionsEventSource() {
  stopConditionsEventSource();
  if (!condTableBody) return;

  conditionsEvents = new EventSource('/api/conditions/stream');

  conditionsEvents.addEventListener('status', (ev) => {
    try {
      const items = JSON.parse(ev.data || '[]');
      if (!Array.isArray(items)) return;

      // Render using the same logic as refreshConditions, but without a fetch.
      condTableBody.textContent = '';
      for (const it of items) {
        const tr = document.createElement('tr');
        tr.dataset.index = String(it.index);
        if (selectedConditionIndex !== null && Number(it.index) === Number(selectedConditionIndex)) {
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
          selectedConditionIndex = Number(it.index);
          // Selection highlight will show on the next SSE update; force a quick render now.
          try {
            const rows = condTableBody.querySelectorAll('tr');
            rows.forEach(r => r.classList.remove('selected'));
            tr.classList.add('selected');
          } catch {
            // ignore
          }
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

  await postJson('/api/conditions', {
    name,
    type,
    roi: { xNormalized, yNormalized, widthNormalized, heightNormalized },
    templateImageBase64,
    templateFromLive,
  });
}

if (btnCondAddRow) {
  btnCondAddRow.addEventListener('click', async () => {
    setStatus('Adding condition...', null);
    try {
      await addConditionFromInputs();
      await refreshConditions();
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
      if (selectedConditionIndex === null) throw new Error('Select a row first');
      await postJson('/api/conditions/remove_index', { index: selectedConditionIndex });
      selectedConditionIndex = null;
      await refreshConditions();
      setStatus('Condition removed.', 'ok');
    } catch (e) {
      setStatus(`Remove condition failed: ${e.message}`, 'err');
    }
  });
}

async function moveSelected(direction) {
  if (selectedConditionIndex === null) throw new Error('Select a row first');
  const res = await postJson('/api/conditions/move', { index: selectedConditionIndex, direction });
  if (res && res.index !== undefined && res.index !== null) {
    selectedConditionIndex = Number(res.index);
  }
}

if (btnCondMoveUp) {
  btnCondMoveUp.addEventListener('click', async () => {
    setStatus('Moving up...', null);
    try {
      await moveSelected('up');
      await refreshConditions();
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
      if (selectedConditionIndex === null) throw new Error('Select a row first');

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
        index: selectedConditionIndex,
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
              refreshConditions().catch(() => {});
            } else {
              stopConditionsEventSource();
            }
        });
    });
});