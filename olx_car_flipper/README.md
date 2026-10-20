# 🚗 OLX Car Flipper — Mureș

Surveille en continu olx.ro pour repérer les voitures d'occasion à **Târgu Mureș / Județul Mureș**
entre **500 € et 1400 €** (prix en RON convertis automatiquement), les fait évaluer par Claude
avec un prompt d'expert en achat-revente, mémorise tout en SQLite et vous alerte dès qu'une
annonce obtient **une note > 8/10 et une marge nette estimée ≥ 200 €**.

## Installation

```bash
cd olx_car_flipper
python3 -m venv .venv && source .venv/bin/activate   # optionnel mais recommandé
pip install -r requirements.txt
python main.py --top          # 1er lancement : crée .env à partir de .env.example
```

Ouvrez ensuite `.env` et renseignez au minimum `ANTHROPIC_API_KEY`.
Le fichier `.env` est ignoré par git : vos clés ne seront jamais commitées.

## Utilisation

| Commande | Effet |
|---|---|
| `python main.py` | Boucle infinie, un cycle toutes les `CHECK_INTERVAL_MINUTES` (10 par défaut) |
| `python main.py --once` | Un seul cycle (pratique avec cron / le planificateur Windows) |
| `python main.py --top` | Les 10 meilleures annonces déjà analysées |
| `python main.py --test-telegram` | Vérifie la configuration Telegram |

## Notifications

- **Console** : gros bandeau vert `🚨 OPPORTUNITÉ DÉTECTÉE 🚨` avec toute l'analyse.
- **Fichier** : `logs/opportunites.log` (uniquement les opportunités) et `logs/olx_car_flipper.log` (journal complet).
- **Telegram** (optionnel) :
  1. Sur Telegram, parlez à `@BotFather` → `/newbot` → copiez le token dans `TELEGRAM_BOT_TOKEN`.
  2. Envoyez un message à votre bot, puis ouvrez `https://api.telegram.org/bot<TOKEN>/getUpdates`
     et copiez `chat.id` dans `TELEGRAM_CHAT_ID`.
  3. `python main.py --test-telegram`.

## Fonctionnement

```
scraper.py   → API JSON OLX (/api/v1/offers), repli automatique sur le HTML
storage.py   → SQLite data/olx_memory.sqlite3 : ID d'annonce + empreinte (titre/année/km/prix)
               pour ne jamais ré-analyser la même voiture, même republiée sous un autre ID
analyzer.py  → Claude (sortie JSON structurée : note, achat cible, revente, frais, marge, risques…)
               Les 4 premières photos sont envoyées au modèle pour juger l'état visible.
prompts.py   → instructions système de l'expert : remplacez-les par les vôtres si besoin
notifier.py  → console + logs + Telegram
main.py      → boucle d'exécution
```

## Réglages utiles (`.env`)

- `CLAUDE_MODEL` / `CLAUDE_EFFORT` : modèle et profondeur de réflexion (`low` = moins cher, `high` = plus fin).
- `MAX_ANALYSES_PER_CYCLE` : plafonne le coût du premier lancement (le stock existant est traité progressivement).
- `EUR_RON_RATE` : taux utilisé pour convertir les prix en lei.
- `OLX_CATEGORY_ID` / `OLX_REGION_ID` : à forcer si la résolution automatique des IDs OLX échoue.

> ⚠️ Les estimations de marge sont produites par une IA à partir de l'annonce : vérifiez toujours
> la voiture (papiers, rouille, moteur, boîte) avant d'acheter.
