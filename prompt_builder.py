"""
Module: prompt_builder.py

Responsabilité:
Construire des prompts finaux prêts pour IA externe à partir:
- d'un DataFrame classifié (URL, niche, langue, droits, stratégie)
- d'un fichier JSON de templates (prompts/prompt_template.json)
- d'une logique robuste de fallback et validation

Aligné strictement sur:
- Source of Truth (SoT)
- Architecture modulaire du projet
- Plan validé (version expert)

Ordre logique:
1. Résolution chemin templates
2. Chargement JSON
3. Validation + injection defaults
4. Génération prompt par ligne
5. Enrichissement DataFrame
6. Debug preview
"""

from pathlib import Path
import json
import pandas as pd


# ============================================================
# A. get_prompt_file_path
# ============================================================

def get_prompt_file_path() -> Path:
    """
    Résout le chemin relatif vers prompts/prompt_template.json
    (100% relatif projet, aucun chemin absolu).
    """
    base_dir = Path(__file__).resolve().parent.parent
    return base_dir / "prompts" / "prompt_template.json"


# ============================================================
# B. load_prompt_templates
# ============================================================

def load_prompt_templates(prompt_path: Path | None = None) -> dict:
    """
    Charge le fichier JSON de templates.

    - Vérifie existence
    - Charge UTF-8
    - Lève erreur explicite si problème
    """

    if prompt_path is None:
        prompt_path = get_prompt_file_path()

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"[prompt_builder] Template file not found: {prompt_path}"
        )

    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            templates = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"[prompt_builder] Invalid JSON format in {prompt_path}"
        ) from e

    print(f"[prompt_builder] templates loaded from {prompt_path}")

    return templates


# ============================================================
# C. validate_templates
# ============================================================

def validate_templates(templates: dict) -> dict:
    """
    Vérifie la présence des sections minimales
    et injecte des defaults sûrs si nécessaire.

    Ne supprime aucune clé existante.
    """

    defaults = {
        "base_prompt": "You are a professional content creator.",
        "content_goals": {
            "viral": "Create highly engaging content designed to maximize reach.",
            "education": "Create clear and structured educational content."
        },
        "transformation_levels": {
            "rewrite": "Rewrite the source with significant transformation.",
            "summary": "Summarize the source clearly.",
            "none": "Keep structure but improve clarity."
        }
    }

    for key, value in defaults.items():
        if key not in templates:
            templates[key] = value

    return templates


# ============================================================
# D. normalize_strategy_key
# ============================================================

def normalize_strategy_key(value: str | None) -> str:
    """
    Harmonise usage_strategy:
    - lower
    - strip
    - fallback 'viral'
    """

    if not value:
        return "viral"

    return str(value).strip().lower()


# ============================================================
# E. normalize_rights_key
# ============================================================

def normalize_rights_key(value: str | None) -> str:
    """
    Mapping déterministe rights -> transformation_levels.
    Compatible SoT (droits = règle métier clé).
    """

    if not value:
        return "rewrite"

    value = str(value).strip().lower()

    mapping = {
        "rewrite_required": "rewrite",
        "summary_only": "summary",
        "original_allowed": "none",
    }

    return mapping.get(value, "rewrite")


# ============================================================
# F. build_prompt_for_row
# ============================================================

def build_prompt_for_row(row: pd.Series, templates: dict) -> str:
    """
    Construit le prompt final pour une ligne DataFrame.
    """

    content_url = row.get("content_url", "")
    niche = row.get("niche", "general")
    lang = row.get("lang", "en")
    strategy_raw = row.get("usage_strategy", None)
    rights_raw = row.get("rights", None)

    strategy = normalize_strategy_key(strategy_raw)
    rights = normalize_rights_key(rights_raw)

    base_prompt = templates.get("base_prompt", "")
    goal = templates.get("content_goals", {}).get(
        strategy,
        templates["content_goals"].get("viral")
    )
    transformation = templates.get("transformation_levels", {}).get(
        rights,
        templates["transformation_levels"].get("rewrite")
    )

    final_prompt = f"""
ROLE:
{base_prompt}

OBJECTIVE:
{goal}

TRANSFORMATION RULE:
{transformation}

NICHE:
{niche}

SOURCE URL:
{content_url}

LANGUAGE:
{lang}

FORMAT:
Structured, platform-ready, optimized for engagement.
""".strip()

    return final_prompt


# ============================================================
# G. build_prompts
# ============================================================

def build_prompts(
    df: pd.DataFrame,
    templates: dict | None = None
) -> pd.DataFrame:
    """
    Génère les prompts pour toutes les lignes
    et enrichit le DataFrame avec:

    - final_prompt
    - prompt_generated (bool)
    - content_ready (bool)
    """

    if templates is None:
        templates = load_prompt_templates()

    templates = validate_templates(templates)

    df_copy = df.copy()

    prompts = []
    prompt_flags = []
    ready_flags = []

    for _, row in df_copy.iterrows():

        prompt = build_prompt_for_row(row, templates)

        prompt_generated = bool(prompt.strip())

        rights_normalized = normalize_rights_key(
            row.get("rights", None)
        )

        content_ready = (
            prompt_generated
            and prompt.strip() != ""
            and rights_normalized in templates["transformation_levels"]
        )

        prompts.append(prompt)
        prompt_flags.append(prompt_generated)
        ready_flags.append(content_ready)

    df_copy["final_prompt"] = prompts
    df_copy["prompt_generated"] = prompt_flags
    df_copy["content_ready"] = ready_flags

    return df_copy


# ============================================================
# H. debug_preview
# ============================================================

def debug_preview(df: pd.DataFrame, n: int = 5) -> None:
    """
    Affiche un aperçu des n premières lignes.
    """
    print("\n[prompt_builder] DEBUG PREVIEW")
    print(df.head(n))


# ============================================================
# I. main (test local autonome)
# ============================================================

def main():
    """
    Test autonome du module.
    Permet validation indépendante sans pipeline complet.
    """

    mock_data = {
        "content_url": ["https://example.com/article1"],
        "niche": ["ai"],
        "lang": ["en"],
        "usage_strategy": ["viral"],
        "rights": ["REWRITE_REQUIRED"],
    }

    df_mock = pd.DataFrame(mock_data)

    df_with_prompts = build_prompts(df_mock)

    debug_preview(df_with_prompts, 5)


if __name__ == "__main__":
    main()
