(function () {
    'use strict';

    function getCsrfToken() {
        var meta = document.querySelector('meta[name=csrf-token]');
        if (meta && meta.content) return meta.content.trim();
        var inp = document.querySelector('[name=csrfmiddlewaretoken]');
        if (inp && inp.value) return inp.value.trim();
        return '';
    }

    /** Overlay precisa ficar sob document.body para position:fixed ser sempre da viewport (ancestral com transform quebra às vezes). */
    function garantirOverlayNoBody() {
        var overlay = document.getElementById('gc-overlay');
        if (overlay && overlay.parentNode !== document.body) {
            document.body.appendChild(overlay);
        }
        return overlay;
    }

    window._gcModalRejectData = null;
    window._gcListaPedidosAlterada = false;

    function getReprovarOverlayEl() {
        return document.getElementById('gc-reprovar-overlay');
    }

    function hideReprovarInlineError() {
        var el = document.getElementById('gc-reprovar-error');
        if (el) {
            el.style.display = 'none';
            el.textContent = '';
        }
    }

    function showReprovarInlineError(msg) {
        var el = document.getElementById('gc-reprovar-error');
        if (!el) return;
        el.textContent = msg || '';
        el.style.display = msg ? 'block' : 'none';
    }

    var gcReprovarNovasTags = [];

    function gcReprovarNovasSyncHidden() {
        var h = document.getElementById('gc-reprovar-novas-hidden');
        if (h) h.value = gcReprovarNovasTags.join(', ');
    }

    function gcReprovarNovasRender() {
        var list = document.getElementById('gc-reprovar-nova-lista');
        if (!list) return;
        list.innerHTML = '';
        if (!gcReprovarNovasTags.length) {
            list.innerHTML = '<span class="gc-reprovar-tags-empty">Nenhuma nova tag.</span>';
            gcReprovarNovasSyncHidden();
            return;
        }
        gcReprovarNovasTags.forEach(function (tag) {
            var chip = document.createElement('span');
            chip.className = 'gc-reprovar-chip';
            chip.appendChild(document.createTextNode(tag));
            var rm = document.createElement('button');
            rm.type = 'button';
            rm.className = 'gc-reprovar-chip-remove';
            rm.setAttribute('aria-label', 'Remover tag');
            rm.textContent = '\u00d7';
            rm.addEventListener('click', function () {
                gcReprovarNovasTags = gcReprovarNovasTags.filter(function (x) {
                    return x.toLowerCase() !== tag.toLowerCase();
                });
                gcReprovarNovasRender();
            });
            chip.appendChild(rm);
            list.appendChild(chip);
        });
        gcReprovarNovasSyncHidden();
    }

    function gcReprovarNovasReset() {
        gcReprovarNovasTags = [];
        var inp = document.getElementById('gc-reprovar-nova-input');
        if (inp) inp.value = '';
        gcReprovarNovasSyncHidden();
        gcReprovarNovasRender();
    }

    function gcReprovarNovasAdd(raw) {
        var value = (raw || '').trim().replace(/\s+/g, ' ');
        if (!value) return;
        var exists = gcReprovarNovasTags.some(function (t) {
            return t.toLowerCase() === value.toLowerCase();
        });
        if (exists) return;
        gcReprovarNovasTags.push(value);
        gcReprovarNovasRender();
    }

    function resetReprovarFormUi() {
        hideReprovarInlineError();
        var wrap = document.getElementById('gc-reprovar-tags');
        if (wrap) wrap.innerHTML = '';
        var ta = document.getElementById('gc-reprovar-comentario');
        if (ta) ta.value = '';
        gcReprovarNovasReset();
        var sub = document.getElementById('gc-reprovar-submit');
        if (sub) sub.disabled = false;
    }

    function renderReprovarTags(tags) {
        var wrap = document.getElementById('gc-reprovar-tags');
        if (!wrap) return;
        wrap.innerHTML = '';
        if (!tags || !tags.length) {
            wrap.innerHTML = '<p class="gc-reprovar-tags-empty">Não há tags cadastradas para este tipo. Use novas tags ou o comentário.</p>';
            return;
        }
        tags.forEach(function (t) {
            var lab = document.createElement('label');
            lab.className = 'gc-reprovar-tag-option';
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = String(t.id);
            var txt = document.createElement('div');
            txt.className = 'gc-reprovar-tag-text';
            var nm = document.createElement('span');
            nm.className = 'gc-reprovar-tag-name';
            nm.textContent = t.nome || '';
            txt.appendChild(nm);
            if (t.descricao) {
                var d = document.createElement('span');
                d.className = 'gc-reprovar-tag-desc';
                d.textContent = t.descricao;
                txt.appendChild(d);
            }
            lab.appendChild(cb);
            lab.appendChild(txt);
            wrap.appendChild(lab);
        });
    }

    window.fecharReprovarSheet = function () {
        var ov = getReprovarOverlayEl();
        if (ov) {
            ov.classList.remove('is-open');
            ov.setAttribute('aria-hidden', 'true');
        }
        resetReprovarFormUi();
    };

    window.abrirReprovarSheet = function () {
        var data = window._gcModalRejectData;
        if (!data || !data.reprovarUrl) {
            alert('Não foi possível abrir a reprovação. Feche e abra o pedido novamente.');
            return;
        }
        hideReprovarInlineError();
        resetReprovarFormUi();
        renderReprovarTags(data.tags);
        var ov = getReprovarOverlayEl();
        if (ov) {
            ov.classList.add('is-open');
            ov.setAttribute('aria-hidden', 'false');
        }
        var inp = document.getElementById('gc-reprovar-nova-input');
        if (inp) inp.focus();
    };

    window.fecharModalPedido = function () {
        var reloadLista =
            !!window._gcListaPedidosAlterada && !!document.querySelector('tr.gc-pedido-row');
        window._gcListaPedidosAlterada = false;

        window.fecharReprovarSheet();
        var overlay = document.getElementById('gc-overlay');
        if (overlay) overlay.style.display = 'none';
        document.body.style.overflow = '';
        document.documentElement.style.overflow = '';
        window._gcModalCurrentPk = null;
        window._gcModalUrls = null;
        window._gcModalRejectData = null;

        if (reloadLista) {
            window.location.reload();
        }
    };

    function escapeHtml(s) {
        if (!s) return '';
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function switchGcPedidoSideTab(which) {
        var comments = which === 'comments';
        var btnC = document.getElementById('gc-tab-btn-comments');
        var btnA = document.getElementById('gc-tab-btn-activities');
        var panelC = document.getElementById('gc-tab-panel-comments');
        var panelA = document.getElementById('gc-tab-panel-activities');
        if (btnC && btnA) {
            btnC.classList.toggle('active', comments);
            btnA.classList.toggle('active', !comments);
            btnC.setAttribute('aria-selected', comments ? 'true' : 'false');
            btnA.setAttribute('aria-selected', comments ? 'false' : 'true');
        }
        if (panelC && panelA) {
            panelC.classList.toggle('gc-side-tab-panel--hidden', !comments);
            panelA.classList.toggle('gc-side-tab-panel--hidden', comments);
        }
    }
    window.switchGcPedidoSideTab = switchGcPedidoSideTab;

    /** Classes de status na lista (list_workorders — badge na coluna Status). */
    var GC_STATUS_ROW_CLASSES = ['rascunho', 'pendente', 'aprovado', 'reprovado', 'reaprovacao', 'cancelado'];

    /** Mantém a lista de pedidos alinhada ao JSON do modal (evita precisar dar F5 após reprovar). */
    function syncGestaoListaPedidoRowFromModal(d) {
        if (!d || d.pk == null) return;
        var row = document.querySelector('tr.gc-pedido-row[data-pk="' + String(d.pk) + '"]');
        if (!row) return;
        var badge = row.querySelector('.status-col .status-badge');
        if (!badge) return;
        GC_STATUS_ROW_CLASSES.forEach(function (s) {
            badge.classList.remove(s);
        });
        if (d.status) badge.classList.add(d.status);
        badge.textContent = d.status_display || '';
    }

    var GC_DOC_SVG = '<svg class="gc-anexo-doc-svg" width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>';

    window.toggleVerMaisAprovacao = function () {
        var el = document.getElementById('gc-ver-mais-body');
        var btn = document.getElementById('gc-ver-mais-btn');
        if (!el) return;
        var open = el.classList.toggle('is-open');
        if (btn) btn.textContent = open ? 'Ver menos' : 'Ver mais sobre o fluxo de aprovação';
    };

    /** Limpa o modal antes do fetch para não mostrar dados do pedido anterior (cores/status). */
    window.modalPedidoResetParaCarregar = function () {
        window.fecharReprovarSheet();
        window._gcModalRejectData = null;
        var bc = document.getElementById('gc-breadcrumb');
        if (bc) bc.innerHTML =
            '<span style="color:#94a3b8;">Carregando…</span>';
        var st = document.getElementById('gc-pill-status');
        if (st) {
            st.textContent = '…';
            st.className = 'gc-pill gc-pill-status';
        }
        var tp = document.getElementById('gc-pill-tipo');
        if (tp) tp.textContent = '…';
        var op = document.getElementById('gc-pill-obra');
        if (op) op.textContent = '…';
        var vp = document.getElementById('gc-pill-valor');
        if (vp) {
            vp.textContent = '—';
            vp.className = 'gc-pill gc-pill-muted gc-mono';
        }
        var cm = document.getElementById('gc-pills-meta');
        if (cm) cm.textContent = '';
        function dash(id) {
            var n = document.getElementById(id);
            if (n) n.textContent = '—';
        }
        dash('gc-f-codigo');
        dash('gc-f-credor');
        dash('gc-f-tipo');
        dash('gc-f-valor-med');
        dash('gc-f-created');
        dash('gc-f-updated');
        var obs = document.getElementById('gc-observacoes');
        if (obs) obs.textContent = '';
        dash('gc-ctl-solicitante');
        dash('gc-ctl-email');
        dash('gc-ctl-envio');
        var act = document.getElementById('gc-activities-list');
        if (act) act.innerHTML = '';
        var hist = document.getElementById('gc-historico-list');
        if (hist) hist.innerHTML = '';
        switchGcPedidoSideTab('comments');
        var cl = document.getElementById('gc-comments-list');
        if (cl) cl.innerHTML = '';
        var anex = document.getElementById('gc-anexos-grid');
        if (anex) anex.innerHTML = '';
        var secAprov = document.getElementById('gc-sec-aprovacao');
        if (secAprov) secAprov.style.display = 'none';
        var secExc = document.getElementById('gc-sec-exclusao');
        if (secExc) secExc.style.display = 'none';
        var lp = document.getElementById('gc-link-pagina-completa');
        if (lp) lp.href = '#';
        var secRep = document.getElementById('gc-sec-reprovado');
        if (secRep) secRep.style.display = 'none';
        var ftLab = document.getElementById('gc-ft-editar-label');
        if (ftLab) ftLab.textContent = 'Editar';
        var ftEd = document.getElementById('gc-ft-editar');
        if (ftEd) {
            ftEd.classList.remove('gc-footer-btn--reenviar');
            ftEd.classList.add('gc-footer-btn--primary');
        }
        var bIna = document.getElementById('gc-banner-obra-inativa');
        if (bIna) {
            bIna.style.display = 'none';
            bIna.textContent = '';
        }
        ['gc-ft-pdf', 'gc-ft-leitura', 'gc-ft-editar', 'gc-ft-exclusao', 'gc-aprov-link', 'gc-reprovado-cta'].forEach(
            function (id) {
                var el = document.getElementById(id);
                if (el) el.href = '#';
            }
        );
    };

    window.preencherModalPedido = function (d) {
        var obraLabel = (d.obra && d.obra.label) ? d.obra.label : '';
        var obraNome = (d.obra && d.obra.nome) ? d.obra.nome : '';
        var bcObraTitulo = (obraNome || obraLabel || '—').trim();
        var bc = document.getElementById('gc-breadcrumb');
        if (bc) {
            bc.innerHTML = escapeHtml(bcObraTitulo) +
                '<span class="gc-bc-sep">›</span>' +
                '<span class="gc-mono">' + escapeHtml(d.codigo || '') + '</span>';
        }
        var lp = document.getElementById('gc-link-pagina-completa');
        if (lp) lp.href = d.url_detalhe_completo || '#';

        var st = document.getElementById('gc-pill-status');
        if (st) {
            st.textContent = d.status_display || '';
            st.className = 'gc-pill gc-pill-status ' + (d.status || '');
        }
        var tp = document.getElementById('gc-pill-tipo');
        if (tp) tp.textContent = d.tipo_solicitacao_display || '';
        var op = document.getElementById('gc-pill-obra');
        if (op) op.textContent = obraNome || obraLabel || '—';
        var vp = document.getElementById('gc-pill-valor');
        if (vp) {
            var vtxt = d.valor_medicao_formatado || d.valor_estimado_formatado || '—';
            vp.textContent = vtxt;
            vp.className = 'gc-pill gc-pill-muted gc-mono';
        }
        var cm = document.getElementById('gc-pills-meta');
        if (cm) {
            cm.textContent = 'Criado por ' + (d.criado_por && d.criado_por.nome ? d.criado_por.nome : '—') +
                (d.created_at ? ' em ' + d.created_at : '');
        }

        var banIna = document.getElementById('gc-banner-obra-inativa');
        if (banIna) {
            if (d.obra_consulta_aviso) {
                banIna.textContent = d.obra_consulta_aviso;
                banIna.style.display = 'block';
            } else {
                banIna.textContent = '';
                banIna.style.display = 'none';
            }
        }

        function setText(id, text) {
            var n = document.getElementById(id);
            if (n) n.textContent = text == null || text === '' ? '—' : text;
        }
        setText('gc-f-codigo', d.codigo);
        setText('gc-f-credor', d.nome_credor);
        setText('gc-f-tipo', d.tipo_solicitacao_display);
        setText('gc-f-valor-med', d.valor_medicao_formatado || '—');
        setText('gc-f-created', d.created_at);
        setText('gc-f-updated', d.updated_at);

        var obs = document.getElementById('gc-observacoes');
        if (obs) {
            obs.textContent = (d.observacoes && d.observacoes.trim()) ? d.observacoes.trim() : 'Nenhuma observação.';
        }

        setText('gc-ctl-solicitante', d.criado_por && d.criado_por.nome);
        setText('gc-ctl-email', (d.criado_por && d.criado_por.email) ? d.criado_por.email : '—');
        setText('gc-ctl-envio', d.data_envio || '—');

        var secAprov = document.getElementById('gc-sec-aprovacao');
        if (secAprov) secAprov.style.display = d.pode_aprovar ? 'block' : 'none';
        window._gcModalRejectData = null;
        var aprovL = document.getElementById('gc-aprov-link');
        if (d.urls && aprovL) aprovL.href = d.urls.aprovar || '#';
        if (d.pode_aprovar && d.urls && d.urls.reprovar) {
            window._gcModalRejectData = {
                reprovarUrl: d.urls.reprovar,
                tags: d.tags_erro_reprovacao || [],
            };
        }

        var secExc = document.getElementById('gc-sec-exclusao');
        if (secExc) {
            if (d.exclusao_pendente) {
                secExc.style.display = 'block';
                setText('gc-exc-solicitante', d.exclusao_pendente.solicitado_por);
                setText('gc-exc-data', d.exclusao_pendente.data);
                var mot = document.getElementById('gc-exc-motivo');
                if (mot) mot.textContent = d.exclusao_pendente.motivo || '—';
                var excAct = document.getElementById('gc-exc-actions');
                if (excAct) excAct.style.display = d.pode_aprovar_exclusao ? 'flex' : 'none';
                var a1 = document.getElementById('gc-exc-link-aprovar');
                var a2 = document.getElementById('gc-exc-link-rejeitar');
                if (a1 && d.urls) a1.href = d.urls.aprovar_exclusao;
                if (a2 && d.urls) a2.href = d.urls.rejeitar_exclusao;
            } else {
                secExc.style.display = 'none';
            }
        }

        var verMais = document.getElementById('gc-ver-mais-body');
        if (verMais) {
            verMais.classList.remove('is-open');
            var btnVm = document.getElementById('gc-ver-mais-btn');
            if (btnVm) btnVm.textContent = 'Ver mais sobre o fluxo de aprovação';
            if (d.aprovacoes_fluxo && d.aprovacoes_fluxo.length) {
                verMais.innerHTML = d.aprovacoes_fluxo.map(function (a) {
                    return '<div class="gc-hist-item" style="border:none;padding:0.35rem 0;">' +
                        '<div class="gc-hist-dot ' + (a.decisao === 'aprovado' ? 'aprovado' : 'reprovado') + '"></div>' +
                        '<div><div class="gc-hist-status">' + escapeHtml(a.decisao_display) + '</div>' +
                        '<div class="gc-hist-meta">' + escapeHtml(a.por) + ' · ' + escapeHtml(a.data || '') + '</div>' +
                        (a.comentario ? '<div style="margin-top:0.25rem;color:#475569;">' + escapeHtml(a.comentario) + '</div>' : '') +
                        '</div></div>';
                }).join('');
            } else {
                verMais.innerHTML = '<p style="margin:0;color:#64748b;">Nenhum registro de aprovação/reprovação ainda.</p>';
            }
        }

        var al = document.getElementById('gc-activities-list');
        if (al) {
            if (d.atividades && d.atividades.length) {
                al.innerHTML = d.atividades.map(function (a) {
                    var dotCls = (a.status_dot || '').trim();
                    var det = (a.detalhes || '').trim();
                    var tit = (a.titulo || '').trim();
                    var showDet = det && det !== tit;
                    return '<div class="gc-act-item">' +
                        '<div class="gc-act-dot ' + escapeHtml(dotCls) + '"></div>' +
                        '<div><div class="gc-act-title">' + escapeHtml(tit || 'Atividade') + '</div>' +
                        '<div class="gc-act-meta">' + escapeHtml(a.por || '—') +
                        ' · ' + escapeHtml(a.data || '') + '</div>' +
                        (showDet ? '<div class="gc-act-details">' + escapeHtml(det) + '</div>' : '') +
                        '</div></div>';
                }).join('');
            } else {
                al.innerHTML = '<p class="gc-side-empty">Nenhuma atividade registrada.</p>';
            }
        }

        var anex = document.getElementById('gc-anexos-grid');
        if (anex) {
            var parts = [];
            if (d.anexos && d.anexos.length) {
                d.anexos.forEach(function (x) {
                    var thumb = x.eh_imagem
                        ? '<img src="' + escapeHtml(x.url) + '" alt="">'
                        : GC_DOC_SVG;
                    parts.push(
                        '<a class="gc-anexo-tile" href="' + escapeHtml(x.url) + '" target="_blank" rel="noopener">' +
                        '<div class="gc-anexo-tile-inner">' + thumb +
                        '<span class="gc-anexo-tile-name">' + escapeHtml(x.nome) + '</span></div></a>'
                    );
                });
            }
            if (d.pode_adicionar_anexo && d.urls && d.urls.upload_anexo) {
                parts.push(
                    '<a class="gc-anexo-tile gc-anexo-tile--add" href="' + escapeHtml(d.urls.upload_anexo) + '">' +
                    '<span class="gc-anexo-add-plus">+</span>' +
                    '<span class="gc-anexo-add-label">Adicionar</span></a>'
                );
            }
            if (parts.length) {
                anex.innerHTML = parts.join('');
            } else {
                anex.innerHTML = '<p class="gc-anexos-empty">Nenhum anexo.</p>';
            }
        }

        var hist = document.getElementById('gc-historico-list');
        if (hist) {
            if (d.historico_status && d.historico_status.length) {
                hist.innerHTML = d.historico_status.map(function (h) {
                    var cls = h.status || '';
                    var obs = (h.obs || '').trim();
                    return '<div class="gc-hist-item">' +
                        '<div class="gc-hist-dot ' + escapeHtml(cls) + '"></div>' +
                        '<div><div class="gc-hist-status">' + escapeHtml(h.status_display) + '</div>' +
                        '<div class="gc-hist-meta">' + escapeHtml(h.por) +
                        ' · ' + escapeHtml(h.data || '') + '</div>' +
                        (obs ? '<div class="gc-hist-obs">' + escapeHtml(obs) + '</div>' : '') +
                        '</div></div>';
                }).join('');
            } else {
                hist.innerHTML = '<p style="color:#94a3b8;font-size:0.85rem;">Sem registros de mudança de status.</p>';
            }
        }

        var cl = document.getElementById('gc-comments-list');
        if (cl) {
            if (d.comentarios && d.comentarios.length) {
                cl.innerHTML = d.comentarios.map(function (c) {
                    return '<div class="gc-comment-item">' +
                        '<div class="gc-comment-avatar">' + escapeHtml(c.iniciais || '?') + '</div>' +
                        '<div class="gc-comment-body">' +
                        '<div class="gc-comment-author">' + escapeHtml(c.autor) +
                        ' <span class="gc-comment-date">' + escapeHtml(c.data || '') + '</span></div>' +
                        '<div class="gc-comment-text">' + escapeHtml(c.texto) + '</div></div></div>';
                }).join('');
            } else {
                cl.innerHTML = '<p class="gc-side-empty">Nenhum comentário ainda.</p>';
            }
        }

        var cf = document.getElementById('gc-comment-form');
        if (cf) cf.style.display = d.pode_comentar ? 'flex' : 'none';
        var ta = document.getElementById('gc-comment-text');
        if (ta) ta.value = '';

        var u = d.urls || {};
        function setHref(id, href) {
            var el = document.getElementById(id);
            if (el) el.href = href || '#';
        }
        setHref('gc-ft-pdf', u.exportar_pdf);
        setHref('gc-ft-leitura', u.leitura_pdf);
        setHref('gc-ft-editar', u.editar);
        var ftEdit = document.getElementById('gc-ft-editar');
        if (ftEdit) ftEdit.style.display = d.pode_editar ? 'inline-flex' : 'none';

        var secReprov = document.getElementById('gc-sec-reprovado');
        var repCta = document.getElementById('gc-reprovado-cta');
        var showReprovHelp = d.status === 'reprovado' && d.pode_editar;
        if (secReprov) secReprov.style.display = showReprovHelp ? 'block' : 'none';
        if (repCta) setHref('gc-reprovado-cta', u.editar);

        var ftEditLabel = document.getElementById('gc-ft-editar-label');
        if (ftEdit && ftEditLabel && d.pode_editar) {
            if (d.status === 'reprovado') {
                ftEditLabel.textContent = 'Reenviar para Reavaliação';
                ftEdit.classList.add('gc-footer-btn--reenviar');
                ftEdit.classList.remove('gc-footer-btn--primary');
            } else {
                ftEditLabel.textContent = 'Editar';
                ftEdit.classList.remove('gc-footer-btn--reenviar');
                ftEdit.classList.add('gc-footer-btn--primary');
            }
        }

        var ftExc = document.getElementById('gc-ft-exclusao');
        if (ftExc) {
            var showExc = d.pode_solicitar_exclusao && !d.exclusao_pendente;
            ftExc.style.display = showExc ? 'inline-flex' : 'none';
            setHref('gc-ft-exclusao', u.solicitar_exclusao);
        }

        syncGestaoListaPedidoRowFromModal(d);
    };

    window.enviarComentarioModal = function () {
        var pk = window._gcModalCurrentPk;
        var u = window._gcModalUrls;
        if (!pk || !u || !u.comentar) return;
        var ta = document.getElementById('gc-comment-text');
        var texto = (ta && ta.value) ? ta.value.trim() : '';
        if (!texto) {
            alert('Digite um comentário.');
            return;
        }
        var fd = new FormData();
        fd.append('texto', texto);
        fd.append('csrfmiddlewaretoken', getCsrfToken());
        fetch(u.comentar, {
            method: 'POST',
            body: fd,
            credentials: 'same-origin',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                Accept: 'application/json',
            },
        })
            .then(function (r) {
                return r.text().then(function (text) {
                    try {
                        return { body: JSON.parse(text), parsed: true, httpOk: r.ok };
                    } catch (err) {
                        return { body: null, parsed: false, httpOk: r.ok, status: r.status };
                    }
                });
            })
            .then(function (res) {
                if (res.body && res.body.ok) {
                    switchGcPedidoSideTab('comments');
                    return window.abrirModalPedido(pk);
                }
                var msg =
                    res.body && res.body.error
                        ? res.body.error
                        : 'Não foi possível enviar o comentário.';
                alert(msg);
            })
            .catch(function () {
                alert('Erro de rede ao enviar comentário.');
            });
    };

    window.enviarReprovarModal = function () {
        var pk = window._gcModalCurrentPk;
        var data = window._gcModalRejectData;
        if (!pk || !data || !data.reprovarUrl) return;
        hideReprovarInlineError();
        var fd = new FormData();
        fd.append('csrfmiddlewaretoken', getCsrfToken());
        var com = document.getElementById('gc-reprovar-comentario');
        fd.append('comentario', com ? com.value.trim() : '');
        var hidden = document.getElementById('gc-reprovar-novas-hidden');
        fd.append('novas_tags', hidden ? hidden.value.trim() : '');
        var wrap = document.getElementById('gc-reprovar-tags');
        if (wrap) {
            wrap.querySelectorAll('input[type="checkbox"]:checked').forEach(function (cb) {
                fd.append('tags_erro', cb.value);
            });
        }
        var sub = document.getElementById('gc-reprovar-submit');
        if (sub) sub.disabled = true;
        fetch(data.reprovarUrl, {
            method: 'POST',
            body: fd,
            credentials: 'same-origin',
            redirect: 'manual',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json',
            },
        })
            .then(function (r) {
                return r.text().then(function (text) {
                    try {
                        return { body: JSON.parse(text), isJson: true };
                    } catch (err) {
                        return { isJson: false };
                    }
                });
            })
            .then(function (res) {
                if (sub) sub.disabled = false;
                if (!res.isJson || !res.body) {
                    showReprovarInlineError('Não foi possível concluir a reprovação. Atualize a página e tente novamente.');
                    return;
                }
                if (res.body.ok) {
                    window.fecharReprovarSheet();
                    window._gcListaPedidosAlterada = true;
                    window.abrirModalPedido(pk);
                    return;
                }
                showReprovarInlineError(res.body.error || 'Não foi possível reprovar.');
            })
            .catch(function () {
                if (sub) sub.disabled = false;
                showReprovarInlineError('Erro de rede. Verifique sua conexão e tente novamente.');
            });
    };

    window.abrirModalPedido = async function (pk) {
        var overlay = garantirOverlayNoBody();
        var modal = document.getElementById('gc-modal');
        if (!overlay || !window.GC_WORKORDER_JSON_URL) return;
        overlay.scrollTop = 0;
        overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        document.documentElement.style.overflow = 'hidden';
        if (modal) modal.setAttribute('aria-busy', 'true');
        if (typeof window.modalPedidoResetParaCarregar === 'function') {
            window.modalPedidoResetParaCarregar();
        }
        try {
            var url = window.GC_WORKORDER_JSON_URL(pk);
            var r = await fetch(url, {
                credentials: 'same-origin',
                cache: 'no-store',
                headers: {
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache',
                },
            });
            if (r.status === 403) {
                var err = await r.json().catch(function () { return {}; });
                alert(err.error || 'Sem permissão.');
                window.fecharModalPedido();
                return;
            }
            if (!r.ok) throw new Error('HTTP ' + r.status);
            var d = await r.json();
            window._gcModalCurrentPk = pk;
            window._gcModalUrls = d.urls;
            window.preencherModalPedido(d);
        } catch (e) {
            console.error(e);
            alert('Não foi possível carregar os dados do pedido.');
            window.fecharModalPedido();
        } finally {
            if (modal) modal.removeAttribute('aria-busy');
        }
    };

    document.addEventListener('DOMContentLoaded', function () {
        gcReprovarNovasRender();

        var reprovarBtn = document.getElementById('gc-reprovar-btn');
        if (reprovarBtn) {
            reprovarBtn.addEventListener('click', function (e) {
                e.preventDefault();
                window.abrirReprovarSheet();
            });
        }

        var rov = getReprovarOverlayEl();
        if (rov) {
            rov.addEventListener('click', function (e) {
                if (e.target === rov) window.fecharReprovarSheet();
            });
        }

        var rc = document.getElementById('gc-reprovar-close');
        if (rc) rc.addEventListener('click', function () { window.fecharReprovarSheet(); });

        var rcan = document.getElementById('gc-reprovar-cancel');
        if (rcan) rcan.addEventListener('click', function () { window.fecharReprovarSheet(); });

        var rsub = document.getElementById('gc-reprovar-submit');
        if (rsub) rsub.addEventListener('click', function () { window.enviarReprovarModal(); });

        var rnovaIn = document.getElementById('gc-reprovar-nova-input');
        var rnovaAdd = document.getElementById('gc-reprovar-nova-add');
        if (rnovaAdd && rnovaIn) {
            rnovaAdd.addEventListener('click', function () {
                gcReprovarNovasAdd(rnovaIn.value);
                rnovaIn.value = '';
                rnovaIn.focus();
            });
            rnovaIn.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    gcReprovarNovasAdd(rnovaIn.value);
                    rnovaIn.value = '';
                }
            });
        }

        var overlay = garantirOverlayNoBody();
        if (overlay) {
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) window.fecharModalPedido();
            });
        }

        var tabComments = document.getElementById('gc-tab-btn-comments');
        var tabActivities = document.getElementById('gc-tab-btn-activities');
        if (tabComments) {
            tabComments.addEventListener('click', function () {
                switchGcPedidoSideTab('comments');
            });
        }
        if (tabActivities) {
            tabActivities.addEventListener('click', function () {
                switchGcPedidoSideTab('activities');
            });
        }

        document.addEventListener('keydown', function (e) {
            if (e.key !== 'Escape') return;
            var ro = getReprovarOverlayEl();
            if (ro && ro.classList.contains('is-open')) {
                window.fecharReprovarSheet();
                e.preventDefault();
                return;
            }
            window.fecharModalPedido();
        });
    });
})();
