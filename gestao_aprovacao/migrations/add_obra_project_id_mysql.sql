-- Adiciona apenas a coluna project_id em gestao_aprovacao_obra (FK para core.Project).
-- Requer que a tabela core_project exista (app core com migrações aplicadas).
-- Se a coluna já existir, vai dar "Duplicate column name" – pode ignorar.
-- Executar: mysql -u lplan_gestaoap2 -p lplan_Sistema < gestao_aprovacao/migrations/add_obra_project_id_mysql.sql

ALTER TABLE `gestao_aprovacao_obra`
  ADD COLUMN `project_id` INT NULL,
  ADD CONSTRAINT `ga_obra_project_fk` FOREIGN KEY (`project_id`) REFERENCES `core_project` (`id`) ON DELETE SET NULL;
