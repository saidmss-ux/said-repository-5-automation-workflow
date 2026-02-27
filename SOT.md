# Source of Truth (SOT) — automation_ia

Ce document est la référence fonctionnelle unique pour le pipeline `generation_prompts`.

## 1. Vision et stratégie

L'objectif est de créer un moteur de contenu automatisé capable de collecter, qualifier et préparer des publications sociales.

- **Philosophie "Content is Content"**: le contenu est agnostique à la plateforme source.
- **Modèle hybride**: l’automatisation prépare les liens + prompts, l’humain valide et l’IA externe finalise.
- **Architecture DB-ready**: stockage CSV structuré, migration SQL possible sans refonte majeure.

---

## 2. Arborescence de référence

```text
automation_ia/
├── data/
│   ├── source/                 # master_sources.csv
│   ├── generated/              # ready_to_generate.csv / prompts_ready.csv
│   └── trends_input/           # (optionnel) inputs trends
├── modules/
│   ├── __init__.py
│   ├── loader.py
│   ├── normalizer.py
│   ├── classifier.py
│   ├── prompt_builder.py
│   ├── generator.py
│   └── utils.py
├── prompts/
│   ├── prompt_templates.json   # template principal
│   └── prompt_template.json    # alias compatibilité
├── scripts/
│   └── validate_artifacts.py
├── master_pipeline.py
├── README.md
└── SKILL.md
```

---

## 3. Workflow pipeline end-to-end

Ordre strict de transformation:

1. **Loader**
   - Charge `data/source/master_sources.csv`
   - Valide colonnes minimales
   - Déduplique (`source_url`)

2. **Normalizer**
   - Produit `content_url` (clé canonique)
   - Normalise les colonnes texte et enums

3. **Classifier**
   - Attribue `origin_platform`, `niche`, `lang`, `rights`
   - Calcule `priority_score`
   - Calcule score manuel fusionné (`blended_priority_score`)

4. **Prompt Builder**
   - Charge templates JSON
   - Injecte métadonnées (`niche`, `lang`, `rights`, `usage_strategy`)
   - Produit `final_prompt`

5. **Generator**
   - Prépare champs intermédiaires (title/caption/raw_text)
   - Prépare payload IA externe (`ai_enhancement_payload`)

6. **Exporter**
   - Écrit:
     - `data/generated/ready_to_generate.csv`
     - `data/generated/prompts_ready.csv`

---

## 4. Statuts contrôlés

Statuts autorisés du pipeline:

- `RAW`
- `FILTERED`
- `READY_TO_GENERATE`
- `GENERATED`
- `PUBLISHED`

Conventions d’usage:
- `FILTERED`: source non exploitable (ex: `rights=AVOID`).
- `READY_TO_GENERATE`: prompt prêt pour IA externe.
- `GENERATED`: contenu textuel créé (hors scope actuel).
- `PUBLISHED`: contenu diffusé (hors scope actuel).

---

## 5. Schéma de données (contrat)

### 5.1 Colonnes minimales entrée (`master_sources.csv`)

- `source_url`
- `niche`
- `usage_strategy`
- `lang`
- `rights`

### 5.2 Colonnes d’entrée recommandées

- `origin_platform`
- `prompt_template`
- `processed`
- `notes`
- `source_file`
- `manual_score`
- `reviewer_decision`
- `reviewer_notes`

### 5.3 Colonnes de sortie (principales)

- **ready_to_generate.csv**
  - `source_url`, `content_url`, `niche`, `usage_strategy`, `lang`, `rights`
  - `priority_score`, `manual_priority_score`, `blended_priority_score`
  - `status`, `prompt_generated`, `content_ready`, `ai_status`

- **prompts_ready.csv**
  - toutes les colonnes ci-dessus +
  - `final_prompt`, `prompt_quality_score`, `prompt_quality_flags`, `ai_enhancement_payload`

---

## 6. Conventions CSV/JSON

- Encodage: **UTF-8**.
- Délimiteur CSV: standard `,`.
- Noms de colonnes en `snake_case`.
- Valeurs enum en majuscules pour `niche`, `lang`, `rights`, `status`.
- Warnings attendus:
  - colonnes optionnelles absentes -> fallback par défaut.
  - colonnes minimales absentes -> erreur explicite.

---

## 7. Templates prompts

Le fichier `prompts/prompt_templates.json` définit:
- `base_prompt` (role/rules/format)
- `content_goals`
- `transformation_levels`

Le fichier `prompts/prompt_template.json` doit rester un alias fonctionnel.

---

## 8. Règles d’implémentation

1. Python 3.13 + Pandas + `pathlib.Path`.
2. Chaque module est testable indépendamment (`__main__`).
3. Pas de chemin absolu système.
4. Si source vide: arrêt propre avec message `Aucun contenu trouvé`.
5. Logs debug simples à chaque étape.

---

## 9. Validation attendue

- `python -m py_compile ...`
- `python scripts/validate_artifacts.py`
- Exécution pipeline complète: `python master_pipeline.py` (environnement avec `pandas`)
- Preview `head(5)` des sorties.

---
## 10. Trend Validation v1 (Interface Layer Module)
## 10.1 Objectif

Trend Validation v1 est un module minimal destiné à fournir :

Un score simplifié (étoiles) d’un lien partagé.

Une suggestion d’amélioration ou de transformation du contenu.

Une aide décisionnelle pour créateur débutant.

Ce module ne remplace pas le pipeline principal.
Il agit comme couche d’interprétation légère destinée à une future interface utilisateur.

## 10.2 Position architecturale

Trend Validation v1 :

Consomme les sorties du pipeline existant.

Ne modifie pas master_pipeline.py.

Ne modifie pas les statuts contrôlés.

Ne modifie pas les schémas CSV contractuels.

Ne crée aucune nouvelle base de données.

Il peut lire :

ready_to_generate.csv

prompts_ready.csv

Mais ne doit jamais les altérer.

## 10.3 Scope fonctionnel

Entrée :

Un lien partagé par l’utilisateur.

Processus :

Recherche correspondance dans données existantes.

Analyse métadonnées existantes.

Génère :

trend_score (1 à 5 étoiles)

trend_reason

improvement_prompt

Sortie :

JSON simple destiné à une future UI.

## 10.4 Contraintes

Moins de 400 lignes.

Python 3.13.

Réutilisation modules existants si pertinent.

Aucun recalcul massif de scoring.

Aucun système asynchrone.

Pas de dépendance externe supplémentaire.

## 10.5 Évolution future

Trend Validation v1 est conçu comme :

Prototype pour interface utilisateur.

Couche de validation rapide.

Une future V2 pourrait :

Introduire pondération avancée.

Connecter API temps réel.

Ajouter métriques externes.

Mais ces évolutions seront versionnées explicitement.

## 10.6 Principe fondamental

Trend Validation v1 ne modifie pas le moteur principal.
Il reste un adaptateur externe aligné avec la philosophie “Content is Content”.
**Statut projet**: Stable V1+, prêt pour préparation de contenu assistée IA.
