"""Standalone YouTube provider for master_source architecture.

This module keeps YouTube ingestion independent from CSV export logic used by the
main pipeline. It focuses on:
- query loading (simple CSV contract),
- quota-aware API calls,
- normalization to master_source schema,
- telemetry capture and export (JSON + CSV),
- clear hooks for quality filtering and scoring.

Quota notes (YouTube Data API v3):
- search.list: expensive endpoint (commonly ~100 quota units / call).
- videos.list: low-cost endpoint (commonly ~1 quota unit / call).

To reduce quota consumption:
1) Use search.list only to gather video IDs.
2) Batch metadata retrieval through videos.list in chunks up to 50 IDs.
3) Deduplicate IDs globally before details calls.
4) Use in-memory TTL caching to avoid repeated requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import csv
import json
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


REQUIRED_QUERY_COLUMNS = {"query", "priority", "max_results", "min_views"}


@dataclass
class YouTubeProviderConfig:
    """Runtime configuration for the YouTube provider."""

    api_key: str = YOUTUBE_API_KEY
    max_results_per_query: int = YOUTUBE_MAX_RESULTS_PER_QUERY
    max_pages: int = YOUTUBE_MAX_PAGES
    search_part: str = YOUTUBE_SEARCH_PART
    videos_part: str = YOUTUBE_VIDEOS_PART
    cache_ttl_seconds: int = YOUTUBE_CACHE_TTL_SECONDS
    request_max_retries: int = 3
    backoff_seconds: float = 1.0


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

    def _safe_execute(self, request: Any, telemetry: dict | None = None) -> dict:
        """Execute an API request with retry/backoff and explicit quota handling."""
        retries = max(1, self.config.request_max_retries)

        for attempt in range(1, retries + 1):
            try:
                return request.execute()
            except HttpError as exc:
                message = str(exc)
                if "quotaExceeded" in message or "dailyLimitExceeded" in message:
                    raise YouTubeQuotaExceededError(
                        "[youtube_provider] YouTube API quota exceeded"
                    ) from exc

                if telemetry is not None:
                    telemetry["http_errors"] = telemetry.get("http_errors", 0) + 1

                if attempt >= retries:
                    raise RuntimeError(
                        f"[youtube_provider] YouTube HTTP error after retries: {exc}"
                    ) from exc

                sleep_seconds = self.config.backoff_seconds * (2 ** (attempt - 1))
                print(
                    "[youtube_provider] HTTP error, retrying "
                    f"attempt={attempt}/{retries} sleep={sleep_seconds:.1f}s"
                )
                time.sleep(sleep_seconds)
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                if "quotaExceeded" in message or "dailyLimitExceeded" in message:
                    raise YouTubeQuotaExceededError(
                        "[youtube_provider] YouTube API quota exceeded"
                    ) from exc

                if telemetry is not None:
                    telemetry["unexpected_errors"] = telemetry.get(
                        "unexpected_errors", 0
                    ) + 1
                if attempt >= retries:
                    raise RuntimeError(
                        f"[youtube_provider] Unexpected API error after retries: {exc}"
                    ) from exc

                sleep_seconds = self.config.backoff_seconds * (2 ** (attempt - 1))
                print(
                    "[youtube_provider] Unexpected error, retrying "
                    f"attempt={attempt}/{retries} sleep={sleep_seconds:.1f}s"
                )
                time.sleep(sleep_seconds)

        return {}

    def search_video_ids(self, query_spec: dict, telemetry: dict) -> list[str]:
        """Get video IDs for one query using paginated search.list calls."""
        query = str(query_spec.get("query", "")).strip()
        max_results = int(query_spec.get("max_results", self.config.max_results_per_query))
        max_pages = int(query_spec.get("max_pages", self.config.max_pages))

        cache_key = f"search_ids::{query}::{max_results}::{max_pages}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            print(f"[youtube_provider] cache hit for query='{query}'")
            telemetry["cache_hits"] = telemetry.get("cache_hits", 0) + 1
            return cached

        collected: list[str] = []
        next_page_token = None
        remaining = max_results

        for _ in range(max_pages):
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
            payload = self._safe_execute(request=request, telemetry=telemetry)

            telemetry["api_search_calls"] = telemetry.get("api_search_calls", 0) + 1
            telemetry["quota_units_estimated"] = telemetry.get(
                "quota_units_estimated", 0
            ) + 100

            for item in payload.get("items", []):
                video_id = item.get("id", {}).get("videoId")
                if video_id:
                    collected.append(video_id)

            remaining = max_results - len(collected)
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

    def fetch_videos_details(self, video_ids: list[str], telemetry: dict) -> list[dict]:
        """Fetch detailed metadata for video IDs using videos.list batching."""
        if not video_ids:
            return []

        details: list[dict] = []
        for start in range(0, len(video_ids), 50):
            chunk = video_ids[start : start + 50]
            chunk_key = f"videos::{','.join(chunk)}::{self.config.videos_part}"
            cached = self.cache.get(chunk_key)
            if cached is not None:
                telemetry["cache_hits"] = telemetry.get("cache_hits", 0) + 1
                details.extend(cached)
                continue

            request = self.service.videos().list(
                part=self.config.videos_part,
                id=",".join(chunk),
                maxResults=len(chunk),
            )
            payload = self._safe_execute(request=request, telemetry=telemetry)

            telemetry["api_videos_calls"] = telemetry.get("api_videos_calls", 0) + 1
            telemetry["quota_units_estimated"] = telemetry.get(
                "quota_units_estimated", 0
            ) + len(chunk)

            items = payload.get("items", [])
            self.cache.set(chunk_key, items)
            details.extend(items)

        return details


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return 0


def load_queries(file_path: str) -> list[dict]:
    """Load structured query specs from CSV.

    Expected columns: query, priority, max_results, min_views
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"[youtube_provider] queries file not found: {path}")

    rows: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        if not REQUIRED_QUERY_COLUMNS.issubset(columns):
            raise ValueError(
                "[youtube_provider] invalid queries CSV columns. "
                f"Expected at least: {sorted(REQUIRED_QUERY_COLUMNS)}"
            )

        for raw in reader:
            query = str(raw.get("query", "")).strip()
            if not query:
                continue
            row = {
                "query": query,
                "priority": str(raw.get("priority", "MEDIUM")).strip().upper() or "MEDIUM",
                "max_results": _safe_int(raw.get("max_results", 0))
                or YOUTUBE_MAX_RESULTS_PER_QUERY,
                "min_views": _safe_int(raw.get("min_views", 0)),
            }
            rows.append(row)

    print(f"[youtube_provider] loaded {len(rows)} queries from {path}")
    return rows


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
    required = {
        "platform",
        "id",
        "title",
        "channel",
        "views",
        "published_at",
        "source_extra",
    }
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


