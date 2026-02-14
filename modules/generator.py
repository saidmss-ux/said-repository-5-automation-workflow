"""Prepare generation-ready fields for external AI tools."""

import pandas as pd

from modules.utils import debug_head


def prepare_generation_payload(row: pd.Series) -> dict:
    """Create generation seed payload for one content row."""
    content_url = row.get("content_url", "")
    niche = row.get("niche", "MOTIVATION")
    lang = row.get("lang", "FR")

    title_seed = f"[{niche}] Hook idea from {content_url}"
    caption_seed = f"{niche.title()} | {lang} | Source: {content_url}"
    raw_text = row.get("raw_text", f"Source content collected from {content_url}")

    return {
        "title_seed": title_seed,
        "caption_seed": caption_seed,
        "raw_text": raw_text,
    }


def build_generation_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add generation helper columns to dataframe."""
    if df.empty:
        return df

    out = df.copy()
    payloads = out.apply(prepare_generation_payload, axis=1)
    out["title_seed"] = payloads.apply(lambda payload: payload["title_seed"])
    out["caption_seed"] = payloads.apply(lambda payload: payload["caption_seed"])
    out["raw_text"] = payloads.apply(lambda payload: payload["raw_text"])

    if "content_ready" not in out.columns:
        out["content_ready"] = out.get("prompt_generated", False)

    return out


def run_generator(df: pd.DataFrame) -> pd.DataFrame:
    """Pipeline-facing generator wrapper."""
    print("[generator] Preparing generation payload")
    if df.empty:
        print("[generator] Empty input DataFrame")
        return df

    try:
        out = build_generation_columns(df)
    except Exception as exc:  # noqa: BLE001
        print(f"[generator] Failed: {exc}")
        raise

    debug_head(out, "generator output")
    return out


if __name__ == "__main__":
    sample = pd.DataFrame(
        {
            "content_url": ["https://example.com/video"],
            "niche": ["BUSINESS"],
            "lang": ["FR"],
            "prompt_generated": [True],
        }
    )
    result = run_generator(sample)
    debug_head(result, "generator self-test")
