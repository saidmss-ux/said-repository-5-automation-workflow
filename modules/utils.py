"""Utility helpers for strict CSV/JSON I/O, directories, and debug display."""

from pathlib import Path
import json
import pandas as pd


def get_project_root() -> Path:
    """Return project root from modules package location."""
    return Path(__file__).resolve().parent.parent


def ensure_dir(path: Path) -> Path:
    """Create directory (parents included) if missing and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_csv_strict(csv_path: Path, required_columns: list[str] | None = None) -> pd.DataFrame:
    """Read CSV or raise explicit errors for missing/bad files."""
    if not csv_path.exists():
        raise FileNotFoundError(f"[utils] CSV file not found: {csv_path}")

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"[utils] Invalid CSV format at {csv_path}: {exc}") from exc

    if required_columns:
        missing = [column for column in required_columns if column not in df.columns]
        if missing:
            raise ValueError(f"[utils] Missing required CSV columns {missing} in {csv_path}")

    return df


def write_csv(df: pd.DataFrame, csv_path: Path, index: bool = False) -> Path:
    """Write DataFrame to CSV after ensuring parent directory exists."""
    ensure_dir(csv_path.parent)
    df.to_csv(csv_path, index=index, encoding="utf-8")
    print(f"[utils] CSV saved: {csv_path} ({len(df)} rows)")
    return csv_path


def read_json_strict(json_path: Path) -> dict:
    """Read JSON or raise explicit errors for missing/bad files."""
    if not json_path.exists():
        raise FileNotFoundError(f"[utils] JSON file not found: {json_path}")

    try:
        with json_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"[utils] Invalid JSON format at {json_path}: {exc}") from exc


def debug_head(df: pd.DataFrame, title: str, n: int = 5) -> None:
    """Print debug title and DataFrame head(n)."""
    print(f"\n[debug] {title} | rows={len(df)}")
    if df.empty:
        print("[debug] DataFrame is empty")
        return
    print(df.head(n).to_string(index=False))


if __name__ == "__main__":
    sample = pd.DataFrame({"col_a": [1, 2, 3], "col_b": ["a", "b", "c"]})
    debug_head(sample, "utils self-test")
