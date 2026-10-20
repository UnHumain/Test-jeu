"""Mémoire persistante (SQLite) des annonces déjà analysées."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from analyzer import Analysis
from scraper import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id              TEXT PRIMARY KEY,
    fingerprint     TEXT NOT NULL,
    url             TEXT NOT NULL,
    title           TEXT,
    price_eur       REAL,
    location        TEXT,
    analyzed_at     TEXT NOT NULL,
    score           REAL,
    net_margin_eur  REAL,
    recommendation  TEXT,
    analysis_json   TEXT,
    notified        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_listings_fingerprint ON listings(fingerprint);
"""


class Memory:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def is_known(self, listing: Listing) -> bool:
        """Vrai si l'annonce (même ID) ou la même voiture republiée (même empreinte) a déjà été traitée."""
        row = self.conn.execute(
            "SELECT 1 FROM listings WHERE id = ? OR fingerprint = ? LIMIT 1",
            (listing.id, listing.fingerprint),
        ).fetchone()
        return row is not None

    def save(self, listing: Listing, analysis: Analysis, notified: bool) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO listings
               (id, fingerprint, url, title, price_eur, location, analyzed_at,
                score, net_margin_eur, recommendation, analysis_json, notified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                listing.id, listing.fingerprint, listing.url, listing.title, listing.price_eur,
                listing.location, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                analysis.score, analysis.net_margin_eur, analysis.data.get("recommandation"),
                json.dumps(analysis.data, ensure_ascii=False), int(notified),
            ),
        )
        self.conn.commit()

    def stats(self) -> dict[str, int]:
        total = self.conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        alerts = self.conn.execute("SELECT COUNT(*) FROM listings WHERE notified = 1").fetchone()[0]
        return {"total": total, "alerts": alerts}

    def top(self, limit: int = 10) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM listings ORDER BY score DESC, net_margin_eur DESC LIMIT ?", (limit,)
        ).fetchall()

    def close(self) -> None:
        self.conn.close()
