-- Adiciona a coluna updated_at em gestao_aprovacao_workorderpermission (MySQL produção). Migração 0005.
-- Se a coluna já existir, vai dar "Duplicate column name" – pode ignorar.
-- Executar: mysql -u lplan_gestaoap2 -p lplan_Sistema < gestao_aprovacao/migrations/add_workorderpermission_updated_at_mysql.sql

ALTER TABLE `gestao_aprovacao_workorderpermission`
  ADD COLUMN `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6);
