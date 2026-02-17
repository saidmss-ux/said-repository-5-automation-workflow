# Manuel d'utilisation — `modules/youtube_scrap.py`

Ce manuel explique comment alimenter `data/source/master_sources.csv` depuis YouTube, avec deux modes:

- **Mode API** (YouTube Data API v3) — recommandé.
- **Mode Scraping HTML** — fallback pour tests rapides.

## 1) Prérequis

- Python 3.13
- Dépendances du projet (`requirements.txt`)
- (Optionnel) clé API YouTube Data API v3

## 2) Contrat CSV produit

Le fichier généré contient strictement ces colonnes:

- `source_url`
- `niche`
- `lang`
- `rights`
- `usage_strategy`
- `origin_platform`

`origin_platform` est toujours fixé à `YOUTUBE`.

## 3) Modes d'exécution

### 3.1 Mode automatique (recommandé)

```bash
python modules/youtube_scrap.py
```

Comportement:
1. Cherche `YOUTUBE_API_KEY` dans l'environnement.
2. Si clé présente: essaie le mode API.
3. Sinon: passe en scraping HTML.
4. Si résultats insuffisants: injecte des seeds de démo pour atteindre 10 lignes.

### 3.2 Mode API forcé

Dans un script Python:

```python
from pathlib import Path
from modules.youtube_scrap import run_scraper

run_scraper(
    queries=["productivity"],
    channels=[],
    playlists=[],
    mode="api",
    api_key="<YOUR_KEY>",
    output_csv=Path("data/source/master_sources.csv"),
)
```

### 3.3 Mode scraping forcé

```python
from pathlib import Path
from modules.youtube_scrap import run_scraper

run_scraper(
    queries=["business mindset"],
    channels=["https://www.youtube.com/@TED"],
    playlists=[],
    mode="scrape",
    output_csv=Path("data/source/master_sources.csv"),
)
```

## 4) Paramètres importants

- `queries`: liste de mots-clés YouTube.
- `channels`: liste d'URLs de chaînes ou channel IDs.
- `playlists`: liste d'URLs playlists.
- `max_results_per_source`: limite par source.
- `mode`: `auto`, `api`, ou `scrape`.

## 5) Logs et validation

Le module affiche:
- mode utilisé
- nombre de vidéos trouvées
- fallback utilisé
- chemin du CSV sauvegardé
- aperçu `head(5)`

## 6) Intégration avec le pipeline principal

Le CSV généré alimente directement:

```bash
python master_pipeline.py
```

Workflow global:
`youtube_scrap -> loader -> normalizer -> classifier -> prompt_builder -> generator`

## 7) Erreurs fréquentes

- **Pas de clé API en mode API**: définir `YOUTUBE_API_KEY` ou passer en `mode="scrape"`.
- **Quota API dépassé**: passer temporairement en scraping.
- **Résultats YouTube faibles/instables**: le module complète à 10 lignes en mode démo pour garder le pipeline testable.

## 8) Bonnes pratiques

- Utiliser l’API en priorité pour fiabilité.
- Garder `max_results_per_source` raisonnable.
- Vérifier le CSV avant exécution du pipeline prompt.
