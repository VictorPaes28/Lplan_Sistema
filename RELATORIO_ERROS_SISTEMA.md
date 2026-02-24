# Relatório de erros e pontos de atenção no sistema

Varredura em **todo o sistema** (Diario_obra, Gestao_aprovacao, Mapa_Controle, suprimentos, etc.).

---

## 1. Uso de `except:` (bare except)

**Problema:** `except:` captura **tudo**, inclusive `KeyboardInterrupt` e `SystemExit`, e esconde erros reais. O recomendado é `except Exception:` (ou exceções específicas) e, quando fizer sentido, registrar o erro em log.

| Arquivo | Linha | Contexto |
|---------|-------|----------|
| **Diario_obra/core/frontend_views.py** | 2647 | Após `diary.refresh_from_db()` em rollback – pode esconder `ObjectDoesNotExist` ou outros |
| **Diario_obra/gestao_aprovacao/models.py** | 608 | `tamanho_formatado()` – falha ao acessar `self.arquivo.size` |
| **Diario_obra/gestao_aprovacao/views.py** | 3288, 3306 | Cálculo de métricas (outliers) – estatísticas |
| **Diario_obra/suprimentos/management/commands/importar_mapa_controle.py** | 71, 74, 77, 101 | Importação de dados |
| **Diario_obra/suprimentos/services/sienge_provider.py** | 65, 100, 103, 115, 222, 226, 237 | Leitura CSV, parse de data/decimal |
| **Diario_obra/gestao_aprovacao/management/commands/verificar_email.py** | 175 | Verificação de e-mail |
| **Gestao_aprovacao/obras/views.py** | 3206, 3224 | Mesmo padrão de métricas que gestao_aprovacao |
| **Gestao_aprovacao/obras/models.py** | 557 | Model (provavelmente formatação de arquivo) |
| **Mapa_Controle/suprimentos/** | Vários | Mesmos padrões do Diario_obra (comandos e sienge_provider) |

**Ação sugerida:** Trocar por `except Exception:` e, onde for relevante, logar a exceção (e, em rollback do diário, tratar `ObjectDoesNotExist` de forma explícita).

---

## 2. Diário de obra – prefixo de formset (já tratado)

- Formset de **ocorrências** usa `prefix='ocorrencias'` em todo o `frontend_views.py`; template e JS usam o mesmo prefixo.
- Se o navegador ainda enviar `occurrences-*` (cache ou outra tela), os dados não serão reconhecidos. Os logs de debug ajudam a confirmar o que está vindo no POST.

---

## 3. Divisão por zero

- **core/services.py:** Uso de `sum(...)/len(...)` está protegido com `if child_progresses` e `if progresses` antes da divisão.
- **gestao_aprovacao/views.py** e **Gestao_aprovacao/obras/views.py:** Cálculo de `tempo_medio_para_corrigir` e `tempo_medio_total_aprovacao` só roda quando `tempos_para_corrigir` / `tempos_total_aprovacao` são não vazios; após o `try/except`, `tempos_validos` é garantido não vazio. Nenhum risco adicional identificado nesses trechos.

---

## 4. Outros pontos já verificados

- **get_object_or_404:** Uso consistente em várias views; evita acesso a objeto inexistente.
- **ProgressService (core/services.py):** Médias calculadas apenas quando há lista não vazia.

---

## 5. Resumo de ações recomendadas

1. ~~**Prioridade alta:** Substituir `except:` por `except Exception:`~~ **FEITO** em todos os arquivos listados na seção 1 (frontend_views, gestao_aprovacao/views e models, Gestao_aprovacao/obras, suprimentos e Mapa_Controle espelhados).
2. **Opcional:** Em pontos críticos, trocar `except Exception:` por exceções específicas (ex.: `ObjectDoesNotExist`) e registrar em log quando fizer sentido.
3. Manter a convenção de nomes (ocorrencias, atividades executadas) e os logs de debug do diário até a confirmação de que ocorrências e atividades executadas estão salvando e aparecendo na tela de detalhe.

---

## 6. Correções já aplicadas (varredura atual)

- **core/frontend_views.py:** `except:` → `except Exception:` (após `refresh_from_db` no rollback).
- **gestao_aprovacao/models.py:** `except:` → `except Exception:` em `tamanho_formatado()`.
- **gestao_aprovacao/views.py:** `except:` → `except Exception:` nos dois blocos de cálculo de métricas (outliers).
- **Gestao_aprovacao/obras/views.py:** idem (dois blocos de métricas).
- **Gestao_aprovacao/obras/models.py:** `except:` → `except Exception:` em formatação de tamanho.
- **Gestao_aprovacao/obras/management/commands/verificar_email.py:** `except:` → `except Exception:`.
- **Diario_obra/gestao_aprovacao/management/commands/verificar_email.py:** `except:` → `except Exception:`.
- **Diario_obra/suprimentos/services/sienge_provider.py:** todos os `except:` → `except Exception:`.
- **Diario_obra/suprimentos/management/commands/importar_mapa_controle.py:** todos os `except:` → `except Exception:` (parse_date e parse_decimal).
- **Mapa_Controle/suprimentos/services/sienge_provider.py:** todos os `except:` → `except Exception:`.
- **Mapa_Controle/suprimentos/management/commands/importar_mapa_controle.py:** todos os `except:` → `except Exception:`.

---

## 7. Varredura completa com abordagens diferentes (fev/2025)

Foram aplicadas **várias formas de busca** no código (não só uma varredura única) para identificar erros e riscos em todo o sistema.

### 7.1 Abordagens usadas

| Abordagem | O que foi buscado | Resultado |
|-----------|-------------------|-----------|
| Acesso a lista/QuerySet vazio | `.get(...)[0]`, `.first().` sem guarda, `filter(...).get()` | 2 usos de `.first().` (ambos protegidos por `if cand.count() == 1`) |
| Divisão por zero | `/ len(`, uso de `sum(...)/len(...)` | Todos protegidos com `if lista` ou garantia de `tempos_validos` não vazio |
| Acesso direto a POST/GET | `request.POST[key]`, `request.GET[key]` | Vários usos; os críticos estão após `key in request.POST` ou usam `.get(key, default)` |
| Bare except | `except:` (sem tipo) | Nenhum restante (já corrigido na varredura anterior) |
| Depreciação pandas | `fillna(method='ffill')` | 2 arquivos: **sienge_provider.py** (Diario_obra e Mapa_Controle) – **corrigido** para `.ffill()` |
| SQL / injeção | `.raw(`, `execute(.*%`, f-string em SELECT | Nenhum padrão de risco encontrado |
| JSON sem tratamento | `json.loads(request.body)` sem try | Todas as views que usam estão dentro de `try` com `except Exception` ou específico |
| Exceções de modelo | `DoesNotExist`, `ObjectDoesNotExist` | Uso consistente em try/except onde necessário |

### 7.2 Correção aplicada nesta varredura

- **Pandas:** Em `Diario_obra/suprimentos/services/sienge_provider.py` e `Mapa_Controle/suprimentos/services/sienge_provider.py`, `fillna(method='ffill')` foi substituído por `.ffill()` (API atual do pandas 2.x).

### 7.3 Pontos verificados e considerados seguros

- **core/services.py:** Médias com `sum/len` só com `if child_progresses` / `if progresses`.
- **gestao_aprovacao/views.py e Gestao_aprovacao/obras/views.py:** `tempo_medio_para_corrigir` e `tempo_medio_total_aprovacao` só com listas não vazias; `tempos_validos` tem fallback.
- **frontend_views.py:** Uso de `request.POST[caption_key]` etc. apenas após `caption_key in request.POST` ou com `.get(caption_key, '')`.
- **suprimentos/views_api.py (Diario e Mapa):** `cand.first().item_sc` só após `if cand.count() == 1`.
- **csrf_exempt:** Apenas em views de webhook (intencional).

### 7.4 Testes automatizados existentes

- **Diario_obra:** `core/tests.py`, `core/tests_diary_flow.py`, `core/test_niveis_acessos.py`, `suprimentos/tests/` (test_load, test_verificacao_mapa, test_sync_logic, test_math_integrity, test_chaos).
- **Mapa_Controle:** `suprimentos/tests/` (test_load, test_chaos, test_sync_logic, test_math_integrity).
- **Gestao_aprovacao:** Sem pasta de testes encontrada nesta varredura.

*Recomendação:* Em máquinas onde o caminho do projeto não tenha problema de encoding (ex.: sem "Área" no path), rodar `python manage.py check` e `python manage.py test` em cada projeto (Diario_obra, Gestao_aprovacao, Mapa_Controle) para validar em runtime.

### 7.5 Verificação pré-deploy

- **Relatório e script:** [RELATORIO_VERIFICACAO_PRE_DEPLOY.md](RELATORIO_VERIFICACAO_PRE_DEPLOY.md) e `run_verificacao_pre_deploy.bat` (raiz do repositório) para executar check, showmigrations, verificar_mapa_suprimentos, verify_dashboard_data, verificar_pre_deploy e testes antes do deploy.
- **Comando novo:** `python manage.py verificar_pre_deploy` (Diario_obra) – contagens por modelo e detecção de duplicatas (project+date, activity+diary).

---

Este relatório pode ser atualizado após cada correção ou nova varredura.
