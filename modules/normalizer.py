"""Normalize source rows into a canonical content schema."""

import pandas as pd

from modules.utils import debug_head


PLATFORM_ENUM = {"youtube": "YOUTUBE", "tiktok": "TIKTOK", "facebook": "FACEBOOK"}


def resolve_content_url(df: pd.DataFrame) -> pd.DataFrame:
    """Create content_url from source_url/link/url (priority order)."""
    out = df.copy()
    if "source_url" in out.columns:
        out["content_url"] = out["source_url"]
    elif "link" in out.columns:
        out["content_url"] = out["link"]
    elif "url" in out.columns:
        out["content_url"] = out["url"]
    else:
        raise ValueError("No URL column found among source_url/link/url")
    return out


def normalize_text_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize text fields to clean, stripped strings."""
    out = df.copy()
    for column in ["niche", "usage_strategy", "lang", "rights", "origin_platform", "notes"]:
        if column not in out.columns:
            out[column] = ""
        out[column] = out[column].fillna("").astype(str).str.strip()
    return out


def normalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Build canonical columns required by downstream modules."""
    out = resolve_content_url(df)
    out = normalize_text_fields(out)

    out["content_url"] = out["content_url"].fillna("").astype(str).str.strip()
    out["source_url"] = out.get("source_url", out["content_url"]).replace("", pd.NA).fillna(out["content_url"])
    out["lang"] = out["lang"].replace("", "FR").str.upper()
    out["niche"] = out["niche"].replace("", "MOTIVATION").str.upper()
    out["usage_strategy"] = out["usage_strategy"].replace("", "viral").str.lower()
    out["rights"] = out["rights"].replace("", "REWRITE_REQUIRED").str.upper()

    if "raw_text" not in out.columns:
        out["raw_text"] = "Source from " + out["origin_platform"].replace("", "UNKNOWN")

    return out


def run_normalizer(df: pd.DataFrame) -> pd.DataFrame:
    """Pipeline-facing normalization wrapper."""
    print("[normalizer] Normalizing records")
    if df.empty:
        print("[normalizer] Empty input DataFrame")
        return df
    try:
        out = normalize_schema(df)
    except Exception as exc:  # noqa: BLE001
        print(f"[normalizer] Failed: {exc}")
        raise

    debug_head(out, "normalizer output")
    return out


if __name__ == "__main__":
    sample = pd.DataFrame(
        {
            "source_url": ["https://youtube.com/watch?v=1", "https://tiktok.com/@user/video/2"],
            "niche": ["motivation", ""],
            "lang": ["fr", None],
        }
    )
    result = run_normalizer(sample)
    debug_head(result, "normalizer self-test")
