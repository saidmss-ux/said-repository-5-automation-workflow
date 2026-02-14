"""Build final prompts from classified records and JSON templates."""

from pathlib import Path
import json
import pandas as pd

from modules.utils import debug_head


def get_prompt_template_path() -> Path:
    """Resolve JSON template path with primary and compatibility fallback."""
    base_dir = Path(__file__).resolve().parent.parent
    primary = base_dir / "prompts" / "prompt_templates.json"
    if primary.exists():
        return primary
    return base_dir / "prompts" / "prompt_template.json"


def load_prompt_templates(template_path: Path | None = None) -> dict:
    """Load prompt templates from JSON file."""
    path = template_path or get_prompt_template_path()
    if not path.exists():
        raise FileNotFoundError(f"Template JSON not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        templates = json.load(file)

    print(f"[prompt_builder] Templates loaded from: {path}")
    return templates


def validate_prompt_templates(templates: dict) -> dict:
    """Validate required sections and inject safe defaults."""
    defaults = {
        "base_prompt": {
            "role": "You are a professional short-form content creator.",
            "rules": ["No plagiarism", "High value rewrite", "Strong hook (3s)"],
            "format": "Short-form script (30 to 60 seconds)",
        },
        "content_goals": {
            "viral": {"objective": "Create viral content", "tone": "Energetic"},
            "education": {"objective": "Teach a concept", "tone": "Clear"},
            "inspiration": {"objective": "Inspire audience action", "tone": "Emotional"},
        },
        "transformation_levels": {
            "rewrite": "Full rewrite with original structure.",
            "inspire": "Extract insights and produce inspirational adaptation.",
            "repost": "Keep core message with safe adaptation.",
            "avoid": "Do not generate content from this source.",
        },
    }

    merged = dict(templates)
    for section, default_value in defaults.items():
        if section not in merged:
            merged[section] = default_value
    return merged


def map_usage_strategy_to_goal_key(usage_strategy: str | None) -> str:
    """Map usage_strategy value to content goal key."""
    strategy = (usage_strategy or "").strip().lower()
    if strategy in {"viral", "education", "inspiration"}:
        return strategy
    return "viral"


def map_rights_to_transform_key(rights: str | None) -> str:
    """Map rights enum to transformation key."""
    mapping = {
        "FREE_REPOST": "repost",
        "REWRITE_REQUIRED": "rewrite",
        "INSPIRE_ONLY": "inspire",
        "AVOID": "avoid",
    }
    normalized = (rights or "").strip().upper()
    return mapping.get(normalized, "rewrite")


def build_prompt_row(row: pd.Series, templates: dict) -> str:
    """Build final prompt text for one row."""
    base = templates["base_prompt"]
    goals = templates["content_goals"]
    transforms = templates["transformation_levels"]

    goal_key = map_usage_strategy_to_goal_key(row.get("usage_strategy"))
    transform_key = map_rights_to_transform_key(row.get("rights"))

    goal = goals.get(goal_key, goals["viral"])
    transform = transforms.get(transform_key, transforms["rewrite"])

    return (
        f"ROLE: {base['role']}\n"
        f"RULES: {'; '.join(base['rules'])}\n"
        f"OBJECTIVE: {goal['objective']}\n"
        f"TONE: {goal['tone']}\n"
        f"TRANSFORMATION: {transform}\n"
        f"NICHE: {row.get('niche', 'MOTIVATION')}\n"
        f"SOURCE: {row.get('content_url', row.get('source_url', ''))}\n"
        f"LANGUAGE: {row.get('lang', 'FR')}\n"
        f"FORMAT: {base['format']}"
    )


def build_prompts(df: pd.DataFrame, templates: dict | None = None) -> pd.DataFrame:
    """Generate prompts and add readiness flags."""
    if df.empty:
        return df

    validated_templates = validate_prompt_templates(templates or load_prompt_templates())
    out = df.copy()

    out["final_prompt"] = out.apply(
        lambda row: "" if row.get("rights") == "AVOID" else build_prompt_row(row, validated_templates),
        axis=1,
    )
    out["prompt_generated"] = out["final_prompt"].astype(str).str.len() > 0
    out["content_ready"] = out["prompt_generated"] & (out.get("status", "") != "FILTERED")

    return out


def run_prompt_builder(df: pd.DataFrame, template_path: Path | None = None) -> pd.DataFrame:
    """Pipeline-facing prompt builder wrapper."""
    print("[prompt_builder] Building prompts")
    if df.empty:
        print("[prompt_builder] Empty input DataFrame")
        return df

    try:
        templates = load_prompt_templates(template_path)
        out = build_prompts(df, templates)
    except Exception as exc:  # noqa: BLE001
        print(f"[prompt_builder] Failed: {exc}")
        raise

    debug_head(out, "prompt_builder output")
    return out


if __name__ == "__main__":
    sample = pd.DataFrame(
        {
            "content_url": ["https://youtube.com/watch?v=abc"],
            "niche": ["MOTIVATION"],
            "lang": ["FR"],
            "rights": ["REWRITE_REQUIRED"],
            "usage_strategy": ["viral"],
            "status": ["READY_TO_GENERATE"],
        }
    )
    result = run_prompt_builder(sample)
    debug_head(result, "prompt_builder self-test")
