import time
import json
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


def _extract_item(data: dict) -> dict | None:
    """Extrae la información de un anuncio a partir de un objeto JSON de Wallapop v3."""
    if not isinstance(data, dict):
        return None

    # Filtrar banners o publicidades
    if data.get("type") in ("ads_banner", "banner", "ad"):
        return None

    # Filtrar reservados o vendidos
    if data.get("reserved") or data.get("flags", {}).get("reserved"):
        return None

    item = data.get("item", data)
    if not isinstance(item, dict):
        return None

    # Debe tener id y título
    item_id = str(item.get("id") or data.get("id") or "")
    title = item.get("title") or data.get("title") or ""
    if not item_id or not title or not isinstance(title, str) or len(title.strip()) < 2:
        return None

    # Precio
    raw_price = item.get("price") or data.get("price") or 0
    if isinstance(raw_price, dict):
        raw_price = raw_price.get("amount") or raw_price.get("cash", {}).get("amount", 0)
    try:
        price = int(float(raw_price))
    except (ValueError, TypeError):
        price = 0

    if price <= 0:
        return None

    # Ubicación
    loc = item.get("location") or data.get("location") or {}
    city = loc.get("city", "") if isinstance(loc, dict) else str(loc or "")

    # Estado
    condition = item.get("condition") or data.get("condition") or item.get("status") or ""

    # URL
    web_slug = item.get("web_slug") or data.get("web_slug") or ""
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


def _collect_items_recursive(data, collected=None, seen_ids=None) -> list[dict]:
    """Rastrea exhaustivamente cualquier JSON y extrae todos los anuncios válidos."""
    if collected is None:
        collected = []
    if seen_ids is None:
        seen_ids = set()

    if isinstance(data, dict):
        item = _extract_item(data)
        if item and item["id"]:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                collected.append(item)
            return collected

        for v in data.values():
            if isinstance(v, (dict, list)):
                _collect_items_recursive(v, collected, seen_ids)

    elif isinstance(data, list):
        for elem in data:
            if isinstance(elem, (dict, list)):
                _collect_items_recursive(elem, collected, seen_ids)

    return collected




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
    session = requests.Session(impersonate="chrome") if HAS_CURL_CFFI else requests.Session()
    try:
        resp = session.get(url, headers=headers, params=params, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            next_data = soup.find("script", id="__NEXT_DATA__")
            if next_data and next_data.string:
                json_data = json.loads(next_data.string)
                items = _collect_items_recursive(json_data)
                if items:
                    print(f"[scraper-web] {len(items)} anuncios obtenidos vía __NEXT_DATA__.")
                    return items
                else:
                    print("[scraper-web] __NEXT_DATA__ encontrado pero 0 items cumplieron formato.")
            else:
                print(f"[scraper-web] No se encontró etiqueta __NEXT_DATA__ (longitud HTML {len(resp.text)}).")
        else:
            snippet = resp.text[:100].replace("\n", " ") if resp.text else ""
            print(f"[scraper-web] Código {resp.status_code}: {snippet}")
    except Exception as e:
        print(f"[scraper-web] Error: {e}")

    return []


def search_term(term: str) -> list[dict]:
    """Busca anuncios para un término usando la API v3 o el fallback web de Wallapop."""
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

    # Paso 1: Obtener search_id y section_id desde /api/v3/search/components
    components_url = "https://api.wallapop.com/api/v3/search/components"
    search_id = None
    section_id = None

    try:
        r1 = session.get(components_url, headers=headers, params=params, timeout=10)
        if r1.status_code == 200:
            data1 = r1.json()

            # 1. Comprobar si components ya traía items directamente
            items = _collect_items_recursive(data1)
            if items:
                print(f"[scraper] {len(items)} anuncios obtenidos directamente en components.")
                return items

            # 2. Extraer search_id y buscar la sección que NO sea ads_banner
            search_id = _find_key_recursive(data1, "search_id")
            components_list = data1.get("components") or []
            types = [c.get("type") for c in components_list if isinstance(c, dict)]
            print(f"[scraper] Componentes disponibles: {types}")

            for c in components_list:
                if isinstance(c, dict) and c.get("type") not in ("ads_banner", "banner"):
                    section_id = c.get("id") or c.get("section_id")
                    if section_id:
                        print(f"[scraper] Sección válida seleccionada: {c.get('type')} (id={section_id})")
                        break

            print(f"[scraper] search_id={search_id}, section_id={section_id}")
        else:
            snippet = r1.text[:100].replace("\n", " ") if r1.text else ""
            print(f"[scraper] {components_url} -> {r1.status_code}: {snippet}")
    except Exception as e:
        print(f"[scraper] Error en components: {e}")

    # Paso 2: Obtener productos con search_id y section_id
    if search_id:
        section_url = "https://api.wallapop.com/api/v3/search/section"
        section_params = {"search_id": search_id}
        if section_id:
            section_params["section_id"] = section_id

        try:
            r2 = session.get(section_url, headers=headers, params=section_params, timeout=10)
            if r2.status_code == 200:
                data2 = r2.json()
                items = _collect_items_recursive(data2)
                if items:
                    print(f"[scraper] /search/section -> {len(items)} anuncios encontrados.")
                    return items
            else:
                snippet = r2.text[:100].replace("\n", " ") if r2.text else ""
                print(f"[scraper] /search/section -> Código {r2.status_code}: {snippet}")
        except Exception as e:
            print(f"[scraper] Error en section: {e}")

    # Paso 3: Fallback a extracción web HTML de Wallapop
    print(f"[scraper] Activando fallback web para '{term}'...")
    web_items = _search_web(term)
    return web_items







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




