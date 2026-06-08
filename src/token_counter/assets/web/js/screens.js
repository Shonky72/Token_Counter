/* screens.js — Compact tray popup, Login/Accounts, Settings dialog, Tray menu.
   Vanilla port of screens.jsx. Each fn(theme) returns a DOM node.
   Depends on ui.js + parts.js. */
(function (global) {
  'use strict';
  var h = UI.h, mi = UI.mi;
  var P = PARTS;

  function frame(theme, w, extra, children) {
    var o = { class: 'm3', style: Object.assign({ width: w + 'px' }, extra || {}) };
    var f = h('div', o);
    f.setAttribute('data-theme', theme);
    (children || []).forEach(function (c) { if (c) f.appendChild(c); });
    return f;
  }

  /* ============================================================
     Compact tray popup
     ============================================================ */
  function CompactPopup(theme) {
    var PR = P.PROVIDERS[theme];
    var list = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '11px' } });
    P.DASH_DATA.forEach(function (d) {
      var p = PR[d.key];
      var lc = P.levelColor(d.pct);
      list.appendChild(h('div', { style: { display: 'flex', alignItems: 'center', gap: '9px' } },
        P.Avatar(p, 22, 13),
        h('span', { class: 't-title-s', style: { flex: '1' } }, p.name),
        P.Flap(d.tokens, 11),
        h('span', { class: 't-label-m', style: { width: '34px', textAlign: 'right', color: lc } }, d.pct + '%')));
    });
    var card = h('div', { class: 'm3-card elev-3', style: { background: 'var(--s-container)', borderRadius: '16px', padding: '12px 14px' } },
      h('div', { style: { display: 'flex', alignItems: 'center', marginBottom: '10px' } },
        h('span', { class: 't-label-m txt-variant', style: { flex: '1', letterSpacing: '.8px' } }, 'TOKN'),
        mi('keep', { style: { fontSize: '18px' } })),
      list);
    card.querySelector('.mi').classList.add('txt-variant');
    return frame(theme, 296, null, [card]);
  }

  /* ============================================================
     Login / Accounts
     ============================================================ */
  function FakeSelect(value) {
    return h('div', { style: { position: 'relative', minWidth: '220px' } },
      h('div', { style: { height: '48px', borderRadius: '8px', border: '1px solid var(--outline)', display: 'flex', alignItems: 'center', padding: '0 12px', gap: '8px', background: 'var(--surface)' } },
        h('span', { class: 't-body-l', style: { flex: '1' } }, value),
        mi('arrow_drop_down', { style: { color: 'var(--on-surface-variant)' } })),
      h('span', { style: { position: 'absolute', top: '-8px', left: '10px', fontSize: '12px', padding: '0 4px', background: 'var(--surface)', color: 'var(--on-surface-variant)' } }, 'Add a service'));
  }

  function LoginScreen(theme) {
    var PR = P.PROVIDERS[theme];
    var rows = [
      { key: 'claude', state: 'live' },
      { key: 'openai', state: 'entering' },
      { key: 'gemini', state: 'empty' },
    ];
    var rowsWrap = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '12px', padding: '16px 24px 22px' } });
    rows.forEach(function (r) {
      var p = PR[r.key];
      var head = h('div', { style: { display: 'flex', alignItems: 'center', gap: '12px' } },
        P.Avatar(p, 40),
        h('div', { style: { flex: '1' } },
          h('div', { class: 't-title-m' }, p.name),
          h('div', { class: 't-body-s txt-variant' }, 'Developer API key')),
        r.state === 'live' ? h('span', { class: 'm3-chip tonal' }, mi('check_circle', { style: { fontSize: '16px' } }), 'Live limits loaded') : null,
        h('button', { class: 'm3-icon-btn', style: { width: '36px', height: '36px', fontSize: '20px' } }, mi('info')));

      var card = h('div', { class: 'm3-card outlined', style: { padding: '16px', borderRadius: '16px' } }, head);

      if (r.state !== 'empty') {
        var field = h('div', { class: 'm3-field' + (r.state === 'entering' ? ' focus' : ''), style: { flex: '1' } },
          h('span', { class: 'lbl' }, 'API key'),
          h('input', { readonly: 'readonly', value: r.state === 'live' ? '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u20223a9F' : 'sk-\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022', style: { paddingTop: '16px' } }));
        card.appendChild(h('div', { style: { display: 'flex', alignItems: 'flex-end', gap: '12px', marginTop: '14px' } },
          field,
          h('button', { class: 'm3-btn tonal' }, r.state === 'live' ? 'Re-validate' : 'Validate & Save', h('span', { class: 'state' })),
          h('button', { class: 'm3-btn text' }, 'Remove', h('span', { class: 'state' }))));
      } else {
        card.appendChild(h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', marginTop: '12px' } },
          h('span', { class: 't-body-s txt-variant', style: { flex: '1' } }, 'Gemini has no live API limits \u2014 tracks usage you report against an allowance.'),
          h('button', { class: 'm3-btn outlined has-icon' }, mi('vpn_key'), 'Add key', h('span', { class: 'state' }))));
      }
      rowsWrap.appendChild(card);
    });

    return frame(theme, 720, { background: 'var(--surface)' }, [
      h('div', { style: { padding: '20px 24px 8px' } },
        h('div', { class: 't-headline-s', style: { fontWeight: '500' } }, 'Accounts'),
        h('div', { class: 't-body-m txt-variant', style: { marginTop: '4px' } },
          'Sign in to your AI services with developer API keys. Stored securely via Windows Credential Manager.')),
      h('div', { style: { display: 'flex', alignItems: 'center', gap: '12px', padding: '14px 24px' } },
        FakeSelect('ChatGPT'),
        h('button', { class: 'm3-btn filled has-icon' }, mi('add'), 'Add', h('span', { class: 'state' }))),
      h('div', { style: { height: '1px', background: 'var(--outline-variant)', margin: '0 24px' } }),
      rowsWrap,
    ]);
  }

  /* ============================================================
     Settings dialog
     ============================================================ */
  function Tabs(items, active) {
    var wrap = h('div', { style: { display: 'flex', borderBottom: '1px solid var(--outline-variant)' } });
    items.forEach(function (t, i) {
      wrap.appendChild(h('div', { style: { flex: '1', textAlign: 'center', padding: '14px 0 12px', position: 'relative', fontSize: '14px', fontWeight: '500', color: i === active ? 'var(--primary)' : 'var(--on-surface-variant)' } },
        t,
        i === active ? h('span', { style: { position: 'absolute', bottom: '0', left: '50%', transform: 'translateX(-50%)', width: 'calc(100% - 24px)', height: '3px', borderRadius: '3px 3px 0 0', background: 'var(--primary)' } }) : null));
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

  function FakeMini(value) {
    return h('div', { style: { height: '40px', borderRadius: '8px', border: '1px solid var(--outline)', minWidth: '130px', display: 'flex', alignItems: 'center', padding: '0 12px', gap: '8px' } },
      h('span', { class: 't-body-m', style: { flex: '1' } }, value),
      mi('arrow_drop_down', { style: { fontSize: '20px', color: 'var(--on-surface-variant)' } }));
  }

  function seg(a, b) {
    return h('div', { class: 'm3-seg' }, h('button', { class: 'sel' }, a), h('button', {}, b));
  }
  function sw() { return h('div', { class: 'm3-switch on' }, h('span', { class: 'knob' })); }

  function SettingsDialog(theme) {
    var body = h('div', { style: { padding: '8px 20px 4px' } },
      Row('Theme', 'Match the OS or pick one', FakeMini('System')),
      Row('Show', null, seg('Used', 'Remaining')),
      Row('As', null, seg('Amount', 'Percent')),
      h('div', { style: { height: '1px', background: 'var(--outline-variant)', margin: '6px 0' } }),
      Row('Estimated cost', 'Approx. spend over the last 30 days', sw()),
      Row('24h sparkline + burn-rate', 'Trend line on each card', sw()));

    var card = h('div', { class: 'm3-card elev-3', style: { background: 'var(--s-high)', borderRadius: '28px', overflow: 'hidden' } },
      h('div', { style: { display: 'flex', alignItems: 'center', padding: '20px 20px 12px' } },
        h('span', { class: 't-headline-s', style: { flex: '1', fontWeight: '500' } }, 'Settings'),
        h('button', { class: 'm3-icon-btn' }, mi('close'))),
      Tabs(['Display', 'Alerts', 'Startup', 'Data'], 0),
      body,
      h('div', { style: { display: 'flex', justifyContent: 'flex-end', padding: '8px 18px 18px' } },
        h('button', { class: 'm3-btn text' }, 'Close', h('span', { class: 'state' }))));
    return frame(theme, 460, null, [card]);
  }

  /* ============================================================
     Tray icon states + right-click menu
     ============================================================ */
  function TrayMenu(theme) {
    var states = [{ p: 32, t: 'OK' }, { p: 70, t: 'Busy' }, { p: 92, t: 'Near limit' }];
    var icons = h('div', { style: { display: 'flex', alignItems: 'flex-end', gap: '18px' } });
    states.forEach(function (st) {
      icons.appendChild(h('div', { style: { textAlign: 'center' } },
        P.TrayIcon(st.p, 44),
        h('div', { class: 't-label-s txt-variant', style: { marginTop: '6px' } }, st.t + ' \u00b7 ' + st.p + '%')));
    });
    function item(icon, label, trail, fill, color) {
      return h('div', { class: 'item' },
        mi(icon, { fill: !!fill, style: color ? { color: color } : null }),
        label,
        trail ? h('span', { class: 'trail' }, trail) : null);
    }
    var menu = h('div', { class: 'm3-menu', style: { width: '100%' } },
      item('dashboard', 'Open dashboard'),
      item('view_compact', 'Compact view'),
      item('manage_accounts', 'Accounts / Login\u2026'),
      h('div', { class: 'divider' }),
      item('check_box', 'Open on startup', null, true, 'var(--primary)'),
      item('refresh', 'Refresh now', '30s'),
      h('div', { class: 'divider' }),
      item('power_settings_new', 'Quit'));
    return frame(theme, 360, { padding: '24px', background: 'var(--background)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '22px' }, [icons, menu]);
  }

  global.SCREENS = { CompactPopup: CompactPopup, LoginScreen: LoginScreen, SettingsDialog: SettingsDialog, TrayMenu: TrayMenu };
})(window);
