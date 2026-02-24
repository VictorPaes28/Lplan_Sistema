# Relatório de verificação pré-deploy – Lplan Sistema

Data da verificação: _preencher_  
Deploy previsto: _amanhã (conforme plano)_

---

## 1. Verificações de código e configuração

### 1.1 Django check (3 projetos)

Execute em cada raiz do projeto:

```batch
cd Diario_obra
python manage.py check

cd ..\Gestao_aprovacao
python manage.py check

cd ..\Mapa_Controle
python manage.py check
```

Ou rode o script único **na raiz do repositório** (pasta `Lplan_Sistema`, não dentro de `Diario_obra`):

```batch
cd "c:\Users\victo\OneDrive\Área de Trabalho\Lplan_Sistema"
.\run_verificacao_pre_deploy.bat
```

No PowerShell, se estiver em `Diario_obra`, volte para a raiz e execute:

```powershell
cd ..
.\run_verificacao_pre_deploy.bat
```

| Projeto           | Comando executado | Resultado (OK / Falha) | Observação |
|-------------------|-------------------|------------------------|------------|
| Diario_obra       | `manage.py check` |                        |            |
| Gestao_aprovacao  | `manage.py check` |                        |            |
| Mapa_Controle     | `manage.py check` |                        |            |

### 1.2 Migrations

Em cada projeto: `python manage.py showmigrations`. Anote se há `[ ]` (não aplicada).

| Projeto           | Migrations pendentes [ ]? (Sim/Não) | Observação |
|-------------------|--------------------------------------|------------|
| Diario_obra       |                                      |            |
| Gestao_aprovacao  |                                      |            |
| Mapa_Controle     |                                      |            |

### 1.3 Dependências

- **Diario_obra:** [Diario_obra/requirements.txt](Diario_obra/requirements.txt) – Django 5.x, PostgreSQL/MySQL, Celery, WeasyPrint, etc.
- **Gestao_aprovacao:** [Gestao_aprovacao/requirements.txt](Gestao_aprovacao/requirements.txt) – Django 5.x, MySQL (pymysql no cPanel).
- **Mapa_Controle:** [Mapa_Controle/requirements.txt](Mapa_Controle/requirements.txt) – Django 5.x, pandas, PostgreSQL.

Versão Python recomendada: 3.10+.

### 1.4 Pontos já cobertos

- Bare `except:` substituídos por `except Exception:` (ver [RELATORIO_ERROS_SISTEMA.md](RELATORIO_ERROS_SISTEMA.md)).
- Pandas: `fillna(method='ffill')` corrigido para `.ffill()` nos dois `sienge_provider.py`.

---

## 2. Testes automatizados

### 2.1 Ajuste aplicado

- **tests_diary_flow.py:** prefixo do formset de ocorrências alterado de `diaryoccurrence-*` para **`ocorrencias-*`** (alinhado a [CONVENCOES_NOMES.md](Diario_obra/CONVENCOES_NOMES.md) e ao frontend).

### 2.2 Execução dos testes

| Projeto       | Comando                                      | Resultado (OK / Falha) | Observação |
|---------------|-----------------------------------------------|------------------------|------------|
| Diario_obra   | `python manage.py test core suprimentos`      |                        |            |
| Mapa_Controle | `python manage.py test suprimentos`           |                        |            |
| Gestao_aprovacao | Sem suite de testes; validar manualmente  | N/A                    |            |

---

## 3. Integridade de dados e duplicados

### 3.1 Comandos de verificação

| Comando                               | Projeto(s)     | Resultado | Observação |
|---------------------------------------|----------------|-----------|------------|
| `python manage.py verificar_mapa_suprimentos` | Diario_obra, Mapa_Controle |           |            |
| `python manage.py verify_dashboard_data`       | Diario_obra    |           | opcional `--project-id N` |
| `python manage.py verificar_pre_deploy`       | Diario_obra    |           | contagens + duplicatas (project+date, activity+diary) |

### 3.2 Comando novo: verificar_pre_deploy

Foi criado o comando **verificar_pre_deploy** em Diario_obra:

- Lista contagens: Project, ConstructionDiary, DiaryOccurrence, DailyWorkLog, DiaryImage, User ativo.
- Detecta duplicatas: ConstructionDiary (project+date), DailyWorkLog (activity+diary).
- Uso: `python manage.py verificar_pre_deploy` ou `--quiet` para só erros/avisos.

### 3.3 Dados sensíveis em seeds

- Os comandos **seed_*** (ex.: seed_teste, seed_gestcontroll) definem senhas de desenvolvimento (ex.: `admin123`, `eng123`). **Não rodar em produção** com dados reais; usar apenas em ambiente de desenvolvimento/dados iniciais controlados.
- Conforme [REVISAO_DEPLOY_ETAPAS.md](REVISAO_DEPLOY_ETAPAS.md) Etapa 6: não executar seeds em produção com dados sensíveis.

---

## 4. Usuários e permissões

- **Diario_obra:** grupos em [accounts/groups.py](Diario_obra/accounts/groups.py). Validar login com 1–2 usuários por perfil (admin, obra).
- **Gestao_aprovacao / Mapa_Controle:** UserProfile e permissões por obra/empresa. Verificar que não há UserProfile órfão (user removido).

| Verificação                         | Feito? | Observação |
|-------------------------------------|--------|------------|
| Listar usuários ativos              |        |            |
| Teste de login por perfil           |        |            |
| Páginas críticas sem 500            |        |            |

---

## 5. Funcionalidades críticas (smoke)

| Fluxo / Funcionalidade | Projeto      | Verificado? | Observação |
|------------------------|-------------|-------------|------------|
| Login → projeto → criar/editar diário (rascunho) → ocorrências e atividades executadas → salvar → detalhe | Diario_obra | | |
| Cópia do relatório anterior (sem observações/responsáveis) | Diario_obra | | |
| Dashboard e listagem; PDF se usado | Diario_obra | | |
| Login → listar OTs/obras → abrir OT → anexos/aprovação | Gestao_aprovacao | | |
| Login → obra → mapa de suprimentos; alocação | Mapa_Controle | | |

---

## 6. Checklist deploy (resumo)

Integrar com [REVISAO_DEPLOY_ETAPAS.md](REVISAO_DEPLOY_ETAPAS.md):

- [ ] Etapas 1–2: segurança (SECRET_KEY, DEBUG=False, ALLOWED_HOSTS).
- [ ] Etapas 7–8: banco (migrate), collectstatic, alias static/media.
- [ ] Etapa 11: variáveis de ambiente no cPanel.
- [ ] Etapa 14: testes pós-deploy (acesso à URL, login, sem 500).

---

## 7. Erros ou incompatibilidades encontradas

_Listar aqui qualquer erro ou incompatibilidade e classificar: bloqueante / corrigir em seguida / aceitar risco._

| Item | Classificação | Ação |
|------|----------------|------|
|      |               |      |

---

## 8. Entregáveis

- [x] Script **run_verificacao_pre_deploy.bat** na raiz: executa check, showmigrations, verificar_pre_deploy, verificar_mapa_suprimentos, verify_dashboard_data e testes nos 3 projetos.
- [x] Comando **verificar_pre_deploy** (Diario_obra): contagens e duplicatas.
- [x] **tests_diary_flow.py** alinhado ao prefixo **ocorrencias**.
- [x] Este relatório com checklist e espaço para preencher resultados.

Após executar os comandos e testes, preencha as tabelas com os resultados (OK/Falha e observações) e documente qualquer erro na seção 7.
