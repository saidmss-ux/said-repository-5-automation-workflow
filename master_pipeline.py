"""Main orchestration pipeline from source links to prompt-ready CSV outputs."""

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
from modules.prompt_builder import run_prompt_builder
from modules.utils import debug_head, ensure_dir, save_csv_safe


def run_pipeline(
    source_csv_path: Path = MASTER_SOURCES_CSV,
    ready_output_path: Path = READY_TO_GENERATE_CSV,
    prompts_output_path: Path = PROMPTS_READY_CSV,
    template_path: Path = PROMPT_TEMPLATES_JSON,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run complete content automation pipeline and export outputs."""
    print("[pipeline] 🚀 MASTER PIPELINE STARTED")

    df = run_loader(source_csv_path)
    if df.empty:
        print("[pipeline] ❌ Aucun contenu trouvé")
        return pd.DataFrame(), pd.DataFrame()

    df = run_normalizer(df)
    df = run_classifier(df)
    df = run_prompt_builder(df, template_path)
    df = run_generator(df)

    ready_columns = [
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
        "status",
        "prompt_generated",
        "content_ready",
        "title_seed",
        "caption_seed",
    ]
    prompts_columns = ready_columns + ["final_prompt", "raw_text"]

    ready_df = df[[column for column in ready_columns if column in df.columns]].copy()
    prompts_df = df[[column for column in prompts_columns if column in df.columns]].copy()

    ensure_dir(ready_output_path.parent)
    save_csv_safe(ready_df, ready_output_path)
    save_csv_safe(prompts_df, prompts_output_path)

    debug_head(ready_df, "ready_to_generate preview")
    debug_head(prompts_df, "prompts_ready preview")

    print("[pipeline] ✅ PIPELINE TERMINÉ")
    return ready_df, prompts_df


def run_demo_with_10_rows() -> None:
    """Create 10 demo rows and run the full pipeline."""
    print("[pipeline] Running demo with 10 fictive rows")
    ensure_dir(MASTER_SOURCES_CSV.parent)

    demo_rows = [
        {
            "source_url": f"https://youtube.com/watch?v=video{i}",
            "niche": "MOTIVATION" if i % 2 == 0 else "BUSINESS",
            "usage_strategy": "viral" if i % 3 != 0 else "education",
            "lang": "FR" if i % 2 == 0 else "EN",
            "rights": "REWRITE_REQUIRED" if i % 4 != 0 else "INSPIRE_ONLY",
            "origin_platform": "",
            "prompt_template": "default",
            "processed": False,
            "notes": f"demo-row-{i}",
            "source_file": "master_sources.csv",
        }
        for i in range(1, 11)
    ]

    pd.DataFrame(demo_rows).to_csv(MASTER_SOURCES_CSV, index=False, encoding="utf-8")
    print(f"[pipeline] Demo source written: {MASTER_SOURCES_CSV}")

    run_pipeline()


if __name__ == "__main__":
    run_demo_with_10_rows()
