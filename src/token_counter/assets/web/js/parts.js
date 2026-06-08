/* parts.js — shared Material 3 / Material You primitives.
   Faithful vanilla port of parts.jsx (+ WavyBar, TrayIcon).
   Every function returns a DOM node. Depends on ui.js. */
(function (global) {
  'use strict';
  var h = UI.h, s = UI.s;

  /* ---- Per-provider dynamic color (Material You content-based color) ---- */
  var PROVIDERS = {
    dark: {
      claude: { name: 'Claude', glyph: 'sunburst', gauge: '#ffb59b', track: '#5a3f33', container: '#4d2a1b', onContainer: '#ffdbcf' },
      openai: { name: 'ChatGPT', glyph: 'ring', gauge: '#54dbb6', track: '#234a40', container: '#00382c', onContainer: '#74f8d8' },
      gemini: { name: 'Gemini', glyph: 'spark', gauge: '#adc6ff', track: '#3a4763', container: '#243665', onContainer: '#dae2ff' },
    },
    light: {
      claude: { name: 'Claude', glyph: 'sunburst', gauge: '#9b4521', track: '#f4d6c8', container: '#ffdbcf', onContainer: '#370e00' },
      openai: { name: 'ChatGPT', glyph: 'ring', gauge: '#006a52', track: '#bdeada', container: '#76f6d6', onContainer: '#002019' },
      gemini: { name: 'Gemini', glyph: 'spark', gauge: '#3a5ba8', track: '#cdd7f5', container: '#dae2ff', onContainer: '#001949' },
    },
  };

  /* ---- Shared dashboard data ---- */
  var DASH_DATA = [
    { key: 'claude', tokens: '28K / 40K', pct: 70, resets: '41s',
      inp: '18K / 30K', out: '10K / 20K', msgs: '12 / 45 msgs', rate: '8.2K tok/min' },
    { key: 'openai', tokens: '1.7M / 2.0M', pct: 85, resets: '14m',
      inp: '1.1M / 1.3M', out: '600K / 700K', msgs: '120 / 150 msgs', rate: '142K tok/min' },
    { key: 'gemini', tokens: '540K / 1.0M', pct: 54, resets: 'daily',
      inp: '380K / 700K', out: '160K / 300K', msgs: 'tracked usage', rate: '34K tok/min' },
  ];

  function levelColor(pct) {
    if (pct >= 80) return 'var(--red)';
    if (pct >= 60) return 'var(--amber)';
    return 'var(--green)';
  }

  /* ---- Provider glyph (simple geometric marks only) ---- */
  function Glyph(kind, color, size) {
    size = size || 18;
    if (kind === 'ring') {
      return s('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none' },
        s('circle', { cx: 12, cy: 12, r: 7.5, stroke: color, 'stroke-width': 2.4 }),
        s('circle', { cx: 12, cy: 12, r: 2.1, fill: color }));
    }
    if (kind === 'spark') {
      return s('svg', { width: size, height: size, viewBox: '0 0 24 24', fill: 'none' },
        s('path', { d: 'M12 2 C12.7 7.5 16.5 11.3 22 12 C16.5 12.7 12.7 16.5 12 22 C11.3 16.5 7.5 12.7 2 12 C7.5 11.3 11.3 7.5 12 2 Z', fill: color }));
    }
    var svg = s('svg', { width: size, height: size, viewBox: '0 0 24 24' });
    for (var i = 0; i < 8; i++) {
      var a = (i * Math.PI) / 4;
      svg.appendChild(s('line', {
        x1: 12 + Math.cos(a) * 3.5, y1: 12 + Math.sin(a) * 3.5,
        x2: 12 + Math.cos(a) * 9, y2: 12 + Math.sin(a) * 9,
        stroke: color, 'stroke-width': 2.2, 'stroke-linecap': 'round',
      }));
    }
    return svg;
  }

  function Avatar(p, size, glyphSize) {
    size = size || 40;
    return h('span', { class: 'm3-avatar', style: { width: size + 'px', height: size + 'px', background: p.container } },
      Glyph(p.glyph, p.onContainer, glyphSize || size * 0.55));
  }

  /* ---- M3 circular progress (determinate ring, rounded caps + track gap) ---- */
  function Ring(opts) {
    var pct = opts.pct, size = opts.size || 72, stroke = opts.stroke || 7, color = opts.color, label = opts.label, sub = opts.sub;
    var r = (size - stroke) / 2;
    var c = 2 * Math.PI * r;
    var gap = c * 0.06;
    var avail = c - gap;
    var ind = Math.max(0.0001, pct / 100) * avail;
    var svg = s('svg', { width: size, height: size },
      s('circle', { cx: size / 2, cy: size / 2, r: r, fill: 'none',
        stroke: 'var(--prov-track, var(--outline-variant))', 'stroke-width': stroke,
        'stroke-dasharray': (avail - ind) + ' ' + (ind + gap), 'stroke-dashoffset': -(ind + gap / 2), 'stroke-linecap': 'round' }),
      s('circle', { cx: size / 2, cy: size / 2, r: r, fill: 'none',
        stroke: color, 'stroke-width': stroke,
        'stroke-dasharray': ind + ' ' + (c - ind), 'stroke-dashoffset': -gap / 2, 'stroke-linecap': 'round' }));
    svg.style.transform = 'rotate(-90deg)';
    var center = h('div', { style: { position: 'absolute', inset: '0', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', lineHeight: '1' } },
      h('span', { style: { fontSize: (size * 0.26) + 'px', fontWeight: '500', color: 'var(--on-surface)' } }, label),
      sub ? h('span', { style: { fontSize: (size * 0.13) + 'px', color: 'var(--on-surface-variant)', marginTop: '2px' } }, sub) : null);
    return h('div', { style: { position: 'relative', width: size + 'px', height: size + 'px', flex: 'none' } }, svg, center);
  }

  /* ---- Linear progress ---- */
  function Linear(pct, color) {
    return h('div', { class: 'm3-linear', style: { '--prov': color } },
      h('div', { class: 'track' }),
      h('div', { class: 'ind', style: { width: 'calc(' + Math.min(pct, 100) + '% - 6px)' } }),
      h('div', { class: 'stop' }));
  }

  /* ---- Split-flap number tiles (signature element) ---- */
  function Flap(text, size, gap) {
    size = size || 15; gap = gap == null ? 2 : gap;
    var flap = h('span', { class: 'flap', style: { gap: gap + 'px' } });
    String(text).split('').forEach(function (ch) {
      var sep = ch === ' ' || ch === '/';
      flap.appendChild(h('span', {
        class: 'tile' + (sep ? ' sep' : ''),
        style: { fontSize: size + 'px', minWidth: sep ? 'auto' : (size * 0.7) + 'px' },
      }, ch === ' ' ? '\u00a0' : ch));
    });
    return flap;
  }

  function Pulse(color) {
    return h('span', { class: 'pulse-dot', style: { '--pc': color } });
  }

  /* ---- M3 Expressive wavy active indicator (SVG path) ---- */
  function WavyBar(pct, color, track) {
    var W = 320, mid = 7, amp = 3.2, wl = 16;
    var d = 'M0 ' + mid;
    var fillX = (pct / 100) * W;
    for (var x = 0; x <= fillX; x += 2) {
      var y = mid + Math.sin((x / wl) * 2 * Math.PI) * amp;
      d += ' L' + x + ' ' + y.toFixed(2);
    }
    var svg = s('svg', { viewBox: '0 0 ' + W + ' 14', preserveAspectRatio: 'none' },
      s('path', { d: d, fill: 'none', stroke: color, 'stroke-width': 3.4, 'stroke-linecap': 'round' }),
      s('circle', { cx: fillX, cy: mid, r: 3.2, fill: color }));
    return h('div', { class: 'm3-wavy', style: { '--prov-track': track } }, h('div', { class: 'wtrack' }), svg);
  }

  /* ---- Tray icon: ascending usage bars (kept motif) ---- */
  function TrayIcon(pct, size) {
    size = size || 40;
    var bars = 5;
    var lc = pct >= 80 ? 'var(--red)' : pct >= 60 ? 'var(--amber)' : 'var(--green)';
    var lit = Math.round((pct / 100) * bars);
    var bw = size / (bars * 1.7);
    var box = h('div', { style: { width: size + 'px', height: size + 'px', borderRadius: '9px', background: 'var(--s-high)',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: (bw * 0.55) + 'px', padding: (size * 0.18) + 'px' } });
    for (var i = 0; i < bars; i++) {
      box.appendChild(h('span', { style: { width: bw + 'px', height: (28 + i * 18) + '%', borderRadius: '2px',
        background: i < lit ? lc : 'var(--outline-variant)' } }));
    }
    return box;
  }

  global.PARTS = {
    PROVIDERS: PROVIDERS, DASH_DATA: DASH_DATA, levelColor: levelColor,
    Glyph: Glyph, Avatar: Avatar, Ring: Ring, Linear: Linear, Flap: Flap, Pulse: Pulse,
    WavyBar: WavyBar, TrayIcon: TrayIcon,
  };
})(window);
