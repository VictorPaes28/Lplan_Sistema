# cPanel: Erro ao instalar dependências (pycairo / meson)

Se ao rodar `pip install -r requirements.txt` no cPanel aparecer:

```
PermissionError: [Errno 13] Permission denied: 'meson'
× Encountered error while generating package metadata.
╰─> pycairo
```

## Causa

O `requirements.txt` pede **WeasyPrint>=60** e **xhtml2pdf**, que dependem de **pycairo**. A compilação do pycairo exige **meson**; no cPanel o usuário não tem permissão para executar meson no ambiente de build do pip.

## Solução: usar `requirements-cpanel.txt`

Foi criado o arquivo **`requirements-cpanel.txt`** na pasta `Diario_obra`:

- **WeasyPrint** está fixado em **52.x** (usa **cairocffi**, que tem wheels pré-compilados – não compila pycairo).
- **xhtml2pdf** não está incluído (evita a cadeia svglib → rlpycairo → pycairo). No Linux o PDF é gerado só pelo WeasyPrint.

## Comandos no servidor

Ative o virtualenv e instale a partir da pasta **Diario_obra** (onde está o `manage.py` e o `requirements-cpanel.txt`):

```bash
cd /home/lplan/sistema_lplan/Diario_obra
source /home/lplan/virtualenv/sistema_lplan/3.11/bin/activate
pip install -r requirements-cpanel.txt
```

Se no seu servidor a pasta tiver outro nome (por exemplo `public_html/sistema_lplan/Diario_obra`), ajuste o `cd` para o caminho correto.

Depois:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

O Django e a geração de PDF (WeasyPrint 52.x) devem funcionar normalmente.
