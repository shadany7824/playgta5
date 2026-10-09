/* Run Inspector viewer (tools/inspector.py builds the data it reads).
 *
 * Data: manifest.json (scenes, views) and data/<scene>/<view>/manifest.json (columns, files, ROIs, metrics rows).
 * *.f16 = float16 little-endian, row-major, row 0 = top, `channels` values per pixel; *.u8 = one byte per pixel.
 * Display: value x exposure, clipped to [0, 1], sRGB-encoded (no tonemapping). Signed error of a component:
 * (Y - Y_ref) / (|Y_ref| + eps), eps = 0.01 |mean of Y_ref over ROI all| (tools/sheets.py relative_error), shown on a
 * blue (too dark) / white / red (too bright) scale. Non-finite values are magenta. No external resources.
 */
(function () {
  'use strict';

  // ------------------------------------------------------------------------------------------ pure helpers

  const LUMA = [0.2126, 0.7152, 0.0722];
  const NONFINITE = [255, 0, 255];
  const MASKED = [64, 64, 64];
  const MISSING = [48, 48, 48];
  // Diverging anchors (tools/png.py DIVERGING_ANCHORS): position in [-1, 1], then RGB.
  const ANCHORS = [[-1.0, 5, 48, 97], [-0.5, 67, 147, 195], [0.0, 247, 247, 247], [0.5, 214, 96, 77],
                   [1.0, 103, 0, 31]];
  const ROI_COLORS = ['#ffd400', '#00e5ff', '#ff4fd8', '#7dff4f', '#ff8a00', '#b18cff', '#ffffff', '#ff5050'];
  const LITTLE_ENDIAN = new Uint8Array(new Uint16Array([1]).buffer)[0] === 1;

  function halfToFloat(h) {
    const s = (h & 0x8000) ? -1 : 1;
    const e = (h >> 10) & 0x1f;
    const f = h & 0x3ff;
    if (e === 0) return s * f * Math.pow(2, -24);
    if (e === 31) return f ? NaN : s * Infinity;
    return s * (1 + f / 1024) * Math.pow(2, e - 15);
  }

  let HALF = null;
  function halfTable() {
    if (!HALF) {
      HALF = new Float32Array(65536);
      for (let i = 0; i < 65536; i++) HALF[i] = halfToFloat(i);
    }
    return HALF;
  }

  /** ArrayBuffer of float16 LE values -> Float32Array. */
  function decodeF16(buffer) {
    const t = halfTable();
    const n = buffer.byteLength >> 1;
    const out = new Float32Array(n);
    if (LITTLE_ENDIAN) {
      const u = new Uint16Array(buffer, 0, n);
      for (let i = 0; i < n; i++) out[i] = t[u[i]];
    } else {
      const dv = new DataView(buffer);
      for (let i = 0; i < n; i++) out[i] = t[dv.getUint16(2 * i, true)];
    }
    return out;
  }

  function luminance(r, g, b) { return LUMA[0] * r + LUMA[1] * g + LUMA[2] * b; }

  const SRGB_N = 16384;
  let SRGB = null;
  function srgbTable() {
    if (!SRGB) {
      SRGB = new Uint8ClampedArray(SRGB_N + 1);
      for (let i = 0; i <= SRGB_N; i++) {
        const x = i / SRGB_N;
        const e = x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
        SRGB[i] = Math.round(e * 255);
      }
    }
    return SRGB;
  }

  /** Linear value (already exposed) -> 8-bit sRGB. */
  function srgb8(v) {
    if (!(v > 0)) return 0;
    if (v >= 1) return 255;
    return srgbTable()[(v * SRGB_N + 0.5) | 0];
  }

  /** t in [-1, 1] (clamped; NaN -> null) -> [r, g, b] of the diverging scale. */
  function diverging(t) {
    if (t !== t) return null;
    if (t < -1) t = -1; else if (t > 1) t = 1;
    for (let i = 1; i < ANCHORS.length; i++) {
      if (t <= ANCHORS[i][0]) {
        const a = ANCHORS[i - 1], b = ANCHORS[i];
        const f = (t - a[0]) / (b[0] - a[0]);
        return [Math.round(a[1] + f * (b[1] - a[1])), Math.round(a[2] + f * (b[2] - a[2])),
                Math.round(a[3] + f * (b[3] - a[3]))];
      }
    }
    return ANCHORS[ANCHORS.length - 1].slice(1);
  }

  function relError(yc, yr, eps) { return (yc - yr) / (Math.abs(yr) + eps); }

  function finite(x) { return typeof x === 'number' && isFinite(x); }

  /** 3 significant digits, as tools/report.py fmt_sig: 0.0990, 1.00, 12.3, 1230, 1.23e-5. */
  function fmtSig(x, digits) {
    digits = digits || 3;
    if (!finite(x)) return '–';
    if (x === 0) return '0';
    const a = Math.abs(x);
    if (a < 1e-3 || a >= 1e7) return x.toExponential(digits - 1);
    if (a >= Math.pow(10, digits)) {  // no exponent: round to the significant digits instead
      const step = Math.pow(10, Math.floor(Math.log10(a)) - digits + 1);
      return String(Math.round(x / step) * step);
    }
    return x.toPrecision(digits);
  }

  /** Fraction as a percentage, signed by default: +10.0%, -0.123%. */
  function fmtPct(x, signed) {
    if (!finite(x)) return '–';
    if (x === 0) return '0%';
    const s = fmtSig(x * 100);
    return ((signed !== false && x > 0) ? '+' + s : s) + '%';
  }

  /** Indices of mask pixels with a 4-neighbour outside the mask (the image border is not an edge). */
  function outline(mask, w, h) {
    const out = [];
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = y * w + x;
        if (!mask[i]) continue;
        if ((x > 0 && !mask[i - 1]) || (x < w - 1 && !mask[i + 1]) ||
            (y > 0 && !mask[i - w]) || (y < h - 1 && !mask[i + w])) out.push(i);
      }
    }
    return out;
  }

  function put(px, i, c) { px[4 * i] = c[0]; px[4 * i + 1] = c[1]; px[4 * i + 2] = c[2]; px[4 * i + 3] = 255; }

  /** Linear image (n*channels floats) -> RGBA bytes at the given exposure; non-finite pixels magenta. */
  function renderLinear(data, channels, w, h, exposure) {
    const n = w * h;
    const px = new Uint8ClampedArray(4 * n);
    for (let i = 0; i < n; i++) {
      const o = i * channels;
      const r = data[o], g = channels >= 3 ? data[o + 1] : r, b = channels >= 3 ? data[o + 2] : r;
      if (!(isFinite(r) && isFinite(g) && isFinite(b))) { put(px, i, NONFINITE); continue; }
      px[4 * i] = srgb8(r * exposure);
      px[4 * i + 1] = srgb8(g * exposure);
      px[4 * i + 2] = srgb8(b * exposure);
      px[4 * i + 3] = 255;
    }
    return px;
  }

  function yAt(data, channels, i) {
    const o = i * channels;
    return channels >= 3 ? luminance(data[o], data[o + 1], data[o + 2]) : data[o];
  }

  /** Signed relative error of comp against ref (both n*channels) on the diverging scale; outside mask grey. */
  function renderError(comp, cch, ref, rch, w, h, eps, scale, mask) {
    const n = w * h;
    const px = new Uint8ClampedArray(4 * n);
    for (let i = 0; i < n; i++) {
      if (mask && !mask[i]) { put(px, i, MASKED); continue; }
      const yc = yAt(comp, cch, i), yr = yAt(ref, rch, i);
      if (!(isFinite(yc) && isFinite(yr))) { put(px, i, NONFINITE); continue; }
      put(px, i, diverging(relError(yc, yr, eps) / scale));
    }
    return px;
  }

  /** Reference noise: per-pixel standard error of Y over (|Y_ref| + eps), on the positive half of the scale. */
  function renderNoise(se, ref, rch, w, h, eps, scale, mask) {
    const n = w * h;
    const px = new Uint8ClampedArray(4 * n);
    for (let i = 0; i < n; i++) {
      if (mask && !mask[i]) { put(px, i, MASKED); continue; }
      const s = se[i], yr = yAt(ref, rch, i);
      if (!(isFinite(s) && isFinite(yr))) { put(px, i, NONFINITE); continue; }
      put(px, i, diverging(Math.abs(s) / (Math.abs(yr) + eps) / scale));
    }
    return px;
  }

  const api = { halfToFloat, decodeF16, luminance, srgb8, diverging, relError, fmtSig, fmtPct, outline,
                renderLinear, renderError, renderNoise, ANCHORS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document === 'undefined') return;

  // ------------------------------------------------------------------------------------------ app state

  const $ = (id) => document.getElementById(id);
  const S = {
    manifest: null, scene: null, viewId: null, view: null, base: '', data: {}, outlines: {},
    row: 'final', ev: 0, errScale: 1, refComp: 'isolated', showRoi: true, roiOn: {}, zoom: 2,
    cursor: null, loadToken: 0, cells: [],
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g,
      (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    for (const k in (attrs || {})) {
      if (k === 'class') e.className = attrs[k];
      else if (k === 'text') e.textContent = attrs[k];
      else if (k === 'html') e.innerHTML = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    for (const c of (children || [])) if (c) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    return e;
  }

  function fatal(html) {
    const f = $('fatal');
    f.innerHTML = html;
    f.hidden = false;
  }

  function fetchJSON(url) {
    return fetch(url, { cache: 'no-store' }).then((r) => {
      if (!r.ok) throw new Error(url + ': HTTP ' + r.status);
      return r.json();
    });
  }

  function fetchBuffer(url) {
    return fetch(url, { cache: 'no-store' }).then((r) => {
      if (!r.ok) throw new Error(url + ': HTTP ' + r.status);
      return r.arrayBuffer();
    });
  }

  // ------------------------------------------------------------------------------------------ startup

  function init() {
    if (location.protocol === 'file:') {
      fatal('<strong>Open the viewer through its local server.</strong> Browsers do not let a page opened from ' +
            'disk read its data files. Run <code>python -m tools.inspector --run &lt;run dir&gt;</code> ' +
            '(Windows: <code>Inspect.cmd</code>) and use the address it prints.');
      return;
    }
    bindControls();
    fetchJSON('manifest.json').then((m) => {
      S.manifest = m;
      $('run-id').textContent = 'run ' + (m.run || '?') + (m.git ? ' · ' + m.git : '');
      document.title = 'Run Inspector · ' + (m.run || '');
      const sceneSel = $('scene');
      sceneSel.innerHTML = '';
      for (const s of m.scenes || []) {
        const built = (s.views || []).filter((v) => v.manifest).length;
        sceneSel.appendChild(el('option', { value: s.name, text: s.name + (built ? '' : ' (no data)') }));
      }
      const fromHash = parseHash();
      const scene = (fromHash.scene && findScene(fromHash.scene)) ? fromHash.scene :
        (m.default_scene && findScene(m.default_scene) ? m.default_scene :
          ((m.scenes || [])[0] || {}).name);
      if (!scene) { fatal('This run has no views to show.'); return; }
      selectScene(scene, fromHash.view);
      window.addEventListener('hashchange', () => {
        const h = parseHash();
        if (h.scene && (h.scene !== S.scene || (h.view && h.view !== S.viewId)) && findScene(h.scene)) {
          selectScene(h.scene, h.view);
        }
      });
    }).catch((e) => fatal('Could not read <code>manifest.json</code>: ' + esc(e.message) +
                          '. Rebuild with <code>python -m tools.inspector</code>.'));
  }

  function parseHash() {
    const h = decodeURIComponent((location.hash || '').replace(/^#/, ''));
    const i = h.indexOf('/');
    return i < 0 ? { scene: h || null, view: null } : { scene: h.slice(0, i), view: h.slice(i + 1) || null };
  }

  function findScene(name) { return (S.manifest.scenes || []).find((s) => s.name === name) || null; }

  function selectScene(name, viewId) {
    const scene = findScene(name);
    S.scene = name;
    $('scene').value = name;
    const viewSel = $('view');
    viewSel.innerHTML = '';
    for (const v of scene.views || []) {
      viewSel.appendChild(el('option', { value: v.id, text: v.id + (v.manifest ? '' : ' (' + (v.error || 'no data') + ')') }));
    }
    const first = (scene.views || []).find((v) => v.manifest) || (scene.views || [])[0];
    const v = (scene.views || []).find((x) => x.id === viewId) || first;
    if (v) selectView(v.id); else showInfo(scene, null);
  }

  function selectView(viewId) {
    const scene = findScene(S.scene);
    const entry = (scene.views || []).find((v) => v.id === viewId);
    S.viewId = viewId;
    $('view').value = viewId;
    const hash = '#' + encodeURIComponent(S.scene) + '/' + encodeURIComponent(viewId);
    if (location.hash !== hash) history.replaceState(null, '', hash);
    S.view = null;
    S.data = {};
    S.outlines = {};
    S.cursor = null;
    $('grid').innerHTML = '';
    $('readout').innerHTML = '';
    $('metrics').innerHTML = '';
    $('rois').innerHTML = '';
    if (!entry || !entry.manifest) {
      showInfo(scene, null);
      $('grid').appendChild(el('div', { class: 'placeholder', text: 'No data for this view: ' +
                                         ((entry && entry.error) || 'not built') + '.' }));
      return;
    }
    const token = ++S.loadToken;
    $('grid').appendChild(el('div', { class: 'placeholder', text: 'Loading ' + S.scene + ' / ' + viewId + ' …' }));
    const base = entry.manifest.replace(/manifest\.json$/, '');
    fetchJSON(entry.manifest).then((vm) => {
      if (token !== S.loadToken) return null;
      S.view = vm;
      S.base = base;
      return loadData(vm, base, token);
    }).then((ok) => {
      if (!ok || token !== S.loadToken) return;
      const vm = S.view;
      if (S.zoom === 0 || !S.zoomSet) {
        S.zoom = vm.width <= 160 ? 3 : (vm.width <= 320 ? 2 : 1);
        $('zoom').value = String(S.zoom);
      }
      const hasIndirect = vm.columns.some((c) => c.component === 'isolated');
      S.refComp = hasIndirect ? 'isolated' : 'direct';
      $('refcomp').value = S.refComp;
      showInfo(scene, vm);
      buildRois(vm);
      buildGrid();
      renderAll();
      renderReadout();
      renderMetrics(vm);
    }).catch((e) => {
      if (token !== S.loadToken) return;
      $('grid').innerHTML = '';
      $('grid').appendChild(el('div', { class: 'placeholder', text: 'Could not load this view: ' + e.message }));
    });
  }

  function loadData(vm, base, token) {
    const jobs = [];
    const want = (key, f, kind) => {
      if (!f || !f.file) return;
      jobs.push(fetchBuffer(base + f.file).then((buf) => {
        if (token !== S.loadToken) return;
        const arr = kind === 'u8' ? new Uint8Array(buf) : decodeF16(buf);
        const expect = vm.width * vm.height * (f.channels || 1);
        if (arr.length !== expect) throw new Error(f.file + ': ' + arr.length + ' values, expected ' + expect);
        S.data[key] = { arr: arr, ch: f.channels || 1 };
      }));
    };
    for (const c of vm.columns) {
      const files = c.files || {};
      for (const k in files) want(c.id + ':' + k, files[k], 'f16');
      for (const k in (c.noise || {})) want(c.id + ':noise:' + k, c.noise[k], 'f16');
    }
    for (const r of vm.rois || []) want('roi:' + r.name, r, 'u8');
    return Promise.all(jobs).then(() => token === S.loadToken);
  }

  // ------------------------------------------------------------------------------------------ chrome

  function showInfo(scene, vm) {
    const info = $('info');
    info.innerHTML = '';
    const meta = [scene.group, 'comparison ' + (scene.comparison || 'exact')].filter(Boolean).join(', ');
    info.appendChild(el('span', { class: 'scene-name', text: scene.name + (S.viewId ? ' / ' + S.viewId : '') }));
    info.appendChild(el('span', { class: 'muted', text: meta }));
    if (vm) {
      let where = vm.kind === 'state' ? 'timeline state, capture frame ' + vm.capture_frame +
        (vm.frames ? ' (frames ' + vm.frames[0] + '–' + vm.frames[1] + ')' : '') : 'station ' + (vm.station || vm.view);
      info.appendChild(el('span', { class: 'muted', text: where + ', ' + vm.width + '×' + vm.height }));
    }
    if (scene.failure_mode) info.appendChild(el('span', { text: 'Failure mode: ' + scene.failure_mode }));
    const links = [];
    if (vm && vm.links && vm.links.sheet) links.push(el('a', { href: vm.links.sheet, target: '_blank', text: 'contact sheet' }));
    for (const t of (vm && vm.links && vm.links.temporal) || []) {
      links.push(el('a', { href: t.href, target: '_blank', text: 'temporal plot: ' + t.label }));
    }
    if (S.manifest.links && S.manifest.links.report) {
      links.push(el('a', { href: S.manifest.links.report, target: '_blank', text: 'report.md' }));
    }
    if (links.length) {
      const span = el('span', {}, []);
      links.forEach((a, i) => { if (i) span.appendChild(document.createTextNode(' · ')); span.appendChild(a); });
      info.appendChild(span);
    }
    const warns = (vm && vm.warnings) || [];
    if (warns.length) info.appendChild(el('div', { class: 'warnings', text: 'Warning: ' + warns.join('; ') }));
  }

  function buildRois(vm) {
    const box = $('rois');
    box.innerHTML = '';
    S.roiOn = {};
    (vm.rois || []).forEach((r, i) => {
      r.color = ROI_COLORS[i % ROI_COLORS.length];
      S.roiOn[r.name] = r.name !== 'all';
      const cb = el('input', { type: 'checkbox' });
      cb.checked = S.roiOn[r.name];
      cb.addEventListener('change', () => { S.roiOn[r.name] = cb.checked; renderOverlays(); });
      box.appendChild(el('label', { class: 'roi-chip', title: r.pixels + ' pixels (eroded mask, as the metrics use)' }, [
        cb, el('span', { class: 'swatch', style: 'background:' + r.color }),
        r.name + ' (' + r.role + ', ' + r.pixels + ' px)']));
      const m = S.data['roi:' + r.name];
      S.outlines[r.name] = m ? outline(m.arr, vm.width, vm.height) : [];
    });
  }

  function bindControls() {
    $('scene').addEventListener('change', (e) => selectScene(e.target.value));
    $('view').addEventListener('change', (e) => selectView(e.target.value));
    for (const b of document.querySelectorAll('#row-seg button')) {
      b.addEventListener('click', () => setRow(b.dataset.row));
    }
    $('ev').addEventListener('input', (e) => setEv(parseFloat(e.target.value)));
    $('ev-auto').addEventListener('click', () => setEv(0));
    $('err-scale').addEventListener('change', (e) => { S.errScale = parseFloat(e.target.value); renderAll(); });
    $('refcomp').addEventListener('change', (e) => { S.refComp = e.target.value; buildGrid(); renderAll(); renderReadout(); });
    $('roi-toggle').addEventListener('change', (e) => { S.showRoi = e.target.checked; renderOverlays(); });
    $('zoom').addEventListener('change', (e) => { S.zoom = parseInt(e.target.value, 10); S.zoomSet = true; applyZoom(); });
    document.addEventListener('keydown', (e) => {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT')) return;
      if (e.key === '1') setRow('final');
      else if (e.key === '2') setRow('component');
      else if (e.key === '3') setRow('error');
      else if (e.key === '[') setEv(S.ev - 0.5);
      else if (e.key === ']') setEv(S.ev + 0.5);
      else if (e.key === 'a') setEv(0);
      else if (e.key === 'r') { S.showRoi = !S.showRoi; $('roi-toggle').checked = S.showRoi; renderOverlays(); }
    });
    setRow('final');
  }

  function setRow(row) {
    S.row = row;
    for (const b of document.querySelectorAll('#row-seg button')) b.setAttribute('aria-pressed', String(b.dataset.row === row));
    $('refcomp-ctl').style.opacity = row === 'final' ? '0.5' : '1';
    $('errscale-ctl').style.opacity = row === 'error' ? '1' : '0.5';
    if (S.view) { buildGrid(); renderAll(); }
  }

  function setEv(v) {
    S.ev = Math.max(-10, Math.min(10, Math.round(v * 10) / 10));
    $('ev').value = String(S.ev);
    $('ev-out').textContent = (S.ev > 0 ? '+' : '') + S.ev.toFixed(1) + ' EV';
    if (S.view && S.row !== 'error') renderAll();
  }

  function applyZoom() {
    if (!S.view) return;
    for (const c of S.cells) {
      if (!c.canvas) continue;
      for (const cv of [c.canvas, c.overlay]) {
        cv.style.width = (S.view.width * S.zoom) + 'px';
        cv.style.height = (S.view.height * S.zoom) + 'px';
      }
    }
  }

  // ------------------------------------------------------------------------------------------ grid

  /** What a column shows in the current row: {img, ref, kind, sub, missing}. */
  function cellSource(col) {
    const vm = S.view;
    const d = (k) => S.data[col.id + ':' + k];
    if (col.kind === 'reference') {
      if (S.row === 'final') return { kind: 'linear', img: d('final'), exposure: vm.exposure.final, sub: 'full' };
      if (S.row === 'component') {
        return { kind: 'linear', img: d(S.refComp), exposure: vm.exposure[S.refComp], sub: S.refComp };
      }
      const se = d('noise:' + S.refComp);
      return se ? { kind: 'noise', img: se, ref: d(S.refComp), eps: vm.eps[S.refComp],
                    sub: 'relative standard error of ' + S.refComp + ' (noise floor)' }
                : { missing: 'no standard-error image' };
    }
    if (!col.files || !col.files.final) {
      return { missing: (col.status && col.status !== 'ok' ? col.status + (col.by_design ? ' (by design)' : '') + ': ' +
               (col.reason || '') : (col.missing || 'no capture')) };
    }
    if (S.row === 'final') return { kind: 'linear', img: d('final'), exposure: vm.exposure.final, sub: 'final' };
    const comp = col.component;
    if (!d('component')) return { missing: col.component_missing || 'component unavailable' };
    if (S.row === 'component') return { kind: 'linear', img: d('component'), exposure: vm.exposure[comp], sub: comp };
    return { kind: 'error', img: d('component'), ref: S.data['reference:' + comp], eps: vm.eps[comp],
             sub: comp + ' vs reference ' + comp };
  }

  function buildGrid() {
    const grid = $('grid');
    grid.innerHTML = '';
    S.cells = [];
    const vm = S.view;
    if (!vm) return;
    for (const col of vm.columns) {
      const src = cellSource(col);
      const failed = col.status === 'failed';
      const cell = el('div', { class: 'cell' + (failed ? ' failed' : '') });
      const kind = col.kind === 'reference' ? 'Mitsuba' : (col.kind || '') + (col.dynamic ? ', dynamic' : '');
      const head = el('header', {}, [el('span', { class: 'label', text: col.label, title: col.label }),
                                     el('span', { class: 'kind muted', text: kind, title: kind })]);
      cell.appendChild(head);
      const sub = el('div', { class: 'sub', text: src.sub || '', title: src.sub || '' });
      cell.appendChild(sub);
      const rec = { col: col, cell: cell, sub: sub, canvas: null, overlay: null, src: src };
      if (src.missing || !src.img) {
        const ph = el('div', { class: 'placeholder', text: src.missing || 'missing' });
        ph.style.width = (vm.width * S.zoom) + 'px';
        ph.style.height = (vm.height * S.zoom) + 'px';
        cell.appendChild(ph);
      } else {
        const stack = el('div', { class: 'stack' });
        const cv = el('canvas', { class: 'img', width: vm.width, height: vm.height });
        const ov = el('canvas', { class: 'overlay', width: vm.width, height: vm.height });
        stack.appendChild(cv);
        stack.appendChild(ov);
        cell.appendChild(stack);
        rec.canvas = cv;
        rec.overlay = ov;
        cv.addEventListener('mousemove', (e) => onHover(e, cv));
        cv.addEventListener('click', (e) => onHover(e, cv));
      }
      grid.appendChild(cell);
      S.cells.push(rec);
    }
    applyZoom();
    renderLegend();
  }

  function renderAll() {
    const vm = S.view;
    if (!vm) return;
    const gain = Math.pow(2, S.ev);
    const mask = S.data['roi:all'] ? S.data['roi:all'].arr : null;
    for (const c of S.cells) {
      if (!c.canvas) continue;
      const s = cellSource(c.col);
      c.src = s;
      let px;
      if (s.kind === 'linear') {
        px = renderLinear(s.img.arr, s.img.ch, vm.width, vm.height, s.exposure * gain);
        c.sub.textContent = s.sub + ' · ×' + fmtSig(s.exposure * gain);
        c.sub.title = c.sub.textContent;
      } else if (s.kind === 'error') {
        px = s.ref ? renderError(s.img.arr, s.img.ch, s.ref.arr, s.ref.ch, vm.width, vm.height, s.eps, S.errScale, mask)
                   : null;
        c.sub.textContent = s.sub;
      } else if (s.kind === 'noise') {
        px = s.ref ? renderNoise(s.img.arr, s.ref.arr, s.ref.ch, vm.width, vm.height, s.eps, S.errScale, mask) : null;
        c.sub.textContent = s.sub;
      }
      const ctx = c.canvas.getContext('2d');
      if (px) ctx.putImageData(new ImageData(px, vm.width, vm.height), 0, 0);
      else { ctx.fillStyle = 'rgb(' + MISSING.join(',') + ')'; ctx.fillRect(0, 0, vm.width, vm.height); }
    }
    renderOverlays();
    renderLegend();
  }

  function renderOverlays() {
    const vm = S.view;
    if (!vm) return;
    const w = vm.width, h = vm.height;
    const px = new Uint8ClampedArray(4 * w * h);
    if (S.showRoi) {
      for (const r of vm.rois || []) {
        if (!S.roiOn[r.name]) continue;
        const c = hexRgb(r.color);
        for (const i of S.outlines[r.name] || []) put(px, i, c);
      }
    }
    if (S.cursor) {
      const cx = S.cursor.x, cy = S.cursor.y;
      for (let x = 0; x < w; x++) if (Math.abs(x - cx) > 2 && (x & 1) === 0) put(px, cy * w + x, [255, 255, 255]);
      for (let y = 0; y < h; y++) if (Math.abs(y - cy) > 2 && (y & 1) === 0) put(px, y * w + cx, [255, 255, 255]);
    }
    const img = new ImageData(px, w, h);
    for (const c of S.cells) if (c.overlay) c.overlay.getContext('2d').putImageData(img, 0, 0);
  }

  function hexRgb(hex) {
    const v = parseInt(hex.slice(1), 16);
    return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
  }

  function renderLegend() {
    const box = $('legend');
    const show = S.view && S.row === 'error';
    box.hidden = !show;
    if (!show) return;
    box.innerHTML = '';
    const cv = el('canvas', { width: 256, height: 1 });
    const ctx = cv.getContext('2d');
    const img = ctx.createImageData(256, 1);
    for (let x = 0; x < 256; x++) {
      const c = diverging((x / 255) * 2 - 1);
      img.data.set([c[0], c[1], c[2], 255], 4 * x);
    }
    ctx.putImageData(img, 0, 0);
    const s = S.errScale;
    const ticks = el('div', { class: 'ticks' }, [el('span', { text: fmtPct(-s) }), el('span', { text: fmtPct(-s / 2) }),
      el('span', { text: '0' }), el('span', { text: fmtPct(s / 2) }), el('span', { text: fmtPct(s) })]);
    box.appendChild(el('div', { class: 'scale' }, [cv, ticks]));
    box.appendChild(el('span', { class: 'muted', html:
      'Signed error (Y − Y<sub>ref</sub>) / (|Y<sub>ref</sub>| + ε), ε = 1% of the reference mean over ROI all: ' +
      'blue = too dark, red = too bright, grey = invalid pixel, magenta = NaN/inf. ' +
      'Reference column: its per-pixel standard error on the same scale.' }));
  }

  // ------------------------------------------------------------------------------------------ readout

  function onHover(e, cv) {
    const vm = S.view;
    const rect = cv.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / rect.width * vm.width);
    const y = Math.floor((e.clientY - rect.top) / rect.height * vm.height);
    if (x < 0 || y < 0 || x >= vm.width || y >= vm.height) return;
    if (S.cursor && S.cursor.x === x && S.cursor.y === y) return;
    S.cursor = { x: x, y: y };
    renderOverlays();
    renderReadout();
  }

  function rgbAt(entry, i) {
    if (!entry) return null;
    const o = i * entry.ch;
    return entry.ch >= 3 ? [entry.arr[o], entry.arr[o + 1], entry.arr[o + 2]] : [entry.arr[o]];
  }

  function rgbText(v) {
    if (!v) return '–';
    return v.length === 3 ? v.map((x) => fmtSig(x)).join(', ') : fmtSig(v[0]);
  }

  function yOf(v) { return v && v.length === 3 ? luminance(v[0], v[1], v[2]) : (v ? v[0] : null); }

  function renderReadout() {
    const box = $('readout');
    const vm = S.view;
    if (!vm) { box.innerHTML = ''; return; }
    if (!S.cursor) {
      $('readout-pos').textContent = '(move the cursor over an image)';
      box.innerHTML = '';
      return;
    }
    const i = S.cursor.y * vm.width + S.cursor.x;
    const inside = (vm.rois || []).filter((r) => S.data['roi:' + r.name] && S.data['roi:' + r.name].arr[i])
      .map((r) => r.name);
    $('readout-pos').textContent = '(x ' + S.cursor.x + ', y ' + S.cursor.y + '; ROIs: ' +
      (inside.length ? inside.join(', ') : 'none') + ')';
    const rows = [];
    for (const col of vm.columns) {
      const d = (k) => S.data[col.id + ':' + k];
      let fin, compName, comp, err = null, errLabel = '';
      if (col.kind === 'reference') {
        fin = rgbAt(d('final'), i);
        compName = S.refComp;
        comp = rgbAt(d(S.refComp), i);
        const se = rgbAt(d('noise:' + S.refComp), i);
        if (se && comp) { err = Math.abs(se[0]) / (Math.abs(yOf(comp)) + vm.eps[S.refComp]); errLabel = ' (rel. s.e.)'; }
      } else {
        fin = rgbAt(d('final'), i);
        compName = col.component || '';
        comp = rgbAt(d('component'), i);
        const ref = rgbAt(S.data['reference:' + col.component], i);
        if (comp && ref) {
          if (yOf(ref) === 0 && !(vm.eps[col.component] > 1e-12)) errLabel = 'ΔY ' + fmtSig(yOf(comp)) + ' (reference 0)';
          else err = relError(yOf(comp), yOf(ref), vm.eps[col.component]);
        }
      }
      rows.push('<tr><td>' + esc(col.label) + '</td><td class="num">' + rgbText(fin) + '</td><td class="num">' +
                fmtSig(yOf(fin)) + '</td><td>' + esc(compName) + '</td><td class="num">' + rgbText(comp) +
                '</td><td class="num">' + fmtSig(yOf(comp)) + '</td><td class="num">' +
                (err == null ? (errLabel ? '' : '–') : (col.kind === 'reference' ? fmtPct(err, false) : fmtPct(err))) +
                esc(errLabel) +
                '</td></tr>');
    }
    box.innerHTML = '<table><thead><tr><th>column</th><th>final R, G, B</th><th>final Y</th><th>component</th>' +
      '<th>component R, G, B</th><th>component Y</th><th>signed error</th></tr></thead><tbody>' +
      rows.join('') + '</tbody></table>';
  }

  // ------------------------------------------------------------------------------------------ metrics

  function metricRows(vm) {
    const order = Object.keys(S.manifest.engines || {});
    const modeIdx = (r) => Object.keys(((S.manifest.engines || {})[r.engine] || {}).modes || {}).indexOf(r.mode);
    return (vm.metrics || []).slice().sort((a, b) =>
      (order.indexOf(a.engine) - order.indexOf(b.engine)) || (modeIdx(a) - modeIdx(b)));
  }

  function renderMetrics(vm) {
    const box = $('metrics');
    const rows = metricRows(vm);
    if (!rows.length) { box.innerHTML = '<p class="muted">No metrics rows for this view.</p>'; return; }
    const FLOOR = 2;  // tools/report.py NOISE_K
    if ((vm.comparison || 'exact') === 'appearance') {
      const rois = [];
      for (const r of rows) for (const k of Object.keys((r.flip && r.flip.rois) || {})) if (!rois.includes(k)) rois.push(k);
      let html = '<table><thead><tr><th>engine / mode</th><th>FLIP mean</th>' +
        rois.map((k) => '<th>FLIP ' + esc(k) + '</th>').join('') + '<th>notes</th></tr></thead><tbody>';
      for (const r of rows) {
        html += '<tr><td>' + esc(r.engine + ' / ' + (r.mode || 'all modes')) + '</td><td class="num">' +
          fmtSig(r.flip && r.flip.mean) + '</td>' + rois.map((k) => '<td class="num">' +
          fmtSig(r.flip && r.flip.rois && r.flip.rois[k]) + '</td>').join('') + '<td class="note">' + esc(notes(r)) +
          '</td></tr>';
      }
      box.innerHTML = html + '</tbody></table><p class="muted">Appearance scene: only FLIP is reported.</p>';
      return;
    }
    const rois = [];
    for (const r of rows) {
      for (const k of Object.keys(r.rois || {})) if (!rois.find((x) => x.name === k)) {
        rois.push({ name: k, role: r.rois[k].role || 'any', pixels: r.rois[k].pixels });
      }
    }
    rois.sort((a, b) => (a.name !== 'all') - (b.name !== 'all'));
    let html = '<table><thead><tr><th>engine / mode</th><th>component</th>' + rois.map((x) => '<th>' + esc(x.name) +
      ' <span class="muted">(' + esc(x.role) + ', ' + x.pixels + ' px)<br>' +
      (x.role === 'dark' ? 'leak_abs / leak_rel (reference)' : 'bias / rel_l1 / rel_mse' + (x.role === 'bleed' ? ' / Δc' : '')) +
      '</span></th>').join('') + '<th>energy</th><th>FLIP</th><th>notes</th></tr></thead><tbody>';
    for (const comp of ['direct', 'isolated']) {
      const src = rows.find((r) => r.status === 'ok' && r.component === comp);
      if (!src) continue;
      html += '<tr class="noise"><td>reference noise σ</td><td>' + comp + '</td>' + rois.map((x) => {
        const s = (src.rois || {})[x.name];
        if (!s) return '<td>–</td>';
        return '<td class="num">' + (x.role === 'dark' ? 'leak_rel σ ' + fmtPct(s.leak_noise_rel, false)
                                                         : 'σ ' + fmtPct(s.ref_noise_rel, false)) + '</td>';
      }).join('') + '<td class="num">σ ' + fmtPct(((src.rois || {}).all || {}).ref_noise_rel, false) +
        '</td><td></td><td class="note">relative s.e. of the reference ROI mean</td></tr>';
    }
    for (const r of rows) {
      const label = esc(r.engine + ' / ' + (r.mode || 'all modes'));
      if (r.status !== 'ok') {
        html += '<tr><td class="status-' + esc(r.status) + '">' + label + '</td><td>' + esc(r.component || '–') +
          '</td>' + rois.map(() => '<td>–</td>').join('') + '<td>–</td><td>–</td><td class="note">' + esc(notes(r)) +
          '</td></tr>';
        continue;
      }
      const cells = rois.map((x) => {
        const s = (r.rois || {})[x.name];
        if (!s) return '<td>–</td>';
        if (x.role === 'dark') {
          const below = finite(s.leak_abs) && finite(s.ref_noise_abs) && finite(s.ref_leak_abs) &&
            Math.abs(s.leak_abs - s.ref_leak_abs) <= FLOOR * s.ref_noise_abs;
          return '<td class="num">' + fmtSig(s.leak_abs) + ' / ' + fmtPct(s.leak_rel, false) + (below ? '†' : '') +
            ' (' + fmtPct(s.ref_leak_rel, false) + ')</td>';
        }
        let t;
        if (s.bias == null && finite(s.bias_abs)) t = 'ΔY ' + fmtSig(s.bias_abs) + (s.ref_mean === 0 ? ' (reference 0)' :
          (s.ref_within_noise ? ' (reference ≈ 0 within noise)' : ''));
        else {
          const below = finite(s.bias) && finite(s.ref_noise_rel) && Math.abs(s.bias) <= FLOOR * s.ref_noise_rel;
          t = fmtPct(s.bias) + (below ? '†' : '') + ' / ' + fmtSig(s.rel_l1) + ' / ' + fmtSig(s.rel_mse);
        }
        if (x.role === 'bleed') t += ' / ' + fmtSig(((r.bleed || {})[x.name] || {}).dist);
        return '<td class="num">' + t + '</td>';
      }).join('');
      const allNoise = ((r.rois || {}).all || {}).ref_noise_rel;
      const eBelow = finite(r.energy) && finite(allNoise) && Math.abs(r.energy) <= FLOOR * allNoise;
      html += '<tr><td>' + label + '</td><td>' + esc(r.component) + '</td>' + cells + '<td class="num">' +
        fmtPct(r.energy) + (eBelow ? '†' : '') + '</td><td class="num">' + fmtSig(r.flip && r.flip.mean) +
        '</td><td class="note">' + esc(notes(r)) + '</td></tr>';
    }
    box.innerHTML = html + '</tbody></table><p class="muted">† within ' + FLOOR + ' reference standard errors of ' +
      'the reference (below the reference noise floor). Bias is relative and signed; energy = ΣY(engine) / ' +
      'ΣY(reference) − 1 over ROI all.</p>';
  }

  function notes(r) {
    if (r.status && r.status !== 'ok') return r.status + (r.by_design ? ' (by design)' : '') + ': ' + (r.reason || '');
    const n = (r.warnings || []).slice();
    if (r.flip && r.flip.error) n.push('FLIP: ' + r.flip.error);
    return n.join('; ');
  }

  init();
})();
