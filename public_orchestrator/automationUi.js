function _buildAutomationSection(cluster, canProxy) {
  const manage = document.createElement('details');
  manage.className = 'cctvManage';
  const manageSummary = document.createElement('summary');
  manageSummary.textContent = 'Automation';
  manage.appendChild(manageSummary);

  const manageBody = document.createElement('div');
  manageBody.className = 'cctvManageBody';
  manage.appendChild(manageBody);

  const actionsBlock = document.createElement('div');
  actionsBlock.className = 'cctvManageBlock';
  const actionsTitle = document.createElement('div');
  actionsTitle.className = 'cctvManageTitle';
  actionsTitle.textContent = 'Actions';
  actionsBlock.appendChild(actionsTitle);

  const actionBuilder = document.createElement('div');
  actionBuilder.className = 'cctvManageForm';

  const actionNameRow = document.createElement('div');
  actionNameRow.className = 'row';
  const actionNameLabel = document.createElement('label');
  actionNameLabel.textContent = 'Action name';
  const actionNameInput = document.createElement('input');
  actionNameInput.type = 'text';
  actionNameInput.placeholder = 'Heal';
  actionNameRow.appendChild(actionNameLabel);
  actionNameRow.appendChild(actionNameInput);
  actionBuilder.appendChild(actionNameRow);

  const actionUuidRow = document.createElement('div');
  actionUuidRow.className = 'row';
  const actionUuidLabel = document.createElement('label');
  actionUuidLabel.textContent = 'Action UUID (optional)';
  const actionUuidInput = document.createElement('input');
  actionUuidInput.type = 'text';
  actionUuidRow.appendChild(actionUuidLabel);
  actionUuidRow.appendChild(actionUuidInput);
  actionBuilder.appendChild(actionUuidRow);

  const actionPresetRow = document.createElement('div');
  actionPresetRow.className = 'row';
  const actionPresetLabel = document.createElement('label');
  actionPresetLabel.textContent = 'Preset';
  const actionPresetWrap = document.createElement('div');
  actionPresetWrap.className = 'buttons';
  const actionPresetSelect = document.createElement('select');
  for (const preset of [
    { label: 'Select preset', value: '' },
    { label: 'Click Center', value: 'click-center' },
    { label: 'Key Stroke (H)', value: 'key-h' },
    { label: 'Delay 200ms', value: 'delay-200' },
  ]) {
    const opt = document.createElement('option');
    opt.value = preset.value;
    opt.textContent = preset.label;
    actionPresetSelect.appendChild(opt);
  }
  const actionPresetBtn = document.createElement('button');
  actionPresetBtn.type = 'button';
  actionPresetBtn.textContent = 'Apply';
  actionPresetWrap.appendChild(actionPresetSelect);
  actionPresetWrap.appendChild(actionPresetBtn);
  actionPresetRow.appendChild(actionPresetLabel);
  actionPresetRow.appendChild(actionPresetWrap);
  actionBuilder.appendChild(actionPresetRow);

  const actionStepTypeRow = document.createElement('div');
  actionStepTypeRow.className = 'row';
  const actionStepTypeLabel = document.createElement('label');
  actionStepTypeLabel.textContent = 'Step type';
  const actionStepType = document.createElement('select');
  for (const name of ['Click', 'KeyStroke', 'Delay']) {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name;
    actionStepType.appendChild(opt);
  }
  actionStepTypeRow.appendChild(actionStepTypeLabel);
  actionStepTypeRow.appendChild(actionStepType);
  actionBuilder.appendChild(actionStepTypeRow);

  const clickRow = document.createElement('div');
  clickRow.className = 'row';
  const clickLabel = document.createElement('label');
  clickLabel.textContent = 'Click (0..1)';
  const clickInputs = document.createElement('div');
  clickInputs.className = 'buttons cctvGeom';
  const clickXInput = document.createElement('input');
  clickXInput.type = 'number';
  clickXInput.step = '0.01';
  clickXInput.placeholder = 'x';
  const clickYInput = document.createElement('input');
  clickYInput.type = 'number';
  clickYInput.step = '0.01';
  clickYInput.placeholder = 'y';
  clickInputs.appendChild(clickXInput);
  clickInputs.appendChild(clickYInput);
  clickRow.appendChild(clickLabel);
  clickRow.appendChild(clickInputs);
  actionBuilder.appendChild(clickRow);

  const keyRow = document.createElement('div');
  keyRow.className = 'row';
  const keyLabel = document.createElement('label');
  keyLabel.textContent = 'Key name';
  const keyInput = document.createElement('input');
  keyInput.type = 'text';
  keyInput.placeholder = 'H';
  keyRow.appendChild(keyLabel);
  keyRow.appendChild(keyInput);
  actionBuilder.appendChild(keyRow);

  const delayRow = document.createElement('div');
  delayRow.className = 'row';
  const delayLabel = document.createElement('label');
  delayLabel.textContent = 'Delay (ms)';
  const delayInput = document.createElement('input');
  delayInput.type = 'number';
  delayInput.min = '0';
  delayInput.step = '10';
  delayInput.placeholder = '200';
  delayRow.appendChild(delayLabel);
  delayRow.appendChild(delayInput);
  actionBuilder.appendChild(delayRow);

  const stepsPreviewRow = document.createElement('div');
  stepsPreviewRow.className = 'row';
  const stepsPreviewLabel = document.createElement('label');
  stepsPreviewLabel.textContent = 'Steps preview';
  const stepsPreview = document.createElement('textarea');
  stepsPreview.className = 'monoBox';
  stepsPreview.rows = 3;
  stepsPreview.readOnly = true;
  stepsPreviewRow.appendChild(stepsPreviewLabel);
  stepsPreviewRow.appendChild(stepsPreview);
  actionBuilder.appendChild(stepsPreviewRow);

  const actionStepButtons = document.createElement('div');
  actionStepButtons.className = 'buttons';
  const addStepBtn = document.createElement('button');
  addStepBtn.type = 'button';
  addStepBtn.textContent = 'Add Step';
  const clearStepsBtn = document.createElement('button');
  clearStepsBtn.type = 'button';
  clearStepsBtn.textContent = 'Clear Steps';
  const buildActionBtn = document.createElement('button');
  buildActionBtn.type = 'button';
  buildActionBtn.textContent = 'Build Payload';
  actionStepButtons.appendChild(addStepBtn);
  actionStepButtons.appendChild(clearStepsBtn);
  actionStepButtons.appendChild(buildActionBtn);
  actionBuilder.appendChild(actionStepButtons);

  const actionSteps = [];
  const updateStepFields = () => {
    const mode = actionStepType.value;
    clickRow.style.display = mode === 'Click' ? '' : 'none';
    keyRow.style.display = mode === 'KeyStroke' ? '' : 'none';
    delayRow.style.display = mode === 'Delay' ? '' : 'none';
  };
  const updateStepsPreview = () => {
    const lines = actionSteps.map((step, idx) => {
      if (step.action === 'Click') return `${idx + 1}. Click x=${step.parameters.x ?? step.parameters.xNormalized} y=${step.parameters.y ?? step.parameters.yNormalized}`;
      if (step.action === 'KeyStroke') return `${idx + 1}. KeyStroke ${step.parameters.keyName ?? step.parameters.key}`;
      if (step.action === 'Delay') return `${idx + 1}. Delay ${step.parameters.ms ?? step.parameters.seconds}s`;
      return `${idx + 1}. ${step.action}`;
    });
    _setPreviewLines(stepsPreview, lines);
  };

  actionStepType.addEventListener('change', updateStepFields);
  updateStepFields();

  actionPresetBtn.addEventListener('click', () => {
    switch (actionPresetSelect.value) {
      case 'click-center':
        actionStepType.value = 'Click';
        clickXInput.value = '0.5';
        clickYInput.value = '0.5';
        break;
      case 'key-h':
        actionStepType.value = 'KeyStroke';
        keyInput.value = 'H';
        break;
      case 'delay-200':
        actionStepType.value = 'Delay';
        delayInput.value = '200';
        break;
      default:
        break;
    }
    updateStepFields();
  });

  addStepBtn.addEventListener('click', () => {
    const kind = actionStepType.value;
    if (kind === 'Click') {
      const x = Math.max(0, Math.min(1, _floatFromInput(clickXInput, 0.5)));
      const y = Math.max(0, Math.min(1, _floatFromInput(clickYInput, 0.5)));
      actionSteps.push({ action: 'Click', parameters: { x, y } });
    } else if (kind === 'KeyStroke') {
      const keyName = String(keyInput.value || '').trim();
      if (!keyName) return _setManageStatus('Key name is required.');
      actionSteps.push({ action: 'KeyStroke', parameters: { keyName } });
    } else if (kind === 'Delay') {
      const ms = Math.max(0, Math.floor(_floatFromInput(delayInput, 0)));
      actionSteps.push({ action: 'Delay', parameters: { ms } });
    }
    updateStepsPreview();
  });

  clearStepsBtn.addEventListener('click', () => {
    actionSteps.length = 0;
    updateStepsPreview();
  });

  buildActionBtn.addEventListener('click', () => {
    const name = String(actionNameInput.value || '').trim();
    if (!name) return _setManageStatus('Action name is required.');
    const uuid = String(actionUuidInput.value || '').trim() || null;
    const payload = { uuid, name, steps: actionSteps.slice() };
    actionPayload.value = JSON.stringify(payload, null, 2);
    _setManageStatus(`Action payload built for ${_clusterLabel(cluster)}.`);
  });

  actionsBlock.appendChild(actionBuilder);

  const actionsSelectRow = document.createElement('div');
  actionsSelectRow.className = 'row';
  const actionsSelectLabel = document.createElement('label');
  actionsSelectLabel.textContent = 'Existing actions';
  const actionsSelectWrap = document.createElement('div');
  actionsSelectWrap.className = 'buttons';
  const actionsSelect = document.createElement('select');
  const actionsLoadBtn = document.createElement('button');
  actionsLoadBtn.type = 'button';
  actionsLoadBtn.textContent = 'Load';
  actionsSelectWrap.appendChild(actionsSelect);
  actionsSelectWrap.appendChild(actionsLoadBtn);
  actionsSelectRow.appendChild(actionsSelectLabel);
  actionsSelectRow.appendChild(actionsSelectWrap);
  actionsBlock.appendChild(actionsSelectRow);

  const actionsOutRow = document.createElement('div');
  actionsOutRow.className = 'row';
  const actionsOutLabel = document.createElement('label');
  actionsOutLabel.textContent = 'List';
  const actionsOut = document.createElement('textarea');
  actionsOut.className = 'monoBox';
  actionsOut.rows = 4;
  actionsOut.readOnly = true;
  actionsOutRow.appendChild(actionsOutLabel);
  actionsOutRow.appendChild(actionsOut);
  actionsBlock.appendChild(actionsOutRow);

  const actionPayloadRow = document.createElement('div');
  actionPayloadRow.className = 'row';
  const actionPayloadLabel = document.createElement('label');
  actionPayloadLabel.textContent = 'Upsert JSON';
  const actionPayload = document.createElement('textarea');
  actionPayload.className = 'monoBox';
  actionPayload.rows = 4;
  actionPayload.placeholder = '{"uuid":null,"name":"My Action","steps":[]}';
  actionPayloadRow.appendChild(actionPayloadLabel);
  actionPayloadRow.appendChild(actionPayload);
  actionsBlock.appendChild(actionPayloadRow);

  const actionsButtons = document.createElement('div');
  actionsButtons.className = 'buttons';
  const actionsFetchBtn = document.createElement('button');
  actionsFetchBtn.type = 'button';
  actionsFetchBtn.textContent = 'Fetch';
  let actionsList = [];
  const loadActionIntoBuilder = (item) => {
    if (!item) return;
    actionNameInput.value = String(item.name ?? '');
    actionUuidInput.value = String(item.uuid ?? '');
    actionSteps.length = 0;
    const steps = Array.isArray(item.steps) ? item.steps : [];
    for (const st of steps) {
      if (!st || !st.action) continue;
      const params = st.parameters && typeof st.parameters === 'object' ? st.parameters : {};
      actionSteps.push({ action: String(st.action), parameters: { ...params } });
    }
    updateStepsPreview();
    actionPayload.value = JSON.stringify({ uuid: item.uuid ?? null, name: item.name ?? '', steps }, null, 2);
  };

  actionsFetchBtn.addEventListener('click', async () => {
    const data = await _clusterGet(cluster, '/actions', actionsOut, 'Actions');
    actionsList = Array.isArray(data) ? data : [];
    _fillSelect(actionsSelect, actionsList, 'uuid', 'name', null);
    if (actionsList.length > 0) {
      actionsSelect.value = String(actionsList[0].uuid ?? '');
      loadActionIntoBuilder(actionsList[0]);
    }
  });
  actionsButtons.appendChild(actionsFetchBtn);

  const actionsRunBtn = document.createElement('button');
  actionsRunBtn.type = 'button';
  actionsRunBtn.textContent = 'Run';
  actionsRunBtn.addEventListener('click', () => {
    const uuid = String(actionUuidInput.value || '').trim();
    if (!uuid) return _setManageStatus('Action UUID is required.');
    _clusterPost(cluster, '/actions/run', { uuid }, actionsOut, 'Action run');
  });
  actionsButtons.appendChild(actionsRunBtn);

  const actionsRemoveBtn = document.createElement('button');
  actionsRemoveBtn.type = 'button';
  actionsRemoveBtn.textContent = 'Remove';
  actionsRemoveBtn.addEventListener('click', () => {
    const uuid = String(actionUuidInput.value || '').trim();
    if (!uuid) return _setManageStatus('Action UUID is required.');
    _clusterPost(cluster, '/actions/remove_uuid', { uuid }, actionsOut, 'Action remove');
  });
  actionsButtons.appendChild(actionsRemoveBtn);

  const actionsUpsertBtn = document.createElement('button');
  actionsUpsertBtn.type = 'button';
  actionsUpsertBtn.textContent = 'Upsert';
  actionsUpsertBtn.addEventListener('click', () => {
    let payload = null;
    try {
      payload = _tryParseJson(actionPayload.value);
    } catch (err) {
      _setManageStatus(`Invalid action JSON: ${err?.message ?? err}`);
      return;
    }
    if (!payload) return _setManageStatus('Action payload is required.');
    _clusterPost(cluster, '/actions/upsert', payload, actionsOut, 'Action upsert');
  });
  actionsButtons.appendChild(actionsUpsertBtn);
  actionsBlock.appendChild(actionsButtons);

  actionsLoadBtn.addEventListener('click', () => {
    const selected = String(actionsSelect.value || '').trim();
    const item = actionsList.find(a => String(a?.uuid ?? '') === selected);
    if (!item) return _setManageStatus('Select an action to load.');
    loadActionIntoBuilder(item);
    _setManageStatus(`Action loaded for ${_clusterLabel(cluster)}.`);
  });

  const conditionsBlock = document.createElement('div');
  conditionsBlock.className = 'cctvManageBlock';
  const conditionsTitle = document.createElement('div');
  conditionsTitle.className = 'cctvManageTitle';
  conditionsTitle.textContent = 'Conditions';
  conditionsBlock.appendChild(conditionsTitle);

  const conditionsBuilder = document.createElement('div');
  conditionsBuilder.className = 'cctvManageForm';

  const conditionUuidRow = document.createElement('div');
  conditionUuidRow.className = 'row';
  const conditionUuidLabel = document.createElement('label');
  conditionUuidLabel.textContent = 'Condition UUID (optional)';
  const conditionUuidInput = document.createElement('input');
  conditionUuidInput.type = 'text';
  conditionUuidRow.appendChild(conditionUuidLabel);
  conditionUuidRow.appendChild(conditionUuidInput);
  conditionsBuilder.appendChild(conditionUuidRow);

  const conditionNameRow = document.createElement('div');
  conditionNameRow.className = 'row';
  const conditionNameLabel = document.createElement('label');
  conditionNameLabel.textContent = 'Condition name';
  const conditionNameInput = document.createElement('input');
  conditionNameInput.type = 'text';
  conditionNameInput.placeholder = 'HP Bar';
  conditionNameRow.appendChild(conditionNameLabel);
  conditionNameRow.appendChild(conditionNameInput);
  conditionsBuilder.appendChild(conditionNameRow);

  const conditionTypeRow = document.createElement('div');
  conditionTypeRow.className = 'row';
  const conditionTypeLabel = document.createElement('label');
  conditionTypeLabel.textContent = 'Type';
  const conditionTypeSelect = document.createElement('select');
  for (const t of ['ProgressBar', 'ImageMatchRoi']) {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    conditionTypeSelect.appendChild(opt);
  }
  conditionTypeRow.appendChild(conditionTypeLabel);
  conditionTypeRow.appendChild(conditionTypeSelect);
  conditionsBuilder.appendChild(conditionTypeRow);

  const conditionRoiRow = document.createElement('div');
  conditionRoiRow.className = 'row';
  const conditionRoiLabel = document.createElement('label');
  conditionRoiLabel.textContent = 'ROI (0..1)';
  const conditionRoiInputs = document.createElement('div');
  conditionRoiInputs.className = 'buttons cctvGeom';
  const roiX = document.createElement('input');
  roiX.type = 'number';
  roiX.step = '0.01';
  roiX.placeholder = 'x';
  const roiY = document.createElement('input');
  roiY.type = 'number';
  roiY.step = '0.01';
  roiY.placeholder = 'y';
  const roiW = document.createElement('input');
  roiW.type = 'number';
  roiW.step = '0.01';
  roiW.placeholder = 'w';
  const roiH = document.createElement('input');
  roiH.type = 'number';
  roiH.step = '0.01';
  roiH.placeholder = 'h';
  conditionRoiInputs.appendChild(roiX);
  conditionRoiInputs.appendChild(roiY);
  conditionRoiInputs.appendChild(roiW);
  conditionRoiInputs.appendChild(roiH);
  conditionRoiRow.appendChild(conditionRoiLabel);
  conditionRoiRow.appendChild(conditionRoiInputs);
  conditionsBuilder.appendChild(conditionRoiRow);

  const conditionTemplateRow = document.createElement('div');
  conditionTemplateRow.className = 'row';
  const conditionTemplateLabel = document.createElement('label');
  conditionTemplateLabel.textContent = 'Template (optional)';
  const conditionTemplateInput = document.createElement('textarea');
  conditionTemplateInput.className = 'monoBox';
  conditionTemplateInput.rows = 3;
  conditionTemplateInput.placeholder = 'Base64 (optional)';
  conditionTemplateRow.appendChild(conditionTemplateLabel);
  conditionTemplateRow.appendChild(conditionTemplateInput);
  conditionsBuilder.appendChild(conditionTemplateRow);

  const conditionLiveRow = document.createElement('div');
  conditionLiveRow.className = 'row';
  const conditionLiveLabel = document.createElement('label');
  const conditionLiveCheckbox = document.createElement('input');
  conditionLiveCheckbox.type = 'checkbox';
  conditionLiveLabel.appendChild(conditionLiveCheckbox);
  conditionLiveLabel.appendChild(document.createTextNode(' Template from live capture'));
  conditionLiveRow.appendChild(conditionLiveLabel);
  conditionsBuilder.appendChild(conditionLiveRow);

  const conditionMoveRow = document.createElement('div');
  conditionMoveRow.className = 'row';
  const conditionMoveLabel = document.createElement('label');
  conditionMoveLabel.textContent = 'Move direction';
  const conditionMoveSelect = document.createElement('select');
  for (const dir of ['up', 'down']) {
    const opt = document.createElement('option');
    opt.value = dir;
    opt.textContent = dir;
    conditionMoveSelect.appendChild(opt);
  }
  conditionMoveRow.appendChild(conditionMoveLabel);
  conditionMoveRow.appendChild(conditionMoveSelect);
  conditionsBuilder.appendChild(conditionMoveRow);

  const conditionBuildRow = document.createElement('div');
  conditionBuildRow.className = 'buttons';
  const conditionBuildBtn = document.createElement('button');
  conditionBuildBtn.type = 'button';
  conditionBuildBtn.textContent = 'Build Payload';
  conditionBuildRow.appendChild(conditionBuildBtn);
  conditionsBuilder.appendChild(conditionBuildRow);

  conditionsBlock.appendChild(conditionsBuilder);

  const conditionsSelectRow = document.createElement('div');
  conditionsSelectRow.className = 'row';
  const conditionsSelectLabel = document.createElement('label');
  conditionsSelectLabel.textContent = 'Existing conditions';
  const conditionsSelectWrap = document.createElement('div');
  conditionsSelectWrap.className = 'buttons';
  const conditionsSelect = document.createElement('select');
  const conditionsLoadBtn = document.createElement('button');
  conditionsLoadBtn.type = 'button';
  conditionsLoadBtn.textContent = 'Load';
  conditionsSelectWrap.appendChild(conditionsSelect);
  conditionsSelectWrap.appendChild(conditionsLoadBtn);
  conditionsSelectRow.appendChild(conditionsSelectLabel);
  conditionsSelectRow.appendChild(conditionsSelectWrap);
  conditionsBlock.appendChild(conditionsSelectRow);

  const conditionsOutRow = document.createElement('div');
  conditionsOutRow.className = 'row';
  const conditionsOutLabel = document.createElement('label');
  conditionsOutLabel.textContent = 'List / Status';
  const conditionsOut = document.createElement('textarea');
  conditionsOut.className = 'monoBox';
  conditionsOut.rows = 4;
  conditionsOut.readOnly = true;
  conditionsOutRow.appendChild(conditionsOutLabel);
  conditionsOutRow.appendChild(conditionsOut);
  conditionsBlock.appendChild(conditionsOutRow);

  const conditionsButtons = document.createElement('div');
  conditionsButtons.className = 'buttons';
  const conditionsFetchBtn = document.createElement('button');
  conditionsFetchBtn.type = 'button';
  conditionsFetchBtn.textContent = 'Fetch';
  let conditionsList = [];
  const loadConditionIntoBuilder = (item) => {
    if (!item) return;
    conditionUuidInput.value = String(item.uuid ?? '');
    conditionNameInput.value = String(item.name ?? '');
    conditionTypeSelect.value = String(item.type ?? 'ProgressBar');
    roiX.value = String(item?.roi?.xNormalized ?? '');
    roiY.value = String(item?.roi?.yNormalized ?? '');
    roiW.value = String(item?.roi?.widthNormalized ?? '');
    roiH.value = String(item?.roi?.heightNormalized ?? '');
    conditionsOp.value = '/conditions/set_from_live';
    const payload = {
      uuid: String(item.uuid ?? ''),
      name: String(item.name ?? ''),
      type: String(item.type ?? ''),
      roi: {
        xNormalized: Number(item?.roi?.xNormalized ?? 0),
        yNormalized: Number(item?.roi?.yNormalized ?? 0),
        widthNormalized: Number(item?.roi?.widthNormalized ?? 0),
        heightNormalized: Number(item?.roi?.heightNormalized ?? 0),
      },
    };
    conditionsPayload.value = JSON.stringify(payload, null, 2);
  };

  conditionsFetchBtn.addEventListener('click', async () => {
    const data = await _clusterGet(cluster, '/conditions', conditionsOut, 'Conditions');
    conditionsList = Array.isArray(data) ? data : [];
    _fillSelect(conditionsSelect, conditionsList, 'uuid', 'name', null);
    if (conditionsList.length > 0) {
      conditionsSelect.value = String(conditionsList[0].uuid ?? '');
      loadConditionIntoBuilder(conditionsList[0]);
    }
  });
  conditionsButtons.appendChild(conditionsFetchBtn);
  const conditionsStatusBtn = document.createElement('button');
  conditionsStatusBtn.type = 'button';
  conditionsStatusBtn.textContent = 'Status';
  conditionsStatusBtn.addEventListener('click', () => _clusterGet(cluster, '/conditions/status', conditionsOut, 'Conditions status'));
  conditionsButtons.appendChild(conditionsStatusBtn);
  conditionsBlock.appendChild(conditionsButtons);

  const conditionsOpRow = document.createElement('div');
  conditionsOpRow.className = 'row';
  const conditionsOpLabel = document.createElement('label');
  conditionsOpLabel.textContent = 'Operation';
  const conditionsOp = document.createElement('select');
  for (const opt of [
    { label: 'Create', value: '/conditions' },
    { label: 'Update (set_from_live)', value: '/conditions/set_from_live' },
    { label: 'Move', value: '/conditions/move' },
    { label: 'Remove', value: '/conditions/remove_uuid' },
  ]) {
    const option = document.createElement('option');
    option.value = opt.value;
    option.textContent = opt.label;
    conditionsOp.appendChild(option);
  }
  conditionsOpRow.appendChild(conditionsOpLabel);
  conditionsOpRow.appendChild(conditionsOp);
  conditionsBlock.appendChild(conditionsOpRow);

  const conditionsPayloadRow = document.createElement('div');
  conditionsPayloadRow.className = 'row';
  const conditionsPayloadLabel = document.createElement('label');
  conditionsPayloadLabel.textContent = 'Payload JSON';
  const conditionsPayload = document.createElement('textarea');
  conditionsPayload.className = 'monoBox';
  conditionsPayload.rows = 4;
  conditionsPayload.placeholder = '{"uuid":null,"name":"HP","type":"ProgressBar","roi":{"xNormalized":0.1,"yNormalized":0.2,"widthNormalized":0.3,"heightNormalized":0.05}}';
  conditionsPayloadRow.appendChild(conditionsPayloadLabel);
  conditionsPayloadRow.appendChild(conditionsPayload);
  conditionsBlock.appendChild(conditionsPayloadRow);

  const conditionsSendRow = document.createElement('div');
  conditionsSendRow.className = 'buttons';
  const conditionsSendBtn = document.createElement('button');
  conditionsSendBtn.type = 'button';
  conditionsSendBtn.textContent = 'Send';
  conditionsSendBtn.addEventListener('click', () => {
    let payload = null;
    try {
      payload = _tryParseJson(conditionsPayload.value);
    } catch (err) {
      _setManageStatus(`Invalid conditions JSON: ${err?.message ?? err}`);
      return;
    }
    if (!payload) return _setManageStatus('Conditions payload is required.');
    _clusterPost(cluster, conditionsOp.value, payload, conditionsOut, 'Conditions');
  });
  conditionsSendRow.appendChild(conditionsSendBtn);
  conditionsBlock.appendChild(conditionsSendRow);

  conditionsLoadBtn.addEventListener('click', () => {
    const selected = String(conditionsSelect.value || '').trim();
    const item = conditionsList.find(c => String(c?.uuid ?? '') === selected);
    if (!item) return _setManageStatus('Select a condition to load.');
    loadConditionIntoBuilder(item);
    _setManageStatus(`Condition loaded for ${_clusterLabel(cluster)}.`);
  });

  conditionBuildBtn.addEventListener('click', () => {
    const op = conditionsOp.value;
    const uuid = String(conditionUuidInput.value || '').trim();
    const name = String(conditionNameInput.value || '').trim();
    const type = String(conditionTypeSelect.value || '').trim();
    const roi = {
      xNormalized: Math.max(0, Math.min(1, _floatFromInput(roiX, 0))),
      yNormalized: Math.max(0, Math.min(1, _floatFromInput(roiY, 0))),
      widthNormalized: Math.max(0, Math.min(1, _floatFromInput(roiW, 0.1))),
      heightNormalized: Math.max(0, Math.min(1, _floatFromInput(roiH, 0.1))),
    };
    const templateImageBase64 = String(conditionTemplateInput.value || '').trim();
    const templateFromLive = Boolean(conditionLiveCheckbox.checked);
    let payload = null;

    if (op === '/conditions') {
      if (!name) return _setManageStatus('Condition name is required.');
      payload = { name, type, roi };
      if (templateImageBase64) payload.templateImageBase64 = templateImageBase64;
      if (templateFromLive) payload.templateFromLive = true;
    } else if (op === '/conditions/set_from_live') {
      if (!uuid) return _setManageStatus('Condition UUID is required.');
      payload = { uuid, roi };
      if (name) payload.name = name;
      if (type) payload.type = type;
      if (templateImageBase64) payload.templateImageBase64 = templateImageBase64;
      if (templateFromLive) payload.templateFromLive = true;
    } else if (op === '/conditions/move') {
      if (!uuid) return _setManageStatus('Condition UUID is required.');
      payload = { uuid, direction: conditionMoveSelect.value };
    } else if (op === '/conditions/remove_uuid') {
      if (!uuid) return _setManageStatus('Condition UUID is required.');
      payload = { uuid };
    }

    if (!payload) return;
    conditionsPayload.value = JSON.stringify(payload, null, 2);
    _setManageStatus(`Condition payload built for ${_clusterLabel(cluster)}.`);
  });

  const triggersBlock = document.createElement('div');
  triggersBlock.className = 'cctvManageBlock';
  const triggersTitle = document.createElement('div');
  triggersTitle.className = 'cctvManageTitle';
  triggersTitle.textContent = 'Triggers';
  triggersBlock.appendChild(triggersTitle);

  const triggersBuilder = document.createElement('div');
  triggersBuilder.className = 'cctvManageForm';

  const triggerUuidRow = document.createElement('div');
  triggerUuidRow.className = 'row';
  const triggerUuidLabel = document.createElement('label');
  triggerUuidLabel.textContent = 'Trigger UUID (optional)';
  const triggerUuidInput = document.createElement('input');
  triggerUuidInput.type = 'text';
  triggerUuidRow.appendChild(triggerUuidLabel);
  triggerUuidRow.appendChild(triggerUuidInput);
  triggersBuilder.appendChild(triggerUuidRow);

  const triggerNameRow = document.createElement('div');
  triggerNameRow.className = 'row';
  const triggerNameLabel = document.createElement('label');
  triggerNameLabel.textContent = 'Trigger name';
  const triggerNameInput = document.createElement('input');
  triggerNameInput.type = 'text';
  triggerNameInput.placeholder = 'Auto Heal';
  triggerNameRow.appendChild(triggerNameLabel);
  triggerNameRow.appendChild(triggerNameInput);
  triggersBuilder.appendChild(triggerNameRow);

  const triggerActionRow = document.createElement('div');
  triggerActionRow.className = 'row';
  const triggerActionLabel = document.createElement('label');
  triggerActionLabel.textContent = 'Action UUID';
  const triggerActionInput = document.createElement('input');
  triggerActionInput.type = 'text';
  triggerActionRow.appendChild(triggerActionLabel);
  triggerActionRow.appendChild(triggerActionInput);
  triggersBuilder.appendChild(triggerActionRow);

  const triggerFlagsRow = document.createElement('div');
  triggerFlagsRow.className = 'row';
  const triggerFlagsLabel = document.createElement('label');
  triggerFlagsLabel.textContent = 'Options';
  const triggerFlagsWrap = document.createElement('div');
  triggerFlagsWrap.className = 'buttons';
  const triggerEnabled = document.createElement('input');
  triggerEnabled.type = 'checkbox';
  const triggerEnabledLabel = document.createElement('label');
  triggerEnabledLabel.appendChild(triggerEnabled);
  triggerEnabledLabel.appendChild(document.createTextNode(' Enabled'));
  const retriggerInput = document.createElement('input');
  retriggerInput.type = 'number';
  retriggerInput.step = '100';
  retriggerInput.placeholder = 'retrigger ms';
  const criteriaModeSelect = document.createElement('select');
  for (const mode of ['All', 'Any']) {
    const opt = document.createElement('option');
    opt.value = mode;
    opt.textContent = `Criteria: ${mode}`;
    criteriaModeSelect.appendChild(opt);
  }
  triggerFlagsWrap.appendChild(triggerEnabledLabel);
  triggerFlagsWrap.appendChild(retriggerInput);
  triggerFlagsWrap.appendChild(criteriaModeSelect);
  triggerFlagsRow.appendChild(triggerFlagsLabel);
  triggerFlagsRow.appendChild(triggerFlagsWrap);
  triggersBuilder.appendChild(triggerFlagsRow);

  const criteriaRow = document.createElement('div');
  criteriaRow.className = 'row';
  const criteriaLabel = document.createElement('label');
  criteriaLabel.textContent = 'Criteria';
  const criteriaInputs = document.createElement('div');
  criteriaInputs.className = 'buttons';
  const criteriaConditionUuid = document.createElement('input');
  criteriaConditionUuid.type = 'text';
  criteriaConditionUuid.placeholder = 'condition uuid';
  const criteriaComparator = document.createElement('select');
  for (const cmp of ['Equals', 'NotEquals', 'GreaterThan', 'LessThan', 'GreaterThanOrEqual', 'LessThanOrEqual']) {
    const opt = document.createElement('option');
    opt.value = cmp;
    opt.textContent = cmp;
    criteriaComparator.appendChild(opt);
  }
  const criteriaExpected = document.createElement('input');
  criteriaExpected.type = 'number';
  criteriaExpected.step = '0.01';
  criteriaExpected.placeholder = 'expected';
  criteriaInputs.appendChild(criteriaConditionUuid);
  criteriaInputs.appendChild(criteriaComparator);
  criteriaInputs.appendChild(criteriaExpected);
  criteriaRow.appendChild(criteriaLabel);
  criteriaRow.appendChild(criteriaInputs);
  triggersBuilder.appendChild(criteriaRow);

  const criteriaPreviewRow = document.createElement('div');
  criteriaPreviewRow.className = 'row';
  const criteriaPreviewLabel = document.createElement('label');
  criteriaPreviewLabel.textContent = 'Criteria preview';
  const criteriaPreview = document.createElement('textarea');
  criteriaPreview.className = 'monoBox';
  criteriaPreview.rows = 3;
  criteriaPreview.readOnly = true;
  criteriaPreviewRow.appendChild(criteriaPreviewLabel);
  criteriaPreviewRow.appendChild(criteriaPreview);
  triggersBuilder.appendChild(criteriaPreviewRow);

  const criteriaButtons = document.createElement('div');
  criteriaButtons.className = 'buttons';
  const criteriaAddBtn = document.createElement('button');
  criteriaAddBtn.type = 'button';
  criteriaAddBtn.textContent = 'Add Criteria';
  const criteriaClearBtn = document.createElement('button');
  criteriaClearBtn.type = 'button';
  criteriaClearBtn.textContent = 'Clear Criteria';
  const triggerBuildBtn = document.createElement('button');
  triggerBuildBtn.type = 'button';
  triggerBuildBtn.textContent = 'Build Payload';
  criteriaButtons.appendChild(criteriaAddBtn);
  criteriaButtons.appendChild(criteriaClearBtn);
  criteriaButtons.appendChild(triggerBuildBtn);
  triggersBuilder.appendChild(criteriaButtons);

  triggersBlock.appendChild(triggersBuilder);

  const triggersSelectRow = document.createElement('div');
  triggersSelectRow.className = 'row';
  const triggersSelectLabel = document.createElement('label');
  triggersSelectLabel.textContent = 'Existing triggers';
  const triggersSelectWrap = document.createElement('div');
  triggersSelectWrap.className = 'buttons';
  const triggersSelect = document.createElement('select');
  const triggersLoadBtn = document.createElement('button');
  triggersLoadBtn.type = 'button';
  triggersLoadBtn.textContent = 'Load';
  triggersSelectWrap.appendChild(triggersSelect);
  triggersSelectWrap.appendChild(triggersLoadBtn);
  triggersSelectRow.appendChild(triggersSelectLabel);
  triggersSelectRow.appendChild(triggersSelectWrap);
  triggersBlock.appendChild(triggersSelectRow);

  const triggersOutRow = document.createElement('div');
  triggersOutRow.className = 'row';
  const triggersOutLabel = document.createElement('label');
  triggersOutLabel.textContent = 'List / Status';
  const triggersOut = document.createElement('textarea');
  triggersOut.className = 'monoBox';
  triggersOut.rows = 4;
  triggersOut.readOnly = true;
  triggersOutRow.appendChild(triggersOutLabel);
  triggersOutRow.appendChild(triggersOut);
  triggersBlock.appendChild(triggersOutRow);

  const triggersButtons = document.createElement('div');
  triggersButtons.className = 'buttons';
  const triggersFetchBtn = document.createElement('button');
  triggersFetchBtn.type = 'button';
  triggersFetchBtn.textContent = 'Fetch';
  let triggersList = [];
  const loadTriggerIntoBuilder = (item) => {
    if (!item) return;
    triggerUuidInput.value = String(item.uuid ?? '');
    triggerNameInput.value = String(item.name ?? '');
    triggerActionInput.value = String(item.action ?? '');
    triggerEnabled.checked = Boolean(item.enabled);
    retriggerInput.value = String(item.retriggerMs ?? '');
    criteriaModeSelect.value = String(item.criteriaMode ?? 'All');
    triggerCriteria.length = 0;
    const list = Array.isArray(item.triggerCiterias) ? item.triggerCiterias : [];
    for (const c of list) {
      triggerCriteria.push({
        conditionUuid: String(c?.conditionUuid ?? ''),
        comparator: String(c?.comparator ?? 'Equals'),
        expectedValue: Number(c?.expectedValue ?? c?.expected ?? 0),
      });
    }
    updateCriteriaPreview();
    triggersOp.value = '/triggers/upsert';
    const payload = {
      uuid: String(item.uuid ?? ''),
      name: String(item.name ?? ''),
      enabled: Boolean(item.enabled),
      retriggerMs: Number(item.retriggerMs ?? 0),
      criteriaMode: String(item.criteriaMode ?? 'All'),
      triggerCiterias: triggerCriteria.slice(),
      action: String(item.action ?? ''),
    };
    triggersPayload.value = JSON.stringify(payload, null, 2);
  };

  triggersFetchBtn.addEventListener('click', async () => {
    const data = await _clusterGet(cluster, '/triggers', triggersOut, 'Triggers');
    triggersList = Array.isArray(data) ? data : [];
    _fillSelect(triggersSelect, triggersList, 'uuid', 'name', null);
    if (triggersList.length > 0) {
      triggersSelect.value = String(triggersList[0].uuid ?? '');
      loadTriggerIntoBuilder(triggersList[0]);
    }
  });
  triggersButtons.appendChild(triggersFetchBtn);
  const triggersStatusBtn = document.createElement('button');
  triggersStatusBtn.type = 'button';
  triggersStatusBtn.textContent = 'Status';
  triggersStatusBtn.addEventListener('click', () => _clusterGet(cluster, '/triggers/status', triggersOut, 'Triggers status'));
  triggersButtons.appendChild(triggersStatusBtn);
  triggersBlock.appendChild(triggersButtons);

  const triggersOpRow = document.createElement('div');
  triggersOpRow.className = 'row';
  const triggersOpLabel = document.createElement('label');
  triggersOpLabel.textContent = 'Operation';
  const triggersOp = document.createElement('select');
  for (const opt of [
    { label: 'Upsert', value: '/triggers/upsert' },
    { label: 'Remove', value: '/triggers/remove_uuid' },
    { label: 'Set Enabled', value: '/triggers/set_enabled' },
  ]) {
    const option = document.createElement('option');
    option.value = opt.value;
    option.textContent = opt.label;
    triggersOp.appendChild(option);
  }
  triggersOpRow.appendChild(triggersOpLabel);
  triggersOpRow.appendChild(triggersOp);
  triggersBlock.appendChild(triggersOpRow);

  const triggersPayloadRow = document.createElement('div');
  triggersPayloadRow.className = 'row';
  const triggersPayloadLabel = document.createElement('label');
  triggersPayloadLabel.textContent = 'Payload JSON';
  const triggersPayload = document.createElement('textarea');
  triggersPayload.className = 'monoBox';
  triggersPayload.rows = 4;
  triggersPayload.placeholder = '{"uuid":null,"name":"Auto Heal","enabled":true,"retriggerMs":2000,"triggerCiterias":[],"action":"00000000-0000-0000-0000-000000000000"}';
  triggersPayloadRow.appendChild(triggersPayloadLabel);
  triggersPayloadRow.appendChild(triggersPayload);
  triggersBlock.appendChild(triggersPayloadRow);

  const triggersSendRow = document.createElement('div');
  triggersSendRow.className = 'buttons';
  const triggersSendBtn = document.createElement('button');
  triggersSendBtn.type = 'button';
  triggersSendBtn.textContent = 'Send';
  triggersSendBtn.addEventListener('click', () => {
    let payload = null;
    try {
      payload = _tryParseJson(triggersPayload.value);
    } catch (err) {
      _setManageStatus(`Invalid triggers JSON: ${err?.message ?? err}`);
      return;
    }
    if (!payload) return _setManageStatus('Triggers payload is required.');
    _clusterPost(cluster, triggersOp.value, payload, triggersOut, 'Triggers');
  });
  triggersSendRow.appendChild(triggersSendBtn);
  triggersBlock.appendChild(triggersSendRow);

  const triggerCriteria = [];
  const updateCriteriaPreview = () => {
    const lines = triggerCriteria.map((c, idx) => `${idx + 1}. ${c.conditionUuid} ${c.comparator} ${c.expectedValue}`);
    _setPreviewLines(criteriaPreview, lines);
  };

  criteriaAddBtn.addEventListener('click', () => {
    const conditionUuid = String(criteriaConditionUuid.value || '').trim();
    if (!conditionUuid) return _setManageStatus('Condition UUID is required.');
    const comparator = criteriaComparator.value;
    const expectedValue = _floatFromInput(criteriaExpected, 0);
    triggerCriteria.push({ conditionUuid, comparator, expectedValue });
    updateCriteriaPreview();
  });

  criteriaClearBtn.addEventListener('click', () => {
    triggerCriteria.length = 0;
    updateCriteriaPreview();
  });

  triggerBuildBtn.addEventListener('click', () => {
    const op = triggersOp.value;
    const uuid = String(triggerUuidInput.value || '').trim();
    const name = String(triggerNameInput.value || '').trim();
    const actionUuid = String(triggerActionInput.value || '').trim();
    const enabled = Boolean(triggerEnabled.checked);
    const retriggerMs = Math.floor(_floatFromInput(retriggerInput, 0));
    const criteriaMode = criteriaModeSelect.value || 'All';
    let payload = null;

    if (op === '/triggers/upsert') {
      if (!name) return _setManageStatus('Trigger name is required.');
      if (!actionUuid) return _setManageStatus('Action UUID is required.');
      payload = {
        uuid: uuid || null,
        name,
        enabled,
        retriggerMs,
        criteriaMode,
        triggerCiterias: triggerCriteria.slice(),
        action: actionUuid,
      };
    } else if (op === '/triggers/remove_uuid') {
      if (!uuid) return _setManageStatus('Trigger UUID is required.');
      payload = { uuid };
    } else if (op === '/triggers/set_enabled') {
      if (!uuid) return _setManageStatus('Trigger UUID is required.');
      payload = { uuid, enabled };
    }

    if (!payload) return;
    triggersPayload.value = JSON.stringify(payload, null, 2);
    _setManageStatus(`Trigger payload built for ${_clusterLabel(cluster)}.`);
  });

  triggersLoadBtn.addEventListener('click', () => {
    const selected = String(triggersSelect.value || '').trim();
    const item = triggersList.find(t => String(t?.uuid ?? '') === selected);
    if (!item) return _setManageStatus('Select a trigger to load.');
    loadTriggerIntoBuilder(item);
    _setManageStatus(`Trigger loaded for ${_clusterLabel(cluster)}.`);
  });

  const manageControls = [
    actionNameInput,
    actionUuidInput,
    actionPresetSelect,
    actionPresetBtn,
    actionStepType,
    clickXInput,
    clickYInput,
    keyInput,
    delayInput,
    addStepBtn,
    clearStepsBtn,
    buildActionBtn,
    actionPayload,
    actionsFetchBtn,
    actionsSelect,
    actionsLoadBtn,
    actionsRunBtn,
    actionsRemoveBtn,
    actionsUpsertBtn,
    conditionUuidInput,
    conditionNameInput,
    conditionTypeSelect,
    roiX,
    roiY,
    roiW,
    roiH,
    conditionTemplateInput,
    conditionLiveCheckbox,
    conditionMoveSelect,
    conditionBuildBtn,
    conditionsSelect,
    conditionsLoadBtn,
    conditionsFetchBtn,
    conditionsStatusBtn,
    conditionsOp,
    conditionsPayload,
    conditionsSendBtn,
    triggerUuidInput,
    triggerNameInput,
    triggerActionInput,
    triggerEnabled,
    retriggerInput,
    criteriaModeSelect,
    criteriaConditionUuid,
    criteriaComparator,
    criteriaExpected,
    criteriaAddBtn,
    criteriaClearBtn,
    triggerBuildBtn,
    triggersSelect,
    triggersLoadBtn,
    triggersFetchBtn,
    triggersStatusBtn,
    triggersOp,
    triggersPayload,
    triggersSendBtn,
  ];
  for (const el of manageControls) {
    if (!el) continue;
    el.disabled = !canProxy;
  }

  manageBody.appendChild(actionsBlock);
  manageBody.appendChild(conditionsBlock);
  manageBody.appendChild(triggersBlock);

  return manage;
}
