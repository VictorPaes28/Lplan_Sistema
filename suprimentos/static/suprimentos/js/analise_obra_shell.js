(function() {
  const saved = localStorage.getItem('lplan-bi-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  window.addEventListener('DOMContentLoaded', function() {
    if (typeof updateThemeUI === 'function') updateThemeUI(saved);
  });
})();

function updateThemeUI(theme) {
  const box = document.getElementById('theme-icon-box');
  const svg = document.getElementById('theme-svg');
  const pill = document.getElementById('theme-pill');
  const knob = document.getElementById('theme-knob');
  const label = document.getElementById('theme-label');
  const sub = document.getElementById('theme-sub');
  if (theme === 'light') {
    if (box) box.style.background = 'rgba(99,102,241,0.18)';
    if (svg) {
      svg.setAttribute('stroke', '#818cf8');
      svg.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>';
    }
    if (pill) pill.style.background = '#6366f1';
    if (knob) { knob.style.transform = 'translateX(14px)'; knob.style.background = '#fff'; }
    if (label) label.textContent = 'Modo escuro';
    if (sub) sub.textContent = 'Tema atual: claro';
  } else {
    if (box) box.style.background = 'rgba(245,158,11,0.18)';
    if (svg) {
      svg.setAttribute('stroke', '#f59e0b');
      svg.innerHTML = '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>';
    }
    if (pill) pill.style.background = 'rgba(255,255,255,0.15)';
    if (knob) { knob.style.transform = 'translateX(0)'; knob.style.background = 'rgba(255,255,255,0.45)'; }
    if (label) label.textContent = 'Modo claro';
    if (sub) sub.textContent = 'Tema atual: escuro';
  }
}

function toggleTheme() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const next = isDark ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('lplan-bi-theme', next);
  updateThemeUI(next);
}

