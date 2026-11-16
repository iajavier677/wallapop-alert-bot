import time
import json
import re
from bs4 import BeautifulSoup
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


def _extract_item(obj: dict) -> dict | None:
    """Extrae la información de un anuncio a partir de un objeto JSON de Wallapop."""
    if not isinstance(obj, dict):
        return None

    # En la API de Wallapop, los datos pueden venir directamente o dentro de 'content' / 'item'
    item = obj.get("content", obj)
    if isinstance(item, dict) and "item" in item:
        item = item["item"]
    if not isinstance(item, dict):
        return None

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


def _search_api(term: str) -> list[dict]:
    """Intenta buscar vía la API interna de Wallapop (search/components)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Origin": "https://es.wallapop.com",
        "Referer": "https://es.wallapop.com/",
        "X-DeviceOS": "0",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }

    params = {
        "keywords": term,
        "source": "search_box",
        "min_sale_price": config.CONFIG["price_min"],
        "max_sale_price": config.CONFIG["price_max"],
        "order_by": "newest",
    }

    loc_name = config.CONFIG.get("location", "").strip().lower()
    if loc_name in CITY_COORDINATES:
        lat, lon = CITY_COORDINATES[loc_name]
        params["latitude"] = lat
        params["longitude"] = lon
        if config.CONFIG.get("radius_km"):
            params["distance_in_km"] = config.CONFIG["radius_km"]

    # Probamos primero el endpoint moderno /api/v3/search/components
    endpoints = [
        "https://api.wallapop.com/api/v3/search/components",
        "https://api.wallapop.com/api/v3/general/search",
    ]

    for url in endpoints:
        try:
            if HAS_CURL_CFFI:
                resp = requests.get(url, headers=headers, params=params, timeout=10, impersonate="chrome")
            else:
                resp = requests.get(url, headers=headers, params=params, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                items = []
                # Formato search_objects
                search_objects = data.get("search_objects", [])
                for obj in search_objects:
                    parsed = _extract_item(obj)
                    if parsed:
                        items.append(parsed)
                # Formato sections (components)
                sections = data.get("sections", [])
                for sec in sections:
                    for obj in sec.get("items", []) or sec.get("elements", []):
                        parsed = _extract_item(obj)
                        if parsed:
                            items.append(parsed)
                if items:
                    return items
            else:
                snippet = resp.text[:120].replace("\n", " ") if resp.text else ""
                print(f"[scraper-api] {url} -> Código {resp.status_code}: {snippet}")
        except Exception as e:
            print(f"[scraper-api] Error en {url}: {e}")

    return []


def _search_web(term: str) -> list[dict]:
    """Fallback: descarga el HTML de búsqueda de Wallapop y extrae el JSON __NEXT_DATA__."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://es.wallapop.com/",
    }

    params = {
        "keywords": term,
        "min_sale_price": config.CONFIG["price_min"],
        "max_sale_price": config.CONFIG["price_max"],
    }

    url = "https://es.wallapop.com/search"
    try:
        if HAS_CURL_CFFI:
            resp = requests.get(url, headers=headers, params=params, timeout=12, impersonate="chrome")
        else:
            resp = requests.get(url, headers=headers, params=params, timeout=12)

        if resp.status_code != 200:
            snippet = resp.text[:120].replace("\n", " ") if resp.text else ""
            print(f"[scraper-web] Código {resp.status_code}: {snippet}")
            return []

        # Buscar el script con ID __NEXT_DATA__
        soup = BeautifulSoup(resp.text, "html.parser")
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data and next_data.string:
            json_data = json.loads(next_data.string)
            page_props = json_data.get("props", {}).get("pageProps", {})
            raw_items = page_props.get("items", []) or page_props.get("searchObjects", [])
            items = []
            for raw in raw_items:
                parsed = _extract_item(raw)
                if parsed:
                    items.append(parsed)
            return items
    except Exception as e:
        print(f"[scraper-web] Error extrayendo HTML: {e}")

    return []


def search_term(term: str) -> list[dict]:
    """Busca anuncios para un término usando la API o el scraper web como respaldo."""
    # 1. Intentar API
    items = _search_api(term)
    if items:
        return items

    # 2. Si la API da 403, intentar extracción web de Next.js
    items = _search_web(term)
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



