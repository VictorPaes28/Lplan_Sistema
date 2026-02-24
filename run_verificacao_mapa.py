#!/usr/bin/env python
"""Roda a verificação do Mapa de Suprimentos. Executar na raiz: python run_verificacao_mapa.py"""
import os
import sys

# Garantir que estamos no Diario_obra para Django
raiz = os.path.dirname(os.path.abspath(__file__))
diario_obra = os.path.join(raiz, 'Diario_obra')
if not os.path.isdir(diario_obra):
    print('Pasta Diario_obra nao encontrada em', raiz)
    sys.exit(1)
os.chdir(diario_obra)
sys.path.insert(0, diario_obra)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lplan_central.settings')
import django
django.setup()

from suprimentos.management.commands.verificar_mapa_suprimentos import Command
c = Command()
c.handle(verbose=True)
