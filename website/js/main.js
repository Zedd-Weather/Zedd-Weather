/* =========================================================================
   Zedd Weather — project site interactions
   Dependency-free vanilla JS: nav, tabs, scroll reveal, progress bar.
   ========================================================================= */

(function () {
  'use strict';

  var prefersReducedMotion = window.matchMedia(
    '(prefers-reduced-motion: reduce)'
  ).matches;

  /* ---------------------------------------------------------------------
     Mobile nav toggle
  --------------------------------------------------------------------- */
  var navToggle = document.getElementById('nav-toggle');
  var siteNav = document.getElementById('site-nav');

  function closeNav() {
    if (!siteNav) return;
    siteNav.classList.remove('open');
    if (navToggle) navToggle.setAttribute('aria-expanded', 'false');
  }

  if (navToggle && siteNav) {
    navToggle.addEventListener('click', function () {
      var isOpen = siteNav.classList.toggle('open');
      navToggle.setAttribute('aria-expanded', String(isOpen));
    });

    // Close the drawer when a link is clicked.
    siteNav.addEventListener('click', function (e) {
      if (e.target && e.target.tagName === 'A') closeNav();
    });

    // Close on Escape.
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeNav();
    });

    // Close when resizing past the mobile breakpoint.
    window.addEventListener('resize', function () {
      if (window.innerWidth > 760) closeNav();
    });
  }

  /* ---------------------------------------------------------------------
     Sector tabs
  --------------------------------------------------------------------- */
  var tabRoot = document.querySelector('[data-tabs]');
  if (tabRoot) {
    var tabButtons = Array.prototype.slice.call(
      tabRoot.querySelectorAll('.tab-btn')
    );
    var tabPanels = Array.prototype.slice.call(
      tabRoot.querySelectorAll('.tab-panel')
    );

    function activateTab(id) {
      tabButtons.forEach(function (btn) {
        var isActive = btn.getAttribute('data-tab') === id;
        btn.classList.toggle('is-active', isActive);
        btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
      });
      tabPanels.forEach(function (panel) {
        panel.classList.toggle(
          'is-active',
          panel.getAttribute('data-panel') === id
        );
      });
    }

    tabButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        activateTab(btn.getAttribute('data-tab'));
      });
    });

    // Keyboard support (arrow left/right within the tablist).
    tabRoot.querySelector('.tab-list').addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      var idx = tabButtons.findIndex(function (b) {
        return b.classList.contains('is-active');
      });
      if (idx === -1) return;
      var next =
        e.key === 'ArrowRight'
          ? (idx + 1) % tabButtons.length
          : (idx - 1 + tabButtons.length) % tabButtons.length;
      tabButtons[next].focus();
      activateTab(tabButtons[next].getAttribute('data-tab'));
    });
  }

  /* ---------------------------------------------------------------------
     Scroll reveal
  --------------------------------------------------------------------- */
  var revealEls = Array.prototype.slice.call(
    document.querySelectorAll('.reveal')
  );

  if (!prefersReducedMotion && 'IntersectionObserver' in window) {
    var revealObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('in-view');
            revealObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );

    revealEls.forEach(function (el) {
      revealObserver.observe(el);
    });
  } else {
    revealEls.forEach(function (el) {
      el.classList.add('in-view');
    });
  }

  /* ---------------------------------------------------------------------
     Progress bar + to-top + header shadow
  --------------------------------------------------------------------- */
  var progress = document.getElementById('progress');
  var toTop = document.getElementById('to-top');
  var header = document.getElementById('site-header');

  function onScroll() {
    var scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    var docHeight =
      document.documentElement.scrollHeight - window.innerHeight;
    var pct = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;

    if (progress) progress.style.width = pct + '%';
    if (toTop) toTop.classList.toggle('visible', scrollTop > 480);
    if (header) {
      header.style.borderColor =
        scrollTop > 8 ? 'var(--border)' : 'var(--border-soft)';
    }
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  if (toTop) {
    toTop.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: prefersReducedMotion ? 'auto' : 'smooth' });
    });
  }

  /* ---------------------------------------------------------------------
     Update the year anywhere it is rendered dynamically (footer stays static)
  --------------------------------------------------------------------- */
  var yearEls = document.querySelectorAll('[data-year]');
  var year = String(new Date().getFullYear());
  yearEls.forEach(function (el) {
    el.textContent = year;
  });
})();
