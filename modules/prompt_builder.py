"""Build final prompts from normalized/classified content rows and JSON templates."""

from pathlib import Path
import pandas as pd

from modules.utils import debug_head, read_json_strict


def resolve_template_path(preferred_path: Path | None = None) -> Path:
    """Resolve template path with compatibility alias support."""
    if preferred_path is not None:
        if not preferred_path.exists():
            raise FileNotFoundError(f"[prompt_builder] Template not found: {preferred_path}")
        return preferred_path

    base_dir = Path(__file__).resolve().parent.parent / "prompts"
    primary = base_dir / "prompt_templates.json"
    alias = base_dir / "prompt_template.json"

    if primary.exists():
        return primary
    if alias.exists():
        return alias

    raise FileNotFoundError(
        f"[prompt_builder] Missing template file. Expected one of: {primary} or {alias}"
    )


def load_templates(template_path: Path | None = None) -> dict:
    """Load templates JSON using strict reader."""
    path = resolve_template_path(template_path)
    templates = read_json_strict(path)
    print(f"[prompt_builder] Loaded templates: {path}")
    return validate_template_contract(templates)


def validate_template_contract(templates: dict) -> dict:
    """Validate required template sections and inject safe defaults if key missing."""
    required_sections = ["base_prompt", "content_goals", "transformation_levels"]
    for section in required_sections:
        if section not in templates:
            raise ValueError(f"[prompt_builder] Missing template section: {section}")

    base = templates["base_prompt"]
    if not isinstance(base, dict):
        raise ValueError("[prompt_builder] base_prompt must be an object")

    base.setdefault("role", "You are a professional short-form content creator.")
    base.setdefault("rules", ["No plagiarism", "High value rewrite", "Strong hook (3s)"])
    base.setdefault("format", "Short-form script (30 to 60 seconds)")

    if not isinstance(base.get("rules"), list):
        raise ValueError("[prompt_builder] base_prompt.rules must be a list")

    return templates


def normalize_prompt_inputs(row: pd.Series) -> dict:
    """Normalize row metadata used for prompt rendering."""
    niche = str(row.get("niche", "MOTIVATION") or "MOTIVATION").strip().upper()
    lang = str(row.get("lang", "FR") or "FR").strip().upper()
    rights = str(row.get("rights", "REWRITE_REQUIRED") or "REWRITE_REQUIRED").strip().upper()
    usage_strategy = str(row.get("usage_strategy", "viral") or "viral").strip().lower()
    content_url = str(row.get("content_url", row.get("source_url", "")) or "").strip()

    if not content_url:
        raise ValueError("[prompt_builder] Missing content_url/source_url for one row")

    return {
        "niche": niche,
        "lang": lang,
        "rights": rights,
        "usage_strategy": usage_strategy,
        "content_url": content_url,
    }


def map_rights_to_transformation(rights: str, transformation_levels: dict) -> str:
    """Map rights enum to transformation key/value."""
    rights_mapping = {
        "FREE_REPOST": "repost",
        "REWRITE_REQUIRED": "rewrite",
        "INSPIRE_ONLY": "inspire",
        "AVOID": "avoid",
    }
    key = rights_mapping.get(rights, "rewrite")
    return transformation_levels.get(key, transformation_levels.get("rewrite", "Rewrite content."))


def map_strategy_to_goal(usage_strategy: str, content_goals: dict) -> dict:
    """Map usage strategy to goal object with safe fallback."""
    if usage_strategy in content_goals:
        return content_goals[usage_strategy]
    return content_goals.get("viral", {"objective": "Create viral content", "tone": "Energetic"})


def build_prompt_for_row(row: pd.Series, templates: dict) -> str:
    """Build final prompt text for a single content row."""
    normalized = normalize_prompt_inputs(row)

    base = templates["base_prompt"]
    goals = templates["content_goals"]
    transformations = templates["transformation_levels"]

    goal = map_strategy_to_goal(normalized["usage_strategy"], goals)
    transformation = map_rights_to_transformation(normalized["rights"], transformations)

    return (
        f"ROLE: {base['role']}\n"
        f"RULES: {'; '.join(base['rules'])}\n"
        f"OBJECTIVE: {goal.get('objective', 'Create viral content')}\n"
        f"TONE: {goal.get('tone', 'Energetic')}\n"
        f"TRANSFORMATION: {transformation}\n"
        f"NICHE: {normalized['niche']}\n"
        f"SOURCE: {normalized['content_url']}\n"
        f"LANGUAGE: {normalized['lang']}\n"
        f"FORMAT: {base['format']}"
    )


def build_prompts(df: pd.DataFrame, template_path: Path | None = None) -> pd.DataFrame:
    """Generate final prompts and prompt/status flags."""
    if df.empty:
        return df.copy()

    templates = load_templates(template_path)
    out = df.copy()

    out["final_prompt"] = out.apply(
        lambda row: "" if str(row.get("rights", "")).upper() == "AVOID" else build_prompt_for_row(row, templates),
        axis=1,
    )
    out["prompt_generated"] = out["final_prompt"].str.len() > 0
    out["content_ready"] = out["prompt_generated"] & (out.get("status", "READY_TO_GENERATE") != "FILTERED")

    return out


def run_prompt_builder(df: pd.DataFrame, template_path: Path | None = None) -> pd.DataFrame:
    """Run prompt builder stage and print debug preview."""
    print("[prompt_builder] Building prompts")
    out = build_prompts(df, template_path)
    debug_head(out, "prompt_builder output")
    return out


if __name__ == "__main__":
    sample_df = pd.DataFrame(
        {
            "content_url": ["https://youtube.com/watch?v=abc", "https://example.com/fallback"],
            "niche": ["MOTIVATION", ""],
            "lang": ["FR", None],
            "rights": ["REWRITE_REQUIRED", "INSPIRE_ONLY"],
            "usage_strategy": ["viral", "education"],
            "status": ["READY_TO_GENERATE", "READY_TO_GENERATE"],
        }
    )
    debug_head(run_prompt_builder(sample_df), "prompt_builder self-test")
