# Obras LPlan – Códigos e preparação para o servidor

Este documento é a **referência única** dos códigos de obra e do que falta preencher no servidor (locais e responsáveis).

---

## 1. Códigos das obras (Sienge / MAPA_CONTROLE)

Os números abaixo são os que o sistema usa para importar o CSV e para vincular **Mapa de Obras** ↔ **Diário de Obra**. Se no servidor o Sienge usar outro número para alguma obra, altere a lista no comando e rode o seed de novo.

| Código | Nome       | Contratante           |
|--------|------------|------------------------|
| **224** | Entreáguas | Incorporadora Adamo   |
| **242** | Okena      | JP Empreendimentos   |
| **259** | Marghot    | Antonina Hotéis      |
| **260** | Sunrise    | Rpontes              |

Onde alterar: arquivo `mapa_obras/management/commands/seed_obras_lplan.py`, lista `OBRAS_LPLAN`.

---

## 2. O que o seed já deixa pronto

Ao rodar no servidor:

```bash
python manage.py seed_obras_lplan
```

o sistema:

- Cria/atualiza **mapa_obras.Obra** (Mapa de Obras) com `codigo_sienge` e nome.
- Cria/atualiza **core.Project** com `code = codigo_sienge`, mesmo nome, **client_name** = contratante, e datas de início/fim placeholder (hoje e daqui 2 anos). No servidor você pode ajustar as datas reais no admin.
- Com isso, Diário de Obra e Mapa de Obras usam o mesmo projeto; ao vincular usuários (ProjectMember/ProjectOwner), as obras aparecem para as pessoas certas.

---

## 3. Responsáveis por obra

O sistema já tem o conceito de responsável; falta apenas **preencher no servidor**:

- **Nome do responsável**  
  - Em **Admin** > **Core** > **Projetos** > [projeto da obra] > campo **Responsável**  
  - Ou deixar em branco até ter a lista definitiva.

- **Quem acessa a obra (engenharia, etc.)**  
  - **Admin** > **Core** > **Membros do projeto** (ProjectMember): adicionar usuário + projeto.  
  - Quem estiver como ProjectMember do projeto cujo `code` = código da obra passa a ver essa obra no Mapa e no Diário.

- **Dono da obra (cliente que recebe o diário)**  
  - **Admin** > **Core** > **Donos da obra** (ProjectOwner): adicionar usuário + projeto.  
  - Esse usuário recebe o diário por e-mail e pode comentar na janela de 24h.

Quando tiver a lista de responsáveis por obra, basta preencher o campo **Responsável** do projeto e/ou criar os vínculos em ProjectMember e ProjectOwner.

---

## 4. Locais (Bloco, Pavimento, Apto, Setor)

Os **locais** de cada obra ainda não estão no sistema. Quando tiver a lista correta:

- Cadastre em **Mapa de Obras** > **Locais** (ou pelo admin em **Locais da Obra**), por obra.
- Hierarquia disponível: Bloco → Pavimento → Apartamento / Setor, etc.

Não é necessário rodar nenhum comando extra; o seed só cria as obras e os projetos. Os locais são preenchidos depois, pela interface ou pelo admin.

---

## 5. Resumo para o servidor

| O quê              | Onde / Como |
|--------------------|-------------|
| **Número de cada obra** | Já definido no seed (224, 242, 259, 260). Alterar em `seed_obras_lplan.py` se o Sienge usar outro código. |
| **Rodar o seed**   | `python manage.py seed_obras_lplan` (uma vez, ou de novo após mudar códigos). |
| **Responsáveis**   | Preencher **Responsável** no projeto (admin) e vincular usuários em **ProjectMember** / **ProjectOwner**. |
| **Locais**         | Cadastrar quando tiver a lista, em Mapa de Obras > Locais (ou admin). |

Com isso, tudo fica preparado para o servidor: códigos únicos por obra, projetos criados e documentação de onde ajustar números, responsáveis e locais.

---

## 6. Verificações recomendadas (antes/subindo no servidor)

- **Testes**: rodar `python manage.py test suprimentos.tests.test_views_mapa suprimentos.tests.test_import_excel` (e outros que usar no projeto). Tudo deve passar.
- **Seed**: rodar `python manage.py seed_obras_lplan --dry-run` para ver o que seria criado/atualizado sem gravar; depois rodar sem `--dry-run` uma vez.
- **Importação**: ao importar o MAPA_CONTROLE, usar `-v 2` só quando precisar de log detalhado (ex.: `python manage.py importar_mapa_controle --file arquivo.csv -v 2`). Em produção o comando fica com saída resumida.
- **Admin**: conferir em **Core > Projetos** que existem os projetos com `code` 224, 242, 259, 260 e, em **Mapa de Obras** (ou app equivalente), que as obras têm o mesmo `codigo_sienge`.
