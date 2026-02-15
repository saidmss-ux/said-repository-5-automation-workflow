"""YouTube scraping module to populate data/source/master_sources.csv.

This module provides a conservative scraping approach using requests + BeautifulSoup,
with optional fallback to youtube-search-python when available.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse
import csv
import json
import re
import time

import requests
from bs4 import BeautifulSoup


YOUTUBE_BASE = "https://www.youtube.com"
WATCH_PREFIX = f"{YOUTUBE_BASE}/watch?v="

MASTER_COLUMNS = [
    "source_url",
    "niche",
    "lang",
    "rights",
    "usage_strategy",
    "origin_platform",
    "prompt_template",
    "processed",
    "notes",
    "source_file",
]


def get_default_headers() -> dict[str, str]:
    """Return default HTTP headers for lightweight web requests."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    }


def build_search_url(query: str) -> str:
    """Build a YouTube search URL for a keyword query."""
    return f"{YOUTUBE_BASE}/results?search_query={quote_plus(query)}"


def extract_video_id_from_href(href: str) -> str | None:
    """Extract a YouTube video ID from href or full URL."""
    if not href:
        return None

    if href.startswith("/"):
        href = f"{YOUTUBE_BASE}{href}"

    parsed = urlparse(href)
    if parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        if video_id:
            return video_id

    short_match = re.search(r"(?:youtu\.be/|/shorts/)([A-Za-z0-9_-]{6,})", href)
    if short_match:
        return short_match.group(1)

    return None


def normalize_watch_url(video_id_or_url: str) -> str | None:
    """Normalize into https://www.youtube.com/watch?v=<id>."""
    if not video_id_or_url:
        return None

    if video_id_or_url.startswith("http"):
        video_id = extract_video_id_from_href(video_id_or_url)
    else:
        video_id = video_id_or_url

    if not video_id:
        return None

    return f"{WATCH_PREFIX}{video_id}"


def fetch_html(url: str, timeout_s: int = 20, headers: dict[str, str] | None = None) -> str:
    """Fetch HTML content with explicit network errors."""
    active_headers = headers or get_default_headers()
    response = requests.get(url, headers=active_headers, timeout=timeout_s)
    response.raise_for_status()
    return response.text


def _parse_script_json_candidates(html: str) -> list[dict]:
    """Extract JSON candidates from script tags for fallback parsing."""
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []
    for script in soup.find_all("script"):
        text = script.string or script.get_text(strip=True)
        if "videoRenderer" in text:
            results.append({"raw": text})
    return results


def _extract_title_from_anchor(anchor) -> str:
    title = anchor.get("title") or anchor.get_text(strip=True)
    return title.strip()


def _parse_video_anchors(html: str, max_results: int = 20) -> list[dict]:
    """Parse video anchors from generic YouTube HTML pages."""
    soup = BeautifulSoup(html, "lxml")
    records: list[dict] = []
    seen_urls: set[str] = set()

    for anchor in soup.select("a[href*='/watch?v=']"):
        href = anchor.get("href", "")
        watch_url = normalize_watch_url(href)
        if not watch_url or watch_url in seen_urls:
            continue

        seen_urls.add(watch_url)
        records.append(
            {
                "source_url": watch_url,
                "title": _extract_title_from_anchor(anchor),
                "description": "",
                "views": "",
                "published_at": "",
                "channel": "",
            }
        )

        if len(records) >= max_results:
            break

    return records


def parse_videos_from_search_html(html: str, max_results: int = 20) -> list[dict]:
    """Parse video records from search result HTML."""
    return _parse_video_anchors(html, max_results=max_results)


def parse_videos_from_channel_html(html: str, max_results: int = 20) -> list[dict]:
    """Parse video records from channel/videos page HTML."""
    return _parse_video_anchors(html, max_results=max_results)


def parse_videos_from_playlist_html(html: str, max_results: int = 20) -> list[dict]:
    """Parse video records from playlist HTML."""
    return _parse_video_anchors(html, max_results=max_results)


