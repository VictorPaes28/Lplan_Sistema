/**
 * Um único controlo multi-ficheiro + pré-visualização com × para o formset imagens-* (máx. 5).
 */
(function () {
  'use strict';

  var MAX = 5;
  var form = document.getElementById('form-comunicado');
  var multi = document.getElementById('comunicado-imagens-multi');
  var previewEl = document.getElementById('comunicado-imagens-preview');
  var msgEl = document.getElementById('comunicado-imagens-msg');
  if (!form || !multi || !previewEl || !document.getElementById('comunicado-imagem-slot-0')) {
    return;
  }

  var previewBlobUrls = [];

  function revokePreviewBlobs() {
    previewBlobUrls.forEach(function (u) {
      try {
        URL.revokeObjectURL(u);
      } catch (e) {
        /* noop */
      }
    });
    previewBlobUrls = [];
  }

  function totalForms() {
    var tf = form.querySelector('input[name="imagens-TOTAL_FORMS"]');
    return tf ? parseInt(tf.value, 10) || 0 : 0;
  }

  function deleteInput(i) {
    return document.getElementById('id_imagens-' + i + '-DELETE');
  }

  function fileInput(i) {
    return document.getElementById('id_imagens-' + i + '-arquivo');
  }

  function idInput(i) {
    return document.getElementById('id_imagens-' + i + '-id');
  }

  function clearCheckbox(i) {
    return document.getElementById('id_imagens-' + i + '-arquivo-clear');
  }

  function slotEl(i) {
    return document.getElementById('comunicado-imagem-slot-' + i);
  }

  function slotMarkedDelete(i) {
    var del = deleteInput(i);
    return !!(del && del.checked);
  }

  function slotOccupied(i) {
    if (slotMarkedDelete(i)) {
      return false;
    }
    var finp = fileInput(i);
    var idinp = idInput(i);
    if (finp && finp.files && finp.files.length) {
      return true;
    }
    if (idinp && String(idinp.value || '').trim()) {
      return true;
    }
    return false;
  }

  function countOccupied() {
    var t = totalForms();
    var c = 0;
    for (var i = 0; i < t; i++) {
      if (slotOccupied(i)) {
        c += 1;
      }
    }
    return c;
  }

  function showMsg(text) {
    if (!msgEl) {
      return;
    }
    msgEl.textContent = text;
    msgEl.hidden = false;
  }

  function hideMsg() {
    if (!msgEl) {
      return;
    }
    msgEl.textContent = '';
    msgEl.hidden = true;
  }

  function clearSlot(i) {
    var finp = fileInput(i);
    var del = deleteInput(i);
    var idinp = idInput(i);
    var clr = clearCheckbox(i);
    if (idinp && String(idinp.value || '').trim()) {
      if (del) {
        del.checked = true;
      }
    }
    if (clr) {
      clr.checked = false;
    }
    if (finp) {
      try {
        finp.value = '';
        finp.files = new DataTransfer().files;
      } catch (e) {
        try {
          finp.value = '';
        } catch (e2) {
          /* noop */
        }
      }
    }
    var slot = slotEl(i);
    if (slot) {
      slot.removeAttribute('data-preview-url');
    }
    hideMsg();
    renderPreview();
  }

  function renderPreview() {
    revokePreviewBlobs();
    previewEl.innerHTML = '';
    var t = totalForms();
    for (var i = 0; i < t; i++) {
      if (!slotOccupied(i)) {
        continue;
      }
      var finp = fileInput(i);
      var slot = slotEl(i);
      var src = '';
      if (finp && finp.files && finp.files[0]) {
        try {
          src = URL.createObjectURL(finp.files[0]);
          previewBlobUrls.push(src);
        } catch (e) {
          src = '';
        }
      } else if (slot) {
        src = slot.getAttribute('data-preview-url') || '';
      }
      if (!src) {
        continue;
      }
      var item = document.createElement('div');
      item.className = 'comunicado-imagens-preview-item';
      item.setAttribute('data-slot-index', String(i));
      var img = document.createElement('img');
      img.src = src;
      img.alt = 'Pré-visualização da imagem ' + (i + 1);
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'comunicado-imagens-preview-remove';
      btn.setAttribute('aria-label', 'Remover imagem');
      btn.innerHTML = '&times;';
      btn.addEventListener('click', function (idx) {
        return function () {
          clearSlot(idx);
        };
      }(i));
      item.appendChild(img);
      item.appendChild(btn);
      previewEl.appendChild(item);
    }
  }

  multi.addEventListener('change', function () {
    var files = Array.prototype.slice.call(multi.files || []);
    multi.value = '';
    if (!files.length) {
      return;
    }
    var occupied = countOccupied();
    var room = MAX - occupied;
    if (room <= 0) {
      showMsg('Já existem 5 imagens. Remova uma antes de adicionar mais.');
      return;
    }
    if (files.length > room) {
      showMsg(
        'Só pode adicionar mais ' +
          room +
          (room === 1 ? ' imagem' : ' imagens') +
          '. Remova algumas ou escolha menos ficheiros.',
      );
      files = files.slice(0, room);
    } else {
      hideMsg();
    }
    var idx = 0;
    for (var f = 0; f < files.length; f++) {
      var t = totalForms();
      while (idx < t && slotOccupied(idx)) {
        idx += 1;
      }
      if (idx >= t) {
        break;
      }
      var finp = fileInput(idx);
      if (!finp) {
        break;
      }
      var del = deleteInput(idx);
      if (del) {
        del.checked = false;
      }
      try {
        var dt = new DataTransfer();
        dt.items.add(files[f]);
        finp.files = dt.files;
      } catch (e) {
        showMsg('Não foi possível anexar um dos ficheiros. Tente outro formato.');
        break;
      }
      try {
        finp.dispatchEvent(new Event('change', { bubbles: true }));
      } catch (e) {
        /* noop */
      }
      idx += 1;
    }
    renderPreview();
  });

  renderPreview();
})();
