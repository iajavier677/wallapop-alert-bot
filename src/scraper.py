import time
import requests
from urllib.parse import urlencode
from src import config

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


def _extract_item(obj: dict) -> dict | None:
    """Extrae la información de un anuncio a partir de la respuesta de Wallapop."""
    # En la API de Wallapop, los datos pueden venir en la raíz o dentro de 'content'
    item = obj.get("content", {})
    if isinstance(item, dict) and "item" in item:
        item = item["item"]
    if not isinstance(item, dict) or "title" not in item:
        item = obj

    item_id = str(item.get("id", ""))
    title = item.get("title", "")
    if not title:
        return None

    # Precio
    raw_price = item.get("price", 0)
    if isinstance(raw_price, dict):
        raw_price = raw_price.get("amount", 0)
    try:
        price = int(float(raw_price))
    except (ValueError, TypeError):
        price = 0

    # Ubicación
    loc = item.get("location", {})
    city = loc.get("city", "") if isinstance(loc, dict) else str(loc or "")

    # Estado
    condition = item.get("condition", "") or item.get("status", "")

    # URL
    web_slug = item.get("web_slug", "")
    if web_slug:
        url = f"https://es.wallapop.com/item/{web_slug}"
    elif item_id:
        url = f"https://es.wallapop.com/item/{item_id}"
    else:
        url = "https://es.wallapop.com"

    return {
        "id": item_id,
        "title": title,
        "price": price,
        "condition": condition,
        "location": city,
        "url": url,
    }


def search_term(term: str) -> list[dict]:
    """Busca anuncios en Wallapop para un término específico usando su API interna."""
    url = "https://api.wallapop.com/api/v3/general/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9",
        "X-DeviceOS": "0",
    }

    params = {
        "keywords": term,
        "min_sale_price": config.CONFIG["price_min"],
        "max_sale_price": config.CONFIG["price_max"],
        "order_by": "newest",
    }

    # Ubicación y coordenadas
    loc_name = config.CONFIG.get("location", "").strip().lower()
    if loc_name in CITY_COORDINATES:
        lat, lon = CITY_COORDINATES[loc_name]
        params["latitude"] = lat
        params["longitude"] = lon
        if config.CONFIG.get("radius_km"):
            params["distance_in_km"] = config.CONFIG["radius_km"]

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            search_objects = data.get("search_objects", [])
            items = []
            for obj in search_objects:
                parsed = _extract_item(obj)
                if parsed:
                    items.append(parsed)
            return items
        else:
            print(f"[scraper] Respuesta no exitosa ({resp.status_code}) para '{term}'")
            return []
    except Exception as e:
        print(f"[scraper] Error buscando '{term}': {e}")
        return []


def fetch_items() -> list[dict]:
    """Obtiene los anuncios de todos los términos configurados individualmente."""
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

        time.sleep(1)  # Pausa breve para evitar bloqueos por frecuencia

    return all_items

