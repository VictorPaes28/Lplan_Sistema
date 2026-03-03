-- Coluna versao_reaprovacao na tabela de anexos (migração 0009).
-- Rodar no MySQL de produção se der: Unknown column 'gestao_aprovacao_attachment.versao_reaprovacao'
-- Uso: mysql --force -u lplan_gestaoap2 -p lplan_Sistema < gestao_aprovacao/migrations/add_attachment_versao_reaprovacao_mysql.sql

ALTER TABLE `gestao_aprovacao_attachment` ADD COLUMN `versao_reaprovacao` INT NOT NULL DEFAULT 0;
