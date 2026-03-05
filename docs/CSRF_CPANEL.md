# CSRF / "Sessão inválida" no cPanel

Quando o Mapa de Suprimentos (ou qualquer POST) retorna **"Sessão inválida"** ou **403** no servidor mas funciona em desenvolvimento, a causa é quase sempre **origem (Referer/Origin) não confiável** ou **proxy não informando HTTPS** ao Django.

## Diferença entre as duas "Sessão inválida"

A mensagem **"Sessão inválida. Recarregue a página e tente novamente."** pode ter duas origens:

1. **No navegador (JavaScript)**  
   O token CSRF **não foi obtido** no cliente (nem na página nem via GET `/api/csrf-token/`). Nesse caso o POST nem chega a ser enviado com token, ou o fetch do token retornou redirect/HTML em vez de JSON.  
   → Use o **diagnóstico no navegador** abaixo.

2. **Resposta 403 do servidor**  
   O Django rejeitou o POST por falha na validação CSRF (origem/referer não confiável, etc.).  
   → Veja a seção **Ver o que o Django está recebendo** e os ajustes de `.env` / Apache.

## Diagnóstico no navegador (produção)

Faça isso **no servidor**, com F12 aberto (aba Console), na tela do Mapa de Suprimentos:

1. **Ao carregar a página**  
   Procure no console a linha que começa com `[LPLAN] Diagnóstico ao carregar:`.  
   - Se aparecer `token em window= não` e `(string vazia!)`, o HTML foi servido **sem** o token (possível cache de página ou template sem `csrf_token`).  
   - Anote `origin=` e `fetch usará=` (a URL usada para buscar o token).

2. **Ao tentar salvar um campo (edição inline)**  
   - Se aparecer `[LPLAN] CSRF token: não encontrado na página; buscando em GET` ou `usando URL absoluta para fetch`, o script está tentando obter o token via GET.  
   - Em seguida deve aparecer `[LPLAN] CSRF GET resposta:` com `status`, `ok`, `url`, `contentType`.  
     - Se `ok: false` e `status: 302` (ou 200 com `contentType` não JSON), a requisição está sendo **redirecionada** ou está retornando **HTML** (ex.: página de login). Isso indica que o cookie de sessão não está sendo enviado no fetch ou que a URL do token está errada.  
   - Se aparecer `[LPLAN] CSRF GET body (primeiros 400 chars):`, copie esse trecho; se for HTML (ex.: `<!DOCTYPE` ou formulário de login), confirma que o GET está recebendo página em vez de JSON.

3. **Aba Network (Rede)**  
   - Filtre por `csrf-token` ou `atualizar` (ou o path do POST).  
   - Ao salvar, verifique se existe uma requisição **GET** para `/api/csrf-token/` (ou a URL absoluta) e qual o **status** e o **tipo** da resposta (JSON vs HTML).  
   - Verifique se a requisição **POST** de salvamento foi enviada e com qual status (403 = servidor rejeitou CSRF).

Com isso dá para saber se o problema é **token não disponível no cliente** (cache, cookie não enviado, redirect no GET) ou **403 no servidor** (origem/referer).

## O que o código já faz (após as alterações)

1. **`lplan_central/settings.py`**
   - Em produção (`DEBUG=False`): `SITE_URL` do `.env` é **incluído automaticamente** em `CSRF_TRUSTED_ORIGINS` (e a variante com/sem `www` também).
   - Basta ter no `.env`: `SITE_URL=https://sistema.lplan.com.br` (sem barra no final).
   - `SECURE_PROXY_SSL_HEADER` e `USE_X_FORWARDED_HOST` ativados para quando o Apache enviar os headers.

2. **`core.middleware.ProxyHeadersMiddleware`**
   - Se o Apache **não** enviar `X-Forwarded-Proto` e `SITE_URL` for `https://...`, o middleware define `X-Forwarded-Proto: https` para o Django tratar a requisição como HTTPS (cookies, redirect, etc.).

3. **`core/csrf_views.py`**
   - Em todo 403 por CSRF é escrito no log (`logs/lplan.log`): `Referer`, `Origin` e `CSRF_TRUSTED_ORIGINS`. Use isso para conferir o que o Django está recebendo no servidor.

## O que fazer no servidor (cPanel)

### 1. .env no servidor

Confirme que existe e está correto (caminho típico: `public_html/.env` ou a pasta da aplicação):

```env
DEBUG=False
SECURE_COOKIES_AND_REDIRECT=True
SITE_URL=https://sistema.lplan.com.br
ALLOWED_HOSTS=sistema.lplan.com.br,www.sistema.lplan.com.br
```

- **SITE_URL**: exatamente a URL que você usa no navegador, **sem barra no final**.
- Com isso, o código já coloca `https://sistema.lplan.com.br` e `https://www.sistema.lplan.com.br` em `CSRF_TRUSTED_ORIGINS`.
- Opcional: pode ainda definir `CSRF_TRUSTED_ORIGINS` manualmente; o código **adiciona** `SITE_URL` (e variante www) à lista.

### 2. .htaccess (Apache / Passenger)

Se ainda der 403, o Apache precisa informar ao Django que a requisição veio por HTTPS. Use o exemplo:

- Arquivo: **`.htaccess.cpanel.example`** na raiz do projeto.
- Copie para **`.htaccess`** na **mesma pasta** do `passenger_wsgi.py` no servidor.
- Ajuste `SEU_USUARIO` e caminhos do `Passenger*` para o seu usuário/cPanel.
- O trecho importante é:

```apache
RewriteCond %{HTTPS} on
RewriteRule ^ - [E=HTTPS:on]
RequestHeader set X-Forwarded-Proto "https" env=HTTPS
```

Isso exige **mod_headers** (e mod_rewrite). Se o cPanel não tiver `mod_headers` ou der erro, o **ProxyHeadersMiddleware** tenta compensar usando apenas `SITE_URL` (sem o header do Apache).

### 3. Ver o que o Django está recebendo

Após um 403, abra no servidor:

- `logs/lplan.log` (ou o arquivo configurado em `LOGGING`)

Procure por algo como:

```text
CSRF 403: Referer=... Origin=... CSRF_TRUSTED_ORIGINS=[...] path=...
```

- **Referer/Origin**: URL que o navegador enviou.
- **CSRF_TRUSTED_ORIGINS**: lista que o Django está usando.

A origem que aparece em Referer/Origin tem de estar **exatamente** nessa lista (esquema + host, sem barra no final). Com `SITE_URL` certo e o middleware, isso já deve estar coberto.

### 4. Cache e cookies

- Teste em aba anônima ou outro navegador.
- Confirme que está acessando por **HTTPS** (e que `SITE_URL` é `https://...`).
- Se tiver **CDN ou cache na frente**, pode ser necessário purgar cache ou desativar para testes.

## Resumo

| Onde       | O que fazer |
|-----------|-------------|
| **.env**  | `DEBUG=False`, `SECURE_COOKIES_AND_REDIRECT=True`, `SITE_URL=https://sistema.lplan.com.br` (sem barra). |
| **Apache** | Usar `.htaccess` com `X-Forwarded-Proto` quando HTTPS (ver `.htaccess.cpanel.example`). |
| **Log**   | Ver `CSRF 403: Referer=...` em `logs/lplan.log` para conferir origem vs `CSRF_TRUSTED_ORIGINS`. |

Com isso, a “Sessão inválida” no cPanel tende a ser resolvida; se continuar, o log dessa linha mostra o próximo ajuste necessário.
