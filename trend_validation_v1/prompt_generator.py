"""Prompt/suggestion generator for Trend Validation v1.

The output structure is intentionally simple for beginner creators and future UI use.
"""

from __future__ import annotations


def build_prompt_suggestions(
    niche: str,
    lang: str,
    decision: str,
    title_seed: str,
    caption_seed: str,
) -> dict:
    """Generate compact adaptation suggestions from candidate metadata."""
    decision = (decision or "ADAPT").upper()
    niche = (niche or "MOTIVATION").upper()
    lang = (lang or "FR").upper()

    hook = (
        f"{title_seed}" if title_seed else f"Hook direct orienté résultat ({niche})."
    )
    angle = {
        "POST": "Publier rapidement avec un angle pratique et une promesse claire.",
        "ADAPT": "Adapter le format avec exemple concret et CTA plus fort.",
        "AVOID": "Éviter tel quel; reformuler autour d’un sous-angle moins saturé.",
    }.get(decision, "Adapter le sujet selon votre audience cible.")

    script_outline = (
        f"1) Hook 3s ({lang})\n"
        "2) Problème fréquent\n"
        "3) 2 actions concrètes\n"
        "4) CTA commentaire/partage"
    )

    base = title_seed or caption_seed or f"Idée {niche}"
    titles = [
        f"{base} | Version simple",
        f"{base} | Version preuve sociale",
    ]

    return {
        "hook": hook,
        "angle": angle,
        "script_outline": script_outline,
        "titles": titles,
    }
