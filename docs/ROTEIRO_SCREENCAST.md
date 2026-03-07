# Roteiro para Screencast – Sistema LPLAN

Roteiro para gravação de vídeo demonstrando todas as funcionalidades do sistema, usando os dados gerados por `python manage.py seed_dados_demo_completo`.

**Duração sugerida:** 25–40 minutos (ou em partes: Diário ~12 min, Mapa ~10 min, Gestão ~8 min).

**Usuário de teste:** `super1` (ou o usuário demo criado pelo seed). Senha: `demo1234` se acabou de criar.

---

## Parte 0 – Preparação (antes de gravar)

- [ ] Rodar o seed: `python manage.py seed_dados_demo_completo`
- [ ] Servidor rodando: `python manage.py runserver`
- [ ] Navegador em tela cheia ou janela fixa (ex.: 1920×1080)
- [ ] Fechar abas e extensões que possam distrair
- [ ] Opcional: desativar notificações do sistema

---

## Parte 1 – Login e seleção de sistema (≈2 min)

**O que mostrar:** Página de login e a tela única de “seleção de sistema” (Diário, Mapa, Gestão, Admin Central).

1. Acessar a URL do sistema (ex.: `http://127.0.0.1:8000/`).
2. Fazer login com o usuário demo/superuser.
3. Na **Seleção de Sistema** (home):
   - Mostrar os quatro “cards”: **Diário de Obra**, **Mapa de Suprimentos**, **Gestão de Aprovação**, **Admin Central**.
   - Dizer que o sistema é modular e o usuário escolhe por onde começar.

---

## Parte 2 – Diário de Obra (≈12 min)

**Objetivo:** Mostrar que o Diário está populado com várias obras, dias, fotos, anexos, ocorrências e progresso.

### 2.1 Seleção de obra e Dashboard

4. Clicar em **Diário de Obra**.
5. Na tela **Selecionar Obra**, mostrar a lista de projetos (ex.: Entreáguas, Okena, Marghot, Sunrise, Residencial Vista Verde). Selecionar uma obra (ex.: **Entreáguas**).
6. No **Dashboard**:
   - **Calendário:** mostrar que há vários dias com registro (cor preenchida) e a legenda (com diário, atrasado, rascunho).
   - Clicar em um dia que tenha diário para abrir o detalhe (ou ir por “Diários” no menu).
   - **Fotos recentes:** grid de fotos do projeto.
   - **Vídeos:** se houver (opcional no seed).
   - **Informações do projeto** na lateral.

### 2.2 Listagem e detalhe de um diário

7. Menu lateral: **Diários** (ou equivalente) para abrir a listagem de diários.
8. Mostrar **filtros** (projeto, data, status) e que há vários registros.
9. Abrir um **diário** (clique em um dia ou em um item da lista):
   - **Data, status, clima** (manhã/tarde, índice pluviométrico).
   - **Descrição geral** (general_notes).
   - **Fotos** com legendas.
   - **Anexos** (arquivos .txt de demonstração).
   - **Ocorrências** (se houver) com tags (Atraso, Material, Segurança, etc.).
   - **Acidentes / Paralisações / Riscos iminentes / Incidentes** (campos profissionais) quando preenchidos.
   - **EAP / Atividades:** progresso por atividade (percentual do dia, acumulado, local, estágio).
   - **Equipamentos** utilizados no dia (Betoneira, Escavadeira, Andaime, etc.).
   - **Mão de obra** (quantidade por cargo: Pedreiro, Servente, etc.).

### 2.3 Relatórios e exportação

10. Voltar ao dashboard ou ao diário e mostrar:
    - **Exportar PDF** (normal, detalhado, sem fotos).
    - **Exportar Excel** do diário (se existir link na tela).

### 2.4 EAP, Mão de obra e Equipamentos

11. Menu **Atividades (EAP):** árvore de atividades (Serviços Preliminares, Fundação, Estrutura, etc.) e status (Em andamento, Concluída, Não iniciada).
12. Menu **Mão de obra:** categorias (Indireta, Direta, Terceirizada) e cargos (Pedreiro, Mestre de Obras, Servente, etc.).
13. Menu **Equipamentos:** lista de equipamentos (ex.: Betoneira 400L, Escavadeira hidráulica, Andaime metálico).

### 2.5 Filtros avançados

14. Menu **Filtros** (ou “Fotos”, “Vídeos”, “Atividades”, “Ocorrências”, “Comentários”, “Anexos”, “Clima”, “Mão de obra”, “Equipamentos”):
    - Mostrar pelo menos um filtro (ex.: **Fotos** ou **Ocorrências**) com resultado preenchido para demonstrar busca e listagem.

### 2.6 Notificações

15. Ícone de **Notificações** no topo: abrir e mostrar que há (ou não) notificações, e marcar como lida se quiser.

---

## Parte 3 – Mapa de Suprimentos (≈10 min)

**Objetivo:** Mostrar obras, locais, itens do mapa com e sem SC, recebimentos, alocações, histórico e dashboards.

### 3.1 Entrada no Mapa e seleção de obra

