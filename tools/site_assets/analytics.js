/* Yaaddi website analytics: Google Analytics 4, loaded only after the visitor accepts.
 *
 * To turn it on, put your GA4 Measurement ID in GA_ID below (looks like G-XXXXXXXXXX).
 * While GA_ID is empty this file does nothing: no banner, no cookies, no requests.
 *
 * Privacy behavior
 *  - Nothing is sent to Google, and no Google script is loaded, until the visitor clicks Accept.
 *  - Do Not Track and Global Privacy Control are honored as "decline" (no banner is shown).
 *  - Consent Mode v2 signals are all "denied" except analytics_storage after Accept.
 *  - Google signals and ad personalization are disabled. No advertising features are used.
 *  - The choice is kept in localStorage and can be changed from the Website privacy page.
 */
(function () {
  'use strict';

  var GA_ID = 'G-GCZRE4EFW1'; // e.g. 'G-ABC123DEF4'
  var STORAGE_KEY = 'yaaddi-analytics-consent';

  if (!/^G-[A-Z0-9]{6,}$/.test(GA_ID)) return;

  var doc = document;
  var win = window;
  var privacyUrl = (doc.currentScript && doc.currentScript.getAttribute('data-privacy')) || '/privacy/';

  function readChoice() {
    try { return win.localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
  }
  function saveChoice(value) {
    try { win.localStorage.setItem(STORAGE_KEY, value); } catch (e) { /* private mode: choice lasts for this page only */ }
  }

  function privacySignal() {
    return navigator.doNotTrack === '1' || win.doNotTrack === '1' || navigator.globalPrivacyControl === true;
  }

  win.dataLayer = win.dataLayer || [];
  function gtag() { win.dataLayer.push(arguments); }
  win.gtag = win.gtag || gtag;

  gtag('consent', 'default', {
    analytics_storage: 'denied',
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
  });

  var loaded = false;
  function enable() {
    gtag('consent', 'update', { analytics_storage: 'granted' });
    if (loaded) return;
    loaded = true;
    var s = doc.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(GA_ID);
    doc.head.appendChild(s);
    gtag('js', new Date());
    gtag('config', GA_ID, { allow_google_signals: false, allow_ad_personalization_signals: false });
  }

  function disable() {
    gtag('consent', 'update', { analytics_storage: 'denied' });
    // Remove the Google Analytics cookies that were set while the visitor had accepted.
    var host = location.hostname;
    var domains = [host, '.' + host, '.' + host.split('.').slice(-2).join('.')];
    doc.cookie.split(';').forEach(function (c) {
      var name = c.split('=')[0].trim();
      if (name === '_ga' || name.indexOf('_ga_') === 0 || name === '_gid') {
        domains.forEach(function (d) {
          doc.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=' + d;
        });
        doc.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
      }
    });
  }

  /* Events: only after consent. Names are lowercase snake_case; no personal data is attached. */
  function trackClick(event) {
    if (readChoice() !== 'granted' || typeof event.target.closest !== 'function') return;
    var link = event.target.closest('a[href]');
    if (!link) return;
    var href = link.getAttribute('href');
    var where = link.getAttribute('data-where') || 'page';
    if (href.indexOf('play.google.com') !== -1) gtag('event', 'play_store_click', { link_location: where });
    else if (href.indexOf('courses.yaaddi.com') !== -1) gtag('event', 'courses_site_click', { link_location: where });
    else if (href.indexOf('mailto:') === 0) gtag('event', 'support_email_click', { link_location: where });
  }

  /* Banner */
  var banner = null;
  function closeBanner() {
    if (banner && banner.parentNode) banner.parentNode.removeChild(banner);
    banner = null;
  }
  function choose(value) {
    saveChoice(value);
    closeBanner();
    if (value === 'granted') enable(); else disable();
    syncSettingsControls();
  }
  function el(tag, attrs, text) {
    var node = doc.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    if (text) node.textContent = text;
    return node;
  }
  function showBanner() {
    if (banner) return;
    banner = el('section', { class: 'consent', 'aria-label': 'Analytics choice' });
    var text = el('p', { class: 'consent-text' }, 'Do you accept cookies? ');
    var more = el('a', { href: privacyUrl }, 'Details');
    text.appendChild(more);
    var buttons = el('div', { class: 'consent-buttons' });
    var decline = el('button', { type: 'button', class: 'btn btn-small btn-ghost' }, 'Decline');
    var accept = el('button', { type: 'button', class: 'btn btn-small' }, 'Accept');
    decline.addEventListener('click', function () { choose('denied'); });
    accept.addEventListener('click', function () { choose('granted'); });
    buttons.appendChild(decline);
    buttons.appendChild(accept);
    banner.appendChild(text);
    banner.appendChild(buttons);
    doc.body.appendChild(banner);
  }

  /* Elements with data-consent-settings: shown only when analytics is configured, reopen the banner. */
  function syncSettingsControls() {
    var state = readChoice() === 'granted' ? 'accepted' : 'declined';
    doc.querySelectorAll('[data-consent-status]').forEach(function (n) {
      n.textContent = privacySignal() && readChoice() === null ? 'declined (your browser sends a privacy signal)' : state;
    });
  }
  function wireSettingsControls() {
    doc.querySelectorAll('[data-consent-settings]').forEach(function (n) {
      n.hidden = false;
      n.addEventListener('click', function (e) { e.preventDefault(); showBanner(); });
    });
    syncSettingsControls();
  }

  function start() {
    doc.addEventListener('click', trackClick);
    wireSettingsControls();
    var choice = readChoice();
    if (choice === 'granted') enable();
    else if (choice === null && !privacySignal()) showBanner();
  }

  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', start); else start();
})();
