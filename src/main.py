import asyncio
from apscheduler.schedulers.blocking import BlockingScheduler
from src import config, scraper, db, notifier


def job():
    """Una ejecución del pipeline: obtener, filtrar, notificar y registrar."""
    items = scraper.fetch_items()
    seen_ids = db.load_seen_ids()
    for item in items:
        if item["id"] in seen_ids:
            continue
        if not (
            config.CONFIG["price_min"] <= item["price"] <= config.CONFIG["price_max"]
            and item["condition"] in config.CONFIG["conditions"]
            and (not config.CONFIG["location"] or item["location"] == config.CONFIG["location"])
        ):
            continue
        # Notificar
        notifier.send_telegram(item)
        # Registrar como visto
        db.save_seen_id(item["id"])


def main():
    scheduler = BlockingScheduler()
    scheduler.add_job(job, "interval", seconds=config.CONFIG["scrape_interval"], next_run_time=None)
    print("[Bot] Scheduler started – polling cada", config.CONFIG["scrape_interval"], "segundos")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[Bot] detenido")

if __name__ == "__main__":
    main()