16. Na **Seleção de Sistema**, clicar em **Mapa de Suprimentos**.
17. Na lista de **Obras** do Mapa (`/mapa/`), mostrar as obras disponíveis e **selecionar uma** (ex.: Entreáguas ou Residencial Vista Verde).

### 3.2 Mapa da Engenharia (tabela de itens)

18. Ir para **Mapa** da Engenharia (`/engenharia/mapa/` ou pelo menu “Mapa” com a obra já selecionada):
    - Tabela com **itens do mapa**: insumo, local de aplicação, quantidade planejada, SC, PC, datas, fornecedor, prioridade, responsável.
    - Mostrar itens **sem SC** (levantamento puro), **com SC sem PC**, **com PC e recebimento**, **com alocação**.
    - Mostrar **prazo de necessidade** (incluindo itens em atraso – prazo no passado).
    - Mostrar **descrição override** e itens **“Não aplica”** (filtro/coluna).
    - **Filtros** por obra, local, categoria, prioridade, status (com/sem SC, etc.).

### 3.3 Detalhe de item e histórico

19. Abrir um **item** (edição ou detalhe) e mostrar:
    - **Histórico de alterações** (auditoria): edições, alocações, importação Sienge (se houver).
20. Se a tela tiver **Notas Fiscais de Entrada** (drill-down por recebimento), mostrar NF vinculada a um recebimento.

### 3.4 Dashboard 2 do Mapa

21. Menu **Dashboard** do Mapa (`/engenharia/dashboard-2/`):
    - Gráficos e resumos (por obra, por status, alocações, pendências).
    - Se existir “alocação” no dashboard, mostrar alocação parcial e entrega.

### 3.5 Insumos e ações opcionais

22. **Cadastro de insumos** (se houver link): listar alguns insumos (portas, janelas, argamassa, etc.).
23. Opcional: **Novo levantamento** ou **Criar item** para mostrar o fluxo rápido de inclusão (sem precisar salvar de fato no screencast).
24. Opcional: **Importar Sienge** só mencionar (“o sistema permite importar planilha do Sienge para popular o mapa”).

---

## Parte 4 – Gestão de Aprovação (≈8 min)

**Objetivo:** Mostrar pedidos de obra em vários status, aprovação/reprovação e estrutura (empresas, obras, usuários).

### 4.1 Entrada e listagem de pedidos

25. Na **Seleção de Sistema**, clicar em **Gestão de Aprovação**.
26. Na **Home** da Gestão, ir para **Pedidos** (`/gestao/pedidos/`):
    - Listagem com **filtros** (obra, status, período).
    - Mostrar pedidos em **rascunho**, **pendente**, **aprovado**, **reprovado**, **reaprovacao**, **cancelado**.

### 4.2 Detalhe e fluxo de aprovação

27. Abrir um pedido **pendente** ou **em reaprovação**:
    - Dados do pedido (credor, tipo, valor estimado, observações).
    - **Anexos** (se houver).
    - Botões **Aprovar** e **Reprovar** (pode simular um “Aprovar” com comentário para mostrar o fluxo).
28. Abrir um pedido **aprovado** ou **reprovado**: mostrar **histórico de aprovação** (quem aprovou/reprovou, data, comentário).

### 4.3 Empresas e Obras

29. Menu **Empresas:** listar (ex.: LPLAN Construções) e abrir detalhe.
30. Menu **Obras:** listar obras da gestão (vinculadas aos projetos) e permissões (solicitante/aprovador) se a tela existir.

### 4.4 Notificações e perfil

31. **Notificações** da Gestão (se houver).
32. **Meu perfil** (edição de nome, email, etc.) se quiser mostrar personalização.

---

## Parte 5 – Admin Central (opcional, ≈3 min)

**Objetivo:** Mostrar que existe administração central (obras, usuários) sem entrar no Django Admin.

33. Na **Seleção de Sistema**, clicar em **Admin Central** (se o usuário for staff).
34. Mostrar **Gerenciar obras** e **Gerenciar usuários** (ou **Análise de usuários**), sem precisar alterar nada.

---

## Parte 6 – Fechamento (≈1 min)

35. Voltar à **Seleção de Sistema** e resumir em uma frase: “O LPLAN integra Diário de Obra, Mapa de Suprimentos e Gestão de Aprovação em um único acesso.”
36. Encerrar o vídeo (e desligar gravação).

---

## Dicas para a gravação

- **Fale pausadamente** e evite “hum”, “então” em excesso.
- **Pause 1–2 segundos** antes de clicar em um botão importante, para o espectador acompanhar.
- Se errar um clique, **repita o trecho** ou faça um corte na edição.
- **Mostre um exemplo real em cada tela** (ex.: um diário com fotos e ocorrências, um item do mapa com SC e alocação, um pedido aprovado).
- Se gravar em **partes**, use este roteiro como índice: Parte 2 = “Vídeo 2 – Diário”, Parte 3 = “Vídeo 3 – Mapa”, etc.

---

## Checklist pós-gravação

- [ ] Áudio claro e volume uniforme.
- [ ] Navegação visível (cursor e cliques).
- [ ] Legendas ou narração em português.
- [ ] Duração final alinhada ao objetivo (único vídeo ou série).
