# -*- coding: utf-8 -*-
"""Tests for configurable persisted intelligence sources."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.config import Config
from src.repositories.intelligence_repo import IntelligenceRepository
from src.services.intelligence_service import IntelligenceService, IntelligenceServiceError
from src.storage import DatabaseManager, IntelligenceItem

RSS_FIXTURE = b'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>\n<item><title>Policy support lifts AI supply chain</title><link>https://news.example.com/a</link><description>Market-level catalyst with evidence link.</description><pubDate>Wed, 17 Jun 2026 08:00:00 GMT</pubDate></item>\n<item><title>Second item</title><link>https://news.example.com/b</link><description>Second summary.</description></item>\n</channel></rss>'


class IntelligenceServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_PATH"] = os.path.join(self._temp_dir.name, "intelligence.db")
        os.environ["NEWS_INTEL_RETENTION_DAYS"] = "30"
        os.environ["NEWS_INTEL_MAX_ITEMS_PER_SOURCE"] = "50"
        os.environ["NEWS_INTEL_FETCH_TIMEOUT_SEC"] = "3"
        Config._instance = None
        DatabaseManager.reset_instance()
        self.service = IntelligenceService()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config._instance = None
        for key in ["DATABASE_PATH", "NEWS_INTEL_RETENTION_DAYS", "NEWS_INTEL_MAX_ITEMS_PER_SOURCE", "NEWS_INTEL_FETCH_TIMEOUT_SEC"]:
            os.environ.pop(key, None)
        self._temp_dir.cleanup()

    def _mock_response(self):
        response = Mock()
        response.content = RSS_FIXTURE
        response.url = "https://feeds.example.com/rss.xml"
        response.raise_for_status.return_value = None
        return response

    def test_create_fetch_and_deduplicate_rss_source(self) -> None:
        source = self.service.create_source({
            "name": "market-feed", "url": "https://feeds.example.com/rss.xml",
            "source_type": "rss", "scope_type": "market", "market": "cn",
        })
        with patch("src.services.intelligence_service.requests.get", return_value=self._mock_response()):
            first = self.service.fetch_source(source["id"])
            second = self.service.fetch_source(source["id"])
        self.assertEqual(first["fetched_count"], 2)
        self.assertEqual(first["saved_count"], 2)
        self.assertEqual(second["saved_count"], 0)
        items = self.service.list_items(scope_type="market", market="cn")
        self.assertEqual(items["total"], 2)
        self.assertEqual(items["items"][0]["scope_type"], "market")
        self.assertTrue(items["items"][0]["url"].startswith("https://news.example.com/"))

    def test_private_network_url_is_rejected(self) -> None:
        with self.assertRaises(IntelligenceServiceError):
            self.service.create_source({"name": "bad", "url": "http://127.0.0.1:8000/rss.xml", "scope_type": "market"})

    def test_fetch_enabled_sources_is_fail_open(self) -> None:
        self.service.create_source({"name": "good-feed", "url": "https://feeds.example.com/rss.xml", "scope_type": "market"})
        bad = self.service.create_source({"name": "bad-feed", "url": "https://bad.example.com/rss.xml", "scope_type": "market"})

        def fake_get(url, **kwargs):
            if "bad" in url:
                raise RuntimeError("network token=secret should not leak")
            return self._mock_response()
        with patch("src.services.intelligence_service.requests.get", side_effect=fake_get):
            result = self.service.fetch_enabled_sources()
        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["saved_count"], 2)
        failures = [item for item in result["results"] if not item["ok"]]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["source_id"], bad["id"])
        self.assertIn("token=***", failures[0]["error"])
        self.assertNotIn("secret", failures[0]["error"])

    def test_retention_removes_old_items(self) -> None:
        repo = IntelligenceRepository()
        old_time = datetime.now() - timedelta(days=60)
        repo.upsert_items([{"source_name": "legacy", "source_type": "rss", "title": "old", "summary": "old item", "url": "https://news.example.com/old", "source": "legacy", "published_at": old_time, "fetched_at": old_time, "scope_type": "market", "scope_value": None, "market": "cn"}])
        self.assertEqual(repo.apply_retention(30), 1)
        with DatabaseManager.get_instance().get_session() as session:
            self.assertEqual(session.query(IntelligenceItem).count(), 0)


if __name__ == "__main__":
    unittest.main()