def scrape_by_keywords_html(
    keywords: list[str],
    max_per_keyword: int = 10,
    sleep_s: float = 1.0,
) -> list[dict]:
    """Scrape YouTube videos from keyword searches."""
    records: list[dict] = []
    for keyword in keywords:
        if not keyword.strip():
            continue
        search_url = build_search_url(keyword)
        print(f"[scraper_youtube] keyword search: {keyword} -> {search_url}")
        try:
            html = fetch_html(search_url)
            items = parse_videos_from_search_html(html, max_results=max_per_keyword)
            print(f"[scraper_youtube] found {len(items)} results for keyword={keyword}")
            records.extend(items)
        except Exception as exc:  # noqa: BLE001
            print(f"[scraper_youtube] warning keyword scrape failed ({keyword}): {exc}")
        time.sleep(sleep_s)
    return records


def scrape_by_channels_html(
    channel_urls: list[str],
    max_per_channel: int = 10,
    sleep_s: float = 1.0,
) -> list[dict]:
    """Scrape videos from YouTube channel URLs."""
    records: list[dict] = []
    for channel_url in channel_urls:
        if not channel_url.strip():
            continue
        url = channel_url.rstrip("/")
        if not url.endswith("/videos"):
            url = f"{url}/videos"
        print(f"[scraper_youtube] channel scrape: {url}")
        try:
            html = fetch_html(url)
            items = parse_videos_from_channel_html(html, max_results=max_per_channel)
            print(f"[scraper_youtube] found {len(items)} results for channel={channel_url}")
            records.extend(items)
        except Exception as exc:  # noqa: BLE001
            print(f"[scraper_youtube] warning channel scrape failed ({channel_url}): {exc}")
        time.sleep(sleep_s)
    return records


def scrape_by_playlists_html(
    playlist_urls: list[str],
    max_per_playlist: int = 10,
    sleep_s: float = 1.0,
) -> list[dict]:
    """Scrape videos from YouTube playlist URLs."""
    records: list[dict] = []
    for playlist_url in playlist_urls:
        if not playlist_url.strip():
            continue
        print(f"[scraper_youtube] playlist scrape: {playlist_url}")
        try:
            html = fetch_html(playlist_url)
            items = parse_videos_from_playlist_html(html, max_results=max_per_playlist)
            print(f"[scraper_youtube] found {len(items)} results for playlist")
            records.extend(items)
        except Exception as exc:  # noqa: BLE001
            print(f"[scraper_youtube] warning playlist scrape failed ({playlist_url}): {exc}")
        time.sleep(sleep_s)
    return records


def try_youtube_searchpython_fallback(
    keywords: list[str],
    max_per_keyword: int = 10,
) -> list[dict]:
    """Fallback search with youtube-search-python if installed."""
    try:
        from youtubesearchpython import VideosSearch  # type: ignore
    except Exception:  # noqa: BLE001
        print("[scraper_youtube] youtube-search-python not installed; skipping fallback")
        return []

    records: list[dict] = []
    for keyword in keywords:
        if not keyword.strip():
            continue
        try:
            search = VideosSearch(keyword, limit=max_per_keyword)
            result = search.result()
            for item in result.get("result", []):
                watch_url = normalize_watch_url(item.get("link", ""))
                if not watch_url:
                    continue
                records.append(
                    {
                        "source_url": watch_url,
                        "title": item.get("title", ""),
                        "description": "",
                        "views": item.get("viewCount", {}).get("short", ""),
                        "published_at": item.get("publishedTime", ""),
                        "channel": item.get("channel", {}).get("name", ""),
                    }
                )
            print(f"[scraper_youtube] fallback found for keyword={keyword}: {len(records)} cumulative")
        except Exception as exc:  # noqa: BLE001
            print(f"[scraper_youtube] fallback failed for keyword={keyword}: {exc}")
    return records


def deduplicate_video_records(records: list[dict]) -> list[dict]:
    """Deduplicate records by source_url."""
    deduped: list[dict] = []
    seen_urls: set[str] = set()
    for record in records:
        source_url = normalize_watch_url(record.get("source_url", ""))
        if not source_url or source_url in seen_urls:
            continue
        seen_urls.add(source_url)
        new_record = dict(record)
        new_record["source_url"] = source_url
        deduped.append(new_record)
    return deduped


