"""Deterministic classification logic with manual scoring support."""

import re
import pandas as pd

from modules.utils import debug_head


def infer_origin_platform(content_url: str) -> str:
    """Infer platform enum from URL."""
    url = (content_url or "").lower()
    if "youtube" in url or "youtu.be" in url:
        return "YOUTUBE"
    if "tiktok" in url:
        return "TIKTOK"
    if "facebook" in url or "fb.watch" in url:
        return "FACEBOOK"
    return "OTHER"


def normalize_rights(rights: str | None) -> str:
    """Normalize rights into allowed enum values."""
    mapping = {
        "FREE_REPOST": "FREE_REPOST",
        "REWRITE_REQUIRED": "REWRITE_REQUIRED",
        "INSPIRE_ONLY": "INSPIRE_ONLY",
        "AVOID": "AVOID",
    }
    return mapping.get((rights or "").strip().upper(), "REWRITE_REQUIRED")


def normalize_strategy(usage_strategy: str | None) -> str:
    """Normalize strategy into allowed values."""
    allowed = {"viral", "education", "inspiration"}
    strategy = (usage_strategy or "").strip().lower()
    return strategy if strategy in allowed else "viral"


def infer_niche(niche: str | None, raw_text: str | None) -> str:
    """Infer niche from explicit value or raw text keywords."""
    explicit = (niche or "").strip().upper()
    if explicit:
        return explicit

    text = (raw_text or "").lower()
    if re.search(r"business|money|entrepreneur", text):
        return "BUSINESS"
    if re.search(r"health|fitness|wellness", text):
        return "HEALTH"
    if re.search(r"story|emotion|histoire", text):
        return "STORY"
    if re.search(r"education|learn|tutorial", text):
        return "EDUCATION"
    return "MOTIVATION"


def compute_priority_score(row: pd.Series) -> int:
    """Compute deterministic priority score between 0 and 100."""
    score = 30
    if row.get("niche") in {"MOTIVATION", "BUSINESS"}:
        score += 25
    if row.get("lang") == "FR":
        score += 20
    if row.get("rights") == "FREE_REPOST":
        score += 20
    elif row.get("rights") == "REWRITE_REQUIRED":
        score += 10
    elif row.get("rights") == "INSPIRE_ONLY":
        score += 5
    else:
        score -= 30
    return max(0, min(score, 100))


def add_manual_scoring_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add manual scoring and reviewer columns if missing."""
    out = df.copy()
    if "manual_score" not in out.columns:
        out["manual_score"] = ""
    if "reviewer_decision" not in out.columns:
        out["reviewer_decision"] = "PENDING"
    if "reviewer_notes" not in out.columns:
        out["reviewer_notes"] = ""

    manual_values = pd.to_numeric(out["manual_score"], errors="coerce")
    out["manual_priority_score"] = manual_values.fillna(out["priority_score"]).astype(int)
    return out


def compute_blended_score(row: pd.Series) -> int:
    """Blend automated and manual scores for final ranking."""
    auto_score = int(row.get("priority_score", 0))
    manual_score = int(row.get("manual_priority_score", auto_score))
    blended = int((auto_score * 0.6) + (manual_score * 0.4))
    return max(0, min(blended, 100))


def run_classifier(df: pd.DataFrame) -> pd.DataFrame:
    """Run classifier stage and print debug preview."""
    print("[classifier] Running deterministic classification")
    out = df.copy()

    def _resolve_platform(row: pd.Series) -> str:
        explicit = str(row.get("origin_platform", "")).strip().upper()
        if explicit and explicit != "UNKNOWN":
            return explicit
        return infer_origin_platform(row.get("content_url", ""))

    out["origin_platform"] = out.apply(_resolve_platform, axis=1)
    out["rights"] = out["rights"].apply(normalize_rights)
    out["usage_strategy"] = out["usage_strategy"].apply(normalize_strategy)
    out["niche"] = out.apply(
        lambda row: infer_niche(row.get("niche"), row.get("raw_text")), axis=1
    )
    out["priority_score"] = out.apply(compute_priority_score, axis=1)
    out = add_manual_scoring_columns(out)
    out["blended_priority_score"] = out.apply(compute_blended_score, axis=1)

    out["status"] = out["rights"].apply(
        lambda value: "FILTERED" if value == "AVOID" else "READY_TO_GENERATE"
    )

    debug_head(out, "classifier output")
    return out


if __name__ == "__main__":
    sample_df = pd.DataFrame(
        {
            "content_url": ["https://youtube.com/watch?v=1", "https://example.com/a"],
            "niche": ["", ""],
            "lang": ["FR", "EN"],
            "rights": ["", "INSPIRE_ONLY"],
            "usage_strategy": ["viral", "education"],
            "raw_text": ["business tips", "story emotion"],
            "origin_platform": ["", ""],
            "manual_score": [90, ""],
        }
    )
    debug_head(run_classifier(sample_df), "classifier self-test")
