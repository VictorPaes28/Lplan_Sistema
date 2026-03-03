# Ajuste do schema MySQL em produção (sistema.lplan.com.br)

O banco em produção está com o registro de migrações “aplicadas” mas parte do schema (tabelas/colunas) não existe. Estes passos recriam só o que falta **sem** criar banco novo — tudo no banco **lplan_Sistema** que a aplicação já usa.

---

## 1. No servidor (SSH)

```bash
cd ~/sistema_lplan
source /home/lplan/virtualenv/sistema_lplan/3.11/bin/activate
git pull
```

---

## 2. Executar os SQL na ordem

Use o usuário e a senha MySQL da aplicação (o mesmo de `DB_USER` / `DB_PASSWORD` no ambiente). Ex.: usuário `lplan_gestaoap2`.

**Ordem obrigatória:**

```bash
# 1) Tabela de notificações (se ainda não rodou)
mysql -u lplan_gestaoap2 -p lplan_Sistema < gestao_aprovacao/migrations/create_notificacao_table_mysql.sql

# 2) Colunas em workorder (solicitado_exclusao, marcado_para_deletar, etc.)
mysql -u lplan_gestaoap2 -p lplan_Sistema < gestao_aprovacao/migrations/add_workorder_columns_mysql.sql

# 3) Restante do gestao_aprovacao (Comment, Lembrete, TagErro, EmailLog, obra.project_id)
mysql -u lplan_gestaoap2 -p lplan_Sistema < gestao_aprovacao/migrations/fix_gestao_aprovacao_schema_mysql.sql
```

Se aparecer **Duplicate column name** ou **Table '...' already exists**, significa que aquela parte já está criada; pode ignorar o erro ou comentar o bloco correspondente no `.sql` e rodar de novo o que faltar.

Se no passo 3 der erro na última parte (`obra.project_id` / `core_project`), é porque a tabela `core_project` não existe no MySQL. Aí você pode comentar no arquivo as linhas do `ALTER TABLE gestao_aprovacao_obra` e rodar o resto; depois que o app **core** estiver com as migrações aplicadas e a tabela `core_project` existir, rode só esse `ALTER` (ou o bloco correspondente).

---

## 3. Conferir

- Abrir https://sistema.lplan.com.br/select-system/ e /gestao/ e usar o sistema.
- Se surgir novo erro de “Unknown column” ou “Table doesn’t exist”, anote a mensagem e o nome da coluna/tabela para ajustar o schema de novo (pode ser outra app: core, accounts, mapa_obras, suprimentos).

---

## Resumo do que cada script faz

| Script | O que faz |
|--------|-----------|
| `create_notificacao_table_mysql.sql` | Cria tabela `gestao_aprovacao_notificacao`. |
| `add_workorder_columns_mysql.sql` | Adiciona em `gestao_aprovacao_workorder`: `solicitado_exclusao`, `solicitado_exclusao_em`, `solicitado_exclusao_por_id`, `marcado_para_deletar`, `marcado_para_deletar_em`, `marcado_para_deletar_por_id`. |
| `fix_gestao_aprovacao_schema_mysql.sql` | Adiciona `motivo_exclusao` em workorder; cria tabelas Comment, Lembrete, TagErro, tabela M2M approval_tags_erro, EmailLog; adiciona `project_id` em obra (FK para `core_project`). |

Nenhum script cria banco de dados novo; todos usam o banco **lplan_Sistema** já existente.