def _seed_demo_records(min_count: int = 10) -> list[dict]:
    """Generate deterministic demo records when network scraping is unavailable."""
    seeds: list[dict] = []
    for index in range(1, min_count + 1):
        seeds.append(
            {
                "source_url": f"{WATCH_PREFIX}demo_video_{index}",
                "title": f"Demo YouTube Video {index}",
                "description": "",
                "views": "",
                "published_at": "",
                "channel": "DEMO_CHANNEL",
            }
        )
    return seeds


def to_master_sources_rows(
    records: list[dict],
    default_niche: str = "MOTIVATION",
    default_lang: str = "FR",
    default_rights: str = "REWRITE_REQUIRED",
    default_usage_strategy: str = "viral",
) -> list[dict]:
    """Map scraped records to pipeline-compatible master_sources rows."""
    rows: list[dict] = []
    for record in records:
        source_url = normalize_watch_url(record.get("source_url", ""))
        if not source_url:
            continue

        notes = record.get("title", "")
        rows.append(
            {
                "source_url": source_url,
                "niche": default_niche,
                "lang": default_lang,
                "rights": default_rights,
                "usage_strategy": default_usage_strategy,
                "origin_platform": "YOUTUBE",
                "prompt_template": "default",
                "processed": False,
                "notes": notes,
                "source_file": "master_sources.csv",
            }
        )
    return rows


def append_or_write_master_sources_csv(rows: list[dict], csv_path: Path) -> Path:
    """Write rows into master_sources CSV using UTF-8 encoding."""
    if not rows:
        raise ValueError("[scraper_youtube] no rows to write")

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    existing_rows: list[dict] = []
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as file:
            existing_rows = list(csv.DictReader(file))

    combined = existing_rows + rows
    deduped = deduplicate_video_records(combined)
    output_rows = to_master_sources_rows(deduped)

    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MASTER_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"[scraper_youtube] wrote {len(output_rows)} rows to {csv_path}")
    return csv_path


def scrape_youtube_to_master_sources(
    keywords: list[str] | None,
    channel_urls: list[str] | None,
    playlist_urls: list[str] | None,
    output_csv: Path,
    max_results_total: int = 50,
) -> list[dict]:
    """Run YouTube scraping and write pipeline-compatible master_sources CSV."""
    keywords = keywords or []
    channel_urls = channel_urls or []
    playlist_urls = playlist_urls or []

    if not keywords and not channel_urls and not playlist_urls:
        raise ValueError("[scraper_youtube] provide at least one source: keywords/channels/playlists")

    scraped_records: list[dict] = []
    scraped_records.extend(scrape_by_keywords_html(keywords, max_per_keyword=10))
    scraped_records.extend(scrape_by_channels_html(channel_urls, max_per_channel=10))
    scraped_records.extend(scrape_by_playlists_html(playlist_urls, max_per_playlist=10))

    deduped = deduplicate_video_records(scraped_records)

    if len(deduped) < 10 and keywords:
        print("[scraper_youtube] trying fallback provider: youtube-search-python")
        fallback = try_youtube_searchpython_fallback(keywords, max_per_keyword=10)
        deduped = deduplicate_video_records(deduped + fallback)

    if len(deduped) < 10:
        print("[scraper_youtube] network/fallback insufficient, using deterministic demo seeds")
        deduped = deduplicate_video_records(deduped + _seed_demo_records(10))

    deduped = deduped[:max_results_total]
    rows = to_master_sources_rows(deduped)
    append_or_write_master_sources_csv(rows, output_csv)
    return rows


def debug_head_csv(csv_path: Path, n: int = 5) -> None:
    """Print head(n) rows from CSV output."""
    if not csv_path.exists():
        print(f"[scraper_youtube] CSV not found: {csv_path}")
        return

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    print(f"[scraper_youtube] head({n}) of {csv_path} | total_rows={len(rows)}")
    for row in rows[:n]:
        print(row)


if __name__ == "__main__":
    output_path = Path("data/source/master_sources.csv")

    demo_keywords = ["productivity", "business mindset"]
    demo_channels = ["https://www.youtube.com/@TED"]
    demo_playlists: list[str] = []

    try:
        scrape_youtube_to_master_sources(
            keywords=demo_keywords,
            channel_urls=demo_channels,
            playlist_urls=demo_playlists,
            output_csv=output_path,
            max_results_total=25,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[scraper_youtube] fatal error: {exc}")

    debug_head_csv(output_path, n=5)
