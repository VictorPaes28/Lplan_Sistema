/**
 * Assinatura manual (canvas) — mesmo padrão TrackHub / Diário de Obra.
 */
(function (global) {
  'use strict';

  function WfManualSignature(options) {
    this.canvas = document.getElementById(options.canvasId);
    this.hidden = document.getElementById(options.hiddenId);
    this.storageKey = options.storageKey || 'lplan_workflow_last_signature';
    this.fallbackKeys = options.fallbackKeys || [];
    this.state = { hasInk: false };
    if (!this.canvas || !this.hidden) return;
    this._init();
  }

  WfManualSignature.prototype._init = function () {
    var self = this;
    var canvas = this.canvas;
    if (canvas.dataset.signatureInitialized === '1') return;

    var ctx = canvas.getContext('2d');
    var isDrawing = false;
    var lastX = 0;
    var lastY = 0;
    var activePointerId = null;

    function resizeCanvas() {
      var rect = canvas.getBoundingClientRect();
      if (!rect.width) return;
      var dpr = window.devicePixelRatio || 1;
      var preserveData = '';
      if (self.state.hasInk) {
        try {
          preserveData = canvas.toDataURL('image/png');
        } catch (e) {
          preserveData = '';
        }
      }
      canvas.width = rect.width * dpr;
      canvas.height = 160 * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 2.2;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      if (preserveData) {
        var img = new Image();
        img.onload = function () {
          try {
            ctx.drawImage(img, 0, 0, rect.width, 160);
          } catch (e) {}
        };
        img.src = preserveData;
      }
    }

    function getPoint(event) {
      var rect = canvas.getBoundingClientRect();
      return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    }

    function startDraw(event) {
      if (activePointerId !== null && activePointerId !== event.pointerId) return;
      event.preventDefault();
      resizeCanvas();
      activePointerId = event.pointerId;
      isDrawing = true;
      var p = getPoint(event);
      lastX = p.x;
      lastY = p.y;
    }

    function drawMove(event) {
      if (!isDrawing || (activePointerId !== null && event.pointerId !== activePointerId)) return;
      event.preventDefault();
      var p = getPoint(event);
      ctx.beginPath();
      ctx.moveTo(lastX, lastY);
      ctx.lineTo(p.x, p.y);
      ctx.stroke();
      self.state.hasInk = true;
      lastX = p.x;
      lastY = p.y;
    }

    function endDraw(event) {
      if (activePointerId !== null && event && event.pointerId !== activePointerId) return;
      isDrawing = false;
      activePointerId = null;
      self.save();
    }

    resizeCanvas();
    canvas.__signatureResize = resizeCanvas;
    window.addEventListener('resize', resizeCanvas);
    canvas.addEventListener('pointerdown', startDraw, { passive: false });
    canvas.addEventListener('pointermove', drawMove, { passive: false });
    canvas.addEventListener('pointerup', endDraw, { passive: false });
    canvas.addEventListener('pointercancel', endDraw, { passive: false });
    canvas.addEventListener('pointerleave', endDraw, { passive: false });
    canvas.dataset.signatureInitialized = '1';
  };

  WfManualSignature.prototype.save = function () {
    if (!this.canvas || !this.hidden) return '';
    var data = this.state.hasInk ? this.canvas.toDataURL('image/png') : '';
    this.hidden.value = data;
    if (data) {
      try {
        localStorage.setItem(this.storageKey, data);
      } catch (e) {}
    }
    return data;
  };

  WfManualSignature.prototype.clear = function () {
    this.state.hasInk = false;
    if (this.canvas && typeof this.canvas.__signatureResize === 'function') {
      this.canvas.__signatureResize();
    } else if (this.canvas) {
      var ctx = this.canvas.getContext('2d');
      ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }
    if (this.hidden) this.hidden.value = '';
  };

  WfManualSignature.prototype.useLast = function () {
    var data = '';
    try {
      data = localStorage.getItem(this.storageKey) || '';
    } catch (e) {}
    if (!data) {
      for (var i = 0; i < this.fallbackKeys.length; i++) {
        try {
          data = localStorage.getItem(this.fallbackKeys[i]) || '';
        } catch (e2) {}
        if (data) break;
      }
    }
    if (!data) {
      alert('Nenhuma assinatura salva encontrada. Desenhe sua assinatura no quadro.');
      return false;
    }
    var self = this;
    var canvas = this.canvas;
    if (!canvas) return false;
    this._init();
    var ctx = canvas.getContext('2d');
    var img = new Image();
    img.onload = function () {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      var rect = canvas.getBoundingClientRect();
      ctx.drawImage(img, 0, 0, rect.width || canvas.width, 160);
      self.state.hasInk = true;
      self.save();
    };
    img.src = data;
    return true;
  };

  WfManualSignature.prototype.hasSignature = function () {
    this.save();
    var v = (this.hidden && this.hidden.value) || '';
    return v.indexOf('data:image/png;base64,') === 0 && v.length > 500;
  };

  global.WfManualSignature = WfManualSignature;
})(window);
