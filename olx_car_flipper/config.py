"""Chargement centralisé de la configuration depuis le fichier .env."""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE = BASE_DIR / ".env.example"


def _ensure_env_file() -> None:
    """Crée .env à partir de .env.example au premier lancement."""
    if not ENV_FILE.exists() and ENV_EXAMPLE.exists():
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        print(f"[config] Fichier {ENV_FILE} créé : renseignez ANTHROPIC_API_KEY puis relancez.")


def _int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    return int(value) if value else default


def _float(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    return float(value) if value else default


def _str(name: str, default: str = "") -> str:
    return os.getenv(name, "").strip() or default


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    claude_model: str
    claude_effort: str

    telegram_bot_token: str
    telegram_chat_id: str

    price_min_eur: float
    price_max_eur: float
    eur_ron_rate: float
    olx_category_path: str
    olx_region_slug: str
    olx_category_id: str
    olx_region_id: str
    max_pages: int

    check_interval_minutes: int
    max_analyses_per_cycle: int
    alert_min_score: float
    alert_min_margin_eur: float

    db_path: Path
    log_dir: Path

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


def load_settings() -> Settings:
    _ensure_env_file()
    load_dotenv(ENV_FILE)

    db_path = Path(_str("DB_PATH", "data/olx_memory.sqlite3"))
    log_dir = Path(_str("LOG_DIR", "logs"))

    return Settings(
        anthropic_api_key=_str("ANTHROPIC_API_KEY"),
        claude_model=_str("CLAUDE_MODEL", "claude-opus-5-5"),
        claude_effort=_str("CLAUDE_EFFORT", "medium"),
        telegram_bot_token=_str("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_str("TELEGRAM_CHAT_ID"),
        price_min_eur=_float("PRICE_MIN_EUR", 500),
        price_max_eur=_float("PRICE_MAX_EUR", 1400),
        eur_ron_rate=_float("EUR_RON_RATE", 5.0),
        olx_category_path=_str("OLX_CATEGORY_PATH", "auto-masini-moto-ambarcatiuni/autoturisme"),
        olx_region_slug=_str("OLX_REGION_SLUG", "mures"),
        olx_category_id=_str("OLX_CATEGORY_ID"),
        olx_region_id=_str("OLX_REGION_ID"),
        max_pages=_int("MAX_PAGES", 3),
        check_interval_minutes=_int("CHECK_INTERVAL_MINUTES", 10),
        max_analyses_per_cycle=_int("MAX_ANALYSES_PER_CYCLE", 25),
        alert_min_score=_float("ALERT_MIN_SCORE", 8),
        alert_min_margin_eur=_float("ALERT_MIN_MARGIN_EUR", 200),
        db_path=db_path if db_path.is_absolute() else BASE_DIR / db_path,
        log_dir=log_dir if log_dir.is_absolute() else BASE_DIR / log_dir,
    )
