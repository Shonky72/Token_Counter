/* bridge.js — wires the bundled Material 3 screens to the Python app.

   The host page sets window.TOKN_SCREEN ('dashboard' | 'compact' | 'settings').
   On load we ask Python (pywebview js_api) for the live state, render the matching
   screen, and attach the controls to Api actions. Python pushes dashboard/compact
   refreshes by calling window.tokn.update().
*/
(function () {
  'use strict';
  var SCREEN = window.TOKN_SCREEN || 'dashboard';
  var h = UI.h, mi = UI.mi;

  function api() { return (window.pywebview && window.pywebview.api) || null; }
  function on(el, fn) { if (el) el.addEventListener('click', fn); }
  function applyTheme(theme) {
    theme = theme || 'dark';
    document.body.className = 'm3';
    document.body.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-theme', theme);
  }

  /* ===================== dashboard / compact ===================== */
  function applyState(state) {
    if (!state) return;
    var theme = state.theme || 'dark';
    PARTS.DASH_DATA = state.cards || [];
    PARTS.PROVIDERS = state.providers || {};
    applyTheme(theme);

    var mount = document.getElementById('app');
    mount.innerHTML = '';
    var node = SCREEN === 'compact'
      ? SCREENS.CompactPopup(theme)
      : DASHBOARDS.DashElevated(theme);
    mount.appendChild(node);
    if (SCREEN !== 'compact') wireDashboard(node, state);
  }

  function wireDashboard(node, state) {
    var a = api();

    // AppBar: [title, version, gear]. Add a global refresh button before the gear.
    var appbar = node.querySelector('.m3-appbar');
    if (appbar) {
      var gear = appbar.querySelector('.m3-icon-btn');  // the settings gear
      var refreshAll = h('button', { class: 'm3-icon-btn', title: 'Refresh all' }, mi('refresh'));
      if (gear) appbar.insertBefore(refreshAll, gear); else appbar.appendChild(refreshAll);
      if (a) on(refreshAll, function () { Promise.resolve(a.refresh()).then(applyState); });
      if (a) on(gear, function () { a.open_settings(); });
    }

    // Footer: [services-text, Accounts button].
    var footer = node.lastElementChild;
    if (footer) {
      var meta = state.meta || {};
      if (footer.firstElementChild && meta.services_line) {
        footer.firstElementChild.textContent = meta.services_line;
      }
      var accounts = footer.querySelector('.m3-btn.tonal');
      if (a) on(accounts, function () { a.open_login(); });
    }

    var cards = node.querySelectorAll('.m3-card.elevated');
    (state.cards || []).forEach(function (d, i) {
      var card = cards[i];
      if (!card) return;

      // Per-card refresh icon -> refresh that provider and re-render (with the flip).
      var refresh = card.querySelector('.m3-icon-btn');
      if (a) on(refresh, function (ev) {
        ev.stopPropagation();
        Promise.resolve(a.refresh_one(d.key)).then(applyState);
      });

      // Click the card to open the provider's usage/billing console.
      if (a && d.usage_url) {
        card.style.cursor = 'pointer';
        on(card, function () { a.open_usage(d.key); });
      }

      // No numeric amount (error / no live data): show a short caption, not a flap.
      if (d.error || !d.tokens) {
        var reel = card.querySelector('.reel');
        if (reel) {
          var note = h('div', { class: 't-body-s txt-variant', title: d.error || '' },
            d.note || d.error || 'no data');
          var wrap = reel.parentNode;
          wrap.replaceChild(note, reel);
          var lbl = wrap.querySelector('.t-label-m.txt-variant');  // "TOKENS / MIN"
          if (lbl) lbl.remove();
        }
      }

      // Drop chips that have no data (no reset window / no input-output split).
      var chips = card.querySelectorAll('.m3-chip');
      if (!d.resets && chips[0]) chips[0].remove();
      if (!(d.inp || d.out) && chips.length && chips[chips.length - 1]) {
        chips[chips.length - 1].remove();
      }
    });
  }

  /* ===================== settings ===================== */
  function Switch(state, onChange, disabled) {
    var el = h('div', {
      class: 'm3-switch' + (state ? ' on' : ''),
      style: disabled ? { opacity: '.45', cursor: 'default' } : null,
    }, h('span', { class: 'knob' }));
    if (!disabled) on(el, function () {
      var now = !el.classList.contains('on');
      el.classList.toggle('on', now);
      onChange(now);
    });
    return el;
  }

  function Segmented(options, value, onChange) {
    var wrap = h('div', { class: 'm3-seg' });
    options.forEach(function (o) {
      var btn = h('button', { class: o.value === value ? 'sel' : '' }, o.label);
      on(btn, function () {
        var bs = wrap.querySelectorAll('button');
        for (var i = 0; i < bs.length; i++) bs[i].className = '';
        btn.className = 'sel';
        onChange(o.value);
      });
      wrap.appendChild(btn);
    });
    return wrap;
  }

  function Row(title, sub, control) {
    return h('div', { style: { display: 'flex', alignItems: 'center', gap: '14px', padding: '12px 0' } },
      h('div', { style: { flex: '1', minWidth: '0' } },
        h('div', { class: 't-body-l' }, title),
        sub ? h('div', { class: 't-body-s txt-variant', style: { marginTop: '2px' } }, sub) : null),
      control);
  }

  function Tabs(items, active, onPick) {
    var wrap = h('div', { style: { display: 'flex', borderBottom: '1px solid var(--outline-variant)' } });
    items.forEach(function (t, i) {
      var tab = h('div', {
        style: {
          flex: '1', textAlign: 'center', padding: '14px 0 12px', position: 'relative',
          fontSize: '14px', fontWeight: '500', cursor: 'pointer',
          color: i === active ? 'var(--primary)' : 'var(--on-surface-variant)',
        },
      }, t, i === active ? h('span', {
        style: {
          position: 'absolute', bottom: '0', left: '50%', transform: 'translateX(-50%)',
          width: 'calc(100% - 24px)', height: '3px', borderRadius: '3px 3px 0 0', background: 'var(--primary)',
        },
      }) : null);
      on(tab, function () { onPick(i); });
      wrap.appendChild(tab);
    });
    return wrap;
  }

  var _tab = 0;
  function set(key, value) {
    var a = api();
    if (!a) return;
    Promise.resolve(a.set_setting(key, value)).then(function (s) {
      // Re-render so the control reflects the persisted value and a theme change
      // recolours the whole dialog (its own data-theme lives on the frame).
      if (s) renderSettings(s);
    });
  }

  function settingsBody(s, toast) {
    var box = h('div', { style: { padding: '8px 20px 4px' } });
    if (_tab === 0) {  // Display
      box.appendChild(Row('Theme', 'Match the OS or pick one',
        Segmented([{ label: 'System', value: 'system' }, { label: 'Dark', value: 'dark' }, { label: 'Light', value: 'light' }],
          s.theme, function (v) { set('theme', v); })));
      box.appendChild(Row('Show', null,
        Segmented([{ label: 'Used', value: 'used' }, { label: 'Remaining', value: 'remaining' }],
          s.basis, function (v) { set('token_basis', v); })));
      box.appendChild(Row('As', null,
        Segmented([{ label: 'Amount', value: 'amount' }, { label: 'Percent', value: 'percent' }],
          s.metric, function (v) { set('display_metric', v); })));
    } else if (_tab === 1) {  // Alerts
      box.appendChild(Row('Usage alerts', 'Notify when a provider crosses the threshold',
        Switch(s.alerts_enabled, function (v) { set('alerts_enabled', v); })));
      var val = h('span', { class: 't-label-l', style: { width: '44px', textAlign: 'right' } }, s.alert_threshold + '%');
      var slider = h('input', { type: 'range', min: '50', max: '99', value: String(s.alert_threshold), style: { flex: '1' } });
      slider.addEventListener('input', function () { val.textContent = slider.value + '%'; });
      slider.addEventListener('change', function () { set('alert_threshold', parseInt(slider.value, 10)); });
      box.appendChild(Row('Alert threshold', 'Percent of a limit before alerting',
        h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', minWidth: '180px' } }, slider, val)));
    } else if (_tab === 2) {  // Startup
      var sw = Switch(s.open_on_startup, function (v) {
        var a = api(); if (a) Promise.resolve(a.set_startup(v));
      }, !s.startup_supported);
      box.appendChild(Row('Open on startup',
        s.startup_supported ? 'Launch tokn when you sign in to Windows' : 'Only available on Windows', sw));
    } else {  // Data
      box.appendChild(Row('Estimated cost', 'Approx. spend over the last 30 days',
        Switch(s.show_cost, function (v) { set('show_cost', v); })));
      box.appendChild(Row('24h sparkline + burn-rate', 'Trend line on each card',
        Switch(s.show_sparkline, function (v) { set('show_sparkline', v); })));
      var exp = h('div', { style: { display: 'flex', gap: '10px', alignItems: 'center', paddingTop: '6px' } },
        h('button', { class: 'm3-btn tonal' }, 'Export JSON'),
        h('button', { class: 'm3-btn text' }, 'Export CSV'));
      var btns = exp.querySelectorAll('button');
      on(btns[0], function () { doExport('json', toast); });
      on(btns[1], function () { doExport('csv', toast); });
      box.appendChild(Row('Export usage', 'Write your ledger to a file', exp));
    }
    return box;
  }

  function doExport(fmt, toast) {
    var a = api(); if (!a) return;
    Promise.resolve(a.export(fmt)).then(function (path) {
      toast(path ? 'Saved to ' + path : 'Nothing to export');
    }).catch(function (e) { toast('Export failed: ' + e); });
  }

  function renderSettings(s) {
    applyTheme(s.resolved_theme || s.theme);
    var mount = document.getElementById('app');
    mount.innerHTML = '';

    var toastEl = h('div', { class: 't-body-s txt-variant', style: { padding: '0 20px 6px', minHeight: '18px' } }, '');
    function toast(msg) { toastEl.textContent = msg || ''; }

    var tabs = Tabs(['Display', 'Alerts', 'Startup', 'Data'], _tab, function (i) {
      _tab = i;
      renderSettings(s);  // simplest correct path: re-render with the new active tab
    });

    var card = h('div', { class: 'm3-card elev-3', style: { background: 'var(--s-high)', borderRadius: '28px', overflow: 'hidden' } },
      h('div', { style: { display: 'flex', alignItems: 'center', padding: '20px 20px 12px' } },
        h('span', { class: 't-headline-s', style: { flex: '1', fontWeight: '500' } }, 'Settings'),
        h('button', { class: 'm3-icon-btn', title: 'Close' }, mi('close'))),
      tabs, settingsBody(s, toast), toastEl);

    var closeBtn = card.querySelector('.m3-icon-btn');
    on(closeBtn, function () { var a = api(); if (a) a.close(); });

    var frame = h('div', { class: 'm3', style: { background: 'var(--surface)' } }, card);
    frame.setAttribute('data-theme', s.resolved_theme || s.theme || 'dark');
    mount.appendChild(frame);
  }

  /* ===================== boot ===================== */
  function showError(e) {
    var m = document.getElementById('app');
    if (m) m.textContent = 'tokn: ' + (e && e.message ? e.message : e);
  }

  function boot() {
    var a = api();
    if (!a) return;
    if (SCREEN === 'settings') {
      Promise.resolve(a.get_settings()).then(renderSettings).catch(showError);
    } else if (a.get_state) {
      Promise.resolve(a.get_state()).then(applyState).catch(showError);
    }
  }

  // Live push channel used by the Python refresh loop (dashboard/compact only).
  window.tokn = { update: applyState };

  if (window.pywebview && window.pywebview.api) boot();
  else window.addEventListener('pywebviewready', boot);
})();
