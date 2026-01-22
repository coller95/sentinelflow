function _buildAutomationSection(cluster, canProxy) {
  const manage = document.createElement('details');
  manage.className = 'cctvManage';
  const manageSummary = document.createElement('summary');
  manageSummary.textContent = 'Automation';
  manage.appendChild(manageSummary);

  const manageBody = document.createElement('div');
  manageBody.className = 'cctvManageBody';
  manage.appendChild(manageBody);

  const buildBlock = (title) => {
    const block = document.createElement('div');
    block.className = 'cctvManageBlock';

    const header = document.createElement('div');
    header.className = 'cctvManageHeader';

    const heading = document.createElement('div');
    heading.className = 'cctvManageTitle';
    heading.textContent = title;

    const tools = document.createElement('div');
    tools.className = 'cctvManageTools';

    const refreshBtn = document.createElement('button');
    refreshBtn.type = 'button';
    refreshBtn.textContent = 'Refresh';

    tools.appendChild(refreshBtn);
    header.appendChild(heading);
    header.appendChild(tools);
    block.appendChild(header);

    const list = document.createElement('div');
    list.className = 'autoList';
    block.appendChild(list);

    return { block, list, refreshBtn, tools };
  };

  const actionsBlock = buildBlock('Actions');
  const conditionsBlock = buildBlock('Conditions');
  const triggersBlock = buildBlock('Triggers');

  manageBody.appendChild(actionsBlock.block);
  manageBody.appendChild(conditionsBlock.block);
  manageBody.appendChild(triggersBlock.block);

  const makeBadge = (text, tone) => {
    const badge = document.createElement('span');
    badge.className = `autoBadge${tone ? ` autoBadge--${tone}` : ''}`;
    badge.textContent = text;
    return badge;
  };

  const makeEmpty = (listEl, text) => {
    listEl.textContent = '';
    const empty = document.createElement('div');
    empty.className = 'autoEmpty';
    empty.textContent = text;
    listEl.appendChild(empty);
  };

  const fmtNumber = (value, digits = 2) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return '-';
    return num.toFixed(digits);
  };

  const fmtTime = (seconds) => {
    const num = Number(seconds);
    if (!Number.isFinite(num)) return '-';
    return new Date(num * 1000).toLocaleTimeString();
  };

  const fmtValue = (value) => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value);
      } catch {
        return '[object]';
      }
    }
    return String(value);
  };

  const fmtActionStep = (step) => {
    if (!step || !step.action) return 'Step';
    const action = String(step.action);
    const params = step.parameters && typeof step.parameters === 'object' ? step.parameters : {};
    if (action === 'Click') {
      const x = params.x ?? params.xNormalized;
      const y = params.y ?? params.yNormalized;
      return `Click ${fmtNumber(x, 2)}, ${fmtNumber(y, 2)}`;
    }
    if (action === 'KeyStroke') {
      const key = params.keyName ?? params.key;
      return `Key ${String(key || '').trim() || '-'}`;
    }
    if (action === 'Delay') {
      const ms = params.ms ?? params.seconds;
      return `Delay ${String(ms ?? '-')}`;
    }
    return action;
  };

  let actionsList = [];
  let actionsLoaded = false;
  let conditionsList = [];
  let conditionsStatus = null;
  let conditionsLoaded = false;
  let triggersList = [];
  let triggersStatus = null;
  let triggersLoaded = false;

  const renderActions = () => {
    if (!actionsList || actionsList.length === 0) {
      return makeEmpty(actionsBlock.list, 'No actions yet.');
    }

    actionsBlock.list.textContent = '';

    for (const item of actionsList) {
      const card = document.createElement('div');
      card.className = 'autoItem';

      const header = document.createElement('div');
      header.className = 'autoItemTop';

      const title = document.createElement('div');
      title.className = 'autoItemTitle';
      title.textContent = String(item?.name || 'Action');

      const badges = document.createElement('div');
      badges.className = 'autoBadges';
      const steps = Array.isArray(item?.steps) ? item.steps : [];
      badges.appendChild(makeBadge(`${steps.length} steps`, 'muted'));

      header.appendChild(title);
      header.appendChild(badges);
      card.appendChild(header);

      const meta = document.createElement('div');
      meta.className = 'autoMeta';
      meta.textContent = String(item?.uuid || '');
      card.appendChild(meta);

      if (steps.length > 0) {
        const preview = steps.slice(0, 3).map(fmtActionStep).join(' | ');
        const previewLine = document.createElement('div');
        previewLine.className = 'autoNote';
        previewLine.textContent = steps.length > 3 ? `${preview} | +${steps.length - 3} more` : preview;
        card.appendChild(previewLine);
      }

      const actions = document.createElement('div');
      actions.className = 'autoButtons';
      const runBtn = document.createElement('button');
      runBtn.type = 'button';
      runBtn.textContent = 'Run';
      runBtn.disabled = !canProxy || !item?.uuid;
      runBtn.addEventListener('click', () => {
        const uuid = String(item?.uuid || '').trim();
        if (!uuid) return _setManageStatus('Action UUID is required.');
        _clusterPost(cluster, '/actions/run', { uuid }, null, 'Action run');
      });
      actions.appendChild(runBtn);
      card.appendChild(actions);

      actionsBlock.list.appendChild(card);
    }
  };

  const renderConditions = () => {
    if (!conditionsList || conditionsList.length === 0) {
      return makeEmpty(conditionsBlock.list, 'No conditions yet.');
    }

    const statusByUuid = conditionsStatus && typeof conditionsStatus === 'object'
      ? (conditionsStatus.byUuid || {})
      : {};

    const ordered = Array.isArray(conditionsStatus?.order)
      ? conditionsStatus.order.map((id) => String(id))
      : [];

    let items = conditionsList.slice();
    if (ordered.length > 0) {
      const index = new Map(ordered.map((id, idx) => [id, idx]));
      items.sort((a, b) => (index.get(String(a?.uuid)) ?? 999) - (index.get(String(b?.uuid)) ?? 999));
    }

    conditionsBlock.list.textContent = '';

    for (const item of items) {
      const card = document.createElement('div');
      card.className = 'autoItem';

      const header = document.createElement('div');
      header.className = 'autoItemTop';

      const title = document.createElement('div');
      title.className = 'autoItemTitle';
      title.textContent = String(item?.name || 'Condition');

      const badges = document.createElement('div');
      badges.className = 'autoBadges';
      badges.appendChild(makeBadge(String(item?.type || 'Unknown'), 'muted'));

      header.appendChild(title);
      header.appendChild(badges);
      card.appendChild(header);

      const meta = document.createElement('div');
      meta.className = 'autoMeta';
      meta.textContent = String(item?.uuid || '');
      card.appendChild(meta);

      const roi = item?.roi;
      if (roi && typeof roi === 'object') {
        const roiLine = document.createElement('div');
        roiLine.className = 'autoNote';
        roiLine.textContent = `ROI ${fmtNumber(roi.xNormalized)} , ${fmtNumber(roi.yNormalized)}  ${fmtNumber(roi.widthNormalized)} x ${fmtNumber(roi.heightNormalized)}`;
        card.appendChild(roiLine);
      }

      const status = statusByUuid[String(item?.uuid || '')];
      if (status && Object.prototype.hasOwnProperty.call(status, 'last')) {
        const lastLine = document.createElement('div');
        lastLine.className = 'autoNote';
        lastLine.textContent = `Last: ${fmtValue(status.last)}`;
        card.appendChild(lastLine);
      }
      if (status && Object.prototype.hasOwnProperty.call(status, 'lastStable')) {
        const lastStableLine = document.createElement('div');
        lastStableLine.className = 'autoNote';
        lastStableLine.textContent = `Stable: ${fmtValue(status.lastStable)}`;
        card.appendChild(lastStableLine);
      }

      if (status && (status.templateThumbBase64 || status.cropThumbBase64)) {
        const thumbs = document.createElement('div');
        thumbs.className = 'autoThumbs';

        if (status.templateThumbBase64) {
          const img = document.createElement('img');
          img.className = 'autoThumb';
          img.alt = 'Template';
          img.src = `data:image/png;base64,${status.templateThumbBase64}`;
          thumbs.appendChild(img);
        }
        if (status.cropThumbBase64) {
          const img = document.createElement('img');
          img.className = 'autoThumb';
          img.alt = 'Crop';
          img.src = `data:image/png;base64,${status.cropThumbBase64}`;
          thumbs.appendChild(img);
        }

        card.appendChild(thumbs);
      }

      conditionsBlock.list.appendChild(card);
    }
  };

  const renderTriggers = () => {
    if (!triggersList || triggersList.length === 0) {
      return makeEmpty(triggersBlock.list, 'No triggers yet.');
    }

    const statusItems = Array.isArray(triggersStatus?.items) ? triggersStatus.items : [];
    const statusByUuid = new Map(statusItems.map((item) => [String(item?.uuid || ''), item]));

    triggersBlock.list.textContent = '';

    for (const item of triggersList) {
      const uuid = String(item?.uuid || '').trim();
      const status = statusByUuid.get(uuid);

      const card = document.createElement('div');
      card.className = 'autoItem';

      const header = document.createElement('div');
      header.className = 'autoItemTop';

      const title = document.createElement('div');
      title.className = 'autoItemTitle';
      title.textContent = String(item?.name || 'Trigger');

      const badges = document.createElement('div');
      badges.className = 'autoBadges';
      const enabled = Boolean(item?.enabled ?? status?.enabled);
      badges.appendChild(makeBadge(enabled ? 'Enabled' : 'Disabled', enabled ? 'ok' : 'warn'));
      if (status) {
        badges.appendChild(makeBadge(status.isMet ? 'Met' : 'Idle', status.isMet ? 'ok' : 'muted'));
      }

      header.appendChild(title);
      header.appendChild(badges);
      card.appendChild(header);

      const meta = document.createElement('div');
      meta.className = 'autoMeta';
      meta.textContent = uuid;
      card.appendChild(meta);

      const actionName = status?.actionName || item?.action || 'Unassigned';
      const actionLine = document.createElement('div');
      actionLine.className = 'autoNote';
      actionLine.textContent = `Action: ${actionName}`;
      card.appendChild(actionLine);

      const criteriaCount = Array.isArray(item?.triggerCiterias) ? item.triggerCiterias.length : 0;
      const mode = String(item?.criteriaMode || 'All');
      const criteriaLine = document.createElement('div');
      criteriaLine.className = 'autoNote';
      criteriaLine.textContent = `Criteria: ${criteriaCount} (${mode})`; 
      card.appendChild(criteriaLine);

      if (item?.retriggerMs) {
        const retriggerLine = document.createElement('div');
        retriggerLine.className = 'autoNote';
        retriggerLine.textContent = `Retrigger: ${item.retriggerMs} ms`;
        card.appendChild(retriggerLine);
      }

      if (status) {
        const fireLine = document.createElement('div');
        fireLine.className = 'autoNote';
        fireLine.textContent = `Fires: ${status.fireCount ?? 0} | Last: ${fmtTime(status.lastFireUnix)}`;
        card.appendChild(fireLine);
      }

      const actions = document.createElement('div');
      actions.className = 'autoButtons';
      const toggleBtn = document.createElement('button');
      toggleBtn.type = 'button';
      toggleBtn.textContent = enabled ? 'Disable' : 'Enable';
      toggleBtn.disabled = !canProxy || !uuid;
      toggleBtn.addEventListener('click', async () => {
        if (!uuid) return _setManageStatus('Trigger UUID is required.');
        await _clusterPost(cluster, '/triggers/set_enabled', { uuid, enabled: !enabled }, null, 'Trigger');
        await loadTriggers();
      });
      actions.appendChild(toggleBtn);
      card.appendChild(actions);

      triggersBlock.list.appendChild(card);
    }
  };

  const loadActions = async () => {
    const data = await _clusterGet(cluster, '/actions', null, 'Actions');
    actionsList = Array.isArray(data) ? data : [];
    actionsLoaded = true;
    renderActions();
  };

  const loadConditions = async () => {
    const [listData, statusData] = await Promise.all([
      _clusterGet(cluster, '/conditions', null, 'Conditions'),
      _clusterGet(cluster, '/conditions/status', null, 'Conditions status'),
    ]);

    conditionsList = Array.isArray(listData) ? listData : [];
    conditionsStatus = statusData && typeof statusData === 'object' ? statusData : null;
    conditionsLoaded = true;
    renderConditions();
  };

  const loadTriggers = async () => {
    const [listData, statusData] = await Promise.all([
      _clusterGet(cluster, '/triggers', null, 'Triggers'),
      _clusterGet(cluster, '/triggers/status', null, 'Triggers status'),
    ]);

    triggersList = Array.isArray(listData) ? listData : [];
    triggersStatus = statusData && typeof statusData === 'object' ? statusData : null;
    triggersLoaded = true;
    renderTriggers();
  };

  actionsBlock.refreshBtn.addEventListener('click', loadActions);
  conditionsBlock.refreshBtn.addEventListener('click', loadConditions);
  triggersBlock.refreshBtn.addEventListener('click', loadTriggers);

  for (const btn of [actionsBlock.refreshBtn, conditionsBlock.refreshBtn, triggersBlock.refreshBtn]) {
    btn.disabled = !canProxy;
  }

  if (!canProxy) {
    makeEmpty(actionsBlock.list, 'Cluster unavailable.');
    makeEmpty(conditionsBlock.list, 'Cluster unavailable.');
    makeEmpty(triggersBlock.list, 'Cluster unavailable.');
  }

  manage.addEventListener('toggle', () => {
    if (!manage.open || !canProxy) return;
    if (!actionsLoaded) loadActions();
    if (!conditionsLoaded) loadConditions();
    if (!triggersLoaded) loadTriggers();
  });

  return manage;
}
