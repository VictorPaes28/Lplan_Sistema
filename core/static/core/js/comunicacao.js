/**
 * UI da central de comunicação: guia recolhível e destaque em cards de opção.
 */
(function () {
  function initGuiaToggle() {
    document.querySelectorAll('.comunicacao-guia-toggle').forEach(function (btn) {
      var body = document.getElementById(btn.getAttribute('aria-controls'));
      if (!body) return;
      btn.addEventListener('click', function () {
        var open = btn.getAttribute('aria-expanded') === 'true';
        btn.setAttribute('aria-expanded', open ? 'false' : 'true');
        body.hidden = open;
        btn.classList.toggle('comunicacao-guia-toggle--fechado', open);
      });
    });
  }

  function initOpcaoCards() {
    document.querySelectorAll('.comunicacao-opcao-input').forEach(function (input) {
      input.addEventListener('change', function () {
        var grid = input.closest('.comunicacao-opcoes-grid');
        if (!grid) return;
        grid.querySelectorAll('.comunicacao-opcao-card').forEach(function (card) {
          card.classList.remove('comunicacao-opcao-card--ativa');
        });
        var card = input.closest('.comunicacao-opcao-card');
        if (card) card.classList.add('comunicacao-opcao-card--ativa');
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initGuiaToggle();
      initOpcaoCards();
    });
  } else {
    initGuiaToggle();
    initOpcaoCards();
  }
})();
