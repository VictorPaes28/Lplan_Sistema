-- =============================================================================
-- Ajuste completo do schema gestao_aprovacao no MySQL (produção).
-- Execute depois de create_notificacao_table_mysql.sql e add_workorder_columns_mysql.sql.
-- Se der "Duplicate column name" ou "Table already exists", pule aquele bloco.
-- Executar: mysql -u lplan_gestaoap2 -p lplan_Sistema < gestao_aprovacao/migrations/fix_gestao_aprovacao_schema_mysql.sql
-- =============================================================================

-- 0011: workorder.motivo_exclusao
ALTER TABLE `gestao_aprovacao_workorder`
  ADD COLUMN `motivo_exclusao` LONGTEXT NULL;

-- 0012: Comment
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
  CONSTRAINT `ga_comment_autor_fk` FOREIGN KEY (`autor_id`) REFERENCES `auth_user` (`id`) ON DELETE PROTECT,
  CONSTRAINT `ga_comment_work_order_fk` FOREIGN KEY (`work_order_id`) REFERENCES `gestao_aprovacao_workorder` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 0013: Lembrete
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

-- 0016: TagErro
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

-- 0016: M2M approval <-> TagErro
CREATE TABLE IF NOT EXISTS `gestao_aprovacao_approval_tags_erro` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `approval_id` BIGINT NOT NULL,
  `tagerro_id` BIGINT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `gestao_aprovacao_approval_tags_erro_uniq` (`approval_id`, `tagerro_id`),
  CONSTRAINT `ga_approval_tags_approval_fk` FOREIGN KEY (`approval_id`) REFERENCES `gestao_aprovacao_approval` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ga_approval_tags_tagerro_fk` FOREIGN KEY (`tagerro_id`) REFERENCES `gestao_aprovacao_tagerro` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 0017: EmailLog
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

-- 0018: obra.project_id (FK para core.Project)
-- Se der erro "Table 'core_project' doesn't exist", comente o bloco abaixo até as migrações do app core estarem aplicadas.
ALTER TABLE `gestao_aprovacao_obra`
  ADD COLUMN `project_id` INT NULL,
  ADD CONSTRAINT `ga_obra_project_fk` FOREIGN KEY (`project_id`) REFERENCES `core_project` (`id`) ON DELETE SET NULL;
