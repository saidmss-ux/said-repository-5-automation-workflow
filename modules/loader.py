"""Load source CSV records and enforce base schema."""

from pathlib import Path
import pandas as pd

from modules.utils import debug_head, read_csv_safe


DEFAULT_COLUMNS = [
    "source_url",
    "niche",
    "usage_strategy",
    "lang",
    "rights",
    "origin_platform",
    "prompt_template",
    "processed",
    "notes",
    "source_file",
]


def validate_required_columns(df: pd.DataFrame, required_cols: list[str]) -> pd.DataFrame:
    """Add missing required columns with empty default values."""
    out = df.copy()
    for column in required_cols:
        if column not in out.columns:
            out[column] = ""
    return out


def deduplicate_sources(df: pd.DataFrame, subset: list[str] | None = None) -> pd.DataFrame:
    """Drop duplicate source rows using subset keys."""
    dedupe_subset = subset or ["source_url"]
    if df.empty:
        return df
    return df.drop_duplicates(subset=dedupe_subset).reset_index(drop=True)


def load_master_sources(source_csv_path: Path) -> pd.DataFrame:
    """Load master source CSV and enrich with source_file column."""
    df = read_csv_safe(source_csv_path)
    if df.empty:
        return df
    if "source_file" not in df.columns:
        df["source_file"] = source_csv_path.name
    return df


def run_loader(source_csv_path: Path) -> pd.DataFrame:
    """Pipeline-facing loader orchestration."""
    print(f"[loader] Loading source file: {source_csv_path}")
    df = load_master_sources(source_csv_path)
    if df.empty:
        print("[loader] Aucun contenu trouvé")
        return df

    df = validate_required_columns(df, DEFAULT_COLUMNS)
    df = deduplicate_sources(df, subset=["source_url"])
    debug_head(df, "loader output")
    return df


if __name__ == "__main__":
    sample_path = Path("data/source/master_sources.csv")
    output = run_loader(sample_path)
    debug_head(output, "loader self-test")
