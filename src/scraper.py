import os
import time
import json
from urllib.parse import urlencode
import requests
from bs4 import BeautifulSoup
from src import config


def _build_search_url(page: int = 1) -> str:
    """Construye la URL de búsqueda con los filtros básicos.
    Wallapop acepta parámetros como `price_min`, `price_max`, `location`.
    Se añaden `page` para paginación.
    """
    base = config.CONFIG["search_url"]
    params = {
        "price_min": config.CONFIG["price_min"],
        "price_max": config.CONFIG["price_max"],
    }
    if config.CONFIG["location"]:
        params["location"] = config.CONFIG["location"]
        # Si se especifica un radio (km) lo añadimos al parámetro `distance`
        if config.CONFIG.get("radius_km") and config.CONFIG["radius_km"] > 0:
            params["distance"] = config.CONFIG["radius_km"]
    # Añadimos términos de búsqueda (keywords) si existen
    if config.CONFIG.get("search_terms"):
        # Wallapop usa el parámetro `search` para palabras clave
        params["search"] = " ".join(config.CONFIG["search_terms"])
    params["page"] = page
    return f"{base}?{urlencode(params)}"




def _parse_item(card) -> dict:
    """Extrae datos de un anuncio a partir de un nodo HTML de la tarjeta.
    La estructura HTML puede cambiar; ajustar selectores si es necesario.
    """
    # Ejemplo de selectores (pueden requerir ajuste).
    title_el = card.select_one("h3._3jM8j")
    price_el = card.select_one("span._1p7hJ")
    location_el = card.select_one("span._2kKxS")
    condition_el = card.select_one("span._1wJ5L")  # hipotético
    link_el = card.select_one("a._3P6c2")

    if not (title_el and price_el and link_el):
        return {}

    # Normalizar datos
    title = title_el.get_text(strip=True)
    price_text = price_el.get_text(strip=True).replace("€", "").replace(".", "").replace(",", "")
    try:
        price = int(price_text)
    except ValueError:
        price = 0
    location = location_el.get_text(strip=True) if location_el else ""
    condition = condition_el.get_text(strip=True) if condition_el else ""
    url = f"https://es.wallapop.com{link_el['href']}"
    # Wallapop incluye un identificador interno en el href, extraemos el último segmento.
    item_id = link_el['href'].split("-")[-1]

    return {
        "id": item_id,
        "title": title,
        "price": price,
        "condition": condition,
        "location": location,
        "url": url,
    }


def fetch_items(max_pages: int = 3) -> list[dict]:
    """Obtiene los últimos anuncios (hasta `max_pages`).
    Devuelve una lista de diccionarios con claves: id, title, price, condition, location, url.
    """
    items = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }
    for page in range(1, max_pages + 1):
        url = _build_search_url(page)
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"[scraper] Error al descargar {url}: {e}")
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("article._2oVvL")  # selector genérico, adaptar según la página
        if not cards:
            break
        for card in cards:
            item = _parse_item(card)
            if item:
                items.append(item)
        # Pequeña pausa entre páginas para no saturar
        time.sleep(1)
    return items
