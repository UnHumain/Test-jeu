"""OLX Car Flipper - surveillance automatique des bonnes affaires auto à Mureș.

Usage :
    python main.py               # boucle infinie (toutes les CHECK_INTERVAL_MINUTES)
    python main.py --once        # un seul cycle puis sortie
    python main.py --top         # affiche les 10 meilleures annonces en mémoire
    python main.py --test-telegram
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

from analyzer import AnalysisError, CarAnalyzer
from config import Settings, load_settings
from notifier import Notifier
from scraper import OlxScraper
from storage import Memory

log = logging.getLogger("olx_car_flipper")


def setup_logging(settings: Settings) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler = RotatingFileHandler(
        settings.log_dir / "olx_car_flipper.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console])
    for noisy in ("httpx", "httpcore", "urllib3", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def run_cycle(scraper: OlxScraper, analyzer: CarAnalyzer, memory: Memory, notifier: Notifier, settings: Settings) -> None:
    log.info("—— Nouveau cycle de recherche ——")
    listings = scraper.fetch_listings()
    new = [l for l in listings if not memory.is_known(l)]
    log.info("%d nouvelle(s) annonce(s) à analyser", len(new))

    if len(new) > settings.max_analyses_per_cycle:
        log.info("Plafond de %d analyses/cycle : le reste sera traité aux cycles suivants",
                 settings.max_analyses_per_cycle)
        new = new[: settings.max_analyses_per_cycle]

    for listing in new:
        scraper.enrich(listing)
        try:
            analysis = analyzer.analyze(listing)
        except AnalysisError as exc:
            log.warning("Analyse impossible pour %s (%s) - retentée au prochain cycle", listing.url, exc)
            continue

        is_deal = notifier.is_opportunity(analysis)
        log.info("[%4.1f/10 | marge %5.0f € | %-10s] %s",
                 analysis.score, analysis.net_margin_eur, analysis.data.get("recommandation"), listing.title)
        if is_deal:
            notifier.notify(listing, analysis)
        memory.save(listing, analysis, notified=is_deal)

    stats = memory.stats()
    log.info("Mémoire : %d annonces analysées au total, %d opportunités signalées", stats["total"], stats["alerts"])


def print_top(memory: Memory) -> None:
    rows = memory.top()
    if not rows:
        print("Aucune annonce analysée pour l'instant.")
    for r in rows:
        print(f"{r['score']:4.1f}/10 | {r['net_margin_eur']:6.0f} € | {r['price_eur'] or 0:6.0f} € | {r['title']}\n      {r['url']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Détecteur d'opportunités auto sur OLX (Mureș)")
    parser.add_argument("--once", action="store_true", help="exécuter un seul cycle")
    parser.add_argument("--top", action="store_true", help="afficher les meilleures annonces en mémoire")
    parser.add_argument("--test-telegram", action="store_true", help="envoyer un message Telegram de test")
    args = parser.parse_args()

    settings = load_settings()
    setup_logging(settings)
    notifier = Notifier(settings)
    memory = Memory(settings.db_path)

    if args.test_telegram:
        notifier.send_test()
        return
    if args.top:
        print_top(memory)
        return

    scraper = OlxScraper(settings)
    analyzer = CarAnalyzer(settings)
    log.info("Démarrage : %s, %.0f-%.0f €, alerte si note > %.0f et marge ≥ %.0f €, Telegram %s",
             settings.olx_region_slug, settings.price_min_eur, settings.price_max_eur,
             settings.alert_min_score, settings.alert_min_margin_eur,
             "activé" if settings.telegram_enabled else "désactivé")

    try:
        while True:
            try:
                run_cycle(scraper, analyzer, memory, notifier, settings)
            except Exception:  # noqa: BLE001 - la boucle ne doit jamais mourir sur une erreur ponctuelle
                log.exception("Erreur pendant le cycle - nouvel essai au prochain passage")
            if args.once:
                break
            # léger décalage aléatoire pour ne pas interroger OLX à heure fixe
            delay = settings.check_interval_minutes * 60 + random.randint(-30, 30)
            next_run = datetime.fromtimestamp(time.time() + delay).strftime("%H:%M:%S")
            log.info("Prochain passage à %s", next_run)
            time.sleep(delay)
    except KeyboardInterrupt:
        log.info("Arrêt demandé par l'utilisateur.")
    finally:
        memory.close()


if __name__ == "__main__":
    main()
