let _roiDrag = null;
let _lastRoi = null;
let _activeRoiHandle = null;
let _liveZoom = 1.0;
let _livePan = { x: 0, y: 0 };
let _panMode = false;
let _panDrag = null;

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
    ctx.lineWidth = 1;
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

    if (w < 0.005 && h < 0.005) {
        clickXEl.value = startPt.x.toFixed(3);
        clickYEl.value = startPt.y.toFixed(3);
        _lastLiveSelectedPoint = { x: Number(startPt.x), y: Number(startPt.y) };
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

function applyLiveViewTransform() {
    if (!livePreviewFrameEl || !livePreviewViewportEl) return;
    const rect = livePreviewFrameEl.getBoundingClientRect();
    const frameW = rect.width;
    const frameH = rect.height;
    if (!(frameW > 0 && frameH > 0)) return;
    const scale = _liveZoom;
    const viewportW = frameW * scale;
    const viewportH = frameH * scale;

    const baseLeft = (frameW - viewportW) / 2;
    const baseTop = (frameH - viewportH) / 2;
    let left = baseLeft + _livePan.x;
    let top = baseTop + _livePan.y;
    const minLeft = frameW - viewportW;
    const minTop = frameH - viewportH;

    left = clamp(left, minLeft, 0);
    top = clamp(top, minTop, 0);

    _livePan.x = left - baseLeft;
    _livePan.y = top - baseTop;
    livePreviewViewportEl.style.width = `${scale * 100}%`;
    livePreviewViewportEl.style.height = `${scale * 100}%`;
    livePreviewViewportEl.style.left = `${left}px`;
    livePreviewViewportEl.style.top = `${top}px`;
    ensureOverlayCanvasSize();
    if (_lastRoi) drawOverlayRoi(_lastRoi);
}

function setPanMode(enabled) {
    _panMode = !!enabled;
    if (livePreviewFrameEl) {
        livePreviewFrameEl.classList.toggle('panMode', _panMode);
        livePreviewFrameEl.classList.remove('panning');
    }
    if (btnPanToggle) btnPanToggle.classList.toggle('primary', _panMode);
    _panDrag = null;
}

function zoomBy(factor) {
    const prev = _liveZoom;
    const next = clamp(prev * factor, 1.0, 8.0);
    if (next === prev) return;

    const ratio = next / prev;
    _livePan.x *= ratio;
    _livePan.y *= ratio;
    _liveZoom = next;
    applyLiveViewTransform();
}

const roiEventTarget = roiOverlay || captureImage;
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
    if (_roiDrag) endDrag(ev);
});

captureImage.addEventListener('load', () => {
    applyLiveViewTransform();
    ensureOverlayCanvasSize();
    if (_lastRoi) drawOverlayRoi(_lastRoi);
});

window.addEventListener('resize', () => {
    applyLiveViewTransform();
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