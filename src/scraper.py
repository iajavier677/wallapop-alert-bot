import re
import time
import json
from src import config

try:
    from curl_cffi import requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests
    HAS_CURL_CFFI = False

# Coordenadas de ciudades frecuentes para búsquedas por radio en Wallapop
CITY_COORDINATES = {
    "valencia": (39.4699, -0.3763),
    "madrid": (40.4168, -3.7038),
    "barcelona": (41.3879, 2.1699),
    "sevilla": (37.3891, -5.9845),
    "zaragoza": (41.6488, -0.8891),
    "malaga": (36.7213, -4.4214),
    "bilbao": (43.2630, -2.9350),
    "alicante": (38.3452, -0.4810),
}


def _parse_price(raw_price) -> int:
    """Extrae un precio entero de cualquier formato (int, float, dict, string con €)."""
    if isinstance(raw_price, dict):
        raw_price = raw_price.get("amount") or raw_price.get("cash", {}).get("amount", 0)
    if isinstance(raw_price, (int, float)):
        return int(raw_price)
    if isinstance(raw_price, str):
        cleaned = re.sub(r'[^\d.]', '', raw_price.replace(',', '.'))
        if cleaned:
            try:
                return int(float(cleaned))
            except ValueError:
                return 0
    return 0


def _extract_item(data: dict) -> dict | None:
    """Extrae la información de un anuncio a partir de un objeto JSON de Wallapop v3."""
    if not isinstance(data, dict):
        return None

    # Filtrar banners o publicidades
    if data.get("type") in ("ads_banner", "banner", "ad", "bumped"):
        return None

    # Filtrar reservados o vendidos
    reserved = data.get("reserved")
    if isinstance(reserved, dict):
        if reserved.get("flag"):
            return None
    elif reserved:
        return None

    if data.get("flags", {}).get("reserved"):
        return None

    # Debe tener id y título
    item_id = str(data.get("id") or "")
    title = data.get("title") or ""
    if not item_id or not title or not isinstance(title, str) or len(title.strip()) < 2:
        return None

    # Precio
    price = _parse_price(data.get("price", 0))
    if price <= 0:
        return None

    # Ubicación
    loc = data.get("location") or {}
    city = loc.get("city", "") if isinstance(loc, dict) else str(loc or "")

    # Estado / condición
    condition = data.get("condition") or data.get("status") or ""

    # URL
    web_slug = data.get("web_slug") or ""
    if web_slug:
        url = f"https://es.wallapop.com/item/{web_slug}"
    else:
        url = f"https://es.wallapop.com/item/{item_id}"

    return {
        "id": item_id,
        "title": title.strip(),
        "price": price,
        "condition": condition,
        "location": city,
        "url": url,
    }


def search_term(term: str) -> list[dict]:
    """Busca anuncios para un término usando la API v3 /search de Wallapop."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Origin": "https://es.wallapop.com",
        "Referer": "https://es.wallapop.com/",
        "X-DeviceOS": "0",
    }

    # Parámetros obligatorios: source y order_by son requeridos por /api/v3/search
    params = {
        "source": "search_box",
        "keywords": term,
        "order_by": "newest",
    }

    # Filtros de precio (solo si son razonables)
    price_min = config.CONFIG.get("price_min", 0)
    price_max = config.CONFIG.get("price_max", 10000)
    if price_min > 0:
        params["min_sale_price"] = str(price_min)
    if price_max < 10000:
        params["max_sale_price"] = str(price_max)

    # Ubicación
    loc_name = config.CONFIG.get("location", "").strip().lower()
    if loc_name in CITY_COORDINATES:
        lat, lon = CITY_COORDINATES[loc_name]
        params["latitude"] = str(lat)
        params["longitude"] = str(lon)
        radius = config.CONFIG.get("radius_km", 0)
        if radius > 0:
            params["distance_in_km"] = str(radius)

    session = (
        requests.Session(impersonate="chrome")
        if HAS_CURL_CFFI
        else requests.Session()
    )

    url = "https://api.wallapop.com/api/v3/search"
    items = []

    try:
        r = session.get(url, headers=headers, params=params, timeout=12)
        print(f"[scraper] /api/v3/search -> {r.status_code}")

        if r.status_code == 200:
            data = r.json()
            # Estructura: data.section.payload.items
            payload = (
                data.get("data", {})
                .get("section", {})
                .get("payload", {})
            )
            raw_items = payload.get("items", [])
            print(f"[scraper] Items brutos recibidos: {len(raw_items)}")

            for raw in raw_items:
                parsed = _extract_item(raw)
                if parsed:
                    items.append(parsed)

            print(f"[scraper] Items válidos tras filtro: {len(items)}")
        else:
            snippet = r.text[:200].replace("\n", " ") if r.text else ""
            print(f"[scraper] Respuesta {r.status_code}: {snippet}")
    except Exception as e:
        print(f"[scraper] Error: {e}")

    return items


def fetch_items() -> list[dict]:
    """Obtiene los anuncios de todos los términos configurados individualmente."""
    print(f"[scraper] curl_cffi activo: {HAS_CURL_CFFI}")
    search_terms = config.CONFIG.get("search_terms") or [""]
    all_items = []
    seen_in_batch = set()

    for term in search_terms:
        term_clean = term.strip()
        if not term_clean:
            continue
        print(f"[scraper] Buscando en Wallapop: '{term_clean}'...")
        term_items = search_term(term_clean)
        print(f"[scraper] '{term_clean}' -> {len(term_items)} anuncios encontrados.")

        for item in term_items:
            if item["id"] and item["id"] not in seen_in_batch:
                seen_in_batch.add(item["id"])
                all_items.append(item)

        time.sleep(1.5)

    return all_items
