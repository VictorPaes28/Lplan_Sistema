import os


def get_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, str(default))
    return str(value).lower() in ("1", "true", "yes", "on")


def get_str(name: str, default: str = "") -> str:
    return str(os.environ.get(name, default)).strip()


INTEGRATIONS_ENABLED = get_bool("INTEGRATIONS_ENABLED", True)

AZURE_TENANT_ID = get_str("AZURE_TENANT_ID")
AZURE_CLIENT_ID = get_str("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = get_str("AZURE_CLIENT_SECRET")
AZURE_BOT_APP_ID = get_str("AZURE_BOT_APP_ID", AZURE_CLIENT_ID)
AZURE_BOT_APP_SECRET = get_str("AZURE_BOT_APP_SECRET", AZURE_CLIENT_SECRET)

TEAMS_ENABLED = get_bool("TEAMS_ENABLED", False)
TEAMS_TEAM_ID = get_str("TEAMS_TEAM_ID")
TEAMS_CHANNEL_ID = get_str("TEAMS_CHANNEL_ID")
TEAMS_DEFAULT_MESSAGE_PREFIX = get_str("TEAMS_DEFAULT_MESSAGE_PREFIX", "[LPLAN]")

POWERBI_ENABLED = get_bool("POWERBI_ENABLED", False)
POWERBI_WORKSPACE_ID = get_str("POWERBI_WORKSPACE_ID")
POWERBI_DATASET_ID = get_str("POWERBI_DATASET_ID")

SHAREPOINT_ENABLED = get_bool("SHAREPOINT_ENABLED", False)
SHAREPOINT_SITE_ID = get_str("SHAREPOINT_SITE_ID")
SHAREPOINT_DRIVE_ID = get_str("SHAREPOINT_DRIVE_ID")

SIGNATURE_ENABLED = get_bool("SIGNATURE_ENABLED", False)
SIGNATURE_PROVIDER = get_str("SIGNATURE_PROVIDER", "clicksign")
SIGNATURE_API_KEY = get_str("SIGNATURE_API_KEY")
SIGNATURE_WEBHOOK_SECRET = get_str("SIGNATURE_WEBHOOK_SECRET")

OPERATIONS_ENABLED = get_bool("OPERATIONS_ENABLED", False)
PONTO_API_URL = get_str("PONTO_API_URL")
PONTO_API_TOKEN = get_str("PONTO_API_TOKEN")
ERP_API_URL = get_str("ERP_API_URL")
ERP_API_TOKEN = get_str("ERP_API_TOKEN")
GEO_PROVIDER = get_str("GEO_PROVIDER", "azure_maps")
GEO_API_KEY = get_str("GEO_API_KEY")

