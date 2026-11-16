import asyncio
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from src import config, scraper, db, notifier


def job():
    """Una ejecución del pipeline: obtener, filtrar, notificar y registrar."""
    print(f"\n--- [Bot] Iniciando ronda de búsqueda: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    try:
        items = scraper.fetch_items()
        print(f"[Bot] Anuncios obtenidos de Wallapop: {len(items)}")
        seen_ids = db.load_seen_ids()
        notified = 0

        for item in items:
            if item["id"] in seen_ids:
                continue

            # Filtro de precio
            if not (config.CONFIG["price_min"] <= item["price"] <= config.CONFIG["price_max"]):
                continue

            # Filtro de estado (si está configurado)
            if config.CONFIG["conditions"] and item.get("condition"):
                if item["condition"] not in config.CONFIG["conditions"]:
                    continue

            # Filtro de ubicación (si está configurado)
            if config.CONFIG["location"] and item.get("location"):
                if config.CONFIG["location"].lower() not in item["location"].lower():
                    continue

            print(f"[Bot] 🚨 ¡Nuevo anuncio encontrado! {item['title']} - {item['price']}€ ({item['url']})")
            notifier.send_telegram(item)
            db.save_seen_id(item["id"])
            notified += 1

        print(f"[Bot] Ronda terminada. {notified} nuevas alertas enviadas a Telegram.\n")
    except Exception as e:
        print(f"[Bot] Error en la ronda de búsqueda: {e}")


def main():
    scheduler = BlockingScheduler()
    # next_run_time=datetime.now() asegura que busque INMEDIATAMENTE al encender y luego cada X segundos
    scheduler.add_job(
        job,
        "interval",
        seconds=config.CONFIG["scrape_interval"],
        next_run_time=datetime.now(),
    )
    print(f"[Bot] Scheduler iniciado – buscando cada {config.CONFIG['scrape_interval']} segundos.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[Bot] detenido")


if __name__ == "__main__":
    main()

