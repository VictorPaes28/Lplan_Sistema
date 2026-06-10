/**
 * Seletor de frente: navegação por ?front= e dropdown pesquisável quando há muitas opções.
 */
(function () {
    'use strict';

    var SEARCHABLE_MIN = 8;

    function navigateWithFront(selectEl, value) {
        var url = new URL(window.location.href);
        if (value) {
            url.searchParams.set('front', value);
        } else {
            url.searchParams.delete('front');
        }
        window.location.href = url.toString();
    }

    function mountSearchableFrontSelect(nativeSelect) {
        if (!nativeSelect || nativeSelect.dataset.lplanFrontEnhanced === '1') {
            return;
        }
        nativeSelect.dataset.lplanFrontEnhanced = '1';

        var wrapper = document.createElement('div');
        wrapper.className = 'lplan-front-searchable';

        var trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'lplan-front-searchable__trigger';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');

        var labelSpan = document.createElement('span');
        labelSpan.className = 'lplan-front-searchable__trigger-label';

        var chevron = document.createElement('span');
        chevron.className = 'lplan-front-searchable__chevron';
        chevron.setAttribute('aria-hidden', 'true');
        chevron.textContent = '▾';

        trigger.appendChild(labelSpan);
        trigger.appendChild(chevron);

        var panel = document.createElement('div');
        panel.className = 'lplan-front-searchable__panel';
        panel.hidden = true;
        panel.setAttribute('role', 'listbox');

        var search = document.createElement('input');
        search.type = 'search';
        search.className = 'lplan-front-searchable__search form-control form-control-sm';
        search.placeholder = 'Buscar frente…';
        search.autocomplete = 'off';

        var list = document.createElement('ul');
        list.className = 'lplan-front-searchable__list';

        panel.appendChild(search);
        panel.appendChild(list);

        nativeSelect.parentNode.insertBefore(wrapper, nativeSelect);
        wrapper.appendChild(trigger);
        wrapper.appendChild(panel);
        wrapper.appendChild(nativeSelect);
        nativeSelect.classList.add('lplan-front-native-hidden');
        nativeSelect.tabIndex = -1;
        nativeSelect.setAttribute('aria-hidden', 'true');

        var options = Array.from(nativeSelect.options).map(function (opt) {
            return {
                value: opt.value,
                text: (opt.textContent || '').trim(),
            };
        });

        function selectedLabel() {
            var hit = options.find(function (o) {
                return o.value === nativeSelect.value;
            });
            return hit ? hit.text : 'Selecionar frente';
        }

        function syncTrigger() {
            labelSpan.textContent = selectedLabel();
            list.querySelectorAll('.lplan-front-searchable__item').forEach(function (li) {
                li.classList.toggle('is-selected', li.dataset.value === nativeSelect.value);
            });
        }

        function closePanel() {
            panel.hidden = true;
            wrapper.classList.remove('is-open');
            trigger.setAttribute('aria-expanded', 'false');
        }

        function openPanel() {
            panel.hidden = false;
            wrapper.classList.add('is-open');
            trigger.setAttribute('aria-expanded', 'true');
            search.value = '';
            renderList('');
            search.focus();
        }

        function renderList(query) {
            var q = (query || '').trim().toLowerCase();
            list.innerHTML = '';
            var hits = options.filter(function (o) {
                return !q || o.text.toLowerCase().indexOf(q) !== -1;
            });
            if (!hits.length) {
                var empty = document.createElement('li');
                empty.className = 'lplan-front-searchable__empty';
                empty.textContent = 'Nenhuma frente encontrada.';
                list.appendChild(empty);
                return;
            }
            hits.forEach(function (item) {
                var li = document.createElement('li');
                li.className = 'lplan-front-searchable__item';
                li.dataset.value = item.value;
                li.textContent = item.text;
                li.setAttribute('role', 'option');
                if (item.value === nativeSelect.value) {
                    li.classList.add('is-selected');
                }
                li.addEventListener('click', function () {
                    nativeSelect.value = item.value;
                    closePanel();
                    navigateWithFront(nativeSelect, item.value);
                });
                list.appendChild(li);
            });
        }

        trigger.addEventListener('click', function () {
            if (panel.hidden) {
                openPanel();
            } else {
                closePanel();
            }
        });

        search.addEventListener('input', function () {
            renderList(search.value);
        });

        search.addEventListener('keydown', function (ev) {
            if (ev.key === 'Escape') {
                ev.preventDefault();
                closePanel();
                trigger.focus();
            }
        });

        document.addEventListener('click', function (ev) {
            if (!wrapper.contains(ev.target)) {
                closePanel();
            }
        });

        syncTrigger();
    }

    function bindNativeSelect(selectEl) {
        if (!selectEl || selectEl.dataset.lplanFrontBound) {
            return;
        }
        selectEl.dataset.lplanFrontBound = '1';

        var rawCount = selectEl.getAttribute('data-lplan-front-count');
        var frontCount = rawCount !== null && rawCount !== ''
            ? parseInt(rawCount, 10)
            : selectEl.options.length;
        if (!Number.isFinite(frontCount)) {
            frontCount = selectEl.options.length;
        }
        if (frontCount >= SEARCHABLE_MIN) {
            mountSearchableFrontSelect(selectEl);
            return;
        }

        selectEl.addEventListener('change', function () {
            navigateWithFront(selectEl, selectEl.value || '');
        });
    }

    function init() {
        document.querySelectorAll('[data-lplan-front-select="1"]').forEach(bindNativeSelect);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.LplanContextoFrente = {
        init: init,
        bind: bindNativeSelect,
    };
})();
