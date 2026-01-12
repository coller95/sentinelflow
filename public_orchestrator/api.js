async function _getJson(url) {
  const res = await fetch(url, { method: 'GET' });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const detail = data && typeof data === 'object' ? (data.detail ?? null) : null;
    throw new Error(detail ? String(detail) : `HTTP ${res.status}`);
  }
  return data;
}

async function _postJson(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });

  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!res.ok) {
    const detail = data && typeof data === 'object' ? (data.detail ?? null) : null;
    throw new Error(detail ? String(detail) : `HTTP ${res.status}`);
  }

  return data;
}

async function _postProxy(clusterUuid, path, bodyObj) {
  const url = String(path).replace('{uuid}', encodeURIComponent(String(clusterUuid)));
  return await _postJson(url, { body: bodyObj ?? {} });
}

async function _clusterGet(cluster, path, outputEl, label) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return;
  if (!cluster?.baseUrl) return _setManageStatus('Cluster baseUrl is not set.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate server UUID detected.');
  try {
    const data = await _getJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}${path}`);
    if (outputEl) _fillTextArea(outputEl, data);
    if (label) _setManageStatus(`${label} loaded for ${_clusterLabel(cluster)}.`);
    return data;
  } catch (err) {
    _setManageStatus(`${label || 'Request'} failed: ${err?.message ?? err}`);
  }
}

async function _clusterPost(cluster, path, payload, outputEl, label) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return;
  if (!cluster?.baseUrl) return _setManageStatus('Cluster baseUrl is not set.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate server UUID detected.');
  try {
    const data = await _postProxy(cu, `/api/orchestrator/clusters/{uuid}${path}`, payload);
    if (outputEl) _fillTextArea(outputEl, data);
    if (label) _setManageStatus(`${label} sent to ${_clusterLabel(cluster)}.`);
  } catch (err) {
    _setManageStatus(`${label || 'Request'} failed: ${err?.message ?? err}`);
  }
}
