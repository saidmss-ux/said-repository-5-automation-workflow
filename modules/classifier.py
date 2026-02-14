"""Deterministic classification rules for niche, language, rights, and priority."""

import re
import pandas as pd

from modules.utils import debug_head


def infer_origin_platform(content_url: str) -> str:
    """Infer origin platform enum from URL."""
    url = (content_url or "").lower()
    if "youtube" in url or "youtu.be" in url:
        return "YOUTUBE"
    if "tiktok" in url:
        return "TIKTOK"
    if "facebook" in url or "fb.watch" in url:
        return "FACEBOOK"
    return "OTHER"


def normalize_lang(lang: str | None) -> str:
    """Normalize language to FR/EN/OTHER with FR default."""
    value = (lang or "").strip().upper()
    if value in {"FR", "EN"}:
        return value
    if value == "":
        return "FR"
    return "OTHER"


def normalize_rights(rights: str | None) -> str:
    """Normalize rights values to allowed enum."""
    value = (rights or "").strip().upper()
    allowed = {"FREE_REPOST", "REWRITE_REQUIRED", "INSPIRE_ONLY", "AVOID"}
    if value in allowed:
        return value
    return "REWRITE_REQUIRED"


def normalize_usage_strategy(usage_strategy: str | None) -> str:
    """Normalize usage strategy with viral default."""
    value = (usage_strategy or "").strip().lower()
    allowed = {"viral", "education", "inspiration"}
    if value in allowed:
        return value
    return "viral"


def infer_niche(niche: str | None, raw_text: str | None) -> str:
    """Infer niche from explicit value or keyword matching."""
    explicit = (niche or "").strip().upper()
    if explicit:
        return explicit

    text = (raw_text or "").lower()
    if re.search(r"business|money|entrepreneur", text):
        return "BUSINESS"
    if re.search(r"health|fitness|wellness", text):
        return "HEALTH"
    if re.search(r"story|histoire|emotion", text):
        return "STORY"
    if re.search(r"learn|education|tutorial", text):
        return "EDUCATION"
    return "MOTIVATION"


def compute_priority_score(row: pd.Series) -> int:
    """Compute score (0-100) from niche/lang/rights."""
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


def run_classifier(df: pd.DataFrame) -> pd.DataFrame:
    """Apply deterministic classification rules."""
    print("[classifier] Classifying records")
    if df.empty:
        print("[classifier] Empty input DataFrame")
        return df

    out = df.copy()
    out["origin_platform"] = out.get("origin_platform", "").astype(str)
    out["origin_platform"] = out.apply(
        lambda row: row["origin_platform"].strip().upper() or infer_origin_platform(row.get("content_url", "")),
        axis=1,
    )
    out["lang"] = out["lang"].apply(normalize_lang)
    out["rights"] = out["rights"].apply(normalize_rights)
    out["usage_strategy"] = out["usage_strategy"].apply(normalize_usage_strategy)
    out["niche"] = out.apply(lambda row: infer_niche(row.get("niche", ""), row.get("raw_text", "")), axis=1)
    out["priority_score"] = out.apply(compute_priority_score, axis=1)

    out["status"] = out.apply(
        lambda row: "FILTERED" if row.get("rights") == "AVOID" else "READY_TO_GENERATE", axis=1
    )

    debug_head(out, "classifier output")
    return out


if __name__ == "__main__":
    sample = pd.DataFrame(
        {
            "content_url": ["https://youtube.com/watch?v=1", "https://example.com/post"],
            "niche": ["", ""],
            "lang": ["fr", "en"],
            "rights": ["", "INSPIRE_ONLY"],
            "usage_strategy": ["viral", "education"],
            "raw_text": ["business mindset tips", "story and emotion"],
            "origin_platform": ["", ""],
        }
    )
    result = run_classifier(sample)
    debug_head(result, "classifier self-test")
