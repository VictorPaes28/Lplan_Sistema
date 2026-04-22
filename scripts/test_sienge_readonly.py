import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lplan_central.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from suprimentos.services.sienge_provider import APISiengeProvider  # noqa: E402


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
    username = (getattr(settings, "SIENGE_API_USERNAME", "") or "").strip()
    password = (getattr(settings, "SIENGE_API_PASSWORD", "") or "").strip()
    auth_mode = (getattr(settings, "SIENGE_API_AUTH_MODE", "auto") or "auto").strip().lower()
    token_url = (getattr(settings, "SIENGE_API_TOKEN_URL", "") or "").strip()
    mapa_tpl = (getattr(settings, "SIENGE_API_MAPA_ENDPOINT_TEMPLATE", "") or "").strip()

    print("Base URL:", base_url or "(vazio)")
    print("Auth mode:", auth_mode)
    print("Client ID:", _safe(client_id))
    print("Client Secret:", _safe(client_secret))
    print("Username:", _safe(username))
    print("Password:", _safe(password))
    print("Token URL:", token_url or "(padrao)")
    print("Mapa endpoint template:", mapa_tpl or "(padrao)")

    if not base_url:
        print("RESULTADO: SIENGE_API_BASE_URL vazio no .env.")
        return

    provider = APISiengeProvider(
        base_url,
        client_id,
        client_secret,
        username=username,
        password=password,
        auth_mode=auth_mode,
        token_url=token_url,
        mapa_endpoint_template=mapa_tpl,
    )

    try:
        headers = provider._get_headers()  # teste de auth (somente leitura)
        auth_header = headers.get("Authorization", "")
        print("AUTH: OK (modo resolvido). Header:", auth_header.split(" ", 1)[0] if auth_header else "(sem auth)")
    except Exception as e:
        print("AUTH: FALHOU ->", str(e))
        return

    # Tentativa de leitura sem escrita externa
    obra_codigo = "259"  # pode ajustar depois
    try:
        items = provider.fetch_items(obra_codigo=obra_codigo)
        print(f"READ: OK para obra {obra_codigo}. Itens retornados: {len(items)}")
        if items:
            sample = items[0]
            print("Sample keys:", sorted(list(sample.keys()))[:10], "...")
    except Exception as e:
        print(f"READ: FALHOU para obra {obra_codigo} -> {e}")


if __name__ == "__main__":
    run()
