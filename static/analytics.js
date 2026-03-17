/**
 * Menu Maker — PostHog Analytics (MVP)
 *
 * Events: section_viewed, section_dwell, scroll_depth, cta_click,
 *         accordion_toggled, profile_edit_started, profile_saved,
 *         advice_generated, advice_result_viewed, card_added,
 *         content_copied, content_pasted
 */
(function () {
  'use strict';

  var CFG = window.MM_ANALYTICS;
  if (!CFG || !CFG.posthogKey) return;

  /* ── 1. PostHog init ─────────────────────────────────────────── */
  !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey getNextSurveyStep identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing debug".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);

  posthog.init(CFG.posthogKey, {
    api_host: 'https://eu.i.posthog.com',
    autocapture: false,
    capture_pageview: true,
    capture_pageleave: true,
    disable_session_recording: false,
    session_recording: {
      maskAllInputs: true,
      maskTextSelector: 'textarea, .api-key, .waardepropositie, .samenvatting-text, .impact-text, .anders-input',
      blockSelector: '.sensitive-data'
    },
    persistence: 'localStorage'
  });

  /* ── Identify (functioneel, geen PII) ────────────────────────── */
  if (CFG.orgId) {
    posthog.identify('org_' + CFG.orgId + '_' + (CFG.userId || 'anon'), {
      user_type: CFG.userType || 'stakeholder',
      restaurant_name: CFG.orgName || '',
      organisation_id: CFG.orgId
    });
  }

  var PAGE_NAME = CFG.pageName || '';

  /* ── 2. Idle detection ───────────────────────────────────────── */
  var IDLE_TIMEOUT = 60000; // 60s
  var lastActivity = Date.now();
  var isIdle = false;

  function onActivity() {
    lastActivity = Date.now();
    if (isIdle) {
      isIdle = false;
      resumeDwellTimers();
    }
  }

  document.addEventListener('mousemove', onActivity, { passive: true });
  document.addEventListener('keydown', onActivity, { passive: true });
  document.addEventListener('scroll', onActivity, { passive: true });
  document.addEventListener('touchstart', onActivity, { passive: true });

  setInterval(function () {
    if (!isIdle && Date.now() - lastActivity > IDLE_TIMEOUT) {
      isIdle = true;
      pauseDwellTimers();
    }
  }, 5000);

  /* ── 3. Visibility tracking ──────────────────────────────────── */
  var isVisible = !document.hidden;

  document.addEventListener('visibilitychange', function () {
    isVisible = !document.hidden;
    if (!isVisible) {
      flushAllDwells(false);
    } else if (!isIdle) {
      resumeDwellTimers();
    }
  });

  /* ── 4. Section observer ─────────────────────────────────────── */
  var sectionState = {}; // key: sectionName → { startTime, active, viewed, flushed }

  function getSectionName(el) {
    return el.getAttribute('data-section') || '';
  }

  function startDwell(name) {
    var s = sectionState[name];
    if (!s) return;
    if (!s.active) {
      s.startTime = Date.now();
      s.active = true;
      s.flushed = false;
    }
  }

  function stopDwell(name, wasActive) {
    var s = sectionState[name];
    if (!s || !s.active || s.flushed) return;
    var elapsed = (Date.now() - s.startTime) / 1000;
    s.active = false;
    s.flushed = true;
    if (elapsed >= 2) {
      posthog.capture('section_dwell', {
        page_name: PAGE_NAME,
        section_name: name,
        dwell_time_s: Math.round(elapsed * 10) / 10,
        was_active: wasActive !== false
      });
    }
  }

  function pauseDwellTimers() {
    Object.keys(sectionState).forEach(function (name) {
      var s = sectionState[name];
      if (s.active) stopDwell(name, false);
    });
  }

  function resumeDwellTimers() {
    Object.keys(sectionState).forEach(function (name) {
      var s = sectionState[name];
      if (s.inViewport && isVisible && !isIdle) {
        startDwell(name);
      }
    });
  }

  function flushAllDwells(wasActive) {
    Object.keys(sectionState).forEach(function (name) {
      if (sectionState[name].active) stopDwell(name, wasActive);
    });
  }

  // pagehide + beforeunload as fallback flush
  window.addEventListener('pagehide', function () { flushAllDwells(true); });
  window.addEventListener('beforeunload', function () { flushAllDwells(true); });

  // IntersectionObserver
  var viewTimers = {}; // sectionName → timeout for 1s viewed threshold

  function initSectionObserver() {
    var sections = document.querySelectorAll('[data-section]');
    if (!sections.length) return;

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var name = getSectionName(entry.target);
        if (!name) return;

        if (!sectionState[name]) {
          sectionState[name] = { startTime: 0, active: false, viewed: false, flushed: false, inViewport: false };
        }
        var s = sectionState[name];

        if (entry.isIntersecting) {
          s.inViewport = true;

          // section_viewed after 1s visible
          if (!s.viewed) {
            viewTimers[name] = setTimeout(function () {
              s.viewed = true;
              posthog.capture('section_viewed', {
                page_name: PAGE_NAME,
                section_name: name
              });
            }, 1000);
          }

          // Start dwell if conditions met
          if (isVisible && !isIdle) {
            startDwell(name);
          }
        } else {
          s.inViewport = false;
          if (viewTimers[name]) {
            clearTimeout(viewTimers[name]);
            delete viewTimers[name];
          }
          if (s.active) stopDwell(name, true);
        }
      });
    }, { threshold: 0.5 });

    sections.forEach(function (el) { observer.observe(el); });
  }

  /* ── 5. Scroll depth ─────────────────────────────────────────── */
  var scrollMilestones = {};

  function trackScrollDepth() {
    var scrollTop = window.scrollY || window.pageYOffset;
    var docHeight = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
    var winHeight = window.innerHeight;
    if (docHeight <= winHeight) return; // no scrollable content

    var pct = Math.round(((scrollTop + winHeight) / docHeight) * 100);
    [25, 50, 75, 100].forEach(function (milestone) {
      if (pct >= milestone && !scrollMilestones[milestone]) {
        scrollMilestones[milestone] = true;
        posthog.capture('scroll_depth', {
          page_name: PAGE_NAME,
          depth_percent: milestone
        });
      }
    });
  }

  document.addEventListener('scroll', debounce(trackScrollDepth, 200), { passive: true });

  /* ── 6. CTA tracking ─────────────────────────────────────────── */
  document.addEventListener('click', function (e) {
    // data-track
    var trackEl = e.target.closest('[data-track]');
    if (trackEl) {
      var targetName = trackEl.getAttribute('data-track');
      var sectionEl = trackEl.closest('[data-section]');
      var sectionName = sectionEl ? sectionEl.getAttribute('data-section') : null;

      posthog.capture('cta_click', {
        page_name: PAGE_NAME,
        section_name: sectionName,
        target_name: targetName
      });

      // Specific events for known actions
      if (targetName === 'profiel_bewerken') {
        posthog.capture('profile_edit_started', { page_name: PAGE_NAME });
      }
    }

    // data-accordion
    var accordionEl = e.target.closest('[data-accordion]');
    if (accordionEl) {
      var accName = accordionEl.getAttribute('data-accordion');
      // Determine open/close by checking the body state after click
      setTimeout(function () {
        var body = accordionEl.nextElementSibling || accordionEl.parentElement.querySelector('.kaart-body');
        var isOpen = body && body.classList.contains('open');
        posthog.capture('accordion_toggled', {
          page_name: PAGE_NAME,
          section_name: accName,
          action: isOpen ? 'open' : 'close'
        });
      }, 50);
    }
  });

  /* ── 7. Form tracking (profile_saved, advice_generated, card_added) ── */
  document.addEventListener('submit', function (e) {
    var form = e.target;

    // Profile saved
    if (form.id === 'segmentForm') {
      var changed = form.querySelectorAll('input:checked, textarea').length;
      posthog.capture('profile_saved', {
        page_name: PAGE_NAME,
        fields_changed: changed
      });
    }

    // Advice generated
    if (form.id === 'builderForm') {
      var doelEl = form.querySelector('input[name="doel"]:checked');
      var focusEl = form.querySelector('input[name="focus_type"]:checked');
      posthog.capture('advice_generated', {
        page_name: PAGE_NAME,
        target_name: doelEl ? doelEl.value : '',
        focus_type: focusEl ? focusEl.value : ''
      });
    }
  });

  /* ── 8. Copy/paste (scoped) ──────────────────────────────────── */
  var COPY_PAGES = ['segment.segment_overzicht', 'voorstel.voorstel_resultaat', 'voorstel.ontwerpruimte'];
  var PASTE_PAGES = ['segment.segment_bewerken', 'voorstel.ontwerpruimte'];

  function getNearestSection(node) {
    var el = node.nodeType === 3 ? node.parentElement : node;
    var sec = el ? el.closest('[data-section]') : null;
    return sec ? sec.getAttribute('data-section') : null;
  }

  if (COPY_PAGES.indexOf(PAGE_NAME) !== -1) {
    document.addEventListener('copy', function () {
      var sel = document.getSelection();
      posthog.capture('content_copied', {
        page_name: PAGE_NAME,
        section_name: sel && sel.anchorNode ? getNearestSection(sel.anchorNode) : null
      });
    });
  }

  if (PASTE_PAGES.indexOf(PAGE_NAME) !== -1) {
    document.addEventListener('paste', function (e) {
      var t = e.target;
      if (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA') {
        posthog.capture('content_pasted', {
          page_name: PAGE_NAME,
          section_name: getNearestSection(t),
          target_name: t.name || t.id || null
        });
      }
    });
  }

  /* ── 9. advice_result_viewed (on voorstel_resultaat page) ────── */
  if (PAGE_NAME === 'voorstel.voorstel_resultaat') {
    var resultMeta = document.querySelector('.result-meta');
    var stats = document.querySelectorAll('.stat-item');
    posthog.capture('advice_result_viewed', {
      page_name: PAGE_NAME,
      target_name: CFG.resultGoal || '',
      result_count: document.querySelectorAll('.annot-card, .voorstel-card').length
    });
  }

  /* ── Utility ─────────────────────────────────────────────────── */
  function debounce(fn, ms) {
    var timer;
    return function () {
      clearTimeout(timer);
      timer = setTimeout(fn, ms);
    };
  }

  /* ── Init ─────────────────────────────────────────────────────── */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSectionObserver);
  } else {
    initSectionObserver();
  }
})();
