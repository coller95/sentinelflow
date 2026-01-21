function _loadClusterOrder() {
  try {
    if (!globalThis.localStorage) return [];
    const raw = globalThis.localStorage.getItem(CLUSTER_ORDER_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(x => String(x || '').trim()).filter(Boolean) : [];
  } catch {
    return [];
  }
}

function _saveClusterOrder(order) {
  try {
    if (!globalThis.localStorage) return;
    const clean = Array.isArray(order) ? order.map(x => String(x || '').trim()).filter(Boolean) : [];
    globalThis.localStorage.setItem(CLUSTER_ORDER_STORAGE_KEY, JSON.stringify(clean));
  } catch {
    // Ignore storage failures.
  }
}

function _applyClusterOrder(clusters) {
  const list = Array.isArray(clusters) ? clusters : [];
  const order = _loadClusterOrder();
  if (order.length === 0) return list;

  const byUuid = new Map();
  for (const c of list) {
    const id = String(c?.uuid ?? '').trim();
    if (id) byUuid.set(id, c);
  }

  const sorted = [];
  for (const id of order) {
    const item = byUuid.get(id);
    if (item) {
      sorted.push(item);
      byUuid.delete(id);
    }
  }

  for (const c of list) {
    const id = String(c?.uuid ?? '').trim();
    if (!id || byUuid.has(id)) {
      sorted.push(c);
      if (id) byUuid.delete(id);
    }
  }

  return sorted;
}

function _reorderClusters(dragUuid, targetUuid) {
  const drag = String(dragUuid || '').trim();
  const target = String(targetUuid || '').trim();
  if (!drag || drag === target) return;

  const ordered = _applyClusterOrder(_cachedClusters).map(c => String(c?.uuid ?? '')).filter(Boolean);
  const next = ordered.filter(id => id !== drag);
  if (!target) {
    next.push(drag);
  } else {
    const targetIdx = next.indexOf(target);
    if (targetIdx < 0) {
      next.push(drag);
    } else {
      next.splice(targetIdx, 0, drag);
    }
  }

  _saveClusterOrder(next);
  _cctvLayoutKey = '';
  _ensureCctvCards();
}

function _ensureDragHandlers() {
  if (_dragInit || !cctvGridEl) return;
  _dragInit = true;
  _dragPlaceholder = document.createElement('div');
  _dragPlaceholder.className = 'cctvDropIndicator';

  cctvGridEl.addEventListener('dragover', (ev) => {
    if (!_draggingUuid) return;
    ev.preventDefault();
    if (ev.dataTransfer) ev.dataTransfer.dropEffect = 'move';

    const cards = Array.from(cctvGridEl.querySelectorAll('.cctvCard')).filter(
      el => !el.classList.contains('dragging')
    );
    const x = ev.clientX;
    let inserted = false;
    for (const card of cards) {
      const rect = card.getBoundingClientRect();
      if (x < rect.left + rect.width / 2) {
        cctvGridEl.insertBefore(_dragPlaceholder, card);
        inserted = true;
        break;
      }
    }
    if (!inserted) {
      cctvGridEl.appendChild(_dragPlaceholder);
    }
  });

  cctvGridEl.addEventListener('dragleave', (ev) => {
    const related = ev.relatedTarget;
    if (related && cctvGridEl.contains(related)) return;
    _clearDropIndicator();
  });

  cctvGridEl.addEventListener('drop', (ev) => {
    if (!_draggingUuid) return;
    ev.preventDefault();
    const dragId = (ev.dataTransfer && ev.dataTransfer.getData('text/plain')) || _draggingUuid;
    _draggingUuid = null;
    const nextCard = _dragPlaceholder && _dragPlaceholder.nextElementSibling;
    const target = nextCard && nextCard.classList.contains('cctvCard') ? nextCard.dataset.uuid : '';
    _clearDropIndicator();
    _reorderClusters(dragId, target || '');
  });
}

function _clearDropIndicator() {
  if (_dragPlaceholder && _dragPlaceholder.parentElement) {
    _dragPlaceholder.parentElement.removeChild(_dragPlaceholder);
  }
}

function _cctvPillInfo(state) {
  switch (state) {
    case 'live':
      return { text: 'live', cls: 'ok' };
    case 'stopped':
      return { text: 'stopped', cls: 'warn' };
    case 'no-url':
      return { text: 'no url', cls: 'warn' };
    case 'duplicate':
      return { text: 'duplicate', cls: 'warn' };
    case 'offline':
      return { text: 'offline', cls: 'bad' };
    case 'no-capture':
      return { text: 'no capture', cls: 'warn' };
    case 'error':
      return { text: 'error', cls: 'bad' };
    default:
      return { text: 'idle', cls: '' };
  }
}

function _isClusterAttached(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return false;
  const status = _appStatusCache.get(cu);
  return !!(status && status.attached);
}

function _setClusterAttachedStatus(clusterUuid, attached) {
  const cu = String(clusterUuid ?? '').trim();
  if (!cu) return;
  const status = _appStatusCache.get(cu) || {};
  status.attached = !!attached;
  _appStatusCache.set(cu, status);
}

function _applyAttachStateToElements(elements, attached) {
  if (!elements) return;
  const canProxy = elements.canProxy !== undefined ? !!elements.canProxy : true;
  if (elements.attachStatusEl) {
    elements.attachStatusEl.textContent = attached ? 'attached' : 'detached';
  }
  if (elements.launchBtn) {
    elements.launchBtn.disabled = !canProxy || attached;
  }
  if (elements.attachBtn) {
    elements.attachBtn.disabled = !canProxy || attached;
  }
  if (elements.captureStartBtn) {
    elements.captureStartBtn.disabled = !canProxy || !attached;
  }
  if (elements.captureStopBtn) {
    elements.captureStopBtn.disabled = !canProxy || !attached;
  }
  if (elements.intervalInput) {
    elements.intervalInput.disabled = !canProxy || !attached;
  }
}

function _setCctvAttachUi(clusterUuid, attached) {
  const cu = String(clusterUuid ?? '').trim();
  if (!cu) return;
  _setClusterAttachedStatus(cu, attached);
  const entry = _cctvCards.get(cu);
  _applyAttachStateToElements(entry, !!attached);
}

function _clearCctvPreview(clusterUuid) {
  const cu = String(clusterUuid ?? '').trim();
  if (!cu) return;
  const entry = _cctvCards.get(cu);
  if (entry && entry.imgEl) {
    entry.imgEl.removeAttribute('src');
  }
}

function _intervalSecondsFromInput(el, fallback = 0.5) {
  const raw = String(el?.value || '').trim();
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return Math.max(0.1, n);
}

function _computeImageNormalized(imgEl, ev) {
  const rect = imgEl.getBoundingClientRect();
  const clickX = ev.clientX - rect.left;
  const clickY = ev.clientY - rect.top;
  if (rect.width <= 0 || rect.height <= 0) return null;

  const naturalW = imgEl.naturalWidth || 0;
  const naturalH = imgEl.naturalHeight || 0;
  if (naturalW > 0 && naturalH > 0) {
    const scale = Math.min(rect.width / naturalW, rect.height / naturalH);
    const drawnW = naturalW * scale;
    const drawnH = naturalH * scale;
    const offsetX = (rect.width - drawnW) / 2;
    const offsetY = (rect.height - drawnH) / 2;
    const dx = clickX - offsetX;
    const dy = clickY - offsetY;
    if (dx < 0 || dy < 0 || dx > drawnW || dy > drawnH) {
      return null;
    }
    return { x: dx / drawnW, y: dy / drawnH };
  }

  return { x: clickX / rect.width, y: clickY / rect.height };
}

async function _sendCctvClick(cluster, imgEl, ev) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return;
  if (!cluster?.baseUrl) return _setManageStatus('Cluster baseUrl is not set.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate cluster UUID detected.');
  if (!_isClusterAttached(cluster)) return _setManageStatus('Cluster app is not attached.');

  const norm = _computeImageNormalized(imgEl, ev);
  if (!norm) return;

  const x = Math.max(0, Math.min(1, Number(norm.x)));
  const y = Math.max(0, Math.min(1, Number(norm.y)));

  _setManageStatus(`Sending click to ${_clusterLabel(cluster)}...`);
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/control/click', { x, y });
    _setManageStatus(`Click sent to ${_clusterLabel(cluster)} (${x.toFixed(3)}, ${y.toFixed(3)}).`);
  } catch (err) {
    _setManageStatus(`Click failed: ${err?.message ?? err}`);
  }
}

