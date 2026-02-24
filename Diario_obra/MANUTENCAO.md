# Manutenção LPLAN

## Erro: no such table: core_projectdiaryrecipient

Se ao acessar **E-mails do diário** de uma obra (`/projects/<id>/diario-emails/`) aparecer:

`OperationalError: no such table: core_projectdiaryrecipient`

**Causa:** A migração que cria a tabela de e-mails do diário não foi aplicada.

**Solução:** No terminal, na pasta do projeto (onde está o `manage.py`), execute:

```bash
python manage.py migrate
```

Ou só para o app core:

```bash
python manage.py migrate core
```

Isso cria a tabela `core_projectdiaryrecipient` e a página de e-mails do diário passa a funcionar.
