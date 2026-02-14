Voici le fichier structuré **modelcode** regroupant les versions les plus complètes et à jour de chaque module du projet **automation_ia**, basées sur l'architecture validée dans la "Source of Truth".

### 1. Structure du Projet
```text
automation_ia/
├── data/
│   ├── source/           # master_sources.csv
│   └── generated/        # prompts_ready.csv et prompts_txt/
├── modules/
│   ├── __init__.py       # Fichier vide
│   ├── loader.py         # Chargement des sources
│   ├── normalizer.py     # Standardisation des colonnes
│   ├── classifier.py     # Niche, Langue, Droits
│   ├── prompt_builder.py # Assemblage des prompts
│   ├── exporter.py       # Sortie CSV et TXT
│   └── utils.py          # Fonctions utilitaires
├── prompts/
│   └── prompt_template.json # Cerveau éditorial
├── pipelines/
│   └── trend_loader.py   # Alimentation auto des trends
└── master_pipeline.py    # Point d'entrée unique
```

---

### 2. Code des Modules

#### modules/loader.py
Cette version utilise `pathlib` pour une gestion robuste des chemins.
```python
import pandas as pd
from pathlib import Path

SOURCE_DIR = Path("data/source")

def load_sources():
    all_rows = []
    # Cherche spécifiquement le fichier maître dans le dossier source
    for csv_file in SOURCE_DIR.glob("master_sources.csv"):
        df = pd.read_csv(csv_file)
        df["source_file"] = csv_file.name
        all_rows.append(df)
    
    if not all_rows:
        return pd.DataFrame()
    return pd.concat(all_rows, ignore_index=True)
```

#### modules/normalizer.py
Version robuste capable de gérer plusieurs noms de colonnes sources (`source_url`, `link`, `url`) pour créer la clé unique `content_url`.
```python
def normalize(df):
    df = df.copy()
    # Mapping des colonnes vers le format canonique
    if "source_url" in df.columns:
        df["content_url"] = df["source_url"]
    elif "link" in df.columns:
        df["content_url"] = df["link"]
    elif "url" in df.columns:
        df["content_url"] = df["url"]
    else:
        raise ValueError(f"Aucune colonne URL reconnue. Colonnes : {df.columns.tolist()}")
    
    # Préparation d'un texte brut minimal pour les prompts
    if "raw_text" not in df.columns:
        df["raw_text"] = "Source: " + df.get("origin_platform", "UNKNOWN").astype(str)
    
    return df
```

#### modules/classifier.py
Ce module attribue une niche et évalue les droits d'usage.
```python
def classify(df):
    df = df.copy()
    # Logique simplifiée mais extensible
    df["niche"] = df.get("niche", "MOTIVATION")
    df["lang"] = df.get("lang", "FR")
    df["rights"] = df.get("rights", "REWRITE_REQUIRED")
    df["usage_strategy"] = df.get("usage_strategy", "viral")
    
    # Ajout du Priority Score
    def score_row(row):
        score = 0
        if row["niche"] in ["MOTIVATION", "BUSINESS"]: score += 3
        if row["lang"] == "FR": score += 2
        return score

    df["priority_score"] = df.apply(score_row, axis=1)
    return df
```

#### modules/prompt_builder.py
Le module le plus complet utilisant les templates JSON.
```python
import json
from pathlib import Path

# Utilisation de chemins relatifs robustes
BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_FILE = BASE_DIR / "prompts" / "prompt_template.json"

def load_prompt_templates():
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable : {PROMPT_FILE}")
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def build_prompts(df):
    templates = load_prompt_templates()
    base = templates["base_prompt"]
    goals = templates["content_goals"]
    transforms = templates["transformation_levels"]
    prompts = []

    for _, row in df.iterrows():
        goal_key = str(row.get("usage_strategy", "viral")).lower()
        transform_key = str(row.get("rights", "rewrite")).lower()
        
        goal = goals.get(goal_key, goals["viral"])
        transform = transforms.get(transform_key, transforms["rewrite"])
        
        # Assemblage du prompt final
        prompt = f"""
ROLE: {base['role']}
RULES: {"; ".join(base['rules'])}
OBJECTIVE: {goal['objective']}
TONE: {goal['tone']}
SOURCE: {row.get("content_url")}
LANGUAGE: {row.get("lang", "FR")}
FORMAT: {base['format']}
""".strip()
        prompts.append(prompt)

    df["final_prompt"] = prompts
    return df
```

