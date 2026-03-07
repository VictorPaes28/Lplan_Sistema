# Roteiro para Screencast – Esqueleto Detalhado

Documento de apoio à gravação: **quem usa cada parte**, **em que ordem** mostrar e **como explorar** cada tela. Os dados vêm do seed: `python manage.py seed_dados_demo_completo`.

---

## 1. Quem usa o quê (personas)

| Módulo | Quem mais usa | Uso principal |
|--------|----------------|----------------|
| **Diário de Obra** | Engenheiro de campo, Mestre de obras, Fiscal | Registrar o dia (clima, atividades, fotos, ocorrências, progresso da EAP, mão de obra e equipamentos). Consultar relatórios e exportar PDF/Excel. |
| **Mapa de Suprimentos** | Engenheiro de planejamento, Suprimentos, Almoxarife | Levantamento de insumos por obra/local, acompanhar SC/PC, recebimentos, alocações e histórico. Dashboard de status. |
| **Gestão de Aprovação (GestControll)** | Gestor, Aprovador, Solicitante | Criar e acompanhar pedidos de obra, aprovar/reprovar, ver empresas/obras e permissões. |
| **Painel do sistema (Admin Central)** | Administrador, Staff | Gerenciar obras (core) e usuários sem usar o Django Admin. |

---

## 2. Ordem escolhida e motivo

1. **Login → Seleção de sistema** — contexto único de entrada.
2. **Diário de Obra** — fluxo principal do "dia a dia" da obra (relatórios, fotos, EAP).
3. **Mapa de Suprimentos** — suprimentos por obra e status (SC, recebimento, alocação).
4. **Gestão de Aprovação** — fluxo de pedidos e aprovação.
5. **Painel do sistema** — rápido, só para mostrar que existe.
6. **Fechamento** — volta à seleção e frase de encerramento.

Motivo: o espectador vê primeiro o **registro da obra** (Diário), depois **o que sustenta a obra** (Mapa) e **quem aprova gastos** (Gestão). Admin por último como "configuração".

---

## 3. Esqueleto cena a cena

Cada bloco tem: **Cena**, **Persona**, **Onde** (URL ou ação), **O que mostrar**, **Como explorar**, **Fala sugerida**.

---

### CENA 0 – Preparação (fora da gravação)

- Rodar `python manage.py seed_dados_demo_completo`.
- Subir `python manage.py runserver`.
- Navegador em tela cheia (ex.: 1920×1080), abas/notificações limpas.
- Usuário: `super1` (ou demo). Senha: `demo1234` se recém-criado.

---

### CENA 1 – Login

- **Onde:** `/login/`.
- **O que mostrar:** Campo usuário, senha, botão Entrar.
- **Como explorar:** Preencher usuário e senha → Entrar.
- **Fala:** "Acessamos o sistema com o usuário de demonstração."

---

### CENA 2 – Seleção de sistema (home)

- **Persona:** Qualquer usuário após login.
- **Onde:** `/select-system/`.
- **O que mostrar:** Os quatro cards: Diário de Obras, Mapa de Suprimentos, GestControll, Painel do sistema.
- **Como explorar:** Só narrar; não clicar ainda.
- **Fala:** "Após o login, o usuário escolhe o módulo: Diário para relatórios de obra, Mapa para suprimentos, GestControll para aprovação de pedidos e Painel do sistema para administração."

---

### CENA 3 – Diário: seleção de obra

- **Persona:** Engenheiro de campo / Mestre de obras.
- **Onde:** Clicar no card **Diário de Obras** → `/select-project/`.
- **O que mostrar:** Lista de projetos (cartões): Entreáguas, Okena, Marghot, Sunrise, Residencial Vista Verde.
- **Como explorar:** Clicar em um projeto (ex.: Entreáguas) para selecionar.
- **Fala:** "Selecionamos a obra com a qual vamos trabalhar."

---

### CENA 4 – Diário: Visão geral (Dashboard)

- **Persona:** Engenheiro de campo.
- **Onde:** `/dashboard/`.
- **O que mostrar:** KPIs (Relatórios, Atividades, Ocorrências, Comentários, Fotos, Vídeos); Calendário com legenda (Preenchido, Atraso, Rascunho); tabela Relatórios Recentes; Fotos recentes; Vídeos; Informações do projeto.
- **Como explorar:** Apontar KPIs; mostrar calendário; clicar em "Ver tudo" em Relatórios Recentes para ir à listagem.
- **Fala:** "No dashboard vemos o resumo da obra: quantidade de relatórios, atividades, ocorrências e fotos. O calendário mostra quais dias têm registro."

