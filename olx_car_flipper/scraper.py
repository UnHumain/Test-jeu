"""Scraping des annonces de voitures d'occasion sur olx.ro (Județul Mureș).

Stratégie :
  1. API JSON publique d'OLX (/api/v1/offers/) - rapide, données complètes.
  2. Repli sur le HTML des pages de résultats si l'API change ou bloque.
"""

from __future__ import annotations

import hashlib
import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any

import requests
from bs4 import BeautifulSoup

from config import Settings

log = logging.getLogger(__name__)

OLX_BASE = "https://www.olx.ro"
PAGE_SIZE = 40

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"
    ),
    "Accept-Language": "ro-RO,ro;q=0.9,fr;q=0.8,en;q=0.7",
}


@dataclass
class Listing:
    id: str
    url: str
    title: str
    price_value: float | None
    currency: str
    price_eur: float | None
    location: str = ""
    description: str = ""
    params: dict[str, str] = field(default_factory=dict)
    photos: list[str] = field(default_factory=list)
    created_time: str = ""
    negotiable: bool = False

    @property
    def fingerprint(self) -> str:
        """Empreinte « même voiture » pour repérer les reposts sous un nouvel ID."""
        title = re.sub(r"[^a-z0-9]", "", self.title.lower())
        year = self.params.get("Anul fabricatiei", self.params.get("year", ""))
        km = re.sub(r"\D", "", self.params.get("Rulaj", self.params.get("mileage", "")))
        price = round((self.price_eur or 0) / 50) * 50
        raw = f"{title}|{year}|{km}|{price}"
        return hashlib.sha1(raw.encode()).hexdigest()

    def to_prompt_text(self) -> str:
        params = "\n".join(f"- {k} : {v}" for k, v in self.params.items()) or "- (non renseignées)"
        price = f"{self.price_value:,.0f} {self.currency}".replace(",", " ") if self.price_value else "inconnu"
        eur = f"≈ {self.price_eur:,.0f} €".replace(",", " ") if self.price_eur else ""
        return (
            f"Titre : {self.title}\n"
            f"Prix affiché : {price} {eur}{' (négociable)' if self.negotiable else ''}\n"
            f"Localisation : {self.location}\n"
            f"Publiée le : {self.created_time}\n"
            f"Lien : {self.url}\n"
            f"Caractéristiques :\n{params}\n"
            f"Nombre de photos : {len(self.photos)}\n\n"
            f"Description du vendeur :\n{self.description.strip() or '(vide)'}"
        )


