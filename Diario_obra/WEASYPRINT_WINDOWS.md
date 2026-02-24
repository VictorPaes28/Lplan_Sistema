# WeasyPrint no Windows - Guia de Instalação

## Problema

O WeasyPrint requer bibliotecas GTK+ nativas do sistema que não estão disponíveis por padrão no Windows. Isso causa o erro:

```
OSError: cannot load library 'libgobject-2.0-0': error 0x7e
```

## Solução Temporária (Sistema Funcional Sem PDF)

O sistema foi configurado para funcionar **sem WeasyPrint**. Você pode:

1. ✅ Criar superuser
2. ✅ Executar migrações
3. ✅ Usar todas as funcionalidades do sistema
4. ❌ Gerar PDFs (retornará erro 503)

## Opções para Habilitar Geração de PDF

### Opção 1: Instalar GTK+ no Windows (Recomendado para Produção)

1. Baixe o GTK+ para Windows:
   - https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
   - Ou use: https://www.gtk.org/docs/installations/windows/

2. Instale o GTK+ Runtime

3. Adicione ao PATH do sistema:
   - Caminho típico: `C:\GTK3-Runtime\bin`

4. Reinicie o terminal e teste:
```bash
python manage.py runserver
```

### Opção 2: Usar Alternativa (reportlab ou xhtml2pdf)

Se preferir não instalar GTK+, podemos substituir WeasyPrint por:

- **reportlab**: Mais simples, mas menos recursos CSS
- **xhtml2pdf**: Similar ao WeasyPrint, mas sem dependências nativas

### Opção 3: Usar Docker/Linux para Produção

Para produção, recomenda-se usar Linux ou Docker, onde o WeasyPrint funciona nativamente.

## Status Atual

✅ Sistema funciona completamente sem WeasyPrint
✅ Todas as funcionalidades disponíveis exceto geração de PDF
✅ Migrações e comandos Django funcionam normalmente
✅ Geração de PDF retorna erro informativo quando tentada

## Teste Rápido

Execute para verificar se tudo está funcionando:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

O sistema deve iniciar normalmente. Apenas a geração de PDF não funcionará até que o WeasyPrint seja configurado.

