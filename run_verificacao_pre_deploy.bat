@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
echo ========================================
echo Verificacao pre-deploy - Lplan Sistema
echo (executando na raiz: %ROOT%)
echo ========================================
echo.

echo [1/3] Diario_obra
echo ---
cd /d "%ROOT%Diario_obra"
python manage.py check
if errorlevel 1 (echo CHECK FALHOU: Diario_obra & set ERR=1)
python manage.py showmigrations 2>nul | findstr /C:"[ ]"
if errorlevel 1 (echo Migrations aplicadas ou nenhuma pendente.) else (echo ATENCAO: existem migrations nao aplicadas [ ].)
python manage.py verificar_pre_deploy 2>nul
python manage.py verificar_mapa_suprimentos 2>nul
python manage.py verify_dashboard_data 2>nul
echo.

echo [2/3] Gestao_aprovacao
echo ---
cd /d "%ROOT%Gestao_aprovacao"
python manage.py check
if errorlevel 1 (echo CHECK FALHOU: Gestao_aprovacao & set ERR=1)
python manage.py showmigrations 2>nul | findstr /C:"[ ]"
if errorlevel 1 (echo Migrations aplicadas ou nenhuma pendente.) else (echo ATENCAO: existem migrations nao aplicadas [ ].)
echo.

echo [3/3] Mapa_Controle
echo ---
cd /d "%ROOT%Mapa_Controle"
python manage.py check
if errorlevel 1 (echo CHECK FALHOU: Mapa_Controle & set ERR=1)
python manage.py showmigrations 2>nul | findstr /C:"[ ]"
if errorlevel 1 (echo Migrations aplicadas ou nenhuma pendente.) else (echo ATENCAO: existem migrations nao aplicadas [ ].)
python manage.py verificar_mapa_suprimentos 2>nul
echo.

echo ========================================
echo Testes (Diario_obra e Mapa_Controle)
echo ========================================
cd /d "%ROOT%Diario_obra"
python manage.py test core suprimentos --verbosity=1
echo.
cd /d "%ROOT%Mapa_Controle"
python manage.py test suprimentos --verbosity=1
echo.

echo ========================================
echo Fim da verificacao. Confira erros acima.
echo ========================================
if defined ERR exit /b 1
exit /b 0