async function _loadAppStatusForCluster(cluster, elements) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu || !cluster?.baseUrl || _isDuplicateCluster(cluster)) return;
  try {
    const data = await _getJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/app/status`);
    const attached = !!(data && data.attached);
    _setClusterAttachedStatus(cu, attached);
    const entry = elements || _cctvCards.get(cu);
    _applyAttachStateToElements(entry, attached);
  } catch (err) {
    // Best-effort; leave existing state.
  }
}

function _refreshClusterAppStatus(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return;
  const entry = _cctvCards.get(cu);
  return _loadAppStatusForCluster(cluster, entry);
}

function _ensureCctvCards() {
  if (!cctvGridEl) return;
  _ensureDragHandlers();
  const clusters = _applyClusterOrder(_cachedClusters);
  const key = clusters.map(c => `${String(c?.uuid ?? '')}|${String(c?.label ?? '')}|${String(c?.baseUrl ?? '')}`).join('|');
  if (key === _cctvLayoutKey) return;
  _cctvLayoutKey = key;

  const activeSet = new Set(clusters.map(c => String(c?.uuid ?? '')));
  for (const [cu] of _cctvStreams.entries()) {
    if (!activeSet.has(cu)) {
      _closeCctvStream(cu);
    }
  }

  cctvGridEl.textContent = '';
  _cctvCards = new Map();

  if (clusters.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'clusterEmpty';
    empty.textContent = 'No clusters registered yet.';
    cctvGridEl.appendChild(empty);
    return;
  }

  for (const cluster of clusters) {
    const card = document.createElement('div');
    card.className = 'cctvCard';
    card.dataset.uuid = String(cluster.uuid ?? '');

    const header = document.createElement('div');
    header.className = 'cctvHeader';

    const dragHandle = document.createElement('span');
    dragHandle.className = 'cctvDrag';
    dragHandle.textContent = 'drag';
    dragHandle.setAttribute('draggable', 'true');
    dragHandle.addEventListener('dragstart', (ev) => {
      _draggingUuid = String(cluster.uuid ?? '');
      card.classList.add('dragging');
      if (ev.dataTransfer) {
        ev.dataTransfer.effectAllowed = 'move';
        ev.dataTransfer.setData('text/plain', _draggingUuid);
      }
    });
    dragHandle.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      _draggingUuid = null;
      _clearDropIndicator();
    });

    const title = document.createElement('div');
    title.className = 'cctvTitle';
    title.textContent = _clusterLabel(cluster);

    const pill = document.createElement('span');
    const initialState = !cluster?.baseUrl ? 'no-url' : (_isDuplicateCluster(cluster) ? 'duplicate' : 'idle');
    const pillInfo = _cctvPillInfo(initialState);
    pill.className = `clusterPill ${pillInfo.cls}`;
    pill.textContent = pillInfo.text;

    header.appendChild(dragHandle);
    header.appendChild(title);
    header.appendChild(pill);

    const meta = document.createElement('div');
    meta.className = 'cctvMeta';
    const baseUrl = String(cluster.baseUrl ?? '').trim();
    const clusterUuid = String(cluster.uuid ?? '').trim();
    const parts = [];
    if (clusterUuid) parts.push(`cluster:${clusterUuid}`);
    if (baseUrl) parts.push(baseUrl);
    meta.textContent = parts.join(' | ');

    const img = document.createElement('img');
    img.className = 'cctvImage';
    img.alt = `${_clusterLabel(cluster)} capture`;
    img.addEventListener('click', (ev) => {
      _sendCctvClick(cluster, img, ev);
    });

    const status = document.createElement('div');
    status.className = 'cctvMeta';
    status.textContent = pillInfo.text;

    const attached = _isClusterAttached(cluster);
    const attachStatus = document.createElement('div');
    attachStatus.className = 'cctvMeta';
    attachStatus.textContent = attached ? 'attached' : 'detached';

    const controls = document.createElement('div');
    controls.className = 'cctvControls';

    const appPathRow = document.createElement('div');
    appPathRow.className = 'row';
    const appPathLabel = document.createElement('label');
    appPathLabel.textContent = 'App path';
    const appPathInput = document.createElement('input');
    appPathInput.type = 'text';
    appPathInput.placeholder = 'C:\\Apps\\MyApp.exe';
    appPathRow.appendChild(appPathLabel);
    appPathRow.appendChild(appPathInput);

    const titleRow = document.createElement('div');
    titleRow.className = 'row';
    const titleLabel = document.createElement('label');
    titleLabel.textContent = 'Window title';
    const titleInput = document.createElement('input');
    titleInput.type = 'text';
    titleInput.placeholder = 'Exact window title';
    titleRow.appendChild(titleLabel);
    titleRow.appendChild(titleInput);

    const geomRow = document.createElement('div');
    geomRow.className = 'row';
    const geomLabel = document.createElement('label');
    geomLabel.textContent = 'Window position/size';
    const geomInputs = document.createElement('div');
    geomInputs.className = 'buttons cctvGeom';
    const leftInput = document.createElement('input');
    leftInput.type = 'number';
    leftInput.placeholder = 'left';
    const topInput = document.createElement('input');
    topInput.type = 'number';
    topInput.placeholder = 'top';
    const widthInput = document.createElement('input');
    widthInput.type = 'number';
    widthInput.placeholder = 'width';
    const heightInput = document.createElement('input');
    heightInput.type = 'number';
    heightInput.placeholder = 'height';
    geomInputs.appendChild(leftInput);
    geomInputs.appendChild(topInput);
    geomInputs.appendChild(widthInput);
    geomInputs.appendChild(heightInput);
    geomRow.appendChild(geomLabel);
    geomRow.appendChild(geomInputs);

    const actionRow = document.createElement('div');
    actionRow.className = 'buttons cctvActions';

    const canProxy = Boolean(cluster?.baseUrl) && !_isDuplicateCluster(cluster);
    const launchBtn = document.createElement('button');
    launchBtn.type = 'button';
    launchBtn.textContent = 'Launch';
    launchBtn.disabled = !canProxy || attached;
    launchBtn.addEventListener('click', () => {
      const geometry = _geometryPayloadFromInputs(leftInput, topInput, widthInput, heightInput);
      _appLaunchCluster(cluster, appPathInput.value, geometry);
    });
    actionRow.appendChild(launchBtn);

    const attachBtn = document.createElement('button');
    attachBtn.type = 'button';
    attachBtn.textContent = 'Attach';
    attachBtn.disabled = !canProxy || attached;
    attachBtn.addEventListener('click', () => {
      const geometry = _geometryPayloadFromInputs(leftInput, topInput, widthInput, heightInput);
      _appAttachCluster(cluster, titleInput.value, geometry);
    });
    actionRow.appendChild(attachBtn);

    const focusBtn = document.createElement('button');
    focusBtn.type = 'button';
    focusBtn.textContent = 'Focus';
    focusBtn.disabled = !canProxy;
    focusBtn.addEventListener('click', () => {
      _appFocusCluster(cluster, titleInput.value);
    });
    actionRow.appendChild(focusBtn);

    const resizeBtn = document.createElement('button');
    resizeBtn.type = 'button';
    resizeBtn.textContent = 'Resize';
    resizeBtn.disabled = !canProxy;
    resizeBtn.addEventListener('click', () => {
      const geometry = _geometryPayloadFromInputs(leftInput, topInput, widthInput, heightInput);
      _appResizeCluster(cluster, geometry);
    });
    actionRow.appendChild(resizeBtn);

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.textContent = 'Close';
    closeBtn.disabled = !canProxy;
    closeBtn.addEventListener('click', () => _appCloseCluster(cluster));
    actionRow.appendChild(closeBtn);

    const detachBtn = document.createElement('button');
    detachBtn.type = 'button';
    detachBtn.textContent = 'Detach';
    detachBtn.disabled = !canProxy;
    detachBtn.addEventListener('click', () => _appDetachCluster(cluster));
    actionRow.appendChild(detachBtn);

    const resetUuidBtn = document.createElement('button');
    resetUuidBtn.type = 'button';
    resetUuidBtn.textContent = 'Reset UUID';
    resetUuidBtn.disabled = !cluster?.baseUrl;
    resetUuidBtn.addEventListener('click', () => _resetClusterUuid(cluster));
    actionRow.appendChild(resetUuidBtn);

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.textContent = 'Remove';
    removeBtn.addEventListener('click', () => _removeCluster(cluster));
    actionRow.appendChild(removeBtn);

    const intervalRow = document.createElement('div');
    intervalRow.className = 'row';
    const intervalLabel = document.createElement('label');
    intervalLabel.textContent = 'Capture interval (seconds)';
    const intervalInput = document.createElement('input');
    intervalInput.type = 'number';
    intervalInput.min = '0.1';
    intervalInput.step = '0.1';
    intervalInput.value = '0.5';
    intervalRow.appendChild(intervalLabel);
    intervalRow.appendChild(intervalInput);

    const captureRow = document.createElement('div');
    captureRow.className = 'buttons cctvActions';
    const captureStartBtn = document.createElement('button');
    captureStartBtn.type = 'button';
    captureStartBtn.textContent = 'Start Capture';
    captureStartBtn.disabled = !canProxy || !attached;
    captureStartBtn.addEventListener('click', () => {
      const interval = _intervalSecondsFromInput(intervalInput, 0.5);
      _captureStartCluster(cluster, interval);
    });
    captureRow.appendChild(captureStartBtn);

    const captureStopBtn = document.createElement('button');
    captureStopBtn.type = 'button';
    captureStopBtn.textContent = 'Stop Capture';
    captureStopBtn.disabled = !canProxy || !attached;
    captureStopBtn.addEventListener('click', () => _captureStopCluster(cluster));
    captureRow.appendChild(captureStopBtn);

    intervalInput.disabled = !canProxy || !attached;

    for (const el of [appPathInput, titleInput, leftInput, topInput, widthInput, heightInput]) {
      if (!el) continue;
      el.disabled = !canProxy;
    }

    _loadAppDefaultsForCluster(cluster, {
      appPathEl: appPathInput,
      titleEl: titleInput,
      leftEl: leftInput,
      topEl: topInput,
      widthEl: widthInput,
      heightEl: heightInput,
    });

    controls.appendChild(appPathRow);
    controls.appendChild(titleRow);
    controls.appendChild(geomRow);
    controls.appendChild(actionRow);
    controls.appendChild(intervalRow);
    controls.appendChild(captureRow);

    const manage = _buildAutomationSection(cluster, canProxy);

    card.appendChild(header);
    card.appendChild(meta);
    card.appendChild(img);
    card.appendChild(status);
    card.appendChild(attachStatus);
    card.appendChild(controls);
    card.appendChild(manage);

    cctvGridEl.appendChild(card);
    _cctvCards.set(String(cluster.uuid ?? ''), {
      imgEl: img,
      statusEl: status,
      pillEl: pill,
      attachStatusEl: attachStatus,
      launchBtn: launchBtn,
      attachBtn: attachBtn,
      captureStartBtn: captureStartBtn,
      captureStopBtn: captureStopBtn,
      intervalInput: intervalInput,
      canProxy: canProxy,
    });

    _loadAppStatusForCluster(cluster, {
      attachStatusEl: attachStatus,
      launchBtn: launchBtn,
      attachBtn: attachBtn,
      captureStartBtn: captureStartBtn,
      captureStopBtn: captureStopBtn,
      intervalInput: intervalInput,
      canProxy: canProxy,
    });
  }
}

function _updateCctvCardState(clusterUuid, state, detail) {
  const entry = _cctvCards.get(String(clusterUuid));
  if (!entry) return;
  const pillInfo = _cctvPillInfo(state);
  entry.pillEl.className = `clusterPill ${pillInfo.cls}`;
  entry.pillEl.textContent = pillInfo.text;
  const detailText = detail ? ` ${detail}` : '';
  entry.statusEl.textContent = `${pillInfo.text}${detailText}`;
}

let _cctvSocket = null;
let _cctvSubscribedUuids = new Set();

function _ensureCctvSocket() {
    if (_cctvSocket && (_cctvSocket.readyState === WebSocket.OPEN || _cctvSocket.readyState === WebSocket.CONNECTING)) {
        return;
    }

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${proto}//${host}/api/orchestrator/cctv/ws`;

    _cctvSocket = new WebSocket(url);

    _cctvSocket.onopen = () => {
        _sendCctvSubscriptions();
    };

    _cctvSocket.onmessage = (ev) => {
        try {
            const updates = JSON.parse(ev.data);
            if (Array.isArray(updates)) {
                for (const item of updates) {
                    const cu = String(item.uuid ?? '');
                    const b64 = String(item.b64 ?? '');
                    const entry = _cctvCards.get(cu);
                    if (entry && entry.imgEl && b64) {
                        entry.imgEl.src = `data:image/jpeg;base64,${b64}`;
                        _updateCctvCardState(cu, 'live', '');
                    }
                }
            }
        } catch {
            // ignore
        }
    };

    _cctvSocket.onclose = () => {
        // Retry after delay if we still have subscriptions
        if (_cctvSubscribedUuids.size > 0) {
            setTimeout(_ensureCctvSocket, 2000);
        }
    };
}

