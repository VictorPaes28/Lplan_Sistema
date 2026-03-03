-- =============================================================================
-- ÚNICO SCRIPT: cria todas as tabelas e colunas faltantes do gestao_aprovacao
-- no MySQL (banco lplan_Sistema). Não cria banco novo.
--
-- Rode UMA VEZ com --force para continuar mesmo se alguma coisa já existir:
--
--   mysql --force -u lplan_gestaoap2 -p lplan_Sistema < gestao_aprovacao/migrations/PRODUCAO_gestao_aprovacao_completo.sql
--
-- (--force faz o MySQL ignorar erros "Duplicate column" / "already exists" e
--  seguir executando o resto.)
-- =============================================================================

-- 1) Tabela notificacao
CREATE TABLE IF NOT EXISTS `gestao_aprovacao_notificacao` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `tipo` VARCHAR(50) NOT NULL,
  `titulo` VARCHAR(200) NOT NULL,
  `mensagem` LONGTEXT NOT NULL,
  `lida` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME(6) NOT NULL,
  `usuario_id` INT NOT NULL,
  `work_order_id` BIGINT NULL,
  PRIMARY KEY (`id`),
  KEY `gestao_apro_usuario_097a75_idx` (`usuario_id`, `lida`, `created_at`),
  KEY `gestao_aprovacao_notificacao_usuario_id_52d78518` (`usuario_id`),
  KEY `gestao_aprovacao_notificacao_work_order_id_b7599d79` (`work_order_id`),
  CONSTRAINT `ga_notif_usuario_fk` FOREIGN KEY (`usuario_id`) REFERENCES `auth_user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ga_notif_work_order_fk` FOREIGN KEY (`work_order_id`) REFERENCES `gestao_aprovacao_workorder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2) Tabela userprofile
CREATE TABLE IF NOT EXISTS `gestao_aprovacao_userprofile` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `foto_perfil` VARCHAR(100) NULL,
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  `usuario_id` INT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `gestao_aprovacao_userprofile_usuario_id_key` (`usuario_id`),
  CONSTRAINT `ga_userprofile_usuario_fk` FOREIGN KEY (`usuario_id`) REFERENCES `auth_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3) Colunas em workorder (0010 + 0017)
ALTER TABLE `gestao_aprovacao_workorder` ADD COLUMN `solicitado_exclusao` TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE `gestao_aprovacao_workorder` ADD COLUMN `solicitado_exclusao_em` DATETIME(6) NULL;
ALTER TABLE `gestao_aprovacao_workorder` ADD COLUMN `solicitado_exclusao_por_id` INT NULL, ADD CONSTRAINT `ga_wo_solicitado_por_fk` FOREIGN KEY (`solicitado_exclusao_por_id`) REFERENCES `auth_user` (`id`) ON DELETE SET NULL;
ALTER TABLE `gestao_aprovacao_workorder` ADD COLUMN `marcado_para_deletar` TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE `gestao_aprovacao_workorder` ADD COLUMN `marcado_para_deletar_em` DATETIME(6) NULL;
ALTER TABLE `gestao_aprovacao_workorder` ADD COLUMN `marcado_para_deletar_por_id` INT NULL, ADD CONSTRAINT `ga_wo_marcado_por_fk` FOREIGN KEY (`marcado_para_deletar_por_id`) REFERENCES `auth_user` (`id`) ON DELETE SET NULL;

-- 4) workorder.motivo_exclusao (0011)
ALTER TABLE `gestao_aprovacao_workorder` ADD COLUMN `motivo_exclusao` LONGTEXT NULL;

-- 5) workorderpermission.updated_at (0005)
ALTER TABLE `gestao_aprovacao_workorderpermission` ADD COLUMN `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6);

-- 5b) attachment.versao_reaprovacao (0009)
ALTER TABLE `gestao_aprovacao_attachment` ADD COLUMN `versao_reaprovacao` INT NOT NULL DEFAULT 0;

-- 6) Tabela comment
CREATE TABLE IF NOT EXISTS `gestao_aprovacao_comment` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `texto` LONGTEXT NOT NULL,
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  `autor_id` INT NOT NULL,
  `work_order_id` BIGINT NOT NULL,
  PRIMARY KEY (`id`),
  KEY `gestao_apro_work_or_1e6a2c_idx` (`work_order_id`, `created_at`),
  KEY `gestao_apro_autor_i_5aba68_idx` (`autor_id`, `created_at`),
  CONSTRAINT `ga_comment_autor_fk` FOREIGN KEY (`autor_id`) REFERENCES `auth_user` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `ga_comment_work_order_fk` FOREIGN KEY (`work_order_id`) REFERENCES `gestao_aprovacao_workorder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7) Tabela lembrete
