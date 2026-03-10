# Corrigir 413 Request Entity Too Large (vídeo/upload grande)

O erro **413 Request Entity Too Large** geralmente vem do **servidor web** (Nginx/Apache) **antes** da requisição chegar ao Django. O Django está configurado para aceitar até 150MB (`settings.py`: `FILE_UPLOAD_MAX_MEMORY_SIZE` e `DATA_UPLOAD_MAX_MEMORY_SIZE`).

## O que fazer no servidor (produção)

### Nginx

No bloco `server` ou no `http`, adicione ou altere:

```nginx
client_max_body_size 150M;
```

Depois: `sudo nginx -t` e `sudo systemctl reload nginx` (ou equivalente).

### Apache (cPanel / mod_wsgi)

No `.htaccess` da aplicação ou na config do VirtualHost:

```apache
LimitRequestBody 157286400
```

(157286400 bytes ≈ 150MB.)

Se usar **PHP** no mesmo domínio, no cPanel aumente `upload_max_filesize` e `post_max_size` para pelo menos `150M` (MultiPHP INI Editor).

### cPanel (sem acesso ao Nginx/Apache)

1. **MultiPHP INI Editor**: `upload_max_filesize` = `150M`, `post_max_size` = `150M`.
2. Se a aplicação Django for servida por proxy reverso (Nginx na frente), o limite costuma estar no Nginx; pedir ao suporte para definir `client_max_body_size 150M`.

## Resumo

| Onde              | O que configurar                          |
|-------------------|-------------------------------------------|
| Django (projeto)  | Já configurado: 150MB em `settings.py`   |
| Nginx             | `client_max_body_size 150M;`              |
| Apache             | `LimitRequestBody 157286400`              |
| cPanel / PHP INI  | `upload_max_filesize` e `post_max_size` = 150M |

Após alterar o servidor web, teste novamente o upload do vídeo.
