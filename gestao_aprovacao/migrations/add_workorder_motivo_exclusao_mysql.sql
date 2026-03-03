-- Adiciona apenas a coluna motivo_exclusao em gestao_aprovacao_workorder (MySQL).
-- Se já existir, vai dar "Duplicate column name" – pode ignorar.
-- Executar: mysql -u lplan_gestaoap2 -p lplan_Sistema < gestao_aprovacao/migrations/add_workorder_motivo_exclusao_mysql.sql

ALTER TABLE `gestao_aprovacao_workorder`
  ADD COLUMN `motivo_exclusao` LONGTEXT NULL;
