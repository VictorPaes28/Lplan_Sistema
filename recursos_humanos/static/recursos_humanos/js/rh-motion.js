/**
 * Utilitários de transição do módulo DP/RH — modais e overlays animados.
 */
(function () {
  var OPEN_RH = 'is-open';
  var OPEN_OVERLAY = 'open';
  var FALLBACK_MS = 320;

  function afterTransition(el, cb) {
    if (!el) {
      cb();
      return;
    }
    var done = false;
    function finish() {
      if (done) return;
      done = true;
      el.removeEventListener('transitionend', onEnd);
      clearTimeout(timer);
      cb();
    }
    function onEnd(e) {
      if (e.target !== el && e.target !== el.querySelector('.modal-rh')) return;
      finish();
    }
    var timer = setTimeout(finish, FALLBACK_MS);
    el.addEventListener('transitionend', onEnd);
  }

  function hasOpenLayer() {
    return !!document.querySelector('.rh-modal.is-open, .modal-overlay.open, .rh-doc-reject-modal.is-open');
  }

  function resetModalLayers() {
    document.querySelectorAll('.rh-modal.is-open, .rh-doc-reject-modal.is-open').forEach(function (modal) {
      modal.classList.remove(OPEN_RH);
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
    });
    document.querySelectorAll('.modal-overlay.open').forEach(function (modal) {
      modal.classList.remove(OPEN_OVERLAY);
      modal.setAttribute('aria-hidden', 'true');
    });
    document.body.classList.remove('rh-modal-open');
  }

  function openRhModal(modal) {
    if (!modal) return;
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('rh-modal-open');
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        modal.classList.add(OPEN_RH);
      });
    });
  }

  function closeRhModal(modal) {
    if (!modal) return;
    if (!modal.classList.contains(OPEN_RH)) {
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
      if (!hasOpenLayer()) document.body.classList.remove('rh-modal-open');
      return;
    }
    modal.classList.remove(OPEN_RH);
    afterTransition(modal.querySelector('.rh-modal-dialog') || modal, function () {
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
      if (!hasOpenLayer()) document.body.classList.remove('rh-modal-open');
    });
  }

  function openOverlay(modal) {
    if (!modal) return;
    document.querySelectorAll('.modal-overlay.open').forEach(function (m) {
      if (m !== modal) {
        m.classList.remove(OPEN_OVERLAY);
        m.setAttribute('aria-hidden', 'true');
      }
    });
    modal.classList.add(OPEN_OVERLAY);
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('rh-modal-open');
  }

  function closeOverlay(modal, keepBodyLock) {
    if (!modal || !modal.classList.contains(OPEN_OVERLAY)) return;
    modal.classList.remove(OPEN_OVERLAY);
    modal.setAttribute('aria-hidden', 'true');
    afterTransition(modal.querySelector('.modal-rh') || modal, function () {
      if (!keepBodyLock && !hasOpenLayer()) {
        document.body.classList.remove('rh-modal-open');
      }
    });
  }

  function closeAllOverlays() {
    document.querySelectorAll('.modal-overlay.open').forEach(function (m) {
      closeOverlay(m, true);
    });
    if (!hasOpenLayer()) document.body.classList.remove('rh-modal-open');
  }

  function markReady() {
    var root = document.querySelector('.rh-fullbleed');
    if (root) root.classList.add('rh-ready');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', markReady);
  } else {
    requestAnimationFrame(markReady);
  }

  window.addEventListener('pageshow', function (event) {
    if (event.persisted) {
      resetModalLayers();
    }
  });

  window.RhMotion = {
    openRhModal: openRhModal,
    closeRhModal: closeRhModal,
    openOverlay: openOverlay,
    closeOverlay: closeOverlay,
    closeAllOverlays: closeAllOverlays,
    resetModalLayers: resetModalLayers,
  };
})();
