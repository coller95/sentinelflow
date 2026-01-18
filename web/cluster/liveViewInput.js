const roiEventTarget = roiOverlay || captureImage;
if (roiEventTarget) {
roiEventTarget.addEventListener('mousedown', (ev) => {
    if (ev.button !== 0) return;
    try {
        if (_actionClickCaptureArmed) {
            const pt = getNormalizedPointFromMouseEvent(ev);
            _actionClickCaptureArmed = false;
            const i = _selectedActionStepIndex;
            if (!Array.isArray(_actionSteps) || i < 0 || i >= _actionSteps.length) {
                setStatus('Captured click (no step selected).', 'ok');
            } else {
                const step = _actionSteps[i];
                if (_actionKindOf(step) !== 'Click') {
                    setStatus('Captured click (select a Click step).', 'ok');
                } else {
                    step.parameters = step.parameters && typeof step.parameters === 'object' ? step.parameters : {};
                    step.parameters.x = Number(pt.x);
                    step.parameters.y = Number(pt.y);
                    _syncHiddenActionStepsTextarea();
                    _renderActionStepList();
                    setStatus(`Captured click: (${pt.x.toFixed(6)}, ${pt.y.toFixed(6)})`, 'ok');
                }
            }
            ev.preventDefault();
            ev.stopPropagation();
            return;
        }

        if (_liveOverlayMode === LIVE_OVERLAY_MODES.CLICK) {
            const pt = getNormalizedPointFromMouseEvent(ev);
            setClickInputsFromPoint(pt);
            if (isInstantClickEnabled()) {
                sendInstantClick(pt);
            }
            ev.preventDefault();
            return;
        }

        if (_liveOverlayMode !== LIVE_OVERLAY_MODES.ROI) return;

        if (_panMode) {
            _panDrag = {
                sx: ev.clientX,
                sy: ev.clientY,
                startPanX: _livePan.x,
                startPanY: _livePan.y,
            };
            if (livePreviewFrameEl) livePreviewFrameEl.classList.add('panning');
            ev.preventDefault();
            return;
        }

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
    if (_liveOverlayMode !== LIVE_OVERLAY_MODES.ROI) return;
    if (_panDrag) {
        const dx = ev.clientX - _panDrag.sx;
        const dy = ev.clientY - _panDrag.sy;
        _livePan.x = _panDrag.startPanX + dx;
        _livePan.y = _panDrag.startPanY + dy;
        applyLiveViewTransform();
        ev.preventDefault();
        return;
    }
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
    if (_panDrag) {
        _panDrag = null;
        if (livePreviewFrameEl) livePreviewFrameEl.classList.remove('panning');
        return;
    }
    if (!_roiDrag || _liveOverlayMode !== LIVE_OVERLAY_MODES.ROI) return;
    try {
        const pt = getNormalizedPointFromMouseEvent(ev);
        finalizeRoi(_roiDrag.start, pt);
    } catch (e) {
        setStatus(`ROI select failed: ${e.message}`, 'err');
    } finally {
        _roiDrag = null;
    }
}

roiEventTarget.addEventListener('mouseup', endDrag);
roiEventTarget.addEventListener('mouseleave', (ev) => {
    if (_roiDrag) endDrag(ev);
});
}

captureImage.addEventListener('load', () => {
    applyLiveViewTransform();
    renderLiveOverlay();
});

window.addEventListener('resize', () => {
    applyLiveViewTransform();
    renderLiveOverlay();
});

document.addEventListener('keydown', (ev) => {
    if (_liveOverlayMode !== LIVE_OVERLAY_MODES.ROI || !_lastRoi || !_activeRoiHandle) return;
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

if (btnPanToggle) {
    btnPanToggle.addEventListener('click', () => {
        setPanMode(!_panMode);
    });
}

if (btnZoomIn) {
    btnZoomIn.addEventListener('click', () => {
        zoomBy(1.25);
    });
}

if (btnZoomOut) {
    btnZoomOut.addEventListener('click', () => {
        zoomBy(1 / 1.25);
    });
}

if (inputInstantClickEl) {
    inputInstantClickEl.addEventListener('change', () => {
        if (_liveOverlayMode === LIVE_OVERLAY_MODES.CLICK) {
            renderLiveOverlay();
        }
    });
}
