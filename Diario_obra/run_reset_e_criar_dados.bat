@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Executando: python manage.py reset_e_criar_dados
python manage.py reset_e_criar_dados
pause
