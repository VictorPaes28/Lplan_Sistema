# Mapa de Suprimentos em produção – checklist e diagnóstico

Quando o Mapa funciona localmente mas **em produção** os dados não persistem ou o botão **Detalhes** não abre, siga este checklist.

---

## 0. 404 em supplymap.js / "initCriarItem is not defined"

Se o Console mostrar **404** em `supplymap.js` e **Refused to execute script... MIME type 'text/html'**, o arquivo estático não está sendo encontrado. O projeto está configurado para o **Django servir `/static/` em produção** (quando `DEBUG=False`), mas os arquivos precisam estar em `STATIC_ROOT`.

**No servidor, obrigatório após cada deploy:**

```bash
python manage.py collectstatic --noinput
```

- Isso copia todos os estáticos (incluindo `suprimentos/static/js/supplymap.js`) para a pasta `staticfiles/` (ou o `STATIC_ROOT` do seu `.env`).
- Sem rodar `collectstatic`, a URL `/static/js/supplymap.js` (ou o nome com hash) continua retornando 404 e o Mapa não funciona.

Se o cPanel/servidor já tiver **Alias /static/** apontando para outra pasta, você pode usar essa pasta como `STATIC_ROOT` e rodar o `collectstatic` para ela, ou deixar o Django servir (já configurado em `lplan_central/urls.py` em produção).

---

## 1. Arquivos estáticos (obrigatório após cada deploy)

Em produção o Django usa `STATICFILES_STORAGE = ManifestStaticFilesStorage`. O navegador pode estar carregando uma **versão antiga** do `supplymap.js` se o comando abaixo não for executado após cada deploy:

```bash
python manage.py collectstatic --noinput
```

- O comando copia os estáticos para `STATIC_ROOT` (ex.: `staticfiles/`) e gera nomes com hash.
- Se o servidor (Apache/cPanel) servir arquivos estáticos dessa pasta, **é preciso rodar collectstatic** depois de alterar qualquer JS/CSS do Mapa.
- Se usar outro método para servir estáticos (CDN, outro caminho), garanta que essa pasta (ou a origem) seja atualizada com o resultado do `collectstatic`.

---

## 2. Conferir qual JS está rodando (F12 → Console)

Ao abrir o Mapa no **servidor**, abra o **Console** (F12) e filtre por `[LPLAN]`. Deve aparecer algo como:

```
[LPLAN] SupplyMap v7 carregado. Se não aparecer "v7" em produção, o JS está em cache...
```

- Se aparecer **v7**: o script novo está carregado. Se ainda assim nada persistir ou o Detalhes não abrir, vá para o passo 3.
- Se **não** aparecer essa linha ou aparecer outra versão (ex.: v5, v6): o navegador está usando **JS em cache** ou o servidor está servindo um arquivo antigo.
  - Faça **hard refresh**: Ctrl+Shift+R (ou Cmd+Shift+R no Mac).
  - Confirme que rodou `collectstatic` e que o servidor está servindo a pasta atualizada.

---

## 3. Requisições no servidor (F12 → Rede / Network)

### Salvando um campo

1. Edite um campo (ex.: código do insumo) e saia do campo (blur) para disparar o salvamento.
2. Na aba **Rede**, procure uma requisição **POST** para algo como:
   - `.../api/internal/item/atualizar-campo/`
3. Clique nessa requisição e verifique:
   - **Status**: deve ser **200**.
   - **Resposta**: corpo em JSON com `"success": true` e `"obra_id": ...`.

Se aparecer **403**, **404** ou **500**, o problema está no backend (sessão, CSRF, URL ou erro no servidor). Use a resposta e o **Console** (mensagens `[LPLAN]`) para ver o que falhou.

### Botão Detalhes

1. Clique em **Detalhes** em uma linha.
2. Na aba **Rede**, deve aparecer um **GET** para:
   - `.../api/internal/item/<id>/detalhe/`
3. Verifique:
   - **Status**: deve ser **200**.
   - **Resposta**: JSON com `"html": "..."`.

Se não aparecer **nenhuma** requisição ao clicar em Detalhes, o clique não está disparando o `fetch` (erro de JS antes do handler ou outro script quebrando). Veja o **Console** por erros em vermelho e por mensagens `[LPLAN]`.

---

## 4. Erros de JavaScript (Console)

- Qualquer **erro em vermelho** no Console pode impedir o restante do script de rodar (incluindo salvamento e Detalhes).
- As mensagens `[LPLAN]` indicam em qual init ocorreu falha, por exemplo:
  - `[LPLAN] Erro em initModals: ...`
  - `[LPLAN] Modal não encontrado: id= ...`
  - `[LPLAN] Detalhes falhou: 403 ...`

Use essas mensagens para saber se o problema é: modal não encontrado, Bootstrap não disponível, ou resposta de rede (status 403/404/500).

---

## 5. Cache do navegador e do servidor

- **Navegador**: após deploy e `collectstatic`, teste em **aba anônima** ou com cache desabilitado (F12 → Rede → “Desabilitar cache”) para garantir que está usando o JS novo.
- **Servidor/CDN**: se houver cache na frente do site (proxy, CDN, Cloudflare, etc.), pode ser necessário **purgar cache** ou desativar cache para o Mapa durante os testes.

---

## 6. Resumo rápido

| Sintoma                         | O que verificar |
|---------------------------------|------------------|
| Dados não persistem ao recarregar | POST para `atualizar-campo/` com status 200 e `success: true`? Se sim, problema pode ser obra/lista no backend. Se não, veja 403/500 e Console. |
| Botão Detalhes não faz nada     | GET para `.../detalhe/<id>/` aparece na Rede? Se não, há erro de JS ou evento não ligado (Console + `[LPLAN]`). Se sim, veja status e resposta. |
| Console não mostra "SupplyMap v7" | JS em cache ou estáticos antigos: hard refresh, collectstatic, conferir origem dos estáticos. |

Depois de rodar **collectstatic**, limpar cache e conferir Console + Rede, use as mensagens `[LPLAN]` e os status das requisições para apontar exatamente onde está o problema (estáticos, frontend ou backend).
