# Wallapop Alert Bot

Este proyecto implementa un sistema de monitorización y notificación para anuncios nuevos en Wallapop (o plataformas similares) que cumplan criterios configurables por el usuario.

## Componentes principales
- **scraper**: obtiene los últimos anuncios mediante API o web‑scraping.
- **db**: registra los IDs de los anuncios ya vistos.
- **filters**: aplica los criterios de precio, estado y ubicación.
- **notifier**: envía la alerta por el canal configurado (Telegram, email, etc.).
- **scheduler**: ejecuta el proceso cada N minutos.

## Requisitos
- Python 3.9+
- Dependencias en `requirements.txt`
- Un token de bot (Telegram, SendGrid, Twilio, etc.) y las credenciales necesarias.

## Ejecutar
```bash
python -m src.main
```

El proyecto está pensado para ser ampliado (Docker, pruebas, métricas, …).