class OlxScraper:
    def __init__(self, settings: Settings):
        self.s = settings
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._category_id = settings.olx_category_id
        self._region_id = settings.olx_region_id

    # ------------------------------------------------------------------ utils
    def _get(self, url: str, **kwargs) -> requests.Response:
        time.sleep(random.uniform(1.0, 2.5))  # politesse envers le serveur
        resp = self.session.get(url, timeout=25, **kwargs)
        resp.raise_for_status()
        return resp

    def _to_eur(self, value: float | None, currency: str) -> float | None:
        if value is None:
            return None
        cur = currency.upper()
        if cur in ("EUR", "€"):
            return float(value)
        if cur in ("RON", "LEI"):
            return round(float(value) / self.s.eur_ron_rate, 2)
        return None

    def in_price_range(self, listing: Listing) -> bool:
        return listing.price_eur is not None and self.s.price_min_eur <= listing.price_eur <= self.s.price_max_eur

    # ------------------------------------------------------------- public API
    def fetch_listings(self) -> list[Listing]:
        """Retourne les annonces récentes, filtrées sur la fourchette de prix."""
        try:
            listings = self._fetch_via_api()
            log.info("API OLX : %d annonces récupérées", len(listings))
        except Exception as exc:  # noqa: BLE001 - on veut tomber sur le repli quoi qu'il arrive
            log.warning("API OLX indisponible (%s) - repli sur le HTML", exc)
            listings = self._fetch_via_html()
            log.info("HTML OLX : %d annonces récupérées", len(listings))

        unique = {l.id: l for l in listings}
        kept = [l for l in unique.values() if self.in_price_range(l)]
        log.info("%d annonces dans la fourchette %.0f-%.0f €", len(kept), self.s.price_min_eur, self.s.price_max_eur)
        return kept

    def enrich(self, listing: Listing) -> Listing:
        """Complète description / caractéristiques depuis la page de l'annonce si besoin."""
        if listing.description and listing.params:
            return listing
        try:
            soup = BeautifulSoup(self._get(listing.url).text, "html.parser")
        except requests.RequestException as exc:
            log.warning("Impossible de charger %s : %s", listing.url, exc)
            return listing

        desc = soup.select_one('[data-cy="ad_description"], [data-testid="ad_description"]')
        if desc and not listing.description:
            listing.description = desc.get_text("\n", strip=True)

        if not listing.params:
            container = soup.select_one('[data-testid="ad-parameters-container"], [data-testid="main"]')
            for p in (container.select("p") if container else []):
                text = p.get_text(" ", strip=True)
                if ":" in text:
                    key, value = text.split(":", 1)
                    listing.params[key.strip()] = value.strip()

        if not listing.photos:
            listing.photos = [img["src"] for img in soup.select('[data-testid="swiper-image"]') if img.get("src")]
        return listing

    # --------------------------------------------------------------- API JSON
    def _resolve_ids(self) -> None:
        if self._category_id and self._region_id:
            return
        url = (
            f"{OLX_BASE}/api/v1/friendly-links/query-params/"
            f"{self.s.olx_category_path}/{self.s.olx_region_slug}/"
        )
        data = self._get(url).json().get("data", {})
        self._category_id = self._category_id or str(data.get("category_id", ""))
        self._region_id = self._region_id or str(data.get("region_id", ""))
        if not (self._category_id and self._region_id):
            raise RuntimeError(f"IDs OLX introuvables : {data}")
        log.info("IDs OLX résolus : category_id=%s region_id=%s", self._category_id, self._region_id)

    def _fetch_via_api(self) -> list[Listing]:
        self._resolve_ids()
        results: list[Listing] = []
        for page in range(self.s.max_pages):
            params = {
                "offset": page * PAGE_SIZE,
                "limit": PAGE_SIZE,
                "category_id": self._category_id,
                "region_id": self._region_id,
                "sort_by": "created_at:desc",
                "currency": "EUR",
                "filter_float_price:from": int(self.s.price_min_eur),
                "filter_float_price:to": int(self.s.price_max_eur),
            }
            payload = self._get(f"{OLX_BASE}/api/v1/offers/", params=params).json()
            offers = payload.get("data", [])
            results.extend(self._parse_api_offer(o) for o in offers)
            if len(offers) < PAGE_SIZE or not payload.get("links", {}).get("next"):
                break
        return results

    def _parse_api_offer(self, o: dict[str, Any]) -> Listing:
        price_value, currency, negotiable = None, "", False
        params: dict[str, str] = {}
        for p in o.get("params", []):
            value = p.get("value") or {}
            if p.get("key") == "price" or p.get("type") == "price":
                price_value = value.get("value")
                currency = value.get("currency", "")
                negotiable = bool(value.get("negotiable"))
            else:
                params[p.get("name") or p.get("key", "?")] = str(value.get("label") or value.get("key") or "")

        loc = o.get("location") or {}
        location = ", ".join(
            x for x in ((loc.get("city") or {}).get("name"), (loc.get("region") or {}).get("name")) if x
        )
        description = BeautifulSoup(o.get("description") or "", "html.parser").get_text("\n", strip=True)
        photos = [
            (ph.get("link") or "").replace("{width}", "800").replace("{height}", "600")
            for ph in o.get("photos", [])
        ]

        return Listing(
            id=str(o.get("id")),
            url=o.get("url", ""),
            title=o.get("title", "").strip(),
            price_value=price_value,
            currency=currency,
            price_eur=self._to_eur(price_value, currency),
            location=location,
            description=description,
            params=params,
            photos=photos,
            created_time=o.get("created_time", ""),
            negotiable=negotiable,
        )

    # ------------------------------------------------------------ HTML repli
    def _fetch_via_html(self) -> list[Listing]:
        results: list[Listing] = []
        base_url = f"{OLX_BASE}/{self.s.olx_category_path}/{self.s.olx_region_slug}/"
        for page in range(1, self.s.max_pages + 1):
            params = {
                "currency": "EUR",
                "search[order]": "created_at:desc",
                "search[filter_float_price:from]": int(self.s.price_min_eur),
                "search[filter_float_price:to]": int(self.s.price_max_eur),
                "page": page,
            }
            try:
                soup = BeautifulSoup(self._get(base_url, params=params).text, "html.parser")
            except requests.RequestException as exc:
                log.error("Échec de la page %d : %s", page, exc)
                break
            cards = soup.select('[data-cy="l-card"]')
            for card in cards:
                listing = self._parse_html_card(card)
                if listing:
                    results.append(listing)
            if len(cards) < PAGE_SIZE:
                break
        return results

    def _parse_html_card(self, card) -> Listing | None:
        link = card.select_one("a[href]")
        if not link:
            return None
        href = link["href"]
        url = href if href.startswith("http") else OLX_BASE + href
        listing_id = card.get("id") or re.sub(r"\W", "", url.rsplit("-", 1)[-1])

        title_el = card.select_one('[data-cy="ad-card-title"] h4, [data-cy="ad-card-title"] h6, h4, h6')
        price_el = card.select_one('[data-testid="ad-price"]')
        loc_el = card.select_one('[data-testid="location-date"]')

        price_text = price_el.get_text(" ", strip=True) if price_el else ""
        price_value, currency = _parse_price_text(price_text)
        location_date = loc_el.get_text(" ", strip=True) if loc_el else ""

        return Listing(
            id=str(listing_id),
            url=url.split("#")[0],
            title=title_el.get_text(strip=True) if title_el else "",
            price_value=price_value,
            currency=currency,
            price_eur=self._to_eur(price_value, currency),
            location=location_date.split(" - ")[0],
            created_time=location_date.split(" - ")[-1] if " - " in location_date else "",
            negotiable="negociabil" in price_text.lower(),
        )


def _parse_price_text(text: str) -> tuple[float | None, str]:
    """'1 200 €' -> (1200, 'EUR') ; '5.500 lei Negociabil' -> (5500, 'RON')."""
    lower = text.lower()
    currency = "EUR" if ("€" in text or "eur" in lower) else "RON" if ("lei" in lower or "ron" in lower) else ""
    digits = re.sub(r"[^\d]", "", text.split("\n")[0])
    return (float(digits), currency) if digits else (None, currency)
