"""Load source CSV records and enforce base schema."""

from pathlib import Path
import pandas as pd

from modules.utils import debug_head, read_csv_strict


REQUIRED_SOURCE_COLUMNS = ["source_url", "niche", "lang", "rights", "usage_strategy"]
OPTIONAL_COLUMNS = ["origin_platform", "prompt_template", "processed", "notes", "source_file"]


def enforce_source_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure optional columns exist with safe defaults."""
    out = df.copy()
    defaults = {
        "origin_platform": "",
        "prompt_template": "default",
        "processed": False,
        "notes": "",
        "source_file": "master_sources.csv",
    }
    for column in OPTIONAL_COLUMNS:
        if column not in out.columns:
            out[column] = defaults[column]
    return out


def drop_duplicate_sources(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate rows based on source_url."""
    return df.drop_duplicates(subset=["source_url"]).reset_index(drop=True)


def load_master_sources(source_csv: Path) -> pd.DataFrame:
    """Load master source CSV with strict validation."""
    df = read_csv_strict(source_csv, required_columns=REQUIRED_SOURCE_COLUMNS)
    return enforce_source_schema(df)


def run_loader(source_csv: Path) -> pd.DataFrame:
    """Run loader stage and print debug preview."""
    print(f"[loader] Loading source CSV: {source_csv}")
    df = load_master_sources(source_csv)
    df = drop_duplicate_sources(df)
    debug_head(df, "loader output")
    return df


if __name__ == "__main__":
    output_df = run_loader(Path("data/source/master_sources.csv"))
    debug_head(output_df, "loader self-test")
