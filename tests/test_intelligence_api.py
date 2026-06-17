# -*- coding: utf-8 -*-
"""API contract tests for intelligence source endpoints."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager

RSS_FIXTURE = b'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><item><title>Market event</title><link>https://news.example.com/market-event</link><description>Evidence summary</description></item></channel></rss>'


class IntelligenceApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_PATH"] = os.path.join(self._temp_dir.name, "api_intel.db")
        Config._instance = None
        DatabaseManager.reset_instance()
        self.client = TestClient(create_app(static_dir=Path(self._temp_dir.name)))

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config._instance = None
        os.environ.pop("DATABASE_PATH", None)
        self._temp_dir.cleanup()

    def _mock_response(self):
        response = Mock()
        response.content = RSS_FIXTURE
        response.url = "https://feeds.example.com/rss.xml"
        response.raise_for_status.return_value = None
        return response

    def test_create_fetch_and_query_items(self) -> None:
        create_resp = self.client.post("/api/v1/intelligence/sources", json={"name": "api-feed", "url": "https://feeds.example.com/rss.xml", "source_type": "rss", "scope_type": "market", "market": "cn"})
        self.assertEqual(create_resp.status_code, 200)
        source_id = create_resp.json()["id"]
        with patch("src.services.intelligence_service.requests.get", return_value=self._mock_response()):
            fetch_resp = self.client.post(f"/api/v1/intelligence/sources/{source_id}/fetch")
        self.assertEqual(fetch_resp.status_code, 200)
        self.assertEqual(fetch_resp.json()["saved_count"], 1)
        list_resp = self.client.get("/api/v1/intelligence/items", params={"scope_type": "market", "market": "cn"})
        self.assertEqual(list_resp.status_code, 200)
        body = list_resp.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["url"], "https://news.example.com/market-event")

    def test_rejects_private_source_url(self) -> None:
        resp = self.client.post("/api/v1/intelligence/sources", json={"name": "bad", "url": "http://localhost/rss.xml", "scope_type": "market"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "validation_error")


if __name__ == "__main__":
    unittest.main()
