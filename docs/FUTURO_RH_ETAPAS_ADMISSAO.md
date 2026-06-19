# Futuro: Etapas extras no fluxo de admissão (RH)

Documento de **backlog / visão** — **não implementado** (decisão em jun/2026: adiar).

Complementa o que já existe: fluxo fixo em 5 etapas + módulo **Papéis do fluxo** (`/rh/papeis/`) para definir responsáveis por etapa.

---

## 1. Contexto da decisão

Foi avaliado um editor **100% personalizável** (“+ etapa”, modal, reordenar, etapas ilimitadas). Conclusão:

- **Não fazer agora** — esforço alto, risco de UX confusa, pouco retorno para a maioria dos RH.
- O problema principal (**quem faz o quê**) já está coberto por `PapelFluxoAdmissao`.
- O fluxo brasileiro típico (requisição → docs → validação → contrato → ativo) é estável; variações são pontos de aprovação/checklist, não fluxos totalmente diferentes.

---

## 2. Se retomar no futuro — abordagem recomendada

**Não** começar por construtor livre. Preferir, em ordem:

### Opção A — Biblioteca de etapas opcionais (recomendada)

Etapas **pré-definidas** que ligam/desligam em configuração, cada uma com papel, notificações e ações prontas.

Candidatos comuns:

| Etapa opcional | Onde encaixa | Exemplo de responsável |
|----------------|--------------|------------------------|
| Aprovação SESMT / medicina | Após docs ou antes do contrato | Papel `sesmt` |
| Aprovação diretoria | Após validação final | Papel `diretoria` |
| Exame admissional (ASO pendente) | Paralelo ou subfluxo etapa 2 | Papel `conferencia_docs` ou novo |
| Checklist pré-ativo (eSocial, crachá) | Antes ou após etapa 5 | Papel `onboarding` |

### Opção B — Checklists configuráveis **dentro** de etapas existentes

Itens marcáveis na etapa 3 ou 4 (sem novo número no stepper). Menor impacto técnico.

### Opção C — Template de fluxo por tipo de contrato / obra

CLT vs temporário vs obra X com sequência pré-montada — não editor etapa a etapa.

### Opção D — Motor BPM completo (só se virar produto enterprise)

Etapas dinâmicas, tipos, transições, condições. **Último recurso** — reescreve `etapa_admissao`, portal, notificações, histórico, testes.

---

## 3. Impacto técnico (se for além de papéis)

| Área | Hoje | Com etapas dinâmicas |
|------|------|----------------------|
| `Colaborador.etapa_admissao` | `1..5` fixo | FK ou ordem configurável |
| Stepper / templates | Labels fixos | Render dinâmico |
| `PapelFluxoAdmissao` | 4 papéis seed | N papéis ou papéis por etapa custom |
| Portal candidato | Regras por etapa 2 + pendência | Regras por tipo de etapa |
| Notificações | Por papel fixo | Por etapa + papel |
| `admissao_actions.py` | Switch por etapa | Motor de transição |

Estimativa grosseira Opção A (2 etapas opcionais): **médio** (1–2 sprints). Opção D: **muito alto** (produto novo).

---

## 4. Pré-requisitos antes de codar

1. Listar **1–2 etapas extras reais** que a Lplan usa (não hipotéticas).
2. Definir **quem aprova** e **o que desbloqueia** (contrato? ativo?).
3. Confirmar se candidato participa ou só RH/gestor.
4. Validar com usuários se stepper com mais de 5 passos ainda é legível.

---

## 5. Referências no código atual

- Papéis: `recursos_humanos/models.py` → `PapelFluxoAdmissao`
- Serviço: `recursos_humanos/services/papeis_fluxo.py`
- Tela config: `/rh/papeis/` → `papeis_fluxo_view`
- Fluxo: `recursos_humanos/services/admissao_actions.py`, `admissao.py`
- Documentação de lacunas já corrigidas: conversa jun/2026 (critério docs unificado, notificações por papel, portal com trava)

---

## 6. Gatilho para reabrir este item

Reabrir quando o usuário disser algo como:

- “Preciso de etapa de SESMT / diretoria”
- “Quero ligar etapa opcional X no `/rh/papeis/`”
- “Implementar FUTURO_RH_ETAPAS_ADMISSAO Opção A”

Até lá: manter fluxo fixo + papéis configuráveis.