function setIndexOpenState(open) {
  const panel = document.getElementById('bi-index');
  const btn = document.querySelector('.index-toggle-btn');
  if (!panel) return;
  panel.classList.toggle('open', !!open);
  if (btn) {
    btn.classList.toggle('is-open', !!open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
}

function toggleIndex() {
  const panel = document.getElementById('bi-index');
  if (!panel) return;
  setIndexOpenState(!panel.classList.contains('open'));
}

function toggleDias() {
  const expandido = document.getElementById('dias-expandido');
  const btn = document.getElementById('btn-ver-mais-dias');
  const icon = document.getElementById('icon-ver-mais-dias');
  if (!expandido || !btn || !icon) return;
  const aberto = expandido.style.display !== 'none';

  if (aberto) {
    expandido.style.display = 'none';
    btn.childNodes[0].textContent = 'Ver mais ';
    icon.innerHTML = '<polyline points="6 9 12 15 18 9"/>';
  } else {
    expandido.style.display = 'block';
    btn.childNodes[0].textContent = 'Ver menos ';
    icon.innerHTML = '<polyline points="18 15 12 9 6 15"/>';
  }
}

function toggleBlocos() {
  const expandido = document.getElementById('blocos-expandido');
  const btn = document.getElementById('btn-ver-mais-blocos');
  const icon = document.getElementById('icon-ver-mais-blocos');
  if (!expandido || !btn || !icon) return;
  const aberto = expandido.style.display !== 'none';

  if (aberto) {
    expandido.style.display = 'none';
    btn.childNodes[0].textContent = 'Ver mais ';
    icon.innerHTML = '<polyline points="6 9 12 15 18 9"/>';
  } else {
    expandido.style.display = 'block';
    btn.childNodes[0].textContent = 'Ver menos ';
    icon.innerHTML = '<polyline points="18 15 12 9 6 15"/>';
  }
}

function toggleAtividades() {
  const expandido = document.getElementById('atividades-expandido');
  const btn = document.getElementById('btn-ver-mais-atividades');
  const icon = document.getElementById('icon-ver-mais-atividades');
  if (!expandido || !btn || !icon) return;
  const aberto = expandido.style.display !== 'none';

  if (aberto) {
    expandido.style.display = 'none';
    btn.childNodes[0].textContent = 'Ver mais ';
    icon.innerHTML = '<polyline points="6 9 12 15 18 9"/>';
  } else {
    expandido.style.display = 'block';
    btn.childNodes[0].textContent = 'Ver menos ';
    icon.innerHTML = '<polyline points="18 15 12 9 6 15"/>';
  }
}

function toggleTipos() {
  const expandido = document.getElementById('tipos-expandido');
  const btn = document.getElementById('btn-ver-mais-tipos');
  const icon = document.getElementById('icon-ver-mais-tipos');
  if (!expandido || !btn || !icon) return;
  const aberto = expandido.style.display !== 'none';

  if (aberto) {
    expandido.style.display = 'none';
    btn.childNodes[0].textContent = 'Ver mais ';
    icon.innerHTML = '<polyline points="6 9 12 15 18 9"/>';
  } else {
    expandido.style.display = 'block';
    btn.childNodes[0].textContent = 'Ver menos ';
    icon.innerHTML = '<polyline points="18 15 12 9 6 15"/>';
  }
}

function toggleResponsaveis() {
  const expandido = document.getElementById('responsaveis-expandido');
  const btn = document.getElementById('btn-ver-mais-responsaveis');
  const icon = document.getElementById('icon-ver-mais-responsaveis');
  if (!expandido || !btn || !icon) return;
  const aberto = expandido.style.display !== 'none';

  if (aberto) {
    expandido.style.display = 'none';
    btn.childNodes[0].textContent = 'Ver mais ';
    icon.innerHTML = '<polyline points="6 9 12 15 18 9"/>';
  } else {
    expandido.style.display = 'block';
    btn.childNodes[0].textContent = 'Ver menos ';
    icon.innerHTML = '<polyline points="18 15 12 9 6 15"/>';
  }
}

function toggleAtrasadas() {
  const expandido = document.getElementById('atrasadas-expandido');
  const btn = document.getElementById('btn-ver-mais-atrasadas');
  const icon = document.getElementById('icon-ver-mais-atrasadas');
  if (!expandido || !btn || !icon) return;
  const aberto = expandido.style.display !== 'none';

  if (aberto) {
    expandido.style.display = 'none';
    btn.childNodes[0].textContent = 'Ver mais ';
    icon.innerHTML = '<polyline points="6 9 12 15 18 9"/>';
  } else {
    expandido.style.display = 'block';
    btn.childNodes[0].textContent = 'Ver menos ';
    icon.innerHTML = '<polyline points="18 15 12 9 6 15"/>';
  }
}

function trocarObra(select) {
  const obraId = select.value;
  // Redirecionar para a mesma URL mas com a nova obra e sem datas
  // (sem datas o servidor vai usar o padrão: data_inicio da obra e hoje)
  const url = new URL(window.location.href);
  url.searchParams.set('obra', obraId);
  url.searchParams.delete('front');
  url.searchParams.delete('data_inicio');
  url.searchParams.delete('data_fim');
  window.location.href = url.toString();
}

document.addEventListener('click', function(e) {
  const panel = document.getElementById('bi-index');
  const btn = document.querySelector('.index-toggle-btn');
  if (panel && panel.classList.contains('open') && !panel.contains(e.target) && btn && !btn.contains(e.target)) {
    setIndexOpenState(false);
  }
});

const biSections = [
  { id: 'hero',    idx: 0 },
  { id: 'bloco-1', idx: 1 },
  { id: 'bloco-2', idx: 2 },
  { id: 'bloco-3', idx: 3 },
  { id: 'bloco-4', idx: 4 },
  { id: 'bloco-5', idx: 5 },
  { id: 'bloco-6', idx: 6 },
];

function updateActive() {
  const scrollTop = window.scrollY || document.documentElement.scrollTop;
  const windowH = window.innerHeight;
  let current = 0;

  biSections.forEach(function(s) {
    const el = document.getElementById(s.id);
    if (!el) return;
    const top = el.getBoundingClientRect().top;
    // Marca como ativa a última seção cujo topo já passou de 30% da tela
    if (top < windowH * 0.35) {
      current = s.idx;
    }
  });

  document.querySelectorAll('.index-item').forEach(function(item, i) {
    item.classList.toggle('active', i === current);
  });
}

// Usar IntersectionObserver para detectar seção visível ao rolar
const observerOptions = {
  root: null,
  rootMargin: '-30% 0px -60% 0px',
  threshold: 0
};

const sectionObserver = new IntersectionObserver(function(entries) {
  entries.forEach(function(entry) {
    if (entry.isIntersecting) {
      const id = entry.target.id;
      const idx = biSections.findIndex(s => s.id === id);
      if (idx !== -1) {
        document.querySelectorAll('.index-item').forEach(function(item, i) {
          item.classList.toggle('active', i === idx);
        });
      }
    }
  });
}, observerOptions);

biSections.forEach(function(s) {
  const el = document.getElementById(s.id);
  if (el) sectionObserver.observe(el);
});

window.addEventListener('load', updateActive);
document.addEventListener('DOMContentLoaded', updateActive);

// Ao clicar num item do índice, manter painel aberto e atualizar estado ativo após scroll
document.querySelectorAll('.index-item').forEach(function(item) {
  item.addEventListener('click', function() {
    setTimeout(updateActive, 400);
  });
});

(function() {
  'use strict';
  function initSidebar() {
    var sidebar = document.getElementById('sidebar');
    var overlay = document.getElementById('mobile-sidebar-overlay');
    var toggleBtn = document.getElementById('mobile-sidebar-toggle');
    var mainWrapper = document.querySelector('.main-content-wrapper');
    var desktopDefaultCollapsed = sidebar && sidebar.dataset.defaultCollapsed === '1';
    if (!sidebar) return;

    function setDesktopSidebarCollapsed(collapsed) {
      var isDesktop = window.innerWidth >= 768;
      if (!isDesktop) return;
      document.body.classList.toggle('sidebar-collapsed', !!collapsed);
      sidebar.classList.toggle('is-collapsed', !!collapsed);
      if (mainWrapper) {
        if (desktopDefaultCollapsed) {
          mainWrapper.classList.add('sidebar-wrapper-collapsed');
          mainWrapper.style.marginLeft = '5.25rem';
          mainWrapper.style.width = 'calc(100% - 5.25rem)';
        } else {
          mainWrapper.classList.toggle('sidebar-wrapper-collapsed', !!collapsed);
          mainWrapper.style.marginLeft = collapsed ? '5.25rem' : '16rem';
          mainWrapper.style.width = collapsed ? 'calc(100% - 5.25rem)' : 'calc(100% - 16rem)';
        }
      }
      document.querySelectorAll('#sidebar .sidebar-link').forEach(function (link) {
        var label = (link.textContent || '').trim().replace(/\s+/g, ' ');
        if (label) link.setAttribute('title', label);
      });
    }

    function closeSidebar() {
      if (window.innerWidth < 768) {
        sidebar.style.transform = 'translateX(-100%)';
        if (overlay) overlay.style.display = 'none';
      }
    }
    function updateSidebar() {
      var isDesktop = window.innerWidth >= 768;
      if (isDesktop) {
        if (overlay) overlay.style.display = 'none';
        setDesktopSidebarCollapsed(desktopDefaultCollapsed);
      } else {
        document.body.classList.remove('sidebar-collapsed');
        sidebar.classList.remove('is-collapsed');
        if (mainWrapper) {
          mainWrapper.classList.remove('sidebar-wrapper-collapsed');
          mainWrapper.style.marginLeft = '';
          mainWrapper.style.width = '';
        }
        var ct = window.getComputedStyle(sidebar).transform;
        var open = ct === 'none' || ct.indexOf('matrix(1, 0, 0, 1, 0, 0)') !== -1 || sidebar.style.transform === 'translateX(0)';
        if (!open) sidebar.style.transform = 'translateX(-100%)';
      }
    }
    updateSidebar();
    window.addEventListener('pageshow', updateSidebar);
    window.addEventListener('resize', function() {
      setTimeout(updateSidebar, 100);
    });
    if (toggleBtn && overlay) {
      toggleBtn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        if (window.innerWidth < 768) {
          var ct = sidebar.style.transform || window.getComputedStyle(sidebar).transform;
          var isOpen = ct === 'none' || ct === '' || ct.indexOf('translateX(0)') !== -1 || ct.indexOf('matrix(1, 0, 0, 1, 0, 0)') !== -1;
          if (isOpen) closeSidebar();
          else {
            sidebar.style.transform = 'translateX(0)';
            overlay.style.display = 'block';
          }
        }
      });
      overlay.addEventListener('click', closeSidebar);
    }

    if (desktopDefaultCollapsed) {
      var hoverOpenTimer = null;
      var hoverCloseTimer = null;
      sidebar.addEventListener('mouseenter', function() {
        if (window.innerWidth < 768) return;
        if (hoverOpenTimer) clearTimeout(hoverOpenTimer);
        if (hoverCloseTimer) { clearTimeout(hoverCloseTimer); hoverCloseTimer = null; }
        hoverOpenTimer = setTimeout(function () {
          setDesktopSidebarCollapsed(false);
          hoverOpenTimer = null;
        }, 130);
      });
      sidebar.addEventListener('mouseleave', function() {
        if (window.innerWidth < 768) return;
        if (hoverOpenTimer) { clearTimeout(hoverOpenTimer); hoverOpenTimer = null; }
        if (hoverCloseTimer) clearTimeout(hoverCloseTimer);
        hoverCloseTimer = setTimeout(function () {
          setDesktopSidebarCollapsed(true);
          hoverCloseTimer = null;
        }, 170);
      });
      sidebar.addEventListener('focusin', function() {
        if (window.innerWidth < 768) return;
        if (hoverOpenTimer) { clearTimeout(hoverOpenTimer); hoverOpenTimer = null; }
        if (hoverCloseTimer) { clearTimeout(hoverCloseTimer); hoverCloseTimer = null; }
        setDesktopSidebarCollapsed(false);
      });
      sidebar.addEventListener('focusout', function() {
        if (window.innerWidth < 768) return;
        setTimeout(function () {
          if (!sidebar.contains(document.activeElement)) {
            setDesktopSidebarCollapsed(true);
          }
        }, 0);
      });
    }
  }
  function initUserMenu() {
    var container = document.getElementById('user-menu-container');
    var button = document.getElementById('user-menu-button');
    var dropdown = document.getElementById('user-menu-dropdown');
    var chevron = document.getElementById('user-menu-chevron');
    if (!container || !button || !dropdown) return;
    var isOpen = false;
    function toggleDropdown(e) {
      if (e) { e.preventDefault(); e.stopPropagation(); }
      isOpen = !isOpen;
      if (isOpen) {
        dropdown.style.display = 'block';
        dropdown.style.visibility = 'visible';
        dropdown.style.opacity = '1';
        button.setAttribute('aria-expanded', 'true');
        if (chevron) chevron.style.transform = 'rotate(180deg)';
      } else {
        dropdown.style.display = 'none';
        dropdown.style.visibility = 'hidden';
        dropdown.style.opacity = '0';
        button.setAttribute('aria-expanded', 'false');
        if (chevron) chevron.style.transform = 'rotate(0deg)';
      }
    }
    button.addEventListener('click', toggleDropdown);
    document.addEventListener('click', function(e) {
      if (isOpen && container && !container.contains(e.target)) {
        isOpen = false;
        dropdown.style.display = 'none';
        dropdown.style.visibility = 'hidden';
        dropdown.style.opacity = '0';
        button.setAttribute('aria-expanded', 'false');
        if (chevron) chevron.style.transform = 'rotate(0deg)';
      }
    });
  }
  function initShell() {
    initSidebar();
    initUserMenu();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initShell);
  } else {
    initShell();
  }
})();

function toggleFiltrosAvancados() {
  var panel = document.getElementById('filtros-avancados');
  var btn = document.getElementById('btn-filtros-mais');
  if (!panel) return;
  var open = !panel.classList.contains('is-open');
  panel.classList.toggle('is-open', open);
  if (btn) btn.setAttribute('aria-expanded', open ? 'true' : 'false');
}
