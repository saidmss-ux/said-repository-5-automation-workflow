"""Configuration for YouTube provider.

Environment variables supported:
- YOUTUBE_API_KEY
- YOUTUBE_MAX_RESULTS_PER_QUERY
- YOUTUBE_MAX_PAGES
- YOUTUBE_VIDEOS_PART
- YOUTUBE_SEARCH_PART
- YOUTUBE_CACHE_TTL_SECONDS
"""

from __future__ import annotations

import os


YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# Quota-sensitive defaults.
YOUTUBE_MAX_RESULTS_PER_QUERY = int(os.getenv("YOUTUBE_MAX_RESULTS_PER_QUERY", "30"))
YOUTUBE_MAX_PAGES = int(os.getenv("YOUTUBE_MAX_PAGES", "3"))

# Use minimal parts to reduce payload size.
YOUTUBE_SEARCH_PART = os.getenv("YOUTUBE_SEARCH_PART", "id")
YOUTUBE_VIDEOS_PART = os.getenv("YOUTUBE_VIDEOS_PART", "snippet,statistics")

# Simple in-memory cache TTL (seconds).
YOUTUBE_CACHE_TTL_SECONDS = int(os.getenv("YOUTUBE_CACHE_TTL_SECONDS", "900"))
