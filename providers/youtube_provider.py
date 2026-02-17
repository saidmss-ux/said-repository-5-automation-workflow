"""YouTube provider for master_source architecture.

Architecture goals:
- Standalone provider (no CSV export side effects).
- Single entrypoint: fetch_youtube_data(queries: list[str]) -> list[dict].
- Quota-aware strategy:
  1) Use search.list only to collect video IDs (expensive endpoint).
  2) Batch details via videos.list with up to 50 IDs/call (cheap endpoint).
  3) Cache responses to avoid repeated calls for same queries.

Master-source normalized output schema per item:
{
  "platform": "youtube",
  "id": "<videoId>",
  "title": "<title>",
  "channel": "<channelTitle>",
  "views": <int>,
  "published_at": "<ISO8601>",
  "source_extra": {...}
}
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
import time

from config.youtube_config import (
    YOUTUBE_API_KEY,
    YOUTUBE_CACHE_TTL_SECONDS,
    YOUTUBE_MAX_PAGES,
    YOUTUBE_MAX_RESULTS_PER_QUERY,
    YOUTUBE_SEARCH_PART,
    YOUTUBE_VIDEOS_PART,
)

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except Exception:  # noqa: BLE001
    build = None

    class HttpError(Exception):
        """Fallback HttpError when googleapiclient is unavailable."""


@dataclass
class YouTubeProviderConfig:
    """Runtime configuration for YouTube provider."""

    api_key: str = YOUTUBE_API_KEY
    max_results_per_query: int = YOUTUBE_MAX_RESULTS_PER_QUERY
    max_pages: int = YOUTUBE_MAX_PAGES
    search_part: str = YOUTUBE_SEARCH_PART
    videos_part: str = YOUTUBE_VIDEOS_PART
    cache_ttl_seconds: int = YOUTUBE_CACHE_TTL_SECONDS


class MemoryCache:
    """Minimal in-memory cache with TTL support."""

    def __init__(self, ttl_seconds: int = 900) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None

        timestamp, value = item
        if (time.time() - timestamp) > self.ttl_seconds:
            self._store.pop(key, None)
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)


class YouTubeQuotaExceededError(RuntimeError):
    """Raised when YouTube API quota is exceeded."""


class YouTubeApiClient:
    """Encapsulated client for YouTube Data API v3 operations."""

    def __init__(
        self,
        config: YouTubeProviderConfig,
        cache: MemoryCache | None = None,
        service: Any | None = None,
    ) -> None:
        self.config = config
        self.cache = cache or MemoryCache(ttl_seconds=config.cache_ttl_seconds)
        self.service = service or self._build_service()

    def _build_service(self) -> Any:
        if not self.config.api_key:
            raise ValueError("[youtube_provider] Missing API key for API mode")
        if build is None:
            raise ImportError(
                "[youtube_provider] googleapiclient is not installed. "
                "Install google-api-python-client to use API mode."
            )
        return build("youtube", "v3", developerKey=self.config.api_key)

    def _safe_execute(self, request: Any) -> dict:
        try:
            return request.execute()
        except HttpError as exc:
            message = str(exc)
            if "quotaExceeded" in message or "dailyLimitExceeded" in message:
                raise YouTubeQuotaExceededError(
                    "[youtube_provider] YouTube API quota exceeded"
                ) from exc
            raise RuntimeError(f"[youtube_provider] YouTube HTTP error: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"[youtube_provider] Unexpected API error: {exc}") from exc

    def search_video_ids(self, query: str) -> list[str]:
        """Get video IDs for a query using paginated search.list."""
        cache_key = f"search_ids::{query}::{self.config.max_results_per_query}::{self.config.max_pages}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            print(f"[youtube_provider] cache hit for query='{query}'")
            return cached

        collected: list[str] = []
        next_page_token = None
        remaining = self.config.max_results_per_query

        for _ in range(self.config.max_pages):
            if remaining <= 0:
                break

            page_size = min(50, remaining)
            request = self.service.search().list(
                part=self.config.search_part,
                q=query,
                type="video",
                maxResults=page_size,
                pageToken=next_page_token,
            )
            payload = self._safe_execute(request)

            for item in payload.get("items", []):
                video_id = item.get("id", {}).get("videoId")
                if video_id:
                    collected.append(video_id)

            remaining = self.config.max_results_per_query - len(collected)
            next_page_token = payload.get("nextPageToken")
            if not next_page_token:
                break

        unique_ids = list(dict.fromkeys(collected))
        self.cache.set(cache_key, unique_ids)
        print(
            "[youtube_provider] search collected "
            f"{len(unique_ids)} IDs for query='{query}'"
        )
        return unique_ids

    def fetch_videos_details(self, video_ids: list[str]) -> list[dict]:
        """Fetch detailed metadata for video IDs using batch videos.list calls."""
        if not video_ids:
            return []

        details: list[dict] = []
        for start in range(0, len(video_ids), 50):
            chunk = video_ids[start : start + 50]
            chunk_key = f"videos::{','.join(chunk)}::{self.config.videos_part}"
            cached = self.cache.get(chunk_key)
            if cached is not None:
                details.extend(cached)
                continue

            request = self.service.videos().list(
                part=self.config.videos_part,
                id=",".join(chunk),
                maxResults=len(chunk),
            )
            payload = self._safe_execute(request)
            items = payload.get("items", [])
            self.cache.set(chunk_key, items)
            details.extend(items)

        return details


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return 0


def normalize_youtube_item(item: dict) -> dict:
    """Normalize one YouTube API item to master_source schema."""
    snippet = item.get("snippet", {})
    statistics = item.get("statistics", {})

    return {
        "platform": "youtube",
        "id": item.get("id", ""),
        "title": snippet.get("title", ""),
        "channel": snippet.get("channelTitle", ""),
        "views": _safe_int(statistics.get("viewCount", 0)),
        "published_at": snippet.get("publishedAt", ""),
        "source_extra": {
            "description": snippet.get("description", ""),
            "tags": snippet.get("tags", []),
            "categoryId": snippet.get("categoryId", ""),
            "likeCount": _safe_int(statistics.get("likeCount", 0)),
            "commentCount": _safe_int(statistics.get("commentCount", 0)),
        },
    }


def validate_normalized_items(items: list[dict]) -> list[dict]:
    """Validate normalized output and drop malformed entries."""
    required = {"platform", "id", "title", "channel", "views", "published_at", "source_extra"}
    valid_items: list[dict] = []

    for item in items:
        if not required.issubset(item.keys()):
            continue
        if item.get("platform") != "youtube":
            continue
        if not item.get("id"):
            continue
        valid_items.append(item)

    return valid_items


def default_quality_filter(items: list[dict]) -> list[dict]:
    """Simple quality filter hook (can be replaced by caller)."""
    return [item for item in items if item.get("title")]


def default_scoring_hook(items: list[dict]) -> list[dict]:
    """No-op scoring hook for future extension."""
    return items


def fetch_youtube_data(
    queries: list[str],
    config: YouTubeProviderConfig | None = None,
    client: YouTubeApiClient | None = None,
    quality_filter: Callable[[list[dict]], list[dict]] | None = None,
    scoring_hook: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    """Fetch and normalize YouTube data for master_source ingestion.

    This function is the single provider entrypoint and does not write CSV.
    """
    if not queries:
        print("[youtube_provider] empty query list")
        return []

    cfg = config or YouTubeProviderConfig()
    api_client = client or YouTubeApiClient(config=cfg)

    all_ids: list[str] = []
    for query in queries:
        query = query.strip()
        if not query:
            continue
        ids = api_client.search_video_ids(query)
        all_ids.extend(ids)

    unique_ids = list(dict.fromkeys(all_ids))
    details = api_client.fetch_videos_details(unique_ids)
    normalized = [normalize_youtube_item(item) for item in details]

    valid = validate_normalized_items(normalized)
    filtered = (quality_filter or default_quality_filter)(valid)
    scored = (scoring_hook or default_scoring_hook)(filtered)

    print(
        "[youtube_provider] done | "
        f"queries={len(queries)} ids={len(unique_ids)} valid={len(valid)} final={len(scored)}"
    )
    return scored


if __name__ == "__main__":
    # Demo local run; requires YOUTUBE_API_KEY in environment.
    demo_queries = ["python automation", "youtube shorts growth"]
    try:
        results = fetch_youtube_data(demo_queries)
        print(f"[youtube_provider] demo fetched: {len(results)}")
        for row in results[:5]:
            print(row)
    except YouTubeQuotaExceededError as exc:
        print(f"[youtube_provider] quota error: {exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"[youtube_provider] demo failed: {exc}")