---

### CENA 5 – Diário: Listagem de relatórios

- **Persona:** Engenheiro de campo.
- **Onde:** Menu **Relatórios** → `/reports/`.
- **O que mostrar:** Filtros (pesquisa, data início/fim), tabela (Data, Nº, Status, Fotos, Ações), botão "Adicionar relatório".
- **Como explorar:** Aplicar filtro por período; clicar em uma linha para abrir o detalhe.
- **Fala:** "Em Relatórios temos todos os diários da obra. Podemos filtrar por data e abrir qualquer registro."

---

### CENA 6 – Diário: Detalhe de um relatório

- **Persona:** Engenheiro de campo.
- **Onde:** `/diaries/<id>/` (clique em relatório ou no calendário).
- **O que mostrar (ordem na página):** Cabeçalho (Voltar, data, nº); botão **Imprimir** (dropdown: PDF normal, PDF detalhado, PDF sem fotos, Excel); Editar/Excluir; Informações do relatório; Clima; Descrição geral; Fotos; Anexos; Ocorrências e tags; Acidentes / Paralisações / Riscos iminentes / Incidentes; Atividades (EAP) com equipamentos; Mão de obra por cargo.
- **Como explorar:** Rolar a página citando cada bloco; abrir dropdown Imprimir e nomear as opções.
- **Fala:** "No detalhe temos clima, descrição, fotos, anexos e ocorrências. Abaixo, progresso por atividade da EAP, equipamentos utilizados e mão de obra por cargo. O botão Imprimir oferece PDF em três formatos e Excel."

---

### CENA 7 – Diário: Exportação (PDF/Excel)

- **Persona:** Engenheiro / Gestor.
- **Onde:** Na tela de detalhe do diário, dropdown Imprimir.
- **O que mostrar:** Links PDF normal, PDF detalhado, PDF sem fotos, Excel (xlsx).
- **Como explorar:** Só abrir o dropdown e nomear cada opção.
- **Fala:** "A exportação permite gerar PDF em três formatos e planilha Excel para uso externo."

---

### CENA 8 – Diário: EAP (Atividades)

- **Persona:** Engenheiro de planejamento / Mestre de obras.
- **Onde:** Dashboard → KPI **Atividades** → `/filters/activities/` (lista de registros por dia/atividade). Ou Menu **Obras** → `/projects/` → clicar no projeto → página do projeto com link para atividades/árvore EAP.
- **O que mostrar:** Lista de registros de progresso por atividade/dia OU árvore de atividades (Serviços Preliminares, Fundação, Estrutura) com status e códigos.
- **Como explorar:** Mostrar a tela e a hierarquia ou os registros.
- **Fala:** "A EAP organiza a obra em atividades com peso e status. Aqui vemos o progresso registrado por dia ou a árvore de atividades."

---

### CENA 9 – Diário: Mão de obra

- **Persona:** Engenheiro de campo / RH da obra.
- **Onde:** Menu **Mão de obra** → `/labor/`.
- **O que mostrar:** Categorias (Indireta, Direta, Terceirizada) e cargos (Pedreiro, Mestre de Obras, Servente, Eletricista, etc.).
- **Como explorar:** Listar; opcional: editar um cargo.
- **Fala:** "Aqui são cadastradas as categorias de mão de obra e os cargos usados nos relatórios diários."

---

### CENA 10 – Diário: Equipamentos

- **Persona:** Engenheiro de campo / Almoxarife.
- **Onde:** Menu **Equipamentos** → `/equipment/`.
- **O que mostrar:** Lista (Betoneira 400L, Escavadeira hidráulica, Andaime metálico) com código e tipo.
- **Como explorar:** Listar; opcional: editar um.
- **Fala:** "Os equipamentos cadastrados aqui são vinculados aos registros de atividade do diário, com quantidade utilizada no dia."

---

### CENA 11 – Diário: Filtros (Fotos, Ocorrências)

- **Persona:** Engenheiro / Gestor.
- **Onde:** Dashboard → KPI **Fotos** → `/filters/photos/` ou KPI **Ocorrências** → `/filters/occurrences/`.
- **O que mostrar:** Filtros e lista/grade (fotos com legenda ou ocorrências com tags).
- **Como explorar:** Aplicar filtro (período/projeto); mostrar itens e um clique que leve ao diário.
- **Fala:** "Os filtros permitem buscar fotos, ocorrências e outros itens por período ou projeto e abrir o relatório de origem."

