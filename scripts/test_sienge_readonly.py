"""
Diagnóstico local Sienge só para a Central de Aprovações:

  - Contratos de suprimentos (lista + detalhe)
  - Medições de contrato (BM / medição)

NÃO usa: pedido de compra, SC, NF de compra, mapa de suprimentos nem suprimentos.APISiengeProvider.

Uso: python scripts/test_sienge_readonly.py

Opcional no .env:
  SIENGE_TEST_DOCUMENT_ID, SIENGE_TEST_CONTRACT_NUMBER — GET /v1/supply-contracts (detalhe)
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lplan_central.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from workflow_aprovacao.services.sienge_api import SiengeCentralApiClient  # noqa: E402


def _probe_get(client: SiengeCentralApiClient, label: str, path: str, params=None) -> None:
    if params is None:
        params = {}
    try:
        r = client.get_http_response(path, params)
    except Exception as exc:
        print(f"  {label}: ERRO -> {exc}")
        return

    ctype = (r.headers.get("content-type") or "").split(";")[0].strip()
    print(f"  {label}: HTTP {r.status_code} ({ctype})")

    snippet = (r.text or "").strip()
    if not snippet:
        return
    if "application/json" in (r.headers.get("content-type") or ""):
        try:
            data = r.json()
        except Exception:
            print(f"    corpo (texto): {snippet[:400]}")
            return
        if isinstance(data, dict):
            keys = list(data.keys())[:15]
            print(f"    JSON keys: {keys}")
            for k in ("data", "results", "items", "content", "resultSet"):
                if k in data and isinstance(data[k], list):
                    print(f"    {k}: lista com {len(data[k])} elemento(s)")
                    if data[k]:
                        row = data[k][0]
                        if isinstance(row, dict):
                            print(f"    primeiro item keys: {list(row.keys())[:12]}")
                            if r.status_code == 200:
                                ex = {k: row.get(k) for k in list(row.keys())[:6]}
                                print(f"    exemplo (primeiros campos): {ex}")
                    return
            if "message" in data:
                print(f"    message: {data.get('message')}")
            if "clientMessage" in data or "developerMessage" in data:
                print(
                    "    Sienge:",
                    data.get("clientMessage") or data.get("developerMessage"),
                )
            if "errors" in data:
                print(f"    errors: {data.get('errors')}")
        elif isinstance(data, list):
            print(f"    lista raiz: {len(data)} elemento(s)")
            if data and isinstance(data[0], dict):
                print(f"    primeiro item keys: {list(data[0].keys())[:12]}")
    else:
        print(f"    corpo: {snippet[:350]}")


def _safe(v: str) -> str:
    if not v:
        return "(vazio)"
    if len(v) <= 6:
        return "*" * len(v)
    return f"{v[:3]}***{v[-2:]}"


def run():
    base_url = (getattr(settings, "SIENGE_API_BASE_URL", "") or "").strip()
    client_id = (getattr(settings, "SIENGE_API_CLIENT_ID", "") or "").strip()
    client_secret = (getattr(settings, "SIENGE_API_CLIENT_SECRET", "") or "").strip()

    print("Base URL:", base_url or "(vazio)")
    print("Client ID:", _safe(client_id))
    print("Client Secret:", _safe(client_secret))
    print("(Central: apenas contratos/medições de suprimentos — sem pedido de compra.)")

    if not base_url:
        print("RESULTADO: SIENGE_API_BASE_URL vazio no .env.")
        return

    client = SiengeCentralApiClient()

    try:
        client.get_json("/v1/supply-contracts/all", {"limit": 1})
        print("AUTH: OK (Basic).")
    except Exception as e:
        print("AUTH / primeira chamada: FALHOU ->", str(e))
        return

    print("\n--- Lista de contratos de suprimentos ---")
    _probe_get(client, "/v1/supply-contracts/all", "/v1/supply-contracts/all", {"limit": 5})

    print("\n--- Medições (todas / listagem) ---")
    rest_paths = [
        ("/v1/supply-contracts/measurements/all", {"limit": 5}),
        ("/v1/supply-contracts/measurements", {"limit": 5}),
        ("/v1/supply-contracts/measurements/items", {"limit": 5}),
        ("/v1/supply-contracts/measurements/clearing", {"limit": 5}),
        ("/v1/supply-contracts/measurements/attachments/all", {"limit": 5}),
    ]
    for path, prm in rest_paths:
        _probe_get(client, path, path, prm)

    print("\n--- Itens da 1ª medição em .../measurements/all ---")
    try:
        r0 = client.get_http_response("/v1/supply-contracts/measurements/all", {"limit": 1})
        if r0.status_code == 200 and "application/json" in (r0.headers.get("content-type") or ""):
            payload = r0.json()
            rows = payload.get("results") or payload.get("data") or []
            if rows and isinstance(rows[0], dict):
                m0 = rows[0]
                prm_items = {
                    "documentId": m0.get("documentId"),
                    "contractNumber": m0.get("contractNumber"),
                    "buildingId": m0.get("buildingId"),
                    "measurementNumber": m0.get("measurementNumber"),
                }
                if all(prm_items.get(k) is not None for k in prm_items):
                    _probe_get(
                        client,
                        "/v1/supply-contracts/measurements/items",
                        "/v1/supply-contracts/measurements/items",
                        prm_items,
                    )
                else:
                    print("  (primeiro registo sem campos para items)")
            else:
                print("  (lista vazia)")
        else:
            print(f"  measurements/all -> HTTP {r0.status_code}")
    except Exception as exc:
        print("  ERRO ->", exc)

    doc_id = (os.environ.get("SIENGE_TEST_DOCUMENT_ID") or "").strip()
    ctr_num = (os.environ.get("SIENGE_TEST_CONTRACT_NUMBER") or "").strip()
    if doc_id and ctr_num:
        print("\n--- Detalhe contrato (documentId + contractNumber) ---")
        _probe_get(
            client,
            "/v1/supply-contracts",
            "/v1/supply-contracts",
            {"documentId": doc_id, "contractNumber": ctr_num},
        )


if __name__ == "__main__":
    run()
