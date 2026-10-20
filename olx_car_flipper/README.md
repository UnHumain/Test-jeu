# 🚗 OLX Car Flipper — Mureș

Surveille en continu olx.ro pour repérer les voitures d'occasion à **Târgu Mureș / Județul Mureș**
entre **500 € et 1400 €** (prix en RON convertis automatiquement), les fait évaluer par Claude
avec un prompt d'expert en achat-revente, mémorise tout en SQLite et vous alerte dès qu'une
annonce obtient **une note > 8/10 et une marge nette estimée ≥ 200 €**.

## Démarrage rapide

### 1. Installer les dépendances

Prérequis : Python 3.10 ou plus récent.

```bash
cd olx_car_flipper

# (optionnel mais recommandé) environnement virtuel
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate

pip install -r requirements.txt
```

Cela installe `requests`, `beautifulsoup4`, `anthropic` et `python-dotenv`.

### 2. Configurer le fichier `.env`

Créez votre `.env` à partir du modèle fourni :

```bash
cp .env.example .env               # Windows : copy .env.example .env
```

(Si vous oubliez cette étape, le premier `python main.py` le crée automatiquement.)

Ouvrez `.env` dans un éditeur et renseignez :

| Variable | Obligatoire | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Votre clé API Anthropic (https://console.anthropic.com → API Keys) |
| `TELEGRAM_BOT_TOKEN` | ❌ | Token du bot Telegram (voir « Notifications » plus bas) |
| `TELEGRAM_CHAT_ID` | ❌ | ID de la conversation qui recevra les alertes |
| `PRICE_MIN_EUR` / `PRICE_MAX_EUR` | ❌ | Fourchette de prix recherchée (500-1400 € par défaut) |
| `CHECK_INTERVAL_MINUTES` | ❌ | Fréquence de vérification (10 min par défaut) |
| `ALERT_MIN_SCORE` / `ALERT_MIN_MARGIN_EUR` | ❌ | Seuils d'alerte (note > 8 et marge ≥ 200 € par défaut) |

Exemple minimal :

```ini
ANTHROPIC_API_KEY=<votre_cle_anthropic>
TELEGRAM_BOT_TOKEN=<token_donne_par_BotFather>
TELEGRAM_CHAT_ID=<votre_chat_id>
```

🔒 Le fichier `.env` est ignoré par git (`.gitignore`) : vos clés restent sur votre machine
et ne seront jamais poussées sur GitHub. Seul `.env.example` (sans clés) est versionné.

### 3. Lancer le bot

```bash
python main.py
```

Le bot tourne en continu : il interroge OLX toutes les 10 minutes, analyse les nouvelles
annonces et vous alerte en cas d'opportunité. Arrêtez-le avec `Ctrl + C` ; la mémoire SQLite
est conservée, il reprendra là où il s'était arrêté au prochain lancement.

## Autres commandes

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