---

### CENA 12 – Diário: Notificações

- **Persona:** Qualquer usuário.
- **Onde:** Ícone de notificações no header → `/notifications/`.
- **O que mostrar:** Lista de notificações (ou vazia); marcar como lidas.
- **Fala:** "As notificações centralizam avisos do sistema."

---

### CENA 13 – Troca para Mapa de Suprimentos

- **Persona:** Engenheiro de planejamento / Suprimentos.
- **Onde:** Menu **Sistemas** → **Mapa de Suprimentos** ou `/mapa/`.
- **O que mostrar:** Lista de obras do Mapa.
- **Como explorar:** Clicar em uma obra (ex.: Entreáguas) para selecionar.
- **Fala:** "Mudamos para o Mapa de Suprimentos e selecionamos a obra."

---

### CENA 14 – Mapa: Tela do Mapa (Engenharia)

- **Persona:** Engenheiro de planejamento.
- **Onde:** `/engenharia/mapa/` (menu **Mapa** na sidebar).
- **O que mostrar:** KPIs (Total, Atrasados, Solicitados, Em Compra, Parciais, Entregues); tabela de itens (insumo, local, quantidade, SC, PC, datas, fornecedor, prioridade); itens sem SC, com SC/PC, com alocação; prazo de necessidade e itens atrasados; descrição override e "Não aplica"; filtros; Novo levantamento.
- **Como explorar:** Apontar KPIs; rolar tabela e destacar exemplos; usar um filtro (prioridade ou local).
- **Fala:** "No Mapa vemos todos os itens da obra: levantamento puro, itens com SC e PC, recebidos e alocados. Os KPIs resumem totais e status. Podemos filtrar por local e prioridade."

---

### CENA 15 – Mapa: Histórico de alterações

- **Persona:** Engenheiro / Gestor.
- **Onde:** Ao editar ou abrir detalhe de um item do mapa que tenha histórico.
- **O que mostrar:** Lista de eventos (edição, alocação, importação) com data, usuário e descrição.
- **Como explorar:** Abrir um item com histórico e mostrar a seção.
- **Fala:** "Cada alteração no mapa fica registrada no histórico, para auditoria."

---

### CENA 16 – Mapa: Notas Fiscais de entrada

- **Persona:** Suprimentos / Almoxarife.
- **Onde:** Onde o sistema exibe NF vinculada a recebimento (detalhe do item ou lista de NFs).
- **O que mostrar:** Número da NF, data, quantidade, recebimento/PC associado.
- **Como explorar:** Navegar até um item recebido que tenha NF.
- **Fala:** "As notas fiscais de entrada ficam vinculadas aos recebimentos."

---

### CENA 17 – Mapa: Dashboard 2

- **Persona:** Gestor / Engenheiro.
- **Onde:** Menu **Dashboard** (sidebar Mapa) → `/engenharia/dashboard-2/`.
- **O que mostrar:** Gráficos e resumos por obra e status.
- **Como explorar:** Apontar cada gráfico/bloco.
- **Fala:** "O dashboard do Mapa resume a situação por obra e por status."

---

### CENA 18 – Mapa: Insumos e Importar Sienge (opcional)

- **Persona:** Engenheiro / Suprimentos.
- **Onde:** Cadastro de insumos; `/engenharia/mapa/importar-sienge/`.
- **O que mostrar:** Lista de insumos (código, descrição, unidade); tela de upload Sienge.
- **Como explorar:** Mostrar lista; na importação, só mostrar a tela.
- **Fala:** "O catálogo de insumos alimenta o mapa. A importação Sienge traz levantamentos da planilha."

---

### CENA 19 – Troca para Gestão de Aprovação

- **Persona:** Gestor / Aprovador.
- **Onde:** Menu **Sistemas** → **GestControll** ou `/gestao/`.
- **O que mostrar:** Home da Gestão (Pedidos, Obras, Empresas, Usuários).
- **Como explorar:** Clicar em **Pedidos**.

---

### CENA 20 – Gestão: Listagem de pedidos

- **Persona:** Solicitante / Aprovador.
- **Onde:** `/gestao/pedidos/`.
- **O que mostrar:** Filtros rápidos (Todos, Rascunho, Pendente, Aprovado, Reprovado, Reaprovação, Cancelado); tabela (código, obra, credor, tipo, valor, status).
- **Como explorar:** Clicar em Pendente e Aprovado; abrir um pedido.
- **Fala:** "Na lista de pedidos filtramos por status e vemos rascunhos, pendentes e aprovados."

