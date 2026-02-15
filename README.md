# automation_ia — Generation Prompts Pipeline

![Build](https://img.shields.io/github/actions/workflow/status/OWNER/REPO/ci.yml?branch=main)
![Coverage](https://img.shields.io/codecov/c/github/OWNER/REPO)
![License](https://img.shields.io/github/license/OWNER/REPO)
![PyPI](https://img.shields.io/pypi/v/automation-ia)

Pipeline Python modulaire pour préparer des liens scrappés et générer des prompts prêts pour IA externe.

## Description

Le projet transforme des sources CSV brutes en deux sorties exploitables:

- `data/generated/ready_to_generate.csv`: liens filtrés + métadonnées + scoring.
- `data/generated/prompts_ready.csv`: mêmes lignes + `final_prompt` généré.

Le workflow suit l’ordre:

`loader -> normalizer -> classifier -> prompt_builder -> generator -> export`

> Le scraping est hors scope de ce repo (voir `SOT.md`).

## Installation

### 1) Créer un environnement virtuel

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate   # Windows PowerShell
```

### 2) Installer les dépendances

```bash
pip install -r requirements.txt
```

## Structure du projet

```text
.
├── config/
├── data/
│   ├── source/
│   │   └── master_sources.csv
│   └── generated/
│       ├── ready_to_generate.csv
│       └── prompts_ready.csv
├── modules/
│   ├── loader.py
│   ├── normalizer.py
│   ├── classifier.py
│   ├── prompt_builder.py
│   ├── generator.py
│   └── utils.py
├── prompts/
│   ├── prompt_templates.json
│   └── prompt_template.json
├── scripts/
│   └── validate_artifacts.py
├── SOT.md
├── SKILL.md
└── master_pipeline.py
```

## Lancement du pipeline

```bash
python master_pipeline.py
```

Le pipeline lit `data/source/master_sources.csv` et produit:

- `data/generated/ready_to_generate.csv`
- `data/generated/prompts_ready.csv`


## Module YouTube Scraping

Un module dédié est disponible: `modules/youtube_scrap.py` (API YouTube + fallback HTML).

- Exécution rapide: `python modules/youtube_scrap.py`
- Manuel détaillé: `docs_youtube_scrap_manual.md`

## Validation

### Validation de syntaxe

```bash
python -m py_compile master_pipeline.py modules/*.py config/settings.py scripts/validate_artifacts.py
```

### Validation artefacts

```bash
python scripts/validate_artifacts.py
```

Ce script vérifie:
- la parité `prompt_templates.json` / `prompt_template.json`;
- la présence des colonnes critiques;
- le volume attendu (10 lignes démo);
- un aperçu `head(5)`.

## Exemples de sorties

- `ready_to_generate.csv` contient notamment:
  - `priority_score`, `manual_priority_score`, `blended_priority_score`, `status`, `ai_status`
- `prompts_ready.csv` contient notamment:
  - `final_prompt`, `prompt_quality_score`, `prompt_quality_flags`, `ai_enhancement_payload`

## Conventions contributeurs

- Respecter PEP8.
- Utiliser `pathlib.Path` pour tous les chemins.
- Ajouter logs debug simples.
- Ajouter/maintenir un test `head(5)`.
- Lever des erreurs explicites pour fichiers/colonnes manquants.

### Process recommandé

1. Ouvrir une issue (bug/feature).
2. Proposer un plan technique.
3. Implémenter par module.
4. Exécuter validations.
5. Soumettre PR avec résumé + commandes test.

## License

Voir `LICENSE`.
