Voici la **Source of Truth (SoT)** officielle pour le projet **automation_ia**, conçue pour servir de référence unique à toute future implémentation ou automatisation via Codex.

### 1. Vision et Stratégie du Projet
L'objectif est de créer un moteur de contenu automatisé capable de collecter, qualifier et préparer des publications pour les réseaux sociaux afin de générer des revenus. 

*   **Philosophie "Content is Content"** : Le contenu est traité de manière agnostique vis-à-vis de la plateforme d'origine (YouTube, TikTok, Facebook) pour être redistribué là où l'audience se trouve.
*   **Modèle Hybride** : L'automatisation s'arrête à la préparation intelligente (liens + prompts). La création finale et la validation restent le fruit d'une collaboration entre l'humain et l'IA générative externe.
*   **Architecture "DB-Ready"** : Le système utilise actuellement des fichiers CSV comme une base de données plate, structurée de manière à être migrée vers SQL sans refonte du code.

---

### 2. Arborescence Officielle du Projet
Cette structure de fichiers est la carte officielle du projet pour garantir la modularité et éviter la dette technique :

```text
automation_ia/
├── data/
│   ├── source/           # Sources brutes (master_sources.csv)
│   ├── generated/        # Sorties finales (prompts_ready.csv)
│   └── trends_input/     # Fichiers texte pour le trend_loader
├── modules/              # Logique métier (importable par le pipeline)
│   ├── __init__.py
│   ├── loader.py         # Chargement des données
│   ├── normalizer.py     # Standardisation des colonnes
│   ├── classifier.py     # Niche, Langue, Droits
│   ├── prompt_builder.py # Assemblage des prompts finaux
│   └── utils.py          # Fonctions I/O communes
├── prompts/
│   └── prompt_template.json # Cerveau éditorial et templates
├── master_pipeline.py    # Point d'entrée unique
└── README.md
```

---

### 3. Pipeline de Données (Workflow)
Le workflow suit un ordre strict de transformation des données :

1.  **Loader** : Charge les liens depuis `data/source/master_sources.csv` et évite les doublons.
2.  **Normalizer** : Convertit les colonnes d'entrée en un schéma canonique, avec `content_url` comme clé de vérité.
3.  **Classifier** : Attribue une niche, une langue et un niveau de droits selon des règles déterministes (sans IA à ce stade).
4.  **Scorer (Optionnel)** : Calcule une priorité (`priority_score`) basée sur la niche et la langue pour trier les meilleurs contenus.
5.  **Prompt Builder** : Injecte les métadonnées dans les templates de `prompt_template.json`.
6.  **Exporter** : Génère le fichier final `prompts_ready.csv` et, optionnellement, des fichiers `.txt` individuels.

---

### 4. Schéma de Données (Table : `content_sources`)
Ceci est le contrat de données que chaque module doit respecter :

| Champ | Type | Description |
| :--- | :--- | :--- |
| `id` | UUID | Identifiant unique du contenu. |
| `source_url` | Text | URL d'origine du contenu. |
| `origin_platform` | Enum | YOUTUBE, TIKTOK, FACEBOOK, OTHER. |
| `niche` | Enum | MOTIVATION, BUSINESS, HEALTH, STORY, EDUCATION, etc. |
| `lang` | Enum | FR, EN, etc. |
| `rights` | Enum | FREE_REPOST, REWRITE_REQUIRED, INSPIRE_ONLY, AVOID. |
| `status` | Enum | RAW, FILTERED, READY_TO_GENERATE, GENERATED, PUBLISHED. |
| `priority_score` | Int | Score de 0 à 100 pour la sélection manuelle. |
| `final_prompt` | Text | Le prompt complet prêt pour l'IA générative externe. |

---

### 5. Bibliothèque de Prompts et Règles Métier

#### Logique des Niches (Public-First)
Les niches sont choisies pour leur potentiel de monétisation et leur facilité de transformation par l'IA :
*   **MOTIVATION** : Focus discipline et mentalité (Haut potentiel).
*   **BUSINESS** : Mindset entrepreneur et finance (Fort CPM).
*   **STORY** : Histoires humaines et émotions brutes.

#### Templates de Prompts (Structure JSON)
Le fichier `prompt_template.json` définit le rôle ("Professional content creator"), les contraintes (Pas de plagiat, hook de 3s) et les objectifs par niche (Viral, Education, Inspiration).

---

### 6. Guide d'Implémentation pour Codex
Pour toute nouvelle fonctionnalité, Codex doit suivre cette **TODO list** dérivée du plan validé :
1.  **Environnement** : Utiliser Python 3.13, Pandas pour la manipulation de données, et `pathlib` pour la gestion des chemins.
2.  **Instruction** : Chaque module doit être testable indépendamment avec un bloc `if __name__ == "__main__":`.
3.  **Contrainte** : Ne jamais utiliser de chemins absolus (ex: `C:\...`) ; utiliser uniquement des chemins relatifs à la racine du projet.
4.  **Validation** : Le pipeline doit s'arrêter proprement et loguer un message clair ("Aucun contenu trouvé") si les sources sont vides.

**Statut du projet** : Stable V1. Prêt pour la phase de production de contenu manuelle assistée par IA.