---

### CENA 21 – Gestão: Detalhe de pedido e aprovação

- **Persona:** Aprovador.
- **Onde:** `/gestao/pedidos/<id>/`.
- **O que mostrar:** Dados do pedido; anexos; histórico de aprovação; botões Aprovar/Reprovar (se pendente).
- **Como explorar:** Abrir pedido pendente → mostrar dados e botões; opcional: aprovar com comentário. Abrir pedido aprovado → mostrar histórico.
- **Fala:** "No detalhe o aprovador vê dados e anexos, aprova ou reprova com comentário. Pedidos julgados exibem o histórico."

---

### CENA 22 – Gestão: Empresas e Obras

- **Persona:** Admin da gestão.
- **Onde:** `/gestao/empresas/` e `/gestao/obras/`.
- **O que mostrar:** Lista de empresas (ex.: LPLAN); lista de obras com pedidos; permissões (se houver).
- **Como explorar:** Mostrar empresas; mostrar obras e, se existir, permissões de uma obra.
- **Fala:** "Empresas e obras são a base da Gestão. Nas obras definimos quem solicita e quem aprova."

---

### CENA 23 – Gestão: Notificações e Meu perfil (opcional)

- **Onde:** `/gestao/notificacoes/` e `/gestao/meu-perfil/`.
- **O que mostrar:** Notificações; formulário de perfil.
- **Fala:** "Notificações avisam sobre pedidos; o perfil permite ajustar dados do usuário."

---

### CENA 24 – Painel do sistema (Admin Central)

- **Persona:** Administrador.
- **Onde:** Menu **Sistemas** → **Painel do sistema** ou `/accounts/admin-central/`.
- **O que mostrar:** Gerenciar obras; Gerenciar usuários (ou Análise de usuários).
- **Como explorar:** Abrir Gerenciar obras (lista de projetos); Gerenciar usuários (lista de usuários).
- **Fala:** "O Painel do sistema permite gerenciar obras e usuários sem usar o Django Admin."

---

### CENA 25 – Fechamento

- **Onde:** Voltar a `/select-system/`.
- **Fala:** "O LPLAN reúne Diário de Obra, Mapa de Suprimentos e Gestão de Aprovação em um único acesso. Obrigado."

---

## 4. Referência rápida (URLs e menus)

| Onde | URL | Menu / Ação |
|------|-----|-------------|
| Login | `/login/` | — |
| Seleção de sistema | `/select-system/` | Home após login |
| Selecionar obra (Diário) | `/select-project/` | Card Diário de Obras |
| Dashboard Diário | `/dashboard/` | Visão geral |
| Relatórios | `/reports/` | Relatórios |
| Detalhe diário | `/diaries/<id>/` | Clique em relatório ou calendário |
| Lista de projetos | `/projects/` | Obras (staff) |
| Filtro atividades | `/filters/activities/` | KPI Atividades |
| Mão de obra | `/labor/` | Mão de obra |
| Equipamentos | `/equipment/` | Equipamentos |
| Filtros (fotos, etc.) | `/filters/photos/`, `/filters/occurrences/`, etc. | KPIs no dashboard |
| Notificações (core) | `/notifications/` | Ícone no header |
| Mapa – lista obras | `/mapa/` | Card Mapa de Suprimentos |
| Mapa – tabela itens | `/engenharia/mapa/` | Mapas (sidebar) |
| Dashboard Mapa | `/engenharia/dashboard-2/` | Dashboard (sidebar mapa) |
| Importar Sienge | `/engenharia/mapa/importar-sienge/` | Importar Sienge |
| Gestão – home | `/gestao/` | Card GestControll |
| Gestão – pedidos | `/gestao/pedidos/` | Pedidos |
| Gestão – empresas | `/gestao/empresas/` | Empresas |
| Gestão – obras | `/gestao/obras/` | Obras |
| Admin Central | `/accounts/admin-central/` | Painel do sistema |

---

## 5. Dicas de gravação

- **Ordem:** Siga o esqueleto na ordem; use as cenas como capítulos se gravar em partes.
- **Persona:** Use a tabela da seção 1 para dar contexto em cada bloco.
- **Pausa:** 1–2 segundos antes de cliques importantes.
- **Exemplo real:** Em cada tela, mostre dados (diário com fotos, item com SC/alocação, pedido aprovado).
- **Edição:** Se errar, repita o trecho ou corte na edição.

---

*Complementa o `ROTEIRO_SCREENCAST.md` com esqueleto cena a cena, personas e referência de URLs.*
