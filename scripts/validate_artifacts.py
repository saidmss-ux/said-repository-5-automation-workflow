"""Validation checks for template aliases and generated CSV artifacts."""

from pathlib import Path
import csv
import json


def load_json(path: Path) -> dict:
    """Load JSON file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def check_template_alias_support(repo_root: Path) -> None:
    """Check both template filenames exist and share same content."""
    primary = repo_root / "prompts" / "prompt_templates.json"
    alias = repo_root / "prompts" / "prompt_template.json"

    if not primary.exists() or not alias.exists():
        raise FileNotFoundError("Missing template files for alias support check")

    if load_json(primary) != load_json(alias):
        raise ValueError("Template alias file content does not match primary template")

    print("[check] Template alias support OK")


def check_generated_csv_outputs(repo_root: Path) -> None:
    """Check generated CSV constraints and print head(5)."""
    ready_path = repo_root / "data" / "generated" / "ready_to_generate.csv"
    prompts_path = repo_root / "data" / "generated" / "prompts_ready.csv"

    with ready_path.open("r", encoding="utf-8", newline="") as file:
        ready_reader = csv.DictReader(file)
        ready_rows = list(ready_reader)
        ready_columns = ready_reader.fieldnames or []

    with prompts_path.open("r", encoding="utf-8", newline="") as file:
        prompts_reader = csv.DictReader(file)
        prompts_rows = list(prompts_reader)
        prompt_columns = prompts_reader.fieldnames or []

    if len(ready_rows) != 10 or len(prompts_rows) != 10:
        raise ValueError("Generated CSV files must contain exactly 10 rows")

    required_ready = {
        "manual_score",
        "manual_priority_score",
        "blended_priority_score",
        "reviewer_decision",
        "prompt_quality_score",
        "ai_status",
    }
    missing_ready = [col for col in required_ready if col not in ready_columns]
    if missing_ready:
        raise ValueError(f"ready_to_generate.csv missing required columns: {missing_ready}")

    required_prompts = {"final_prompt", "prompt_quality_flags", "ai_enhancement_payload"}
    missing_prompt_cols = [col for col in required_prompts if col not in prompt_columns]
    if missing_prompt_cols:
        raise ValueError(f"prompts_ready.csv missing required columns: {missing_prompt_cols}")

    print("[check] Generated CSV row/column constraints OK")
    print("[check] ready_to_generate head(5):")
    for row in ready_rows[:5]:
        print(row)

    print("[check] prompts_ready head(5):")
    for row in prompts_rows[:5]:
        print(
            {
                "source_url": row.get("source_url"),
                "blended_priority_score": row.get("blended_priority_score"),
                "final_prompt": row.get("final_prompt", "")[:80],
            }
        )




def check_master_sources_csv_contract(repo_root: Path) -> None:
    """Check strict CSV contract for YouTube scraping bridge file."""
    source_path = repo_root / "data" / "source" / "master_sources.csv"
    required = [
        "source_url",
        "niche",
        "lang",
        "rights",
        "usage_strategy",
        "origin_platform",
    ]

    with source_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        cols = reader.fieldnames or []

    missing = [col for col in required if col not in cols]
    if missing:
        raise ValueError(f"master_sources.csv missing required columns: {missing}")

    print("[check] master_sources.csv contract OK")
    print("[check] master_sources head(5):")
    for row in rows[:5]:
        print({k: row.get(k, "") for k in required})

def main() -> None:
    """Run all artifact checks."""
    repo_root = Path(__file__).resolve().parent.parent
    check_template_alias_support(repo_root)
    check_generated_csv_outputs(repo_root)
    check_master_sources_csv_contract(repo_root)


if __name__ == "__main__":
    main()
