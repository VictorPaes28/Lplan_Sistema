-- Adiciona colunas faltantes em gestao_aprovacao_workorder (MySQL produção).
-- Migrações 0010 e 0017 já marcadas como aplicadas mas colunas não existem.
-- Se der "Duplicate column name", comente ou apague a linha daquela coluna e rode o resto.
--
-- Executar: mysql -u lplan_gestaoap2 -p lplan_Sistema < gestao_aprovacao/migrations/add_workorder_columns_mysql.sql

-- 0010: solicitado_exclusao
ALTER TABLE `gestao_aprovacao_workorder`
  ADD COLUMN `solicitado_exclusao` TINYINT(1) NOT NULL DEFAULT 0;

ALTER TABLE `gestao_aprovacao_workorder`
  ADD COLUMN `solicitado_exclusao_em` DATETIME(6) NULL;

ALTER TABLE `gestao_aprovacao_workorder`
  ADD COLUMN `solicitado_exclusao_por_id` INT NULL,
  ADD CONSTRAINT `ga_wo_solicitado_por_fk` FOREIGN KEY (`solicitado_exclusao_por_id`) REFERENCES `auth_user` (`id`) ON DELETE SET NULL;

-- 0017: marcado_para_deletar
ALTER TABLE `gestao_aprovacao_workorder`
  ADD COLUMN `marcado_para_deletar` TINYINT(1) NOT NULL DEFAULT 0;

ALTER TABLE `gestao_aprovacao_workorder`
  ADD COLUMN `marcado_para_deletar_em` DATETIME(6) NULL;

ALTER TABLE `gestao_aprovacao_workorder`
  ADD COLUMN `marcado_para_deletar_por_id` INT NULL,
  ADD CONSTRAINT `ga_wo_marcado_por_fk` FOREIGN KEY (`marcado_para_deletar_por_id`) REFERENCES `auth_user` (`id`) ON DELETE SET NULL;
