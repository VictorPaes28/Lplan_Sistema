-- Cria a tabela gestao_aprovacao_userprofile (MySQL produção). Migração 0007.
-- Executar: mysql -u lplan_gestaoap2 -p lplan_Sistema < gestao_aprovacao/migrations/create_userprofile_table_mysql.sql

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
