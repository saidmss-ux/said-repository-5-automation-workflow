"""Normalize source rows into a canonical content schema."""

import pandas as pd

from modules.utils import debug_head


URL_COLUMN_PRIORITY = ["source_url", "link", "url"]


def resolve_content_url(df: pd.DataFrame) -> pd.DataFrame:
    """Create content_url from supported URL columns."""
    out = df.copy()
    source_col = next((column for column in URL_COLUMN_PRIORITY if column in out.columns), None)
    if source_col is None:
        raise ValueError("[normalizer] No URL column found among source_url/link/url")

    out["content_url"] = out[source_col].fillna("").astype(str).str.strip()
    if (out["content_url"] == "").all():
        raise ValueError("[normalizer] content_url is empty for all rows")
    return out


def normalize_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize text fields and apply defaults."""
    out = df.copy()
    defaults = {
        "niche": "MOTIVATION",
        "lang": "FR",
        "rights": "REWRITE_REQUIRED",
        "usage_strategy": "viral",
        "origin_platform": "UNKNOWN",
        "notes": "",
    }

    for column, default in defaults.items():
        if column not in out.columns:
            out[column] = default
        out[column] = out[column].fillna("").astype(str).str.strip()
        out[column] = out[column].replace("", default)

    out["niche"] = out["niche"].str.upper()
    out["lang"] = out["lang"].str.upper()
    out["rights"] = out["rights"].str.upper()
    out["usage_strategy"] = out["usage_strategy"].str.lower()
    return out


def run_normalizer(df: pd.DataFrame) -> pd.DataFrame:
    """Run normalizer stage and print debug preview."""
    print("[normalizer] Normalizing source rows")
    out = resolve_content_url(df)
    out = normalize_text_columns(out)

    if "source_url" not in out.columns:
        out["source_url"] = out["content_url"]
    if "raw_text" not in out.columns:
        out["raw_text"] = "Source from " + out["content_url"]

    debug_head(out, "normalizer output")
    return out


if __name__ == "__main__":
    sample_df = pd.DataFrame(
        {
            "source_url": ["https://youtube.com/watch?v=1", "https://tiktok.com/@x/video/2"],
            "niche": ["business", ""],
            "lang": ["fr", "en"],
            "rights": ["", "inspire_only"],
            "usage_strategy": ["viral", "education"],
        }
    )
    result_df = run_normalizer(sample_df)
    debug_head(result_df, "normalizer self-test")
