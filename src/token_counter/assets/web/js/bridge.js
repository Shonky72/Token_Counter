/* bridge.js — wires the bundled Material 3 screens to the Python app.

   The host page sets window.TOKN_SCREEN ('dashboard' | 'compact'). On load we
   ask Python (pywebview js_api) for the live state, point PARTS.DASH_DATA /
   PARTS.PROVIDERS at it, render the matching design builder, and attach the
   buttons to Api actions. Python pushes refreshes by calling window.tokn.update().
*/
(function () {
  'use strict';
  var SCREEN = window.TOKN_SCREEN || 'dashboard';

  function api() { return (window.pywebview && window.pywebview.api) || null; }

  function applyState(state) {
    if (!state) return;
    var theme = state.theme || 'dark';
    PARTS.DASH_DATA = state.cards || [];
    PARTS.PROVIDERS = state.providers || {};

    document.body.className = 'm3';
    document.body.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-theme', theme);

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
    // Footer is the frame's last child: [services-text, Accounts button].
    var footer = node.lastElementChild;
    if (footer) {
      var meta = state.meta || {};
      if (footer.firstElementChild && meta.services_line) {
        footer.firstElementChild.textContent = meta.services_line;
      }
      // "Accounts" (the only tonal button) -> open the login window.
      var accounts = footer.querySelector('.m3-btn.tonal');
      if (accounts && a) on(accounts, function () { a.open_login(); });
    }

    var cards = node.querySelectorAll('.m3-card.elevated');
    (state.cards || []).forEach(function (d, i) {
      var card = cards[i];
      if (!card) return;
      // Per-card refresh icon button.
      var refresh = card.querySelector('.m3-icon-btn');
      if (refresh && a) on(refresh, function (ev) { ev.stopPropagation(); a.refresh_one(d.key); });
      // Click the card to open the provider's usage/billing console.
      if (a && d.usage_url) {
        card.style.cursor = 'pointer';
        on(card, function () { a.open_usage(d.key); });
      }
      // Drop chips that have no data (no reset window / no input-output split).
      var chips = card.querySelectorAll('.m3-chip');
      if (!d.resets && chips[0]) chips[0].remove();
      if (!(d.inp || d.out) && chips.length && chips[chips.length - 1]) {
        chips[chips.length - 1].remove();
      }
    });
  }

  function on(el, fn) { el.addEventListener('click', fn); }

  function showError(e) {
    var m = document.getElementById('app');
    if (m) m.textContent = 'tokn: ' + (e && e.message ? e.message : e);
  }

  function boot() {
    var a = api();
    if (a && a.get_state) {
      Promise.resolve(a.get_state()).then(applyState).catch(showError);
    }
  }

  // Live push channel used by the Python refresh loop.
  window.tokn = { update: applyState };

  if (window.pywebview && window.pywebview.api) boot();
  else window.addEventListener('pywebviewready', boot);
})();
