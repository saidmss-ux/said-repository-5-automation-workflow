"""Build final prompts from normalized/classified rows and JSON templates."""

from pathlib import Path
import re
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
        f"[prompt_builder] Missing template file. Expected: {primary} or {alias}"
    )


def load_templates(template_path: Path | None = None) -> dict:
    """Load templates JSON using strict reader."""
    path = resolve_template_path(template_path)
    templates = read_json_strict(path)
    print(f"[prompt_builder] Loaded templates: {path}")
    return validate_template_contract(templates)


def validate_template_contract(templates: dict) -> dict:
    """Validate required template sections and base shape."""
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

    if not isinstance(base["rules"], list):
        raise ValueError("[prompt_builder] base_prompt.rules must be a list")

    return templates


def normalize_prompt_inputs(row: pd.Series) -> dict:
    """Normalize row metadata used for prompt rendering."""
    content_url = str(row.get("content_url", row.get("source_url", "")) or "").strip()
    if not content_url:
        raise ValueError("[prompt_builder] Missing content_url/source_url on one row")

    return {
        "content_url": content_url,
        "niche": str(row.get("niche", "MOTIVATION") or "MOTIVATION").strip().upper(),
        "lang": str(row.get("lang", "FR") or "FR").strip().upper(),
        "rights": str(row.get("rights", "REWRITE_REQUIRED") or "REWRITE_REQUIRED").strip().upper(),
        "usage_strategy": str(row.get("usage_strategy", "viral") or "viral").strip().lower(),
        "notes": str(row.get("notes", "") or "").strip(),
        "blended_priority_score": int(row.get("blended_priority_score", row.get("priority_score", 0))),
    }


def map_rights_to_transformation(rights: str, transformation_levels: dict) -> str:
    """Map rights enum to transformation description."""
    mapping = {
        "FREE_REPOST": "repost",
        "REWRITE_REQUIRED": "rewrite",
        "INSPIRE_ONLY": "inspire",
        "AVOID": "avoid",
    }
    key = mapping.get(rights, "rewrite")
    return transformation_levels.get(key, transformation_levels.get("rewrite", "Rewrite content."))


def map_strategy_to_goal(usage_strategy: str, content_goals: dict) -> dict:
    """Map strategy to goal object with fallback."""
    return content_goals.get(
        usage_strategy,
        content_goals.get("viral", {"objective": "Create viral content", "tone": "Energetic"}),
    )


def build_prompt_for_row(row: pd.Series, templates: dict, ai_enhancement: dict | None = None) -> str:
    """Build final prompt text for one row."""
    normalized = normalize_prompt_inputs(row)
    base = templates["base_prompt"]
    goals = templates["content_goals"]
    transformations = templates["transformation_levels"]

    goal = map_strategy_to_goal(normalized["usage_strategy"], goals)
    transformation = map_rights_to_transformation(normalized["rights"], transformations)

    ai_hint = ""
    if ai_enhancement:
        ai_hint = f"\nAI_ENHANCEMENT_HINT: {ai_enhancement.get('hint', '')}"

    return (
        f"ROLE: {base['role']}\n"
        f"RULES: {'; '.join(base['rules'])}\n"
        f"OBJECTIVE: {goal.get('objective', 'Create viral content')}\n"
        f"TONE: {goal.get('tone', 'Energetic')}\n"
        f"TRANSFORMATION: {transformation}\n"
        f"NICHE: {normalized['niche']}\n"
        f"LANGUAGE: {normalized['lang']}\n"
        f"SOURCE: {normalized['content_url']}\n"
        f"PRIORITY_SCORE: {normalized['blended_priority_score']}\n"
        f"EDITOR_NOTES: {normalized['notes'] or 'None'}\n"
        f"FORMAT: {base['format']}"
        f"{ai_hint}"
    )


def apply_prompt_quality_rules(prompt_text: str) -> dict:
    """Return lightweight prompt quality flags and score."""
    flags = []
    score = 100

    if len(prompt_text) < 180:
        flags.append("prompt_too_short")
        score -= 25
    if not re.search(r"\bROLE:\b", prompt_text):
        flags.append("missing_role")
        score -= 20
    if not re.search(r"\bOBJECTIVE:\b", prompt_text):
        flags.append("missing_objective")
        score -= 20
    if not re.search(r"\bSOURCE:\b", prompt_text):
        flags.append("missing_source")
        score -= 20

    return {
        "prompt_text": prompt_text,
        "quality_flags": "|".join(flags) if flags else "OK",
        "quality_score": max(0, min(score, 100)),
    }


def build_prompts(
    df: pd.DataFrame,
    template_path: Path | None = None,
    enable_ai_prep: bool = True,
) -> pd.DataFrame:
    """Generate final prompts and prompt quality columns."""
    if df.empty:
        return df.copy()

    templates = load_templates(template_path)
    out = df.copy()

    out["final_prompt"] = out.apply(
        lambda row: ""
        if str(row.get("rights", "")).upper() == "AVOID"
        else build_prompt_for_row(
            row,
            templates,
            ai_enhancement={"hint": "Improve hook + CTA"} if enable_ai_prep else None,
        ),
        axis=1,
    )

    quality_df = out["final_prompt"].apply(apply_prompt_quality_rules).apply(pd.Series)
    out["final_prompt"] = quality_df["prompt_text"]
    out["prompt_quality_flags"] = quality_df["quality_flags"]
    out["prompt_quality_score"] = quality_df["quality_score"]

    out["prompt_generated"] = out["final_prompt"].str.len() > 0
    out["content_ready"] = out["prompt_generated"] & (out.get("status", "READY_TO_GENERATE") != "FILTERED")

    return out


def run_prompt_builder(df: pd.DataFrame, template_path: Path | None = None) -> pd.DataFrame:
    """Run prompt builder stage and print debug preview."""
    print("[prompt_builder] Building prompts")
    out = build_prompts(df, template_path=template_path, enable_ai_prep=True)
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
            "blended_priority_score": [78, 64],
        }
    )
    debug_head(run_prompt_builder(sample_df), "prompt_builder self-test")
