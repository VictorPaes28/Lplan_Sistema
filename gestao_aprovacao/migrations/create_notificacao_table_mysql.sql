-- Cria a tabela gestao_aprovacao_notificacao no MySQL (produção).
-- Use quando o Django disser "No migrations to apply" mas a tabela não existir.
--
-- Como executar:
-- 1) phpMyAdmin: selecione o banco lplan_Sistema, aba SQL, cole o conteúdo abaixo e execute.
-- 2) SSH no servidor, na pasta do projeto:
--    python manage.py dbshell
--    (cole o SQL abaixo e saia com \q)
-- 3) Linha de comando: mysql -u SEU_USUARIO -p lplan_Sistema < create_notificacao_table_mysql.sql
--
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
