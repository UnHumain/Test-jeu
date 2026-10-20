"""Alertes : console très visible + fichier de log dédié + Telegram (optionnel)."""

from __future__ import annotations

import html
import logging

import requests

from analyzer import Analysis
from config import Settings
from scraper import Listing

log = logging.getLogger(__name__)

GREEN = "\033[1;92m"
YELLOW = "\033[1;93m"
RESET = "\033[0m"


class Notifier:
    def __init__(self, settings: Settings):
        self.s = settings
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        self.opportunities_file = settings.log_dir / "opportunites.log"

    def is_opportunity(self, analysis: Analysis) -> bool:
        return (
            analysis.passes_red_flags
            and analysis.score > self.s.alert_min_score
            and analysis.net_margin_eur >= self.s.alert_min_margin_eur
        )

    def notify(self, listing: Listing, analysis: Analysis) -> None:
        text = self._format_plain(listing, analysis)
        banner = "=" * 70
        print(f"\n{GREEN}{banner}\n🚨  OPPORTUNITÉ DÉTECTÉE  🚨\n{banner}{RESET}\n{text}\n{GREEN}{banner}{RESET}\n", flush=True)

        with self.opportunities_file.open("a", encoding="utf-8") as fh:
            fh.write(f"{banner}\n{text}\n")

        if self.s.telegram_enabled:
            self._send_telegram(self._format_html(listing, analysis))

    def _send_telegram(self, message: str) -> None:
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.s.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": self.s.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
                timeout=15,
            )
            if not resp.ok:
                log.error("Telegram a répondu %s : %s", resp.status_code, resp.text[:300])
        except requests.RequestException as exc:
            log.error("Envoi Telegram impossible : %s", exc)

    def send_test(self) -> None:
        if not self.s.telegram_enabled:
            print(f"{YELLOW}Telegram non configuré (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID vides).{RESET}")
            return
        self._send_telegram("✅ OLX Car Flipper : notifications Telegram opérationnelles.")
        print("Message de test envoyé sur Telegram.")

    # ----------------------------------------------------------------- format
    @staticmethod
    def _format_plain(listing: Listing, a: Analysis) -> str:
        d = a.data
        alerts = "\n".join(f"   ⚠ {x}" for x in d.get("signaux_alerte", [])) or "   (aucun)"
        strengths = "\n".join(f"   ✓ {x}" for x in d.get("points_forts", [])) or "   (aucun)"
        questions = "\n".join(f"   ? {x}" for x in d.get("questions_au_vendeur", [])) or "   (aucune)"
        arguments = "\n".join(f"   → {x}" for x in d.get("arguments_negociation", [])) or "   (aucun)"
        return (
            f"🚗 {listing.title}\n"
            f"   {d.get('vehicule', '')}\n"
            f"📍 {listing.location}\n"
            f"💶 Prix affiché : {listing.price_value} {listing.currency} (≈ {listing.price_eur or 0:.0f} €)\n"
            f"⭐ Note : {a.score:.1f}/10   |   Recommandation : {d.get('recommandation')}   |   Risque : {d.get('niveau_risque')}"
            f"   |   Lignes rouges OK : {d.get('conforme_lignes_rouges')}\n"
            f"🎯 Achat cible : {d.get('prix_achat_cible_eur')} €   →   Revente : {d.get('prix_revente_estime_eur')} €"
            f"   (frais : {d.get('frais_estimes_eur')} €)\n"
            f"💰 MARGE NETTE ESTIMÉE : {a.net_margin_eur:.0f} €\n"
            f"📝 {d.get('resume', '')}\n"
            f"Points forts :\n{strengths}\n"
            f"Signaux d'alerte :\n{alerts}\n"
            f"Arguments de négociation :\n{arguments}\n"
            f"Questions au vendeur :\n{questions}\n"
            f"🔗 {listing.url}"
        )

    @staticmethod
    def _format_html(listing: Listing, a: Analysis) -> str:
        d = a.data
        e = html.escape
        alerts = "\n".join(f"⚠️ {e(x)}" for x in d.get("signaux_alerte", [])[:5])
        arguments = "\n".join(f"🤝 {e(x)}" for x in d.get("arguments_negociation", [])[:4])
        questions = "\n".join(f"❓ {e(x)}" for x in d.get("questions_au_vendeur", [])[:4])
        return (
            f"🚨 <b>OPPORTUNITÉ OLX</b> 🚨\n\n"
            f"🚗 <b>{e(listing.title)}</b>\n"
            f"{e(d.get('vehicule', ''))}\n"
            f"📍 {e(listing.location)}\n"
            f"💶 Prix : <b>{listing.price_value} {e(listing.currency)}</b> (≈ {listing.price_eur or 0:.0f} €)\n"
            f"⭐ Note : <b>{a.score:.1f}/10</b> — {e(str(d.get('recommandation')))}\n"
            f"🎯 Achat cible {d.get('prix_achat_cible_eur')} € → revente {d.get('prix_revente_estime_eur')} €\n"
            f"💰 <b>Marge nette : {a.net_margin_eur:.0f} €</b>\n\n"
            f"{e(d.get('resume', ''))}\n\n"
            f"{alerts}\n\n"
            f"{arguments}\n\n"
            f"{questions}\n\n"
            f'🔗 <a href="{e(listing.url)}">Voir l\'annonce</a>'
        )
