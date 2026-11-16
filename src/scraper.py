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


def _extract_item(item: dict) -> dict | None:
    """Extrae la información de un anuncio a partir de un elemento de Wallapop v3."""
    if not isinstance(item, dict):
        return None

    # Ignorar anuncios ya reservados o vendidos
    if item.get("reserved") or item.get("flags", {}).get("reserved"):
        return None

    # Si viene anidado en 'item'
    if "item" in item and isinstance(item["item"], dict):
        item = item["item"]

    item_id = str(item.get("id", ""))
    title = item.get("title", "")
    if not title:
        return None

    # Precio (soporta int, float, price.amount y price.cash.amount)
    raw_price = item.get("price", 0)
    if isinstance(raw_price, dict):
        raw_price = raw_price.get("amount") or raw_price.get("cash", {}).get("amount", 0)
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



def _find_key_recursive(d, target="search_id"):
    """Busca una clave recursivamente en cualquier nivel del diccionario o lista."""
    if isinstance(d, dict):
        if target in d and d[target]:
            return d[target]
        for v in d.values():
            res = _find_key_recursive(v, target)
            if res:
                return res
    elif isinstance(d, list):
        for item in d:
            res = _find_key_recursive(item, target)
            if res:
                return res
    return None


def search_term(term: str) -> list[dict]:
    """Busca anuncios para un término usando la API v3 de Wallapop."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Origin": "https://es.wallapop.com",
        "Referer": "https://es.wallapop.com/",
        "X-DeviceOS": "0",
    }

    params = {
        "keywords": term,
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

    session = requests.Session(impersonate="chrome") if HAS_CURL_CFFI else requests.Session()

    # VÍA 1: Endpoint directo /api/v3/search (devuelve los productos en una sola llamada)
    direct_url = "https://api.wallapop.com/api/v3/search"
    try:
        r = session.get(direct_url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            raw_items = (
                data.get("data", {}).get("section", {}).get("payload", {}).get("items", [])
                or data.get("section", {}).get("payload", {}).get("items", [])
                or data.get("search_objects", [])
                or _find_key_recursive(data, "items")
                or []
            )
            items = []
            for raw in raw_items:
                parsed = _extract_item(raw)
                if parsed:
                    items.append(parsed)
            if items:
                print(f"[scraper] /api/v3/search directo -> {len(items)} anuncios encontrados con éxito.")
                return items
            else:
                keys = list(data.keys()) if isinstance(data, dict) else type(data)
                print(f"[scraper] /api/v3/search devolvió 200. Claves disponibles: {keys}")
        else:
            print(f"[scraper] /api/v3/search -> Código {r.status_code}")
    except Exception as e:
        print(f"[scraper] Error en /api/v3/search directo: {e}")

    # VÍA 2: Endpoint /api/v3/search/components
    components_url = "https://api.wallapop.com/api/v3/search/components"
    try:
        r = session.get(components_url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            # Comprobar si components ya traía items
            raw_items = (
                data.get("section", {}).get("payload", {}).get("items", [])
                or data.get("search_objects", [])
                or _find_key_recursive(data, "items")
                or []
            )
            if raw_items:
                items = []
                for raw in raw_items:
                    parsed = _extract_item(raw)
                    if parsed:
                        items.append(parsed)
                if items:
                    print(f"[scraper] /search/components -> {len(items)} anuncios encontrados.")
                    return items

            # Si no hay items directos, extraer search_id
            search_id = _find_key_recursive(data, "search_id")
            if search_id:
                section_url = f"https://api.wallapop.com/api/v3/search/section?search_id={search_id}&step=0"
                r2 = session.get(section_url, headers=headers, timeout=10)
                if r2.status_code == 200:
                    sec_data = r2.json()
                    sec_items = (
                        sec_data.get("section", {}).get("payload", {}).get("items", [])
                        or _find_key_recursive(sec_data, "items")
                        or []
                    )
                    items = []
                    for raw in sec_items:
                        parsed = _extract_item(raw)
                        if parsed:
                            items.append(parsed)
                    if items:
                        return items
                else:
                    snippet = r2.text[:100].replace("\n", " ") if r2.text else ""
                    print(f"[scraper] {section_url} -> {r2.status_code}: {snippet}")
    except Exception as e:
        print(f"[scraper] Error en vía components: {e}")

    return []





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