def _build_default_telemetry_path() -> Path:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return Path("telemetry") / f"youtube_run_{timestamp}.json"


def export_telemetry(telemetry: dict, path: str | Path) -> Path:
    """Export telemetry as JSON and companion CSV summary."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(telemetry, handle, ensure_ascii=False, indent=2)

    csv_path = output_path.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["metric", "value"])
        writer.writeheader()
        for key, value in telemetry.get("summary", {}).items():
            writer.writerow({"metric": key, "value": value})

    print(f"[youtube_provider] telemetry exported: {output_path}")
    print(f"[youtube_provider] telemetry summary csv: {csv_path}")
    return output_path


def fetch_youtube_data(
    queries: list[dict] | list[str],
    config: YouTubeProviderConfig | None = None,
    client: YouTubeApiClient | None = None,
    quality_filter: Callable[[list[dict]], list[dict]] | None = None,
    scoring_hook: Callable[[list[dict]], list[dict]] | None = None,
    telemetry_path: str | Path | None = None,
) -> list[dict]:
    """Fetch and normalize YouTube data for master_source ingestion.

    Args:
        queries: Either a list of strings or list of structured dicts with
            keys: query, priority, max_results, min_views.
    """
    if not queries:
        print("[youtube_provider] empty query list")
        return []

    cfg = config or YouTubeProviderConfig()
    api_client = client or YouTubeApiClient(config=cfg)

    query_specs: list[dict] = []
    for query in queries:
        if isinstance(query, dict):
            query_specs.append(
                {
                    "query": str(query.get("query", "")).strip(),
                    "priority": str(query.get("priority", "MEDIUM")).upper(),
                    "max_results": _safe_int(query.get("max_results", 0))
                    or cfg.max_results_per_query,
                    "min_views": _safe_int(query.get("min_views", 0)),
                }
            )
        else:
            query_specs.append(
                {
                    "query": str(query).strip(),
                    "priority": "MEDIUM",
                    "max_results": cfg.max_results_per_query,
                    "min_views": 0,
                }
            )

    telemetry: dict[str, Any] = {
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "query_count": len(query_specs),
        "api_search_calls": 0,
        "api_videos_calls": 0,
        "quota_units_estimated": 0,
        "cache_hits": 0,
        "http_errors": 0,
        "unexpected_errors": 0,
        "queries": [],
    }

    all_rows: list[dict] = []
    global_ids: list[str] = []

    for query_spec in query_specs:
        query = query_spec.get("query", "")
        if not query:
            continue

        query_telemetry = {
            "query": query,
            "priority": query_spec.get("priority"),
            "max_results": query_spec.get("max_results"),
            "min_views": query_spec.get("min_views"),
        }

        ids = api_client.search_video_ids(query_spec=query_spec, telemetry=telemetry)
        global_ids.extend(ids)

        unique_ids = list(dict.fromkeys(ids))
        details = api_client.fetch_videos_details(video_ids=unique_ids, telemetry=telemetry)
        normalized = [normalize_youtube_item(item) for item in details]
        valid = validate_normalized_items(normalized)
        min_views = _safe_int(query_spec.get("min_views", 0))
        filtered_by_views = [row for row in valid if row.get("views", 0) >= min_views]

        for row in filtered_by_views:
            row["source_extra"]["query"] = query
            row["source_extra"]["query_priority"] = query_spec.get("priority", "MEDIUM")

        query_telemetry["ids"] = len(unique_ids)
        query_telemetry["valid_items"] = len(valid)
        query_telemetry["min_views_filtered_items"] = len(filtered_by_views)
        telemetry["queries"].append(query_telemetry)
        all_rows.extend(filtered_by_views)

    dedup_rows: list[dict] = []
    seen_ids: set[str] = set()
    for row in all_rows:
        row_id = row.get("id", "")
        if row_id and row_id not in seen_ids:
            seen_ids.add(row_id)
            dedup_rows.append(row)

    filtered = (quality_filter or default_quality_filter)(dedup_rows)
    scored = (scoring_hook or default_scoring_hook)(filtered)

    telemetry["finished_at"] = datetime.now(tz=timezone.utc).isoformat()
    telemetry["summary"] = {
        "queries": len(query_specs),
        "global_ids_collected": len(list(dict.fromkeys(global_ids))),
        "rows_after_dedup": len(dedup_rows),
        "rows_after_quality_filter": len(filtered),
        "rows_final": len(scored),
        "api_search_calls": telemetry.get("api_search_calls", 0),
        "api_videos_calls": telemetry.get("api_videos_calls", 0),
        "cache_hits": telemetry.get("cache_hits", 0),
        "quota_units_estimated": telemetry.get("quota_units_estimated", 0),
    }

    telemetry_output_path = Path(telemetry_path) if telemetry_path else _build_default_telemetry_path()
    export_telemetry(telemetry=telemetry, path=telemetry_output_path)

    print(
        "[youtube_provider] done | "
        f"queries={len(query_specs)} final={len(scored)} "
        f"quota_est={telemetry['summary']['quota_units_estimated']}"
    )
    return scored


if __name__ == "__main__":
    try:
        sample_queries_path = Path("queries") / "youtube_queries.csv"
        if sample_queries_path.exists():
            demo_queries = load_queries(str(sample_queries_path))
        else:
            demo_queries = [
                {
                    "query": "python automation",
                    "priority": "HIGH",
                    "max_results": 10,
                    "min_views": 0,
                }
            ]

        results = fetch_youtube_data(demo_queries)
        print(f"[youtube_provider] demo fetched: {len(results)}")
        for row in results[:5]:
            print(row)
    except YouTubeQuotaExceededError as exc:
        print(f"[youtube_provider] quota error: {exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"[youtube_provider] demo failed: {exc}")
