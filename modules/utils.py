"""Utility helpers for CSV I/O, directories, and debug display."""

from pathlib import Path
import pandas as pd


def get_project_root() -> Path:
    """Return project root from modules package location."""
    return Path(__file__).resolve().parent.parent


def ensure_dir(path: Path) -> Path:
    """Create directory (parents included) if missing and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_csv_safe(csv_path: Path) -> pd.DataFrame:
    """Read CSV safely and return an empty DataFrame on recoverable errors."""
    try:
        if not csv_path.exists():
            print(f"[utils] CSV missing: {csv_path}")
            return pd.DataFrame()
        return pd.read_csv(csv_path)
    except Exception as exc:  # noqa: BLE001
        print(f"[utils] Failed reading CSV {csv_path}: {exc}")
        return pd.DataFrame()


def save_csv_safe(df: pd.DataFrame, csv_path: Path, index: bool = False) -> Path:
    """Save a DataFrame to CSV while ensuring parent directory exists."""
    try:
        ensure_dir(csv_path.parent)
        df.to_csv(csv_path, index=index, encoding="utf-8")
        print(f"[utils] CSV saved: {csv_path} ({len(df)} rows)")
        return csv_path
    except Exception as exc:  # noqa: BLE001
        print(f"[utils] Failed writing CSV {csv_path}: {exc}")
        raise


def debug_head(df: pd.DataFrame, title: str, n: int = 5) -> None:
    """Print a debug title and DataFrame head."""
    print(f"\n[debug] {title} | rows={len(df)}")
    if df.empty:
        print("[debug] DataFrame is empty")
        return
    print(df.head(n).to_string(index=False))


if __name__ == "__main__":
    root = get_project_root()
    print(f"[utils] Project root: {root}")
    sample = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    debug_head(sample, "utils self-test")
