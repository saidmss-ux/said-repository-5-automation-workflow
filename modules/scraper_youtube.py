"""Backward-compatible wrapper for legacy module name.

Use `modules/youtube_scrap.py` as the canonical implementation.
"""

from modules.youtube_scrap import *  # noqa: F401,F403


if __name__ == "__main__":
    main()
