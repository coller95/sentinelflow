async function _appLaunchCluster(cluster, appPath, geometry) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate cluster UUID detected.');
  const app_path = String(appPath || '').trim();
  if (!app_path) return _setManageStatus('App path is required.');
  const payload = geometry || _defaultGeometryPayload();
  _setManageStatus(`Launching app on ${_clusterLabel(cluster)}...`);
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/app/launch', { app_path, ...payload });
    _setManageStatus(`App launched on ${_clusterLabel(cluster)}.`);
    if (typeof _refreshClusterAppStatus === 'function') {
      await _refreshClusterAppStatus(cluster);
    }
  } catch (err) {
    _setManageStatus(`Launch failed: ${err?.message ?? err}`);
  }
}

async function _appAttachCluster(cluster, windowTitle, geometry) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate cluster UUID detected.');
  const window_title = String(windowTitle || '').trim();
  if (!window_title) return _setManageStatus('Window title is required.');
  const payload = geometry || _defaultGeometryPayload();
  _setManageStatus(`Attaching app on ${_clusterLabel(cluster)}...`);
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/app/attach', { window_title, ...payload });
    _setManageStatus(`App attached on ${_clusterLabel(cluster)}.`);
    if (typeof _refreshClusterAppStatus === 'function') {
      await _refreshClusterAppStatus(cluster);
    }
  } catch (err) {
    _setManageStatus(`Attach failed: ${err?.message ?? err}`);
  }
}

async function _appCloseCluster(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate cluster UUID detected.');
  _setManageStatus(`Closing app on ${_clusterLabel(cluster)}...`);
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/app/close`, {});
    _setManageStatus(`App closed on ${_clusterLabel(cluster)}.`);
  } catch (err) {
    _setManageStatus(`Close failed: ${err?.message ?? err}`);
  }
}

async function _appDetachCluster(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate cluster UUID detected.');
  _setManageStatus(`Detaching app on ${_clusterLabel(cluster)}...`);
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/app/detach`, {});
    if (typeof _closeCctvStream === 'function') {
      _closeCctvStream(cu);
    }
    if (typeof _updateCctvCardState === 'function') {
      _updateCctvCardState(cu, 'stopped', 'detached');
    }
    if (typeof _setCctvAttachUi === 'function') {
      _setCctvAttachUi(cu, false);
    } else if (typeof _setClusterAttachedStatus === 'function') {
      _setClusterAttachedStatus(cu, false);
    }
    if (typeof _clearCctvPreview === 'function') {
      _clearCctvPreview(cu);
    }
    _setManageStatus(`App detached on ${_clusterLabel(cluster)}.`);
    await refreshClusters();
  } catch (err) {
    _setManageStatus(`Detach failed: ${err?.message ?? err}`);
  }
}

async function _appFocusCluster(cluster, windowTitle) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate cluster UUID detected.');
  const window_title = String(windowTitle || '').trim();
  const payload = window_title ? { window_title } : {};
  _setManageStatus(`Focusing app on ${_clusterLabel(cluster)}...`);
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/app/focus', payload);
    _setManageStatus(`Focused app on ${_clusterLabel(cluster)}.`);
  } catch (err) {
    _setManageStatus(`Focus failed: ${err?.message ?? err}`);
  }
}

async function _appResizeCluster(cluster, geometry) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (_isDuplicateCluster(cluster)) return _setManageStatus('Duplicate cluster UUID detected.');
  const payload = geometry || _defaultGeometryPayload();
  _setManageStatus(`Resizing app on ${_clusterLabel(cluster)}...`);
  try {
    await _postProxy(cu, '/api/orchestrator/clusters/{uuid}/app/resize', payload);
    _setManageStatus(`Resized app on ${_clusterLabel(cluster)}.`);
  } catch (err) {
    _setManageStatus(`Resize failed: ${err?.message ?? err}`);
  }
}

async function _removeCluster(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return;
  if (!confirm(`Remove cluster ${_clusterLabel(cluster)} (${cu})?`)) return;
  _setManageStatus(`Removing ${_clusterLabel(cluster)}...`);
  try {
    await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/remove`, {});
    _closeCctvStream(cu);
    _setManageStatus(`Removed ${_clusterLabel(cluster)}.`);
    await refreshClusters();
  } catch (err) {
    _setManageStatus(`Remove failed: ${err?.message ?? err}`);
  }
}

async function _resetClusterUuid(cluster) {
  const cu = String(cluster?.uuid ?? '').trim();
  if (!cu) return _setManageStatus('Select a cluster first.');
  if (!cluster?.baseUrl) return _setManageStatus('Cluster baseUrl is not set.');
  const label = _clusterLabel(cluster);
  if (!confirm(`Reset server UUID for ${label}?`)) return;
  _setManageStatus(`Resetting UUID for ${label}...`);
  try {
    const data = await _postJson(`/api/orchestrator/clusters/${encodeURIComponent(cu)}/server/reset_uuid`, {});
    const newUuid = String(data?.cluster?.uuid ?? data?.reset?.serverUuid ?? '').trim();
    _setManageStatus(`UUID reset for ${label}${newUuid ? ` -> ${newUuid}` : ''}.`);
    await refreshClusters();
  } catch (err) {
    _setManageStatus(`Reset UUID failed: ${err?.message ?? err}`);
  }
}
