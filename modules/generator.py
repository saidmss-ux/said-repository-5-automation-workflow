"""Prepare generation payload fields for external AI integration."""

import pandas as pd

from modules.utils import debug_head


def prepare_generation_fields(row: pd.Series) -> dict:
    """Prepare title/caption/raw_text seeds for one row."""
    content_url = str(row.get("content_url", "")).strip()
    niche = str(row.get("niche", "MOTIVATION")).strip().upper()
    lang = str(row.get("lang", "FR")).strip().upper()

    return {
        "title_seed": f"[{niche}] Hook idea from {content_url}",
        "caption_seed": f"{niche.title()} | {lang} | Source: {content_url}",
        "raw_text": row.get("raw_text", f"Source content collected from {content_url}"),
    }


def build_generation_payload(df: pd.DataFrame) -> pd.DataFrame:
    """Add generation helper columns to DataFrame."""
    out = df.copy()
    payload_series = out.apply(prepare_generation_fields, axis=1)
    out["title_seed"] = payload_series.apply(lambda payload: payload["title_seed"])
    out["caption_seed"] = payload_series.apply(lambda payload: payload["caption_seed"])
    out["raw_text"] = payload_series.apply(lambda payload: payload["raw_text"])

    if "content_ready" not in out.columns:
        out["content_ready"] = out.get("prompt_generated", False)

    return out


def run_generator(df: pd.DataFrame) -> pd.DataFrame:
    """Run generator stage and print debug preview."""
    print("[generator] Building generation payload")
    out = build_generation_payload(df)
    debug_head(out, "generator output")
    return out


if __name__ == "__main__":
    sample_df = pd.DataFrame(
        {
            "content_url": ["https://youtube.com/watch?v=demo"],
            "niche": ["BUSINESS"],
            "lang": ["FR"],
            "prompt_generated": [True],
        }
    )
    debug_head(run_generator(sample_df), "generator self-test")
