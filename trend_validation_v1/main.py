"""CLI entrypoint for Trend Validation v1 facade.

SOT alignment:
- Reads stable artifacts from core pipeline
- No writes to core pipeline outputs
- Stateless execution and JSON response
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from trend_validation_v1.adapter import adapt_input_to_candidate
from trend_validation_v1.prompt_generator import build_prompt_suggestions
from trend_validation_v1.star_scorer import score_candidate


DEFAULT_READY_CSV = Path("data/generated/ready_to_generate.csv")


def run(user_input: str, ready_csv: Path) -> dict:
    """Run facade pipeline: adapter -> scorer -> suggestions."""
    candidate = adapt_input_to_candidate(user_input=user_input, ready_csv=ready_csv)
    scored = score_candidate(
        blended_priority_score=candidate.blended_priority_score,
        prompt_quality_score=candidate.prompt_quality_score,
        rights=candidate.rights,
    )
    suggestions = build_prompt_suggestions(
        niche=candidate.niche,
        lang=candidate.lang,
        decision=scored.decision,
        title_seed=candidate.title_seed,
        caption_seed=candidate.caption_seed,
    )

    return {
        "stars": scored.stars,
        "decision": scored.decision,
        "metrics": scored.metrics,
        "explanation": scored.explanation,
        "prompt_suggestions": suggestions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Trend Validation v1 facade")
    parser.add_argument("--input", required=True, help="YouTube URL or keyword")
    parser.add_argument(
        "--ready-csv",
        default=str(DEFAULT_READY_CSV),
        help="Path to ready_to_generate.csv",
    )
    args = parser.parse_args()

    output = run(user_input=args.input, ready_csv=Path(args.ready_csv))
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
