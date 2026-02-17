"""Tests for providers.youtube_provider with mocked API responses."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from providers.youtube_provider import (
    MemoryCache,
    YouTubeApiClient,
    YouTubeProviderConfig,
    YouTubeQuotaExceededError,
    export_telemetry,
    fetch_youtube_data,
    load_queries,
)


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeSearchResource:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = 0

    def list(self, **kwargs):
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return FakeRequest(payload)


class FakeVideosResource:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def list(self, **kwargs):
        self.calls += 1
        return FakeRequest(self.payload)


class FakeQuotaRequest:
    def execute(self):
        raise RuntimeError("quotaExceeded")


class FakeQuotaSearchResource:
    def list(self, **kwargs):
        return FakeQuotaRequest()


class FakeQuotaService:
    def search(self):
        return FakeQuotaSearchResource()

    def videos(self):
        return FakeVideosResource({"items": []})


class FakeService:
    def __init__(self, search_payloads, videos_payload):
        self._search = FakeSearchResource(search_payloads)
        self._videos = FakeVideosResource(videos_payload)

    def search(self):
        return self._search

    def videos(self):
        return self._videos


class YouTubeProviderTests(unittest.TestCase):
    def setUp(self):
        search_payloads = [
            {
                "items": [
                    {"id": {"videoId": "vid1"}},
                    {"id": {"videoId": "vid2"}},
                ],
                "nextPageToken": None,
            }
        ]
        videos_payload = {
            "items": [
                {
                    "id": "vid1",
                    "snippet": {
                        "title": "Video One",
                        "channelTitle": "Channel A",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "description": "desc",
                    },
                    "statistics": {
                        "viewCount": "100",
                        "likeCount": "5",
                        "commentCount": "2",
                    },
                },
                {
                    "id": "vid2",
                    "snippet": {
                        "title": "Video Two",
                        "channelTitle": "Channel B",
                        "publishedAt": "2024-01-02T00:00:00Z",
                        "description": "desc2",
                    },
                    "statistics": {
                        "viewCount": "250",
                        "likeCount": "10",
                        "commentCount": "4",
                    },
                },
            ]
        }
        fake_service = FakeService(search_payloads, videos_payload)
        self.client = YouTubeApiClient(
            config=YouTubeProviderConfig(api_key="dummy", max_results_per_query=10, max_pages=1),
            cache=MemoryCache(ttl_seconds=300),
            service=fake_service,
        )

    def test_fetch_youtube_data_returns_normalized_rows(self):
        rows = fetch_youtube_data(
            [{"query": "automation", "priority": "HIGH", "max_results": 10, "min_views": 0}],
            client=self.client,
            telemetry_path=Path("telemetry") / "test_fetch.json",
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["platform"], "youtube")
        self.assertIn("source_extra", rows[0])
        self.assertIsInstance(rows[0]["views"], int)

    def test_cache_reduces_search_calls(self):
        telemetry = {}
        first = self.client.search_video_ids(
            {"query": "automation", "max_results": 10, "max_pages": 1}, telemetry
        )
        second = self.client.search_video_ids(
            {"query": "automation", "max_results": 10, "max_pages": 1}, telemetry
        )
        self.assertEqual(first, second)
        self.assertEqual(self.client.service.search().calls, 1)

    def test_quota_error_is_raised_explicitly(self):
        quota_client = YouTubeApiClient(
            config=YouTubeProviderConfig(api_key="dummy", max_results_per_query=5, max_pages=1),
            cache=MemoryCache(ttl_seconds=300),
            service=FakeQuotaService(),
        )

        with self.assertRaises(YouTubeQuotaExceededError):
            fetch_youtube_data(
                [{"query": "automation", "priority": "HIGH", "max_results": 5, "min_views": 0}],
                client=quota_client,
            )

    def test_load_queries_and_min_views_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "queries.csv"
            csv_path.write_text(
                "query,priority,max_results,min_views\n"
                "automation,HIGH,10,200\n",
                encoding="utf-8",
            )
            queries = load_queries(str(csv_path))
            rows = fetch_youtube_data(
                queries,
                client=self.client,
                telemetry_path=Path(tmpdir) / "telemetry.json",
            )
            self.assertEqual(len(rows), 1)
            self.assertGreaterEqual(rows[0]["views"], 200)

    def test_export_telemetry_writes_json_and_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            telemetry = {"summary": {"rows_final": 2, "api_search_calls": 1}}
            out_path = export_telemetry(telemetry, Path(tmpdir) / "run.json")
            self.assertTrue(out_path.exists())
            self.assertTrue(out_path.with_suffix(".csv").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
