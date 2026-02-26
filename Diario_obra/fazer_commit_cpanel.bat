@echo off
REM Execute na raiz do repo (pasta onde esta o .git)
REM Commit apenas dos arquivos seguros: cPanel + correcao PDF (WeasyPrint 52)

cd /d "%~dp0"
if exist "manage.py" cd ..
if not exist ".git" (
  echo Erro: execute na raiz do repositorio (Lplan_Sistema) ou dentro de Diario_obra.
  pause
  exit /b 1
)

REM Adiciona APENAS estes arquivos (nao adiciona .env, db, media, etc.)
git add Diario_obra/requirements-cpanel.txt
git add Diario_obra/CPANEL_PIP.md
git add Diario_obra/ESTRUTURA_CPANEL.md
git add Diario_obra/core/utils/pdf_generator.py

git status
echo.
echo Confira acima: so devem aparecer esses 4 arquivos. Nao deve ter .env, db.sqlite3, media.
echo.
set /p OK="Fazer commit? (s/n): "
if /i not "%OK%"=="s" exit /b 0

git commit -m "cPanel: requirements-cpanel.txt (evita pycairo/meson) + doc + PDF WeasyPrint 52 compat"
echo.
echo Pronto. Agora no cPanel: cd sistema_lplan && git pull
pause
