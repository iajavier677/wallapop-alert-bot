# src/test_notify.py
from src import config, notifier

print("TOKEN :", config.CONFIG["telegram_token"])
print("CHAT_ID:", config.CONFIG["telegram_chat_id"])
print("Bot creado:", bool(notifier._telegram))

item = {
    "title": "⚡ PRUEBA DE NOTIFICACIÓN (script)",
    "price": 0,
    "condition": "Nuevo",
    "location": "Valencia",
    "url": "https://example.com",
}

print("Enviando notificación…")
notifier.send_telegram(item)
print("¡Hecho!")