CREATE TABLE IF NOT EXISTS `gestao_aprovacao_lembrete` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `dias_pendente` INT NOT NULL,
  `enviado_em` DATETIME(6) NOT NULL,
  `tipo` VARCHAR(50) NOT NULL,
  `enviado_para_id` INT NOT NULL,
  `work_order_id` BIGINT NOT NULL,
  PRIMARY KEY (`id`),
  KEY `gestao_apro_work_or_721525_idx` (`work_order_id`, `enviado_para_id`, `enviado_em`),
  KEY `gestao_apro_enviado_a3d050_idx` (`enviado_para_id`, `enviado_em`),
  CONSTRAINT `ga_lembrete_enviado_para_fk` FOREIGN KEY (`enviado_para_id`) REFERENCES `auth_user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ga_lembrete_work_order_fk` FOREIGN KEY (`work_order_id`) REFERENCES `gestao_aprovacao_workorder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8) Tabela tagerro
CREATE TABLE IF NOT EXISTS `gestao_aprovacao_tagerro` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `nome` VARCHAR(200) NOT NULL,
  `tipo_solicitacao` VARCHAR(20) NOT NULL,
  `descricao` LONGTEXT NULL,
  `ativo` TINYINT(1) NOT NULL DEFAULT 1,
  `ordem` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME(6) NOT NULL,
  `updated_at` DATETIME(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `gestao_aprovacao_tagerro_nome_tipo_uniq` (`nome`, `tipo_solicitacao`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9) Tabela M2M approval_tags_erro
CREATE TABLE IF NOT EXISTS `gestao_aprovacao_approval_tags_erro` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `approval_id` BIGINT NOT NULL,
  `tagerro_id` BIGINT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `gestao_aprovacao_approval_tags_erro_uniq` (`approval_id`, `tagerro_id`),
  CONSTRAINT `ga_approval_tags_approval_fk` FOREIGN KEY (`approval_id`) REFERENCES `gestao_aprovacao_approval` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ga_approval_tags_tagerro_fk` FOREIGN KEY (`tagerro_id`) REFERENCES `gestao_aprovacao_tagerro` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 10) Tabela emaillog
CREATE TABLE IF NOT EXISTS `gestao_aprovacao_emaillog` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `tipo_email` VARCHAR(20) NOT NULL,
  `destinatarios` LONGTEXT NOT NULL,
  `assunto` VARCHAR(500) NOT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'pendente',
  `mensagem_erro` LONGTEXT NULL,
  `tentativas` INT NOT NULL DEFAULT 1,
  `enviado_em` DATETIME(6) NULL,
  `criado_em` DATETIME(6) NOT NULL,
  `atualizado_em` DATETIME(6) NOT NULL,
  `work_order_id` BIGINT NULL,
  PRIMARY KEY (`id`),
  KEY `gestao_apro_emaillog_tipo_idx` (`tipo_email`),
  KEY `gestao_apro_emaillog_status_idx` (`status`),
  KEY `gestao_apro_criado__5046fa_idx` (`criado_em`, `status`),
  KEY `gestao_apro_work_or_991e88_idx` (`work_order_id`, `tipo_email`),
  CONSTRAINT `ga_emaillog_work_order_fk` FOREIGN KEY (`work_order_id`) REFERENCES `gestao_aprovacao_workorder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 11) obra.project_id (exige tabela core_project; se der erro, rode depois que o core tiver migrado)
ALTER TABLE `gestao_aprovacao_obra` ADD COLUMN `project_id` BIGINT NULL;
ALTER TABLE `gestao_aprovacao_obra` ADD CONSTRAINT `ga_obra_project_fk` FOREIGN KEY (`project_id`) REFERENCES `core_project` (`id`) ON DELETE SET NULL;
