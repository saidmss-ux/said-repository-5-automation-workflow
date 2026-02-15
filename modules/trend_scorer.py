"""Trend scoring module for ranking source rows before prompt generation."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re

import pandas as pd


REQUIRED_COLUMNS = ["source_url", "niche", "lang", "rights", "usage_strategy"]


def load_sources(csv_path: Path) -> pd.DataFrame:
    """Load source CSV with required-column validation."""
    if not csv_path.exists():
        raise FileNotFoundError(f"[trend_scorer] Input CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"[trend_scorer] Missing required columns: {missing}")

    print(f"[trend_scorer] Loaded {len(df)} rows from {csv_path}")
    return df


def _safe_parse_publication_date(value: object) -> pd.Timestamp | pd.NaT:
    """Parse potentially heterogeneous date value into timestamp."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NaT
    parsed = pd.to_datetime(str(value), errors="coerce", utc=True)
    return parsed


def compute_recency_score(df: pd.DataFrame) -> pd.Series:
    """Compute recency score in [0,1] using publication date if available."""
    date_col = None
    for candidate in ["publication_date", "published_at", "date"]:
        if candidate in df.columns:
            date_col = candidate
            break

    if date_col is None:
        print("[trend_scorer] No date column found, using neutral recency score")
        return pd.Series([0.5] * len(df), index=df.index, dtype=float)

    parsed_dates = df[date_col].apply(_safe_parse_publication_date)
    now = pd.Timestamp(datetime.now(timezone.utc))
    age_days = (now - parsed_dates).dt.total_seconds() / 86400.0

    valid_age = age_days.dropna()
    if valid_age.empty:
        print("[trend_scorer] Date parse failed for all rows, using neutral recency score")
        return pd.Series([0.5] * len(df), index=df.index, dtype=float)

    # Lower age means more recent => higher score
    max_age = max(float(valid_age.max()), 1.0)
    recency = 1.0 - (age_days / max_age)
    recency = recency.clip(lower=0.0, upper=1.0).fillna(0.5)
    return recency.astype(float)


def _extract_keywords(text: str) -> list[str]:
    """Extract normalized keywords from text."""
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "youtube",
        "watch",
        "video",
        "www",
        "com",
        "https",
        "http",
    }
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [token for token in tokens if len(token) > 2 and token not in stopwords]


def _row_keyword_text(row: pd.Series) -> str:
    """Build keyword extraction text from available columns."""
    title = str(row.get("title", "") or "")
    notes = str(row.get("notes", "") or "")
    source_url = str(row.get("source_url", "") or "")
    niche = str(row.get("niche", "") or "")
    return " ".join([title, notes, source_url, niche]).strip()


def compute_keyword_frequency_score(df: pd.DataFrame) -> pd.Series:
    """Compute score based on dominant keyword frequency across dataset."""
    all_keywords: list[str] = []
    row_keywords: list[list[str]] = []

    for _, row in df.iterrows():
        keywords = _extract_keywords(_row_keyword_text(row))
        row_keywords.append(keywords)
        all_keywords.extend(keywords)

    if not all_keywords:
        print("[trend_scorer] No keywords extracted, using neutral frequency score")
        return pd.Series([0.5] * len(df), index=df.index, dtype=float)

    counter = Counter(all_keywords)
    max_count = max(counter.values())

    scores: list[float] = []
    for keywords in row_keywords:
        if not keywords:
            scores.append(0.5)
            continue
        dominant = max(counter[keyword] for keyword in keywords)
        scores.append(float(dominant / max_count))

    return pd.Series(scores, index=df.index, dtype=float).clip(0.0, 1.0)


def compute_multi_source_score(df: pd.DataFrame) -> pd.Series:
    """Compute multi-source trend signal from repeated themes across rows."""
    themes: list[str] = []
    for _, row in df.iterrows():
        keywords = _extract_keywords(_row_keyword_text(row))
        if keywords:
            themes.append(keywords[0])
        else:
            themes.append(str(row.get("niche", "UNKNOWN") or "UNKNOWN").upper())

    counts = Counter(themes)
    max_count = max(counts.values()) if counts else 1

    scores = [float(counts[theme] / max_count) for theme in themes]
    return pd.Series(scores, index=df.index, dtype=float).clip(0.0, 1.0)


def _weighted_row_score(row: pd.Series) -> float:
    """Compute weighted score with dynamic redistribution if values missing."""
    base_weights = {
        "recency_score": 0.4,
        "frequency_score": 0.3,
        "multi_source_score": 0.3,
    }

    available = {
        key: float(row[key])
        for key in base_weights
        if key in row and pd.notna(row[key])
    }
    if not available:
        return 0.5

    total_weight = sum(base_weights[key] for key in available)
    weighted_sum = sum(available[key] * base_weights[key] for key in available)
    score = weighted_sum / total_weight if total_weight else 0.5
    return float(max(0.0, min(score, 1.0)))


def compute_trend_score(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all sub-scores and aggregated trend_score."""
    out = df.copy()

    out["recency_score"] = compute_recency_score(out)
    out["frequency_score"] = compute_keyword_frequency_score(out)
    out["multi_source_score"] = compute_multi_source_score(out)

    out["trend_score"] = out.apply(_weighted_row_score, axis=1)
    out["trend_score"] = out["trend_score"].astype(float).clip(0.0, 1.0)

    print("[trend_scorer] Computed trend scores")
    return out


def assign_priority_level(df: pd.DataFrame) -> pd.DataFrame:
    """Assign HIGH/MEDIUM/LOW according to trend_score thresholds."""
    out = df.copy()

    def to_priority(score: float) -> str:
        if score >= 0.65:
            return "HIGH"
        if score >= 0.40:
            return "MEDIUM"
        return "LOW"

    out["priority_level"] = out["trend_score"].astype(float).apply(to_priority)
    return out


def save_ranked_csv(df: pd.DataFrame, path: Path) -> Path:
    """Save ranked dataframe to CSV in UTF-8 encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"[trend_scorer] Saved ranked CSV: {path} ({len(df)} rows)")
    return path


def run_trend_scoring(input_csv: Path, output_csv: Path) -> Path:
    """Run complete trend scoring workflow and save ranked output."""
    df = load_sources(input_csv)
    scored = compute_trend_score(df)
    ranked = assign_priority_level(scored)
    save_ranked_csv(ranked, output_csv)
    return output_csv


def _debug_quick_checks(df: pd.DataFrame) -> None:
    """Print quick validation checks for local debugging."""
    print("\n[trend_scorer] head(5):")
    print(df.head(5).to_string(index=False))
    print(f"\n[trend_scorer] shape: {df.shape}")
    print("[trend_scorer] priority counts:")
    print(df["priority_level"].value_counts(dropna=False).to_string())


def main() -> None:
    """Local demo run for trend scoring module."""
    input_csv = Path("data/source/master_sources.csv")
    output_csv = Path("data/generated/ranked_sources.csv")

    output_path = run_trend_scoring(input_csv=input_csv, output_csv=output_csv)
    ranked_df = pd.read_csv(output_path)
    _debug_quick_checks(ranked_df)


if __name__ == "__main__":
    main()
