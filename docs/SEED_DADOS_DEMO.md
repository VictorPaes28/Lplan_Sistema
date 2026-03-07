# Seed de Dados de Demo (Ambiente Local)

Comando para popular o sistema com **dados de teste completos** apenas em **desenvolvimento**, para gravação de screencasts e demonstrações.

## Segurança

- **Só executa com `DEBUG=True`.** Em produção (`DEBUG=False`) o comando é bloqueado.
- Use apenas no ambiente local (ou em cópia de desenvolvimento).

## Uso

```bash
# Gerar todos os dados
python manage.py seed_dados_demo_completo

# Simular sem gravar (dry-run)
python manage.py seed_dados_demo_completo --dry-run
```

## O que é criado

| Módulo | Conteúdo |
|--------|----------|
| **Obras** | Entreáguas, Okena, Marghot, Sunrise (LPLAN) com códigos 224, 242, 259, 260 |
| **Locais** | Bloco A, Bloco B, Pavimento 1, Pavimento Térreo, Lobby, Setor 1 por obra |
| **Insumos** | Catálogo variado (cimento, tubos, ferragem, concreto, blocos, elétrica, etc.) |
| **Mapa de Suprimentos** | Itens com situações variadas: com/sem SC, com/sem PC, com alocações, sem planejamento (qtd 0) |
| **SCs / Recebimentos** | RecebimentoObra vinculados às SCs; alocações para parte dos itens |
| **Diário de Obra** | Vários diários em datas diferentes (últimos ~60 dias), com clima, descrições, horas, DDS, deliberações |
| **Fotos do diário** | Fotos placeholder (1x1 PNG) com legendas realistas |
| **EAP** | Atividades (Serviços Preliminares, Fundação, Estrutura) com filhos |
| **Work logs** | Registros de progresso em atividades nos diários |
| **Ocorrências** | Tags (Atraso, Material, Segurança, etc.) e ocorrências em diários |

## Usuário

- Se existir superuser ou staff, ele é usado como criador dos dados e vinculado a todos os projetos.
- Caso contrário, é criado o usuário **demo** (senha: **demo1234**) e vinculado aos projetos.

Assim você consegue fazer login e ver todas as obras no **Mapa de Suprimentos**, no **Dashboard** e no **Diário de Obra**.

## Vídeos no diário

Vídeos **não** são criados automaticamente (exigiriam arquivos reais). Anexe manualmente pelo sistema se precisar demonstrar essa funcionalidade.

## Complementar dados existentes

Se as obras (224, 242, 259, 260) já existirem, o comando **reutiliza** e apenas **complementa** (locais, itens, diários, etc.). Pode rodar mais de uma vez; `get_or_create` evita duplicar onde há unicidade.
