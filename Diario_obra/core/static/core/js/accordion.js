/**
 * Sistema Robusto de Accordion/Seções Expansíveis
 * Implementação profissional usando Event Delegation e classes CSS
 * Compatível com browsers modernos (ES5+ com fallbacks)
 * Pode ser usado em qualquer template do projeto
 */
(function() {
    'use strict';
    
    // Polyfill para closest() - compatibilidade IE11
    if (!Element.prototype.closest) {
        Element.prototype.closest = function(selector) {
            var element = this;
            while (element && element.nodeType === 1) {
                if (element.matches(selector)) {
                    return element;
                }
                element = element.parentElement;
            }
            return null;
        };
    }
    
    // Polyfill para matches() - compatibilidade IE11
    if (!Element.prototype.matches) {
        Element.prototype.matches = 
            Element.prototype.matchesSelector || 
            Element.prototype.mozMatchesSelector ||
            Element.prototype.msMatchesSelector || 
            Element.prototype.oMatchesSelector || 
            Element.prototype.webkitMatchesSelector ||
            function(s) {
                var matches = (this.document || this.ownerDocument).querySelectorAll(s),
                    i = matches.length;
                while (--i >= 0 && matches.item(i) !== this) {}
                return i > -1;            
            };
    }
    
    // Polyfill para CustomEvent - compatibilidade IE11
    (function() {
        if (typeof window.CustomEvent === 'function') return false;
        
        function CustomEvent(event, params) {
            params = params || { bubbles: false, cancelable: false, detail: undefined };
            var evt = document.createEvent('CustomEvent');
            evt.initCustomEvent(event, params.bubbles, params.cancelable, params.detail);
            return evt;
        }
        
        CustomEvent.prototype = window.Event.prototype;
        window.CustomEvent = CustomEvent;
    })();
    
    // Polyfill para forEach em NodeList - compatibilidade IE11
    if (window.NodeList && !NodeList.prototype.forEach) {
        NodeList.prototype.forEach = function(callback, thisArg) {
            thisArg = thisArg || window;
            for (var i = 0; i < this.length; i++) {
                callback.call(thisArg, this[i], i, this);
            }
        };
    }
    
    // Classe principal para gerenciar accordions (ES5 compatible)
    function AccordionManager() {
        this.sections = {};
        this.init();
    }
    
    AccordionManager.prototype.init = function() {
        // Inicializa todas as seções existentes
        this.initializeSections();
        
        // Event delegation para novos cliques
        this.setupEventDelegation();
    };
    
    AccordionManager.prototype.initializeSections = function() {
        var self = this;
        // Encontra todas as seções e inicializa seus estados
        var buttons = document.querySelectorAll('[data-toggle-section]');
        
        for (var i = 0; i < buttons.length; i++) {
            var button = buttons[i];
            var sectionId = button.getAttribute('data-toggle-section');
            var content = document.getElementById('section-' + sectionId + '-content');
            
            if (content) {
                // Salva referência
                this.sections[sectionId] = {
                    button: button,
                    content: content,
                    chevron: button.querySelector('.section-chevron')
                };
                
                // Sincroniza estado inicial
                this.syncState(sectionId);
            }
        }
    };
    
    AccordionManager.prototype.setupEventDelegation = function() {
        var self = this;
        // Event delegation - captura cliques em qualquer lugar do documento
        document.addEventListener('click', function(event) {
            var button = event.target.closest('[data-toggle-section]');
            
            if (button && button.hasAttribute('data-toggle-section')) {
                event.preventDefault();
                event.stopPropagation();
                
                var sectionId = button.getAttribute('data-toggle-section');
                self.toggle(sectionId);
            }
        });
    };
    
    AccordionManager.prototype.toggle = function(sectionId) {
        var section = this.sections[sectionId];
        
        if (!section) {
            if (console && console.warn) {
                console.warn('Seção não encontrada:', sectionId);
            }
            return;
        }
        
        var isExpanded = section.button.getAttribute('aria-expanded') === 'true';
        
        if (isExpanded) {
            this.collapse(sectionId);
        } else {
            this.expand(sectionId);
        }
    };
    
    AccordionManager.prototype.expand = function(sectionId) {
        var section = this.sections[sectionId];
        if (!section) return;
        
        // Remove classe collapsed primeiro para garantir transição suave
        if (section.content.classList) {
            section.content.classList.remove('section-collapsed');
        } else {
            section.content.className = section.content.className.replace(/\bsection-collapsed\b/g, '');
        }
        
        // Força reflow para garantir que a transição funcione
        section.content.offsetHeight;
        
        // Atualiza conteúdo - display primeiro, depois classes
        section.content.style.display = 'block';
        
        // Adiciona classe expanded imediatamente para iniciar animação
        if (section.content.classList) {
            section.content.classList.add('section-expanded');
        } else {
            section.content.className += ' section-expanded';
        }
        
        // Atualiza botão
        section.button.setAttribute('aria-expanded', 'true');
        if (section.button.classList) {
            section.button.classList.remove('section-collapsed');
            section.button.classList.add('section-expanded');
        } else {
            // Fallback para IE11
            section.button.className = section.button.className.replace(/\bsection-collapsed\b/g, '');
            section.button.className += ' section-expanded';
        }
        
        // Atualiza chevron com animação suave
        if (section.chevron) {
            section.chevron.style.transform = 'rotate(180deg)';
            if (section.chevron.classList) {
                section.chevron.classList.add('rotated');
            } else {
                section.chevron.className += ' rotated';
            }
        }
        
        // Trigger evento customizado
        this.dispatchEvent(sectionId, 'expanded');
    };
    
    AccordionManager.prototype.collapse = function(sectionId) {
        var section = this.sections[sectionId];
        if (!section) return;
        
        // Remove classe expanded primeiro para iniciar transição
        if (section.content.classList) {
            section.content.classList.remove('section-expanded');
            section.content.classList.add('section-collapsed');
        } else {
            section.content.className = section.content.className.replace(/\bsection-expanded\b/g, '');
            section.content.className += ' section-collapsed';
        }
        
        // Atualiza chevron imediatamente para feedback visual rápido
        if (section.chevron) {
            section.chevron.style.transform = 'rotate(0deg)';
            if (section.chevron.classList) {
                section.chevron.classList.remove('rotated');
            } else {
                section.chevron.className = section.chevron.className.replace(/\brotated\b/g, '');
            }
        }
        
        // Aguarda transição antes de esconder completamente
        var self = this;
        setTimeout(function() {
            section.content.style.display = 'none';
        }, 400); // Tempo da transição CSS
        
        // Atualiza botão
        section.button.setAttribute('aria-expanded', 'false');
        if (section.button.classList) {
            section.button.classList.remove('section-expanded');
            section.button.classList.add('section-collapsed');
        } else {
            // Fallback para IE11
            section.button.className = section.button.className.replace(/\bsection-expanded\b/g, '');
            section.button.className += ' section-collapsed';
        }
        
        // Trigger evento customizado
        this.dispatchEvent(sectionId, 'collapsed');
    };
    
    AccordionManager.prototype.syncState = function(sectionId) {
        var section = this.sections[sectionId];
        if (!section) return;
        
        var computedDisplay = window.getComputedStyle(section.content).display;
        var isExpanded = computedDisplay !== 'none';
        
        if (isExpanded) {
            section.button.setAttribute('aria-expanded', 'true');
            if (section.chevron) {
                section.chevron.style.transform = 'rotate(180deg)';
            }
        } else {
            section.button.setAttribute('aria-expanded', 'false');
            if (section.chevron) {
                section.chevron.style.transform = 'rotate(0deg)';
            }
        }
    };
    
    AccordionManager.prototype.dispatchEvent = function(sectionId, eventType) {
        try {
            var event = new CustomEvent('accordion:' + eventType, {
                detail: { sectionId: sectionId },
                bubbles: true
            });
            document.dispatchEvent(event);
        } catch (e) {
            // Fallback silencioso se CustomEvent não funcionar
            if (console && console.warn) {
                console.warn('Não foi possível disparar evento customizado:', e);
            }
        }
    };
    
    // Inicializa quando o DOM estiver pronto
    function initAccordion() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                window.accordionManager = new AccordionManager();
            });
        } else {
            window.accordionManager = new AccordionManager();
        }
    }
    
    // Função global para compatibilidade
    window.toggleSection = function(sectionId) {
        if (window.accordionManager) {
            window.accordionManager.toggle(sectionId);
        } else {
            if (console && console.warn) {
                console.warn('AccordionManager não inicializado ainda');
            }
        }
    };
    
    // Inicializa
    initAccordion();
})();

