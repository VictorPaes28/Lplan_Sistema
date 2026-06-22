(function () {
  function formatFileSize(bytes) {
    if (!bytes && bytes !== 0) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  var iconByExt = {
    pdf: 'fa-file-pdf',
    doc: 'fa-file-word',
    docx: 'fa-file-word',
    jpg: 'fa-file-image',
    jpeg: 'fa-file-image',
    png: 'fa-file-image',
    webp: 'fa-file-image',
  };

  function updateUploadPanelFileUi(form, file) {
    if (!form) return;
    var picker = form.querySelector('[data-role="picker"]');
    var selected = form.querySelector('[data-role="selected"]');
    if (!picker || !selected) return;

    var chipName = form.querySelector('[data-role="chip-name"]');
    var chipSize = form.querySelector('[data-role="chip-size"]');
    var chipIcon = form.querySelector('[data-role="chip-icon"]');

    if (!file) {
      selected.hidden = true;
      picker.hidden = false;
      if (chipName) chipName.textContent = '';
      if (chipSize) chipSize.textContent = '';
      return;
    }

    picker.hidden = true;
    selected.hidden = false;
    if (chipName) chipName.textContent = file.name;
    if (chipSize) chipSize.textContent = formatFileSize(file.size);
    if (chipIcon) {
      var parts = file.name.split('.');
      var ext = parts.length > 1 ? parts.pop().toLowerCase() : '';
      chipIcon.className = 'fas ' + (iconByExt[ext] || 'fa-file');
    }
  }

  function tryAutoSubmitPanel(form) {
    if (!form || form.closest('.rh-doc-item--uploading')) return;
    var dateInput = form.querySelector('input[type="date"]');
    var fileInput = form.querySelector('input[type="file"]');
    if (!dateInput || !dateInput.value || !fileInput || !fileInput.files.length) return;

    if (form.classList.contains('js-rh-doc-ajax-upload')) {
      form.dispatchEvent(new CustomEvent('rh-doc-panel-autosubmit', { bubbles: true }));
      return;
    }

    if (typeof form.requestSubmit === 'function') {
      form.requestSubmit();
    } else {
      form.submit();
    }
  }

  window.RhDocUploadPanel = {
    update: updateUploadPanelFileUi,
  };

  document.addEventListener('click', function (e) {
    var clearBtn = e.target.closest('.rh-doc-upload-panel [data-role="clear"]');
    if (!clearBtn) return;
    e.preventDefault();
    var clearForm = clearBtn.closest('.rh-doc-upload-panel');
    var clearInput = clearForm && clearForm.querySelector('input[type="file"]');
    if (clearInput) clearInput.value = '';
    updateUploadPanelFileUi(clearForm, null);
  });

  document.addEventListener('change', function (e) {
    var input = e.target;
    if (input.matches('.rh-doc-upload-panel input[type="file"]')) {
      var form = input.closest('.rh-doc-upload-panel');
      var file = input.files && input.files[0];
      updateUploadPanelFileUi(form, file || null);
      tryAutoSubmitPanel(form);
      return;
    }
    if (input.matches('.rh-doc-upload-panel input[type="date"]')) {
      tryAutoSubmitPanel(input.closest('.rh-doc-upload-panel'));
    }
  });

  document.addEventListener('submit', function (e) {
    var form = e.target.closest('.rh-doc-upload-panel:not(.js-rh-doc-ajax-upload)');
    if (!form) return;
    var fileInput = form.querySelector('input[type="file"]');
    var dateInput = form.querySelector('input[type="date"]');
    if (dateInput && !dateInput.value) {
      e.preventDefault();
      alert('Informe a data de emissão do documento.');
      return;
    }
    if (!fileInput || !fileInput.files.length) {
      e.preventDefault();
      alert('Selecione um arquivo antes de enviar.');
    }
  });
})();
