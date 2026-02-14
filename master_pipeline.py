"""Main orchestration pipeline from sources CSV to prompt-ready outputs."""

from pathlib import Path
import pandas as pd

from config.settings import (
    MASTER_SOURCES_CSV,
    PROMPT_TEMPLATES_JSON,
    PROMPTS_READY_CSV,
    READY_TO_GENERATE_CSV,
)
from modules.classifier import run_classifier
from modules.generator import run_generator
from modules.loader import run_loader
from modules.normalizer import run_normalizer
from modules.prompt_builder import build_prompts
from modules.utils import debug_head, ensure_dir, write_csv


READY_COLUMNS = [
    "source_url",
    "content_url",
    "niche",
    "usage_strategy",
    "lang",
    "rights",
    "origin_platform",
    "prompt_template",
    "processed",
    "notes",
    "source_file",
    "priority_score",
    "manual_score",
    "manual_priority_score",
    "blended_priority_score",
    "reviewer_decision",
    "reviewer_notes",
    "status",
    "prompt_generated",
    "prompt_quality_score",
    "content_ready",
    "title_seed",
    "caption_seed",
    "ai_status",
]

PROMPTS_COLUMNS = READY_COLUMNS + [
    "final_prompt",
    "prompt_quality_flags",
    "raw_text",
    "ai_enhancement_payload",
]


def sort_for_manual_review(df: pd.DataFrame) -> pd.DataFrame:
    """Sort output by blended score descending for human review."""
    if "blended_priority_score" not in df.columns:
        return df
    return df.sort_values(by=["blended_priority_score", "priority_score"], ascending=False).reset_index(drop=True)


def run_pipeline(
    source_csv: Path = MASTER_SOURCES_CSV,
    template_path: Path | None = PROMPT_TEMPLATES_JSON,
    ready_csv: Path = READY_TO_GENERATE_CSV,
    prompts_csv: Path = PROMPTS_READY_CSV,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run full pipeline and export final CSV files."""
    print("[pipeline] START")
    df = run_loader(source_csv)
    if df.empty:
        print("[pipeline] Aucun contenu trouvé")
        return pd.DataFrame(), pd.DataFrame()

    df = run_normalizer(df)
    df = run_classifier(df)
    df = build_prompts(df, template_path=template_path, enable_ai_prep=True)
    df = run_generator(df)
    df = sort_for_manual_review(df)

    ready_df = df[[column for column in READY_COLUMNS if column in df.columns]].copy()
    prompts_df = df[[column for column in PROMPTS_COLUMNS if column in df.columns]].copy()

    ensure_dir(ready_csv.parent)
    write_csv(ready_df, ready_csv)
    write_csv(prompts_df, prompts_csv)

    debug_head(ready_df, "ready_to_generate head(5)")
    debug_head(prompts_df, "prompts_ready head(5)")
    print("[pipeline] END")
    return ready_df, prompts_df


def run_demo_10_rows() -> None:
    """Generate demo dataset with 10 rows and execute pipeline."""
    ensure_dir(MASTER_SOURCES_CSV.parent)
    demo_rows = []

    for index in range(1, 11):
        demo_rows.append(
            {
                "source_url": f"https://youtube.com/watch?v=video{index}",
                "niche": "MOTIVATION" if index % 2 == 0 else "BUSINESS",
                "usage_strategy": "education" if index % 3 == 0 else "viral",
                "lang": "FR" if index % 2 == 0 else "EN",
                "rights": "INSPIRE_ONLY" if index % 4 == 0 else "REWRITE_REQUIRED",
                "manual_score": 92 if index in {2, 6} else "",
                "reviewer_decision": "SELECT" if index in {2, 6} else "PENDING",
                "reviewer_notes": "High potential" if index in {2, 6} else "",
                "origin_platform": "",
                "prompt_template": "default",
                "processed": False,
                "notes": f"demo-row-{index}",
                "source_file": MASTER_SOURCES_CSV.name,
            }
        )

    pd.DataFrame(demo_rows).to_csv(MASTER_SOURCES_CSV, index=False, encoding="utf-8")
    print(f"[pipeline] Demo source generated: {MASTER_SOURCES_CSV}")
    run_pipeline()


if __name__ == "__main__":
    run_demo_10_rows()
