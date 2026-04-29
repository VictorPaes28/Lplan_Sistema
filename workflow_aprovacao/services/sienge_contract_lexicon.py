"""
Referência cruzada: textos da ajuda Sienge (Suprimentos / contratos) ↔ campos da API.

A API GET /v1/supply-contracts/all devolve campos como ``status``, ``statusApproval``,
``isAuthorized`` (nomes conforme payload real do tenant).

Documentação de interface (filtros e colunas), não substitui o OpenAPI do Sienge:
https://ajuda.sienge.com.br/support/solutions/articles/153000199483-suprimentos-contratos-e-medic%C3%B5es-como-funciona-a-nova-consulta-de-contratos-
"""

from __future__ import annotations

# Situação de *autorização* do contrato — textos citados na coluna / filtros da Sienge (3).
SIENGE_SITUACAO_AUTORIZACAO_CONTRATO_UI = (
    'Aguardando autorização',
    'Autorizado',
    'Reprovado',
)

# O código integra pendência com ``isAuthorized is not True`` (ver sienge_measurement_sync).
