# Git não encontrado no terminal

No PowerShell o comando `git` não está sendo reconhecido. Use uma das opções abaixo.

---

## Opção 1: Usar o Source Control do Cursor (recomendado)

1. No Cursor, pressione **Ctrl+Shift+G** (ou clique no ícone de ramificação na barra lateral).
2. Em **Source Control**, você verá os arquivos modificados.
3. **Adicione só estes arquivos** (clique no **+** ao lado de cada um):
   - `Diario_obra/requirements-cpanel.txt`
   - `Diario_obra/CPANEL_PIP.md`
   - `Diario_obra/ESTRUTURA_CPANEL.md`
   - `Diario_obra/core/utils/pdf_generator.py`
4. **Não** inclua `.env`, `db.sqlite3`, `media`, pastas `logs`, etc.
5. Na caixa de mensagem, digite:  
   `cPanel: requirements-cpanel.txt (evita pycairo/meson) + doc + PDF WeasyPrint 52 compat`
6. Clique em **Commit** (✓).

Depois, no cPanel: `git pull` na pasta do projeto.

---

## Opção 2: Instalar ou reparar o Git no PATH

Se o Git está instalado mas não aparece no PowerShell:

1. **Instalar Git para Windows** (se ainda não tiver):  
   https://git-scm.com/download/win  
   Durante a instalação, marque **"Git from the command line and also from 3rd-party software"**.
2. **Fechar e reabrir** o terminal (ou o Cursor) para atualizar o PATH.
3. Testar: `git --version`

Se o Git já estiver instalado em outro lugar (por exemplo em `C:\Users\victo\AppData\Local\...`), adicione a pasta que contém `git.exe` às variáveis de ambiente **PATH** do Windows (Configurações → Sistema → Sobre → Configurações avançadas do sistema → Variáveis de ambiente → Path → Editar → Novo).

---

## Comandos para depois que o Git funcionar

Na raiz do repositório (`Lplan_Sistema`):

```powershell
git add Diario_obra/requirements-cpanel.txt Diario_obra/CPANEL_PIP.md Diario_obra/ESTRUTURA_CPANEL.md Diario_obra/core/utils/pdf_generator.py
git status
git commit -m "cPanel: requirements-cpanel.txt (evita pycairo/meson) + doc + PDF WeasyPrint 52 compat"
git push
```

No cPanel:

```bash
cd /home/lplan/sistema_lplan
git pull
```