function _sendCctvSubscriptions() {
    if (!_cctvSocket || _cctvSocket.readyState !== WebSocket.OPEN) return;
    const list = Array.from(_cctvSubscribedUuids);
    _cctvSocket.send(JSON.stringify(list));
}

function _startCctvStream(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return;

  _cctvSubscribedUuids.add(cu);
  _ensureCctvSocket();
  _sendCctvSubscriptions();
}

function _closeCctvStream(clusterUuid) {
  const cu = String(clusterUuid ?? '').trim();
  if (_cctvSubscribedUuids.has(cu)) {
      _cctvSubscribedUuids.delete(cu);
      _sendCctvSubscriptions();
  }
}

async function _captureStartCluster(cluster, intervalSeconds) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (!cluster?.baseUrl) return _setManageStatus('Cluster baseUrl is not set.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate cluster UUID detected.');
  if (!_isClusterAttached(cluster)) return _setManageStatus('Cluster app is not attached.');
  const interval = Math.max(0.1, Number(intervalSeconds) || 0.5);
  _setManageStatus(`Starting capture on ${_clusterLabel(cluster)}...`);
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/capture/start', { intervalSeconds: interval });
    _startCctvStream(cluster);
    _updateCctvCardState(cu, 'live', 'starting');
    _setManageStatus(`Capture started on ${_clusterLabel(cluster)}.`);
  } catch (err) {
    _updateCctvCardState(cu, 'error', '');
    _setManageStatus(`Start capture failed: ${err?.message ?? err}`);
  }
}

async function _captureStopCluster(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (!cluster?.baseUrl) return _setManageStatus('Cluster baseUrl is not set.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate cluster UUID detected.');
  _setManageStatus(`Stopping capture on ${_clusterLabel(cluster)}...`);
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/capture/stop`, {});
  } catch (err) {
    _setManageStatus(`Stop capture failed: ${err?.message ?? err}`);
  }
  _closeCctvStream(cu);
  _updateCctvCardState(cu, 'stopped', '');
  _setManageStatus(`Capture stopped on ${_clusterLabel(cluster)}.`);
}
