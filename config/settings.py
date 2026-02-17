"""Global settings and canonical paths for the content automation pipeline."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SOURCE_DIR = DATA_DIR / "source"
GENERATED_DIR = DATA_DIR / "generated"

MASTER_SOURCES_CSV = SOURCE_DIR / "master_sources.csv"
READY_TO_GENERATE_CSV = GENERATED_DIR / "ready_to_generate.csv"
PROMPTS_READY_CSV = GENERATED_DIR / "prompts_ready.csv"

PROMPT_TEMPLATES_JSON = PROJECT_ROOT / "prompts" / "prompt_templates.json"
