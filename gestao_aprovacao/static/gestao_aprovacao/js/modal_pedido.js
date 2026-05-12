(function () {
    'use strict';

    function getCsrfToken() {
        var meta = document.querySelector('meta[name=csrf-token]');
        if (meta && meta.content) return meta.content.trim();
        var inp = document.querySelector('[name=csrfmiddlewaretoken]');
        if (inp && inp.value) return inp.value.trim();
        return '';
    }

    window.fecharModalPedido = function () {
        var overlay = document.getElementById('gc-overlay');
        if (overlay) overlay.style.display = 'none';
        document.body.style.overflow = '';
        window._gcModalCurrentPk = null;
        window._gcModalUrls = null;
    };

    function escapeHtml(s) {
        if (!s) return '';
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
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
        var hist = document.getElementById('gc-historico-list');
        if (hist) hist.innerHTML = '';
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
        ['gc-ft-pdf', 'gc-ft-leitura', 'gc-ft-editar', 'gc-ft-exclusao', 'gc-aprov-link', 'gc-reprovar-link'].forEach(
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
        var aprovL = document.getElementById('gc-aprov-link');
        var reprovL = document.getElementById('gc-reprovar-link');
        if (d.urls) {
            if (aprovL) aprovL.href = d.urls.aprovar || '#';
            if (reprovL) reprovL.href = d.urls.reprovar || '#';
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

        var hist = document.getElementById('gc-historico-list');
        if (hist) {
            if (d.historico_status && d.historico_status.length) {
                hist.innerHTML = d.historico_status.map(function (h) {
                    var cls = h.status || '';
                    return '<div class="gc-hist-item">' +
                        '<div class="gc-hist-dot ' + escapeHtml(cls) + '"></div>' +
                        '<div><div class="gc-hist-status">' + escapeHtml(h.status_display) + '</div>' +
                        '<div class="gc-hist-meta">' + escapeHtml(h.por) +
                        (h.obs ? ' · ' + escapeHtml(h.obs) : '') +
                        ' · ' + escapeHtml(h.data || '') + '</div></div></div>';
                }).join('');
            } else {
                hist.innerHTML = '<p style="color:#94a3b8;font-size:0.85rem;">Sem registros de mudança de status.</p>';
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
                cl.innerHTML = '<p style="color:#94a3b8;font-size:0.85rem;">Nenhum comentário ainda.</p>';
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

        var ftExc = document.getElementById('gc-ft-exclusao');
        if (ftExc) {
            var showExc = d.pode_solicitar_exclusao && !d.exclusao_pendente;
            ftExc.style.display = showExc ? 'inline-flex' : 'none';
            setHref('gc-ft-exclusao', u.solicitar_exclusao);
        }
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
            redirect: 'manual',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (r) {
            if (r.status === 302 || r.status === 303) {
                return window.abrirModalPedido(pk);
            }
            if (r.ok) return window.abrirModalPedido(pk);
            alert('Não foi possível enviar o comentário.');
        }).catch(function () {
            alert('Erro de rede ao enviar comentário.');
        });
    };

    window.abrirModalPedido = async function (pk) {
        var overlay = document.getElementById('gc-overlay');
        var modal = document.getElementById('gc-modal');
        if (!overlay || !window.GC_WORKORDER_JSON_URL) return;
        overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
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
        var overlay = document.getElementById('gc-overlay');
        /* Ancora no body: evita fixed relativo a ancestral com transform/contain (modal “no fundo” da página). */
        if (overlay && overlay.parentNode !== document.body) {
            document.body.appendChild(overlay);
        }
        if (overlay) {
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) window.fecharModalPedido();
            });
        }
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') window.fecharModalPedido();
        });
    });
})();
