import os
import asyncio
import requests
from src import config

def _telegram_bot():
    token = config.CONFIG.get("telegram_token")
    if token:
        try:
            from telegram import Bot
            return Bot(token=token)
        except Exception as e:
            print(f"[notifier] Error al cargar telegram Bot: {e}")
    return None

_telegram = _telegram_bot()

def _send_via_http(chat_id: str, text: str) -> None:
    """Fallback: send a message using the raw Telegram HTTP API.
    This can help when the python‑telegram‑bot async client fails silently.
    """
    token = config.CONFIG.get("telegram_token")
    if not token:
        print("[notifier] No Telegram token – cannot use HTTP API")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            print(f"[notifier] Telegram API error (HTTP fallback): {data}")
        else:
            print("[notifier] Message sent via HTTP API (fallback)")
    except Exception as e:
        print(f"[notifier] HTTP fallback failed: {e}")

def _send_async_message(chat_id, text):
    """Run the async send_message coroutine in a fresh event loop.
    If it raises an exception, fall back to the raw HTTP API.
    """
    async def _inner():
        result = await _telegram.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            disable_web_page_preview=False,
        )
        print("[notifier] Async send_message result:", result)
    try:
        asyncio.run(_inner())
    except Exception as exc:
        print(f"[notifier] Error al enviar mensaje Telegram (async): {exc}")
        _send_via_http(chat_id, text)

def send_telegram(item: dict):
    """Envía la alerta por Telegram usando el bot configurado.
    Si no hay token o ocurre un error, escribe la información en stdout.
    """
    if not _telegram:
        print("[notifier] Telegram no configurado – muestra en consola:")
        print(item)
        return
    msg = (
        f"*{item['title']}*\n"
        f"Precio: {item['price']} €\n"
        f"Estado: {item['condition']}\n"
        f"Ubicación: {item['location']}\n"
        f"[Ver anuncio]({item['url']})"
    )
    chat_id = config.CONFIG.get("telegram_chat_id")
    if not chat_id:
        print("[notifier] telegram_chat_id no configurado – muestra en consola:")
        print(item)
        return
    _send_async_message(chat_id, msg)
