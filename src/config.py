import os
from pathlib import Path
# Load .env variables if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed – ignore (defaults will be used)
    pass

# Load configuration from environment variables or a .env file.
# Example variables:
#   WALLAPOP_SEARCH_URL – URL de búsqueda de Wallapop con los filtros base.
#   PRICE_MIN, PRICE_MAX – rango de precios.
#   CONDITIONS – lista de estados permitidos (separados por comas).
#   LOCATION – ciudad o zona.
#   TELEGRAM_TOKEN, TELEGRAM_CHAT_ID – credenciales para enviar notificaciones.
#   SCRAPE_INTERVAL – intervalo en segundos entre ejecuciones (default 300).

BASE_DIR = Path(__file__).resolve().parent.parent

# Helper to read env vars with defaults
def get_env(name: str, default: str | None = None) -> str:
    return os.getenv(name, default)

# Configuration dictionary
CONFIG = {
    "search_url": get_env("WALLAPOP_SEARCH_URL", "https://es.wallapop.com/search"),
    "price_min": int(get_env("PRICE_MIN", "0")),
    "price_max": int(get_env("PRICE_MAX", "10000")),
    "conditions": [c.strip() for c in get_env("CONDITIONS", "Nuevo,Como nuevo").split(",")],
    "location": get_env("LOCATION", ""),
    "telegram_token": get_env("TELEGRAM_TOKEN", ""),
    "telegram_chat_id": get_env("TELEGRAM_CHAT_ID", ""),
    "radius_km": int(get_env("RADIUS_KM", "0")),
    "scrape_interval": int(get_env("SCRAPE_INTERVAL", "300")),
    "search_terms": [t.strip() for t in get_env("SEARCH_TERMS", "").split(",") if t.strip()],
}
