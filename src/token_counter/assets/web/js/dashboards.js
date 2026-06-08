/* dashboards.js — three Material 3 dashboard directions.
   Vanilla port of dashboards.jsx. Each fn(theme) returns a DOM node.
   Depends on ui.js + parts.js. */
(function (global) {
  'use strict';
  var h = UI.h, mi = UI.mi;
  var P = PARTS;

  function Frame(theme, children, w, pad) {
    w = w || 412; pad = pad || 0;
    var frame = h('div', { class: 'm3', style: { width: w + 'px', padding: pad + 'px', background: 'var(--surface)', display: 'flex', flexDirection: 'column' } });
    frame.setAttribute('data-theme', theme);
    children.forEach(function (c) { if (c) frame.appendChild(c); });
    return frame;
  }

  function AppBar(trailing) {
    return h('div', { class: 'm3-appbar' },
      h('span', { class: 't-title-l title', style: { fontWeight: '500' } }, 'tokn'),
      h('span', { class: 't-label-s ver' }, 'v0.1.0'),
      trailing);
  }

  function settingsBtn(extraStyle) {
    return h('button', { class: 'm3-icon-btn', style: extraStyle || {} }, mi('settings'));
  }

  /* ============================================================
     V1 — Elevated cards (comfortable). Ring gauge headline.
     ============================================================ */
  function DashElevated(theme) {
    var PR = P.PROVIDERS[theme];
    var cards = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '12px', padding: '4px 16px 12px' } });
    P.DASH_DATA.forEach(function (d) {
      var p = PR[d.key];
      var lc = P.levelColor(d.pct);
      var card = h('div', { class: 'm3-card elevated elev-1', style: { padding: '16px', '--prov': p.gauge, '--prov-track': p.track } },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' } },
          P.Avatar(p, 40),
          h('div', { style: { flex: '1', minWidth: '0' } },
            h('div', { class: 't-title-m' }, p.name),
            h('div', { class: 't-body-s txt-variant' }, d.msgs)),
          P.Pulse(lc),
          h('button', { class: 'm3-icon-btn', style: { width: '32px', height: '32px', fontSize: '18px' } }, mi('refresh'))),
        h('div', { style: { display: 'flex', alignItems: 'center', gap: '16px' } },
          P.Ring({ pct: d.pct, size: 80, stroke: 8, color: p.gauge, label: d.pct + '%', sub: 'used' }),
          h('div', { style: { flex: '1', minWidth: '0' } },
            P.Flap(d.tokens, 17),
            h('div', { class: 't-label-m txt-variant', style: { marginTop: '4px', letterSpacing: '.5px' } }, 'TOKENS / MIN'),
            h('div', { style: { display: 'flex', gap: '6px', marginTop: '12px', flexWrap: 'wrap' } },
              h('span', { class: 'm3-chip' }, mi('schedule', { style: { fontSize: '15px' } }), 'Resets ' + d.resets),
              h('span', { class: 'm3-chip' }, '\u2191 ' + d.inp.split(' / ')[0] + ' \u00b7 \u2193 ' + d.out.split(' / ')[0])))));
      cards.appendChild(card);
    });
    var footer = h('div', { style: { display: 'flex', alignItems: 'center', padding: '4px 16px 16px', gap: '8px' } },
      h('span', { class: 't-body-s txt-variant', style: { flex: '1' } }, '3 services \u00b7 live within 30s'),
      h('button', { class: 'm3-btn tonal has-icon' }, mi('manage_accounts'), 'Accounts', h('span', { class: 'state' })));
    return Frame(theme, [AppBar(settingsBtn({ marginLeft: 'auto' })), cards, footer]);
  }

  /* ============================================================
     V2 — Filled tonal list (compact). Linear gauges, dense rows.
     ============================================================ */
  function DashList(theme) {
    var PR = P.PROVIDERS[theme];
    var seg = h('div', { style: { padding: '0 16px 10px' } },
      h('div', { class: 'm3-seg' },
        h('button', { class: 'sel' }, mi('data_usage'), 'Used'),
        h('button', {}, 'Remaining')));
    var rows = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '8px', padding: '0 16px 12px' } });
    P.DASH_DATA.forEach(function (d) {
      var p = PR[d.key];
      var lc = P.levelColor(d.pct);
      rows.appendChild(h('div', { class: 'm3-card filled', style: { padding: '12px 14px', '--prov': p.gauge, '--prov-track': p.track } },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px' } },
          P.Avatar(p, 30, 16),
          h('div', { style: { flex: '1', minWidth: '0' } }, h('div', { class: 't-title-s' }, p.name)),
          P.Pulse(lc),
          h('div', { style: { textAlign: 'right' } }, P.Flap(d.tokens, 13)),
          h('span', { class: 't-title-s', style: { width: '38px', textAlign: 'right', color: lc } }, d.pct + '%')),
        h('div', { style: { marginTop: '10px' } }, P.Linear(d.pct, p.gauge)),
        h('div', { style: { display: 'flex', marginTop: '7px' } },
          h('span', { class: 't-body-s txt-variant', style: { flex: '1' } }, '\u2191 ' + d.inp + ' \u00b7 \u2193 ' + d.out),
          h('span', { class: 't-body-s txt-variant' }, 'resets ' + d.resets))));
    });
    var footer = h('div', { style: { display: 'flex', alignItems: 'center', padding: '0 12px 14px' } },
      h('button', { class: 'm3-btn text has-icon' }, mi('add'), 'Add a service', h('span', { class: 'state' })),
      h('button', { class: 'm3-btn text', style: { marginLeft: 'auto' } }, 'Accounts', h('span', { class: 'state' })));
    return Frame(theme, [AppBar(settingsBtn({ marginLeft: 'auto' })), seg, rows, footer]);
  }

  /* ============================================================
     V3 — Expressive (bold/spacious). Hero card + big shapes.
     ============================================================ */
  function DashExpressive(theme) {
    var PR = P.PROVIDERS[theme];
    var hero = P.DASH_DATA[1];
    var rest = [P.DASH_DATA[0], P.DASH_DATA[2]];
    var hp = PR[hero.key];

    var head = h('div', { style: { padding: '16px 20px 6px', display: 'flex', alignItems: 'baseline', gap: '10px' } },
      h('span', { class: 't-headline-s', style: { fontWeight: '500' } }, 'tokn'),
      h('span', { class: 't-body-s txt-variant', style: { flex: '1' } }, 'live API limits'),
      h('button', { class: 'm3-icon-btn' }, mi('settings')));

    var heroAvatarP = Object.assign({}, hp, { container: 'color-mix(in srgb,' + hp.onContainer + ' 16%, transparent)' });
    var heroCard = h('div', { style: { padding: '6px 16px 10px' } },
      h('div', { class: 'm3-card', style: { background: hp.container, borderRadius: '28px', padding: '20px', '--prov-track': 'color-mix(in srgb, ' + hp.onContainer + ' 22%, transparent)' } },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' } },
          P.Avatar(heroAvatarP, 36, 20),
          h('span', { class: 't-title-m', style: { color: hp.onContainer, fontWeight: '600', flex: '1' } }, hp.name),
          h('span', { style: { display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 14px', borderRadius: '999px', background: 'color-mix(in srgb,' + hp.onContainer + ' 16%, transparent)', color: hp.onContainer, fontSize: '12px', fontWeight: '600' } },
            mi('schedule', { style: { fontSize: '15px' } }), 'Resets ' + hero.resets)),
        h('div', { style: { display: 'flex', alignItems: 'center', gap: '18px', marginTop: '8px' } },
          P.Ring({ pct: hero.pct, size: 118, stroke: 11, color: hp.onContainer, label: hero.pct + '%', sub: 'used' }),
          h('div', { style: { flex: '1', minWidth: '0' } },
            h('div', { style: { color: hp.onContainer } }, P.Flap(hero.tokens, 22, 3)),
            h('div', { style: { color: hp.onContainer, opacity: '.85', fontSize: '12px', fontWeight: '600', letterSpacing: '.6px', marginTop: '8px' } }, 'TOKENS / MIN \u00b7 ' + hero.rate)))));

    var restWrap = h('div', { style: { display: 'flex', flexDirection: 'column', gap: '10px', padding: '0 16px 12px' } });
    rest.forEach(function (d) {
      var p = PR[d.key];
      var lc = P.levelColor(d.pct);
      restWrap.appendChild(h('div', { class: 'm3-card filled', style: { borderRadius: '24px', padding: '18px' } },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: '12px' } },
          P.Avatar(p, 36, 20),
          h('div', { style: { flex: '1', minWidth: '0' } },
            h('div', { class: 't-title-m' }, p.name),
            h('div', { class: 't-body-s txt-variant' }, 'resets ' + d.resets + ' \u00b7 ' + d.rate)),
          h('div', { style: { textAlign: 'right' } },
            P.Flap(d.tokens, 16),
            h('div', { class: 't-label-m', style: { color: lc, marginTop: '3px' } }, d.pct + '% used'))),
        h('div', { style: { marginTop: '14px' } }, P.WavyBar(d.pct, p.gauge, p.track))));
    });

    var fab = h('div', { style: { padding: '2px 16px 18px' } },
      h('button', { class: 'm3-fab', style: { width: '100%', justifyContent: 'center' } }, mi('add'), 'Add a service'));

    return Frame(theme, [head, heroCard, restWrap, fab]);
  }

  global.DASHBOARDS = { DashElevated: DashElevated, DashList: DashList, DashExpressive: DashExpressive };
})(window);