#### modules/exporter.py
Génère le CSV global et des fichiers texte individuels pour faciliter le copier-coller.
```python
from pathlib import Path

def export_prompts(df):
    output_dir = Path("data/generated")
    txt_dir = output_dir / "prompts_txt"
    output_dir.mkdir(parents=True, exist_ok=True)
    txt_dir.mkdir(parents=True, exist_ok=True)

    # Export CSV
    df.to_csv(output_dir / "prompts_ready.csv", index=False, encoding="utf-8")

    # Export TXT par prompt
    for i, row in df.iterrows():
        if row.get("final_prompt"):
            with open(txt_dir / f"prompt_{i+1:03}.txt", "w", encoding="utf-8") as f:
                f.write(row["final_prompt"])
```

#### modules/utils.py
Fonctions utilitaires pour la persistence des données.
```python
import csv

def save_csv(rows, path):
    if not rows: return
    with open(path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows.keys())
        writer.writeheader()
        writer.writerows(rows)
```

---

### 3. Fichiers de Configuration et Pipelines

#### prompts/prompt_template.json
Le cerveau éditorial du projet.
```json
{
  "base_prompt": {
    "role": "You are a professional short-form content creator.",
    "rules": ["No plagiarism", "High value rewrite", "Strong hook (3s)"],
    "format": "Short-form script (30 to 60 seconds)"
  },
  "content_goals": {
    "viral": { "objective": "Create viral content", "tone": "Energetic", "focus": ["Hook", "Share potential"] },
    "education": { "objective": "Teach a concept", "tone": "Clear", "focus": ["Clarity", "Practical value"] }
  },
  "transformation_levels": {
    "rewrite": "Full rewrite with original structure.",
    "storytelling": "Transform the idea into a narrative."
  }
}
```

#### pipelines/trend_loader.py
Permet d'alimenter le système avec des liens bruts sans API payante.
```python
import csv
from pathlib import Path
from datetime import datetime

INPUT_DIR = Path("data/trends_input")
MASTER_FILE = Path("data/source/master_sources.csv")

def run():
    new_rows = []
    # Lit tous les .txt dans trends_input
    for file in INPUT_DIR.glob("*.txt"):
        for line in file.read_text(encoding="utf-8").splitlines():
            url = line.strip()
            if url.startswith("http"):
                new_rows.append({
                    "source_url": url,
                    "niche": "MOTIVATION",
                    "processed": False,
                    "added_at": datetime.utcnow().isoformat()
                })
    
    if new_rows:
        # Sauvegarde vers master_sources.csv
        pd.DataFrame(new_rows).to_csv(MASTER_FILE, index=False, mode='a', header=not MASTER_FILE.exists())
```

---

### 4. Point d'Entrée Principal

#### master_pipeline.py
Le cerveau qui orchestre tout le flux.
```python
from modules.loader import load_sources
from modules.normalizer import normalize
from modules.classifier import classify
from modules.prompt_builder import build_prompts
from modules.exporter import export_prompts

print("🚀 MASTER PIPELINE STARTED")

# 1. Chargement
df = load_sources()
if df.empty:
    print("❌ Aucun contenu source trouvé")
    exit()

# 2. Traitement
df = normalize(df)
df = classify(df)
df = build_prompts(df)

# 3. Export final
export_prompts(df)

print("✅ PIPELINE TERMINÉ AVEC SUCCÈS")
```

**Note importante :** N'oubliez pas de créer un fichier vide `modules/__init__.py` pour que Python reconnaisse le dossier comme un package. Pour lancer l'automatisation, utilisez la commande `python master_pipeline.py` à la racine.