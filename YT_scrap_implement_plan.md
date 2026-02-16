Architecture recommandée v1
youtube_pipeline/
│
├── config.py              # Paramètres API + filtres qualité
├── queries.txt            # Liste des requêtes (modifiable sans toucher au code)
├── youtube_client.py      # Gestion API optimisée quota
├── data_filter.py         # Scoring & nettoyage data
├── exporter.py            # Export CSV unique
├── main.py                # Orchestrateur pipeline
└── output/
    └── master_youtube.csv


🎯 Objectif :

Séparer requêtes

Séparer logique API

Séparer logique qualité

Séparer export

🔑 2️⃣ config.py (optimisation quota + qualité)
API_KEY = "YOUR_API_KEY"

MAX_RESULTS_PER_QUERY = 10  # Limite stricte pour réduire quota
REGION_CODE = "DZ"          # Optimisation géographique
RELEVANCE_LANGUAGE = "fr"

MIN_VIEWS = 1000
MIN_DURATION_SECONDS = 60
MAX_DURATION_SECONDS = 1800

OUTPUT_FILE = "output/master_youtube.csv"


Pourquoi ?

🎯 limiter maxResults

🎯 limiter région

🎯 éviter les shorts (si inutile)

🎯 éviter spam / low quality

🔍 3️⃣ youtube_client.py (ULTRA IMPORTANT pour quota)

Le endpoint search.list coûte 100 unités par requête ⚠️
Le endpoint videos.list coûte 1 unité.

Donc stratégie intelligente :

🔎 search → récupérer IDs seulement

🎥 videos.list → récupérer toutes stats en batch

from googleapiclient.discovery import build
import config

youtube = build("youtube", "v3", developerKey=config.API_KEY)

def search_videos(query):
    request = youtube.search().list(
        part="id",
        q=query,
        type="video",
        maxResults=config.MAX_RESULTS_PER_QUERY,
        regionCode=config.REGION_CODE,
        relevanceLanguage=config.RELEVANCE_LANGUAGE
    )
    response = request.execute()
    
    video_ids = [item["id"]["videoId"] for item in response["items"]]
    return video_ids


def get_video_details(video_ids):
    request = youtube.videos().list(
        part="snippet,statistics,contentDetails",
        id=",".join(video_ids)
    )
    return request.execute()


👉 On batch les IDs → énorme économie de quota 💰

🧮 4️⃣ data_filter.py (contrôle qualité + scoring)
import isodate
import config

def filter_videos(response):
    valid_videos = []

    for item in response["items"]:
        stats = item["statistics"]
        snippet = item["snippet"]
        duration = isodate.parse_duration(item["contentDetails"]["duration"]).total_seconds()

        views = int(stats.get("viewCount", 0))

        if views < config.MIN_VIEWS:
            continue

        if duration < config.MIN_DURATION_SECONDS or duration > config.MAX_DURATION_SECONDS:
            continue

        score = compute_score(views)

        valid_videos.append({
            "title": snippet["title"],
            "channel": snippet["channelTitle"],
            "views": views,
            "duration_sec": duration,
            "score": score,
            "video_id": item["id"]
        })

    return valid_videos


def compute_score(views):
    return round((views / 1000), 2)


🎯 Ici tu peux implémenter ton scoring crédible plus tard.

📤 5️⃣ exporter.py (UN SEUL CSV GLOBAL)
import csv
import config
import os

def export_to_csv(data):
    os.makedirs("output", exist_ok=True)

    with open(config.OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

🚀 6️⃣ main.py (orchestrateur clean)
import config
from youtube_client import search_videos, get_video_details
from data_filter import filter_videos
from exporter import export_to_csv

def load_queries():
    with open("queries.txt", "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def main():
    all_results = []
    queries = load_queries()

    for query in queries:
        video_ids = search_videos(query)
        if not video_ids:
            continue

        response = get_video_details(video_ids)
        filtered = filter_videos(response)
        all_results.extend(filtered)

    if all_results:
        export_to_csv(all_results)
        print("Pipeline terminé ✅")
    else:
        print("Aucune donnée valide trouvée.")

if __name__ == "__main__":
    main()

🧠 Optimisation avancée quota (très important)
🔥 1. Regrouper les requêtes similaires

Ne pas faire :

AI automation
automation AI
AI tools


Mais normaliser dans queries.txt.

🔥 2. Déduplication globale

Ajouter :

seen_ids = set()


Et éviter d’exporter 2 fois la même vidéo.

🔥 3. Planifier intelligemment

1 exécution par jour

Log du quota utilisé

Sauvegarde progressive

📊 Résultat final

✔ 1 seul CSV
✔ Modulaire
✔ Configurable
✔ Optimisé quota
✔ Facile à scaler
✔ Compatible futur scoring IA