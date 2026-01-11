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

function safeJsonStringify(value) {
    try {
        return JSON.stringify(value, null, 2);
    } catch {
        return '';
    }
}

function parseActionStepsFromEditor() {
    const raw = (actionStepsEl && actionStepsEl.value ? String(actionStepsEl.value) : '').trim();
    if (!raw) return [];
    let parsed;
    try {
        parsed = JSON.parse(raw);
    } catch {
        throw new Error('Steps must be valid JSON');
    }

    if (!Array.isArray(parsed)) {
        throw new Error('Steps JSON must be an array');
    }

    for (const s of parsed) {
        if (!s || typeof s !== 'object') throw new Error('Each step must be an object');
        if (!('action' in s)) throw new Error('Each step must have an action');
        if (!('parameters' in s)) s.parameters = {};
    }
    return parsed;
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

function _fmtUnixSeconds(ts) {
    if (ts === null || ts === undefined) return '';
    const n = Number(ts);
    if (!Number.isFinite(n) || n <= 0) return '';
    try {
        return new Date(n * 1000).toLocaleString();
    } catch {
        return String(n);
    }
}

function _fmtAgoSeconds(ts) {
    if (ts === null || ts === undefined) return '';
    const n = Number(ts);
    if (!Number.isFinite(n) || n <= 0) return '';
    const now = Date.now() / 1000;
    const dt = now - n;
    if (!Number.isFinite(dt)) return '';
    if (dt < 0) return 'in future';
    if (dt < 1) return 'just now';
    if (dt < 60) return `${dt.toFixed(1)}s ago`;
    if (dt < 3600) return `${(dt / 60).toFixed(1)}m ago`;
    return `${(dt / 3600).toFixed(1)}h ago`;
}

function clamp01(v) {
    if (v < 0) return 0;
    if (v > 1) return 1;
    return v;
}

function clamp(v, lo, hi) {
    return Math.min(hi, Math.max(lo, v));
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

function normalizeKeyNameFromEvent(ev) {
    const key = String(ev.key || '');
    const code = String(ev.code || '');

    if (key.length === 1) {
        const ch = key;
        return /^[a-z]$/i.test(ch) ? ch.toUpperCase() : ch;
    }

    if (/^F\d{1,2}$/i.test(key)) return key.toUpperCase();
    if (/^F\d{1,2}$/i.test(code)) return code.toUpperCase();

    const map = {
        Enter: 'Enter',
        Escape: 'Esc',
        Tab: 'Tab',
        ' ': 'Space',
        Spacebar: 'Space',
        Backspace: 'Backspace',
        Delete: 'Delete',
        Insert: 'Insert',
        Home: 'Home',
        End: 'End',
        PageUp: 'PageUp',
        PageDown: 'PageDown',
        ArrowLeft: 'ArrowLeft',
        ArrowRight: 'ArrowRight',
        ArrowUp: 'ArrowUp',
        ArrowDown: 'ArrowDown',
        Shift: ev.location === 2 ? 'RShift' : 'LShift',
        Control: ev.location === 2 ? 'RCtrl' : 'LCtrl',
        Alt: ev.location === 2 ? 'RAlt' : 'LAlt',
    };
    if (map[key]) return map[key];

    return key;
}

function _actionKindOf(step) {
    const raw = step && typeof step === 'object' ? String(step.action ?? '') : '';
    if (!raw) return '';
    if (raw === 'Keyboard') return 'KeyStroke';
    return raw;
}

function _formatStepLabel(step) {
    const kind = _actionKindOf(step);
    const p = step && typeof step === 'object' ? (step.parameters ?? {}) : {};
    if (kind === 'Click') {
        const x = Number(p.x ?? p.xNormalized ?? 0);
        const y = Number(p.y ?? p.yNormalized ?? 0);
        const fx = Number.isFinite(x) ? x : 0;
        const fy = Number.isFinite(y) ? y : 0;
        return `Click at (${fx.toFixed(6)}, ${fy.toFixed(6)})`;
    }
    if (kind === 'KeyStroke') {
        const k = String(p.keyName ?? p.key ?? '').trim();
        const kk = k || '?';
        return `Press "${kk}"`;
    }
    if (kind === 'Delay') {
        let ms = Number(p.ms);
        if (!Number.isFinite(ms)) {
            const seconds = Number(p.seconds);
            ms = Number.isFinite(seconds) ? (seconds * 1000.0) : 0;
        }
        const mm = Math.max(0, Math.round(Number.isFinite(ms) ? ms : 0));
        return `Delay ${mm}ms`;
    }
    return String(kind || 'Step');
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

function coerceConditionStatusItems(payload) {
    if (Array.isArray(payload)) return payload;
    if (!payload || typeof payload !== 'object') return [];
    const byUuid = (payload.byUuid && typeof payload.byUuid === 'object') ? payload.byUuid : null;
    if (!byUuid) return [];
    const order = Array.isArray(payload.order) ? payload.order.map(String) : Object.keys(byUuid);
    const out = [];
    for (const uuid of order) {
        const it = byUuid[uuid];
        if (!it) continue;
        out.push({ uuid: String(uuid), ...(typeof it === 'object' ? it : {}) });
    }
    return out;
}

// --- Exports or make available globally if needed ---
// e.g., if other modules need these:
// window.setBusy = setBusy;
// window.setStatus = setStatus;
// etc.