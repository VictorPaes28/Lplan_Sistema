/**
 * Editor rich text (contenteditable + execCommand) — TrackHub
 */
(function (global) {
  'use strict';

  function escHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function looksLikeHtml(s) {
    return /<[a-z][\s\S]*>/i.test(s || '');
  }

  function plainToHtml(text) {
    if (!text) return '';
    if (looksLikeHtml(text)) return text;
    return String(text)
      .split(/\r?\n/)
      .map(function (line) {
        return line ? '<p>' + escHtml(line) + '</p>' : '<p><br></p>';
      })
      .join('');
  }

  function isEmptyHtml(html) {
    var tmp = document.createElement('div');
    tmp.innerHTML = html || '';
    return !(tmp.textContent || '').replace(/\u00a0/g, ' ').trim();
  }

  function hasStructuralContent(source) {
    var el = source;
    if (!el) return false;
    if (typeof source === 'string') {
      el = document.createElement('div');
      el.innerHTML = source || '';
    }
    return !!el.querySelector('ul, ol, table, blockquote, pre, hr');
  }

  function isEditorVisuallyEmpty(editor) {
    if (!editor) return true;
    if (hasStructuralContent(editor)) return false;
    return isEmptyHtml(getHtml(editor));
  }

  function normalizeIfEmpty(editor, opts) {
    opts = opts || {};
    if (!editor) return;

    var hasText = !isEmptyHtml(getHtml(editor));
    var hasStructure = hasStructuralContent(editor);

    if (hasText) {
      updatePlaceholder(editor);
      return;
    }

    if (hasStructure) {
      if (opts.forceClear) editor.innerHTML = '';
      updatePlaceholder(editor);
      return;
    }

    var isFocused = document.activeElement === editor;
    if (isFocused && !opts.forceClear) {
      if (editor.innerHTML === '') editor.innerHTML = '<br>';
    } else if (editor.innerHTML !== '') {
      editor.innerHTML = '';
    }
    updatePlaceholder(editor);
  }

  function prepareEmptyEditorForInput(editor) {
    if (!editor || !isEditorVisuallyEmpty(editor)) return;
    if (editor.innerHTML === '') editor.innerHTML = '<br>';
    placeCaretInEmptyEditor(editor);
  }

  function placeCaretInEmptyEditor(editor) {
    if (!editor) return;
    var range = document.createRange();
    var sel = window.getSelection();
    if (!sel) return;
    if (!editor.childNodes.length) editor.innerHTML = '<br>';
    range.setStart(editor, 0);
    range.collapse(true);
    sel.removeAllRanges();
    sel.addRange(range);
  }

  function getListContext(editor) {
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount || !editor) return null;
    var node = sel.anchorNode;
    if (node && node.nodeType === 3) node = node.parentNode;
    while (node && node !== editor) {
      if (node.nodeName === 'LI') {
        var list = node.parentNode;
        var type = list && list.nodeName === 'OL' ? 'ol' : list && list.nodeName === 'UL' ? 'ul' : null;
        if (type) return { li: node, list: list, type: type };
      }
      node = node.parentNode;
    }
    return null;
  }

  function isListItemEmpty(li) {
    return !(li.textContent || '').replace(/\u00a0/g, ' ').trim();
  }

  function placeCaretInNode(node) {
    if (!node) return;
    var range = document.createRange();
    range.setStart(node, 0);
    range.collapse(true);
    var sel = window.getSelection();
    if (!sel) return;
    sel.removeAllRanges();
    sel.addRange(range);
  }

  function exitList(editor, ctx) {
    if (!editor || !ctx || !ctx.list) return;
    var list = ctx.list;
    var parent = list.parentNode;
    if (!parent) return;
    if (ctx.li && isListItemEmpty(ctx.li)) ctx.li.remove();
    var p = document.createElement('p');
    p.appendChild(document.createElement('br'));
    if (!list.children.length) {
      parent.replaceChild(p, list);
    } else {
      parent.insertBefore(p, list.nextSibling);
    }
    placeCaretInNode(p);
    editor.focus();
  }

  function bindEnterKey(editor, root) {
    var lastEnterAt = 0;
    editor.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      var ctx = getListContext(editor);

      if (e.ctrlKey || e.metaKey) {
        if (ctx) {
          e.preventDefault();
          exitList(editor, ctx);
          syncToTextarea(root);
          normalizeIfEmpty(editor);
        }
        return;
      }

      if (!ctx) return;

      if (isListItemEmpty(ctx.li)) {
        var now = Date.now();
        if (now - lastEnterAt < 700) {
          e.preventDefault();
          exitList(editor, ctx);
          syncToTextarea(root);
          normalizeIfEmpty(editor);
          lastEnterAt = 0;
          return;
        }
        lastEnterAt = now;
      } else {
        lastEnterAt = Date.now();
      }
    });
  }

  function getHtml(editor) {
    if (!editor) return '';
    return (editor.innerHTML || '').trim();
  }

  function setHtml(editor, html) {
    if (!editor) return;
    if (!html || isEmptyHtml(html)) {
      editor.innerHTML = '';
    } else {
      editor.innerHTML = plainToHtml(html || '');
    }
    updatePlaceholder(editor);
  }

  function syncToTextarea(root) {
    if (!root) return;
    var editor = root.querySelector('.th-richtext-editor');
    var ta = root.querySelector('textarea.th-richtext-sync, textarea[name]');
    if (!editor || !ta) return;
    var html = getHtml(editor);
    ta.value = isEmptyHtml(html) ? '' : html;
  }

  function syncAll(scope) {
    var base = scope && scope.querySelectorAll ? scope : document;
    base.querySelectorAll('.th-richtext[data-th-richtext]').forEach(syncToTextarea);
  }

  function updatePlaceholder(editor) {
    if (!editor) return;
    editor.classList.toggle('is-empty', isEditorVisuallyEmpty(editor));
  }

  function updateToolbarState(toolbar, editor) {
    if (!toolbar || !editor) return;
    toolbar.querySelectorAll('.th-richtext-btn[data-cmd]').forEach(function (btn) {
      var cmd = btn.getAttribute('data-cmd');
      var active = false;
      try {
        if (cmd === 'bold') active = document.queryCommandState('bold');
        else if (cmd === 'italic') active = document.queryCommandState('italic');
        else if (cmd === 'underline') active = document.queryCommandState('underline');
        else if (cmd === 'insertUnorderedList') active = document.queryCommandState('insertUnorderedList');
        else if (cmd === 'insertOrderedList') active = document.queryCommandState('insertOrderedList');
      } catch (e) {}
      btn.classList.toggle('is-active', !!active);
    });
  }

  function bindToolbar(toolbar, editor, root) {
    if (!toolbar || !editor) return;
    toolbar.querySelectorAll('.th-richtext-btn[data-cmd]').forEach(function (btn) {
      btn.addEventListener('mousedown', function (e) {
        e.preventDefault();
      });
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        editor.focus();
        var cmd = btn.getAttribute('data-cmd');
        if (cmd) document.execCommand(cmd, false, null);
        updateToolbarState(toolbar, editor);
        syncToTextarea(root);
        updatePlaceholder(editor);
      });
    });
    ['keyup', 'mouseup', 'focus'].forEach(function (ev) {
      editor.addEventListener(ev, function () {
        updateToolbarState(toolbar, editor);
      });
    });
  }

  function initRoot(root) {
    if (!root || root.getAttribute('data-th-richtext-init') === '1') return root;
    root.setAttribute('data-th-richtext-init', '1');
    var editor = root.querySelector('.th-richtext-editor');
    var ta = root.querySelector('textarea.th-richtext-sync, textarea[name]');
    if (!editor) return root;

    if (ta && ta.value) {
      setHtml(editor, ta.value);
    } else if (editor.textContent && !editor.innerHTML.trim()) {
      setHtml(editor, editor.textContent);
    }

    var toolbar = root.querySelector('.th-richtext-toolbar');
    if (toolbar) bindToolbar(toolbar, editor, root);
    bindEnterKey(editor, root);

    editor.addEventListener('input', function () {
      if (isEmptyHtml(getHtml(editor)) && document.activeElement === editor && editor.innerHTML === '') {
        editor.innerHTML = '<br>';
      }
      syncToTextarea(root);
      updatePlaceholder(editor);
      if (toolbar) updateToolbarState(toolbar, editor);
    });

    editor.addEventListener('blur', function () {
      normalizeIfEmpty(editor, { forceClear: true });
      syncToTextarea(root);
    });

    editor.addEventListener('focus', function () {
      prepareEmptyEditorForInput(editor);
      updatePlaceholder(editor);
    });

    editor.addEventListener('paste', function (e) {
      e.preventDefault();
      var text = (e.clipboardData || window.clipboardData).getData('text/plain');
      document.execCommand('insertText', false, text);
    });

    normalizeIfEmpty(editor);
    return root;
  }

  function initAll(scope) {
    var base = scope && scope.querySelectorAll ? scope : document;
    base.querySelectorAll('.th-richtext[data-th-richtext]').forEach(initRoot);
  }

  /** Envolve contenteditable standalone (ex.: descrição no modal de detalhe). */
  function wrapStandaloneEditor(el, opts) {
    if (!el || el.closest('.th-richtext')) return el;
    opts = opts || {};
    var toolbarPos = opts.toolbar || 'top';
    var wrap = document.createElement('div');
    wrap.className = 'th-richtext th-richtext--' + toolbarPos + ' th-richtext--standalone';
    wrap.setAttribute('data-th-richtext', toolbarPos);
    wrap.setAttribute('data-th-richtext-standalone', '1');

    var parent = el.parentNode;
    var next = el.nextSibling;
    parent.insertBefore(wrap, el);
    wrap.appendChild(el);

    if (toolbarPos === 'top') {
      var tb = document.createElement('div');
      tb.className = 'th-richtext-toolbar';
      tb.setAttribute('role', 'toolbar');
      tb.setAttribute('aria-label', 'Formatação de texto');
      tb.innerHTML = toolbarButtonsHtml();
      wrap.insertBefore(tb, el);
    }

    el.classList.add('th-richtext-editor');
    if (opts.placeholder) el.setAttribute('data-placeholder', opts.placeholder);

    var toolbar = wrap.querySelector('.th-richtext-toolbar');
    bindToolbar(toolbar, el, wrap);
    bindEnterKey(el, wrap);
    normalizeIfEmpty(el);
    wrap.setAttribute('data-th-richtext-init', '1');
    return el;
  }

  function setToolbarVisible(wrap, visible) {
    if (!wrap) return;
    var tb = wrap.querySelector('.th-richtext-toolbar');
    if (tb) tb.hidden = !visible;
  }

  document.addEventListener('DOMContentLoaded', function () {
    initAll(document);
    document.querySelectorAll('form[enctype="multipart/form-data"], #th-cal-criar-form, form[action*="comentar"]').forEach(function (form) {
      form.addEventListener('submit', function () {
        syncAll(form);
      });
    });
  });

  var SVG_UL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">'
    + '<line x1="9" y1="6" x2="20" y2="6"/>'
    + '<line x1="9" y1="12" x2="20" y2="12"/>'
    + '<line x1="9" y1="18" x2="20" y2="18"/>'
    + '<circle cx="4" cy="6" r="1.5" fill="currentColor" stroke="none"/>'
    + '<circle cx="4" cy="12" r="1.5" fill="currentColor" stroke="none"/>'
    + '<circle cx="4" cy="18" r="1.5" fill="currentColor" stroke="none"/>'
    + '</svg>';
  var SVG_OL = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">'
    + '<line x1="10" y1="6" x2="21" y2="6"/>'
    + '<line x1="10" y1="12" x2="21" y2="12"/>'
    + '<line x1="10" y1="18" x2="21" y2="18"/>'
    + '<path d="M4 6h1v4" stroke="currentColor" stroke-width="1.5"/>'
    + '<path d="M4 10h2" stroke="currentColor" stroke-width="1.5"/>'
    + '<path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1" stroke="currentColor" stroke-width="1.5"/>'
    + '</svg>';

  function toolbarButtonsHtml() {
    return ''
      + '<button type="button" class="th-richtext-btn" data-cmd="bold" title="Negrito"><strong>B</strong></button>'
      + '<button type="button" class="th-richtext-btn" data-cmd="italic" title="Itálico"><em>I</em></button>'
      + '<button type="button" class="th-richtext-btn" data-cmd="underline" title="Sublinhado"><u style="text-decoration:underline;font-weight:600">U</u></button>'
      + '<span class="th-richtext-sep" aria-hidden="true"></span>'
      + '<button type="button" class="th-richtext-btn" data-cmd="insertUnorderedList" title="Lista com marcadores">' + SVG_UL + '</button>'
      + '<button type="button" class="th-richtext-btn" data-cmd="insertOrderedList" title="Lista numerada">' + SVG_OL + '</button>';
  }

  function toolbarHtml() {
    return '<div class="th-richtext-toolbar" role="toolbar" aria-label="Formatação de texto">'
      + toolbarButtonsHtml()
      + '</div>';
  }

  function observacaoBlockHtml(initialValue) {
    var val = escHtml(initialValue || '');
    return ''
      + '<div class="th-richtext th-richtext--top" data-th-richtext="top">'
      + toolbarHtml()
      + '<div class="th-richtext-editor" contenteditable="true" role="textbox" aria-multiline="true" tabindex="0" data-placeholder="Observações sobre esta etapa..."></div>'
      + '<textarea name="observacao" class="th-richtext-sync" style="display:none;">' + val + '</textarea>'
      + '</div>';
  }

  global.ThRichText = {
    initAll: initAll,
    initRoot: initRoot,
    syncAll: syncAll,
    syncToTextarea: syncToTextarea,
    getHtml: getHtml,
    setHtml: setHtml,
    isEmptyHtml: isEmptyHtml,
    plainToHtml: plainToHtml,
    wrapStandaloneEditor: wrapStandaloneEditor,
    setToolbarVisible: setToolbarVisible,
    updatePlaceholder: updatePlaceholder,
    normalizeIfEmpty: normalizeIfEmpty,
    observacaoBlockHtml: observacaoBlockHtml,
  };
})(window);
