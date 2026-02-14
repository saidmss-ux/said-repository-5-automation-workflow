"""Validation checks for template aliases and generated CSV artifacts."""

from pathlib import Path
import csv
import json


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def check_template_alias_support(repo_root: Path) -> None:
    primary = repo_root / "prompts" / "prompt_templates.json"
    alias = repo_root / "prompts" / "prompt_template.json"

    if not primary.exists() or not alias.exists():
        raise FileNotFoundError("Missing template files for alias support check")

    primary_data = load_json(primary)
    alias_data = load_json(alias)
    if primary_data != alias_data:
        raise ValueError("Template alias file content does not match primary template")

    print("[check] Template alias support OK")


def check_generated_csv_outputs(repo_root: Path) -> None:
    ready_path = repo_root / "data" / "generated" / "ready_to_generate.csv"
    prompts_path = repo_root / "data" / "generated" / "prompts_ready.csv"

    with ready_path.open("r", encoding="utf-8", newline="") as file:
        ready_rows = list(csv.DictReader(file))

    with prompts_path.open("r", encoding="utf-8", newline="") as file:
        prompts_reader = csv.DictReader(file)
        prompts_rows = list(prompts_reader)
        prompt_columns = prompts_reader.fieldnames or []

    if len(ready_rows) != 10 or len(prompts_rows) != 10:
        raise ValueError("Generated CSV files must contain exactly 10 rows")

    if "final_prompt" not in prompt_columns:
        raise ValueError("prompts_ready.csv must include final_prompt column")

    print("[check] Generated CSV row/column constraints OK")
    print("[check] ready_to_generate head(5):")
    for row in ready_rows[:5]:
        print(row)

    print("[check] prompts_ready head(5):")
    for row in prompts_rows[:5]:
        print({"source_url": row.get("source_url"), "final_prompt": row.get("final_prompt", "")[:80]})


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    check_template_alias_support(repo_root)
    check_generated_csv_outputs(repo_root)


if __name__ == "__main__":
    main()
