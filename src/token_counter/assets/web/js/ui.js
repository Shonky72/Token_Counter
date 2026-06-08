/* ui.js — tiny DOM helpers used by every screen module.
   Replaces JSX with plain function calls. No build step, no deps. */
(function (global) {
  'use strict';

  function setStyle(el, style) {
    for (var k in style) {
      var v = style[k];
      if (v == null) continue;
      if (k.charAt(0) === '-' && k.charAt(1) === '-') el.style.setProperty(k, v);
      else el.style[k] = v;
    }
  }

  // h('div', {class, style, title, on:{click}, ...attrs}, ...children)
  function h(tag, props) {
    var el = document.createElement(tag);
    if (props) {
      for (var k in props) {
        var v = props[k];
        if (v == null) continue;
        if (k === 'class') el.className = v;
        else if (k === 'style') setStyle(el, v);
        else if (k === 'on' && typeof v === 'object') { for (var ev in v) el.addEventListener(ev, v[ev]); }
        else el.setAttribute(k, v);
      }
    }
    for (var i = 2; i < arguments.length; i++) append(el, arguments[i]);
    return el;
  }

  function append(el, kid) {
    if (kid == null || kid === false) return;
    if (Array.isArray(kid)) { kid.forEach(function (k) { append(el, k); }); return; }
    el.appendChild(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }

  var NS = 'http://www.w3.org/2000/svg';
  function s(tag, attrs) {
    var el = document.createElementNS(NS, tag);
    if (attrs) for (var k in attrs) if (attrs[k] != null) el.setAttribute(k, attrs[k]);
    for (var i = 2; i < arguments.length; i++) if (arguments[i]) el.appendChild(arguments[i]);
    return el;
  }

  // material symbol span
  function mi(name, props) {
    props = props || {};
    var cls = 'mi' + (props.fill ? ' fill' : '');
    var o = { class: cls };
    if (props.style) o.style = props.style;
    return h('span', o, name);
  }

  global.UI = { h: h, s: s, mi: mi, setStyle: setStyle, append: append };
})(window);
