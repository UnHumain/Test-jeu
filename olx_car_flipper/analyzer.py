"""Évaluation des annonces par Claude (API Anthropic) avec sortie JSON structurée."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import anthropic

from config import Settings
from prompts import SYSTEM_PROMPT
from scraper import Listing

log = logging.getLogger(__name__)

MAX_PHOTOS = 4

ANALYSIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "vehicule": {"type": "string", "description": "Marque, modèle, année, motorisation identifiés"},
        "note_sur_10": {"type": "number", "description": "Note d'opportunité de 0 à 10"},
        "conforme_lignes_rouges": {
            "type": "string",
            "enum": ["Oui", "Non"],
            "description": "Oui si l'annonce ne déclenche AUCUNE ligne rouge, Non sinon",
        },
        "prix_achat_cible_eur": {"type": "integer", "description": "Prix d'achat réaliste après négociation"},
        "prix_revente_estime_eur": {"type": "integer", "description": "Prix de revente réaliste en 2-4 semaines"},
        "frais_estimes_eur": {"type": "integer", "description": "Réparations + papiers + préparation"},
        "marge_nette_estimee_eur": {"type": "integer", "description": "Revente - achat cible - frais"},
        "niveau_risque": {"type": "string", "enum": ["faible", "moyen", "eleve"]},
        "recommandation": {"type": "string", "enum": ["ACHETER", "NEGOCIER", "SURVEILLER", "PASSER"]},
        "points_forts": {"type": "array", "items": {"type": "string"}},
        "signaux_alerte": {"type": "array", "items": {"type": "string"}},
        "arguments_negociation": {"type": "array", "items": {"type": "string"}},
        "questions_au_vendeur": {"type": "array", "items": {"type": "string"}},
        "resume": {"type": "string", "description": "Synthèse en 2-3 phrases"},
    },
    "required": [
        "vehicule", "note_sur_10", "conforme_lignes_rouges", "prix_achat_cible_eur",
        "prix_revente_estime_eur", "frais_estimes_eur", "marge_nette_estimee_eur", "niveau_risque",
        "recommandation", "points_forts", "signaux_alerte", "arguments_negociation",
        "questions_au_vendeur", "resume",
    ],
    "additionalProperties": False,
}


@dataclass
class Analysis:
    data: dict[str, Any]
    model: str

    @property
    def score(self) -> float:
        return float(self.data.get("note_sur_10", 0))

    @property
    def net_margin_eur(self) -> float:
        return float(self.data.get("marge_nette_estimee_eur", 0))

    @property
    def passes_red_flags(self) -> bool:
        return self.data.get("conforme_lignes_rouges") == "Oui"


class AnalysisError(Exception):
    """L'annonce n'a pas pu être analysée (sera retentée au cycle suivant)."""


class CarAnalyzer:
    def __init__(self, settings: Settings):
        if not settings.anthropic_api_key:
            raise SystemExit("ANTHROPIC_API_KEY manquante : renseignez-la dans olx_car_flipper/.env")
        self.s = settings
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key, max_retries=4)

    def analyze(self, listing: Listing) -> Analysis:
        try:
            return self._call(listing, with_photos=True)
        except anthropic.BadRequestError as exc:
            # Le plus souvent : une URL de photo OLX non téléchargeable. On réessaie sans images.
            if listing.photos:
                log.warning("Requête refusée avec photos (%s) - nouvel essai sans photos", exc.message)
                return self._call(listing, with_photos=False)
            raise AnalysisError(exc.message) from exc

    def _call(self, listing: Listing, with_photos: bool) -> Analysis:
        content: list[dict[str, Any]] = []
        if with_photos:
            content += [
                {"type": "image", "source": {"type": "url", "url": url}}
                for url in listing.photos[:MAX_PHOTOS]
                if url.startswith("http")
            ]
        content.append({
            "type": "text",
            "text": (
                "Évalue cette annonce OLX pour un achat-revente. "
                f"Mon budget d'achat est de {self.s.price_min_eur:.0f} à {self.s.price_max_eur:.0f} €.\n\n"
                f"{listing.to_prompt_text()}"
            ),
        })

        try:
            response = self.client.beta.messages.create(
                model=self.s.claude_model,
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": content}],
                output_config={
                    "effort": self.s.claude_effort,
                    "format": {"type": "json_schema", "schema": ANALYSIS_SCHEMA},
                },
            )
        except anthropic.BadRequestError:
            raise
        except anthropic.AuthenticationError as exc:
            raise SystemExit("Clé ANTHROPIC_API_KEY invalide.") from exc
        except anthropic.RateLimitError as exc:
            raise AnalysisError("limite de débit atteinte") from exc
        except anthropic.APIStatusError as exc:
            raise AnalysisError(f"erreur API {exc.status_code} : {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise AnalysisError("erreur réseau vers l'API Anthropic") from exc

        if response.stop_reason == "refusal":
            raise AnalysisError("le modèle a refusé d'analyser cette annonce")
        if response.stop_reason == "max_tokens":
            raise AnalysisError("réponse tronquée (max_tokens)")

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"JSON invalide : {text[:200]}") from exc
        return Analysis(data=data, model=response.model)
