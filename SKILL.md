# SKILL.md — Engineering Contract (Pipeline `generation_prompts`)

Ce document est le **contrat d’ingénierie** pour tout changement sur le pipeline Python.
Les sorties générées par Codex (code, prompts, docs) doivent rester conformes à ce contrat.

## 1) Scope

- Projet Python 3.13 orienté automatisation de contenu.
- Source of Truth fonctionnelle: `SOT.md`.
- Pipeline cible: `loader -> normalizer -> classifier -> prompt_builder -> generator -> export`.

## 2) Coding Rules

- Code **modulaire**, lisible, et testable par module.
- Respect strict PEP8.
- Utiliser `pathlib.Path` pour tous les chemins.
- Ajouter des logs simples pour debug (`print("[module] ...")`).
- Chaque module doit inclure un bloc `if __name__ == "__main__":` avec un mini test.
- Toujours conserver la compatibilité des noms de templates:
  - `prompts/prompt_templates.json`
  - `prompts/prompt_template.json` (alias)

## 3) Error Handling Contract

### Erreur explicite (obligatoire)

Lever une erreur explicite dans les cas suivants:
- CSV source manquant ou mal formé.
- Colonnes minimales manquantes.
- JSON template manquant ou mal formé.
- Schéma template invalide.

### Fallback contrôlé (autorisé)

Utiliser un fallback uniquement pour:
- Valeurs métiers manquantes (`niche`, `lang`, `rights`, `usage_strategy`) avec defaults documentés.
- Mapping strategy/rights vers valeurs par défaut sûres (`viral`, `rewrite`).

## 4) Data Conventions

- Encodage CSV/JSON: UTF-8.
- Colonnes minimales d’entrée: `source_url`, `niche`, `lang`, `rights`, `usage_strategy`.
- Colonnes de sortie critiques:
  - `ready_to_generate.csv`: métadonnées + scores + flags.
  - `prompts_ready.csv`: mêmes métadonnées + `final_prompt`.

## 5) Tests & Validation

- Validation syntaxique (`py_compile`) obligatoire.
- Validation artefacts obligatoire via script dédié.
- Afficher `head(5)` des sorties dans les checks de validation.
- Tenter un run end-to-end de `master_pipeline.py` dans un environnement avec `pandas`.

## 6) Acceptance Criteria (End-to-End)

Une implémentation est acceptée si:
1. Les templates alias sont cohérents (`prompt_templates.json` == `prompt_template.json`).
2. Les deux CSV finaux existent et contiennent 10 lignes en mode démo.
3. `prompts_ready.csv` contient `final_prompt` non vide pour les lignes éligibles.
4. Les colonnes de scoring (`priority_score`, `blended_priority_score`) sont présentes.
5. Les logs de debug et les previews `head(5)` sont visibles.

## 7) Prompt/Docs Contract for Codex

- Les prompts générés par Codex doivent respecter ce contrat (structure, contraintes et mapping).
- Les documents (`README.md`, `SOT.md`, `SKILL.md`) servent de **source contractuelle** pour les futures générations.
- En cas de divergence, `SOT.md` + ce `SKILL.md` priment sur les hypothèses implicites.
