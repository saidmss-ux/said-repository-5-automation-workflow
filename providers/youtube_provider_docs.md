# YouTube Provider Manual (`providers/youtube_provider.py`)

## Objectif

Provider standalone pour collecter des vidéos YouTube via API v3, normaliser les résultats au format `master_source`, et exporter une télémétrie d'exécution (JSON + CSV).

## Schéma de sortie normalisé

Chaque item retourné:

```json
{
  "platform": "youtube",
  "id": "<videoId>",
  "title": "<title>",
  "channel": "<channelTitle>",
  "views": 12345,
  "published_at": "<ISO8601>",
  "source_extra": {"query": "...", "query_priority": "HIGH"}
}
```

## Préparer `queries.csv`

Fichier recommandé: `queries/youtube_queries.csv`

Colonnes obligatoires:
- `query`
- `priority`
- `max_results`
- `min_views`

Exemple:

```csv
query,priority,max_results,min_views
python automation,HIGH,15,1000
youtube shorts growth,MEDIUM,10,500
```

## Configuration API key

Définir la clé avant exécution:

```bash
export YOUTUBE_API_KEY="<your_api_key>"
```

Paramètres configurables (via `config/youtube_config.py` + env):
- `YOUTUBE_MAX_RESULTS_PER_QUERY`
- `YOUTUBE_MAX_PAGES`
- `YOUTUBE_SEARCH_PART`
- `YOUTUBE_VIDEOS_PART`
- `YOUTUBE_CACHE_TTL_SECONDS`

## Quotas & stratégie d'économie

- `search.list` est coûteux (souvent ~100 unités / appel).
- `videos.list` est peu coûteux (souvent ~1 unité / item).

Optimisations intégrées:
1. collecte d'IDs via `search.list` uniquement,
2. enrichissement en batch `videos.list` (chunks de 50 IDs max),
3. déduplication globale des IDs,
4. cache mémoire TTL,
5. pagination bornée (`max_pages`, `max_results`).

## Télémétrie

Après chaque exécution, export automatique:
- `telemetry/youtube_run_<timestamp>.json`
- `telemetry/youtube_run_<timestamp>.csv`

Le JSON contient:
- nombre de requêtes,
- appels API (`search`, `videos`),
- estimation quota,
- cache hits,
- erreurs HTTP,
- détails par requête (`ids`, `valid_items`, `min_views_filtered_items`).

Le CSV contient un résumé clé/valeur.

## Exécution standalone

```bash
python providers/youtube_provider.py
```

Comportement:
1. lit `queries/youtube_queries.csv` si présent,
2. exécute `fetch_youtube_data(...)`,
3. exporte la télémétrie,
4. affiche les 5 premiers résultats en console.

## Intégration dans un pipeline master_source

```python
from providers.youtube_provider import load_queries, fetch_youtube_data

queries = load_queries("queries/youtube_queries.csv")
items = fetch_youtube_data(queries)
# items est une list[dict] normalisée prête à être fusionnée dans master_source.
```

## Erreurs courantes

- `YouTubeQuotaExceededError`: quota API dépassé.
- `RuntimeError` (HTTP): erreur API après retries/backoff.
- `FileNotFoundError` / `ValueError`: CSV de requêtes absent ou invalide.

## Hooks d'extension

`fetch_youtube_data(...)` accepte:
- `quality_filter`: filtrage qualité custom,
- `scoring_hook`: scoring custom,
- `telemetry_path`: chemin de sortie de la télémétrie.
