"""Adapter layer for Trend Validation v1.

Aligned with SOT.md: this module only *reads* core pipeline artifacts and does not
mutate core files. It maps a user input (URL or keyword) to a single candidate row
from `data/generated/ready_to_generate.csv`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import pandas as pd


YOUTUBE_URL_RE = re.compile(
    r"^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_-]+"
)


@dataclass
class AdaptedCandidate:
    """Minimal candidate payload consumed by the v1 facade."""

    matched_by: str
    input_value: str
    content_url: str
    niche: str
    lang: str
    rights: str
    blended_priority_score: float
    prompt_quality_score: float
    status: str
    title_seed: str
    caption_seed: str


def detect_input_type(user_input: str) -> str:
    """Return `youtube_url` or `keyword` based on user input."""
    value = (user_input or "").strip()
    if not value:
        raise ValueError("[trend_v1.adapter] empty input is not allowed")
    return "youtube_url" if YOUTUBE_URL_RE.match(value) else "keyword"


def load_ready_dataframe(ready_csv: Path) -> pd.DataFrame:
    """Load ready_to_generate artifact with explicit UTF-8 contract."""
    if not ready_csv.exists():
        raise FileNotFoundError(f"[trend_v1.adapter] missing file: {ready_csv}")

    df = pd.read_csv(ready_csv, encoding="utf-8")
    required_cols = {
        "source_url",
        "content_url",
        "niche",
        "lang",
        "rights",
        "blended_priority_score",
        "status",
    }
    missing = sorted(required_cols - set(df.columns))
    if missing:
        raise ValueError(f"[trend_v1.adapter] missing required columns: {missing}")
    return df


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return default


def _select_best_row(df: pd.DataFrame, user_input: str, input_type: str) -> pd.Series:
    """Select the best matching row for URL or keyword mode."""
    if input_type == "youtube_url":
        mask = (
            df["content_url"].fillna("").astype(str).str.strip() == user_input.strip()
        ) | (df["source_url"].fillna("").astype(str).str.strip() == user_input.strip())
        subset = df[mask].copy()
    else:
        needle = user_input.strip().lower()
        haystack_cols = [
            col
            for col in ["title_seed", "caption_seed", "niche", "notes", "content_url"]
            if col in df.columns
        ]
        if not haystack_cols:
            subset = df.copy()
        else:
            subset = df.copy()
            subset["_search_blob"] = ""
            for col in haystack_cols:
                subset["_search_blob"] = (
                    subset["_search_blob"] + " " + subset[col].fillna("").astype(str)
                )
            subset = subset[
                subset["_search_blob"].str.lower().str.contains(needle, regex=False)
            ]

    if subset.empty:
        raise LookupError(f"[trend_v1.adapter] no match found for input='{user_input}'")

    ranked = subset.sort_values(by=["blended_priority_score"], ascending=False)
    return ranked.iloc[0]


def adapt_input_to_candidate(user_input: str, ready_csv: Path) -> AdaptedCandidate:
    """Resolve input to one candidate row from stable core artifacts."""
    input_type = detect_input_type(user_input)
    df = load_ready_dataframe(ready_csv)
    row = _select_best_row(df, user_input=user_input, input_type=input_type)

    return AdaptedCandidate(
        matched_by=input_type,
        input_value=user_input,
        content_url=str(row.get("content_url", row.get("source_url", ""))),
        niche=str(row.get("niche", "MOTIVATION")),
        lang=str(row.get("lang", "FR")),
        rights=str(row.get("rights", "REWRITE_REQUIRED")),
        blended_priority_score=_safe_float(row.get("blended_priority_score", 0.0)),
        prompt_quality_score=_safe_float(row.get("prompt_quality_score", 0.0)),
        status=str(row.get("status", "RAW")),
        title_seed=str(row.get("title_seed", "")),
        caption_seed=str(row.get("caption_seed", "")),
    )
