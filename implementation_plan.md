# Implementation Plan (aligned with SOT.md / SKILL.md)

## Objective
Deliver and maintain the stable V1+ pipeline:
`loader -> normalizer -> classifier -> prompt_builder -> generator -> export`

## Phases

### Phase 1 — Input contract hardening
1. Validate `data/source/master_sources.csv` existence and minimal columns.
2. Deduplicate by `source_url`.
3. Normalize text + enum fields and canonical `content_url`.

### Phase 2 — Classification and scoring
1. Infer/normalize `origin_platform`, `niche`, `rights`, `usage_strategy`.
2. Compute `priority_score` + manual blend (`manual_priority_score`, `blended_priority_score`).
3. Control status values (`RAW`, `FILTERED`, `READY_TO_GENERATE`, `GENERATED`, `PUBLISHED`).

### Phase 3 — Prompt construction
1. Validate template file and alias consistency.
2. Build `final_prompt` with metadata injection.
3. Add prompt quality flags/scores.

### Phase 4 — Generator and export
1. Build AI-ready payload fields.
2. Export `ready_to_generate.csv` and `prompts_ready.csv` in UTF-8.
3. Print `head(5)` previews for quick human verification.

### Phase 5 — Validation gates (required)
1. `python -m py_compile ...`
2. `python scripts/validate_artifacts.py`
3. `python master_pipeline.py`

## Acceptance Criteria
- Template alias parity verified.
- Generated artifacts exist and contain the expected demo rows.
- Prompt outputs include non-empty `final_prompt` for eligible rows.
- Scoring columns exist (`priority_score`, `blended_priority_score`).
- Debug logs + `head(5)` previews are visible.
