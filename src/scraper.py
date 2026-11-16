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
    """Busca anuncios para un término usando el flujo oficial v3 de Wallapop."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Origin": "https://es.wallapop.com",
        "Referer": "https://es.wallapop.com/",
        "X-DeviceOS": "0",
    }

    params = {
        "source": "search_box",
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

    # Paso 1: Obtener search_id desde /api/v3/search/components
    components_url = "https://api.wallapop.com/api/v3/search/components"
    search_id = None
    try:
        r1 = session.get(components_url, headers=headers, params=params, timeout=10)
        if r1.status_code == 200:
            data1 = r1.json()
            # Si components ya trae items en su payload, los extraemos
            raw_items = (
                data1.get("section", {}).get("payload", {}).get("items", [])
                or data1.get("search_objects", [])
                or []
            )
            if raw_items:
                items = [_extract_item(x) for x in raw_items if _extract_item(x)]
                if items:
                    print(f"[scraper] {len(items)} anuncios obtenidos en components.")
                    return items

            # Extraer el search_id para el paso 2
            search_id = _find_key_recursive(data1, "search_id")
            if search_id:
                print(f"[scraper] Obtenido search_id: {search_id}")
        else:
            snippet = r1.text[:100].replace("\n", " ") if r1.text else ""
            print(f"[scraper] {components_url} -> {r1.status_code}: {snippet}")
    except Exception as e:
        print(f"[scraper] Error en components: {e}")

    if not search_id:
        print(f"[scraper] No se obtuvo search_id para '{term}'")
        return []

    # Paso 2: Obtener los productos desde /api/v3/search/section usando ÚNICAMENTE search_id
    section_url = "https://api.wallapop.com/api/v3/search/section"
    section_params = {
        "search_id": search_id,
    }

    try:
        r2 = session.get(section_url, headers=headers, params=section_params, timeout=10)
        if r2.status_code == 200:
            data2 = r2.json()
            raw_items = (
                data2.get("section", {}).get("payload", {}).get("items", [])
                or data2.get("items", [])
                or _find_key_recursive(data2, "items")
                or []
            )
            items = []
            for raw in raw_items:
                parsed = _extract_item(raw)
                if parsed:
                    items.append(parsed)
            print(f"[scraper] /search/section -> {len(items)} anuncios encontrados.")
            return items
        else:
            snippet = r2.text[:100].replace("\n", " ") if r2.text else ""
            print(f"[scraper] /search/section -> Código {r2.status_code}: {snippet}")
            return []
    except Exception as e:
        print(f"[scraper] Error en section: {e}")
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




